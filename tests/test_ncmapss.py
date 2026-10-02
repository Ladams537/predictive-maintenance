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


def test_healthy_model_is_cross_fitted(monkeypatch):
    """No engine's residuals may come from a healthy model that was fit on that engine, and
    test engines must never be in any healthy-model fit."""
    import pandas as pd

    from cmapss import ncmapss_features as nf

    rng = np.random.default_rng(0)
    rows = []
    for engine in range(12):
        split = "test" if engine >= 9 else "dev"
        for cycle in range(1, 16):
            w = rng.normal(size=(20, len(nf.OPS)))
            df = pd.DataFrame(w, columns=nf.OPS)
            for j, s in enumerate(nf.SENSORS):
                df[s] = w.sum(1) * (j + 1) + 0.01 * cycle
            rows.append(df.assign(engine=engine, split=split, cycle=cycle))
    df = pd.concat(rows, ignore_index=True)

    calls = []
    real = nf.fit_predict

    def spy(train, apply):
        calls.append((set(train["engine"]), set(apply["engine"])))
        return real(train, apply)

    monkeypatch.setattr(nf, "fit_predict", spy)
    monkeypatch.setattr(nf, "_healthy_model", lambda: nf.XGBRegressor(n_estimators=5))
    resid, _ = nf.residuals(df)
    test_engines = {9, 10, 11}
    assert len(calls) == nf.N_FOLDS + 1
    for fit_on, applied_to in calls:
        assert not fit_on & applied_to
        assert not fit_on & test_engines
    assert np.isfinite(resid).all()


def test_cycle_table():
    from cmapss.ncmapss_features import OUT, load_cycles

    if not OUT.exists():
        pytest.skip("run python -m cmapss.ncmapss_features first")
    c = load_cycles()
    assert c.engine.nunique() == 99
    assert not c.isna().any().any()
    g = c.groupby("engine")
    # One row per cycle, contiguous from 1, RUL = last cycle - cycle.
    assert (g.cycle.min() == 1).all() and (g.cycle.diff().dropna() == 1).all()
    np.testing.assert_array_equal(c.rul, g.cycle.transform("max") - c.cycle)
