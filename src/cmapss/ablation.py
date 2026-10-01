"""Interrogate a suspiciously good baseline: seeds, feature ablations, shuffled labels, caps.

Usage: uv run python -m cmapss.ablation --subset FD001
Results are quoted in docs/PROTOCOL.md.
"""

import argparse

import numpy as np

from cmapss.baselines import MODELS
from cmapss.data import cap_rul, last_cycles, load_test, load_train
from cmapss.features import feature_columns, informative_sensors, window_features
from cmapss.metrics import rmse


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--subset", default="FD001")
    p.add_argument("--cap", type=float, default=125)
    a = p.parse_args()

    train, test = load_train(a.subset), load_test(a.subset)
    test_last = last_cycles(test)
    sensors = informative_sensors(train)
    cols = feature_columns(sensors)
    X_tr = window_features(train, sensors)[cols]
    X_te = window_features(test, sensors)[cols].loc[test.groupby("unit").cycle.idxmax()]
    y_raw = test_last["rul"].to_numpy(float)

    def score(features, train_cap=a.cap, seed=0, labels=None):
        model = MODELS["xgboost"]().set_params(random_state=seed)
        y = cap_rul(train["rul"], train_cap) if labels is None else labels
        model.fit(X_tr[features], y)
        pred = np.clip(model.predict(X_te[features]), 0, None)
        return rmse(cap_rul(y_raw, a.cap), np.minimum(pred, a.cap)), rmse(y_raw, pred)

    rows = {f"seed {s}": score(cols, seed=s) for s in range(5)}
    rows["cycle only"] = score(["cycle"])
    rows["no cycle"] = score([c for c in cols if c != "cycle"])
    rows["last values only"] = score([c for c in cols if c.endswith("_last")])
    rows["train cap 130"] = score(cols, train_cap=130)
    rows["train uncapped"] = score(cols, train_cap=None)
    shuffled = np.random.default_rng(0).permutation(cap_rul(train["rul"], a.cap))
    rows["shuffled labels"] = score(cols, labels=shuffled)

    print(f"{'check':<20} {'rmse_capped':>12} {'rmse_raw':>10}")
    for k, (c, r) in rows.items():
        print(f"{k:<20} {c:>12.2f} {r:>10.2f}")


if __name__ == "__main__":
    main()
