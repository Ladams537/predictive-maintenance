# N-CMAPSS pooled baselines

Train: 60 dev engines; test: 39 engines, 2938 cycles. Uncapped RUL, every test cycle scored. CV = 5-fold GroupKFold by engine on dev.

| model               |   rmse |    mae |   phm08_score |   mean_bias |   std_ratio |   cv_rmse_mean |   cv_rmse_std |
|:--------------------|-------:|-------:|--------------:|------------:|------------:|---------------:|--------------:|
| floor_mean          | 23.427 | 19.887 |       28205   |       0.483 |       0     |        nan     |       nan     |
| floor_lifetime      | 11.895 | 10.102 |        5446.8 |      -1.285 |       0.96  |        nan     |       nan     |
| floor_noise_xgboost | 24.018 | 20.238 |       32815.5 |       0.64  |       0.227 |        nan     |       nan     |
| linear              |  9.466 |  7.649 |        3840.6 |       1.693 |       0.908 |         12.519 |         2.071 |
| xgboost             |  7.095 |  5.077 |        2308   |       0.787 |       0.963 |          8.968 |         1.015 |
