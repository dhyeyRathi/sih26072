"""
ConvLSTM implementation for radar nowcasting.
Based on Shi et al. (2015) "Convolutional LSTM Network: A Machine Learning Approach
for Precipitation Nowcasting"

Architecture (CORE.md Section 9):
  Input: [batch, time, channels, height, width] — sequence of radar frames
  Output: predicted future frames at +10/+20/+30/+40/+50/+60 minutes
"""

import torch
import torch.nn as nn
from typing import Optional


class ConvLSTMCell(nn.Module):
    """
    Single ConvLSTM cell.
    Applies convolution operations within LSTM gates to capture
    spatial correlations in the hidden/cell states.
    """

    def __init__(
        self,
        input_channels: int,
        hidden_channels: int,
        kernel_size: int = 3,
    ):
        super().__init__()
        self.hidden_channels = hidden_channels
        padding = kernel_size // 2

        # Combined gate convolution (input, forget, output, cell)
        self.gates = nn.Conv2d(
            in_channels=input_channels + hidden_channels,
            out_channels=4 * hidden_channels,
            kernel_size=kernel_size,
            padding=padding,
            bias=True,
        )

    def forward(
        self,
        x: torch.Tensor,
        h_prev: Optional[torch.Tensor] = None,
        c_prev: Optional[torch.Tensor] = None,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: input tensor [batch, channels, height, width]
            h_prev: previous hidden state [batch, hidden_channels, height, width]
            c_prev: previous cell state [batch, hidden_channels, height, width]

        Returns:
            h_next, c_next
        """
        batch, _, height, width = x.shape

        if h_prev is None:
            h_prev = torch.zeros(batch, self.hidden_channels, height, width, device=x.device)
        if c_prev is None:
            c_prev = torch.zeros(batch, self.hidden_channels, height, width, device=x.device)

        # Concatenate input and previous hidden state
        combined = torch.cat([x, h_prev], dim=1)
        gates = self.gates(combined)

        # Split into individual gates
        i, f, o, g = gates.chunk(4, dim=1)

        i = torch.sigmoid(i)  # Input gate
        f = torch.sigmoid(f)  # Forget gate
        o = torch.sigmoid(o)  # Output gate
        g = torch.tanh(g)     # Cell candidate

        c_next = f * c_prev + i * g
        h_next = o * torch.tanh(c_next)

        return h_next, c_next


class ConvLSTM(nn.Module):
    """
    Multi-layer ConvLSTM for spatiotemporal sequence prediction.

    Processes a sequence of 2D grids (e.g., radar frames) and produces
    hidden states that encode spatial and temporal patterns.
    """

    def __init__(
        self,
        input_channels: int = 1,
        hidden_channels: list[int] = None,
        kernel_size: int = 3,
        num_layers: int = 3,
    ):
        super().__init__()

        if hidden_channels is None:
            hidden_channels = [64, 64, 64]

        assert len(hidden_channels) == num_layers

        self.num_layers = num_layers
        self.hidden_channels = hidden_channels

        cells = []
        for i in range(num_layers):
            in_ch = input_channels if i == 0 else hidden_channels[i - 1]
            cells.append(ConvLSTMCell(in_ch, hidden_channels[i], kernel_size))

        self.cells = nn.ModuleList(cells)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, list]:
        """
        Args:
            x: input sequence [batch, time, channels, height, width]

        Returns:
            output: last layer hidden states for all timesteps [batch, time, hidden, H, W]
            last_states: list of (h, c) for each layer at the last timestep
        """
        batch, seq_len, _, height, width = x.shape

        # Initialize hidden states
        h_states = [None] * self.num_layers
        c_states = [None] * self.num_layers

        outputs = []

        for t in range(seq_len):
            input_t = x[:, t]  # [batch, channels, H, W]

            for layer_idx, cell in enumerate(self.cells):
                h, c = cell(input_t, h_states[layer_idx], c_states[layer_idx])
                h_states[layer_idx] = h
                c_states[layer_idx] = c
                input_t = h  # Output of this layer is input to next

            outputs.append(h_states[-1])

        # Stack outputs: [batch, time, hidden, H, W]
        output = torch.stack(outputs, dim=1)
        last_states = list(zip(h_states, c_states))

        return output, last_states


class NowcastingModel(nn.Module):
    """
    Complete nowcasting model with encoder-decoder structure.

    Encoder: ConvLSTM processes input sequence (T-60 to T)
    Decoder: ConvLSTM generates future predictions (T+10 to T+60)

    Output heads (CORE.md Section 10):
    - Reflectivity: future radar fields (regression)
    - Thunderstorm probability: per-pixel probability (classification)
    - Lightning probability: per-pixel probability (classification)
    """

    def __init__(
        self,
        input_channels: int = 1,
        hidden_channels: int = 64,
        num_layers: int = 3,
        output_horizons: int = 6,  # +10, +20, +30, +40, +50, +60
        kernel_size: int = 3,
    ):
        super().__init__()
        self.output_horizons = output_horizons

        # Encoder
        self.encoder = ConvLSTM(
            input_channels=input_channels,
            hidden_channels=[hidden_channels] * num_layers,
            kernel_size=kernel_size,
            num_layers=num_layers,
        )

        # Decoder cells (auto-regressive)
        self.decoder_cell = ConvLSTMCell(
            input_channels=hidden_channels,
            hidden_channels=hidden_channels,
            kernel_size=kernel_size,
        )

        # Output heads
        self.reflectivity_head = nn.Sequential(
            nn.Conv2d(hidden_channels, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 1, 1),
            nn.ReLU(inplace=True),  # Reflectivity is non-negative
        )

        self.thunderstorm_head = nn.Sequential(
            nn.Conv2d(hidden_channels, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 1, 1),
            nn.Sigmoid(),  # Probability 0-1
        )

        self.lightning_head = nn.Sequential(
            nn.Conv2d(hidden_channels, 32, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(32, 1, 1),
            nn.Sigmoid(),  # Probability 0-1
        )

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """
        Args:
            x: input sequence [batch, time, 1, H, W]

        Returns:
            dict with keys:
            - reflectivity: [batch, horizons, 1, H, W]
            - thunderstorm_prob: [batch, horizons, 1, H, W]
            - lightning_prob: [batch, horizons, 1, H, W]
        """
        # Encode input sequence
        _, last_states = self.encoder(x)
        h, c = last_states[-1]  # Take the last layer's state

        # Decode future timesteps auto-regressively
        reflectivity_preds = []
        thunderstorm_preds = []
        lightning_preds = []

        decoder_input = h  # Start with encoder's last hidden state

        for t in range(self.output_horizons):
            h, c = self.decoder_cell(decoder_input, h, c)
            decoder_input = h

            reflectivity_preds.append(self.reflectivity_head(h))
            thunderstorm_preds.append(self.thunderstorm_head(h))
            lightning_preds.append(self.lightning_head(h))

        return {
            "reflectivity": torch.stack(reflectivity_preds, dim=1),
            "thunderstorm_prob": torch.stack(thunderstorm_preds, dim=1),
            "lightning_prob": torch.stack(lightning_preds, dim=1),
        }


def create_model(
    input_channels: int = 1,
    hidden_channels: int = 64,
    num_layers: int = 3,
    output_horizons: int = 6,
) -> NowcastingModel:
    """Factory function to create the nowcasting model."""
    return NowcastingModel(
        input_channels=input_channels,
        hidden_channels=hidden_channels,
        num_layers=num_layers,
        output_horizons=output_horizons,
    )
