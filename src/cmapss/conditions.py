"""Operating-condition normalisation for the multi-condition subsets (FD002, FD004).

In FD002/FD004 every row is flown at one of six discrete operating conditions, and sensor
readings move far more with the condition than with degradation. Without removing that, a
model mostly learns "which condition is this row" and the degradation trend is buried.

Approach (standard in the literature): cluster rows on the three settings, then z-score each
sensor within its condition using *train* statistics only. On single-condition subsets this
reduces to an ordinary global z-score.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from cmapss.data import SENSOR_COLS, SETTING_COLS

# The settings sit on a few discrete values with ~0.003 noise; this rounding collapses the
# noise without merging distinct conditions (checked: 1 group on FD001/3, 6 on FD002/4).
_ROUND = {"op1": 0, "op2": 2, "op3": 0}


class ConditionNormalizer:
    """Fit on train, apply to train and test. Raises if test rows fall outside train's
    conditions, because then per-condition stats don't exist for them."""

    def fit(self, train: pd.DataFrame) -> "ConditionNormalizer":
        self.n_conditions = len(train[SETTING_COLS].round(_ROUND).drop_duplicates())
        X = train[SETTING_COLS].to_numpy()
        self._scale = X.std(axis=0) + 1e-9
        self.km = KMeans(self.n_conditions, n_init=10, random_state=0).fit(X / self._scale)
        cond = self.km.labels_
        # Max distance to centroid on train defines what "belongs to a condition" means.
        self._max_dist = self._dist(X).max()
        g = train[SENSOR_COLS].groupby(cond)
        self.mean, self.std = g.mean(), g.std()
        return self

    def _dist(self, X: np.ndarray) -> np.ndarray:
        return self.km.transform(X / self._scale).min(axis=1)

    def condition(self, df: pd.DataFrame) -> np.ndarray:
        X = df[SETTING_COLS].to_numpy()
        far = self._dist(X) > 2 * self._max_dist + 1e-6
        if far.any():
            raise ValueError(f"{far.sum()} rows are not near any training operating condition")
        return self.km.predict(X / self._scale)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        cond = self.condition(df)
        mu = self.mean.loc[cond].to_numpy()
        sd = self.std.loc[cond].to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            z = (df[SENSOR_COLS].to_numpy() - mu) / sd
        # A sensor that is constant within a condition carries no information there.
        out[SENSOR_COLS] = np.where(sd > 0, z, 0.0)
        out["condition"] = cond
        return out


def informative_sensors_by_condition(
    train: pd.DataFrame, cond: np.ndarray, min_unique: int = 3
) -> list[str]:
    """A sensor is informative if it takes >= min_unique distinct raw values within the
    typical (median) condition. Same rule as `features.informative_sensors` on FD001/3, but
    not fooled by sensors that only vary *between* conditions."""
    nunique = train[SENSOR_COLS].groupby(cond).nunique().median()
    return [c for c in SENSOR_COLS if nunique[c] >= min_unique]
