"""Per-cycle tables -> fixed-length windows for sequence models.

One sample per (engine, cycle t): the feature vectors of cycles t-L+1..t, right-aligned so the
last position is always the cycle being predicted. Engines with fewer than L cycles so far are
left-padded with zeros and a mask marks the padding. Windows never cross engines and never
include cycles after t (tested).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Windows:
    X: np.ndarray  # (N, L, F) float32
    pad: np.ndarray  # (N, L) bool, True = padding
    y: np.ndarray  # (N,) float32 target
    engine: np.ndarray  # (N,) engine key
    cycle: np.ndarray  # (N,) cycle number of the predicted cycle
    index: np.ndarray  # (N,) row index into the source frame

    def __len__(self) -> int:
        return len(self.y)

    def subset(self, mask: np.ndarray) -> "Windows":
        return Windows(
            self.X[mask],
            self.pad[mask],
            self.y[mask],
            self.engine[mask],
            self.cycle[mask],
            self.index[mask],
        )


def make_windows(
    df: pd.DataFrame, features: list[str], target: str, length: int, engine_col: str = "unit"
) -> Windows:
    df = df.sort_values([engine_col, "cycle"])
    F = len(features)
    n = len(df)
    X = np.zeros((n, length, F), dtype=np.float32)
    pad = np.ones((n, length), dtype=bool)
    i = 0
    for _, g in df.groupby(engine_col, sort=False):
        a = g[features].to_numpy(np.float32)
        T = len(a)
        for t in range(T):
            lo = max(0, t - length + 1)
            k = t - lo + 1
            X[i + t, length - k :] = a[lo : t + 1]
            pad[i + t, length - k :] = False
        i += T
    return Windows(
        X=X,
        pad=pad,
        y=df[target].to_numpy(np.float32),
        engine=df[engine_col].to_numpy(),
        cycle=df["cycle"].to_numpy(),
        index=df.index.to_numpy(),
    )
