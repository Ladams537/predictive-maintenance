"""N-CMAPSS baselines: floors + linear + XGBoost on per-cycle healthy-baseline residuals.

Protocol differences from C-MAPSS (see docs/NCMAPSS.md):
- N-CMAPSS test engines run to failure, so we score *every* test cycle, not just the last.
- Target is uncapped RUL (the N-CMAPSS convention; lifetimes are only ~60-100 cycles).
- Two settings: `pooled` (all subsets together -- what the explainer will use, since fault
  type ~ subset) and `DS02` (the PHM21 challenge subset most papers report on).

Usage: uv run python -m cmapss.ncmapss_baselines
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import GroupKFold  # noqa: E402

from cmapss import sanity  # noqa: E402
from cmapss.baselines import MODELS, SEED  # noqa: E402
from cmapss.data import REPO_ROOT  # noqa: E402
from cmapss.features import feature_columns, window_features  # noqa: E402
from cmapss.metrics import distribution_check, rmse, summarize  # noqa: E402
from cmapss.ncmapss_features import OPS, RESID, load_cycles  # noqa: E402
from cmapss.report import INK, PRED, TRUE  # noqa: E402

WINDOW = 10
OUT_ROOT = REPO_ROOT / "reports" / "ncmapss"
GROUND_TRUTH = OUT_ROOT / "fault_ground_truth.csv"


def build_features(cycles: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    df = cycles.rename(columns={"unit": "unit_local"}).assign(unit=cycles["engine"])
    df = df.sort_values(["unit", "cycle"]).reset_index(drop=True)
    wf = window_features(df, RESID, WINDOW)
    # OPS, Fc and n_samples are already columns of df (current-cycle values).
    cols = feature_columns(RESID) + OPS + ["Fc", "n_samples"]
    data = pd.concat([df, wf.drop(columns=["cycle"])], axis=1)
    assert not data.columns.duplicated().any()
    return data, cols


def cross_validate(factory, X, y, groups, n_splits=5) -> dict:
    scores = []
    for tr, va in GroupKFold(n_splits=n_splits).split(X, y, groups=groups):
        sanity.assert_units_disjoint(groups.iloc[tr], groups.iloc[va])
        m = factory().fit(X.iloc[tr], y[tr])
        scores.append(rmse(y[va], m.predict(X.iloc[va])))
    return {
        "cv_rmse_mean": round(float(np.mean(scores)), 3),
        "cv_rmse_std": round(float(np.std(scores)), 3),
    }


def breakdown(test: pd.DataFrame, pred: np.ndarray, by: str) -> pd.DataFrame:
    d = test.assign(err=pred - test["rul"])
    return (
        d.groupby(by, observed=True)
        .agg(
            engines=("engine", "nunique"),
            cycles=("err", "size"),
            rmse=("err", lambda e: float(np.sqrt(np.mean(e**2)))),
            bias=("err", "mean"),
        )
        .round(2)
    )


def _trajectories(test: pd.DataFrame, pred: np.ndarray, path: Path) -> None:
    engines = test[["engine", "subset", "unit_local", "components"]].drop_duplicates()
    n = len(engines)
    ncol = 6
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(2.6 * ncol, 2.0 * nrow), squeeze=False, sharey=True
    )
    for ax, (_, e) in zip(axes.ravel(), engines.iterrows(), strict=False):
        m = (test["engine"] == e.engine).to_numpy()
        ax.plot(test.cycle[m], test.rul[m], color=TRUE, lw=1.5)
        ax.plot(test.cycle[m], pred[m], color=PRED, lw=1.5)
        r = rmse(test.rul[m], pred[m])
        ax.set_title(
            f"{e.subset} u{e.unit_local} {e.components}\nRMSE {r:.1f}", fontsize=7, loc="left"
        )
        ax.tick_params(labelsize=6)
    for ax in axes.ravel()[n:]:
        ax.axis("off")
    axes[0, 0].plot([], [], color=TRUE, label="true RUL")
    axes[0, 0].plot([], [], color=PRED, label="predicted")
    axes[0, 0].legend(frameon=False, fontsize=6)
    fig.supxlabel("cycle", color=INK)
    fig.supylabel("RUL (cycles)", color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)


def write_report(
    out: Path, name: str, test: pd.DataFrame, pred: np.ndarray, extra: dict | None = None
) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    y = test["rul"].to_numpy(float)
    res = {
        "model": name,
        "all_test_cycles": summarize(y, pred),
        "distribution": distribution_check(y, pred),
        **(extra or {}),
    }
    tables = {by: breakdown(test, pred, by) for by in ("subset", "components", "Fc")}
    per_engine = breakdown(test, pred, ["subset", "unit_local", "components", "Fc"])
    per_engine.to_csv(out / "per_engine.csv")
    _trajectories(test, pred, out / "trajectories.png")
    (out / "metrics.json").write_text(
        json.dumps(
            {**res, **{f"by_{k}": v.reset_index().to_dict("records") for k, v in tables.items()}},
            indent=2,
            default=str,
        )
    )
    m, d = res["all_test_cycles"], res["distribution"]
    md = [
        f"# {name}",
        "",
        f"Uncapped RUL, every test cycle (n={len(y)} cycles, {test.engine.nunique()} engines).",
        "",
        f"**RMSE {m['rmse']}**, MAE {m['mae']}, mean bias {m['mean_bias']}, "
        f"std ratio {d['std_ratio']}.",
        "",
    ]
    for by, t in tables.items():
        md += [f"## By {by}", "", t.to_markdown(), ""]
    md += [
        "## Worst engines",
        "",
        per_engine.sort_values("rmse", ascending=False).head(8).to_markdown(),
        "",
        "![trajectories](trajectories.png)",
    ]
    if extra:
        md += ["", "```json", json.dumps(extra, indent=2, default=str), "```"]
    (out / "report.md").write_text("\n".join(md) + "\n")
    return res


def run(setting: str, data: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    dev, test = data[data.split == "dev"], data[data.split == "test"].reset_index(drop=True)
    if setting != "pooled":
        dev, test = (
            dev[dev.subset.str.startswith(setting)],
            test[test.subset.str.startswith(setting)].reset_index(drop=True),
        )
    X, y = dev[cols], dev["rul"].to_numpy(float)
    out = OUT_ROOT / setting
    life = dev.groupby("engine").cycle.max().mean()
    preds = {
        "floor_mean": np.full(len(test), y.mean()),
        "floor_lifetime": np.clip(life - test["cycle"].to_numpy(), 0, None),
    }
    noise = MODELS["xgboost"]().fit(sanity.noise_features(*X.shape, seed=SEED), y)
    preds["floor_noise_xgboost"] = noise.predict(
        sanity.noise_features(len(test), len(cols), seed=SEED + 1)
    )
    rows = []
    for name, p in preds.items():
        r = write_report(out / name, name, test, p)
        rows.append(
            {"model": name, **r["all_test_cycles"], "std_ratio": r["distribution"]["std_ratio"]}
        )
    for name, factory in MODELS.items():
        cv = cross_validate(factory, X, y, dev["engine"])
        p = np.clip(factory().fit(X, y).predict(test[cols]), 0, None)
        r = write_report(out / name, name, test, p, extra=cv)
        rows.append(
            {
                "model": name,
                **r["all_test_cycles"],
                "std_ratio": r["distribution"]["std_ratio"],
                **cv,
            }
        )
    table = pd.DataFrame(rows)
    (out / "SUMMARY.md").write_text(
        "\n".join(
            [
                f"# N-CMAPSS {setting} baselines",
                "",
                f"Train: {dev.engine.nunique()} dev engines; "
                f"test: {test.engine.nunique()} engines, "
                f"{len(test)} cycles. Uncapped RUL, every test cycle scored. CV = 5-fold "
                "GroupKFold by engine on dev.",
                "",
                table.to_markdown(index=False),
                "",
            ]
        )
    )
    print(f"== {setting}\n{table.to_string(index=False)}")
    return table


def main() -> None:
    data, cols = build_features(load_cycles())
    gt = pd.read_csv(GROUND_TRUTH)[["subset", "unit", "components"]]
    data = data.merge(
        gt.rename(columns={"unit": "unit_local"}),
        on=["subset", "unit_local"],
        how="left",
        validate="many_to_one",
    )
    assert data["components"].notna().all()
    for setting in ("pooled", "DS02"):
        run(setting, data, cols)


if __name__ == "__main__":
    main()
