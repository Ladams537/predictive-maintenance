"""What is the N-CMAPSS XGBoost baseline actually using?

Checks: age only, no age, residuals only (no flight-profile features), flight profile only,
shuffled labels. Usage: uv run python -m cmapss.ncmapss_ablation
"""

import numpy as np

from cmapss.baselines import MODELS
from cmapss.features import feature_columns
from cmapss.metrics import rmse
from cmapss.ncmapss_baselines import build_features
from cmapss.ncmapss_features import OPS, RESID, load_cycles

PROFILE = OPS + ["Fc", "n_samples"]


def main() -> None:
    data, cols = build_features(load_cycles())
    for setting in ("pooled", "DS02"):
        d = data if setting == "pooled" else data[data.subset.str.startswith(setting)]
        dev, test = d[d.split == "dev"], d[d.split == "test"]
        y = dev["rul"].to_numpy(float)

        def score(features, labels=None, dev=dev, test=test, y=y):
            m = MODELS["xgboost"]().fit(dev[features], y if labels is None else labels)
            return rmse(test["rul"], np.clip(m.predict(test[features]), 0, None))

        resid = [c for c in feature_columns(RESID) if c != "cycle"]
        rows = {
            "all features": score(cols),
            "cycle only": score(["cycle"]),
            "no cycle": score([c for c in cols if c != "cycle"]),
            "residuals + cycle (no flight profile)": score(["cycle"] + resid),
            "residuals only": score(resid),
            "flight profile + cycle": score(["cycle"] + PROFILE),
            "shuffled labels": score(cols, np.random.default_rng(0).permutation(y)),
        }
        print(f"== {setting}")
        for k, v in rows.items():
            print(f"  {k:<40} {v:6.2f}")


if __name__ == "__main__":
    main()
