# predictive-maintenance

Remaining Useful Life (RUL) prediction on NASA C-MAPSS turbofan data, with LLM-generated
failure explanations grounded in the sensor signals that drove each prediction.

**Status:** week 1. C-MAPSS pipeline, sanity floors, linear + XGBoost baselines, per-model
reports. N-CMAPSS ingested as ground truth for the explanation evals
([`docs/NCMAPSS.md`](docs/NCMAPSS.md)).

## Quickstart

```bash
uv sync
uv run python -m cmapss.download          # fetch + sha256-verify C-MAPSS into data/raw/
uv run python -m cmapss.ncmapss_download  # N-CMAPSS (~5 min, 15.8 GB streamed, 4.6 GB kept)
uv run pytest                             # data/label/leakage tests
uv run python -m cmapss.baselines --subset FD001 --cap 125
```

Every model writes `reports/<subset>/<model>/` (metrics.json, report.md, per_unit.csv,
overview.png, worst_engines.png), and each subset gets a `SUMMARY.md`.

## Current numbers: FD001, RUL cap 125, last-cycle test evaluation

| model | test RMSE (capped truth) | test RMSE (raw truth) | CV RMSE (by engine) | pred/true std |
|---|---|---|---|---|
| floor: predict mean | 41.9 | 43.1 | – | 0.00 |
| floor: noise features → XGBoost | 42.3 | 43.3 | – | 0.11 |
| floor: mean lifetime − cycle | 36.1 | 36.8 | – | 1.04 |
| linear (Ridge, window features) | 18.2 | 19.5 | 18.7 ± 1.6 | 0.83 |
| XGBoost (window features) | 12.2 | 13.4 | 12.0 ± 1.5 | 1.00 |

Published FD001 for comparison: CNN 18.45 (Babu 2016), LSTM 16.14 (Zheng 2017),
DCNN 12.61 (Li 2018), recent attention/Transformer models ~11–12.

See [`docs/PROTOCOL.md`](docs/PROTOCOL.md) for exactly how these numbers are computed and why
the XGBoost result was checked before being trusted.

## Layout

```
src/cmapss/
  data.py       load train/test, attach RUL, cap_rul, sensor descriptions (Saxena 2008)
  download.py   fetch + checksum verification
  features.py   trailing-window features (last/mean/std/slope), no lookahead
  metrics.py    RMSE, MAE, PHM08 score, distribution check
  sanity.py     floors, leakage checks
  report.py     per-model report generation
  baselines.py  week-1 runner
  ncmapss.py    N-CMAPSS loader, float32 repack, per-engine fault ground truth
  ncmapss_download.py  streaming download + checksums
  ablation.py   seeds / feature ablations / shuffled labels for a suspicious result
tests/          data facts, label correctness, lookahead + leakage guards, N-CMAPSS truth
reports/        generated, committed so results are reviewable in diffs
```
