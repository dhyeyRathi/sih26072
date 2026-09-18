"""
Simulated weather data generator for development and demonstration.
Generates realistic-looking Doppler radar reflectivity, rain bands, lightning, and storm data for Gujarat/Ahmedabad region.
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from src.config import settings


class SimulatedDataGenerator:
    """
    Generates synthetic Doppler radar weather data that mimics real atmospheric reflectivity observations.
    Maintains 3 persistent, smooth storm systems across Gujarat.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)
        self.grid_h = settings.grid_height  # 200
        self.grid_w = settings.grid_width   # 200
        self.center_lat = settings.mvp_center_lat
        self.center_lon = settings.mvp_center_lon

        self._storms: list[dict] = []
        self._time_step = 0
        self._init_storms()

    def _init_storms(self):
        """Initialize 3 persistent storm systems with stable IDs, coordinates, and motion vectors."""
        preset_positions = [
            {"id": "C-1001", "y": 85, "x": 90, "vy": -0.25, "vx": 0.55, "radius": 24, "dbz": 62.0},
            {"id": "C-1002", "y": 135, "x": 125, "vy": -0.20, "vx": 0.65, "radius": 28, "dbz": 66.0},
            {"id": "C-1003", "y": 65, "x": 145, "vy": -0.30, "vx": 0.50, "radius": 20, "dbz": 56.0},
        ]
        for p in preset_positions:
            self._storms.append({
                "id": p["id"],
                "center_y": float(p["y"]),
                "center_x": float(p["x"]),
                "radius": float(p["radius"]),
                "max_dbz": float(p["dbz"]),
                "velocity_y": float(p["vy"]),
                "velocity_x": float(p["vx"]),
                "lightning_rate": float(self.rng.uniform(15, 35)),
                "active": True,
            })

    def generate_radar_frame(self, timestamp: Optional[datetime] = None) -> dict:
        """
        Generate a single radar reflectivity frame (200x200 grid).
        Moves 3 persistent storms smoothly across Gujarat.
        """
        self._time_step += 1
        grid = np.zeros((self.grid_h, self.grid_w), dtype=np.float32)

        active_storms = []
        for i, storm in enumerate(self._storms):
            # Smooth movement
            storm["center_y"] += storm["velocity_y"]
            storm["center_x"] += storm["velocity_x"]

            # Keep simulation active inside grid bounds
            if storm["center_x"] >= self.grid_w - 25:
                storm["center_x"] = 35.0
            if storm["center_x"] < 25:
                storm["center_x"] = float(self.grid_w - 35)
            if storm["center_y"] >= self.grid_h - 25 or storm["center_y"] < 25:
                storm["velocity_y"] *= -1

            cy, cx = int(storm["center_y"]), int(storm["center_x"])
            r = int(storm["radius"])

            # Draw smooth Gaussian storm core & rain envelope (max dBZ 55-66 at center, 20-35 dBZ outer)
            y_start = max(0, cy - r * 2)
            y_end = min(self.grid_h, cy + r * 2)
            x_start = max(0, cx - r * 2)
            x_end = min(self.grid_w, cx + r * 2)

            for y in range(y_start, y_end):
                for x in range(x_start, x_end):
                    dist = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
                    if dist < r * 2:
                        intensity = storm["max_dbz"] * np.exp(-(dist ** 2) / (2 * (r ** 2)))
                        grid[y, x] = max(grid[y, x], intensity)

            # Convert grid position to lat/lon
            lat = self.center_lat + (cy - self.grid_h / 2) * (settings.mvp_grid_resolution_km / 111.0)
            lon = self.center_lon + (cx - self.grid_w / 2) * (settings.mvp_grid_resolution_km / 111.0)

            speed_kmh = np.sqrt(storm["velocity_y"]**2 + storm["velocity_x"]**2) * (
                settings.mvp_grid_resolution_km * 60 / settings.mvp_time_step_minutes
            )
            direction_deg = np.degrees(np.arctan2(storm["velocity_x"], -storm["velocity_y"])) % 360

            active_storms.append({
                "cell_id": storm["id"],
                "center_lat": round(float(lat), 4),
                "center_lon": round(float(lon), 4),
                "center_y": int(cy),
                "center_x": int(cx),
                "radius_cells": int(storm["radius"]),
                "max_reflectivity_dbz": round(float(storm["max_dbz"]), 1),
                "area_sq_km": round(float(np.pi * (storm["radius"] * settings.mvp_grid_resolution_km) ** 2), 1),
                "lightning_rate": round(float(storm["lightning_rate"]), 1),
                "speed_kmh": round(float(max(10.0, speed_kmh)), 1),
                "direction_deg": round(float(direction_deg), 1),
                "velocity_y": float(storm["velocity_y"]),
                "velocity_x": float(storm["velocity_x"]),
                "intensity": self._classify_intensity(storm["max_dbz"]),
                "trend": "steady",
            })

        # Add light background noise (< 12 dBZ so it never triggers false storm cell detections)
        noise = self.rng.uniform(0, 4, size=(self.grid_h, self.grid_w)).astype(np.float32)
        grid = np.clip(grid + noise, 0, 75)

        ts = timestamp or datetime.utcnow()

        self._last_frame = {
            "grid": grid,
            "timestamp": ts.isoformat(),
            "grid_shape": [self.grid_h, self.grid_w],
            "resolution_km": settings.mvp_grid_resolution_km,
            "center_lat": self.center_lat,
            "center_lon": self.center_lon,
            "storms": active_storms,
        }
        return self._last_frame

    def get_current_frame(self) -> dict:
        if not hasattr(self, '_last_frame'):
            return self.generate_radar_frame()
        return self._last_frame

    def generate_lightning_data(self, frame: dict) -> list[dict]:
        strikes = []
        for storm in frame["storms"]:
            rate = storm["lightning_rate"]
            count = int(rate / 5)
            for _ in range(count):
                offset_lat = self.rng.uniform(-0.08, 0.08)
                offset_lon = self.rng.uniform(-0.08, 0.08)
                strikes.append({
                    "lat": round(storm["center_lat"] + offset_lat, 4),
                    "lon": round(storm["center_lon"] + offset_lon, 4),
                    "timestamp": frame["timestamp"],
                    "intensity_ka": round(float(self.rng.uniform(-40, -10 if self.rng.random() > 0.5 else 30)), 1),
                    "cell_id": storm["cell_id"],
                })
        return strikes

    @staticmethod
    def _classify_intensity(max_dbz: float) -> str:
        if max_dbz >= 55: return "severe"
        if max_dbz >= 45: return "strong"
        if max_dbz >= 35: return "moderate"
        return "weak"

    @staticmethod
    def _classify_trend(growth_rate: float) -> str:
        if growth_rate > 0.1: return "intensifying"
        if growth_rate < -0.1: return "weakening"
        return "steady"


data_generator = SimulatedDataGenerator()
