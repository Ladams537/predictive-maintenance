"""Per-model reports. Every trained model gets one; RMSE alone is never the deliverable.

A report contains: metrics (vs capped and uncapped truth), distribution check, error by
true-RUL bucket, per-unit errors, worst-N engines with their sensor trajectories.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cmapss.data import SENSOR_DESCRIPTIONS, cap_rul  # noqa: E402
from cmapss.metrics import distribution_check, summarize  # noqa: E402

PRED = "#2a78d6"
TRUE = "#eb6834"
INK = "#52514e"
GRID = "#e4e3df"

plt.rcParams.update(
    {
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "font.size": 9,
    }
)

RUL_BUCKETS = [0, 25, 50, 75, 100, 125, np.inf]


def evaluate(y_true_raw: np.ndarray, y_pred: np.ndarray, cap: float | None) -> dict:
    """Metrics against both the capped and the raw test truth.

    Many papers cap the *test* labels too, which flatters RMSE on engines with true RUL > cap.
    We report both so the comparison to published numbers is explicit, not accidental.
    """
    y_capped = cap_rul(y_true_raw, cap)
    within = np.ones_like(y_true_raw, bool) if cap is None else y_true_raw <= cap
    return {
        "vs_capped_truth": summarize(y_capped, y_pred),
        "vs_raw_truth": summarize(y_true_raw, y_pred),
        # Engines where capping is irrelevant: comparable across capping conventions.
        "within_cap": {**summarize(y_true_raw[within], y_pred[within]), "n": int(within.sum())},
        "distribution_vs_capped_truth": distribution_check(y_capped, y_pred),
    }


def error_by_bucket(y_true: np.ndarray, y_pred: np.ndarray) -> pd.DataFrame:
    err = y_pred - y_true
    b = pd.cut(y_true, RUL_BUCKETS, right=False)
    return (
        pd.DataFrame({"bucket": b, "err": err})
        .groupby("bucket", observed=True)["err"]
        .agg(n="size", rmse=lambda e: float(np.sqrt(np.mean(e**2))), bias="mean")
        .round(2)
    )


def _scatter(ax, y_true, y_pred, title):
    lim = max(y_true.max(), y_pred.max()) * 1.05
    ax.plot([0, lim], [0, lim], color=INK, lw=1, ls="--", label="perfect")
    ax.scatter(y_true, y_pred, s=18, color=PRED, edgecolor="white", linewidth=0.8, label="engine")
    ax.set(xlabel="true RUL (cycles)", ylabel="predicted RUL (cycles)", title=title)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.legend(frameon=False, loc="upper left")


def _hist(ax, y_true, y_pred):
    bins = np.linspace(0, max(y_true.max(), y_pred.max()) + 1, 25)
    ax.hist(y_true, bins=bins, color=TRUE, histtype="step", lw=2, label="true (capped)")
    ax.hist(y_pred, bins=bins, color=PRED, histtype="step", lw=2, label="predicted")
    ax.set(xlabel="RUL (cycles)", ylabel="engines", title="Prediction vs truth distribution")
    ax.legend(frameon=False, loc="upper left")


def _unit_errors(ax, units, err):
    order = np.argsort(err)
    ax.bar(range(len(err)), err[order], color=PRED, width=0.8)
    ax.axhline(0, color=INK, lw=0.8)
    ax.set(
        xlabel="test engines, sorted by error",
        ylabel="pred − true (cycles)",
        title="Per-engine error (positive = late = dangerous)",
    )


def sensor_reference(train: pd.DataFrame, sensors: list[str]) -> pd.DataFrame:
    """Train-set mean/std per sensor, and its sign so that 'up' always means 'more degraded'."""
    sign = np.sign([np.corrcoef(train[s], -train["rul"])[0, 1] for s in sensors])
    return pd.DataFrame(
        {"mean": train[sensors].mean(), "std": train[sensors].std(), "sign": sign}, index=sensors
    )


def _worst_engines(test, worst, ref: pd.DataFrame, path: Path, smooth: int = 10):
    n = len(worst)
    fig, axes = plt.subplots(n, 1, figsize=(8, 2.0 * n), squeeze=False)
    for ax, (_, row) in zip(axes[:, 0], worst.iterrows(), strict=True):
        traj = test[test.unit == row.unit]
        z = (traj[ref.index] - ref["mean"]) / ref["std"] * ref["sign"]
        z = z.rolling(smooth, min_periods=1).mean()
        for s in ref.index:
            ax.plot(traj.cycle, z[s], lw=0.8, color="#b5b4ae")
        ax.plot(traj.cycle, z.mean(axis=1), lw=2, color=PRED, label="mean (health index)")
        ax.set_title(
            f"unit {int(row.unit)}: true {row.y_true:.0f}, pred {row.y_pred:.0f} "
            f"(err {row.err:+.0f}) — {len(traj)} cycles observed",
            fontsize=9,
            loc="left",
        )
        ax.set_ylabel("degradation (σ)")
    axes[0, 0].legend(frameon=False, loc="upper left")
    axes[-1, 0].set_xlabel("cycle")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_report(
    out_dir: Path,
    name: str,
    test: pd.DataFrame,
    test_last: pd.DataFrame,
    y_pred: np.ndarray,
    cap: float | None,
    sensor_ref: pd.DataFrame,
    extra: dict | None = None,
    n_worst: int = 5,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    y_raw = test_last["rul"].to_numpy(float)
    y_cap = cap_rul(y_raw, cap)
    result = {"model": name, "cap": cap, **evaluate(y_raw, y_pred, cap), **(extra or {})}

    buckets = error_by_bucket(y_cap, y_pred)
    per_unit = pd.DataFrame(
        {
            "unit": test_last["unit"],
            "cycles_observed": test_last["cycle"],
            "y_true": y_cap,
            "y_true_raw": y_raw,
            "y_pred": y_pred.round(1),
            "err": (y_pred - y_cap).round(1),
        }
    )
    per_unit.to_csv(out_dir / "per_unit.csv", index=False)
    worst = per_unit.reindex(per_unit.err.abs().sort_values(ascending=False).index).head(n_worst)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    _scatter(axes[0], y_cap, y_pred, f"{name}: test last-cycle")
    _hist(axes[1], y_cap, y_pred)
    _unit_errors(axes[2], per_unit.unit.to_numpy(), per_unit.err.to_numpy())
    fig.tight_layout()
    fig.savefig(out_dir / "overview.png", dpi=110)
    plt.close(fig)
    _worst_engines(test, worst, sensor_ref, out_dir / "worst_engines.png")

    (out_dir / "metrics.json").write_text(json.dumps(result, indent=2, default=str))
    m, r, w = result["vs_capped_truth"], result["vs_raw_truth"], result["within_cap"]
    d = result["distribution_vs_capped_truth"]
    md = [
        f"# {name}",
        "",
        f"RUL cap: **{cap}**. Evaluated on the last observed cycle of each test engine "
        f"(n={len(y_raw)}).",
        "",
        "| truth | RMSE | MAE | PHM08 score | mean bias |",
        "|---|---|---|---|---|",
        f"| capped | {m['rmse']} | {m['mae']} | {m['phm08_score']} | {m['mean_bias']} |",
        f"| raw | {r['rmse']} | {r['mae']} | {r['phm08_score']} | {r['mean_bias']} |",
        f"| true RUL ≤ cap only (n={w['n']}) | {w['rmse']} | {w['mae']} | {w['phm08_score']} "
        f"| {w['mean_bias']} |",
        "",
        f"**Distribution:** std ratio {d['std_ratio']} (1.0 = same spread as truth), "
        f"KS {d['ks_stat']} (p={d['ks_pvalue']}), "
        f"pred range {d['pred_range']} vs true {d['true_range']}.",
        "",
        "## Error by true-RUL bucket",
        "",
        buckets.to_markdown(),
        "",
        "## Worst engines",
        "",
        worst.to_markdown(index=False),
        "",
        "![overview](overview.png)",
        "",
        "![worst engines](worst_engines.png)",
        "",
        "Grey lines: each informative sensor, z-scored with train-set stats, sign-flipped so up = "
        "toward failure, rolling mean over 10 cycles. Blue: their average. Sensors: "
        + ", ".join(f"{s} = {SENSOR_DESCRIPTIONS[s]}" for s in sensor_ref.index)
        + ".",
    ]
    if extra:
        md += ["", "## Run details", "", "```json", json.dumps(extra, indent=2, default=str), "```"]
    (out_dir / "report.md").write_text("\n".join(md) + "\n")
    return result
