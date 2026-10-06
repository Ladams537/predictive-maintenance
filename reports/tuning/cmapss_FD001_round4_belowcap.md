# Tuning cmapss FD001 (3-fold engine CV, train set only)

| config      |   rmse_all |   rmse_all_sd |   rmse_trunc |   rmse_below_cap |   best_epoch |   train_rmse |
|:------------|-----------:|--------------:|-------------:|-----------------:|-------------:|-------------:|
| REF_xgboost |      12.16 |          1.03 |        13.71 |            13.2  |       nan    |       nan    |
| D_gru       |      12.26 |          1.2  |        13.54 |            13.89 |        11.67 |         6.33 |

Configs:

```json
{
  "D_gru": {
    "arch": "gru",
    "lr": 0.001,
    "warmup": 2,
    "cosine": true,
    "epochs": 60,
    "patience": 0
  }
}
```
