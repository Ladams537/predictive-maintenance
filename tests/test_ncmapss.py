"""N-CMAPSS: integrity and ground-truth derivation. Skipped if the data isn't downloaded."""

import numpy as np
import pytest

from cmapss import ncmapss
from cmapss.ncmapss_download import verify

pytestmark = pytest.mark.skipif(
    bool(verify()), reason="N-CMAPSS not present; run python -m cmapss.ncmapss_download"
)


@pytest.fixture(scope="module")
def ground_truth():
    return ncmapss.fault_ground_truth()


def test_ds02_matches_paper_table5(ground_truth):
    """Arias Chao et al., Table 5: units, end-of-life cycle and failure mode for DS02."""
    expected = {
        2: (75, "HPT"),
        5: (89, "HPT"),
        10: (82, "HPT"),
        16: (63, "HPT+LPT"),
        18: (71, "HPT+LPT"),
        20: (66, "HPT+LPT"),
        11: (59, "HPT+LPT"),
        14: (76, "HPT+LPT"),
        15: (67, "HPT+LPT"),
    }
    ds02 = ground_truth[ground_truth.subset == "DS02-006"].set_index("unit")
    got = {u: (r.eol_cycle, r.components) for u, r in ds02.iterrows()}
    assert got == expected


def test_degradation_is_unambiguous(ground_truth):
    """Untouched health parameters change by exactly zero, and every real degradation clears
    DEGRADED_TOL with margin, so the component labels don't hinge on where the tolerance sits."""
    deltas = ground_truth.filter(like="delta_").abs().to_numpy().ravel()
    nonzero = deltas[deltas > 0]
    assert nonzero.min() > 1.4 * ncmapss.DEGRADED_TOL, nonzero.min()
    assert (ground_truth.components.notna() & (ground_truth.components != "")).all()


def test_units_unique_within_subset(ground_truth):
    assert not ground_truth.duplicated(["subset", "unit"]).any()


def test_rul_and_health_state():
    df = ncmapss.load("DS02-006", "dev", groups=("A", "Y"), every=7)
    full = ncmapss.load("DS02-006", "dev", groups=("A",))
    last = full.groupby("unit").cycle.max()
    np.testing.assert_array_equal(df.rul, df.unit.map(last) - df.cycle)
    # Once abnormal (hs=0), an engine never becomes healthy again.
    assert full.groupby("unit").hs.apply(lambda s: (s.diff().dropna() <= 0).all()).all()
