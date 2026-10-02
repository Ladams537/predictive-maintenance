"""N-CMAPSS -> one row per (engine, flight cycle) of healthy-baseline residuals.

N-CMAPSS operating conditions are continuous (altitude, Mach, throttle, inlet temperature
change every second), so C-MAPSS-style condition clustering doesn't apply. Instead:

1. A *healthy-engine model* f(W) -> X_s predicts what each sensor would read at these
   operating conditions on an undegraded engine. It's fit on the first HEALTHY_CYCLES cycles of
   dev engines. Cycle number is observable; the simulator's `hs` flag is ground truth and isn't
   used.
2. residual = X_s - f(W) is the degradation signal, averaged per flight cycle.

Dev engines' residuals are *cross-fitted*: each comes from an f trained on other engines, so
dev and test residuals are both out-of-sample. Test engines use f fit on all dev engines.

Usage: uv run python -m cmapss.ncmapss_features   # -> data/interim/ncmapss_cycles.parquet
"""

import json
import sys
import time

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from xgboost import XGBRegressor

from cmapss import ncmapss
from cmapss.data import REPO_ROOT

OPS = ["alt", "Mach", "TRA", "T2"]
SENSORS = [
    "T24",
    "T30",
    "T48",
    "T50",
    "P15",
    "P2",
    "P21",
    "P24",
    "Ps30",
    "P40",
    "P50",
    "Nf",
    "Nc",
    "Wf",
]
RESID = [f"r_{s}" for s in SENSORS]
HEALTHY_CYCLES = 10
EVERY = 5  # 1 Hz -> 0.2 Hz. A flight cycle still has ~2,400 samples to average over.
FIT_EVERY = 4  # further thinning of healthy rows for fitting f
N_FOLDS = 5
OUT = REPO_ROOT / "data" / "interim" / "ncmapss_cycles.parquet"
META = REPO_ROOT / "reports" / "ncmapss" / "healthy_model.json"


def _healthy_model() -> XGBRegressor:
    return XGBRegressor(
        n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8, n_jobs=-1, random_state=0
    )


def load_all() -> pd.DataFrame:
    frames = []
    for subset in ncmapss.SUBSETS:
        for split in ("dev", "test"):
            t = time.time()
            df = ncmapss.load(subset, split, groups=("A", "W", "X_s", "Y"), every=EVERY)
            df.insert(0, "subset", subset)
            df.insert(1, "split", split)
            frames.append(df)
            print(f"loaded {subset} {split}: {len(df):,} rows ({time.time() - t:.0f}s)", flush=True)
    df = pd.concat(frames, ignore_index=True)
    df["subset"] = df["subset"].astype("category")
    df["split"] = df["split"].astype("category")
    # Unit numbers repeat across subsets; `engine` is the global key.
    df["engine"] = df.groupby(["subset", "unit"], observed=True).ngroup().astype(np.int32)
    return df


def fit_predict(train: pd.DataFrame, apply: pd.DataFrame) -> np.ndarray:
    out = np.empty((len(apply), len(SENSORS)), dtype=np.float32)
    for j, s in enumerate(SENSORS):
        m = _healthy_model().fit(train[OPS], train[s])
        out[:, j] = m.predict(apply[OPS])
    return out


def residuals(df: pd.DataFrame) -> tuple[np.ndarray, dict]:
    dev = df["split"].eq("dev").to_numpy()
    healthy = dev & (df["cycle"] <= HEALTHY_CYCLES).to_numpy()
    fit_rows = df[healthy].iloc[::FIT_EVERY]
    pred = np.empty((len(df), len(SENSORS)), dtype=np.float32)
    dev_engines = df.loc[dev, "engine"].unique()

    folds = GroupKFold(N_FOLDS).split(dev_engines, groups=dev_engines)
    heldout_r2 = []
    for k, (_, va) in enumerate(folds):
        va_eng = dev_engines[va]
        in_va = df["engine"].isin(va_eng).to_numpy()
        tr = fit_rows[~fit_rows["engine"].isin(va_eng)]
        pred[in_va] = fit_predict(tr, df[in_va])
        # How well does f explain *healthy* sensors on engines it never saw?
        hv = in_va & healthy
        y, p = df.loc[hv, SENSORS].to_numpy(), pred[hv]
        heldout_r2.append(1 - ((y - p) ** 2).sum(0) / ((y - y.mean(0)) ** 2).sum(0))
        print(
            f"  fold {k}: healthy-model R² on held-out engines, min over sensors "
            f"{heldout_r2[-1].min():.4f}",
            flush=True,
        )
    test = ~dev
    pred[test] = fit_predict(fit_rows, df[test])
    r2 = np.mean(heldout_r2, axis=0)
    meta = {
        "healthy_cycles": HEALTHY_CYCLES,
        "every": EVERY,
        "fit_rows": len(fit_rows),
        "heldout_healthy_r2": dict(zip(SENSORS, np.round(r2, 5).tolist(), strict=True)),
    }
    return df[SENSORS].to_numpy(np.float32) - pred, meta


def build() -> pd.DataFrame:
    df = load_all()
    resid, meta = residuals(df)
    df[RESID] = resid
    # Scale each residual by its healthy-period spread on dev, so sensors are comparable.
    healthy = df["split"].eq("dev") & (df["cycle"] <= HEALTHY_CYCLES)
    scale = df.loc[healthy, RESID].std()
    df[RESID] = df[RESID] / scale
    meta["residual_scale"] = scale.round(6).to_dict()

    keys = ["subset", "split", "engine", "unit", "cycle"]
    agg = (
        df.groupby(keys, sort=True, observed=True)
        .agg(
            **{c: (c, "mean") for c in RESID + OPS},
            Fc=("Fc", "first"),
            rul=("rul", "first"),
            hs=("hs", "min"),
            n_samples=("cycle", "size"),
        )
        .reset_index()
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    agg.to_parquet(OUT, index=False)
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2))
    print(f"wrote {OUT}: {len(agg):,} engine-cycles, {agg.engine.nunique()} engines")
    return agg


def load_cycles() -> pd.DataFrame:
    if not OUT.exists():
        raise FileNotFoundError(f"{OUT} missing; run `uv run python -m cmapss.ncmapss_features`")
    return pd.read_parquet(OUT)


if __name__ == "__main__":
    build()
    sys.exit(0)
