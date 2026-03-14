# Lab Notebook: Paper Gap Ledger and Next Execution Block

## 2026-03-14

### 18 missing paper-level components

1. **Corpus-level compression objective is not implemented**
   - Status: missing.
   - Why it matters: the paper optimizes compression of the proof corpus, not just frequency or support.
   - Feasibility: feasible now. We already have candidate sizes, witness counts, theorem assignments, and collapsibility results. We can compute compression-style proxy scores immediately and refine them after refactoring is implemented.

2. **No real `LearnTactic` optimization loop**
   - Status: missing.
   - Why it matters: the paper keeps searching until the highest-scoring tactic is found under the optimization objective.
   - Feasibility: feasible, but should come after compression-power scoring and better candidate generation. The loop is implementable once scoring and candidate expansion are trustworthy.

3. **No graph grammar extraction**
   - Status: missing.
   - Why it matters: the paper learns a graph grammar from existing TDGs and uses it to guide graph search.
   - Feasibility: feasible, but not immediate. It requires a cleaner stage-2 candidate representation than the current path-only miner.

4. **No upper-bound pruning based on compression power**
   - Status: missing.
   - Why it matters: the paper prunes candidate expansions using upper bounds on achievable compression.
   - Feasibility: feasible after we define a concrete compression-power objective and a candidate expansion framework. Not blocked in principle, but premature before the scoring layer exists.

5. **We only mine path motifs, not general connected TDG subgraphs**
   - Status: missing.
   - Why it matters: the paper is about common isomorphic subgraphs, not just paths.
   - Feasibility: feasible. This is a substantial but tractable stage-2 upgrade. It will require canonicalization and witness-preserving enumeration for small connected subgraphs.

6. **No tactic-sized candidate representation beyond motif shape**
   - Status: missing.
   - Why it matters: the paper learns tactics, not just subgraphs. A tactic needs a coherent input/output interface and body abstraction.
   - Feasibility: feasible. The current proof-object TDGs provide the raw material; we still need to synthesize a tactic candidate abstraction from repeated embeddings.

7. **No generalized argument abstraction / anti-unification-like parameterization for learned tactics**
   - Status: missing.
   - Why it matters: repeated subgraphs must be generalized into reusable tactics over varying arguments.
   - Feasibility: feasible, but it depends on a better tactic-candidate representation first. The current object ids and witness maps make this possible.

8. **Refactoring is not implemented as an actual proof transformation**
   - Status: missing.
   - Why it matters: the paper contracts collapsible embeddings and rebuilds proofs. That is how it turns structure into proof-size reduction.
   - Feasibility: feasible at the TDG level now, even without Lean replay. Executable Lean replay is a later layer.

9. **No iterative library growth**
   - Status: missing.
   - Why it matters: the paper learns a library, not just one tactic. It refactors the corpus and repeats.
   - Feasibility: feasible after compression scoring and refactoring exist. It is a natural second-order loop, not something fundamentally blocked.

10. **No proof-size accounting at the theorem/corpus level after refactoring**
   - Status: missing.
   - Why it matters: the paper measures proof size reduction over the corpus. We currently only count supports and witnesses.
   - Feasibility: feasible now in approximate form. Exact Lean-level proof-script size comes later, but TDG-level size accounting can be implemented immediately.

11. **No disjoint embedding accounting**
   - Status: missing.
   - Why it matters: overlapping collapsible embeddings cannot all be counted toward compression simultaneously.
   - Feasibility: feasible now. Exact optimal selection is combinatorial, but a principled disjoint-selection procedure or approximation can be implemented on current witness data.

12. **No induced-proof / topological reconstruction**
   - Status: missing.
   - Why it matters: the paper relies on TDGs inducing valid topological orderings after contraction.
   - Feasibility: feasible at TDG level. It needs branch-aware reconstruction logic, but nothing here is blocked conceptually.

13. **No executable Lean replay of learned tactics**
   - Status: missing.
   - Why it matters: the paper validates learned tactics in the prover.
   - Feasibility: feasible only after we have a matching mathlib checkout and toolchain. The concept is implementable; the local environment is the current blocker.

14. **No evaluation protocol comparable to the paper**
   - Status: missing.
   - Why it matters: we have not yet measured held-out compression, number of learned tactics, or search/runtime tradeoffs.
   - Feasibility: feasible once the learning/refactoring pipeline exists. This is downstream, not impossible.

15. **No automation integration**
   - Status: missing.
   - Why it matters: the paper also demonstrates utility for proof automation.
   - Feasibility: feasible later. This depends on replay, generated tactics, and an automation interface.

16. **Tactic semantics are still only partially tactic-head-aware**
   - Status: partially implemented, still incomplete.
   - Why it matters: the paper’s Table 1 style semantics matter for robust input/output inference.
   - Feasibility: feasible. We can incrementally add tactic-family-specific semantics for `intro`, `apply`, `exact`, `split`, `constructor`, `cases`, `rcases`, `rw`, and related families.

17. **Nested `by` / flattened trace handling is only a workaround**
   - Status: partially handled, still incomplete.
   - Why it matters: flattened nested subproofs can distort true proof-state flow if not handled carefully.
   - Feasibility: feasible to improve. We already resynchronize nested subproofs; we can make that logic cleaner and better documented.

18. **Current candidate ranking overemphasizes tiny motifs**
   - Status: present limitation.
   - Why it matters: short frequent motifs dominate support-based ranking even when larger motifs may be more compressive.
   - Feasibility: feasible to improve immediately. Compression-power scoring and overlap-aware accounting directly address this.

### Priority decision after reviewing the 18 points

After writing the full gap list, the best first execution block is still:

1. implement compression-power based ranking,
2. add disjoint collapsible embedding accounting,
3. produce a reranked candidate table and report.

Why this comes first:

- it directly addresses points 1, 10, 11, and 18,
- it changes candidate ranking in a paper-relevant way,
- it is implementable on the current outputs without waiting for larger architectural changes,
- and it gives a better basis for deciding which candidates deserve richer subgraph mining or refactoring work next.

### Immediate execution commitment

I will execute next:

- a stage-4 compression analysis script,
- a disjoint collapsible witness selector per theorem,
- corpus-level compression-power ranking outputs,
- and a report describing how the ranking differs from raw support-based ranking.
