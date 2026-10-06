# Tuning cmapss FD001 (3-fold engine CV, train set only)

| config              |   rmse_all |   rmse_all_sd |   rmse_trunc |   best_epoch |   train_rmse |
|:--------------------|-----------:|--------------:|-------------:|-------------:|-------------:|
| D_gru               |      12.26 |          1.2  |        13.44 |        11.67 |         6.33 |
| B_warmup_cosine     |      15.23 |          1.3  |        15.42 |         6    |         4.36 |
| C_B_small           |      15.25 |          2.22 |        14.88 |        19    |         6.3  |
| A_baseline_const_lr |      15.32 |          1.83 |        16.66 |         3.67 |         6.18 |

Configs:

```json
{
  "A_baseline_const_lr": {
    "epochs": 60
  },
  "B_warmup_cosine": {
    "lr": 0.0005,
    "warmup": 3,
    "cosine": true,
    "epochs": 60,
    "patience": 0,
    "weight_decay": 0.01
  },
  "C_B_small": {
    "d_model": 32,
    "lr": 0.0005,
    "warmup": 3,
    "cosine": true,
    "epochs": 60,
    "patience": 0,
    "weight_decay": 0.01
  },
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
