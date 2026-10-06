"""Tabular features for the week-1 baselines (linear / XGBoost).

Each row's features use only that row and earlier rows of the same unit -- no lookahead.
`test_no_lookahead` in tests/ enforces this.
"""

import pandas as pd

from cmapss.data import SENSOR_COLS


def informative_sensors(train: pd.DataFrame, min_unique: int = 3) -> list[str]:
    """Sensors that actually vary in the *training* data.

    Decided from train only. A relative-std threshold is the wrong tool here: s8/s13 (fan
    speeds ~2388 rpm) move by ~0.1 rpm, tiny relative to their level but strongly trending.
    Counting distinct values drops only the genuinely flat channels -- on FD001 that is
    s1, s5, s6, s10, s16, s18, s19 (s6 toggles between two values). On FD002/FD004 every
    sensor varies with operating condition, so those need per-condition normalisation first.
    """
    return [c for c in SENSOR_COLS if train[c].nunique() >= min_unique]


def window_features(df: pd.DataFrame, sensors: list[str], window: int = 30) -> pd.DataFrame:
    """Per-row features over a trailing window: last value, mean, std, and linear slope.

    The slope is the degradation-rate signal; the level alone is confounded by each engine's
    unknown initial wear.
    """
    g = df.groupby("unit", sort=False)
    t = df["cycle"].astype(float)
    out = {"cycle": df["cycle"].astype(float)}
    roll = lambda s: s.groupby(df["unit"], sort=False).rolling(window, min_periods=1)  # noqa: E731
    t_mean = roll(t).mean().reset_index(level=0, drop=True)
    t_var = roll(t * t).mean().reset_index(level=0, drop=True) - t_mean**2
    for s in sensors:
        x = df[s]
        x_mean = roll(x).mean().reset_index(level=0, drop=True)
        xt_mean = roll(x * t).mean().reset_index(level=0, drop=True)
        out[f"{s}_last"] = x
        out[f"{s}_mean"] = x_mean
        out[f"{s}_std"] = g[s].transform(lambda v: v.rolling(window, min_periods=2).std()).fillna(0)
        # Slope of least-squares fit of x on t within the window; 0 when only one point.
        out[f"{s}_slope"] = ((xt_mean - x_mean * t_mean) / t_var.where(t_var > 0)).fillna(0)
    return pd.DataFrame(out, index=df.index)


def feature_columns(sensors: list[str]) -> list[str]:
    return ["cycle"] + [f"{s}_{k}" for s in sensors for k in ("last", "mean", "std", "slope")]
