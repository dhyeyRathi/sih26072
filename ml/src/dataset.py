"""
PyTorch Dataset for radar nowcasting training.

Training sample design (CORE.md Section 8):
  Input window:  T-60, T-50, T-40, T-30, T-20, T-10, T  (7 frames)
  Target window: T+10, T+20, T+30, T+40, T+50, T+60     (6 frames)
"""

import numpy as np
import torch
from torch.utils.data import Dataset
from typing import Optional
import os
import sys

# Add parent paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'api'))


class RadarSequenceDataset(Dataset):
    """
    Dataset that generates radar frame sequences from simulated data.
    For production, this would load from NetCDF/HDF5/Zarr archives.

    Each sample:
    - Input:  7 consecutive frames (60 minutes of history)
    - Target: 6 future frames (60 minutes of forecast)
    """

    def __init__(
        self,
        num_samples: int = 1000,
        input_length: int = 7,
        output_length: int = 6,
        grid_size: int = 64,  # Use smaller grid for training (crop from 200x200)
        seed: int = 42,
        augment: bool = True,
    ):
        self.num_samples = num_samples
        self.input_length = input_length
        self.output_length = output_length
        self.total_length = input_length + output_length
        self.grid_size = grid_size
        self.augment = augment
        self.rng = np.random.default_rng(seed)

        # Pre-generate all sequences for reproducibility
        self.sequences = self._generate_sequences()

    def _generate_sequences(self) -> list[np.ndarray]:
        """Generate synthetic radar sequences with moving storm cells."""
        sequences = []

        for _ in range(self.num_samples):
            seq = np.zeros((self.total_length, self.grid_size, self.grid_size), dtype=np.float32)

            # Generate 1-3 storms per sequence
            n_storms = self.rng.integers(1, 4)

            for _ in range(n_storms):
                # Storm properties
                cy = self.rng.uniform(10, self.grid_size - 10)
                cx = self.rng.uniform(10, self.grid_size - 10)
                vy = self.rng.uniform(-1.5, 1.5)
                vx = self.rng.uniform(0.3, 2.0)
                radius = self.rng.uniform(3, 10)
                max_dbz = self.rng.uniform(30, 65)
                growth = self.rng.uniform(-0.05, 0.15)

                for t in range(self.total_length):
                    # Update position
                    cy_t = cy + vy * t
                    cx_t = cx + vx * t
                    r_t = max(2, radius + growth * t)
                    dbz_t = max(15, max_dbz + self.rng.uniform(-2, 2))

                    # Draw gaussian blob
                    y_coords = np.arange(self.grid_size)
                    x_coords = np.arange(self.grid_size)
                    yy, xx = np.meshgrid(y_coords, x_coords, indexing='ij')

                    dist = np.sqrt((yy - cy_t) ** 2 + (xx - cx_t) ** 2)
                    storm_field = dbz_t * np.exp(-(dist ** 2) / (2 * r_t ** 2))

                    seq[t] = np.maximum(seq[t], storm_field)

            # Add background noise
            noise = self.rng.uniform(0, 5, size=seq.shape).astype(np.float32)
            seq = np.clip(seq + noise, 0, 75)

            sequences.append(seq)

        return sequences

    def __len__(self) -> int:
        return self.num_samples

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        seq = self.sequences[idx].copy()

        # Data augmentation
        if self.augment and self.rng.random() > 0.5:
            # Random horizontal flip
            seq = seq[:, :, ::-1].copy()

        if self.augment and self.rng.random() > 0.5:
            # Random vertical flip
            seq = seq[:, ::-1, :].copy()

        # Normalize to 0-1 range (max dBZ ≈ 75)
        seq = seq / 75.0

        # Split into input and target
        input_seq = seq[:self.input_length]   # [7, H, W]
        target_seq = seq[self.input_length:]  # [6, H, W]

        # Add channel dimension: [T, 1, H, W]
        input_tensor = torch.from_numpy(input_seq).unsqueeze(1)
        target_reflectivity = torch.from_numpy(target_seq).unsqueeze(1)

        # Generate thunderstorm probability targets (>35 dBZ threshold, normalized)
        thunderstorm_target = (target_seq > (35.0 / 75.0)).astype(np.float32)
        thunderstorm_tensor = torch.from_numpy(thunderstorm_target).unsqueeze(1)

        # Generate lightning probability targets (>45 dBZ threshold)
        lightning_target = (target_seq > (45.0 / 75.0)).astype(np.float32)
        lightning_tensor = torch.from_numpy(lightning_target).unsqueeze(1)

        targets = {
            "reflectivity": target_reflectivity,
            "thunderstorm_prob": thunderstorm_tensor,
            "lightning_prob": lightning_tensor,
        }

        return input_tensor, targets


def create_dataloaders(
    num_train: int = 800,
    num_val: int = 200,
    batch_size: int = 8,
    grid_size: int = 64,
    num_workers: int = 0,
):
    """Create train and validation dataloaders."""
    train_dataset = RadarSequenceDataset(
        num_samples=num_train,
        grid_size=grid_size,
        seed=42,
        augment=True,
    )

    val_dataset = RadarSequenceDataset(
        num_samples=num_val,
        grid_size=grid_size,
        seed=123,
        augment=False,
    )

    train_loader = torch.utils.data.DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
    )

    val_loader = torch.utils.data.DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )

    return train_loader, val_loader
