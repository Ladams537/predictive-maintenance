# FD002 baselines (RUL cap 125)

Test metrics on the last observed cycle of each engine. `rmse` is vs capped truth (the convention in most papers); `rmse_raw_truth` is vs the uncapped labels; `rmse_rul_le_cap` uses only engines whose true RUL <= cap, where the capping convention makes no difference -- the most protocol-robust number here. `cv_rmse_mean` is 5-fold GroupKFold-by-engine on train -- use it, not test, for model selection.

| model               |   rmse |    mae |   phm08_score |   mean_bias |   rmse_raw_truth |   rmse_rul_le_cap |   std_ratio |   cv_rmse_mean |   cv_rmse_std |
|:--------------------|-------:|-------:|--------------:|------------:|-----------------:|------------------:|------------:|---------------:|--------------:|
| floor_mean          | 44.929 | 38.142 |      115590   |      13.222 |           54.083 |            46.679 |       0     |        nan     |       nan     |
| floor_lifetime      | 34.218 | 25.418 |       21565   |      -0.748 |           40.31  |            37.521 |       1.055 |        nan     |       nan     |
| floor_noise_xgboost | 44.988 | 38.006 |      126777   |      13.188 |           54.107 |            46.864 |       0.077 |        nan     |       nan     |
| linear              | 18.445 | 15.329 |        1525.6 |       0.479 |           30.6   |            18.143 |       0.833 |         20.389 |         0.734 |
| xgboost             | 12.698 |  9.107 |         686.6 |      -0.39  |           25.375 |            12.894 |       0.972 |         14.225 |         0.864 |

## Sanity checks

```json
{
  "trajectory_overlap": {
    "shared_unit_ids": 259,
    "identical_sensor_rows": 0,
    "test_rows": 33991,
    "verdict": "OK"
  },
  "operating_conditions": 6,
  "informative_sensors": [
    "s2",
    "s3",
    "s4",
    "s7",
    "s8",
    "s9",
    "s11",
    "s12",
    "s13",
    "s14",
    "s15",
    "s17",
    "s20",
    "s21"
  ],
  "n_train_units": 260,
  "n_test_units": 259,
  "window": 30
}
```

## Published FD002 reference (RMSE)

|                          |   RMSE |
|:-------------------------|-------:|
| CNN (Babu et al. 2016)   |  30.29 |
| LSTM (Zheng et al. 2017) |  24.49 |
| DCNN (Li et al. 2018)    |  22.36 |
