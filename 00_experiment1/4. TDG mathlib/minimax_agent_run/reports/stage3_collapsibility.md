# Stage 3: Collapsible Embedding Report

**Date**: 2026-03-14
**Stage**: Collapsible Embedding Identification

---

## 1. Collapsibility Conditions

### Path Closure
If two matched nodes have an intermediate path node in the host TDG, that intermediate node must also lie inside the embedding.

### Internal Edge Completeness
If host TDG contains an edge between two matched host nodes, the candidate must also contain the corresponding edge.

---

## 2. Results

| Category | Count |
|----------|-------|
| Collapsible patterns | 431 |
| Non-collapsible patterns | 827 |
| Total checked | 18,253 |

### Failure Distribution

| Reason | Count |
|--------|-------|
| internal_edge_incomplete | 16,922 |
| path_closure_violation | 1,331 |

---

## 3. Top Collapsible Patterns

| Rank | Pattern | Support | Collapsible Ratio |
|------|---------|---------|-------------------|
| 1 | simp -> have | 5 | 100% |
| 2 | rcases -> bullet | 92 | 100% |
| 3 | by_cases -> bullet | 150 | 100% |
| 4 | ext -> simp | 211 | 100% |
| 5 | match -> simp | 6 | 100% |
| 6 | suffices -> refine | 9 | 100% |
| 7 | obtain -> rw | 10 | 100% |
| 8 | cases -> rfl | 18 | 100% |
| 9 | unfold -> rw | 18 | 100% |
| 10 | ext1 -> rw | 7 | 100% |

---

## 4. Analysis

### Why These Patterns Are Collapsible

All top patterns share a common structure:
1. **Two-node linear chains**: Node 0 produces output, Node 1 consumes it
2. **Direct edge**: There's a single edge from node 0 to node 1
3. **No intermediate nodes**: No other tactics between them

### Why Other Patterns Fail

1. **internal_edge_incomplete**: Pattern has only one edge, but host TDG has multiple edges between pattern nodes (more complex structure)

2. **path_closure_violation**: There's an intermediate tactic between pattern nodes in some embeddings

---

## 5. Implications for Tactic Learning

These 431 collapsible patterns represent the most promising candidates for:
- Automated tactic extraction
- Proof refactoring
- Building a learned tactic library

The top patterns (like `ext -> simp` with 211 occurrences) are the most widely applicable.

---

## 6. Next Steps

- Stage 4: Tactic Candidate Extraction and Refactoring
- Generate executable Lean tactic definitions from collapsible patterns

---
