"""Evaluation metrics. All functions take (y_true, y_pred) in cycles."""

import numpy as np
from scipy import stats


def rmse(y_true, y_pred) -> float:
    d = np.asarray(y_pred, float) - np.asarray(y_true, float)
    return float(np.sqrt(np.mean(d**2)))


def mae(y_true, y_pred) -> float:
    return float(np.mean(np.abs(np.asarray(y_pred, float) - np.asarray(y_true, float))))


def phm08_score(y_true, y_pred) -> float:
    """PHM08 challenge score (Saxena et al. 2008). Lower is better.

    Asymmetric: late predictions (pred > true, i.e. we think the engine has more life than it
    does) are penalised more heavily than early ones, because they are the dangerous error.
    It is a *sum*, so it scales with the number of test units -- only compare within a subset.
    """
    d = np.asarray(y_pred, float) - np.asarray(y_true, float)
    return float(np.sum(np.where(d < 0, np.exp(-d / 13.0) - 1, np.exp(d / 10.0) - 1)))


def quantiles(y: np.ndarray, qs=(0.05, 0.25, 0.5, 0.75, 0.95)) -> dict[str, float]:
    return {str(q): round(float(np.quantile(y, q)), 1) for q in qs}


def distribution_check(y_true, y_pred) -> dict:
    """Does the prediction distribution look like the truth distribution?

    A model can get a decent RMSE by predicting a narrow band around the mean. These numbers
    expose that: std_ratio << 1 or a large KS statistic means predictions are collapsed.
    """
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    ks = stats.ks_2samp(y_true, y_pred)
    return {
        "true_quantiles": quantiles(y_true),
        "pred_quantiles": quantiles(y_pred),
        "true_range": [float(y_true.min()), float(y_true.max())],
        "pred_range": [round(float(y_pred.min()), 1), round(float(y_pred.max()), 1)],
        "std_ratio": round(float(y_pred.std() / y_true.std()), 3),
        "ks_stat": round(float(ks.statistic), 3),
        "ks_pvalue": round(float(ks.pvalue), 4),
    }


def summarize(y_true, y_pred) -> dict:
    return {
        "rmse": round(rmse(y_true, y_pred), 3),
        "mae": round(mae(y_true, y_pred), 3),
        "phm08_score": round(phm08_score(y_true, y_pred), 1),
        "mean_bias": round(float(np.mean(np.asarray(y_pred) - np.asarray(y_true))), 3),
    }
