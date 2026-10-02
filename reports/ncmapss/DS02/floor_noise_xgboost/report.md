# floor_noise_xgboost

Uncapped RUL, every test cycle (n=202 cycles, 3 engines).

**RMSE 22.288**, MAE 18.795, mean bias 3.432, std ratio 0.428.

## By subset

| subset   |   engines |   cycles |   rmse |   bias |
|:---------|----------:|---------:|-------:|-------:|
| DS02-006 |         3 |      202 |  22.29 |   3.43 |

## By components

| components   |   engines |   cycles |   rmse |   bias |
|:-------------|----------:|---------:|-------:|-------:|
| HPT+LPT      |         3 |      202 |  22.29 |   3.43 |

## By Fc

|   Fc |   engines |   cycles |   rmse |   bias |
|-----:|----------:|---------:|-------:|-------:|
|    1 |         1 |       76 |  23.54 |  -1.57 |
|    2 |         1 |       67 |  22.9  |   4.49 |
|    3 |         1 |       59 |  19.79 |   8.67 |

## Worst engines

|                                |   engines |   cycles |   rmse |   bias |
|:-------------------------------|----------:|---------:|-------:|-------:|
| ('DS02-006', 14, 'HPT+LPT', 1) |         1 |       76 |  23.54 |  -1.57 |
| ('DS02-006', 15, 'HPT+LPT', 2) |         1 |       67 |  22.9  |   4.49 |
| ('DS02-006', 11, 'HPT+LPT', 3) |         1 |       59 |  19.79 |   8.67 |

![trajectories](trajectories.png)
