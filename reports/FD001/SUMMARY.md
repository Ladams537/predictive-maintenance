# FD001 baselines (RUL cap 125)

Test metrics on the last observed cycle of each engine. `rmse` is vs capped truth (the convention in most papers); `rmse_raw_truth` is vs the uncapped labels. `cv_rmse_mean` is 5-fold GroupKFold-by-engine on train -- use it, not test, for model selection.

| model               |   rmse |    mae |   phm08_score |   mean_bias |   rmse_raw_truth |   std_ratio |   cv_rmse_mean |   cv_rmse_std |
|:--------------------|-------:|-------:|--------------:|------------:|-----------------:|------------:|---------------:|--------------:|
| floor_mean          | 41.942 | 34.83  |       33354.5 |      12.379 |           43.067 |       0     |        nan     |       nan     |
| floor_lifetime      | 36.084 | 26.943 |       21032.4 |      -2.22  |           36.793 |       1.035 |        nan     |       nan     |
| floor_noise_xgboost | 42.28  | 35.267 |       36269.4 |      12.82  |           43.34  |       0.108 |        nan     |       nan     |
| linear              | 18.168 | 14.407 |         553.5 |       1.326 |           19.467 |       0.827 |         18.658 |         1.633 |
| xgboost             | 12.17  |  8.517 |         221.3 |       0.731 |           13.446 |       0.995 |         12.01  |         1.514 |

## Sanity checks

```json
{
  "trajectory_overlap": {
    "shared_unit_ids": 100,
    "identical_sensor_rows": 0,
    "test_rows": 13096,
    "verdict": "OK"
  },
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
  "n_train_units": 100,
  "n_test_units": 100,
  "window": 30
}
```

## Published FD001 reference (RMSE)

|                                          | RMSE   |
|:-----------------------------------------|:-------|
| CNN (Babu et al. 2016)                   | 18.45  |
| LSTM (Zheng et al. 2017)                 | 16.14  |
| DCNN (Li et al. 2018)                    | 12.61  |
| SOTA band (Transformer/attention, 2021+) | ~11-12 |
