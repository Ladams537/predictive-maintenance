"""Windowing and model-interface guarantees (no data needed)."""

import numpy as np
import pandas as pd
import torch

from cmapss.model import ARCHS
from cmapss.seq import make_windows


def _frame():
    rows = []
    for unit, T in [(1, 5), (2, 3)]:
        for c in range(1, T + 1):
            rows.append({"unit": unit, "cycle": c, "f": unit * 100 + c, "y": T - c})
    return pd.DataFrame(rows).sample(frac=1, random_state=0)  # order must not matter


def test_windows_are_causal_and_per_engine():
    w = make_windows(_frame(), ["f"], "y", length=3)
    by = {(int(e), int(c)): i for i, (e, c) in enumerate(zip(w.engine, w.cycle, strict=True))}
    # Unit 1, cycle 4: cycles 2..4 of unit 1 only.
    i = by[(1, 4)]
    assert w.X[i, :, 0].tolist() == [102, 103, 104] and not w.pad[i].any()
    # Unit 2, cycle 1: right-aligned, two padding slots of zeros.
    i = by[(2, 1)]
    assert w.X[i, :, 0].tolist() == [0, 0, 201] and w.pad[i].tolist() == [True, True, False]
    # Every window contains only its own engine's values, never later cycles.
    for i in range(len(w)):
        vals = w.X[i, ~w.pad[i], 0]
        assert (vals // 100 == w.engine[i]).all() and (vals % 100 <= w.cycle[i]).all()
    assert (
        w.y
        == np.array([5 - c if e == 1 else 3 - c for e, c in zip(w.engine, w.cycle, strict=True)])
    ).all()


def test_padding_does_not_change_predictions():
    """Changing values in padded positions must not change the output (mask works)."""
    torch.manual_seed(0)
    for arch in ARCHS.values():
        m = arch(n_features=2, length=4).eval()
        x = torch.randn(3, 4, 2)
        pad = torch.tensor([[True, True, False, False]] * 3)
        x2 = x.clone()
        x2[:, :2] = 999.0
        torch.testing.assert_close(m(x, pad), m(x2, pad))
