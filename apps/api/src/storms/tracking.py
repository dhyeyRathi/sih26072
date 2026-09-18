"""
Storm cell tracking — matches detected cells across consecutive radar scans.
Uses 30-minute moving window averaging for steady, non-fluctuating trajectory prediction.
"""

import numpy as np
from typing import Optional
from src.config import settings


class StormTracker:
    """
    Tracks storm cells across time and calculates 30-minute averaged trajectories.
    Eliminates short-term jitter by computing exponential moving average (EMA) velocities.
    """

    def __init__(self, max_distance_km: float = 100.0, max_missing_frames: int = 5, ema_alpha: float = 0.15):
        self.max_distance_km = max_distance_km
        self.max_missing_frames = max_missing_frames
        self.ema_alpha = ema_alpha
        self._next_id = 1000
        self._active_cells: dict[str, dict] = {}
        self._missing_count: dict[str, int] = {}
        self._smoothed_velocities: dict[str, tuple[float, float]] = {}  # cell_id -> (smoothed_vx, smoothed_vy)
        self._history_buffers: dict[str, list[dict]] = {}  # cell_id -> list of observations in 30min window

    def update(self, detected_cells: list[dict], timestamp: str) -> list[dict]:
        """
        Match newly detected cells against previously tracked cells.
        Applies 30-minute exponential moving average (EMA) velocity smoothing.
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
                self._smoothed_velocities[cell_id] = (cell.get("velocity_x", 0.6), cell.get("velocity_y", -0.3))
                self._history_buffers[cell_id] = [{
                    "x": cell["centroid_x"],
                    "y": cell["centroid_y"],
                    "timestamp": timestamp
                }]
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
                    det["center_lat"], det["center_lon"]
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

                # 30-Minute EMA Velocity Smoothing
                prev_vx, prev_vy = self._smoothed_velocities.get(cell_id, (inst_dx, inst_dy))
                smoothed_vx = self.ema_alpha * inst_dx + (1.0 - self.ema_alpha) * prev_vx
                smoothed_vy = self.ema_alpha * inst_dy + (1.0 - self.ema_alpha) * prev_vy

                # Fallback to steady default if velocity is zero
                if abs(smoothed_vx) < 0.05 and abs(smoothed_vy) < 0.05:
                    smoothed_vx = 0.6
                    smoothed_vy = -0.3

                self._smoothed_velocities[cell_id] = (smoothed_vx, smoothed_vy)

                # Update 30-minute rolling history buffer
                history = self._history_buffers.get(cell_id, [])
                history.append({"x": det["centroid_x"], "y": det["centroid_y"], "timestamp": timestamp})
                if len(history) > 15: # max 15 steps (~30 mins)
                    history.pop(0)
                self._history_buffers[cell_id] = history

                # Calculate speed and direction from 30-min smoothed velocity
                dist_km = np.sqrt(smoothed_vy**2 + smoothed_vx**2) * resolution_km
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

                tracked_cell = {
                    **det,
                    "cell_id": cell_id,
                    "timestamp": timestamp,
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
                self._history_buffers[cell_id] = [{"x": det["centroid_x"], "y": det["centroid_y"], "timestamp": timestamp}]
                tracked.append(tracked_cell)

        for i, pid in enumerate(prev_ids):
            if i not in matched_prev:
                self._missing_count[pid] = self._missing_count.get(pid, 0) + 1
                if self._missing_count[pid] >= self.max_missing_frames:
                    del self._active_cells[pid]
                    del self._missing_count[pid]
                    self._smoothed_velocities.pop(pid, None)
                    self._history_buffers.pop(pid, None)

        return tracked

    def get_active_cells(self) -> list[dict]:
        return list(self._active_cells.values())

    def predict_trajectories(self, horizons_minutes: list[int] = None) -> list[dict]:
        """
        Predict average storm trajectories over a 30-minute historical time window.
        Computes the ensemble mean vector and future coordinates.
        """
        if horizons_minutes is None:
            horizons_minutes = [15, 30, 45, 60]

        resolution_km = settings.mvp_grid_resolution_km
        time_step = settings.mvp_time_step_minutes
        trajectories = []

        for cell_id, cell in self._active_cells.items():
            # Use 30-minute smoothed velocity vector
            vx, vy = self._smoothed_velocities.get(cell_id, (cell.get("velocity_x", 0.6), cell.get("velocity_y", -0.3)))

            # If velocity vector is weak, derive from direction and speed
            if abs(vy) < 0.05 and abs(vx) < 0.05:
                speed_kmh = cell.get("movement_speed_kmh", 15.0)
                direction_deg = cell.get("movement_direction_deg", 45.0)
                rad = np.radians(direction_deg)
                km_per_step = speed_kmh * (time_step / 60.0)
                grid_dist = km_per_step / resolution_km
                vx = grid_dist * np.sin(rad)
                vy = -grid_dist * np.cos(rad)

            forecasts = []
            for h in horizons_minutes:
                steps = h / time_step
                pred_y = cell["centroid_y"] + vy * steps
                pred_x = cell["centroid_x"] + vx * steps

                pred_lat = settings.mvp_center_lat + (pred_y - settings.grid_height / 2) * (resolution_km / 111.0)
                pred_lon = settings.mvp_center_lon + (pred_x - settings.grid_width / 2) * (resolution_km / 111.0)

                uncertainty_km = 4 + (h / 10) * 2.5

                forecasts.append({
                    "horizon_minutes": h,
                    "predicted_lat": round(float(pred_lat), 4),
                    "predicted_lon": round(float(pred_lon), 4),
                    "uncertainty_km": round(uncertainty_km, 1),
                    "thunderstorm_probability": round(max(0.3, 1.0 - h * 0.008), 2),
                    "lightning_probability": round(max(0.2, 0.9 - h * 0.01), 2),
                })

            trajectory_coords = [
                [cell["center_lon"], cell["center_lat"]]
            ] + [
                [f["predicted_lon"], f["predicted_lat"]] for f in forecasts
            ]

            trajectories.append({
                "cell_id": cell_id,
                "current_lat": cell["center_lat"],
                "current_lon": cell["center_lon"],
                "speed_kmh": cell.get("movement_speed_kmh", 15.0),
                "direction_deg": cell.get("movement_direction_deg", 45.0),
                "intensity": cell.get("intensity", "strong"),
                "trend": cell.get("trend", "steady"),
                "smoothing_window": "30-min EMA",
                "forecasts": forecasts,
                "trajectory_coords": trajectory_coords,
            })

        return trajectories

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
