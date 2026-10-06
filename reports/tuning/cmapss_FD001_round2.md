# Tuning cmapss FD001 (3-fold engine CV, train set only)

| config      |   rmse_all |   rmse_all_sd |   rmse_trunc |   best_epoch |   train_rmse |
|:------------|-----------:|--------------:|-------------:|-------------:|-------------:|
| REF_xgboost |      12.16 |          1.03 |        13.71 |       nan    |       nan    |
| D_gru       |      12.26 |          1.2  |        13.54 |        11.67 |         6.33 |
| E_gru_reg   |      12.98 |          1.56 |        13.42 |         7.33 |         8.23 |
| F_gru_d32   |      13.74 |          0.58 |        14.78 |        11.67 |         7.31 |
| H_tr_heavy  |      14.55 |          1.58 |        15.12 |        29    |        16.99 |
| G_tr_reg    |      15.87 |          2.29 |        16.24 |        16    |        10.6  |

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
  },
  "E_gru_reg": {
    "arch": "gru",
    "lr": 0.001,
    "warmup": 2,
    "cosine": true,
    "epochs": 60,
    "patience": 0,
    "dropout": 0.3,
    "weight_decay": 0.01,
    "input_noise": 0.1
  },
  "F_gru_d32": {
    "arch": "gru",
    "d_model": 32,
    "lr": 0.001,
    "warmup": 2,
    "cosine": true,
    "epochs": 60,
    "patience": 0
  },
  "G_tr_reg": {
    "d_model": 32,
    "n_layers": 1,
    "dropout": 0.3,
    "weight_decay": 0.1,
    "lr": 0.0005,
    "warmup": 3,
    "cosine": true,
    "epochs": 60,
    "patience": 0,
    "input_noise": 0.1
  },
  "H_tr_heavy": {
    "d_model": 32,
    "n_layers": 2,
    "dropout": 0.5,
    "weight_decay": 0.3,
    "lr": 0.0003,
    "warmup": 3,
    "cosine": true,
    "epochs": 60,
    "patience": 0,
    "input_noise": 0.3
  }
}
```
