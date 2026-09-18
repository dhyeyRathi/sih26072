"""
Simulated weather data generator for development and demonstration.
Generates realistic Doppler radar reflectivity, rain bands, lightning, and storm data for Gujarat/Ahmedabad region.
Maintains 3 permanent storm systems with pinned geographical centers so markers NEVER jump or move erratically,
while radar reflectivity, lightning, and telemetry update dynamically every 1 second.
"""

import numpy as np
from datetime import datetime
from typing import Optional
from src.config import settings


class SimulatedDataGenerator:
    """
    Generates synthetic Doppler radar weather data that mimics real atmospheric reflectivity observations.
    Storm centers are pinned at realistic geographical locations in Gujarat.
    Radar reflectivity, lightning strikes, and atmospheric properties evolve dynamically in real time.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)
        self.grid_h = settings.grid_height  # 200
        self.grid_w = settings.grid_width   # 200
        self.center_lat = settings.mvp_center_lat  # 23.0
        self.center_lon = settings.mvp_center_lon  # 72.5

        self._storms: list[dict] = []
        self._time_step = 0
        self._init_storms()

    def _init_storms(self):
        """
        Initialize 3 permanent, geographically stable storm systems:
        - C-1001: Ahmedabad Metro Core (Central)
        - C-1002: Anand / Vadodara Core (South-East)
        - C-1003: Gandhinagar / Mehsana Core (North-East)
        Positions remain fixed so markers NEVER jump or wander.
        """
        preset_positions = [
            {
                "id": "C-1001",
                "y": 98.0, "x": 105.0,
                "radius": 24.0, "base_dbz": 63.5,
                "heading": 52.0, "speed": 24.0,
                "velocity_x": 0.45, "velocity_y": -0.35,
            },
            {
                "id": "C-1002",
                "y": 138.0, "x": 128.0,
                "radius": 28.0, "base_dbz": 66.0,
                "heading": 48.0, "speed": 28.0,
                "velocity_x": 0.50, "velocity_y": -0.40,
            },
            {
                "id": "C-1003",
                "y": 62.0, "x": 132.0,
                "radius": 20.0, "base_dbz": 57.0,
                "heading": 65.0, "speed": 19.0,
                "velocity_x": 0.40, "velocity_y": -0.25,
            },
        ]

        self._storms = []
        for p in preset_positions:
            lat = self.center_lat + (p["y"] - self.grid_h / 2) * (settings.mvp_grid_resolution_km / 111.0)
            lon = self.center_lon + (p["x"] - self.grid_w / 2) * (settings.mvp_grid_resolution_km / 111.0)

            self._storms.append({
                "id": p["id"],
                "center_y": float(p["y"]),
                "center_x": float(p["x"]),
                "fixed_lat": round(float(lat), 4),
                "fixed_lon": round(float(lon), 4),
                "radius": float(p["radius"]),
                "base_dbz": float(p["base_dbz"]),
                "max_dbz": float(p["base_dbz"]),
                "heading": float(p["heading"]),
                "speed": float(p["speed"]),
                "velocity_x": float(p["velocity_x"]),
                "velocity_y": float(p["velocity_y"]),
                "lightning_rate": 22.0,
                "active": True,
            })

    def generate_radar_frame(self, timestamp: Optional[datetime] = None) -> dict:
        """
        Generate a single radar reflectivity frame (200x200 grid).
        Storm centers stay fixed at their anchor positions (zero marker drift).
        Radar core reflectivity and rain bands dynamically pulse every 1 second.
        """
        self._time_step += 1
        grid = np.zeros((self.grid_h, self.grid_w), dtype=np.float32)

        active_storms = []
        for storm in self._storms:
            # Dynamic natural intensity fluctuation (reflectivity breathing +/- 1.5 dBZ)
            pulse = float(np.sin(self._time_step * 0.15) * 1.5 + self.rng.uniform(-0.5, 0.5))
            current_dbz = float(np.clip(storm["base_dbz"] + pulse, 35.0, 72.0))
            storm["max_dbz"] = current_dbz

            # Dynamic natural lightning rate fluctuation
            storm["lightning_rate"] = float(np.clip(
                (current_dbz - 38.0) * 1.2 + self.rng.uniform(-2.0, 2.0), 5.0, 45.0
            ))

            cy = int(round(storm["center_y"]))
            cx = int(round(storm["center_x"]))
            r = int(round(storm["radius"]))

            # Draw smooth Gaussian storm core & rain envelope
            y_start = max(0, cy - r * 2)
            y_end = min(self.grid_h, cy + r * 2)
            x_start = max(0, cx - r * 2)
            x_end = min(self.grid_w, cx + r * 2)

            for y in range(y_start, y_end):
                for x in range(x_start, x_end):
                    dist = np.sqrt((y - storm["center_y"]) ** 2 + (x - storm["center_x"]) ** 2)
                    if dist < r * 2:
                        intensity = current_dbz * np.exp(-(dist ** 2) / (2 * (r ** 2)))
                        grid[y, x] = max(grid[y, x], intensity)

            # Storm centers are permanently fixed to their designated geographic coordinates
            active_storms.append({
                "cell_id": storm["id"],
                "center_lat": storm["fixed_lat"],
                "center_lon": storm["fixed_lon"],
                "center_y": cy,
                "center_x": cx,
                "centroid_y": float(storm["center_y"]),
                "centroid_x": float(storm["center_x"]),
                "radius_cells": int(r),
                "max_reflectivity_dbz": round(current_dbz, 1),
                "area_sq_km": round(float(np.pi * (storm["radius"] * settings.mvp_grid_resolution_km) ** 2), 1),
                "lightning_rate": round(float(storm["lightning_rate"]), 1),
                "speed_kmh": round(float(storm["speed"]), 1),
                "direction_deg": round(float(storm["heading"]), 1),
                "velocity_y": float(storm["velocity_y"]),
                "velocity_x": float(storm["velocity_x"]),
                "intensity": self._classify_intensity(current_dbz),
                "trend": "steady",
            })

        # Add light background noise (< 6 dBZ)
        noise = self.rng.uniform(0, 3, size=(self.grid_h, self.grid_w)).astype(np.float32)
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
            count = max(1, int(rate / 7))
            for _ in range(count):
                offset_lat = self.rng.uniform(-0.06, 0.06)
                offset_lon = self.rng.uniform(-0.06, 0.06)
                strikes.append({
                    "lat": round(storm["center_lat"] + offset_lat, 4),
                    "lon": round(storm["center_lon"] + offset_lon, 4),
                    "timestamp": frame["timestamp"],
                    "intensity_ka": round(float(self.rng.uniform(-35, 25)), 1),
                    "cell_id": storm["cell_id"],
                })
        return strikes

    @staticmethod
    def _classify_intensity(max_dbz: float) -> str:
        if max_dbz >= 55: return "severe"
        if max_dbz >= 45: return "strong"
        if max_dbz >= 35: return "moderate"
        return "weak"


data_generator = SimulatedDataGenerator()
