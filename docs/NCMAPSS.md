# N-CMAPSS: ground truth for the explanation evals

**Decision (2026-10-01):** C-MAPSS stays the RUL benchmark (comparable to published numbers).
N-CMAPSS (Arias Chao et al. 2021) provides the ground truth for week 4. Its `T` arrays record
the simulator's health parameters (efficiency and flow modifiers for fan, LPC, HPC, HPT, LPT)
for every sample, so for every prediction we know which component is actually degrading.
C-MAPSS has no per-engine fault labels, not even in FD003/FD004.

## Getting the data

```bash
uv run python -m cmapss.ncmapss_download     # ~5 min, streams + repacks, needs <9 GB free
uv run python -m cmapss.ncmapss ground-truth # -> reports/ncmapss/fault_ground_truth.csv
```

- The NASA archive is 15.8 GB: a zip whose only member is a deflated zip. We stream it, keep
  only the `.h5` files, check each against a pinned sha256, and repack it to float32 + gzip
  in `data/interim/` (4.6 GB for all nine, ~6x smaller). Every element of a repack is checked
  against the float32 cast of the hashed source before the raw file is deleted.
- **DS08d is corrupt upstream and excluded.** The archive's CRC matches what we extracted
  (Info-ZIP `unzip -t` OK), but the HDF5 file is internally broken: its stored EOF is 32 bytes
  past the real end, and the group index fails even when padded. It also compresses at 59%,
  against ~44% for every other file. We lose 10 mixed-fault engines; DS08a/DS08c cover that case.

## What's in it (measured from the data, not the docs)

1 Hz samples within each flight (~12k samples per flight cycle; DS02 dev alone is 5.3M rows).
Per sample: `A` (unit, cycle, flight class Fc 1–3, health state hs), `W` (alt, Mach, TRA, T2),
`X_s` (14 real sensors), `X_v` (14 virtual sensors), `T` (10 health parameters), `Y` (RUL).
RUL = unit's last cycle − cycle. `hs` goes 1→0 once at the onset of abnormal degradation.

| fault signature | subsets | engines (dev/test) | median life (cycles) |
|---|---|---|---|
| HPT | DS01, DS02 (units 2, 5, 10) | 13 (9/4) | 89 |
| HPT+LPT | DS02, DS03 | 21 (12/9) | 71 |
| fan | DS04 | 10 (6/4) | 86 |
| HPC | DS05 | 10 (6/4) | 81 |
| LPC+HPC | DS06 | 10 (6/4) | 79 |
| LPT | DS07 | 10 (6/4) | 81 |
| all five | DS08a, DS08c | 25 (15/10) | 59 |

Derived by `fault_ground_truth()` from the health parameters. It reproduces the dataset
paper's DS02 table exactly (units, end-of-life cycles, failure modes), and that is pinned
in `tests/test_ncmapss.py`. `HPT_flow` never degrades in any engine, so "HPT" always means
HPT efficiency.

## Traps the eval design has to handle

1. **Inputs vs. answers.** `T` is the answer key and `X_v` are virtual sensors you can't
   measure on a real engine. Neither may ever be a model or explainer input. The model sees
   `W` + `X_s` only.
2. **Fault type ≈ subset.** Each subset mostly holds one fault type. Any per-subset
   processing (normalisation, a model per subset) lets a model or LLM "identify" the fault
   from processing artefacts. Pool subsets and process them identically.
3. **Flight-class confound.** No fan-fault engine flies short flights (Fc=1: 0 of 10, against
   27 of 99 overall). An explanation that leans on flight profile can look right for the
   wrong reason. Check explanations cite `X_s` sensors, and stratify eval results by Fc.
4. **Severity isn't comparable across parameters.** Max end-of-life change is 0.22 for
   fan_eff and 0.018 for HPT_eff. Degradation is also a continuum (smallest real change is
   0.0014), not on/off. "Dominant component" has to be defined against each parameter's own
   scale, and for DS08 (everything degrades) the label is a ranking, not a single class.
5. **Small n.** 39 test engines in total, 4 per single-fault class. Many predictions per
   engine, but they're correlated: the engine is the unit of analysis. Report per-engine
   accuracy with confidence intervals, and consider cross-validated dev engines to grow the
   eval set (each judged by a model that didn't train on it).
6. **Train/test shift built in.** e.g. DS02 dev engines are all Fc=3 (long flights); its
   test engines are Fc 1, 2 and 3.
