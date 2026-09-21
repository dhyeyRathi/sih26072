"""
SIH26072 — Deep Neural Nowcaster ML Model Architecture v3
PyTorch multi-task neural network with residual connections, deeper layers,
expanded 18-feature input (including optical flow), and MC Dropout support
for storm cell trajectory and intensity nowcasting.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict


class ResidualBlock(nn.Module):
    """Pre-activation residual block with dropout for MC Dropout inference."""

    def __init__(self, dim: int, dropout: float = 0.1):
        super().__init__()
        self.norm1 = nn.BatchNorm1d(dim)
        self.linear1 = nn.Linear(dim, dim)
        self.norm2 = nn.BatchNorm1d(dim)
        self.linear2 = nn.Linear(dim, dim)
        self.dropout = nn.Dropout(p=dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.norm1(x)
        out = F.silu(out)
        out = self.linear1(out)
        out = self.norm2(out)
        out = F.silu(out)
        out = self.dropout(out)
        out = self.linear2(out)
        return out + residual


class StormNowcasterMLP(nn.Module):
    """
    Multi-Task PyTorch Neural Network for Storm Cell Nowcasting v3.
    
    Architecture improvements over v2:
    - Expanded input: 18 features (vs 14) including optical flow velocity,
      divergence, and curl for real-time storm dynamics
    - Wider hidden dimension (320 vs 256) for more capacity
    - 4 residual blocks (vs 3) for deeper feature extraction
    - MC Dropout (kept enabled during inference for ensemble averaging)
    
    Inputs (Feature vector of length 18):
    - [0-1]: Current velocity (vx, vy) from wind observations
    - [2-3]: Current acceleration (ax, ay)
    - [4]: Max reflectivity (dBZ)
    - [5]: Mean reflectivity (dBZ)
    - [6]: Reflectivity trend (dBZ/dt)
    - [7]: Cell Area (sq km)
    - [8]: Area growth rate (dArea/dt)
    - [9]: Lightning rate (flashes/min)
    - [10]: Lightning trend (dLightning/dt)
    - [11]: Normalized Latitude offset from region center
    - [12]: Normalized Longitude offset from region center
    - [13]: Historical trajectory curvature (radians)
    - [14-15]: Optical flow velocity at centroid (of_vx, of_vy)
    - [16]: Optical flow divergence (convergence = intensification)
    - [17]: Optical flow curl (rotation = mesocyclone)
    
    Outputs:
    - trajectory_offsets: (batch_size, 4, 2) -> (dx, dy) in grid units for 15, 30, 45, 60 min horizons
    - dbz_forecasts: (batch_size, 4) -> predicted max dBZ at 15, 30, 45, 60 min
    - thunderstorm_probs: (batch_size, 4) -> calibrated thunderstorm probability [0, 1]
    - lightning_probs: (batch_size, 4) -> calibrated lightning probability [0, 1]
    """

    def __init__(self, input_dim: int = 18, hidden_dim: int = 320, mc_dropout: float = 0.1):
        super().__init__()
        self.mc_dropout_rate = mc_dropout

        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.SiLU(),
        )

        # Deep feature extractor with 4 residual blocks
        self.res_block1 = ResidualBlock(hidden_dim, dropout=mc_dropout)
        self.res_block2 = ResidualBlock(hidden_dim, dropout=mc_dropout)
        self.res_block3 = ResidualBlock(hidden_dim, dropout=mc_dropout)
        self.res_block4 = ResidualBlock(hidden_dim, dropout=mc_dropout)

        # Bottleneck
        self.bottleneck = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.BatchNorm1d(hidden_dim // 2),
            nn.SiLU(),
            nn.Dropout(p=mc_dropout),
        )

        half_dim = hidden_dim // 2

        # 1. Non-linear Trajectory Prediction Head -> 4 horizons x 2 coords (dx, dy)
        self.trajectory_head = nn.Sequential(
            nn.Linear(half_dim, 128),
            nn.SiLU(),
            nn.Dropout(p=mc_dropout),
            nn.Linear(128, 64),
            nn.SiLU(),
            nn.Linear(64, 4 * 2)
        )

        # 2. Reflectivity Intensity Forecasting Head -> 4 horizons
        self.intensity_head = nn.Sequential(
            nn.Linear(half_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 4)
        )

        # 3. Thunderstorm Probability Classifier Head -> 4 horizons
        self.ts_prob_head = nn.Sequential(
            nn.Linear(half_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 4),
            nn.Sigmoid()
        )

        # 4. Lightning Probability Classifier Head -> 4 horizons
        self.lt_prob_head = nn.Sequential(
            nn.Linear(half_dim, 64),
            nn.SiLU(),
            nn.Linear(64, 4),
            nn.Sigmoid()
        )

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        if x.dim() == 1:
            x = x.unsqueeze(0)

        h = self.input_proj(x)
        h = self.res_block1(h)
        h = self.res_block2(h)
        h = self.res_block3(h)
        h = self.res_block4(h)
        features = self.bottleneck(h)

        traj_out = self.trajectory_head(features).reshape(-1, 4, 2)
        dbz_out = self.intensity_head(features)
        ts_prob_out = self.ts_prob_head(features)
        lt_prob_out = self.lt_prob_head(features)

        return {
            "trajectory_offsets": traj_out,
            "dbz_forecasts": dbz_out,
            "thunderstorm_probs": ts_prob_out,
            "lightning_probs": lt_prob_out,
        }
