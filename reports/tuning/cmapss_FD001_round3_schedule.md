# Tuning cmapss FD001 (3-fold engine CV, train set only)

| config         |   rmse_all |   rmse_all_sd |   rmse_trunc |   best_epoch |   train_rmse |
|:---------------|-----------:|--------------:|-------------:|-------------:|-------------:|
| REF_xgboost    |      12.16 |          1.03 |        13.71 |       nan    |       nan    |
| D_gru_e30_b512 |      12.67 |          0.67 |        13.55 |        10.67 |         8.96 |
| D_gru_e30      |      13.07 |          1.69 |        13.97 |         8.67 |         8.74 |

Configs:

```json
{
  "D_gru_e30": {
    "arch": "gru",
    "lr": 0.001,
    "warmup": 2,
    "cosine": true,
    "epochs": 30,
    "patience": 0
  },
  "D_gru_e30_b512": {
    "arch": "gru",
    "lr": 0.002,
    "warmup": 2,
    "cosine": true,
    "epochs": 30,
    "patience": 0,
    "batch": 512
  }
}
```
