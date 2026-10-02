# N-CMAPSS DS02 baselines

Train: 6 dev engines; test: 3 engines, 202 cycles. Uncapped RUL, every test cycle scored. CV = 5-fold GroupKFold by engine on dev.

| model               |   rmse |    mae |   phm08_score |   mean_bias |   std_ratio |   cv_rmse_mean |   cv_rmse_std |
|:--------------------|-------:|-------:|--------------:|------------:|------------:|---------------:|--------------:|
| floor_mean          | 20.381 | 17.433 |        1468.7 |       3.684 |       0     |        nan     |       nan     |
| floor_lifetime      |  9.356 |  7.526 |         297.1 |       6.295 |       0.999 |        nan     |       nan     |
| floor_noise_xgboost | 22.288 | 18.795 |        1937.2 |       3.432 |       0.428 |        nan     |       nan     |
| linear              | 10.698 |  8.639 |         527.6 |       7.974 |       1.038 |          9.439 |         2.364 |
| xgboost             |  6.424 |  4.71  |         151.6 |       2.561 |       1.015 |          6.762 |         2.037 |
