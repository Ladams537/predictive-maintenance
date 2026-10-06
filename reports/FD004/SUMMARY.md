# FD004 baselines (RUL cap 125)

Test metrics on the last observed cycle of each engine. `rmse` is vs capped truth (the convention in most papers); `rmse_raw_truth` is vs the uncapped labels; `rmse_rul_le_cap` uses only engines whose true RUL <= cap, where the capping convention makes no difference -- the most protocol-robust number here. `cv_rmse_mean` is 5-fold GroupKFold-by-engine on train -- use it, not test, for model selection.

| model               |   rmse |    mae |   phm08_score |   mean_bias |   rmse_raw_truth |   rmse_rul_le_cap |   std_ratio |   cv_rmse_mean |   cv_rmse_std |
|:--------------------|-------:|-------:|--------------:|------------:|-----------------:|------------------:|------------:|---------------:|--------------:|
| floor_mean          | 45.565 | 38.059 |      164681   |      15.126 |           54.902 |            49.652 |       0     |        nan     |       nan     |
| floor_lifetime      | 52.658 | 38.726 |      569516   |      -1.171 |           59.054 |            55.11  |       1.152 |        nan     |       nan     |
| floor_noise_xgboost | 45.247 | 37.763 |      158385   |      14.669 |           54.661 |            49.233 |       0.077 |        nan     |       nan     |
| linear              | 21.931 | 17.252 |        2871.5 |       2.755 |           32.992 |            22.022 |       0.791 |         20.363 |         1.052 |
| xgboost             | 13.844 |  9.399 |         960.1 |       0.703 |           26.185 |            14.072 |       0.951 |         13.384 |         1.014 |

## Sanity checks

```json
{
  "trajectory_overlap": {
    "shared_unit_ids": 248,
    "identical_sensor_rows": 0,
    "test_rows": 41214,
    "verdict": "OK"
  },
  "operating_conditions": 6,
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
  "n_train_units": 249,
  "n_test_units": 248,
  "window": 30
}
```

## Published FD004 reference (RMSE)

|                          |   RMSE |
|:-------------------------|-------:|
| CNN (Babu et al. 2016)   |  29.16 |
| LSTM (Zheng et al. 2017) |  28.17 |
| DCNN (Li et al. 2018)    |  23.31 |
