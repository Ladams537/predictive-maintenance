# FD003 baselines (RUL cap 125)

Test metrics on the last observed cycle of each engine. `rmse` is vs capped truth (the convention in most papers); `rmse_raw_truth` is vs the uncapped labels; `rmse_rul_le_cap` uses only engines whose true RUL <= cap, where the capping convention makes no difference -- the most protocol-robust number here. `cv_rmse_mean` is 5-fold GroupKFold-by-engine on train -- use it, not test, for model selection.

| model               |   rmse |    mae |   phm08_score |   mean_bias |   rmse_raw_truth |   rmse_rul_le_cap |   std_ratio |   cv_rmse_mean |   cv_rmse_std |
|:--------------------|-------:|-------:|--------------:|------------:|-----------------:|------------------:|------------:|---------------:|--------------:|
| floor_mean          | 43.7   | 36.443 |       57686.9 |      19.383 |           45.07  |            45.471 |       0     |        nan     |       nan     |
| floor_lifetime      | 46.118 | 34.438 |      103388   |       6.706 |           47.225 |            44.443 |       1.229 |        nan     |       nan     |
| floor_noise_xgboost | 43.953 | 37.108 |       56419.6 |      18.528 |           45.362 |            45.633 |       0.142 |        nan     |       nan     |
| linear              | 18.102 | 14.159 |         758.9 |       5.289 |           19.635 |            18.501 |       0.925 |         19.245 |         1.217 |
| xgboost             | 12.116 |  8.614 |         238.9 |       1.33  |           13.954 |            11.471 |       0.97  |         11.327 |         1.335 |

## Sanity checks

```json
{
  "trajectory_overlap": {
    "shared_unit_ids": 100,
    "identical_sensor_rows": 0,
    "test_rows": 16596,
    "verdict": "OK"
  },
  "operating_conditions": 1,
  "informative_sensors": [
    "s2",
    "s3",
    "s4",
    "s6",
    "s7",
    "s8",
    "s9",
    "s10",
    "s11",
    "s12",
    "s13",
    "s14",
    "s15",
    "s17",
    "s20",
    "s21"
  ],
  "n_train_units": 100,
  "n_test_units": 100,
  "window": 30
}
```

## Published FD003 reference (RMSE)

|                          |   RMSE |
|:-------------------------|-------:|
| CNN (Babu et al. 2016)   |  19.82 |
| LSTM (Zheng et al. 2017) |  16.18 |
| DCNN (Li et al. 2018)    |  12.64 |
