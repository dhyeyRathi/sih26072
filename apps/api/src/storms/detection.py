"""
Storm cell detection using reflectivity thresholding and connected-component labeling.
Simplified TITAN-like approach for identifying individual storm objects from radar grids.
"""

import numpy as np
from scipy import ndimage
from typing import Optional
from src.config import settings


def detect_storm_cells(
    reflectivity_grid: np.ndarray,
    threshold_dbz: float = 35.0,
    min_area_cells: int = 10,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
) -> list[dict]:
    """
    Detect individual storm cells from a reflectivity grid.

    Algorithm:
    1. Threshold the reflectivity grid at `threshold_dbz`
    2. Label connected components using scipy.ndimage
    3. Filter out small components (< min_area_cells)
    4. Extract properties for each cell (centroid, area, max intensity, etc.)

    Args:
        reflectivity_grid: 2D numpy array of reflectivity values (dBZ)
        threshold_dbz: Minimum reflectivity to consider as storm (default 35 dBZ)
        min_area_cells: Minimum number of grid cells to qualify as a storm
        center_lat: Latitude of grid center for coordinate conversion
        center_lon: Longitude of grid center for coordinate conversion

    Returns:
        List of detected storm cell dictionaries
    """
    center_lat = center_lat or settings.mvp_center_lat
    center_lon = center_lon or settings.mvp_center_lon
    grid_h, grid_w = reflectivity_grid.shape
    resolution_km = settings.mvp_grid_resolution_km

    # Step 1: Binary threshold
    binary = (reflectivity_grid >= threshold_dbz).astype(np.int32)

    # Step 2: Connected-component labeling
    labeled, num_features = ndimage.label(binary)

    if num_features == 0:
        return []

    # Step 3 & 4: Extract properties for each component
    cells = []
    for label_id in range(1, num_features + 1):
        mask = labeled == label_id
        area_cells = int(np.sum(mask))

        # Filter small components
        if area_cells < min_area_cells:
            continue

        # Cell properties
        cell_values = reflectivity_grid[mask]
        max_dbz = float(np.max(cell_values))
        mean_dbz = float(np.mean(cell_values))

        # Centroid (intensity-weighted)
        ys, xs = np.where(mask)
        weights = cell_values
        centroid_y = float(np.average(ys, weights=weights))
        centroid_x = float(np.average(xs, weights=weights))

        # Bounding box
        min_y, max_y = int(np.min(ys)), int(np.max(ys))
        min_x, max_x = int(np.min(xs)), int(np.max(xs))

        # Convert grid position to lat/lon
        lat = center_lat + (centroid_y - grid_h / 2) * (resolution_km / 111.0)
        lon = center_lon + (centroid_x - grid_w / 2) * (resolution_km / 111.0)

        # Area in sq km
        area_sq_km = area_cells * (resolution_km ** 2)

        # Intensity classification
        if max_dbz >= 55:
            intensity = "severe"
        elif max_dbz >= 45:
            intensity = "strong"
        elif max_dbz >= 35:
            intensity = "moderate"
        else:
            intensity = "weak"

        # Build footprint polygon (convex hull of cell pixels in lat/lon)
        footprint_coords = []
        for y, x in zip(ys, xs):
            f_lat = center_lat + (y - grid_h / 2) * (resolution_km / 111.0)
            f_lon = center_lon + (x - grid_w / 2) * (resolution_km / 111.0)
            footprint_coords.append([round(f_lon, 4), round(f_lat, 4)])

        cells.append({
            "centroid_y": round(centroid_y, 2),
            "centroid_x": round(centroid_x, 2),
            "center_lat": round(lat, 4),
            "center_lon": round(lon, 4),
            "max_reflectivity_dbz": round(max_dbz, 1),
            "mean_reflectivity_dbz": round(mean_dbz, 1),
            "area_cells": area_cells,
            "area_sq_km": round(area_sq_km, 1),
            "intensity": intensity,
            "bbox": {
                "min_y": min_y, "max_y": max_y,
                "min_x": min_x, "max_x": max_x
            },
            "label_id": label_id,
        })

    # Sort by intensity (strongest first)
    cells.sort(key=lambda c: c["max_reflectivity_dbz"], reverse=True)

    return cells
