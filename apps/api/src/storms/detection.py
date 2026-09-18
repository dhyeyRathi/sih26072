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
    threshold_dbz: float = 45.0,
    min_area_cells: int = 25,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
) -> list[dict]:
    """
    Detect individual storm cells from a reflectivity grid.
    Filters out noise specks and transient artifacts to maintain clean, persistent storm cell objects.
    """
    center_lat = center_lat or settings.mvp_center_lat
    center_lon = center_lon or settings.mvp_center_lon
    grid_h, grid_w = reflectivity_grid.shape
    resolution_km = settings.mvp_grid_resolution_km

    # Step 1: Binary threshold at storm core intensity (45+ dBZ)
    binary = (reflectivity_grid >= threshold_dbz).astype(np.int32)

    # Step 2: Connected-component labeling
    labeled, num_features = ndimage.label(binary)

    if num_features == 0:
        return []

    # Step 3 & 4: Extract properties for each major storm component
    cells = []
    for label_id in range(1, num_features + 1):
        mask = labeled == label_id
        area_cells = int(np.sum(mask))

        # Filter out small noise components (< 25 grid cells = 25 sq km)
        if area_cells < min_area_cells:
            continue

        cell_values = reflectivity_grid[mask]
        max_dbz = float(np.max(cell_values))
        mean_dbz = float(np.mean(cell_values))

        # Intensity-weighted centroid
        ys, xs = np.where(mask)
        weights = np.maximum(1.0, cell_values - 40.0)
        centroid_y = float(np.average(ys, weights=weights))
        centroid_x = float(np.average(xs, weights=weights))

        min_y, max_y = int(np.min(ys)), int(np.max(ys))
        min_x, max_x = int(np.min(xs)), int(np.max(xs))

        lat = center_lat + (centroid_y - grid_h / 2) * (resolution_km / 111.0)
        lon = center_lon + (centroid_x - grid_w / 2) * (resolution_km / 111.0)

        area_sq_km = area_cells * (resolution_km ** 2)

        if max_dbz >= 55:
            intensity = "severe"
        elif max_dbz >= 45:
            intensity = "strong"
        elif max_dbz >= 35:
            intensity = "moderate"
        else:
            intensity = "weak"

        cells.append({
            "centroid_y": centroid_y,
            "centroid_x": centroid_x,
            "center_lat": round(float(lat), 4),
            "center_lon": round(float(lon), 4),
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

    return cells
