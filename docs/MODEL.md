# Sequence model: what we tried and why the GRU won

**Input (both datasets):** a window of the last *L* per-cycle feature vectors, right-aligned
so the final position is the cycle being predicted. Windows that would start before cycle 1
are padded at the front and masked. Tests check that windows never include later cycles or
another engine, and that padded values can't change predictions.

- C-MAPSS: condition-normalised informative sensors + age (cycle/100); L = 30; target RUL
  capped at 125.
- N-CMAPSS: 14 healthy-baseline residuals + standardised flight profile (alt, Mach, TRA, T2,
  flight length) + flight class + age; L = 20; uncapped RUL.

This per-cycle representation was chosen over raw 1 Hz within-flight windows: attributions
land on (cycle, sensor), which is what an explanation can talk about and an eval can check.

## Model selection protocol

`python -m cmapss.tune` runs **nested engine-level CV on the training set only**. Outer
3-fold GroupKFold scores configs. Inside each outer-train set, 15% of engines drive early
stopping. Test data is never loaded. Each held-out fold is scored two ways: every cycle, and
one random cycle per engine (the analogue of C-MAPSS's truncated test engines). XGBoost on
the engineered window features runs on **identical folds** as a like-for-like reference.

All selection so far was done on FD001 and then applied unchanged to every other setting. No
per-subset tuning, so other subsets' test results are not tuned against.

## FD001 results (3-fold engine CV, training set; full tables in `reports/tuning/`)

| config | held-out RMSE, all cycles | one point per engine | final train RMSE |
|---|---|---|---|
| XGBoost (reference) | 12.16 | 13.71 | – |
| **GRU, d=64, 2 layers, warmup + cosine, 60 epochs** | **12.26** | **13.54** | 6.3 |
| GRU + dropout 0.3, wd 1e-2, input noise 0.1 | 12.98 | 13.42 | 8.2 |
| GRU, d=32 | 13.74 | 14.78 | 7.3 |
| Transformer, d=64, constant LR | 15.32 | 16.66 | 6.2 |
| Transformer, warmup + cosine | 15.23 | 15.42 | 4.4 |
| Transformer, d=32, 1 layer, dropout 0.3, wd 0.1, noise 0.1 | 15.87 | 16.24 | 10.6 |
| Transformer, dropout 0.5, wd 0.3, noise 0.3 | 14.55 | 15.12 | 17.0 |

**Reading.** The Transformer overfits ~70 training engines: training error 4–6, held-out
~15, best epoch within the first 6. Regularising it hard swaps overfitting for underfitting
(train 17) without getting near the GRU. The GRU's assumption that the signal evolves step by
step suits slow monotone degradation. **The GRU ties XGBoost on FD001**: a deep model doesn't
buy accuracy on this subset, which matches FD001 being close to saturated (see PROTOCOL.md).
What it does buy is a differentiable model over (cycle, sensor), which the explanation
pipeline uses for attributions.

A shorter schedule was also checked (30 epochs; batch 256 or 512 at 2× LR): held-out
12.7–13.1 on all cycles and 13.55–13.97 one point per engine. That's within fold noise of the
60-epoch run but no better, so the validated 60-epoch config is used everywhere:
`{"arch": "gru", "lr": 1e-3, "warmup": 2, "cosine": true, "epochs": 60, "patience": 0}`
(train all epochs, keep the weights with the best early-stopping-set RMSE).

## A flaw in the validation, found and fixed

The first full runs scored worse on test than CV predicted (FD001: GRU 14.2 ± 0.4 per seed,
5-seed ensemble 13.7, against XGBoost 11.9). The cause was the CV views. Random points over
whole engine lives are ~40% in the flat capped region (RUL ≥ 125), where every model does
well. Only 11% of FD001 test engines are there. The views over-weighted the easy region.

`tune.py` now also scores **held-out cycles below the cap**, mirroring the cap-independent
test metric. It needs no test information. On the same folds:

| | all cycles | one point per engine | **below cap** |
|---|---|---|---|
| XGBoost | 12.16 | 13.71 | **13.20** |
| GRU | 12.26 | 13.54 | **13.89** |

The below-cap view agrees with test: XGBoost is better. Use it for selection from here on.
Paired bootstrap on test engines (GRU ensemble − XGBoost RMSE): FD001 +1.77, 95% CI
[0.11, 3.52]; FD003 +0.05, CI [−1.71, 1.92].

## Test results: GRU (5 seeds, config above, no per-subset tuning) vs XGBoost

C-MAPSS, cap 125, last observed cycle. Differences are GRU-ensemble minus XGBoost RMSE, 95%
paired-bootstrap CI over test engines.

| subset | XGBoost | GRU per seed | GRU 5-seed ensemble | diff CI | XGBoost, RUL ≤ cap | GRU ens., RUL ≤ cap | diff CI |
|---|---|---|---|---|---|---|---|
| FD001 | 11.93 | 14.20 ± 0.40 | 13.69 | [+0.11, +3.52] | 11.60 | 13.23 | [−0.14, +3.60] |
| FD002 | 12.70 | 13.85 ± 0.26 | 13.40 | [−0.19, +1.55] | 12.90 | 14.05 | [+0.15, +2.14] |
| FD003 | 12.12 | 13.26 ± 0.87 | 12.17 | [−1.71, +1.92] | 11.47 | 12.35 | [−1.02, +2.98] |
| FD004 | 13.84 | 13.62 ± 0.37 | 12.86 | [−2.12, +0.08] | 14.07 | 14.07 | [−1.06, +1.04] |

N-CMAPSS, uncapped, every test cycle:

| setting | age-only floor | XGBoost | GRU per seed | GRU ensemble |
|---|---|---|---|---|
| pooled | 11.9 | 7.10 | 7.67 ± 0.32 | 7.30 |
| DS02 | 9.4 | 6.42 | 9.24 ± 2.55 | 8.71 |

**Bottom line:**
- A single GRU is worse than XGBoost everywhere except FD004.
- A 5-seed GRU ensemble ties XGBoost on FD003, FD004 and N-CMAPSS pooled, and loses on
  FD001/FD002.
- On DS02 (5 training engines after early stopping) the GRU is no better than predicting from
  age.

Nothing here supports "the deep model is more accurate". The GRU is a competent second
model, not an upgrade.
