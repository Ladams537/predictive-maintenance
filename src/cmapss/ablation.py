"""Interrogate a suspiciously good baseline: seeds, feature ablations, shuffled labels, caps,
and (on multi-condition subsets) what the condition normalisation is worth.

Usage: uv run python -m cmapss.ablation --subset FD001
Results are quoted in docs/PROTOCOL.md.
"""

import argparse

import numpy as np

from cmapss.baselines import MODELS, prepare
from cmapss.data import cap_rul
from cmapss.metrics import rmse


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--subset", default="FD001")
    p.add_argument("--cap", type=float, default=125)
    a = p.parse_args()

    d = prepare(a.subset)
    y_raw = d.test_last["rul"].to_numpy(float)
    within = y_raw <= a.cap

    def score(features=None, train_cap=a.cap, seed=0, labels=None, data=d):
        features = features or data.cols
        model = MODELS["xgboost"]().set_params(random_state=seed)
        y = cap_rul(data.train["rul"], train_cap) if labels is None else labels
        model.fit(data.X_train[features], y)
        pred = np.clip(model.predict(data.X_test_last[features]), 0, None)
        capped = np.minimum(pred, a.cap)
        return (
            rmse(cap_rul(y_raw, a.cap), capped),
            rmse(y_raw, pred),
            rmse(y_raw[within], capped[within]),
        )

    cols = d.cols
    rows = {f"seed {s}": score(seed=s) for s in range(5)}
    rows["cycle only"] = score(["cycle"])
    rows["no cycle"] = score([c for c in cols if c != "cycle"])
    rows["last values only"] = score([c for c in cols if c.endswith("_last")])
    rows["train cap 130"] = score(train_cap=130)
    rows["train uncapped"] = score(train_cap=None)
    shuffled = np.random.default_rng(0).permutation(cap_rul(d.train["rul"], a.cap))
    rows["shuffled labels"] = score(labels=shuffled)
    if d.n_conditions > 1:
        rows["no condition norm"] = score(data=prepare(a.subset, normalise=False))

    print(f"{a.subset}: {within.sum()}/{len(y_raw)} test engines have true RUL <= {a.cap:g}")
    print(f"{'check':<20} {'rmse_capped':>12} {'rmse_raw':>10} {'rmse_rul<=cap':>14}")
    for k, (c, r, w) in rows.items():
        print(f"{k:<20} {c:>12.2f} {r:>10.2f} {w:>14.2f}")


if __name__ == "__main__":
    main()
