# floor_lifetime

Uncapped RUL, every test cycle (n=202 cycles, 3 engines).

**RMSE 9.356**, MAE 7.526, mean bias 6.295, std ratio 0.999.

## By subset

| subset   |   engines |   cycles |   rmse |   bias |
|:---------|----------:|---------:|-------:|-------:|
| DS02-006 |         3 |      202 |   9.36 |    6.3 |

## By components

| components   |   engines |   cycles |   rmse |   bias |
|:-------------|----------:|---------:|-------:|-------:|
| HPT+LPT      |         3 |      202 |   9.36 |    6.3 |

## By Fc

|   Fc |   engines |   cycles |   rmse |   bias |
|-----:|----------:|---------:|-------:|-------:|
|    1 |         1 |       76 |   1.65 |  -1.64 |
|    2 |         1 |       67 |   7.33 |   7.33 |
|    3 |         1 |       59 |  15.33 |  15.33 |

## Worst engines

|                                |   engines |   cycles |   rmse |   bias |
|:-------------------------------|----------:|---------:|-------:|-------:|
| ('DS02-006', 11, 'HPT+LPT', 3) |         1 |       59 |  15.33 |  15.33 |
| ('DS02-006', 15, 'HPT+LPT', 2) |         1 |       67 |   7.33 |   7.33 |
| ('DS02-006', 14, 'HPT+LPT', 1) |         1 |       76 |   1.65 |  -1.64 |

![trajectories](trajectories.png)
