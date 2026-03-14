# GPT Lab Notebook: TDG mathlib

## 2026-03-14

### Reset and supervision

- Moved the full Minimax-generated baseline into `minimax_agent_run/` so the new implementation can be audited independently.
- Kept the paper PDF, the execution plan, and the supervised audit report at project root.
- Main lesson from the failed run: do not allow stage 2 or 3 to outrun stage 1 semantics. The graph representation must stay conservative and witness-preserving even if that reduces recall.

### Stage 0 schema findings

- Confirmed primary inputs are under `E:\LEAN-experiments\00_experiment1\jsons`.
- `traced_theorems_unified_v2.jsonl` provides theorem-level tactic traces with:
  - theorem metadata,
  - proof text,
  - per-tactic before/after states,
  - resolved premise references,
  - basic context.
- First live schema probe showed tactic records contain:
  - `index`
  - `tactic`
  - `annotated_tactic`
  - `state_before`
  - `state_after`
  - `context`
  - `premises`
  - `is_terminal`
  - `num_goals_before`
  - `num_goals_after`
- Multi-goal traces use visible `case ...` blocks. That gives a workable parser anchor for branch-aware state splitting.

### Stage 1 design choices

- Parse each proof state into explicit goal blocks.
- Treat the first visible goal as the active branch for the current tactic.
- Carry sibling goals forward only when they match exactly by `(case_label, normalized_target)`.
- Use explicit local-name references from tactic text for `hyp_to_goal` edges.
- Keep `premise_use` as annotations attached to tactic nodes via edges from theorem-local premise source ids.
- Add theorem-local `in` and `out` special nodes to preserve TDG entry/exit structure.

### Meta adjustment to plan

- The implementation order is now stricter than the original document:
  1. stage 0 audit
  2. conservative stage 1 TDGs
  3. stage 1 validation and figures
  4. only then decide whether stage 2 is safe
- This is a deliberate correction based on the earlier failure mode.

### Stage 0 results

- Audit outputs written:
  - `data/00_corpus_schema_summary.json`
  - `data/00_sample_theorem_records.jsonl`
  - `reports/00_data_audit.md`
- Current parser recovers `state_before` and `state_after` for all traced tactic steps once `no goals` is treated as the terminal state marker.
- About 21.6% of tactic proofs contain at least one multi-goal step, so branch handling is not optional.
- No local matching replay environment was found yet:
  - no `Mathlib/` checkout in the expected project root,
  - no `lean-toolchain`,
  - no `lake-manifest.json`.

### Stage 1 results

- Built TDGs for 54,473 tactic proofs.
- Artifact sizes:
  - 276,014 tactic nodes
  - 384,960 total nodes including theorem-local `in/out`
  - 1,238,292 edges
- Edge breakdown:
  - `goal_to_goal`: 386,579
  - `hyp_to_goal`: 200,844
  - `premise_use`: 650,869
- Branching steps detected: 16,513.
- Validation status:
  - current validation script is a structural gate, not semantic proof of correctness,
  - it confirms state parseability and active-goal lineage consistency on the sampled theorem set,
  - deeper manual semantic review still needs focused theorem-level spot checks.

### Stage 1 figure outputs

- Generated SVG bundles under:
  - `figs/stage1_single_proof_examples/`
  - `figs/stage1_pair_examples/`
  - `figs/stage1_refactoring_triptychs/`
  - `figs/stage1_corpus_summary/`
- Since Graphviz is unavailable in this environment, layouts use deterministic topological left-to-right placement through `networkx` + `matplotlib`.

### Stage 2 results

- Implemented a witness-preserving miner over tactic-only TDGs.
- Current search space is intentionally restricted to directed path motifs of length 2-4 nodes.
- Outputs written:
  - `data/stage2_isomorphic_candidates.parquet`
  - `data/stage2_isomorphic_witnesses.parquet`
  - `data/stage2_validation_samples.jsonl`
  - `reports/stage2_embedding_mining.md`
  - `reports/stage2_manual_embedding_validation.md`
- Totals:
  - 34,642 candidates
  - 1,170,749 explicit witnesses
- Top motifs are plausible and align with expectations from the paper and the earlier baseline:
  - `rw -> exact`
  - `have -> rw`
  - `refine -> rw`
  - `rw -> simp`
  - `ext -> simp`
- Important restraint:
  - this is a valid witness-preserving embedding stage,
  - but it is still only a path-motif approximation to the paper's broader subgraph grammar search.

### Stage 3 results

- Implemented a witness-level collapsibility filter.
- Checks now use concrete `(candidate, witness, host graph)` triples instead of index-aligned guesses.
- Outputs written:
  - `data/stage3_collapsible_candidates.parquet`
  - `data/stage3_collapsible_witnesses.parquet`
  - `data/stage3_validation_samples.jsonl`
  - `reports/stage3_collapsibility.md`
  - `reports/stage3_manual_collapsibility_validation.md`
- Totals:
  - 34,642 candidates checked
  - 1,170,749 witnesses checked
  - 23,822 candidates with at least one collapsible witness
  - witness-level collapsibility rate about 46.95%
- Main rejection reasons:
  - `missing_internal_edge`
  - `intermediate_path_violation`
- Interpretation:
  - the filter is doing useful work and is not trivially accepting everything,
  - but many accepted motifs are still very small proof idioms rather than substantial learned tactics.

### Current assessment

- This run is materially better than the prior Minimax attempt because:
  - stage 1 is conservative and provenance-preserving,
  - stage 2 stores explicit witness maps,
  - stage 3 evaluates concrete witnesses.
- The main remaining limitation is representational breadth:
  - stage 2 currently mines paths, not general connected TDG subgraphs,
  - so the discovered library candidates are still biased toward short motifs.
- Therefore stage 4 tactic extraction is not yet the right next step for all candidates.
- Better next step:
  - expand stage 2 from paths to small connected labeled subgraphs while preserving witness mappings,
  - then re-run stage 3 before any Lean-facing refactoring attempt.

## 2026-03-14 follow-up: TDG construction correction

The earlier stage-1 builder still had a conceptual gap relative to the paper:

- it used proof states,
- but it did not explicitly construct each tactic application as a map from actual proof-state inputs to actual outputs.

After re-reading the paper sections on proof states, tactic applications, and TDG edges, I replaced the builder with a more faithful Lean adaptation.

### What changed

- Each theorem now gets explicit proof objects:
  - goal objects,
  - hypothesis objects,
  - premise objects.
- For each tactic application, the builder records:
  - actual input goal,
  - actual input hypotheses referenced in the tactic text and present in the active goal context,
  - actual input premises,
  - actual output goals,
  - actual output hypotheses introduced by the tactic.
- TDG edges are now induced by proof-object flow:
  - producer of consumed goal -> tactic node,
  - producer of consumed hypothesis -> tactic node,
  - `in` -> tactic node for theorem-external premise objects.

### Why this is closer to the paper

This matches the paper's central construction idea:

- tactics consume specific proof elements from the current proof state,
- tactics produce specific new proof elements,
- and TDG edges represent that object-level dependency, not mere syntactic adjacency.

### Lean-specific complication discovered during implementation

Some Lean traces flatten nested `by` blocks, so the trace can contain both:

- an outer tactic like `have ... := by ...`,
- and later the internal body tactics of that `by` block.

That breaks a naive single-thread proof-state simulation. The new builder handles this by:

- matching tactic inputs against currently live proof objects when possible,
- and resynchronizing nested subproof segments when a tactic's `state_before` does not match the visible outer open-goal frontier.

This is still an approximation, but it is much more faithful than the previous stage-1 graph.

### Concrete check

For `LinearRecurrence.eq_mk_of_is_sol_of_eq_init`, the corrected builder now records:

- `split_ifs` consuming one goal object and producing:
  - two goal objects (`pos`, `neg`)
  - two distinct hypothesis objects for the branch-local `h'`
- the following `exact` consuming:
  - the `pos` goal object
  - explicit hypothesis objects `heq`, `n`, and branch-local `h'`
- the nested `rw` inside the `have := by ...` body producing two separate output goal objects rather than one merged malformed goal.

This is the level of TDG construction the downstream stages should use.
