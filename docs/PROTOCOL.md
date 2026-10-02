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

## Why we believe XGBoost ≈ 12 on FD001 (it's inside the published SOTA band)

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

## Operating conditions (FD002, FD004)

FD002/FD004 fly six discrete operating conditions, and sensors move far more with condition
than with wear. `ConditionNormalizer` clusters rows on the three settings (KMeans, k = number
of distinct rounded setting combinations: 1 on FD001/3, 6 on FD002/4) and z-scores each
sensor within its condition, using **train statistics only**. Tests check that each setting
combination maps to exactly one cluster in both splits, and that test values never move the
normalisation. It's applied to all four subsets. On FD001/3 it's a global z-score: linear
results are identical and XGBoost moves within its seed noise.

The normaliser is fit on all training engines, including each CV fold's validation engines.
It uses no labels and only per-condition sensor means and stds over ~200 engines, so the
leak is negligible. Noted rather than ignored.

Sensor selection counts distinct raw values *within* the median condition. FD002 then gets
the same 14 sensors as FD001. FD003/FD004 add s6 (bypass-duct pressure) and s10 (engine
pressure ratio), which fits physically: those are the subsets with fan degradation.

## Results, all subsets (cap 125, last-cycle test evaluation)

`rmse_rul_le_cap` scores only test engines whose true RUL ≤ 125, where the capping
convention makes no difference. **It's the most protocol-robust number we report.**

| subset | linear | XGBoost | XGBoost, RUL ≤ cap only | XGBoost vs raw truth | XGBoost CV |
|---|---|---|---|---|---|
| FD001 | 18.2 | 11.9 | 11.6 (n=89) | 13.2 | 12.1 ± 1.4 |
| FD002 | 18.4 | 12.7 | 12.9 (n=202) | 25.4 | 14.2 ± 0.9 |
| FD003 | 18.1 | 12.1 | 11.5 (n=85) | 14.0 | 11.3 ± 1.3 |
| FD004 | 21.9 | 13.8 | 14.1 (n=181) | 26.2 | 13.4 ± 1.0 |

`uv run python -m cmapss.ablation --subset FDxxx` on all four: seed spread ≤ 0.4, shuffled
labels → ~45 (the mean floor), cycle-only → 30–39. On FD002/FD004, removing condition
normalisation costs ~4 RMSE (12.7 → 16.4, 13.8 → 18.2).

### Open question: our multi-condition numbers beat the reference papers by ~10 RMSE

Reference figures (Babu 2016 CNN, Zheng 2017 LSTM, Li 2018 DCNN) for FD002/FD004 are
22–30. Our XGBoost gets 12.7/13.8. We've ruled out the obvious explanations:

- *Capping artefact?* No. On engines where capping is irrelevant it's 12.9/14.1.
- *Label leakage?* No. Shuffled labels collapse to the floor.
- *Train/test contamination?* No identical rows. Normalisation stats are train-only (tested).

The most plausible explanation is protocol: those papers normalise globally (min-max) rather
than per operating condition, and per-condition normalisation alone is worth ~4 RMSE here.
Recent papers that do normalise per condition are believed to report FD002 ≈ 13–15 and
FD004 ≈ 15–18, which would put this baseline *at* SOTA, not past it. **This is unverified.**
Settling it means reading a modern SOTA paper's protocol section: normalisation, test-label
capping, window length, last-cycle evaluation. Until then, the multi-condition numbers are
reported but not claimed as SOTA-beating.

The real gap on FD002/FD004 is engines with RUL > 125 (22–27% of test). No capped model can
tell RUL 150 from 190, so raw-truth RMSE stays ~25 whatever the model.

## Known gaps / next

- The PHM08 score is a sum, so it's only comparable within a subset.
