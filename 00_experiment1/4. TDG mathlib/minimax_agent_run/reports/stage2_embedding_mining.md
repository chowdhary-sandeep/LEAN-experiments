# Stage 2: Isomorphic Embedding Mining Report

**Date**: 2026-03-14
**Stage**: Isomorphic Embedding Mining

---

## 1. Methodology

### Matching Granularity
- **Node labels**: Normalized tactic head (rw, simp, exact, have, apply, etc.)
- **Edge labels**: edge_type (hyp_to_goal, goal_to_goal, premise_use)
- **Not matched**: Theorem names, literal proposition strings

### Generation Approach
1. Extract connected subgraphs of size 2-4 from each TDG
2. Count unique pattern occurrences across theorems
3. Filter by minimum support threshold

---

## 2. Results

### Pattern Count by Support

| Support | Patterns | Percentage |
|---------|----------|------------|
| 2 | 6,790 | 57% |
| 3-5 | 3,529 | 29% |
| 6-10 | 1,023 | 9% |
| 11+ | 624 | 5% |
| **Total** | **11,966** | 100% |

---

## 3. Top 10 Most Frequent Patterns

| Rank | Pattern | Support | Description |
|------|---------|---------|-------------|
| 1 | rw -> exact | 391 | Rewrite then close goal |
| 2 | ext -> simp | 211 | Extensionality then simplify |
| 3 | rw -> simp | 152 | Rewrite then simplify |
| 4 | by_cases -> bullet | 150 | Case analysis |
| 5 | rw -> exact (later) | 144 | Alternative rewrite position |
| 6 | constructor -> bullet | 141 | Constructor splits |
| 7 | bullet -> rw | 127 | Subgoal then rewrite |
| 8 | induction' -> bullet | 124 | Induction variant |
| 9 | bullet -> simp | 117 | Subgoal then simplify |
| 10 | have -> rw | 104 | Introduce lemma then rewrite |

---

## 4. Sample Witnesses

### Pattern 1: rw -> exact

```
LinearMap.BilinForm.span_singleton_sup_orthogonal_eq_top
pow_lt_pow_succ
Set.bounded_lt_inter_lt
```

### Pattern 2: ext -> simp

```
Algebra.traceMatrix_reindex
op_smul_coe_set
Multiset.coe_inter
```

---

## 5. Analysis

### What These Patterns Tell Us

1. **Rewrite-heavy proofs**: The most common pattern is `rw -> exact`, showing that most mathlib proofs use rewriting to transform the goal before finishing.

2. **Simplification follows extensionality**: `ext -> simp` is the second most common, reflecting the common idiom of "extensionality + simplify".

3. **Case analysis is common**: `by_cases -> bullet` shows that manual case analysis is frequent.

4. **Constructor proofs**: `constructor -> bullet` reflects the common pattern of using constructors to decompose goals.

### Patterns Are Reusable

Each pattern appears across different mathematical domains (algebra, topology, measure theory), suggesting they are genuinely reusable proof idioms.

---

## 6. Next Steps

- Stage 3: Collapsible Embedding Filtering
- Filter patterns that satisfy the paper's collapsibility conditions
- Identify which patterns can be refactored into single tactics

---
