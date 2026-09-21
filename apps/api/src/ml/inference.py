"""
SIH26072 — Deep Neural Nowcaster Inference Engine v3
Loads PyTorch StormNowcasterMLP v3 weights and provides high-accuracy ML forecasts
using Monte Carlo Dropout ensemble averaging with optical flow fusion for stable,
non-linear trajectory predictions.
"""

import os
import torch
import numpy as np
from typing import Dict, List, Any, Optional
from src.config import settings
from src.ml.model import StormNowcasterMLP
from src.ml.trainer import WEIGHTS_PATH, SCALER_PATH, train_nowcaster_model


class StormMLInference:
    """
    Real-time inference manager for storm trajectory, reflectivity evolution,
    and probabilistic nowcasting.

    v3 improvements:
    - 18-feature input with optical flow velocity, divergence, curl
    - Feature normalization using saved StandardScaler params
    - 8 MC Dropout passes (vs 5) for better uncertainty estimates
    - Optical flow trajectory fusion (short-term: 70% OF, long-term: 60% ML)
    - Coordinate precision to 5 decimal places with cos(lat) correction
    - Gujarat bounding box clamping
    """

    MC_PASSES = 8  # Increased from 5 for more robust uncertainty

    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = StormNowcasterMLP(input_dim=18, hidden_dim=320, mc_dropout=0.1).to(self.device)
        self.loaded = False
        self.scaler_mean: Optional[np.ndarray] = None
        self.scaler_std: Optional[np.ndarray] = None
        self.load_model()

    def load_model(self):
        """Loads trained model weights and scaler from disk or triggers training."""
        try:
            if not os.path.exists(WEIGHTS_PATH):
                print("[WARN] PyTorch Nowcaster v3 weights not found. Training model now...")
                train_nowcaster_model(epochs=120)

            state_dict = torch.load(WEIGHTS_PATH, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self.loaded = True
            print(f"[OK] Loaded PyTorch StormNowcasterMLP v3 on {self.device}")

            # Load feature scaler
            if os.path.exists(SCALER_PATH):
                scaler_data = np.load(SCALER_PATH)
                self.scaler_mean = scaler_data["mean"]
                self.scaler_std = scaler_data["std"]
                print(f"[OK] Loaded feature scaler ({len(self.scaler_mean)} features)")
            else:
                print("[WARN] Feature scaler not found. Using raw features.")

        except Exception as e:
            print(f"[ERROR] Failed to load PyTorch Nowcaster model: {e}")
            self.loaded = False

    def predict_cell_nowcast(
        self,
        cell: Dict[str, Any],
        history_buffer: List[Dict[str, Any]],
        horizons_minutes: List[int] = [15, 30, 45, 60],
        optical_flow_trajectory: Optional[list] = None,
    ) -> Dict[str, Any]:
        """
        Calculates non-linear ML forecasts for a single tracked storm cell
        using Monte Carlo Dropout ensemble averaging, fused with optical flow.
        """
        if not self.loaded:
            self.load_model()

        # Extract 18-dim features
        features = self._extract_features(cell, history_buffer)

        # Apply normalization
        if self.scaler_mean is not None:
            features = (features - self.scaler_mean) / self.scaler_std

        x_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(self.device)

        # --- Monte Carlo Dropout Ensemble ---
        self._enable_mc_dropout()

        all_traj = []
        all_dbz = []
        all_ts = []
        all_lt = []

        for _ in range(self.MC_PASSES):
            with torch.no_grad():
                preds = self.model(x_tensor)
            all_traj.append(preds["trajectory_offsets"].squeeze(0).cpu().numpy())
            all_dbz.append(preds["dbz_forecasts"].squeeze(0).cpu().numpy())
            all_ts.append(preds["thunderstorm_probs"].squeeze(0).cpu().numpy())
            all_lt.append(preds["lightning_probs"].squeeze(0).cpu().numpy())

        # Restore eval mode
        self.model.eval()

        # Average across MC samples
        traj_offsets = np.mean(all_traj, axis=0)       # shape (4, 2)
        traj_std = np.std(all_traj, axis=0)             # shape (4, 2) — uncertainty
        dbz_forecasts = np.mean(all_dbz, axis=0)        # shape (4,)
        ts_probs = np.mean(all_ts, axis=0)              # shape (4,)
        lt_probs = np.mean(all_lt, axis=0)              # shape (4,)

        resolution_km = settings.mvp_grid_resolution_km
        center_lat = settings.mvp_center_lat
        center_lon = settings.mvp_center_lon
        grid_h, grid_w = settings.grid_height, settings.grid_width
        precision = settings.coordinate_precision

        curr_y = cell["centroid_y"]
        curr_x = cell["centroid_x"]

        forecasts = []
        trajectory_coords = [[float(cell["center_lon"]), float(cell["center_lat"])]]

        for idx, h in enumerate(horizons_minutes):
            dx, dy = float(traj_offsets[idx][0]), float(traj_offsets[idx][1])

            pred_y = float(curr_y) + dy
            pred_x = float(curr_x) + dx

            # Convert grid to lat/lon with cos(lat) correction
            pred_lat = float(center_lat + (pred_y - grid_h / 2) * (resolution_km / 111.0))
            cos_lat = np.cos(np.radians(pred_lat))
            pred_lon = float(center_lon + (pred_x - grid_w / 2) * (resolution_km / (111.0 * max(0.5, cos_lat))))

            # --- Optical Flow Fusion ---
            if optical_flow_trajectory and idx < len(optical_flow_trajectory):
                of_point = optical_flow_trajectory[idx]
                of_lat = of_point.get("lat", pred_lat)
                of_lon = of_point.get("lon", pred_lon)

                # Fusion weights: short-term favors optical flow, long-term favors ML
                if h <= 15:
                    of_weight = 0.70
                elif h <= 30:
                    of_weight = 0.55
                elif h <= 45:
                    of_weight = 0.40
                else:
                    of_weight = 0.30

                ml_weight = 1.0 - of_weight
                pred_lat = of_weight * of_lat + ml_weight * pred_lat
                pred_lon = of_weight * of_lon + ml_weight * pred_lon

            # Clamp to Gujarat bounding box
            pred_lat = float(np.clip(pred_lat, settings.gujarat_lat_min, settings.gujarat_lat_max))
            pred_lon = float(np.clip(pred_lon, settings.gujarat_lon_min, settings.gujarat_lon_max))

            # Principled uncertainty from MC Dropout std-dev
            traj_variance = float(np.sqrt(traj_std[idx][0] ** 2 + traj_std[idx][1] ** 2))
            base_uncertainty = max(2.0, 3.0 + (h / 10.0) * 1.5)
            mc_uncertainty = traj_variance * resolution_km * 2.0
            uncertainty_km = base_uncertainty + mc_uncertainty

            ts_prob = float(np.clip(ts_probs[idx], 0.05, 0.99))
            lt_prob = float(np.clip(lt_probs[idx], 0.05, 0.98))
            pred_dbz = float(np.clip(dbz_forecasts[idx], 10.0, 75.0))

            # Confidence score inversely proportional to MC variance
            confidence = float(np.clip(1.0 - traj_variance * 0.25, 0.3, 0.99))

            forecasts.append({
                "horizon_minutes": int(h),
                "predicted_lat": round(pred_lat, precision),
                "predicted_lon": round(pred_lon, precision),
                "predicted_dbz": round(pred_dbz, 1),
                "uncertainty_km": round(uncertainty_km, 1),
                "thunderstorm_probability": round(ts_prob, 2),
                "lightning_probability": round(lt_prob, 2),
                "confidence_score": round(confidence, 2),
            })

            trajectory_coords.append([round(pred_lon, precision), round(pred_lat, precision)])

        return {
            "smoothing_model": "PyTorch-DeepNowcaster-v3-MCDropout-OpticalFlow",
            "forecasts": forecasts,
            "trajectory_coords": trajectory_coords,
        }

    def _enable_mc_dropout(self):
        """Enable dropout layers for MC Dropout inference while keeping BatchNorm in eval mode."""
        for module in self.model.modules():
            if isinstance(module, torch.nn.Dropout):
                module.train()

    def _extract_features(self, cell: Dict[str, Any], history: List[Dict[str, Any]]) -> np.ndarray:
        """Constructs 18-dim feature vector for model input (expanded from 14)."""
        vx = cell.get("velocity_x", 0.6)
        vy = cell.get("velocity_y", -0.3)

        # Acceleration from history buffer
        ax, ay = 0.0, 0.0
        curvature = 0.0
        if len(history) >= 3:
            p1, p2, p3 = history[-3], history[-2], history[-1]
            vx1, vy1 = p2["x"] - p1["x"], p2["y"] - p1["y"]
            vx2, vy2 = p3["x"] - p2["x"], p3["y"] - p2["y"]
            ax = vx2 - vx1
            ay = vy2 - vy1

            # Angle difference (curvature)
            ang1 = np.arctan2(vx1, -vy1)
            ang2 = np.arctan2(vx2, -vy2)
            curvature = float(ang2 - ang1)

        max_dbz = cell.get("max_reflectivity_dbz", 45.0)
        mean_dbz = cell.get("mean_reflectivity_dbz", max_dbz * 0.75)

        # Reflectivity trend
        prev_dbz = history[-2].get("max_reflectivity_dbz", max_dbz) if len(history) >= 2 else max_dbz
        dbz_trend = float(max_dbz - prev_dbz)

        area_sq_km = cell.get("area_sq_km", 50.0)
        prev_area = history[-2].get("area_sq_km", area_sq_km) if len(history) >= 2 else area_sq_km
        d_area = float(area_sq_km - prev_area)

        lightning_rate = cell.get("lightning_rate", 10.0)
        prev_lt = history[-2].get("lightning_rate", lightning_rate) if len(history) >= 2 else lightning_rate
        d_lightning = float(lightning_rate - prev_lt)

        lat_offset = (cell.get("center_lat", settings.mvp_center_lat) - settings.mvp_center_lat)
        lon_offset = (cell.get("center_lon", settings.mvp_center_lon) - settings.mvp_center_lon)

        # Optical flow features (injected by tracker or zeroed)
        of_vx = cell.get("optical_flow_vx", 0.0)
        of_vy = cell.get("optical_flow_vy", 0.0)
        of_div = cell.get("optical_flow_divergence", 0.0)
        of_curl = cell.get("optical_flow_curl", 0.0)

        return np.array([
            vx, vy, ax, ay, max_dbz, mean_dbz, dbz_trend,
            area_sq_km, d_area, lightning_rate, d_lightning,
            lat_offset, lon_offset, curvature,
            of_vx, of_vy, of_div, of_curl,
        ], dtype=np.float32)


ml_inference = StormMLInference()
