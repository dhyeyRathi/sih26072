"""
SIH26072 — Real-Data PyTorch Model Trainer v3
Trains StormNowcasterMLP v3 on REAL Open-Meteo historical weather observations.
NO synthetic data is used. Features are normalized with StandardScaler.
Severe storm events are oversampled for balanced training.
"""

import os
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
from typing import Tuple, Dict
from src.ml.model import StormNowcasterMLP
from src.ml.real_data_builder import build_real_dataset, DATASET_PATH


WEIGHTS_DIR = os.path.join(os.path.dirname(__file__), "weights")
WEIGHTS_PATH = os.path.join(WEIGHTS_DIR, "storm_nowcaster.pt")
SCALER_PATH = os.path.join(WEIGHTS_DIR, "feature_scaler.npz")


def _compute_normalization_params(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute mean and std for StandardScaler normalization."""
    mean = np.mean(X, axis=0)
    std = np.std(X, axis=0)
    # Prevent division by zero for constant features
    std[std < 1e-6] = 1.0
    return mean, std


def _normalize_features(X: np.ndarray, mean: np.ndarray, std: np.ndarray) -> np.ndarray:
    """Apply StandardScaler normalization."""
    return (X - mean) / std


def _oversample_severe_events(
    X: np.ndarray,
    Y: Dict[str, np.ndarray],
    oversample_factor: int = 3,
) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
    """
    Oversample severe storm events (high dBZ, high lightning rate) to balance
    the training set. Severe events are rare but most important for accuracy.
    """
    # Identify severe samples: max_dbz > 55 dBZ (feature index 4)
    severe_mask = X[:, 4] > 55.0

    if np.sum(severe_mask) == 0:
        # Also try moderate threshold
        severe_mask = X[:, 4] > 45.0

    if np.sum(severe_mask) == 0:
        return X, Y

    severe_X = X[severe_mask]
    severe_Y = {k: v[severe_mask] for k, v in Y.items()}

    # Repeat severe samples
    repeated_X = np.tile(severe_X, (oversample_factor, 1))
    repeated_Y = {k: np.tile(v, (oversample_factor, 1) if v.ndim == 2 else (oversample_factor, 1, 1))
                  for k, v in severe_Y.items()}

    # Add small noise to repeated samples for diversity
    noise = np.random.randn(*repeated_X.shape).astype(np.float32) * 0.02
    noise[:, 11:] = 0  # Don't noise positional features
    repeated_X += noise

    # Concatenate
    X_out = np.concatenate([X, repeated_X], axis=0)
    Y_out = {k: np.concatenate([Y[k], repeated_Y[k]], axis=0) for k in Y}

    print(f"  Oversampled {np.sum(severe_mask)} severe events × {oversample_factor} "
          f"→ {len(X_out)} total samples")

    return X_out, Y_out


def _augment_features(X: np.ndarray, noise_std: float = 0.03) -> np.ndarray:
    """Add small Gaussian noise to training features for robustness."""
    noise = np.random.randn(*X.shape).astype(np.float32) * noise_std
    # Don't add noise to positional features (indices 11-13) or optical flow placeholders (14-17)
    noise[:, 11:] = 0
    return X + noise


def train_nowcaster_model(epochs: int = 120, batch_size: int = 128) -> Dict[str, float]:
    """
    Trains PyTorch StormNowcasterMLP v3 model on REAL weather data.
    
    Process:
    1. Fetch/load real Open-Meteo historical observations for Gujarat
    2. Normalize features with StandardScaler (saved for inference)
    3. Oversample severe storm events for balanced training
    4. Train with noise augmentation, gradient clipping, cosine annealing
    5. Validate on held-out test set
    6. Save model weights and scaler parameters
    """
    os.makedirs(WEIGHTS_DIR, exist_ok=True)

    print("[TRAIN] Training PyTorch StormNowcasterMLP v3 on REAL weather data...")

    # Step 1: Get real training data
    X, Y = build_real_dataset(years_back=3, min_samples=5000)

    if len(X) < 50:
        print("[WARN] Insufficient real data. Cannot train. Will train when more data is available.")
        return {"mae_km": 0.0, "rmse_km": 0.0, "epochs": 0, "samples": len(X)}

    print(f"  Raw dataset: {len(X)} samples, {X.shape[1]} features")

    # Step 2: Feature normalization
    mean, std = _compute_normalization_params(X)
    X_norm = _normalize_features(X, mean, std)

    # Save scaler for inference
    np.savez(SCALER_PATH, mean=mean, std=std)
    print(f"  Feature scaler saved to {SCALER_PATH}")

    # Step 3: Oversample severe events
    X_norm, Y = _oversample_severe_events(X_norm, Y)

    # Step 4: Noise augmentation
    X_augmented = _augment_features(X_norm.copy())
    X_combined = np.concatenate([X_norm, X_augmented], axis=0)
    Y_combined = {
        k: np.concatenate([v, v], axis=0) for k, v in Y.items()
    }

    # Step 5: Train / Val / Test Split (70/15/15)
    n = len(X_combined)
    indices = np.random.permutation(n)
    train_end = int(0.70 * n)
    val_end = int(0.85 * n)

    train_idx = indices[:train_end]
    val_idx = indices[train_end:val_end]
    test_idx = indices[val_end:]

    X_train = torch.tensor(X_combined[train_idx])
    X_val = torch.tensor(X_combined[val_idx])
    X_test = torch.tensor(X_combined[test_idx])

    Y_train_traj = torch.tensor(Y_combined["trajectories"][train_idx])
    Y_val_traj = torch.tensor(Y_combined["trajectories"][val_idx])
    Y_test_traj = torch.tensor(Y_combined["trajectories"][test_idx])
    Y_train_dbz = torch.tensor(Y_combined["dbz"][train_idx])
    Y_val_dbz = torch.tensor(Y_combined["dbz"][val_idx])
    Y_train_ts = torch.tensor(Y_combined["thunderstorm"][train_idx])
    Y_val_ts = torch.tensor(Y_combined["thunderstorm"][val_idx])
    Y_train_lt = torch.tensor(Y_combined["lightning"][train_idx])
    Y_val_lt = torch.tensor(Y_combined["lightning"][val_idx])

    print(f"  Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")

    # Step 6: Initialize model
    model = StormNowcasterMLP(input_dim=18, hidden_dim=320, mc_dropout=0.1)
    optimizer = optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)

    mse_loss_fn = nn.SmoothL1Loss()
    bce_loss_fn = nn.BCELoss()

    dataset = torch.utils.data.TensorDataset(
        X_train, Y_train_traj, Y_train_dbz, Y_train_ts, Y_train_lt
    )
    loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True, drop_last=True)

    # Step 7: Training loop
    best_val_loss = float("inf")
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

            # Higher weight on trajectory accuracy (the user's primary concern)
            loss = 6.0 * l_traj + 0.3 * l_dbz + 0.8 * l_ts + 0.8 * l_lt
            loss.backward()

            # Gradient clipping for stability
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()
            epoch_loss += loss.item()

        scheduler.step()

        # Validation check
        if (epoch + 1) % 10 == 0:
            model.eval()
            with torch.no_grad():
                val_preds = model(X_val)
                v_traj = mse_loss_fn(val_preds["trajectory_offsets"], Y_val_traj)
                v_dbz = mse_loss_fn(val_preds["dbz_forecasts"], Y_val_dbz)
                v_ts = bce_loss_fn(val_preds["thunderstorm_probs"], Y_val_ts)
                v_lt = bce_loss_fn(val_preds["lightning_probs"], Y_val_lt)
                val_loss = 6.0 * v_traj + 0.3 * v_dbz + 0.8 * v_ts + 0.8 * v_lt

            avg_train = epoch_loss / max(1, len(loader))
            print(f"   Epoch {epoch + 1}/{epochs} - Train: {avg_train:.4f}, Val: {val_loss.item():.4f}")

            if val_loss.item() < best_val_loss:
                best_val_loss = val_loss.item()
                torch.save(model.state_dict(), WEIGHTS_PATH)

            model.train()

    # Step 8: Final test evaluation
    model.eval()
    with torch.no_grad():
        test_preds = model(X_test)
        test_traj_err = torch.abs(test_preds["trajectory_offsets"] - Y_test_traj)
        mae_km = float(test_traj_err.mean().item())
        rmse_km = float(torch.sqrt((test_traj_err ** 2).mean()).item())

    # Save final weights if no validation checkpoint was saved
    if not os.path.exists(WEIGHTS_PATH):
        torch.save(model.state_dict(), WEIGHTS_PATH)

    print(f"[OK] Trained PyTorch Nowcaster v3 Saved: {WEIGHTS_PATH}")
    print(f"     Test MAE: {mae_km:.3f} grid units, Test RMSE: {rmse_km:.3f} grid units")
    print(f"     Total samples: {len(X_combined)}, Epochs: {epochs}")

    return {
        "mae_km": round(mae_km, 3),
        "rmse_km": round(rmse_km, 3),
        "epochs": epochs,
        "samples": len(X_combined),
        "best_val_loss": round(best_val_loss, 4),
    }


if __name__ == "__main__":
    train_nowcaster_model()
