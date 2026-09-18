"""
SIH26072 — Deep Neural Nowcaster Inference Engine
Loads PyTorch StormNowcasterMLP weights and provides high-accuracy ML forecasts.
"""

import os
import torch
import numpy as np
from typing import Dict, List, Any, Optional
from src.config import settings
from src.ml.model import StormNowcasterMLP
from src.ml.trainer import WEIGHTS_PATH, train_nowcaster_model


class StormMLInference:
    """
    Real-time inference manager for storm trajectory, reflectivity evolution,
    and probabilistic nowcasting.
    """

    def __init__(self, device: Optional[str] = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = StormNowcasterMLP(input_dim=14, hidden_dim=128).to(self.device)
        self.loaded = False
        self.load_model()

    def load_model(self):
        """Loads trained model weights from disk or triggers lightweight training."""
        try:
            if not os.path.exists(WEIGHTS_PATH):
                print("⚠️  PyTorch Nowcaster weights not found. Training model now...")
                train_nowcaster_model(epochs=25)
            
            state_dict = torch.load(WEIGHTS_PATH, map_location=self.device)
            self.model.load_state_dict(state_dict)
            self.model.eval()
            self.loaded = True
            print(f"🚀 Loaded PyTorch StormNowcasterMLP on {self.device}")
        except Exception as e:
            print(f"❌ Failed to load PyTorch Nowcaster model: {e}")
            self.loaded = False

    def predict_cell_nowcast(
        self,
        cell: Dict[str, Any],
        history_buffer: List[Dict[str, Any]],
        horizons_minutes: List[int] = [15, 30, 45, 60]
    ) -> Dict[str, Any]:
        """
        Calculates non-linear ML forecasts for a single tracked storm cell.
        """
        if not self.loaded:
            self.load_model()

        # Extract features
        features = self._extract_features(cell, history_buffer)
        x_tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0).to(self.device)

        with torch.no_grad():
            preds = self.model(x_tensor)

        traj_offsets = preds["trajectory_offsets"].squeeze(0).cpu().numpy()  # shape (4, 2)
        dbz_forecasts = preds["dbz_forecasts"].squeeze(0).cpu().numpy()      # shape (4,)
        ts_probs = preds["thunderstorm_probs"].squeeze(0).cpu().numpy()        # shape (4,)
        lt_probs = preds["lightning_probs"].squeeze(0).cpu().numpy()          # shape (4,)

        resolution_km = settings.mvp_grid_resolution_km
        center_lat = settings.mvp_center_lat
        center_lon = settings.mvp_center_lon
        grid_h, grid_w = settings.grid_height, settings.grid_width

        curr_y = cell["centroid_y"]
        curr_x = cell["centroid_x"]

        forecasts = []
        trajectory_coords = [[float(cell["center_lon"]), float(cell["center_lat"])]]

        for idx, h in enumerate(horizons_minutes):
            dx, dy = float(traj_offsets[idx][0]), float(traj_offsets[idx][1])
            
            pred_y = float(curr_y) + dy
            pred_x = float(curr_x) + dx

            pred_lat = float(center_lat + (pred_y - grid_h / 2) * (resolution_km / 111.0))
            pred_lon = float(center_lon + (pred_x - grid_w / 2) * (resolution_km / 111.0))

            # Dynamic non-linear uncertainty radius based on horizon and feature volatility
            volatility = float(abs(features[2]) + abs(features[3]) + abs(features[6]) * 0.1)
            uncertainty_km = max(2.5, 3.5 + (h / 10.0) * (1.8 + volatility * 0.5))

            ts_prob = float(np.clip(ts_probs[idx], 0.05, 0.99))
            lt_prob = float(np.clip(lt_probs[idx], 0.05, 0.98))
            pred_dbz = float(np.clip(dbz_forecasts[idx], 10.0, 75.0))

            forecasts.append({
                "horizon_minutes": int(h),
                "predicted_lat": float(round(pred_lat, 4)),
                "predicted_lon": float(round(pred_lon, 4)),
                "predicted_dbz": float(round(pred_dbz, 1)),
                "uncertainty_km": float(round(uncertainty_km, 1)),
                "thunderstorm_probability": float(round(ts_prob, 2)),
                "lightning_probability": float(round(lt_prob, 2)),
            })

            trajectory_coords.append([float(round(pred_lon, 4)), float(round(pred_lat, 4))])

        return {
            "smoothing_model": "PyTorch-DeepNowcaster-v2",
            "forecasts": forecasts,
            "trajectory_coords": trajectory_coords,
        }

    def _extract_features(self, cell: Dict[str, Any], history: List[Dict[str, Any]]) -> np.ndarray:
        """Constructs 14-dim feature vector for model input."""
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

        return np.array([
            vx, vy, ax, ay, max_dbz, mean_dbz, dbz_trend,
            area_sq_km, d_area, lightning_rate, d_lightning,
            lat_offset, lon_offset, curvature
        ], dtype=np.float32)


ml_inference = StormMLInference()
