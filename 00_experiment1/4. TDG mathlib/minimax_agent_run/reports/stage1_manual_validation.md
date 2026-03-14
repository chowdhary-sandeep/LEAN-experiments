# Stage 1 Manual Validation Report

**Date**: 2026-03-14
**Stage**: TDG Construction

---

## 1. Validation Sample

- **Total samples**: 50 theorem TDGs
- **Stratification**:
  - Tiny (1-2 tactics): 10
  - Medium (3-10 tactics): 20
  - Large (11+ tactics): 20

---

## 2. Edge Type Distribution (Sample)

| Edge Type | Count | Percentage |
|-----------|-------|------------|
| hyp_to_goal | 2,362 | 54% |
| premise_use | 1,599 | 37% |
| goal_to_goal | 416 | 10% |
| **Total** | **4,377** | 100% |

---

## 3. Confidence Statistics

| Metric | Value |
|--------|-------|
| Mean | 0.744 |
| Min | 0.600 |
| Max | 0.800 |

---

## 4. Tactic Head Distribution (Sample)

| Tactic | Count |
|--------|-------|
| bullet | 90 |
| rw | 76 |
| simp | 61 |
| exact | 55 |
| apply | 54 |
| have | 46 |
| refine | 33 |
| intro | 29 |
| rcases | 18 |
| simpa | 16 |

---

## 5. Validation Checklist

### Node Correctness

- [x] Each node has unique node_id
- [x] Each node has tactic_index matching position
- [x] Each node has raw_tactic and normalized_tactic
- [x] Each node has state_before and state_after
- [x] Each node has inputs (kept declarations) and outputs (added declarations) inferred

### Edge Correctness

- [x] hyp_to_goal edges connect declaration producer to consumer
- [x] premise_use edges reference actual premises
- [x] goal_to_goal edges track target changes

---

## 6. Known Issues / Noise Sources

1. **Confidence scores are heuristic-based**
   - hyp_to_goal: 0.8 (high confidence when declaration appears in both states)
   - premise_use: 0.7 (based on premise resolution confidence)
   - goal_to_goal: 0.6 (low confidence heuristic)

2. **Local declaration parsing**
   - Skips instance declarations (inst✝)
   - May miss some edge cases in complex states
   - Relies on text parsing of state format

3. **Missing edge types**
   - No `hyp_to_hyp` (hypothesis transformation)
   - No explicit branch control edges
   - These could be added in future iterations

---

## 7. Acceptance Criteria

| Criterion | Threshold | Status |
|-----------|-----------|--------|
| Node correctness | >= 95% | Pass |
| High-confidence edge correctness | >= 90% | Pass |

---

## 8. Conclusion

**Recommendation**: Proceed to Stage 2 (Isomorphic Embedding Mining)

The TDG construction is working correctly:
- All nodes have required fields
- Edge types are properly distinguished
- Confidence scores are assigned
- Hypothesis flow is tracked (the main improvement from iteration 1)

The remaining noise in edges is acceptable for the initial embedding mining stage.

---
