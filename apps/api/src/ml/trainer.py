"""
SIH26072 — Atmospheric Dataset Generator & PyTorch Model Trainer
Generates physics-rich storm trajectory training datasets with wind shear, 
storm rotation, anvil spread, and noise augmentation. Trains StormNowcasterMLP v2.
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


def generate_synthetic_storm_dataset(num_samples: int = 25000, seed: int = 42) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Generates physics-guided synthetic storm trajectories and feature matrices.
    
    Physics modeled:
    - Non-linear steering flow with environmental wind shear
    - Storm cell acceleration and deceleration (convective bursts)
    - Right-moving supercell turning vectors (Coriolis effect)
    - Storm rotation (mesocyclone) influence on trajectory curvature
    - Reflectivity evolution (convective growth, maturity, decay lifecycle)
    - Lightning flash rate correlation with updraft strength
    - Anvil spread affecting cell area growth
    - Environmental instability affecting intensification rate
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
        # --- Kinematic initial conditions ---
        speed_kmh = np.random.uniform(8.0, 60.0)
        direction_deg = np.random.uniform(0.0, 360.0)
        rad = np.radians(direction_deg)

        grid_dist_per_step = (speed_kmh * (time_step_min / 60.0)) / 1.0
        vx = grid_dist_per_step * np.sin(rad)
        vy = -grid_dist_per_step * np.cos(rad)

        # --- Non-linear dynamics ---
        # Turning rate: right-movers tend +0.05 rad/step, left-movers -0.05
        storm_type = np.random.choice(["right_mover", "left_mover", "linear"], p=[0.4, 0.15, 0.45])
        if storm_type == "right_mover":
            turning_rate = np.random.uniform(0.02, 0.15)
        elif storm_type == "left_mover":
            turning_rate = np.random.uniform(-0.15, -0.02)
        else:
            turning_rate = np.random.uniform(-0.04, 0.04)

        # Wind shear modulation: stronger shear → more deviation at longer horizons
        wind_shear_factor = np.random.uniform(0.0, 0.08)

        # Acceleration (convective burst can speed up or slow down cell)
        ax = np.random.uniform(-0.12, 0.12)
        ay = np.random.uniform(-0.12, 0.12)

        # --- Reflectivity and lightning ---
        max_dbz = np.random.uniform(25.0, 70.0)
        mean_dbz = max_dbz * np.random.uniform(0.60, 0.85)

        # Storm lifecycle stage affects dBZ trend
        lifecycle = np.random.choice(["growing", "mature", "decaying"], p=[0.35, 0.40, 0.25])
        if lifecycle == "growing":
            dbz_trend = np.random.uniform(0.5, 5.0)
        elif lifecycle == "mature":
            dbz_trend = np.random.uniform(-1.5, 1.5)
        else:
            dbz_trend = np.random.uniform(-5.0, -0.5)

        area_sq_km = np.random.uniform(20.0, 500.0)
        # Anvil spread: growing storms expand area
        if lifecycle == "growing":
            d_area = np.random.uniform(2.0, 25.0)
        elif lifecycle == "mature":
            d_area = np.random.uniform(-5.0, 10.0)
        else:
            d_area = np.random.uniform(-20.0, -2.0)

        # Lightning rate correlates with updraft strength (proxy: max_dbz)
        lightning_rate = max(0.0, (max_dbz - 30.0) * np.random.uniform(0.5, 3.0))
        d_lightning = np.random.uniform(-4.0, 6.0) if lifecycle != "decaying" else np.random.uniform(-6.0, -1.0)

        lat_offset = np.random.uniform(-0.9, 0.9)
        lon_offset = np.random.uniform(-0.9, 0.9)
        curvature = turning_rate

        # Feature vector (dim=14)
        x_feat = np.array([
            vx, vy, ax, ay, max_dbz, mean_dbz, dbz_trend,
            area_sq_km, d_area, lightning_rate, d_lightning,
            lat_offset, lon_offset, curvature
        ], dtype=np.float32)

        # --- Ground truth simulation for 4 horizons ---
        sample_trajs = []
        sample_dbz = []
        sample_ts = []
        sample_lt = []

        for h in horizons:
            steps = h / time_step_min

            # Integrated non-linear curved trajectory with wind shear
            total_dx = 0.0
            total_dy = 0.0
            s_rad = rad
            for s in range(1, int(steps) + 1):
                s_rad += turning_rate
                # Wind shear adds increasing deviation with altitude/time
                shear_dx = wind_shear_factor * s * np.cos(s_rad + np.pi / 4)
                shear_dy = wind_shear_factor * s * np.sin(s_rad + np.pi / 4)

                s_vx = grid_dist_per_step * np.sin(s_rad) + ax * s + shear_dx
                s_vy = -grid_dist_per_step * np.cos(s_rad) + ay * s + shear_dy
                total_dx += s_vx
                total_dy += s_vy

            # Reflectivity evolution following lifecycle
            h_dbz = np.clip(max_dbz + dbz_trend * (h / 20.0), 10.0, 75.0)

            # Calibrated probabilities (sigmoid on dBZ thresholds)
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


def _augment_features(X: np.ndarray, noise_std: float = 0.03) -> np.ndarray:
    """Add small Gaussian noise to training features for robustness."""
    noise = np.random.randn(*X.shape).astype(np.float32) * noise_std
    # Don't add noise to the curvature or positional features (indices 11-13)
    noise[:, 11:] = 0
    return X + noise


def train_nowcaster_model(epochs: int = 80, batch_size: int = 128) -> Dict[str, float]:
    """
    Trains PyTorch StormNowcasterMLP v2 model and saves weights.
    
    Improvements:
    - 25,000 training samples (vs 12,000)
    - 80 epochs (vs 25-60)
    - Noise augmentation for robustness
    - Higher trajectory loss weight (5.0 vs 3.0) for path accuracy
    - Gradient clipping for training stability
    """
    os.makedirs(WEIGHTS_DIR, exist_ok=True)

    print("[TRAIN] Training PyTorch StormNowcasterMLP v2 Model...")
    X, Y = generate_synthetic_storm_dataset(num_samples=25000)

    # Noise augmentation
    X_augmented = _augment_features(X.copy())
    X_combined = np.concatenate([X, X_augmented], axis=0)
    Y_combined = {
        k: np.concatenate([v, v], axis=0) for k, v in Y.items()
    }

    # Train / Val Split (85/15)
    split = int(0.85 * len(X_combined))
    X_train = torch.tensor(X_combined[:split])
    X_val = torch.tensor(X_combined[split:])

    Y_train_traj = torch.tensor(Y_combined["trajectories"][:split])
    Y_val_traj = torch.tensor(Y_combined["trajectories"][split:])
    Y_train_dbz = torch.tensor(Y_combined["dbz"][:split])
    Y_val_dbz = torch.tensor(Y_combined["dbz"][split:])
    Y_train_ts = torch.tensor(Y_combined["thunderstorm"][:split])
    Y_val_ts = torch.tensor(Y_combined["thunderstorm"][split:])
    Y_train_lt = torch.tensor(Y_combined["lightning"][:split])
    Y_val_lt = torch.tensor(Y_combined["lightning"][split:])

    model = StormNowcasterMLP(input_dim=14, hidden_dim=256, mc_dropout=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    mse_loss_fn = nn.SmoothL1Loss()
    bce_loss_fn = nn.BCELoss()

    dataset = torch.utils.data.TensorDataset(
        X_train, Y_train_traj, Y_train_dbz, Y_train_ts, Y_train_lt
    )
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)

    model.train()
    for epoch in range(epochs):
        epoch_loss = 0.0
        for batch_x, batch_traj, batch_dbz, batch_ts, batch_lt in loader:
            optimizer.zero_grad()
            preds = model(batch_x)

            l_traj = mse_loss_fn(preds["trajectory_offsets"], batch_traj)
            l_dbz = mse_loss_fn(preds["dbz_forecasts"], batch_dbz)
            l_ts = bce_loss_fn(preds["thunderstorm_probs"], batch_ts)
            l_lt = bce_loss_fn(preds["lightning_probs"], batch_lt)

            # Higher weight on trajectory accuracy
            loss = 5.0 * l_traj + 0.3 * l_dbz + 0.8 * l_ts + 0.8 * l_lt
            loss.backward()

            # Gradient clipping for stability
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()
            epoch_loss += loss.item()

        scheduler.step()

        if (epoch + 1) % 20 == 0:
            avg_loss = epoch_loss / len(loader)
            print(f"   Epoch {epoch + 1}/{epochs} - Loss: {avg_loss:.4f}")

    # Validation evaluation
    model.eval()
    with torch.no_grad():
        val_preds = model(X_val)
        val_traj_err = torch.abs(val_preds["trajectory_offsets"] - Y_val_traj)
        mae_km = float(val_traj_err.mean().item())
        rmse_km = float(torch.sqrt((val_traj_err ** 2).mean()).item())

    # Save model weights
    torch.save(model.state_dict(), WEIGHTS_PATH)
    print(f"[OK] Trained PyTorch Nowcaster v2 Saved: {WEIGHTS_PATH} (MAE: {mae_km:.3f} km, RMSE: {rmse_km:.3f} km)")

    return {
        "mae_km": round(mae_km, 3),
        "rmse_km": round(rmse_km, 3),
        "epochs": epochs,
    }


if __name__ == "__main__":
    train_nowcaster_model()
