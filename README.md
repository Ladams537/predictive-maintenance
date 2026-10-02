# predictive-maintenance

Remaining Useful Life (RUL) prediction on NASA C-MAPSS turbofan data, with LLM-generated
failure explanations grounded in the sensor signals that drove each prediction.

**Status:** week 1. C-MAPSS pipeline (all four subsets), sanity floors, linear + XGBoost baselines, per-model
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

## Current numbers (RUL cap 125, last-cycle test evaluation)

| subset | floor (lifetime) | linear | XGBoost | XGBoost, true RUL ≤ cap only | XGBoost vs raw truth |
|---|---|---|---|---|---|
| FD001 | 36.1 | 18.2 | 11.9 | 11.6 | 13.2 |
| FD002 | 34.2 | 18.4 | 12.7 | 12.9 | 25.4 |
| FD003 | 46.1 | 18.1 | 12.1 | 11.5 | 14.0 |
| FD004 | 52.7 | 21.9 | 13.8 | 14.1 | 26.2 |

FD001 published for comparison: CNN 18.45 (Babu 2016), LSTM 16.14 (Zheng 2017),
DCNN 12.61 (Li 2018), recent attention/Transformer models ~11–12. On FD002/FD004 this
baseline beats those older papers by ~10 RMSE. That's an open question, not a claim: see
[`docs/PROTOCOL.md`](docs/PROTOCOL.md), which also documents how every number is computed
and how the suspicious ones were checked.

## Layout

```
src/cmapss/
  data.py       load train/test, attach RUL, cap_rul, sensor descriptions (Saxena 2008)
  download.py   fetch + checksum verification
  conditions.py operating-condition clustering + per-condition normalisation
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
