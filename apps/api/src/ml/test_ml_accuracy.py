"""
SIH26072 — ML Model Accuracy & Evaluation Benchmark
Compares PyTorch Deep Neural Nowcaster vs Baseline Linear Persistence Model.
"""

import numpy as np
from src.ml.trainer import generate_synthetic_storm_dataset
from src.ml.inference import StormMLInference


def evaluate_accuracy_benchmark():
    print("=" * 70)
    print("🌩️  SIH26072 — STORM NOWCASTING ACCURACY EVALUATION BENCHMARK")
    print("=" * 70)

    # 1. Initialize ML Inference Engine
    inference = StormMLInference()
    
    # 2. Generate Evaluation Test Set (1000 independent samples)
    X_test, Y_test = generate_synthetic_storm_dataset(num_samples=1000, seed=999)

    ml_errors_km = []
    linear_errors_km = []

    horizons = [15, 30, 45, 60]

    for i in range(len(X_test)):
        feat = X_test[i]
        true_trajs = Y_test["trajectories"][i]  # shape (4, 2) -> (dx, dy) in grid km

        vx, vy = feat[0], feat[1]
        
        # Synthetic Cell Object & History
        cell = {
            "centroid_y": 100.0,
            "centroid_x": 100.0,
            "center_lat": 23.0225,
            "center_lon": 72.5714,
            "velocity_x": vx,
            "velocity_y": vy,
            "max_reflectivity_dbz": feat[4],
            "mean_reflectivity_dbz": feat[5],
            "area_sq_km": feat[7],
            "lightning_rate": feat[9],
        }

        history = [
            {"x": 100.0 - 2 * vx, "y": 100.0 - 2 * vy, "max_reflectivity_dbz": feat[4] - feat[6]},
            {"x": 100.0 - vx, "y": 100.0 - vy, "max_reflectivity_dbz": feat[4] - 0.5 * feat[6]},
            {"x": 100.0, "y": 100.0, "max_reflectivity_dbz": feat[4]},
        ]

        # A) ML PyTorch Model Forecast
        nowcast = inference.predict_cell_nowcast(cell, history, horizons_minutes=horizons)
        ml_forecasts = nowcast["forecasts"]

        # Calculate ML Spatial Errors (km)
        for h_idx, h in enumerate(horizons):
            true_dx, true_dy = true_trajs[h_idx]
            
            # Linear model prediction
            steps = h / 10.0
            lin_dx = vx * steps
            lin_dy = vy * steps

            # ML predicted position delta
            pred_lat = ml_forecasts[h_idx]["predicted_lat"]
            pred_lon = ml_forecasts[h_idx]["predicted_lon"]
            
            # Lat/Lon displacement back to km (1 deg ~ 111 km)
            ml_dy = (pred_lat - 23.0225) * 111.0
            ml_dx = (pred_lon - 72.5714) * 111.0

            ml_err = np.sqrt((ml_dx - true_dx)**2 + (ml_dy - true_dy)**2)
            lin_err = np.sqrt((lin_dx - true_dx)**2 + (lin_dy - true_dy)**2)

            ml_errors_km.append(ml_err)
            linear_errors_km.append(lin_err)

    ml_mae = float(np.mean(ml_errors_km))
    ml_rmse = float(np.sqrt(np.mean(np.square(ml_errors_km))))

    lin_mae = float(np.mean(linear_errors_km))
    lin_rmse = float(np.sqrt(np.mean(np.square(linear_errors_km))))

    improvement_pct = ((lin_mae - ml_mae) / lin_mae) * 100.0

    print(f"\n📊 EVALUATION RESULTS OVER {len(X_test)} TEST TRAJECTORIES:")
    print(f"--------------------------------------------------")
    print(f"  • Baseline Linear Extrapolation: MAE = {lin_mae:.3f} km | RMSE = {lin_rmse:.3f} km")
    print(f"  • PyTorch Deep Neural Nowcaster: MAE = {ml_mae:.3f} km | RMSE = {ml_rmse:.3f} km")
    print(f"  ⚡ Accuracy Improvement: {improvement_pct:.1f}% reduction in position error!")
    print(f"--------------------------------------------------\n")

    assert ml_mae < lin_mae, "PyTorch Deep Nowcaster should have lower MAE than linear extrapolation!"
    print("✅ Benchmark Test Passed Successfully!")


if __name__ == "__main__":
    evaluate_accuracy_benchmark()
