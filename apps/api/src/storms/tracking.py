"""
Storm cell tracking — matches detected cells across consecutive radar scans.
Uses heavy EMA smoothing for jitter-free positions and trajectory averaging
across multiple prediction cycles for stable, non-flickering forecast paths.
"""

import numpy as np
from typing import Optional
from src.config import settings
from src.ml.inference import ml_inference


class StormTracker:
    """
    Tracks storm cells across time with:
    - Heavy coordinate EMA smoothing (alpha=0.12) to eliminate marker jumps
    - Velocity EMA smoothing (alpha=0.08) for gradual speed/direction changes
    - Rolling trajectory averager: stores last 10 ML prediction sets per cell
      and outputs element-wise mean → single stable "consensus" trajectory
    """

    def __init__(
        self,
        max_distance_km: float = 100.0,
        max_missing_frames: int = 5,
        coord_ema_alpha: float = 0.12,
        velocity_ema_alpha: float = 0.08,
        trajectory_window: int = 10,
    ):
        self.max_distance_km = max_distance_km
        self.max_missing_frames = max_missing_frames
        self.coord_ema_alpha = coord_ema_alpha
        self.velocity_ema_alpha = velocity_ema_alpha
        self.trajectory_window = trajectory_window

        self._next_id = 1000
        self._active_cells: dict[str, dict] = {}
        self._missing_count: dict[str, int] = {}
        self._smoothed_velocities: dict[str, tuple[float, float]] = {}
        self._history_buffers: dict[str, list[dict]] = {}

        # Rolling window of recent trajectory predictions per cell for averaging
        self._trajectory_averager: dict[str, list[list[list[float]]]] = {}
        # Rolling window of recent forecast dicts per cell
        self._forecast_averager: dict[str, list[list[dict]]] = {}

    # ------------------------------------------------------------------
    # Cell Update (match + smooth)
    # ------------------------------------------------------------------

    def update(self, detected_cells: list[dict], timestamp: str) -> list[dict]:
        """
        Match newly detected cells against previously tracked cells.
        Applies heavy coordinate + velocity EMA smoothing to eliminate jumps.
        """
        if not self._active_cells:
            tracked = []
            for cell in detected_cells:
                cell_id = cell.get("cell_id") or self._new_id()
                tracked_cell = {
                    **cell,
                    "cell_id": cell_id,
                    "timestamp": timestamp,
                    "movement_speed_kmh": cell.get("speed_kmh", 15.0),
                    "movement_direction_deg": cell.get("direction_deg", 45.0),
                    "trend": cell.get("trend", "steady"),
                    "lightning_rate": cell.get("lightning_rate", 12.0),
                }
                self._active_cells[cell_id] = tracked_cell
                self._missing_count[cell_id] = 0
                self._smoothed_velocities[cell_id] = (
                    cell.get("velocity_x", 0.6),
                    cell.get("velocity_y", -0.3),
                )
                self._history_buffers[cell_id] = [
                    {"x": cell["centroid_x"], "y": cell["centroid_y"], "timestamp": timestamp}
                ]
                tracked.append(tracked_cell)
            return tracked

        prev_ids = list(self._active_cells.keys())
        prev_cells = [self._active_cells[cid] for cid in prev_ids]

        matched_prev = set()
        matched_det = set()
        assignments = {}

        distances = []
        for i, prev in enumerate(prev_cells):
            for j, det in enumerate(detected_cells):
                d = self._haversine_km(
                    prev["center_lat"], prev["center_lon"],
                    det["center_lat"], det["center_lon"],
                )
                distances.append((d, i, j))

        distances.sort(key=lambda x: x[0])

        for dist, i, j in distances:
            if i in matched_prev or j in matched_det:
                continue
            if dist > self.max_distance_km:
                break
            assignments[j] = prev_ids[i]
            matched_prev.add(i)
            matched_det.add(j)

        tracked = []
        resolution_km = settings.mvp_grid_resolution_km
        time_step_hours = settings.mvp_time_step_minutes / 60.0

        for j, det in enumerate(detected_cells):
            if j in assignments:
                cell_id = assignments[j]
                prev = self._active_cells[cell_id]

                # Instantaneous velocity
                inst_dy = det["centroid_y"] - prev["centroid_y"]
                inst_dx = det["centroid_x"] - prev["centroid_x"]

                # Heavy velocity EMA (alpha=0.08 → 92% from previous)
                prev_vx, prev_vy = self._smoothed_velocities.get(cell_id, (inst_dx, inst_dy))
                smoothed_vx = self.velocity_ema_alpha * inst_dx + (1.0 - self.velocity_ema_alpha) * prev_vx
                smoothed_vy = self.velocity_ema_alpha * inst_dy + (1.0 - self.velocity_ema_alpha) * prev_vy

                # Fallback to steady default if velocity is near-zero
                if abs(smoothed_vx) < 0.05 and abs(smoothed_vy) < 0.05:
                    smoothed_vx = 0.6
                    smoothed_vy = -0.3

                self._smoothed_velocities[cell_id] = (smoothed_vx, smoothed_vy)

                # Update rolling history buffer
                history = self._history_buffers.get(cell_id, [])
                history.append({"x": det["centroid_x"], "y": det["centroid_y"], "timestamp": timestamp})
                if len(history) > 20:
                    history.pop(0)
                self._history_buffers[cell_id] = history

                # Speed and direction from smoothed velocity
                dist_km = np.sqrt(smoothed_vy ** 2 + smoothed_vx ** 2) * resolution_km
                speed_kmh = dist_km / time_step_hours if time_step_hours > 0 else det.get("speed_kmh", 15.0)
                direction_deg = float(np.degrees(np.arctan2(smoothed_vx, -smoothed_vy)) % 360)

                prev_dbz = prev.get("max_reflectivity_dbz", 0)
                curr_dbz = det["max_reflectivity_dbz"]
                if curr_dbz - prev_dbz > 3:
                    trend = "intensifying"
                elif curr_dbz - prev_dbz < -3:
                    trend = "weakening"
                else:
                    trend = "steady"

                # Heavy coordinate EMA (alpha=0.12 → 88% from previous position)
                smoothed_lat = prev["center_lat"] + self.coord_ema_alpha * (det["center_lat"] - prev["center_lat"])
                smoothed_lon = prev["center_lon"] + self.coord_ema_alpha * (det["center_lon"] - prev["center_lon"])

                tracked_cell = {
                    **det,
                    "cell_id": cell_id,
                    "timestamp": timestamp,
                    "center_lat": round(float(smoothed_lat), 4),
                    "center_lon": round(float(smoothed_lon), 4),
                    "movement_speed_kmh": round(max(5.0, speed_kmh), 1),
                    "movement_direction_deg": round(direction_deg, 1),
                    "velocity_y": smoothed_vy,
                    "velocity_x": smoothed_vx,
                    "trend": trend,
                    "lightning_rate": det.get("lightning_rate", prev.get("lightning_rate", 10.0)),
                }
                self._active_cells[cell_id] = tracked_cell
                self._missing_count[cell_id] = 0
                tracked.append(tracked_cell)
            else:
                cell_id = det.get("cell_id") or self._new_id()
                tracked_cell = {
                    **det,
                    "cell_id": cell_id,
                    "timestamp": timestamp,
                    "movement_speed_kmh": det.get("speed_kmh", 15.0),
                    "movement_direction_deg": det.get("direction_deg", 45.0),
                    "velocity_y": det.get("velocity_y", -0.3),
                    "velocity_x": det.get("velocity_x", 0.6),
                    "trend": "steady",
                    "lightning_rate": det.get("lightning_rate", 12.0),
                }
                self._active_cells[cell_id] = tracked_cell
                self._missing_count[cell_id] = 0
                self._smoothed_velocities[cell_id] = (0.6, -0.3)
                self._history_buffers[cell_id] = [
                    {"x": det["centroid_x"], "y": det["centroid_y"], "timestamp": timestamp}
                ]
                tracked.append(tracked_cell)

        for i, pid in enumerate(prev_ids):
            if i not in matched_prev:
                self._missing_count[pid] = self._missing_count.get(pid, 0) + 1
                if self._missing_count[pid] >= self.max_missing_frames:
                    del self._active_cells[pid]
                    del self._missing_count[pid]
                    self._smoothed_velocities.pop(pid, None)
                    self._history_buffers.pop(pid, None)
                    self._trajectory_averager.pop(pid, None)
                    self._forecast_averager.pop(pid, None)

        return tracked

    def get_active_cells(self) -> list[dict]:
        return list(self._active_cells.values())

    # ------------------------------------------------------------------
    # Trajectory Prediction with Rolling Average (Consensus Path)
    # ------------------------------------------------------------------

    def predict_trajectories(self, horizons_minutes: list[int] = None) -> list[dict]:
        """
        Predict storm trajectories using the PyTorch Deep Neural Nowcaster.
        Falls back to smoothed EMA velocity extrapolation if model is unavailable.

        After obtaining raw ML predictions, pushes them into a rolling window buffer
        and outputs the element-wise mean across all buffered predictions → producing
        a single stable "consensus" trajectory path that doesn't flicker frame-to-frame.
        """
        if horizons_minutes is None:
            horizons_minutes = [15, 30, 45, 60]

        trajectories = []

        for cell_id, cell in self._active_cells.items():
            history = self._history_buffers.get(cell_id, [])

            try:
                # Primary: PyTorch Neural Nowcasting
                ml_res = ml_inference.predict_cell_nowcast(cell, history, horizons_minutes)
                raw_forecasts = ml_res["forecasts"]
                raw_coords = ml_res["trajectory_coords"]
                smoothing_model = ml_res["smoothing_model"]
            except Exception:
                # Fallback: Smoothed Linear EMA Kinematic Extrapolation
                resolution_km = settings.mvp_grid_resolution_km
                time_step = settings.mvp_time_step_minutes
                vx, vy = self._smoothed_velocities.get(
                    cell_id, (cell.get("velocity_x", 0.6), cell.get("velocity_y", -0.3))
                )

                raw_forecasts = []
                for h in horizons_minutes:
                    steps = h / time_step
                    pred_y = cell["centroid_y"] + vy * steps
                    pred_x = cell["centroid_x"] + vx * steps

                    pred_lat = settings.mvp_center_lat + (pred_y - settings.grid_height / 2) * (resolution_km / 111.0)
                    pred_lon = settings.mvp_center_lon + (pred_x - settings.grid_width / 2) * (resolution_km / 111.0)
                    uncertainty_km = 4 + (h / 10) * 2.5

                    raw_forecasts.append({
                        "horizon_minutes": h,
                        "predicted_lat": round(float(pred_lat), 4),
                        "predicted_lon": round(float(pred_lon), 4),
                        "uncertainty_km": round(uncertainty_km, 1),
                        "thunderstorm_probability": round(max(0.3, 1.0 - h * 0.008), 2),
                        "lightning_probability": round(max(0.2, 0.9 - h * 0.01), 2),
                        "confidence_score": round(max(0.4, 1.0 - h * 0.01), 2),
                    })

                raw_coords = [[cell["center_lon"], cell["center_lat"]]] + [
                    [f["predicted_lon"], f["predicted_lat"]] for f in raw_forecasts
                ]
                smoothing_model = "Linear-EMA-Fallback"

            # ----- Rolling Trajectory Averaging (Consensus Path) -----
            # Push raw prediction into the rolling window
            if cell_id not in self._trajectory_averager:
                self._trajectory_averager[cell_id] = []
                self._forecast_averager[cell_id] = []

            self._trajectory_averager[cell_id].append(raw_coords)
            self._forecast_averager[cell_id].append(raw_forecasts)

            # Trim to window size
            if len(self._trajectory_averager[cell_id]) > self.trajectory_window:
                self._trajectory_averager[cell_id].pop(0)
                self._forecast_averager[cell_id].pop(0)

            # Compute element-wise mean across all buffered predictions
            avg_coords = self._average_trajectory_coords(
                self._trajectory_averager[cell_id], cell
            )
            avg_forecasts = self._average_forecasts(
                self._forecast_averager[cell_id]
            )

            # Calculate ETA to Ahmedabad city center
            ahmedabad_lat, ahmedabad_lon = 23.0225, 72.5714
            eta_minutes = self._calculate_eta(
                cell["center_lat"], cell["center_lon"],
                ahmedabad_lat, ahmedabad_lon,
                cell.get("movement_speed_kmh", 15.0),
                cell.get("movement_direction_deg", 45.0),
            )

            trajectories.append({
                "cell_id": cell_id,
                "current_lat": cell["center_lat"],
                "current_lon": cell["center_lon"],
                "speed_kmh": cell.get("movement_speed_kmh", 15.0),
                "direction_deg": cell.get("movement_direction_deg", 45.0),
                "intensity": cell.get("intensity", "strong"),
                "trend": cell.get("trend", "steady"),
                "smoothing_window": smoothing_model,
                "forecasts": avg_forecasts,
                "trajectory_coords": avg_coords,
                "eta_ahmedabad_minutes": eta_minutes,
                "averaging_samples": len(self._trajectory_averager.get(cell_id, [])),
            })

        return trajectories

    # ------------------------------------------------------------------
    # Averaging helpers
    # ------------------------------------------------------------------

    def _average_trajectory_coords(
        self, coord_buffer: list[list[list[float]]], cell: dict
    ) -> list[list[float]]:
        """Average trajectory coordinate sets element-wise. First point is always current cell position."""
        if not coord_buffer:
            return [[cell["center_lon"], cell["center_lat"]]]

        # Find the max number of points across all buffered predictions
        max_len = max(len(coords) for coords in coord_buffer)

        averaged = []
        for i in range(max_len):
            if i == 0:
                # First point: always use current (smoothed) cell position
                averaged.append([float(cell["center_lon"]), float(cell["center_lat"])])
                continue

            lons, lats = [], []
            for coords in coord_buffer:
                if i < len(coords):
                    lons.append(coords[i][0])
                    lats.append(coords[i][1])

            if lons:
                averaged.append([
                    round(float(np.mean(lons)), 4),
                    round(float(np.mean(lats)), 4),
                ])

        return averaged

    def _average_forecasts(self, forecast_buffer: list[list[dict]]) -> list[dict]:
        """Average forecast dicts element-wise across the rolling window."""
        if not forecast_buffer:
            return []

        num_horizons = max(len(fc_list) for fc_list in forecast_buffer)
        averaged = []

        for i in range(num_horizons):
            lats, lons, uncertainties = [], [], []
            ts_probs, lt_probs, confidences = [], [], []
            dbz_vals = []
            horizon_min = None

            for fc_list in forecast_buffer:
                if i < len(fc_list):
                    fc = fc_list[i]
                    horizon_min = fc.get("horizon_minutes", (i + 1) * 15)
                    lats.append(fc["predicted_lat"])
                    lons.append(fc["predicted_lon"])
                    uncertainties.append(fc.get("uncertainty_km", 5.0))
                    ts_probs.append(fc.get("thunderstorm_probability", 0.5))
                    lt_probs.append(fc.get("lightning_probability", 0.3))
                    confidences.append(fc.get("confidence_score", 0.7))
                    if "predicted_dbz" in fc:
                        dbz_vals.append(fc["predicted_dbz"])

            if not lats:
                continue

            avg_fc = {
                "horizon_minutes": int(horizon_min),
                "predicted_lat": round(float(np.mean(lats)), 4),
                "predicted_lon": round(float(np.mean(lons)), 4),
                "uncertainty_km": round(float(np.mean(uncertainties)), 1),
                "thunderstorm_probability": round(float(np.mean(ts_probs)), 2),
                "lightning_probability": round(float(np.mean(lt_probs)), 2),
                "confidence_score": round(float(np.mean(confidences)), 2),
            }
            if dbz_vals:
                avg_fc["predicted_dbz"] = round(float(np.mean(dbz_vals)), 1)

            # Estimate affected area from uncertainty radius
            r_km = avg_fc["uncertainty_km"]
            avg_fc["affected_area_km2"] = round(float(np.pi * r_km ** 2), 0)

            averaged.append(avg_fc)

        return averaged

    # ------------------------------------------------------------------
    # ETA calculation
    # ------------------------------------------------------------------

    @staticmethod
    def _calculate_eta(
        storm_lat: float, storm_lon: float,
        target_lat: float, target_lon: float,
        speed_kmh: float, direction_deg: float,
    ) -> float | None:
        """ETA to a target, returns minutes or None if moving away."""
        if speed_kmh < 1.0:
            return None

        distance_km = StormTracker._haversine_km(storm_lat, storm_lon, target_lat, target_lon)

        # Bearing from storm to target
        dlon = np.radians(target_lon - storm_lon)
        lat1_r, lat2_r = np.radians(storm_lat), np.radians(target_lat)
        x = np.sin(dlon) * np.cos(lat2_r)
        y = np.cos(lat1_r) * np.sin(lat2_r) - np.sin(lat1_r) * np.cos(lat2_r) * np.cos(dlon)
        bearing = (np.degrees(np.arctan2(x, y)) + 360) % 360

        angle_diff = abs(direction_deg - bearing)
        if angle_diff > 180:
            angle_diff = 360 - angle_diff

        if angle_diff > 90:
            return None

        approach_speed = speed_kmh * np.cos(np.radians(angle_diff))
        if approach_speed < 1.0:
            return None

        eta_minutes = (distance_km / approach_speed) * 60
        return round(eta_minutes, 0) if eta_minutes <= 120 else None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _new_id(self) -> str:
        self._next_id += 1
        return f"C-{self._next_id}"

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        R = 6371.0
        dlat = np.radians(lat2 - lat1)
        dlon = np.radians(lon2 - lon1)
        a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
        return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


storm_tracker = StormTracker()
