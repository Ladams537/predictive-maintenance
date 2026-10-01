# Evaluation protocol and decisions

The whole point of this file is that no number is reported without saying how it was made.

## Data

- Source: NASA PCoE "Turbofan Engine Degradation Simulation Data Set" (C-MAPSS), fetched from
  `phm-datasets.s3.amazonaws.com`, sha256-pinned in `src/cmapss/download.py`.
- 26 columns: unit, cycle, 3 operating settings, **21** sensors (the readme says "26 sensors";
  it means 26 columns).
- The readme swaps FD004's counts: the files have **249 train / 248 test** units.
- Unit IDs restart at 1 in every file. Train unit 1 ≠ test unit 1. Never join on `unit`.

## Labels

- Train RUL = (unit's last cycle − cycle). Last train cycle = failure.
- Test RUL per row = RUL_FDxxx[unit] + (unit's last observed cycle − cycle).
- **Benchmark evaluation uses only the last observed cycle of each test engine** (n=100 on
  FD001). That's a small sample: expect ±1.5 RMSE noise between equivalent models.

## The RUL cap (the single biggest lever on the headline number)

Training targets are capped at 125 (piecewise-linear RUL, Heimes 2008; Li et al. 2018 use 125,
Zheng et al. 2017 use 130). The rationale: early in life there is no degradation signal, so
asking the model to distinguish RUL 200 from RUL 300 is asking it to guess.

Consequences we measured on FD001 / XGBoost:

| training target | RMSE vs capped truth | RMSE vs raw truth |
|---|---|---|
| capped at 125 | 12.2 | 13.4 |
| capped at 130 | 12.5 | 13.7 |
| uncapped | 15.6 | **25.4** |

So "SOTA on FD001" is a statement about the capped problem. We always report both columns.
Test truth on FD001 tops out at 145, so capping the test labels only affects the 11 engines
above 125. That's why the two columns are close.

## Validation

- 5-fold `GroupKFold` by engine on the training set. `assert_units_disjoint` runs on every fold.
- Validation is scored on 5 random truncation points per held-out engine rather than every
  cycle. This mimics the test protocol and stops long-lived engines dominating.
- **Model selection uses CV RMSE, never test RMSE.** Test is run each time for the report,
  but it is not a tuning target.

## Sanity floors (a model that doesn't clear these is broken)

- **mean:** constant prediction = mean capped train RUL.
- **lifetime:** mean train lifetime − current cycle. No sensors at all.
- **noise:** XGBoost trained on Gaussian noise of the same shape as the real features.
  This should collapse to ≈ the mean floor with std ratio ≈ 0, and it does (42.3, 0.11).

## Why we believe XGBoost = 12.2 (it's inside the published SOTA band)

An off-the-shelf tree model matching deep-learning papers is a red flag, so we checked
(`uv run python -m cmapss.ablation`, FD001):

| check | RMSE (capped) | reading |
|---|---|---|
| 5 seeds | 11.8 – 12.4 | stable, not a lucky seed |
| CV on held-out engines | 12.0 ± 1.5 | train-side estimate agrees with test |
| labels shuffled | 42.5 | = mean floor, so no leakage path from labels |
| `cycle` feature only | 31.2 | age alone is weak; the sensors carry the signal |
| all features except `cycle` | 13.2 | most of the signal is in sensor trends |
| last values only (no window stats) | 16.9 | window mean/slope is what does the work |

Plus the tests: no train/test row overlap, features invariant to truncating future cycles
(no lookahead), features for one unit unchanged when other units are removed.

Conclusion: the number is real *for the capped, last-cycle FD001 protocol*. FD001 is close to
saturated with good feature engineering. The deep-model story has to be won on FD002/FD004
(six operating conditions) and/or on what the model enables for explanations, not on FD001
RMSE alone.

## Known gaps / next

- FD002/FD004: all 21 sensors vary with operating condition, so they need per-condition
  normalisation (cluster on op1–op3, z-score per cluster) before features mean anything.
- The PHM08 score is a sum, so it's only comparable within a subset.
