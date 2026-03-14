# Stage 0 Data Audit

## Inputs

- `E:\LEAN-experiments\00_experiment1\jsons\traced_theorems_unified_v2.jsonl`
- `E:\LEAN-experiments\00_experiment1\jsons\corpus.jsonl`
- `E:\LEAN-experiments\00_experiment1\jsons\corpus_code_index.json`
- `E:\LEAN-experiments\00_experiment1\jsons\premise_index_v2.json`
- `E:\LEAN-experiments\00_experiment1\jsons\theorem_stats_v2.json`

## Summary

- Tactic-proof theorem records scanned: 54,473
- Usable tactic proofs: 54,473
- Fully parseable tactic proofs under the current state parser: 54,473 (100.00%)
- Parseable `state_before` share across tactic steps: 100.00%
- Parseable `state_after` share across tactic steps: 100.00%
- Tactic proofs with at least one multi-goal step: 21.59%

## Common tactic heads

- `rw`: 50,284
- `simp`: 34,912
- `exact`: 34,288
- `have`: 18,452
- `refine`: 15,133
- `apply`: 10,805
- `intro`: 10,702
- `simpa`: 6,764
- `obtain`: 6,648
- `rintro`: 6,539
- `rcases`: 5,373
- `ext`: 5,224
- `simp_rw`: 4,990
- `rfl`: 4,071
- `let`: 3,141

## Replay environment check

- `E:\LEAN-experiments\00_experiment1\Mathlib` exists: `False`
- `E:\LEAN-experiments\00_experiment1\mathlib4` exists: `False`
- `E:\LEAN-experiments\00_experiment1\lake-manifest.json` exists: `False`
- `E:\LEAN-experiments\00_experiment1\lean-toolchain` exists: `False`

## Interpretation

- Theorem trace coverage is sufficient to begin TDG construction from local JSONs.
- Full Lean replay is probably deferred unless a matching mathlib checkout and `lean-toolchain` are added or discovered elsewhere.
- The state parser is already strong enough for stage 1 because it recovers goals for essentially all tactic steps, including many multi-goal traces.
- The main hard cases are branch-heavy proofs, bullets, and long compound tactics, which must remain explicit in stage-1 validation.

## Manual audit sample policy

- `data/00_sample_theorem_records.jsonl` contains 25 random tactic-proof samples plus 10 edge cases.
- These should be the default manual inspection seed before accepting later stages.
