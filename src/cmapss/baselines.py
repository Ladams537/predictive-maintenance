"""Week-1 baselines: sanity floors + linear regression + XGBoost, each with a full report.

Usage: uv run python -m cmapss.baselines --subset FD001 --cap 125
"""

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor

from cmapss import sanity
from cmapss.data import REPO_ROOT, cap_rul, last_cycles, load_test, load_train
from cmapss.features import feature_columns, informative_sensors, window_features
from cmapss.metrics import rmse
from cmapss.report import sensor_reference, write_report

SEED = 0

# Published FD001 RMSE (cap 125/130, last-cycle evaluation) -- for "is my number plausible?".
# Verify against the papers before quoting; these are the commonly cited figures.
PUBLISHED_FD001 = {
    "CNN (Babu et al. 2016)": 18.45,
    "LSTM (Zheng et al. 2017)": 16.14,
    "DCNN (Li et al. 2018)": 12.61,
    "SOTA band (Transformer/attention, 2021+)": "~11-12",
}

ModelFactory = Callable[[], object]

MODELS: dict[str, ModelFactory] = {
    "linear": lambda: make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
    "xgboost": lambda: XGBRegressor(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=SEED,
        n_jobs=-1,
    ),
}


def sample_eval_rows(df: pd.DataFrame, per_unit: int, seed: int) -> pd.Index:
    """Emulate the test protocol inside validation: a few random truncation points per engine,
    rather than scoring every cycle (which over-weights long-lived engines and the flat
    capped region)."""
    rng = np.random.default_rng(seed)
    idx = [
        rng.choice(g.index, size=min(per_unit, len(g)), replace=False)
        for _, g in df.groupby("unit")
    ]
    return pd.Index(np.concatenate(idx))


def cross_validate(
    factory: ModelFactory, X: pd.DataFrame, y: np.ndarray, train: pd.DataFrame, n_splits: int = 5
) -> dict:
    eval_rows = sample_eval_rows(train, per_unit=5, seed=SEED)
    scores = []
    for tr_idx, va_idx in GroupKFold(n_splits=n_splits).split(X, y, groups=train["unit"]):
        sanity.assert_units_disjoint(train.unit.iloc[tr_idx], train.unit.iloc[va_idx])
        model = factory()
        model.fit(X.iloc[tr_idx], y[tr_idx])
        va = X.index[va_idx].intersection(eval_rows)
        scores.append(rmse(y[X.index.get_indexer(va)], model.predict(X.loc[va])))
    return {
        "cv_rmse_mean": round(float(np.mean(scores)), 3),
        "cv_rmse_std": round(float(np.std(scores)), 3),
        "cv_rmse_folds": [round(s, 2) for s in scores],
    }


def run(subset: str, cap: float | None, window: int, out_root: Path) -> pd.DataFrame:
    train, test = load_train(subset), load_test(subset)
    test_last = last_cycles(test)
    sensors = informative_sensors(train)
    cols = feature_columns(sensors)
    X_train = window_features(train, sensors, window)[cols]
    X_test_last = window_features(test, sensors, window)[cols].loc[
        test.groupby("unit")["cycle"].idxmax().to_numpy()
    ]
    y_train = cap_rul(train["rul"], cap)
    ref = sensor_reference(train, sensors)
    out = out_root / subset

    checks = {
        "trajectory_overlap": sanity.trajectory_overlap(train, test),
        "informative_sensors": sensors,
        "n_train_units": int(train.unit.nunique()),
        "n_test_units": int(test.unit.nunique()),
        "window": window,
    }
    print(json.dumps(checks, indent=2))

    rows = []
    preds = {
        "floor_mean": sanity.mean_floor(train, test_last, cap),
        "floor_lifetime": sanity.lifetime_floor(train, test_last, cap),
    }
    for name, pred in preds.items():
        res = write_report(out / name, name, test, test_last, pred, cap, ref)
        rows.append(
            {
                "model": name,
                **res["vs_capped_truth"],
                "rmse_raw_truth": res["vs_raw_truth"]["rmse"],
                "std_ratio": res["distribution_vs_capped_truth"]["std_ratio"],
            }
        )

    # Noise floor: same model class, features replaced by noise. Keep `cycle` out of it --
    # the point is "what does the model learn with zero signal".
    noise_train = sanity.noise_features(*X_train.shape, seed=SEED)
    noise_test = sanity.noise_features(*X_test_last.shape, seed=SEED + 1)
    m = MODELS["xgboost"]()
    m.fit(noise_train, y_train)
    res = write_report(
        out / "floor_noise_xgboost",
        "floor_noise_xgboost",
        test,
        test_last,
        m.predict(noise_test),
        cap,
        ref,
    )
    rows.append(
        {
            "model": "floor_noise_xgboost",
            **res["vs_capped_truth"],
            "rmse_raw_truth": res["vs_raw_truth"]["rmse"],
            "std_ratio": res["distribution_vs_capped_truth"]["std_ratio"],
        }
    )

    for name, factory in MODELS.items():
        cv = cross_validate(factory, X_train, y_train, train)
        model = factory()
        model.fit(X_train, y_train)
        pred = np.clip(model.predict(X_test_last), 0, cap)
        res = write_report(
            out / name, name, test, test_last, pred, cap, ref, extra={**cv, "features": cols}
        )
        rows.append(
            {
                "model": name,
                **res["vs_capped_truth"],
                "rmse_raw_truth": res["vs_raw_truth"]["rmse"],
                "std_ratio": res["distribution_vs_capped_truth"]["std_ratio"],
                **cv,
            }
        )

    table = pd.DataFrame(rows).drop(columns=["cv_rmse_folds"], errors="ignore")
    summary = [
        f"# {subset} baselines (RUL cap {cap})",
        "",
        "Test metrics on the last observed cycle of each engine. `rmse` is vs capped truth "
        "(the convention in most papers); `rmse_raw_truth` is vs the uncapped labels. "
        "`cv_rmse_mean` is 5-fold GroupKFold-by-engine on train -- use it, not test, "
        "for model selection.",
        "",
        table.to_markdown(index=False),
        "",
        "## Sanity checks",
        "",
        "```json",
        json.dumps(checks, indent=2),
        "```",
    ]
    if subset == "FD001":
        summary += [
            "",
            "## Published FD001 reference (RMSE)",
            "",
            pd.Series(PUBLISHED_FD001, name="RMSE").to_markdown(),
        ]
    (out / "SUMMARY.md").write_text("\n".join(summary) + "\n")
    print(table.to_string(index=False))
    return table


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--subset", default="FD001")
    p.add_argument("--cap", type=float, default=125)
    p.add_argument("--window", type=int, default=30)
    p.add_argument("--out", type=Path, default=REPO_ROOT / "reports")
    a = p.parse_args()
    run(a.subset, a.cap, a.window, a.out)


if __name__ == "__main__":
    main()
