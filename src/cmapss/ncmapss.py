"""N-CMAPSS (Arias Chao et al. 2021): storage and loading.

Why N-CMAPSS: unlike C-MAPSS it ships the simulator's *health parameters* (`T_*`: efficiency
and flow modifiers for fan, LPC, HPC, HPT, LPT) for every row. That's ground truth for
"which component is degrading", which the explanation evals need.

Raw files are float64 HDF5 (28.5 GB for all ten). `repack` writes float32 + gzip copies to
data/interim and verifies them before the raw file is removed. float32 keeps ~7 significant
digits, which resolves e.g. core speed (~8000 rpm) to ~0.001 rpm, far below sensor noise.

Usage:
  uv run python -m cmapss.ncmapss repack [--delete-raw]
  uv run python -m cmapss.ncmapss ground-truth   # -> reports/ncmapss/fault_ground_truth.csv
"""

import argparse
import shutil
import sys
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from cmapss.data import REPO_ROOT
from cmapss.ncmapss_download import DATA_DIR as RAW_DIR
from cmapss.ncmapss_download import SHA256

INTERIM_DIR = REPO_ROOT / "data" / "interim" / "N-CMAPSS"
CHUNK_ROWS = 1 << 16

# Name stems of the usable files. DS08d is corrupt upstream (see ncmapss_download).
SUBSETS = (
    "DS01-005",
    "DS02-006",
    "DS03-012",
    "DS04",
    "DS05",
    "DS06",
    "DS07",
    "DS08a-009",
    "DS08c-008",
)
GROUPS = ("A", "W", "X_s", "X_v", "T", "Y")
COMPONENTS = ("fan", "LPC", "HPC", "HPT", "LPT")
# |end-of-life minus first-cycle| health-parameter change that counts as "this component
# degraded". Untouched parameters move by exactly 0; the smallest real degradation is 0.0014
# (DS08a unit 15, HPT_eff). Degradations are a continuum above that, NOT a clean big/zero split,
# and eff/flow parameters differ in scale by ~10x -- compare severity per parameter, not raw.
DEGRADED_TOL = 1e-3


def _path(subset: str) -> Path:
    return INTERIM_DIR / f"N-CMAPSS_{subset}.h5"


def load(subset: str, split: str, groups=GROUPS, every: int = 1) -> pd.DataFrame:
    """One row per 1 Hz sample (~12k per flight cycle). `every` subsamples rows.

    Columns: A (unit, cycle, Fc = flight class 1-3, hs = 1 healthy / 0 abnormal degradation),
    W (operating conditions), X_s (14 real sensors), X_v (virtual sensors -- not measurable on
    a real engine, so never use them as model inputs), T (health parameters -- the ground
    truth; never a model input), Y -> `rul` (= unit's last cycle - cycle).
    """
    if split not in ("dev", "test"):
        raise ValueError("split is 'dev' or 'test'")
    frames = []
    with h5py.File(_path(subset), "r") as f:
        for g in groups:
            names = ["rul"] if g == "Y" else [x.decode() for x in f[f"{g}_var"]]
            frames.append(pd.DataFrame(f[f"{g}_{split}"][::every], columns=names))
    df = pd.concat(frames, axis=1)
    for c in ("unit", "cycle", "Fc", "hs"):
        if c in df:
            df[c] = df[c].astype(np.int32)
    return df


def fault_ground_truth(subsets=SUBSETS) -> pd.DataFrame:
    """Per engine: which health parameters (and hence components) degrade over its life.

    Derived from T, not from documentation. Matches the dataset paper's DS02 table exactly.
    Unit numbers are unique within a subset, not across subsets: key on (subset, unit).
    """
    rows = []
    for subset in subsets:
        for split in ("dev", "test"):
            df = load(subset, split, groups=("A", "T"))
            t_cols = [c for c in df.columns if c.endswith("_mod")]
            g = df.groupby("unit")
            delta = g[t_cols].last() - g[t_cols].first()
            transition = df[df.hs == 0].groupby("unit")["cycle"].min()
            for unit, d in delta.iterrows():
                params = [c.removesuffix("_mod") for c in t_cols if abs(d[c]) > DEGRADED_TOL]
                comps = [c for c in COMPONENTS if any(p.startswith(c + "_") for p in params)]
                rows.append(
                    {
                        "subset": subset,
                        "split": split,
                        "unit": int(unit),
                        "flight_class": int(g["Fc"].first()[unit]),
                        "eol_cycle": int(g["cycle"].max()[unit]),
                        "abnormal_from_cycle": int(transition.get(unit, -1)),
                        "components": "+".join(comps),
                        "params": ",".join(params),
                        **{f"delta_{c}": round(float(d[c]), 5) for c in t_cols},
                    }
                )
    return pd.DataFrame(rows)


def _target_dtype(dt: np.dtype) -> np.dtype:
    if dt.kind == "f":
        return np.dtype(np.float32)
    if dt.kind in "iu":
        return np.dtype(np.int32)
    return dt


def repack_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".h5.part")
    with h5py.File(src, "r") as fin, h5py.File(tmp, "w") as fout:
        fout.attrs["source_file"] = src.name
        fout.attrs["source_sha256"] = SHA256[src.name]
        for key, d in fin.items():
            dt = _target_dtype(d.dtype)
            if d.dtype.kind in "SO":
                fout.create_dataset(key, data=d[()])
                continue
            out = fout.create_dataset(
                key,
                shape=d.shape,
                dtype=dt,
                compression="gzip",
                compression_opts=4,
                shuffle=True,
                chunks=(min(CHUNK_ROWS, d.shape[0]), *d.shape[1:]),
            )
            for i in range(0, d.shape[0], CHUNK_ROWS):
                out[i : i + CHUNK_ROWS] = d[i : i + CHUNK_ROWS].astype(dt)
    verify_repack(src, tmp)
    tmp.rename(dst)


def verify_repack(src: Path, dst: Path) -> None:
    """Exact equality with the float32/int32 cast of the source, plus: integer-valued columns
    (A: unit, cycle, Fc, hs; Y: RUL) must round-trip with no change at all."""
    with h5py.File(src, "r") as a, h5py.File(dst, "r") as b:
        if set(a.keys()) != set(b.keys()):
            raise AssertionError(f"{dst.name}: key mismatch")
        for key, d in a.items():
            if d.dtype.kind in "SO":
                if not np.array_equal(d[()], b[key][()]):
                    raise AssertionError(f"{dst.name}/{key}: string arrays differ")
                continue
            exact = key.startswith(("A_", "Y_"))
            for i in range(0, d.shape[0], CHUNK_ROWS):
                x, y = d[i : i + CHUNK_ROWS], b[key][i : i + CHUNK_ROWS]
                ok = (
                    np.array_equal(y.astype(x.dtype), x)
                    if exact
                    else np.array_equal(y, x.astype(y.dtype))
                )
                if not ok:
                    raise AssertionError(f"{dst.name}/{key}: rows {i}+ differ")


def repack_all(delete_raw: bool) -> None:
    for src in sorted(RAW_DIR.glob("*.h5"), key=lambda p: p.stat().st_size):
        dst = INTERIM_DIR / src.name
        if dst.exists():
            verify_repack(src, dst)
        else:
            free = shutil.disk_usage(INTERIM_DIR.parent if INTERIM_DIR.exists() else REPO_ROOT)
            print(
                f"repacking {src.name} ({src.stat().st_size / 1e9:.2f} GB, "
                f"{free.free / 1e9:.1f} GB free)",
                flush=True,
            )
            repack_file(src, dst)
        print(f"  ok {dst.name} {dst.stat().st_size / 1e9:.2f} GB", flush=True)
        if delete_raw:
            src.unlink()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["repack", "ground-truth"])
    p.add_argument("--delete-raw", action="store_true")
    a = p.parse_args()
    if a.cmd == "repack":
        repack_all(a.delete_raw)
    else:
        out = REPO_ROOT / "reports" / "ncmapss" / "fault_ground_truth.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        gt = fault_ground_truth()
        gt.to_csv(out, index=False)
        print(gt.groupby(["subset", "components"]).size().to_string())
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
