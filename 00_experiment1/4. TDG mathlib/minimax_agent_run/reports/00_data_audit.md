# Stage 0: Data Audit Report

## Corpus: Lean/mathlib traced theorem proofs

**Date**: 2026-03-14
**Status**: Complete

---

## 1. Primary Input Files Confirmed

| File | Size | Purpose |
|------|------|---------|
| `traced_theorems_unified_v2.jsonl` | 717 MB | Main theorem traces with tactic-level proof states |
| `corpus.jsonl` | 54 MB | Premise/declaration inventory |
| `corpus_code_index.json` | 38 MB | Code index for fast lookup |
| `premise_index_v2.json` | 18 MB | Global premise index |
| `theorem_stats_v2.json` | 860 B | Corpus summary statistics |

## 2. Schema Confirmation

### Theorem Record Fields

- `full_name`: Theorem qualified name (e.g., "Algebraic.cardinal_mk_lift_le_mul")
- `file`: Source file path (e.g., "Mathlib\\Algebra\\AlgebraicCard.lean")
- `statement`: Theorem type signature
- `proof_type`: "tactic" or "term"
- `proof_text`: Raw proof text
- `tactics`: List of tactic trace entries
- `all_premises`: Dict of premise references
- `metrics`: num_tactics, num_premises, statement_length, proof_length
- `quality`: Tracing quality flags

### Per-Tactic Fields

- `index`: Position in proof (0-based)
- `tactic`: Raw tactic text
- `annotated_tactic`: Annotated version
- `state_before`: Proof state before execution
- `state_after`: Proof state after execution
- `context`: Variables, hypotheses, typeclasses, goal
- `premises`: List of premises used with confidence scores
- `is_terminal`: Whether tactic closes proof
- `num_goals_before`: Goals before
- `num_goals_after`: Goals after

## 3. Usable Data Quantification

| Category | Count |
|----------|-------|
| Total theorems | 126,797 |
| **Tactic proofs** | **54,477** ✓ |
| Term proofs | 72,315 (excluded) |
| Total tactic instances | 276,014 |
| Total premise references | 784,726 |

**Filter Applied**: `proof_type == "tactic"` and `nonempty(tactics)`

## 4. Tactic Frequency Analysis

| Tactic | Count | Category |
|--------|-------|----------|
| rw | 44,680 | Rewriting |
| simp | 29,925 | Simplification |
| exact | 28,376 | Goal completion |
| have | 17,202 | Local facts |
| refine | 13,798 | Partial terms |
| apply | 9,659 | Theorem application |
| intro | 8,018 | Variable intro |
| obtain | 6,121 | Destructuring |
| simpa | 6,107 | Alt. simp |

## 5. Proof Size Distribution

- **Average tactics per proof**: 5.1
- **Median**: 2
- **Min**: 0 (empty)
- **Max**: 156
- **Average premises per proof**: 6.6

## 6. Edge Cases Identified

- Short proofs (1-2 tactics): 10+ samples available
- Long proofs (11+ tactics): 20+ samples available
- Multi-goal proofs: Present in corpus
- Terminal tactics: Many `exact?` closing proofs

## 7. Data Quality Assessment

### Strengths
- Complete state_before/state_after for dependency inference
- Premise resolution with confidence scores
- Rich context information (variables, hypotheses, typeclasses)

### Considerations
- Premise confidence varies (0.3 - 1.0)
- Some resolution methods are ambiguous
- Unicode encoding in proof states (manageable)

## 8. Manual Validation Sample

30 sample records saved to `data/00_sample_theorem_records.jsonl`:
- 5 short proofs
- 10 medium proofs
- 10 long proofs
- 5 multi-goal proofs

## 9. Replay Availability

**Status**: Not confirmed - mathlib source checkout and Lean toolchain version not locally available.

**Implication**: Stage 4 refactoring validation will need to be abstract-only unless replay infrastructure is added later.

---

## Acceptance Criteria Status

- [x] Primary input files identified
- [x] Schema documented without guessing
- [x] Sample records saved for manual inspection
- [x] Tactic proof count quantified (54,477)
- [x] Edge cases identified
- [ ] Replay availability confirmed (deferred)

**Recommendation**: Proceed to Stage 1 (TDG Construction)

---
