"""
Training script for the radar nowcasting model.

ML development strategy (CORE.md Section 9):
  Baseline 0: Persistence (current state = future state)
  Baseline 1: Radar-only ConvLSTM model
"""

import os
import time
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from src.convlstm import create_model
from src.dataset import create_dataloaders


def train(
    epochs: int = 50,
    batch_size: int = 8,
    lr: float = 1e-3,
    hidden_channels: int = 64,
    num_layers: int = 3,
    grid_size: int = 64,
    num_train: int = 800,
    num_val: int = 200,
    save_dir: str = "./models",
    device: str = None,
):
    """
    Train the ConvLSTM nowcasting model.

    Loss: weighted combination of:
    - MSE for reflectivity (regression)
    - BCE for thunderstorm probability (classification)
    - BCE for lightning probability (classification)
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"🌩️  SIH26072 — Nowcasting Model Training")
    print(f"   Device: {device}")
    print(f"   Grid: {grid_size}x{grid_size}")
    print(f"   Epochs: {epochs}")
    print(f"   Batch size: {batch_size}")
    print(f"   Hidden channels: {hidden_channels}")
    print(f"   Layers: {num_layers}")
    print()

    # Create model
    model = create_model(
        input_channels=1,
        hidden_channels=hidden_channels,
        num_layers=num_layers,
        output_horizons=6,
    ).to(device)

    param_count = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"   Parameters: {param_count:,}")

    # Create dataloaders
    train_loader, val_loader = create_dataloaders(
        num_train=num_train,
        num_val=num_val,
        batch_size=batch_size,
        grid_size=grid_size,
    )

    # Loss functions
    mse_loss = nn.MSELoss()
    bce_loss = nn.BCELoss()

    # Optimizer + scheduler
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    # Training loop
    os.makedirs(save_dir, exist_ok=True)
    best_val_loss = float("inf")
    patience = 10
    patience_counter = 0

    for epoch in range(1, epochs + 1):
        # --- Train ---
        model.train()
        train_loss = 0.0
        train_steps = 0

        for inputs, targets in train_loader:
            inputs = inputs.to(device)
            target_refl = targets["reflectivity"].to(device)
            target_ts = targets["thunderstorm_prob"].to(device)
            target_lt = targets["lightning_prob"].to(device)

            optimizer.zero_grad()

            outputs = model(inputs)

            # Weighted loss
            loss_refl = mse_loss(outputs["reflectivity"], target_refl)
            loss_ts = bce_loss(outputs["thunderstorm_prob"], target_ts)
            loss_lt = bce_loss(outputs["lightning_prob"], target_lt)

            loss = 1.0 * loss_refl + 0.5 * loss_ts + 0.5 * loss_lt
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

            optimizer.step()

            train_loss += loss.item()
            train_steps += 1

        avg_train_loss = train_loss / max(train_steps, 1)

        # --- Validate ---
        model.eval()
        val_loss = 0.0
        val_steps = 0
        val_mse = 0.0

        with torch.no_grad():
            for inputs, targets in val_loader:
                inputs = inputs.to(device)
                target_refl = targets["reflectivity"].to(device)
                target_ts = targets["thunderstorm_prob"].to(device)
                target_lt = targets["lightning_prob"].to(device)

                outputs = model(inputs)

                loss_refl = mse_loss(outputs["reflectivity"], target_refl)
                loss_ts = bce_loss(outputs["thunderstorm_prob"], target_ts)
                loss_lt = bce_loss(outputs["lightning_prob"], target_lt)

                loss = 1.0 * loss_refl + 0.5 * loss_ts + 0.5 * loss_lt
                val_loss += loss.item()
                val_mse += loss_refl.item()
                val_steps += 1

        avg_val_loss = val_loss / max(val_steps, 1)
        avg_val_mse = val_mse / max(val_steps, 1)

        scheduler.step()

        # Logging
        print(
            f"  Epoch {epoch:3d}/{epochs} | "
            f"Train Loss: {avg_train_loss:.4f} | "
            f"Val Loss: {avg_val_loss:.4f} | "
            f"Val MSE: {avg_val_mse:.4f} | "
            f"LR: {scheduler.get_last_lr()[0]:.2e}"
        )

        # Save best model
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            patience_counter = 0
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "val_loss": best_val_loss,
                "config": {
                    "hidden_channels": hidden_channels,
                    "num_layers": num_layers,
                    "grid_size": grid_size,
                },
            }, os.path.join(save_dir, "best_model.pt"))
            print(f"  ✅ Saved best model (val_loss: {best_val_loss:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print(f"\n  ⏹️  Early stopping at epoch {epoch}")
                break

    # Save final model
    torch.save({
        "epoch": epoch,
        "model_state_dict": model.state_dict(),
        "config": {
            "hidden_channels": hidden_channels,
            "num_layers": num_layers,
            "grid_size": grid_size,
        },
    }, os.path.join(save_dir, "final_model.pt"))

    print(f"\n  ✅ Training complete. Best val loss: {best_val_loss:.4f}")
    print(f"  📁 Models saved to: {save_dir}")

    return model


if __name__ == "__main__":
    train(
        epochs=50,
        batch_size=8,
        lr=1e-3,
        hidden_channels=64,
        num_layers=3,
        grid_size=64,
        num_train=500,
        num_val=100,
        save_dir="./models",
    )
