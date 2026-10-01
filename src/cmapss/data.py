"""Loading C-MAPSS and attaching RUL labels.

Conventions used everywhere in this repo:
- `unit` / `cycle` identify a row. Unit IDs restart at 1 in every file, so train unit 1 and
  test unit 1 are *different engines*. Never join train and test on `unit`.
- `rul` is the uncapped ground truth. Capping (the piecewise-linear target the literature
  uses) is applied explicitly via `cap_rul`, never silently at load time.
"""

import os
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("CMAPSS_DATA_DIR", REPO_ROOT / "data" / "raw" / "CMAPSSData"))

SUBSETS = ("FD001", "FD002", "FD003", "FD004")
SETTING_COLS = ["op1", "op2", "op3"]
# The dataset readme says "26 sensor measurements" -- it is 26 columns in total,
# of which 21 are sensors.
SENSOR_COLS = [f"s{i}" for i in range(1, 22)]
COLUMNS = ["unit", "cycle", *SETTING_COLS, *SENSOR_COLS]

# Physical meaning from Saxena et al. (2008), Table 2. Used later to ground explanations,
# so keep it accurate rather than "nice-sounding".
SENSOR_DESCRIPTIONS = {
    "s1": "Total temperature at fan inlet (T2, °R)",
    "s2": "Total temperature at LPC outlet (T24, °R)",
    "s3": "Total temperature at HPC outlet (T30, °R)",
    "s4": "Total temperature at LPT outlet (T50, °R)",
    "s5": "Pressure at fan inlet (P2, psia)",
    "s6": "Total pressure in bypass-duct (P15, psia)",
    "s7": "Total pressure at HPC outlet (P30, psia)",
    "s8": "Physical fan speed (Nf, rpm)",
    "s9": "Physical core speed (Nc, rpm)",
    "s10": "Engine pressure ratio P50/P2 (epr)",
    "s11": "Static pressure at HPC outlet (Ps30, psia)",
    "s12": "Ratio of fuel flow to Ps30 (phi, pps/psi)",
    "s13": "Corrected fan speed (NRf, rpm)",
    "s14": "Corrected core speed (NRc, rpm)",
    "s15": "Bypass ratio (BPR)",
    "s16": "Burner fuel-air ratio (farB)",
    "s17": "Bleed enthalpy (htBleed)",
    "s18": "Demanded fan speed (Nf_dmd, rpm)",
    "s19": "Demanded corrected fan speed (PCNfR_dmd, rpm)",
    "s20": "HPT coolant bleed (W31, lbm/s)",
    "s21": "LPT coolant bleed (W32, lbm/s)",
}


def _read(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found. Run `uv run python -m cmapss.download`.")
    # Rows have trailing whitespace; sep=r"\s+" handles it without phantom columns.
    df = pd.read_csv(path, sep=r"\s+", header=None, names=COLUMNS)
    df[["unit", "cycle"]] = df[["unit", "cycle"]].astype(int)
    return df


def load_train(subset: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Run-to-failure trajectories. The last cycle of each unit is the failure cycle (RUL=0)."""
    df = _read(data_dir / f"train_{subset}.txt")
    last = df.groupby("unit")["cycle"].transform("max")
    df["rul"] = last - df["cycle"]
    return df


def load_test(subset: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Truncated trajectories with per-row RUL derived from RUL_FDxxx.txt.

    The official metric uses only the last row of each unit (see `last_cycles`).
    Labels on earlier rows are correct but are not part of the benchmark.
    """
    df = _read(data_dir / f"test_{subset}.txt")
    rul_end = np.loadtxt(data_dir / f"RUL_{subset}.txt", dtype=int)
    n_units = df["unit"].nunique()
    if len(rul_end) != n_units:
        raise ValueError(f"{subset}: {len(rul_end)} RUL labels for {n_units} test units")
    last = df.groupby("unit")["cycle"].transform("max")
    df["rul"] = df["unit"].map(dict(enumerate(rul_end, start=1))) + (last - df["cycle"])
    return df


def last_cycles(df: pd.DataFrame) -> pd.DataFrame:
    """One row per unit: its final observed cycle. This is the benchmark evaluation point."""
    return df.loc[df.groupby("unit")["cycle"].idxmax()].reset_index(drop=True)


def cap_rul(rul: np.ndarray | pd.Series, cap: float | None) -> np.ndarray:
    """Piecewise-linear RUL target: early in life the engine is 'healthy' and RUL is flat at cap.

    Published FD001 numbers (RMSE ~11-13) almost all use cap=125 or 130. This changes the
    problem materially, so every report states the cap it used.
    """
    rul = np.asarray(rul, dtype=float)
    return rul if cap is None else np.minimum(rul, cap)
