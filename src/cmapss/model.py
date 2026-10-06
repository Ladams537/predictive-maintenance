"""Small Transformer encoder for RUL regression over per-cycle windows.

Deliberately small (~50k parameters): C-MAPSS has 100-260 training engines, N-CMAPSS 60.
Input (B, L, F) + padding mask; output RUL in cycles. Differentiable end to end in its
inputs, so gradient attributions over (cycle, feature) are available for explanations.
"""

import torch
from torch import nn


class RULTransformer(nn.Module):
    def __init__(
        self,
        n_features: int,
        length: int,
        d_model: int = 64,
        n_heads: int = 4,
        n_layers: int = 2,
        d_ff: int = 128,
        dropout: float = 0.1,
        target_scale: float = 100.0,
    ):
        super().__init__()
        self.inp = nn.Linear(n_features, d_model)
        self.pos = nn.Parameter(torch.zeros(1, length, d_model))
        nn.init.normal_(self.pos, std=0.02)
        layer = nn.TransformerEncoderLayer(
            d_model, n_heads, d_ff, dropout, batch_first=True, norm_first=True
        )
        self.encoder = nn.TransformerEncoder(layer, n_layers, enable_nested_tensor=False)
        self.head = nn.Sequential(
            nn.LayerNorm(2 * d_model),
            nn.Linear(2 * d_model, d_model),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, 1),
        )
        # Targets are O(100) cycles; regress target/scale so the output layer starts near range.
        self.target_scale = target_scale

    def forward(self, x: torch.Tensor, pad: torch.Tensor) -> torch.Tensor:
        h = self.encoder(self.inp(x) + self.pos, src_key_padding_mask=pad)
        valid = (~pad).unsqueeze(-1).float()
        mean = (h * valid).sum(1) / valid.sum(1).clamp(min=1)
        last = h[:, -1]  # right-aligned: the last position is always the current cycle
        return self.head(torch.cat([last, mean], dim=-1)).squeeze(-1) * self.target_scale


class RULGRU(nn.Module):
    """Recurrent comparison model with the same interface. Padding is at the front and
    zero-valued; the GRU reads left to right, so the final state is at the current cycle."""

    def __init__(
        self,
        n_features: int,
        length: int,
        d_model: int = 64,
        n_layers: int = 2,
        dropout: float = 0.1,
        target_scale: float = 100.0,
        **_,
    ):
        super().__init__()
        self.gru = nn.GRU(
            n_features,
            d_model,
            n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.head = nn.Sequential(
            nn.Linear(d_model, d_model), nn.GELU(), nn.Dropout(dropout), nn.Linear(d_model, 1)
        )
        self.target_scale = target_scale

    def forward(self, x: torch.Tensor, pad: torch.Tensor) -> torch.Tensor:
        h, _ = self.gru(x * (~pad).unsqueeze(-1))
        return self.head(h[:, -1]).squeeze(-1) * self.target_scale


ARCHS = {"transformer": RULTransformer, "gru": RULGRU}
