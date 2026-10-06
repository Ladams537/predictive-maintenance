"""Train the RUL Transformer on C-MAPSS or N-CMAPSS, several seeds, full report.

Protocol (same as the baselines, see docs/PROTOCOL.md):
- Early stopping uses VAL_FRAC of the *training* engines, chosen per seed. Test is never
  looked at during training or model selection.
- Each seed's test predictions are reported; the headline is the mean over seeds of per-seed
  RMSE (not the ensemble, which is reported separately and is always a bit better).

Usage:
  uv run python -m cmapss.train cmapss FD001
  uv run python -m cmapss.train ncmapss pooled
"""

import argparse
import json
import time
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import torch

from cmapss import sanity
from cmapss.baselines import prepare
from cmapss.data import REPO_ROOT, cap_rul
from cmapss.metrics import rmse
from cmapss.model import ARCHS, RULTransformer
from cmapss.seq import Windows, make_windows

VAL_FRAC = 0.15
MODELS_DIR = REPO_ROOT / "models"


def _batches(w: Windows, size: int, rng: np.random.Generator | None):
    idx = rng.permutation(len(w)) if rng is not None else np.arange(len(w))
    for i in range(0, len(w), size):
        j = idx[i : i + size]
        yield torch.from_numpy(w.X[j]), torch.from_numpy(w.pad[j]), torch.from_numpy(w.y[j])


@torch.no_grad()
def predict(model: RULTransformer, w: Windows, batch: int = 2048) -> np.ndarray:
    model.eval()
    return np.concatenate([model(x, p).numpy() for x, p, _ in _batches(w, batch, None)])


@dataclass(frozen=True)
class Config:
    arch: str = "transformer"
    d_model: int = 64
    n_layers: int = 2
    dropout: float = 0.1
    lr: float = 1e-3
    weight_decay: float = 1e-4
    batch: int = 256
    epochs: int = 80
    warmup: int = 0  # epochs of linear warmup
    cosine: bool = False  # cosine decay to 0 over `epochs`
    patience: int = 10  # early stopping; 0 = train all epochs, keep best-val weights
    input_noise: float = 0.0  # std of Gaussian noise added to real (non-pad) inputs in training


def _lr_factor(cfg: Config, epoch: float) -> float:
    if cfg.warmup and epoch < cfg.warmup:
        return (epoch + 1) / (cfg.warmup + 1)
    if cfg.cosine:
        return 0.5 * (1 + np.cos(np.pi * min(epoch, cfg.epochs) / cfg.epochs))
    return 1.0


def fit(
    train: Windows, val: Windows, length: int, seed: int, cfg: Config | None = None, log=print
) -> tuple:
    cfg = cfg or Config()
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    model = ARCHS[cfg.arch](
        train.X.shape[2], length, d_model=cfg.d_model, n_layers=cfg.n_layers, dropout=cfg.dropout
    )
    opt = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda e: _lr_factor(cfg, e))
    best, best_state, best_epoch = np.inf, None, 0
    history = {"train_rmse": [], "val_rmse": []}
    for epoch in range(cfg.epochs):
        model.train()
        se, n = 0.0, 0
        for x, p, y in _batches(train, cfg.batch, rng):
            if cfg.input_noise:
                x = x + cfg.input_noise * torch.randn_like(x) * (~p).unsqueeze(-1)
            opt.zero_grad()
            loss = torch.nn.functional.mse_loss(model(x, p), y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            se, n = se + loss.item() * len(y), n + len(y)
        sched.step()
        val_rmse = rmse(val.y, predict(model, val))
        history["train_rmse"].append(round(float(np.sqrt(se / n)), 3))
        history["val_rmse"].append(round(val_rmse, 3))
        if val_rmse < best:
            best, best_epoch = val_rmse, epoch
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        elif cfg.patience and epoch - best_epoch >= cfg.patience:
            break
    model.load_state_dict(best_state)
    log(f"    seed {seed}: best val RMSE {best:.2f} at epoch {best_epoch} (stopped at {epoch})")
    return model, {"val_rmse": round(best, 3), "best_epoch": best_epoch, **history}


def split_engines(engines: np.ndarray, seed: int) -> np.ndarray:
    """Boolean mask over `engines`: True = held out for early stopping."""
    uniq = np.unique(engines)
    rng = np.random.default_rng(10_000 + seed)
    val = rng.choice(uniq, size=max(2, round(VAL_FRAC * len(uniq))), replace=False)
    return np.isin(engines, val)


def run_seeds(train_w: Windows, test_w: Windows, length: int, seeds: int, tag: str, cfg: Config):
    preds, infos = [], []
    for seed in range(seeds):
        is_val = split_engines(train_w.engine, seed)
        sanity.assert_units_disjoint(
            np.unique(train_w.engine[~is_val]), np.unique(train_w.engine[is_val])
        )
        t = time.time()
        model, info = fit(train_w.subset(~is_val), train_w.subset(is_val), length, seed, cfg)
        info["seconds"] = round(time.time() - t)
        out = MODELS_DIR / tag
        out.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), out / f"seed{seed}.pt")
        preds.append(predict(model, test_w))
        infos.append(info)
    return np.stack(preds), infos


def _seed_summary(per_seed: list[float]) -> dict:
    return {
        "per_seed_test_rmse": per_seed,
        "seed_mean": round(float(np.mean(per_seed)), 3),
        "seed_std": round(float(np.std(per_seed)), 3),
    }


# --------------------------------------------------------------------------- C-MAPSS
CMAPSS_LENGTH = 30


def cmapss_data(subset: str, cap: float = 125) -> dict:
    p = prepare(subset)
    feats = p.sensors + ["age"]
    train = p.train.assign(age=p.train.cycle / 100, target=cap_rul(p.train.rul, cap))
    test = p.test.assign(age=p.test.cycle / 100, target=cap_rul(p.test.rul, cap))
    te_w = make_windows(test, feats, "target", CMAPSS_LENGTH)
    is_last = pd.Series(te_w.cycle).groupby(te_w.engine).transform("max").to_numpy() == te_w.cycle
    return {
        "prepared": p,
        "features": feats,
        "length": CMAPSS_LENGTH,
        "train": make_windows(train, feats, "target", CMAPSS_LENGTH),
        "test": te_w.subset(is_last),
    }


def run_cmapss(subset: str, seeds: int, cfg: Config, name: str, cap: float = 125) -> dict:
    from cmapss.report import sensor_reference, write_report

    d = cmapss_data(subset, cap)
    p, tr_w, te_last = d["prepared"], d["train"], d["test"]
    print(f"{subset}: {len(tr_w)} train windows, {len(te_last)} test engines")
    P, infos = run_seeds(tr_w, te_last, d["length"], seeds, f"cmapss/{subset}/{name}", cfg)
    P = np.clip(P, 0, cap)
    test_last = p.test_last.set_index("unit").loc[te_last.engine].reset_index()
    y_cap = cap_rul(test_last.rul.to_numpy(float), cap)
    extra = {
        **_seed_summary([round(rmse(y_cap, s), 3) for s in P]),
        "window": d["length"],
        "config": asdict(cfg),
        "features": d["features"],
        "training": infos,
    }
    res = write_report(
        REPO_ROOT / "reports" / subset / name,
        f"{name} (seed ensemble)",
        p.test,
        test_last,
        P.mean(0),
        cap,
        sensor_reference(p.train, p.sensors),
        extra=extra,
    )
    return {
        "setting": subset,
        **extra,
        "ensemble": res["vs_capped_truth"]["rmse"],
        "ensemble_rul_le_cap": res["within_cap"]["rmse"],
    }


# --------------------------------------------------------------------------- N-CMAPSS
NCMAPSS_LENGTH = 20


def ncmapss_data(setting: str) -> dict:
    from cmapss.ncmapss_baselines import GROUND_TRUTH
    from cmapss.ncmapss_features import OPS, RESID, load_cycles

    c = load_cycles()
    if setting != "pooled":
        c = c[c.subset.str.startswith(setting)]
    gt = pd.read_csv(GROUND_TRUTH)[["subset", "unit", "components"]]
    c = c.merge(gt, on=["subset", "unit"], how="left", validate="many_to_one")
    dev = c.split == "dev"
    # Standardise flight-profile inputs with dev statistics only.
    prof = OPS + ["n_samples"]
    mu, sd = c.loc[dev, prof].mean(), c.loc[dev, prof].std()
    c = c.assign(
        **{f"z_{k}": (c[k] - mu[k]) / sd[k] for k in prof},
        fc=c.Fc / 3,
        age=c.cycle / 100,
        target=c.rul.astype(float),
    )
    feats = RESID + [f"z_{k}" for k in prof] + ["fc", "age"]
    test = c[~dev]
    return {
        "cycles": c,
        "features": feats,
        "length": NCMAPSS_LENGTH,
        "test_rows": test,
        "train": make_windows(c[dev], feats, "target", NCMAPSS_LENGTH, "engine"),
        "test": make_windows(test, feats, "target", NCMAPSS_LENGTH, "engine"),
    }


def run_ncmapss(setting: str, seeds: int, cfg: Config, name: str) -> dict:
    from cmapss.ncmapss_baselines import OUT_ROOT, write_report

    d = ncmapss_data(setting)
    tr_w, te_w = d["train"], d["test"]
    print(f"N-CMAPSS {setting}: {len(tr_w)} train windows, {len(te_w)} test cycles")
    P, infos = run_seeds(tr_w, te_w, d["length"], seeds, f"ncmapss/{setting}/{name}", cfg)
    P = np.clip(P, 0, None)
    rows = d["test_rows"].loc[te_w.index].rename(columns={"unit": "unit_local"})
    rows = rows.reset_index(drop=True)
    extra = {
        **_seed_summary([round(rmse(rows.rul, s), 3) for s in P]),
        "window": d["length"],
        "config": asdict(cfg),
        "features": d["features"],
        "training": infos,
    }
    res = write_report(
        OUT_ROOT / setting / name, f"{name} (seed ensemble)", rows, P.mean(0), extra=extra
    )
    return {"setting": setting, **extra, "ensemble": res["all_test_cycles"]["rmse"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset", choices=["cmapss", "ncmapss"])
    ap.add_argument("setting", help="FD001..FD004, or pooled / DS02")
    ap.add_argument("--config", default="{}", help="JSON overrides for Config")
    ap.add_argument("--name", default="transformer", help="report/model directory name")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--threads", type=int, default=0)
    a = ap.parse_args()
    if a.threads:
        torch.set_num_threads(a.threads)
    cfg = Config(**json.loads(a.config))
    run = run_cmapss if a.dataset == "cmapss" else run_ncmapss
    r = run(a.setting, a.seeds, cfg, a.name)
    print(json.dumps({k: v for k, v in r.items() if k not in ("training", "features")}, indent=2))
    out = MODELS_DIR / a.dataset / a.setting / a.name
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps(r, indent=2, default=str))


if __name__ == "__main__":
    main()
