"""
SIH26072 — Optical Flow Storm Tracking Engine
Implements Farnebäck dense optical flow and Lucas-Kanade sparse tracking
for per-pixel motion estimation from consecutive radar reflectivity grids.

Based on techniques used by operational nowcasting systems:
- SWIRLS (Hong Kong Observatory) — ROVER variational optical flow
- STEPS (Bureau of Meteorology) — Bowler optical flow
- pysteps / rainymotion — open-source benchmark implementations
"""

import numpy as np
from typing import Tuple, Optional, Dict
from collections import deque

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False
    print("[WARN] OpenCV not available. Optical flow disabled. Install with: pip install opencv-python")

from src.config import settings


class OpticalFlowEngine:
    """
    Dense optical flow engine for radar reflectivity tracking.
    
    Methods:
    1. Farnebäck Dense Optical Flow — per-pixel motion vectors
    2. Lucas-Kanade Sparse Optical Flow — feature-point tracking on storm cores
    3. Semi-Lagrangian Advection — non-linear trajectory extrapolation
    
    Output:
    - Dense motion field (2, H, W) in pixels/timestep
    - Per-cell velocity at centroid
    - Derived quantities: divergence, curl (for storm dynamics)
    """

    def __init__(
        self,
        frame_buffer_size: int = 6,
        smoothing_passes: int = 3,
        outlier_std_threshold: float = 3.0,
        temporal_decay: float = 0.3,
    ):
        self.frame_buffer: deque = deque(maxlen=frame_buffer_size)
        self.motion_field_buffer: deque = deque(maxlen=5)
        self.smoothing_passes = smoothing_passes
        self.outlier_std = outlier_std_threshold
        self.temporal_decay = temporal_decay
        
        self._latest_motion_field: Optional[np.ndarray] = None
        self._latest_divergence: Optional[np.ndarray] = None
        self._latest_curl: Optional[np.ndarray] = None

    def push_frame(self, reflectivity_grid: np.ndarray) -> None:
        """Push a new radar frame into the buffer."""
        self.frame_buffer.append(reflectivity_grid.copy())

    def compute_motion_field(self) -> Optional[np.ndarray]:
        """
        Compute dense motion field from last two radar frames using
        Farnebäck optical flow (OpenCV).
        
        Returns:
            Motion field of shape (2, H, W) where:
            - [0] = x-component (east-west, pixels/timestep)
            - [1] = y-component (north-south, pixels/timestep)
            Returns None if insufficient frames or OpenCV unavailable.
        """
        if not HAS_OPENCV or len(self.frame_buffer) < 2:
            return None

        # Get last two frames
        prev_frame = self.frame_buffer[-2]
        curr_frame = self.frame_buffer[-1]

        # Normalize to uint8 for OpenCV
        prev_u8 = self._normalize_to_uint8(prev_frame)
        curr_u8 = self._normalize_to_uint8(curr_frame)

        # Farnebäck Dense Optical Flow
        # Parameters tuned for weather radar (10-min intervals, ~1km resolution):
        #   pyr_scale=0.5 — standard pyramid scale
        #   levels=4 — 4 pyramid levels for multi-scale (catches 1-16 pixel motions)
        #   winsize=15 — window size (15km neighborhood at 1km resolution)
        #   iterations=5 — refinement iterations per level
        #   poly_n=7 — polynomial expansion neighborhood (7km smoothing)
        #   poly_sigma=1.5 — Gaussian sigma for polynomial expansion
        flow = cv2.calcOpticalFlowFarneback(
            prev_u8, curr_u8,
            flow=None,
            pyr_scale=0.5,
            levels=4,
            winsize=15,
            iterations=5,
            poly_n=7,
            poly_sigma=1.5,
            flags=cv2.OPTFLOW_FARNEBACK_GAUSSIAN,
        )

        # flow shape: (H, W, 2) — [dx, dy] per pixel
        # Reorder to (2, H, W)
        motion_field = np.transpose(flow, (2, 0, 1)).astype(np.float32)

        # Post-processing pipeline
        motion_field = self._reject_outliers(motion_field)
        motion_field = self._spatial_smooth(motion_field)
        motion_field = self._temporal_smooth(motion_field)

        # Compute derived fields
        self._latest_motion_field = motion_field
        self._latest_divergence = self._compute_divergence(motion_field)
        self._latest_curl = self._compute_curl(motion_field)

        # Store for temporal smoothing
        self.motion_field_buffer.append(motion_field.copy())

        return motion_field

    def get_velocity_at_centroid(
        self, centroid_y: float, centroid_x: float
    ) -> Tuple[float, float]:
        """
        Get interpolated optical flow velocity at a specific storm centroid location.
        Uses bilinear interpolation for sub-pixel accuracy.
        
        Returns: (vx, vy) in pixels/timestep
        """
        if self._latest_motion_field is None:
            return (0.0, 0.0)

        H, W = self._latest_motion_field.shape[1], self._latest_motion_field.shape[2]

        # Clamp to valid range
        y = np.clip(centroid_y, 0, H - 1.001)
        x = np.clip(centroid_x, 0, W - 1.001)

        # Bilinear interpolation
        y0, x0 = int(y), int(x)
        y1, x1 = min(y0 + 1, H - 1), min(x0 + 1, W - 1)
        fy, fx = y - y0, x - x0

        vx = (
            self._latest_motion_field[0, y0, x0] * (1 - fy) * (1 - fx)
            + self._latest_motion_field[0, y1, x0] * fy * (1 - fx)
            + self._latest_motion_field[0, y0, x1] * (1 - fy) * fx
            + self._latest_motion_field[0, y1, x1] * fy * fx
        )
        vy = (
            self._latest_motion_field[1, y0, x0] * (1 - fy) * (1 - fx)
            + self._latest_motion_field[1, y1, x0] * fy * (1 - fx)
            + self._latest_motion_field[1, y0, x1] * (1 - fy) * fx
            + self._latest_motion_field[1, y1, x1] * fy * fx
        )

        return (float(vx), float(vy))

    def get_divergence_at(self, centroid_y: float, centroid_x: float) -> float:
        """Get divergence at centroid. Negative = convergence = intensification."""
        if self._latest_divergence is None:
            return 0.0
        return self._interpolate_scalar(self._latest_divergence, centroid_y, centroid_x)

    def get_curl_at(self, centroid_y: float, centroid_x: float) -> float:
        """Get vorticity/curl at centroid. Large magnitude = rotation = mesocyclone."""
        if self._latest_curl is None:
            return 0.0
        return self._interpolate_scalar(self._latest_curl, centroid_y, centroid_x)

    def extrapolate_trajectory(
        self,
        start_y: float,
        start_x: float,
        horizons_minutes: list,
        time_step_minutes: float = 10.0,
    ) -> list:
        """
        Semi-Lagrangian trajectory extrapolation using the dense motion field.
        
        At each sub-step, the particle position is updated, and the motion field
        is re-sampled at the new position — producing curved, non-linear trajectories
        that follow the actual steering flow.
        
        Returns: List of (lat, lon) tuples for each horizon.
        """
        if self._latest_motion_field is None:
            return []

        resolution_km = settings.mvp_grid_resolution_km
        center_lat = settings.mvp_center_lat
        center_lon = settings.mvp_center_lon
        grid_h = settings.grid_height
        grid_w = settings.grid_width
        precision = settings.coordinate_precision

        trajectory = []
        curr_y, curr_x = float(start_y), float(start_x)

        for horizon in horizons_minutes:
            steps = horizon / time_step_minutes
            step_y, step_x = float(start_y), float(start_x)

            # Sub-step integration (1-minute resolution for smooth curves)
            n_substeps = max(1, int(horizon))
            dt = steps / n_substeps

            for _ in range(n_substeps):
                vx, vy = self.get_velocity_at_centroid(step_y, step_x)
                step_x += vx * dt
                step_y += vy * dt

                # Clamp to grid
                step_x = np.clip(step_x, 0, grid_w - 1)
                step_y = np.clip(step_y, 0, grid_h - 1)

            # Convert grid position to lat/lon with cos(lat) correction
            lat = center_lat + (step_y - grid_h / 2) * (resolution_km / 111.0)
            cos_lat = np.cos(np.radians(lat))
            lon = center_lon + (step_x - grid_w / 2) * (resolution_km / (111.0 * max(0.5, cos_lat)))

            # Clamp to Gujarat bounding box
            lat = np.clip(lat, settings.gujarat_lat_min, settings.gujarat_lat_max)
            lon = np.clip(lon, settings.gujarat_lon_min, settings.gujarat_lon_max)

            trajectory.append({
                "horizon_minutes": horizon,
                "lat": round(float(lat), precision),
                "lon": round(float(lon), precision),
                "grid_y": round(float(step_y), 2),
                "grid_x": round(float(step_x), 2),
            })

        return trajectory

    def compute_sparse_flow(self) -> Optional[Dict]:
        """
        Lucas-Kanade sparse optical flow for feature-point validation.
        Tracks prominent storm cores (Shi-Tomasi corners) across frames.
        
        Returns dict with tracked feature points and their velocities.
        """
        if not HAS_OPENCV or len(self.frame_buffer) < 2:
            return None

        prev_u8 = self._normalize_to_uint8(self.frame_buffer[-2])
        curr_u8 = self._normalize_to_uint8(self.frame_buffer[-1])

        # Shi-Tomasi corner detection on storm cores
        corners = cv2.goodFeaturesToTrack(
            prev_u8,
            maxCorners=200,
            qualityLevel=0.15,
            minDistance=7,
            blockSize=21,
        )

        if corners is None or len(corners) == 0:
            return {"features": [], "count": 0}

        # Lucas-Kanade tracking
        lk_params = dict(
            winSize=(20, 20),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 15, 0.01),
        )

        next_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_u8, curr_u8, corners, None, **lk_params
        )

        # Filter valid tracks
        if next_pts is None:
            return {"features": [], "count": 0}

        tracked = []
        for i, (s, pt_prev, pt_next) in enumerate(zip(status, corners, next_pts)):
            if s[0] == 1:
                dx = pt_next[0][0] - pt_prev[0][0]
                dy = pt_next[0][1] - pt_prev[0][1]
                tracked.append({
                    "prev": (float(pt_prev[0][0]), float(pt_prev[0][1])),
                    "curr": (float(pt_next[0][0]), float(pt_next[0][1])),
                    "dx": float(dx),
                    "dy": float(dy),
                    "speed_pixels": float(np.sqrt(dx**2 + dy**2)),
                })

        return {"features": tracked, "count": len(tracked)}

    # ------------------------------------------------------------------
    # Post-processing helpers
    # ------------------------------------------------------------------

    def _normalize_to_uint8(self, grid: np.ndarray) -> np.ndarray:
        """Normalize reflectivity grid to uint8 [0, 255] for OpenCV."""
        # Clip to valid dBZ range and scale
        clipped = np.clip(grid, 0, 75)
        scaled = (clipped / 75.0 * 255).astype(np.uint8)
        return scaled

    def _reject_outliers(self, field: np.ndarray) -> np.ndarray:
        """Reject motion vectors that are > N standard deviations from local median."""
        for c in range(2):
            magnitude = np.abs(field[c])
            median = np.median(magnitude)
            std = np.std(magnitude)
            threshold = median + self.outlier_std * std
            mask = magnitude > threshold
            field[c][mask] = 0.0
        return field

    def _spatial_smooth(self, field: np.ndarray) -> np.ndarray:
        """Apply Gaussian spatial smoothing to the motion field."""
        if not HAS_OPENCV:
            return field
        for _ in range(self.smoothing_passes):
            field[0] = cv2.GaussianBlur(field[0], (5, 5), 1.0)
            field[1] = cv2.GaussianBlur(field[1], (5, 5), 1.0)
        return field

    def _temporal_smooth(self, field: np.ndarray) -> np.ndarray:
        """Exponential decay temporal averaging across buffered motion fields."""
        if len(self.motion_field_buffer) == 0:
            return field

        alpha = self.temporal_decay
        smoothed = field.copy()

        for past_field in reversed(list(self.motion_field_buffer)):
            if past_field.shape == smoothed.shape:
                smoothed = alpha * smoothed + (1 - alpha) * past_field

        return smoothed

    def _compute_divergence(self, field: np.ndarray) -> np.ndarray:
        """
        Compute 2D divergence of the motion field.
        div(V) = du/dx + dv/dy
        Negative divergence = convergence = updraft/intensification signal.
        """
        du_dx = np.gradient(field[0], axis=1)
        dv_dy = np.gradient(field[1], axis=0)
        return du_dx + dv_dy

    def _compute_curl(self, field: np.ndarray) -> np.ndarray:
        """
        Compute 2D curl (vorticity) of the motion field.
        curl(V) = dv/dx - du/dy
        Large magnitude = rotation = mesocyclone signature.
        """
        dv_dx = np.gradient(field[1], axis=1)
        du_dy = np.gradient(field[0], axis=0)
        return dv_dx - du_dy

    def _interpolate_scalar(
        self, field: np.ndarray, y: float, x: float
    ) -> float:
        """Bilinear interpolation of a 2D scalar field at (y, x)."""
        H, W = field.shape
        y = np.clip(y, 0, H - 1.001)
        x = np.clip(x, 0, W - 1.001)

        y0, x0 = int(y), int(x)
        y1, x1 = min(y0 + 1, H - 1), min(x0 + 1, W - 1)
        fy, fx = y - y0, x - x0

        val = (
            field[y0, x0] * (1 - fy) * (1 - fx)
            + field[y1, x0] * fy * (1 - fx)
            + field[y0, x1] * (1 - fy) * fx
            + field[y1, x1] * fy * fx
        )
        return float(val)

    @property
    def has_motion_field(self) -> bool:
        return self._latest_motion_field is not None

    @property
    def frame_count(self) -> int:
        return len(self.frame_buffer)


# Global singleton
optical_flow_engine = OpticalFlowEngine()
