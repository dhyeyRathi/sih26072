"""
SIH26072 — Atmospheric Dataset Generator & PyTorch Model Trainer
Generates physical storm trajectory training datasets and trains StormNowcasterMLP.
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import Tuple, Dict
from src.ml.model import StormNowcasterMLP


WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights")
WEIGHTS_PATH = os.path.join(WEIGHTS_DIR, "storm_nowcaster.pt")


def generate_synthetic_storm_dataset(num_samples: int = 10000, seed: int = 42) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Generates physics-guided synthetic storm trajectories and feature matrices.
    Simulates non-linear steering flow, storm cell acceleration, right-moving turning vectors,
    reflectivity evolution (convective growth/decay), and lightning flash rates.
    """
    np.random.seed(seed)
    
    inputs = []
    target_trajs = []
    target_dbz = []
    target_ts_probs = []
    target_lt_probs = []

    horizons = [15, 30, 45, 60]
    time_step_min = 10.0

    for _ in range(num_samples):
        # Initial kinematics
        speed_kmh = np.random.uniform(10.0, 50.0)
        direction_deg = np.random.uniform(0.0, 360.0)
        rad = np.radians(direction_deg)
        
        # Grid velocity vector (grid resolution 1km, time step 10 min)
        grid_dist_per_step = (speed_kmh * (time_step_min / 60.0)) / 1.0
        vx = grid_dist_per_step * np.sin(rad)
        vy = -grid_dist_per_step * np.cos(rad)
        
        # Acceleration and non-linear turning (Coriolis / right-mover vector)
        turning_rate = np.random.uniform(-0.12, 0.12)  # curvature rad/step
        ax = np.random.uniform(-0.15, 0.15)
        ay = np.random.uniform(-0.15, 0.15)

        max_dbz = np.random.uniform(25.0, 68.0)
        mean_dbz = max_dbz * np.random.uniform(0.65, 0.85)
        dbz_trend = np.random.uniform(-4.0, 4.0)

        area_sq_km = np.random.uniform(25.0, 400.0)
        d_area = np.random.uniform(-15.0, 20.0)

        lightning_rate = max(0.0, (max_dbz - 35.0) * np.random.uniform(0.5, 2.5))
        d_lightning = np.random.uniform(-3.0, 5.0)

        lat_offset = np.random.uniform(-0.8, 0.8)
        lon_offset = np.random.uniform(-0.8, 0.8)
        curvature = turning_rate

        # Feature vector (dim=14)
        x_feat = np.array([
            vx, vy, ax, ay, max_dbz, mean_dbz, dbz_trend,
            area_sq_km, d_area, lightning_rate, d_lightning,
            lat_offset, lon_offset, curvature
        ], dtype=np.float32)

        # Ground truth simulation for 4 horizons
        sample_trajs = []
        sample_dbz = []
        sample_ts = []
        sample_lt = []

        curr_rad = rad
        curr_dbz = max_dbz

        for h in horizons:
            steps = h / time_step_min
            
            # Integrated non-linear curved trajectory
            total_dx = 0.0
            total_dy = 0.0
            s_rad = rad
            for s in range(1, int(steps) + 1):
                s_rad += turning_rate
                s_vx = grid_dist_per_step * np.sin(s_rad) + ax * s
                s_vy = -grid_dist_per_step * np.cos(s_rad) + ay * s
                total_dx += s_vx
                total_dy += s_vy

            # Reflectivity decay/growth over time
            h_dbz = np.clip(curr_dbz + dbz_trend * (h / 30.0), 10.0, 75.0)
            
            # Calibrated true probabilities
            ts_prob = 1.0 / (1.0 + np.exp(-(h_dbz - 32.0) / 5.0))
            lt_prob = 1.0 / (1.0 + np.exp(-(h_dbz - 42.0) / 4.0))

            sample_trajs.append([total_dx, total_dy])
            sample_dbz.append(h_dbz)
            sample_ts.append(ts_prob)
            sample_lt.append(lt_prob)

        inputs.append(x_feat)
        target_trajs.append(sample_trajs)
        target_dbz.append(sample_dbz)
        target_ts_probs.append(sample_ts)
        target_lt_probs.append(sample_lt)

    X = np.array(inputs, dtype=np.float32)
    Y = {
        "trajectories": np.array(target_trajs, dtype=np.float32),
        "dbz": np.array(target_dbz, dtype=np.float32),
        "thunderstorm": np.array(target_ts_probs, dtype=np.float32),
        "lightning": np.array(target_lt_probs, dtype=np.float32),
    }

    return X, Y


def train_nowcaster_model(epochs: int = 60, batch_size: int = 64) -> Dict[str, float]:
    """
    Trains PyTorch StormNowcasterMLP model and saves weights.
    Returns metrics dictionary (train loss, validation MAE km, accuracy).
    """
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    
    print("🧠 Training PyTorch StormNowcasterMLP Model...")
    X, Y = generate_synthetic_storm_dataset(num_samples=12000)

    # Train / Val Split
    split = int(0.85 * len(X))
    X_train, X_val = torch.tensor(X[:split]), torch.tensor(X[split:])
    
    Y_train_traj, Y_val_traj = torch.tensor(Y["trajectories"][:split]), torch.tensor(Y["trajectories"][split:])
    Y_train_dbz, Y_val_dbz = torch.tensor(Y["dbz"][:split]), torch.tensor(Y["dbz"][split:])
    Y_train_ts, Y_val_ts = torch.tensor(Y["thunderstorm"][:split]), torch.tensor(Y["thunderstorm"][split:])
    Y_train_lt, Y_val_lt = torch.tensor(Y["lightning"][:split]), torch.tensor(Y["lightning"][split:])

    model = StormNowcasterMLP(input_dim=14, hidden_dim=128)
    optimizer = optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    
    mse_loss_fn = nn.SmoothL1Loss()
    bce_loss_fn = nn.BCELoss()

    dataset = torch.utils.data.TensorDataset(X_train, Y_train_traj, Y_train_dbz, Y_train_ts, Y_train_lt)
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model.train()
    for epoch in range(epochs):
        for batch_x, batch_traj, batch_dbz, batch_ts, batch_lt in loader:
            optimizer.zero_grad()
            preds = model(batch_x)

            l_traj = mse_loss_fn(preds["trajectory_offsets"], batch_traj)
            l_dbz = mse_loss_fn(preds["dbz_forecasts"], batch_dbz)
            l_ts = bce_loss_fn(preds["thunderstorm_probs"], batch_ts)
            l_lt = bce_loss_fn(preds["lightning_probs"], batch_lt)

            loss = 3.0 * l_traj + 0.3 * l_dbz + 0.8 * l_ts + 0.8 * l_lt
            loss.backward()
            optimizer.step()
            
        scheduler.step()

    # Evaluation on Val set
    model.eval()
    with torch.no_grad():
        val_preds = model(X_val)
        val_traj_err = torch.abs(val_preds["trajectory_offsets"] - Y_val_traj)
        mae_km = float(val_traj_err.mean().item())
        rmse_km = float(torch.sqrt((val_traj_err ** 2).mean()).item())

    # Save model weights
    torch.save(model.state_dict(), WEIGHTS_PATH)
    print(f"✅ Trained PyTorch Nowcaster Saved: {WEIGHTS_PATH} (MAE: {mae_km:.3f} km, RMSE: {rmse_km:.3f} km)")

    return {
        "mae_km": round(mae_km, 3),
        "rmse_km": round(rmse_km, 3),
        "epochs": epochs,
    }


if __name__ == "__main__":
    train_nowcaster_model()
