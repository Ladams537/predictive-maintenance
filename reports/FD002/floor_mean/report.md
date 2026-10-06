# floor_mean

RUL cap: **125**. Evaluated on the last observed cycle of each test engine (n=259).

| truth | RMSE | MAE | PHM08 score | mean bias |
|---|---|---|---|---|
| capped | 44.929 | 38.142 | 115589.9 | 13.222 |
| raw | 54.083 | 45.636 | 153229.3 | 5.728 |
| true RUL ≤ cap only (n=202) | 46.679 | 38.157 | 114579.7 | 27.7 |

**Distribution:** std ratio 0.0 (1.0 = same spread as truth), KS 0.552 (p=0.0), pred range [86.9, 86.9] vs true [6.0, 125.0].

## Error by true-RUL bucket

| bucket         |   n |   rmse |   bias |
|:---------------|----:|-------:|-------:|
| [0.0, 25.0)    |  58 |  74.62 |  74.48 |
| [25.0, 50.0)   |  29 |  48.33 |  47.91 |
| [50.0, 75.0)   |  31 |  26.81 |  25.59 |
| [75.0, 100.0)  |  48 |   7.4  |  -0.23 |
| [100.0, 125.0) |  36 |  26.09 | -24.89 |
| [125.0, inf)   |  57 |  38.09 | -38.09 |

## Worst engines

|   unit |   cycles_observed |   y_true |   y_true_raw |   y_pred |   err |
|-------:|------------------:|---------:|-------------:|---------:|------:|
|    211 |               155 |        6 |            6 |     86.9 |  80.9 |
|     44 |               164 |        6 |            6 |     86.9 |  80.9 |
|     11 |               162 |        6 |            6 |     86.9 |  80.9 |
|      7 |               184 |        6 |            6 |     86.9 |  80.9 |
|    177 |               191 |        6 |            6 |     86.9 |  80.9 |

![overview](overview.png)

![worst engines](worst_engines.png)

Grey lines: each informative sensor, z-scored with train-set stats, sign-flipped so up = toward failure, rolling mean over 10 cycles. Blue: their average. Sensors: s2 = Total temperature at LPC outlet (T24, °R), s3 = Total temperature at HPC outlet (T30, °R), s4 = Total temperature at LPT outlet (T50, °R), s7 = Total pressure at HPC outlet (P30, psia), s8 = Physical fan speed (Nf, rpm), s9 = Physical core speed (Nc, rpm), s11 = Static pressure at HPC outlet (Ps30, psia), s12 = Ratio of fuel flow to Ps30 (phi, pps/psi), s13 = Corrected fan speed (NRf, rpm), s14 = Corrected core speed (NRc, rpm), s15 = Bypass ratio (BPR), s17 = Bleed enthalpy (htBleed), s20 = HPT coolant bleed (W31, lbm/s), s21 = LPT coolant bleed (W32, lbm/s).
