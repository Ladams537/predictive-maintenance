"""Compare training configs by nested engine-level CV on the TRAINING set only.

Outer K folds by engine score each config; inside each outer-train set, held-out engines
drive early stopping. Test data is never loaded. Folds x configs run in parallel processes,
one torch thread each.

Usage:
  uv run python -m cmapss.tune cmapss FD001 --configs '{"a": {}, "b": {"lr": 5e-4}}'
"""

import argparse
import json
import multiprocessing as mp
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from cmapss.data import REPO_ROOT
from cmapss.metrics import rmse
from cmapss.train import Config, cmapss_data, fit, ncmapss_data, predict, split_engines

OUT = REPO_ROOT / "reports" / "tuning"


def trunc_points(engines: np.ndarray, seed: int) -> np.ndarray:
    """One random row per engine: the held-out analogue of C-MAPSS's truncated test engines.
    Deterministic in (engines, seed), so every model is scored on the same points."""
    rng = np.random.default_rng(seed)
    return np.array([rng.choice(np.flatnonzero(engines == e)) for e in np.unique(engines)])


def _job(args):
    import torch

    torch.set_num_threads(1)
    name, cfg, fold, tr_w, va_w, length, seed = args
    inner_val = split_engines(tr_w.engine, seed)
    model, info = fit(
        tr_w.subset(~inner_val), tr_w.subset(inner_val), length, seed, cfg, log=lambda *_: None
    )
    pred = predict(model, va_w)
    # Two views of the held-out fold: every cycle, and the test-like "one random truncation
    # point per engine" (C-MAPSS scores last observed cycles of truncated engines).
    trunc = trunc_points(va_w.engine, fold)
    return {
        "config": name,
        "fold": fold,
        "rmse_all": rmse(va_w.y, pred),
        "rmse_trunc": rmse(va_w.y[trunc], pred[trunc]),
        "best_epoch": info["best_epoch"],
        "train_rmse_final": info["train_rmse"][-1],
    }


def _xgb_reference(d: dict, folds) -> list[dict]:
    """XGBoost on the engineered window features, scored on exactly the same folds and the
    same two views as the sequence models, so the comparison is like for like."""
    from cmapss.baselines import MODELS

    p, w = d["prepared"], d["train"]
    X, y = p.X_train.loc[w.index], w.y
    out = []
    for fold, (tr, va) in enumerate(folds):
        m = MODELS["xgboost"]().fit(X.iloc[tr], y[tr])
        pred = np.clip(m.predict(X.iloc[va]), 0, None)
        t = trunc_points(w.engine[va], fold)
        out.append(
            {
                "config": "REF_xgboost",
                "fold": fold,
                "rmse_all": rmse(y[va], pred),
                "rmse_trunc": rmse(y[va][t], pred[t]),
                "best_epoch": np.nan,
                "train_rmse_final": np.nan,
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=["cmapss", "ncmapss"])
    ap.add_argument("setting")
    ap.add_argument("--configs", required=True, help="JSON {name: Config overrides}")
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    configs = {k: Config(**v) for k, v in json.loads(a.configs).items()}
    d = cmapss_data(a.setting) if a.dataset == "cmapss" else ncmapss_data(a.setting)
    w, length = d["train"], d["length"]  # training windows only
    folds = list(GroupKFold(a.folds).split(w.X, groups=w.engine))
    jobs = []
    for fold, (tr, va) in enumerate(folds):
        tr_m, va_m = np.zeros(len(w), bool), np.zeros(len(w), bool)
        tr_m[tr], va_m[va] = True, True
        for name, cfg in configs.items():
            jobs.append((name, cfg, fold, w.subset(tr_m), w.subset(va_m), length, fold))
    with mp.get_context("spawn").Pool(a.procs) as pool:
        res = pd.DataFrame(pool.map(_job, jobs))
    if a.dataset == "cmapss":
        res = pd.concat([res, pd.DataFrame(_xgb_reference(d, folds))], ignore_index=True)
    summary = (
        res.groupby("config")
        .agg(
            rmse_all=("rmse_all", "mean"),
            rmse_all_sd=("rmse_all", "std"),
            rmse_trunc=("rmse_trunc", "mean"),
            best_epoch=("best_epoch", "mean"),
            train_rmse=("train_rmse_final", "mean"),
        )
        .round(2)
        .sort_values("rmse_all")
    )
    print(summary.to_string())
    OUT.mkdir(parents=True, exist_ok=True)
    stem = f"{a.dataset}_{a.setting}{'_' + a.tag if a.tag else ''}"
    Path(OUT / f"{stem}.md").write_text(
        f"# Tuning {a.dataset} {a.setting} ({a.folds}-fold engine CV, train set only)\n\n"
        + summary.to_markdown()
        + "\n\nConfigs:\n\n```json\n"
        + json.dumps({k: v for k, v in json.loads(a.configs).items()}, indent=2)
        + "\n```\n"
    )


if __name__ == "__main__":
    main()
