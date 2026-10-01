"""Tests that fail loudly if the data, labels or features are wrong.

These pin facts about C-MAPSS that every downstream number depends on.
"""

import numpy as np
import pandas as pd
import pytest

from cmapss import sanity
from cmapss.data import DATA_DIR, cap_rul, last_cycles, load_test, load_train
from cmapss.download import verify
from cmapss.features import feature_columns, informative_sensors, window_features
from cmapss.metrics import phm08_score, rmse

pytestmark = pytest.mark.skipif(
    bool(verify()), reason=f"C-MAPSS not present/valid at {DATA_DIR}; run python -m cmapss.download"
)

# (train units, test units, train rows, test rows). NB: the NASA readme swaps FD004 -- it
# says 248 train / 249 test, but the files (and RUL_FD004.txt) have 249 train / 248 test.
EXPECTED = {
    "FD001": (100, 100, 20631, 13096),
    "FD002": (260, 259, 53759, 33991),
    "FD003": (100, 100, 24720, 16596),
    "FD004": (249, 248, 61249, 41214),
}


@pytest.mark.parametrize("subset", EXPECTED)
def test_shapes(subset):
    tr, te = load_train(subset), load_test(subset)
    n_tr, n_te, r_tr, r_te = EXPECTED[subset]
    assert (tr.unit.nunique(), len(tr)) == (n_tr, r_tr)
    assert (te.unit.nunique(), len(te)) == (n_te, r_te)
    assert not tr.isna().any().any() and not te.isna().any().any()


@pytest.mark.parametrize("subset", EXPECTED)
def test_rul_labels(subset):
    tr, te = load_train(subset), load_test(subset)
    # Train: every unit runs to failure, RUL hits 0 exactly once, decreases by 1 per cycle.
    assert (tr.groupby("unit").rul.min() == 0).all()
    assert (tr.groupby("unit").rul.diff().dropna() == -1).all()
    # Cycles are contiguous from 1 in both splits.
    for df in (tr, te):
        assert (df.groupby("unit").cycle.min() == 1).all()
        assert (df.groupby("unit").cycle.diff().dropna() == 1).all()
    # Test last-cycle RUL equals the official RUL file.
    official = np.loadtxt(DATA_DIR / f"RUL_{subset}.txt", dtype=int)
    np.testing.assert_array_equal(last_cycles(te).rul.to_numpy(), official)


def test_cap():
    np.testing.assert_array_equal(cap_rul([0, 100, 200], 125), [0, 100, 125])
    np.testing.assert_array_equal(cap_rul([0, 200], None), [0, 200])


def test_fd001_sensor_selection_matches_literature():
    # The 14 sensors used by essentially every FD001 paper.
    expected = [
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
        "s21",
    ]
    assert informative_sensors(load_train("FD001")) == expected


def test_no_lookahead():
    """Features at cycle t must not change when cycles > t are removed."""
    tr = load_train("FD001")
    sensors = informative_sensors(tr)
    cols = feature_columns(sensors)
    full = window_features(tr, sensors)[cols]
    truncated = tr[tr.cycle <= 50].copy()
    trunc_feats = window_features(truncated, sensors)[cols]
    pd.testing.assert_frame_equal(full.loc[truncated.index], trunc_feats, check_exact=False)


def test_features_isolated_per_unit():
    """Features for one unit must not depend on other units' rows."""
    tr = load_train("FD001")
    sensors = informative_sensors(tr)
    cols = feature_columns(sensors)
    full = window_features(tr, sensors)[cols]
    alone = tr[tr.unit == 7]
    pd.testing.assert_frame_equal(full.loc[alone.index], window_features(alone, sensors)[cols])


def test_no_train_test_row_overlap():
    for subset in EXPECTED:
        res = sanity.trajectory_overlap(load_train(subset), load_test(subset))
        assert res["identical_sensor_rows"] == 0, subset


def test_unit_disjoint_guard():
    with pytest.raises(AssertionError):
        sanity.assert_units_disjoint([1, 2, 3], [3, 4])


def test_metrics():
    assert rmse([0, 0], [3, 4]) == pytest.approx(np.sqrt(12.5))
    # Late (pred > true) is penalised more than early by the same amount.
    assert phm08_score([50], [60]) > phm08_score([50], [40])
    assert phm08_score([10, 20], [10, 20]) == 0
