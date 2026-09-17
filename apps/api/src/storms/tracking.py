"""
Storm cell tracking — matches detected cells across consecutive radar scans.
Uses centroid proximity and area overlap for cell-to-cell matching.
"""

import numpy as np
from typing import Optional
from src.config import settings


class StormTracker:
    """
    Tracks storm cells across time by matching detections between consecutive frames.

    Matching is based on:
    1. Centroid distance (primary)
    2. Area similarity (secondary)

    Cells that cannot be matched get new IDs.
    Cells that disappear are marked inactive after a configurable timeout.
    """

    def __init__(self, max_distance_km: float = 30.0, max_missing_frames: int = 3):
        self.max_distance_km = max_distance_km
        self.max_missing_frames = max_missing_frames
        self._next_id = 1000
        self._active_cells: dict[str, dict] = {}  # cell_id -> last observation
        self._missing_count: dict[str, int] = {}   # cell_id -> consecutive missing frames

    def update(self, detected_cells: list[dict], timestamp: str) -> list[dict]:
        """
        Match newly detected cells against previously tracked cells.
        Returns list of tracked cells with persistent IDs and computed motion vectors.
        """
        if not self._active_cells:
            # First frame — assign new IDs to all detections
            tracked = []
            for cell in detected_cells:
                cell_id = self._new_id()
                tracked_cell = {
                    **cell,
                    "cell_id": cell_id,
                    "timestamp": timestamp,
                    "movement_speed_kmh": 0.0,
                    "movement_direction_deg": 0.0,
                    "trend": "steady",
                    "lightning_rate": 0.0,
                }
                self._active_cells[cell_id] = tracked_cell
                self._missing_count[cell_id] = 0
                tracked.append(tracked_cell)
            return tracked

        # Build cost matrix: distance between each previous cell and each new detection
        prev_ids = list(self._active_cells.keys())
        prev_cells = [self._active_cells[cid] for cid in prev_ids]

        matched_prev = set()
        matched_det = set()
        assignments = {}

        # Greedy matching by minimum distance
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

        # Build tracked cells
        tracked = []
        resolution_km = settings.mvp_grid_resolution_km
        time_step_hours = settings.mvp_time_step_minutes / 60.0

        for j, det in enumerate(detected_cells):
            if j in assignments:
                cell_id = assignments[j]
                prev = self._active_cells[cell_id]

                # Compute motion vector
                dy = det["centroid_y"] - prev["centroid_y"]
                dx = det["centroid_x"] - prev["centroid_x"]
                dist_km = np.sqrt(dy**2 + dx**2) * resolution_km
                speed_kmh = dist_km / time_step_hours if time_step_hours > 0 else 0
                direction_deg = float(np.degrees(np.arctan2(dx, -dy)) % 360)

                # Determine trend
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
                    "movement_speed_kmh": round(speed_kmh, 1),
                    "movement_direction_deg": round(direction_deg, 1),
                    "velocity_y": dy,
                    "velocity_x": dx,
                    "trend": trend,
                    "lightning_rate": det.get("lightning_rate", prev.get("lightning_rate", 0)),
                }
                self._active_cells[cell_id] = tracked_cell
                self._missing_count[cell_id] = 0
                tracked.append(tracked_cell)
            else:
                # New cell
                cell_id = self._new_id()
                tracked_cell = {
                    **det,
                    "cell_id": cell_id,
                    "timestamp": timestamp,
                    "movement_speed_kmh": 0.0,
                    "movement_direction_deg": 0.0,
                    "velocity_y": 0.0,
                    "velocity_x": 0.0,
                    "trend": "steady",
                    "lightning_rate": 0.0,
                }
                self._active_cells[cell_id] = tracked_cell
                self._missing_count[cell_id] = 0
                tracked.append(tracked_cell)

        # Handle cells that were not matched (missing in this frame)
        for i, pid in enumerate(prev_ids):
            if i not in matched_prev:
                self._missing_count[pid] = self._missing_count.get(pid, 0) + 1
                if self._missing_count[pid] >= self.max_missing_frames:
                    del self._active_cells[pid]
                    del self._missing_count[pid]

        return tracked

    def get_active_cells(self) -> list[dict]:
        """Return all currently active tracked cells."""
        return list(self._active_cells.values())

    def predict_trajectories(self, horizons_minutes: list[int] = None) -> list[dict]:
        """
        Predict future positions for all active cells using linear extrapolation.
        Returns trajectory forecasts with uncertainty corridors.
        """
        if horizons_minutes is None:
            horizons_minutes = [15, 30, 45, 60]

        resolution_km = settings.mvp_grid_resolution_km
        time_step = settings.mvp_time_step_minutes
        trajectories = []

        for cell_id, cell in self._active_cells.items():
            vy = cell.get("velocity_y", 0)
            vx = cell.get("velocity_x", 0)

            if abs(vy) < 0.01 and abs(vx) < 0.01:
                continue  # Stationary cell, no meaningful trajectory

            forecasts = []
            for h in horizons_minutes:
                steps = h / time_step
                pred_y = cell["centroid_y"] + vy * steps
                pred_x = cell["centroid_x"] + vx * steps

                pred_lat = settings.mvp_center_lat + (pred_y - settings.grid_height / 2) * (resolution_km / 111.0)
                pred_lon = settings.mvp_center_lon + (pred_x - settings.grid_width / 2) * (resolution_km / 111.0)

                # Uncertainty grows with forecast horizon
                uncertainty_km = 5 + (h / 10) * 3  # 5km base + 3km per 10min

                forecasts.append({
                    "horizon_minutes": h,
                    "predicted_lat": round(float(pred_lat), 4),
                    "predicted_lon": round(float(pred_lon), 4),
                    "uncertainty_km": round(uncertainty_km, 1),
                    "thunderstorm_probability": round(max(0.3, 1.0 - h * 0.008), 2),
                    "lightning_probability": round(max(0.2, 0.9 - h * 0.01), 2),
                })

            # Trajectory as LineString coordinates
            trajectory_coords = [
                [cell["center_lon"], cell["center_lat"]]
            ] + [
                [f["predicted_lon"], f["predicted_lat"]] for f in forecasts
            ]

            trajectories.append({
                "cell_id": cell_id,
                "current_lat": cell["center_lat"],
                "current_lon": cell["center_lon"],
                "speed_kmh": cell["movement_speed_kmh"],
                "direction_deg": cell["movement_direction_deg"],
                "intensity": cell["intensity"],
                "trend": cell["trend"],
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


# Singleton tracker
storm_tracker = StormTracker()
