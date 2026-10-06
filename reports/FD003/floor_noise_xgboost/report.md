# floor_noise_xgboost

RUL cap: **125**. Evaluated on the last observed cycle of each test engine (n=100).

| truth | RMSE | MAE | PHM08 score | mean bias |
|---|---|---|---|---|
| capped | 43.953 | 37.108 | 56419.6 | 18.528 |
| raw | 45.362 | 38.668 | 56719.9 | 16.968 |
| true RUL ≤ cap only (n=85) | 45.633 | 37.922 | 56239.3 | 27.532 |

**Distribution:** std ratio 0.142 (1.0 = same spread as truth), KS 0.51 (p=0.0), pred range [75.3, 105.9] vs true [6.0, 125.0].

## Error by true-RUL bucket

| bucket         |   n |   rmse |   bias |
|:---------------|----:|-------:|-------:|
| [0.0, 25.0)    |  15 |  79.31 |  79.08 |
| [25.0, 50.0)   |  14 |  57.97 |  57.5  |
| [50.0, 75.0)   |  20 |  33.8  |  32.86 |
| [75.0, 100.0)  |  18 |  11.17 |   5.67 |
| [100.0, 125.0) |  18 |  24.15 | -22.79 |
| [125.0, inf)   |  15 |  32.85 | -32.49 |

## Worst engines

|   unit |   cycles_observed |   y_true |   y_true_raw |   y_pred |   err |
|-------:|------------------:|---------:|-------------:|---------:|------:|
|     50 |               147 |       11 |           11 |    102.8 |  91.8 |
|     39 |               310 |        8 |            8 |     95.6 |  87.6 |
|     46 |               180 |        7 |            7 |     92.8 |  85.8 |
|     99 |               289 |        8 |            8 |     89.9 |  81.9 |
|     81 |               155 |       15 |           15 |     96.6 |  81.6 |

![overview](overview.png)

![worst engines](worst_engines.png)

Grey lines: each informative sensor, z-scored with train-set stats, sign-flipped so up = toward failure, rolling mean over 10 cycles. Blue: their average. Sensors: s2 = Total temperature at LPC outlet (T24, °R), s3 = Total temperature at HPC outlet (T30, °R), s4 = Total temperature at LPT outlet (T50, °R), s6 = Total pressure in bypass-duct (P15, psia), s7 = Total pressure at HPC outlet (P30, psia), s8 = Physical fan speed (Nf, rpm), s9 = Physical core speed (Nc, rpm), s10 = Engine pressure ratio P50/P2 (epr), s11 = Static pressure at HPC outlet (Ps30, psia), s12 = Ratio of fuel flow to Ps30 (phi, pps/psi), s13 = Corrected fan speed (NRf, rpm), s14 = Corrected core speed (NRc, rpm), s15 = Bypass ratio (BPR), s17 = Bleed enthalpy (htBleed), s20 = HPT coolant bleed (W31, lbm/s), s21 = LPT coolant bleed (W32, lbm/s).
