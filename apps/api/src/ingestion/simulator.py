"""
Simulated weather data generator for development and demonstration.
Generates realistic-looking radar, lightning, and storm data for Gujarat/Ahmedabad region.
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from src.config import settings


class SimulatedDataGenerator:
    """
    Generates synthetic weather data that mimics real atmospheric observations.
    Used for development before real MOSDAC/IMD data access is established.
    """

    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)
        self.grid_h = settings.grid_height  # 200
        self.grid_w = settings.grid_width   # 200
        self.center_lat = settings.mvp_center_lat
        self.center_lon = settings.mvp_center_lon

        # Persistent storm state for temporal coherence
        self._storms: list[dict] = []
        self._time_step = 0
        self._init_storms()

    def _init_storms(self):
        """Initialize 2-4 simulated storm cells with realistic properties."""
        n_storms = self.rng.integers(2, 5)
        for i in range(n_storms):
            self._storms.append({
                "id": f"C-{1000 + i}",
                "center_y": self.rng.integers(30, self.grid_h - 30),
                "center_x": self.rng.integers(30, self.grid_w - 30),
                "radius": self.rng.integers(8, 25),
                "max_dbz": self.rng.uniform(35, 65),
                "velocity_y": self.rng.uniform(-2, 2),    # cells per step
                "velocity_x": self.rng.uniform(0.5, 3),   # generally moving east/NE
                "lightning_rate": self.rng.uniform(2, 20),
                "growth_rate": self.rng.uniform(-0.1, 0.3),
                "active": True,
            })

    def generate_radar_frame(self, timestamp: Optional[datetime] = None) -> dict:
        """
        Generate a single radar reflectivity frame (200x200 grid).
        Returns dict with grid data, metadata, and detected storm properties.
        """
        self._time_step += 1
        grid = np.zeros((self.grid_h, self.grid_w), dtype=np.float32)

        active_storms = []
        for i, storm in enumerate(self._storms):
            if not storm["active"]:
                # Respawn a new storm
                self._storms[i] = {
                    "id": f"C-{1000 + self._time_step + i}",
                    "center_y": self.rng.integers(30, self.grid_h - 30),
                    "center_x": self.rng.integers(30, self.grid_w - 30),
                    "radius": self.rng.integers(8, 25),
                    "max_dbz": self.rng.uniform(35, 65),
                    "velocity_y": self.rng.uniform(-2, 2),
                    "velocity_x": self.rng.uniform(0.5, 3),
                    "lightning_rate": self.rng.uniform(2, 20),
                    "growth_rate": self.rng.uniform(-0.1, 0.3),
                    "active": True,
                }
                storm = self._storms[i]

            # Move the storm
            storm["center_y"] += storm["velocity_y"]
            storm["center_x"] += storm["velocity_x"]
            storm["radius"] = max(5, storm["radius"] + storm["growth_rate"])
            storm["max_dbz"] = np.clip(
                storm["max_dbz"] + self.rng.uniform(-1, 1), 20, 70
            )
            storm["lightning_rate"] = max(0, storm["lightning_rate"] + self.rng.uniform(-1, 2))

            # Check if storm left the grid
            cy, cx = int(storm["center_y"]), int(storm["center_x"])
            if cy < 0 or cy >= self.grid_h or cx < 0 or cx >= self.grid_w:
                storm["active"] = False
                continue

            # Draw storm cell on grid (gaussian-like blob)
            r = int(storm["radius"])
            y_start = max(0, cy - r * 2)
            y_end = min(self.grid_h, cy + r * 2)
            x_start = max(0, cx - r * 2)
            x_end = min(self.grid_w, cx + r * 2)

            for y in range(y_start, y_end):
                for x in range(x_start, x_end):
                    dist = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
                    if dist < r * 2:
                        intensity = storm["max_dbz"] * np.exp(-(dist ** 2) / (2 * (r ** 2)))
                        noise = self.rng.uniform(-3, 3)
                        grid[y, x] = max(grid[y, x], intensity + noise)

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
                "speed_kmh": round(float(speed_kmh), 1),
                "direction_deg": round(float(direction_deg), 1),
                "velocity_y": float(storm["velocity_y"]),
                "velocity_x": float(storm["velocity_x"]),
                "intensity": self._classify_intensity(storm["max_dbz"]),
                "trend": self._classify_trend(storm["growth_rate"]),
            })

        # Add background noise
        noise = self.rng.uniform(0, 8, size=(self.grid_h, self.grid_w)).astype(np.float32)
        grid = np.clip(grid + noise, 0, 75)

        ts = timestamp or (datetime.utcnow() - timedelta(minutes=(100 - self._time_step) * settings.mvp_time_step_minutes))

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
        """Return the last generated frame without advancing the simulation."""
        if not hasattr(self, '_last_frame'):
            return self.generate_radar_frame()
        return self._last_frame

    def generate_lightning_data(self, radar_frame: dict) -> list[dict]:
        """Generate lightning strike locations based on storm positions."""
        strikes = []
        for storm in radar_frame["storms"]:
            n_strikes = int(storm["lightning_rate"] * self.rng.uniform(0.5, 1.5))
            for _ in range(n_strikes):
                offset_lat = self.rng.normal(0, 0.1)
                offset_lon = self.rng.normal(0, 0.1)
                strikes.append({
                    "lat": round(storm["center_lat"] + offset_lat, 4),
                    "lon": round(storm["center_lon"] + offset_lon, 4),
                    "timestamp": radar_frame["timestamp"],
                    "intensity_ka": round(float(self.rng.uniform(5, 200)), 1),
                    "cell_id": storm["cell_id"],
                })
        return strikes

    def generate_sequence(self, n_frames: int = 7) -> list[dict]:
        """Generate a sequence of radar frames for training/inference input."""
        frames = []
        base_time = datetime.utcnow() - timedelta(minutes=n_frames * settings.mvp_time_step_minutes)
        for i in range(n_frames):
            ts = base_time + timedelta(minutes=i * settings.mvp_time_step_minutes)
            frames.append(self.generate_radar_frame(timestamp=ts))
        return frames

    @staticmethod
    def _classify_intensity(max_dbz: float) -> str:
        if max_dbz >= 55:
            return "severe"
        elif max_dbz >= 45:
            return "strong"
        elif max_dbz >= 35:
            return "moderate"
        return "weak"

    @staticmethod
    def _classify_trend(growth_rate: float) -> str:
        if growth_rate > 0.2:
            return "intensifying"
        elif growth_rate > -0.05:
            return "steady"
        elif growth_rate > -0.2:
            return "weakening"
        return "dissipating"


# Singleton for consistent state across the app
data_generator = SimulatedDataGenerator()
