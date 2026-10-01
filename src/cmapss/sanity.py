"""Sanity checks and trivial floors. A model that can't beat these is broken, not 'tuned badly'.

Floors (all trained on train only, evaluated on the test last-cycles):
- mean:      predict the mean (capped) training RUL for every engine.
- lifetime:  predict (mean training lifetime - current cycle), capped. Uses no sensors at all,
             only "how old is this engine" -- the strongest sensor-free baseline.
- noise:     the real model class trained on Gaussian noise of the same shape as the features.
             Measures what the model gets from the label/cycle structure alone.
"""

import hashlib

import numpy as np
import pandas as pd

from cmapss.data import SENSOR_COLS, SETTING_COLS, cap_rul


def assert_units_disjoint(train_units, val_units) -> None:
    """Validation must split by engine, never by row. Row-level splits put neighbouring cycles
    of the same engine on both sides and make RMSE a lie."""
    overlap = set(train_units) & set(val_units)
    if overlap:
        raise AssertionError(f"Leakage: {len(overlap)} units in both train and val: {overlap}")


def _row_hashes(df: pd.DataFrame) -> set[str]:
    vals = df[SETTING_COLS + SENSOR_COLS].round(6).to_numpy()
    return {hashlib.blake2b(r.tobytes(), digest_size=12).hexdigest() for r in vals}


def trajectory_overlap(train: pd.DataFrame, test: pd.DataFrame) -> dict:
    """Do any test rows appear verbatim in train? Unit IDs overlap by construction (both start
    at 1) but are different engines; this checks the *data* instead of the IDs."""
    tr, te = _row_hashes(train), _row_hashes(test)
    shared = tr & te
    return {
        "shared_unit_ids": int(len(set(train.unit) & set(test.unit))),
        "identical_sensor_rows": len(shared),
        "test_rows": len(te),
        "verdict": "OK" if not shared else "INVESTIGATE: identical rows across train/test",
    }


def mean_floor(train: pd.DataFrame, test_last: pd.DataFrame, cap: float | None) -> np.ndarray:
    return np.full(len(test_last), cap_rul(train["rul"], cap).mean())


def lifetime_floor(train: pd.DataFrame, test_last: pd.DataFrame, cap: float | None) -> np.ndarray:
    mean_life = train.groupby("unit")["cycle"].max().mean()
    return cap_rul(np.clip(mean_life - test_last["cycle"].to_numpy(), 0, None), cap)


def noise_features(n_rows: int, n_cols: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((n_rows, n_cols))
