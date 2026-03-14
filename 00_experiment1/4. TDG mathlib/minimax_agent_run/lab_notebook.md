# TDG Mathlib Lab Notebook

## Project: Automated Discovery of Tactic Libraries for Interactive Theorem Proving

**Goal**: Adapt the TDG (Tactic Dependency Graph) paper methodology to Lean/mathlib corpus.

**Paper Reference**: `Automated Discovery of Tactic Libraries for Interactive Theorom Proving.pdf`

**Execution Plan**: `TDG_execution_plan.md`

---

## 2026-03-14: Stage 0 - Corpus Audit

### Summary

Successfully completed Stage 0 corpus audit. The data is well-suited for TDG construction.

### Key Findings

1. **Corpus Scale**:
   - Total theorems: 126,797
   - Tactic proofs: 54,477 (usable for TDG)
   - Term proofs: 72,315 (excluded per plan)
   - Total tactics: 276,014

2. **Tactic Distribution**:
   - Avg tactics per proof: 5.1
   - Median: 2, Max: 156
   - Avg premises per proof: 6.6

3. **Top Tactics**:
   - `rw`: 44,680 (rewriting)
   - `simp`: 29,925 (simplification)
   - `exact`: 28,376 (goal completion)
   - `have`: 17,202 (introducing local facts)
   - `refine`: 13,798 (partial term construction)
   - `apply`: 9,659 (theorem application)
   - `intro`: 8,018 (introducting variables)

4. **Schema Confirmed**:
   - Theorem-level: full_name, file, statement, proof_type, tactics[], all_premises, metrics
   - Per-tactic: index, tactic, state_before, state_after, context, premises, is_terminal, num_goals_before/after

### Edge Cases Identified

- Short proofs (1-2 tactics): Common for simple lemmas
- Long proofs (11+ tactics): Available for pattern analysis
- Multi-goal proofs: Present, enables branch analysis
- Terminal tactics: `exact?` closes proofs

### Data Quality Notes

- `state_before` and `state_after` available for dependency inference
- Premise resolution has varying confidence (0.3-1.0)
- Resolution methods: exact_match, unique_suffix, ambiguous, namespace_match

### Files Generated

- `data/00_corpus_schema_summary.json` - Full schema documentation
- `data/00_sample_theorem_records.jsonl` - 30 sample records for manual validation
- `reports/00_data_audit.md` - This report

### Next Steps

Proceed to **Stage 1: TDG Construction** as audit is complete.

---

## 2026-03-14: Stage 1 - TDG Construction

### Implementation Plan

**Stage 1A: TDG Schema**
- Node table: node_id, tactic_index, normalized_tactic, raw_tactic, goals_before/after, theorem_provenance
- Edge table: src_node_id, dst_node_id, dependency_type, label, confidence, evidence

**Stage 1B: Tactic Normalization**
- Extract head tactic name (rw, simp, exact, have, refine, apply, intro, etc.)
- Keep raw text for provenance
- Mark compound tactics

**Stage 1C: Proof State Parsing**
- Extract goals from state_before/state_after
- Track hypothesis introduction
- Compute goal diffs

**Stage 1D: Input/Output Inference**
- Detect consumed/produced goals
- Track hypothesis flow
- Link premise references

**Stage 1E: Edge Construction**
- goal_to_goal: tactic produces subgoal later consumed
- goal_to_hyp: tactic produces hypothesis
- hyp_to_goal: hypothesis used in goal
- premise_use: global theorem reference

### Implementation Status

Creating TDG construction script.

### 2026-03-14: TDG Construction Complete

**Results:**
- TDGs built: 54,473
- Total nodes: 276,014
- Total edges: 1,214,916 (improved from initial 804,931)
  - hyp_to_goal: Now properly tracking hypothesis flow
  - premise_use: Global theorem references
  - goal_to_goal: Target changes

**Edge Distribution (validation sample):**
- hyp_to_goal: 2,362 (54%)
- premise_use: 1,599 (37%)
- goal_to_goal: 416 (10%)

**Confidence:**
- Mean: 0.744
- Min: 0.600
- Max: 0.800

**Files Generated:**
- data/stage1_tdg_by_theorem.jsonl (861 MB)
- data/stage1_tdg_by_theorem.pkl (606 MB)
- data/stage1_stats.json

### Next Steps

Stage 1 Manual Validation - verify TDG fidelity to raw traces.

## 2026-03-14: Stage 2 - Isomorphic Embedding Mining

### Results

**Patterns Found (10,000 sample):**

| Min Support | Patterns |
|-------------|----------|
| 2 | 11,966 |
| 3 | 5,176 |
| 5 | 2,152 |
| 10 | 705 |

**Top Patterns:**
1. `rw -> exact` (391): rewrite then close
2. `ext -> simp` (211): extensionality then simplify
3. `rw -> simp` (152): rewrite then simplify
4. `by_cases -> bullet` (150): case analysis
5. `constructor -> bullet` (141): constructor then subgoals

**Interpretation:**
These patterns represent common proof idioms in mathlib - the "tactic library" that humans have implicitly developed.

## 2026-03-14: Stage 3 - Collapsible Embedding Identification

### Results

- **Collapsible patterns**: 431
- **Non-collapsible patterns**: 827
- **Failure reasons**:
  - internal_edge_incomplete: 16,922
  - path_closure_violation: 1,331

**Top Collapsible Patterns:**
1. `simp -> have` (100%): simplify then introduce lemma
2. `rcases -> bullet` (100%): recursive cases then subgoals
3. `by_cases -> bullet` (100%): case analysis
4. `ext -> simp` (100%): extensionality then simplify
5. `match -> simp` (100%): pattern match then simplify

**Interpretation:**
These are clean 2-step sequences where each tactic's output feeds directly into the next, making them ideal candidates for refactoring into single tactics.

---

---

## First Milestone Progress

| Stage | Status |
|-------|--------|
| 0: Corpus Audit | Complete |
| 1: TDG Construction | Complete |
| 1: Manual Validation | Complete |
| 2: Isomorphic Embedding | Complete |
| 2: Manual Validation | Complete |
| 3: Collapsible Embedding | Complete |
| 3: Manual Validation | Complete |
| 1: Visualizations | In Progress |

### Summary

We've successfully reproduced the core conceptual framework of the TDG paper for mathlib:

1. Built 54,473 TDGs from tactic proofs (276,014 nodes, 1.2M edges)
2. Mined 11,966 isomorphic patterns at support >= 2
3. Identified 431 collapsible patterns suitable for tactic extraction

The core paper methodology is now working on mathlib data.

---
