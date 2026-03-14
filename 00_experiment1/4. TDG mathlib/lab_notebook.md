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

## 2026-03-14 follow-up: executed compression-power block

### What was implemented

- Implemented `scripts/09_compute_compression_power.py`.
- It uses:
  - accepted collapsible witnesses from stage 3,
  - host-node mappings from stage 2,
  - candidate sizes from stage 3 candidate summaries.
- It computes:
  - theorem-local disjoint witness selections using node-set non-overlap,
  - theorem-level estimated savings,
  - candidate-level estimated corpus savings,
  - and a reranked candidate table.

### Outputs written

- `data/stage4_candidate_compression_ranking.parquet`
- `data/stage4_theorem_level_compression.parquet`
- `reports/stage4_compression_power.md`

### What changed in ranking

The top of the table is still dominated by size-2 motifs, but compression-aware ranking changes the ordering and starts surfacing some larger candidates.

Top by estimated corpus savings:

- `rw -> exact`
- `have -> rw` with `hyp_to_goal`
- `have -> have`
- `rw -> simp`
- `refine -> rw`

Most important larger candidate now visible near the top:

- `have -> have -> have`
  - size 3
  - disjoint hits 788
  - estimated corpus savings 1576

Other larger candidates that now become visible:

- `refine -> rw -> exact`
- `have -> rw -> exact`
- `have -> have -> rw`
- `apply -> rw -> exact`
- `rw -> rw -> exact`

### Interpretation

- Compression-aware scoring does improve the ranking and reduces some support-only distortion.
- However, the best-scoring candidates are still mostly tiny motifs.
- This means compression scoring was necessary but not sufficient.
- The next bottleneck is now clearer:
  - stage 2 candidate generation is too narrow because it only mines path motifs.

### Revised priority after execution

After running the compression block, the revised next priorities are:

1. upgrade stage 2 from paths to small connected subgraphs,
2. keep compression-power ranking as the primary scoring function,
3. then implement TDG-level refactoring on the reranked candidates,
4. then revisit iterative library growth.

So the earlier priority list was directionally right, but the execution result makes the ordering sharper:

- scoring first was correct,
- and the next highest-leverage step is definitely richer subgraph generation rather than immediately jumping to full library loops.

## 2026-03-14 note: how the paper makes richer subgraph search efficient

After re-reading the relevant learning sections of the paper, the efficient search story is:

1. **graph-grammar-guided top-down enumeration**
   - They do not brute-force all subgraphs.
   - `LearnTactic(Π)` first constructs TDGs, then calls `LearnGraphGrammar(G)`, initializes a worklist from that grammar, and expands candidates with `Expand`.
   - So candidate generation is constrained by graph patterns actually seen in the corpus.

2. **upper-bound pruning**
   - Before fully pursuing a candidate, they compute `UpperBound(Ψ, Π)`.
   - If that upper bound is already below the best effectiveness score seen so far, they prune the candidate and all of its possible expansions.
   - The paper proves this pruning is sound.

3. **optimization does not stop at “found a common subgraph”**
   - The search is driven by candidate effectiveness and ultimately compression power, not by support alone.
   - The search continues until the worklist is exhausted modulo pruning, so the result is the highest-scoring tactic under the objective.

### How we can faithfully mirror this in our work

We can mirror this fairly faithfully, but we need to adapt each ingredient to our current Lean/mathlib pipeline.

#### A. `LearnGraphGrammar(G)` analogue for our setting

Faithful mirror:

- treat validated stage-1 theorem TDGs as the source corpus,
- extract recurring local graph expansions rooted at a node or partial connected subgraph,
- represent grammar productions as allowed node-and-edge extensions that are observed in real theorem TDGs.

Practical adaptation:

- start with small connected tactic-only subgraphs rather than full arbitrary TDG fragments,
- include edge labels (`goal_to_goal`, `hyp_to_goal`) and tactic heads in productions,
- optionally keep premise-use outside the structural grammar at first.

Reason this is faithful:

- the paper also learns the grammar from existing TDGs rather than assuming one in advance.

#### B. `InitWorklist(R, Π)` analogue

Faithful mirror:

- initialize the worklist from grammar-derived seed candidates, not from all possible subgraphs.

Practical adaptation:

- seeds should include:
  - single tactic nodes,
  - two-node connected patterns observed frequently in the corpus,
  - possibly roots chosen by tactic-head frequency or branch-centrality.

#### C. `Expand(Ψ, R, Π)` analogue

Faithful mirror:

- expand a candidate only using grammar-consistent local graph growth.

Practical adaptation:

- given a connected candidate subgraph, expansions can:
  - add one new node connected by an allowed labeled edge to an existing node,
  - add one missing internal edge between already-present nodes if supported by the grammar,
  - preserve connectedness and a designated root.

This is the key step that would replace our current path-only miner.

#### D. `E(Ψ, Π)` analogue

Faithful mirror:

- candidate effectiveness should depend on:
  - candidate size,
  - collapsible embeddings in the corpus,
  - and the resulting proof-size reduction.

Practical adaptation:

- use our current overlap-aware compression proxy first:
  - `disjoint_witness_count * (Size(candidate) - 1)`
- then later replace it with TDG-level refactoring-based size reduction,
- and later still with proof-script-level reduction if Lean replay becomes available.

This is already much closer to the paper than support-based ranking.

#### E. `UpperBound(Ψ, Π)` analogue

Faithful mirror:

- compute an upper bound on the best possible compression any expansion of `Ψ` could achieve.

Practical adaptation:

- for each witness of `Ψ` in a theorem TDG, compute a maximum extendable connected region rooted compatibly with `Ψ`,
- use the size of that maximal extension plus witness-count information to bound the best possible future savings of descendants of `Ψ`,
- prune if this bound is below the current best candidate score.

This mirrors the paper’s logic even if our exact bound formula differs initially.

#### F. stopping criterion

Faithful mirror:

- do not stop after finding a frequent or collapsible motif,
- stop only when the worklist is exhausted after upper-bound pruning.

This is a major correction relative to our current approach.

### Concrete implementation path for a faithful mirror

1. replace stage 2 path mining with connected-subgraph candidate generation,
2. learn a small expansion grammar from validated TDGs,
3. maintain a worklist of candidates,
4. score candidates with compression-aware effectiveness,
5. compute an upper bound for expandable candidates,
6. prune aggressively,
7. return the best candidate only after search exhaustion modulo pruning,
8. then apply TDG-level refactoring and repeat for library growth.

### Bottom-line assessment

This part of the paper can be mirrored faithfully in our work.

The main adaptations needed are:

- our grammar must be learned from Lean/mathlib TDGs rather than Rocq TDGs,
- our effectivess score must initially use a proxy based on current collapsible witnesses,
- and our upper bound will likely begin as a simpler but sounder approximation before we make it tighter.

Nothing about this search strategy is fundamentally blocked for our setting. The real work is engineering the candidate representation, witness-preserving connected-subgraph expansion, and sound pruning.

## 2026-03-14 execution: connected-subgraph upgrade

I executed the next step after the design note:

- replaced path-only stage-2 approximation with a bounded connected-subgraph miner,
- reran collapsibility on those connected candidates,
- reran compression-power ranking on the resulting connected candidates.

### Scripts added

- `scripts/10_mine_connected_embeddings.py`
- `scripts/11_compute_connected_collapsible.py`
- `scripts/12_compute_connected_compression.py`

### Outputs written

- `data/stage2b_connected_candidates.parquet`
- `data/stage2b_connected_witnesses.parquet`
- `data/stage3b_connected_collapsible_candidates.parquet`
- `data/stage3b_connected_collapsible_witnesses.parquet`
- `data/stage4b_connected_compression_ranking.parquet`
- `data/stage4b_connected_theorem_compression.parquet`
- `reports/stage2b_connected_embedding_mining.md`
- `reports/stage3b_connected_collapsibility.md`
- `reports/stage4b_connected_compression_power.md`

### Quantitative results

- connected candidates mined: 102,541
- connected witnesses mined: 1,578,698
- connected candidates surviving collapsibility and compression ranking table: 75,115

### What changed qualitatively

The connected-subgraph pass still has many top size-2 motifs, but it now surfaces richer non-path candidates much more clearly.

Top larger connected candidates include:

- `have / have / have`
- `by_cases / rw / rw`
- `by_cases / simp / simp`
- `refine / rw / exact`
- `have / rw / exact`
- `constructor / rintro / rintro`
- `apply / rw / exact`

This is a real improvement over the previous path-only search because:

- some candidates now have internal structure beyond a single path edge,
- some branch-related motifs start to appear,
- and compression-aware ranking can now reward larger connected tactics more directly.

### Current interpretation

- This connected-subgraph upgrade was worth doing and is closer to the paper.
- However, the search is still not yet fully paper-faithful because:
  - it is a bounded connected-subgraph enumerator, not yet a grammar-guided worklist search,
  - and it does not yet use `UpperBound`-style pruning.

### Revised next bottleneck

After executing connected subgraphs, the next bottleneck is no longer “paths vs connected subgraphs.”

The next bottleneck is now:

- grammar-guided candidate expansion,
- plus upper-bound pruning over compression effectiveness.

That is the next step required to mirror the paper more faithfully and make larger-subgraph search efficient enough to scale.

## 2026-03-14 dashboard update notes

The dashboard needed two corrections after the connected-subgraph upgrade.

### 1. Data correction

The dashboard should not continue to surface the older path-based collapsibility outputs once the connected-subgraph pipeline exists.

So the dashboard data layer should use:

- `data/stage2b_connected_witnesses.parquet`
- `data/stage3b_connected_collapsible_witnesses.parquet`
- `data/stage3b_connected_collapsible_candidates.parquet`
- `data/stage4b_connected_compression_ranking.parquet`

This matters because otherwise the UI would present obsolete witness families and obsolete candidate rankings.

### 2. UI correction

The original dashboard was serviceable as a utility, but not good enough as an analysis instrument.

For this project the dashboard should expose:

- theorem search and selection over the full corpus,
- theorem-level proof statistics,
- theorem statement and proof text context,
- connected-subgraph collapsible witnesses ranked by estimated corpus savings,
- subgraph highlighting inside the TDG,
- and direct inspection of node- and edge-level proof-object flow.

### 3. Visualization correction

For connected candidates, highlighting should reflect the induced matched subgraph inside the host theorem TDG.

That means:

- highlight all matched tactic nodes in the witness,
- highlight all TDG edges whose endpoints both lie inside the matched node set,
- and dim the rest of the theorem graph when inspecting a witness.

This is better than the previous path-style highlight, because connected candidates are not always reducible to one ordered chain.

### 4. Aesthetic goal

The dashboard should look like a research tool rather than an internal debug page.

So the redesign should aim for:

- stronger visual hierarchy,
- more intentional typography and spacing,
- cleaner theorem cards,
- better graph framing,
- better collapsibility cards,
- and a more legible proof-analysis panel layout on both desktop and narrower screens.

### 5. Immediate execution plan

The immediate execution sequence is:

1. keep the connected-subgraph dashboard data source,
2. rewrite `TDG.html` with a more deliberate visual system,
3. rebuild dashboard assets,
4. verify that theorem JSON payloads now contain connected-subgraph witness metadata,
5. and verify that the browser UI highlights induced witness subgraphs correctly.

## 2026-03-14 dashboard performance/layout follow-up

After the first redesign pass, two practical issues were clear:

- the graph renderer was too expensive for larger theorem TDGs,
- and the previous layout made some proofs look unnaturally narrow or overly stretched.

### Corrections applied

- switched from the coarse `breadthfirst` layout to a DAG-oriented `dagre` layout,
- added explicit orientation controls for top-down versus left-right viewing,
- turned edge labels off by default and made them opt-in,
- enabled Cytoscape viewport performance options so panning and zooming are lighter,
- and kept witness highlighting while reducing the always-on rendering burden.

### Why this should help

- `dagre` is better matched to proof DAG structure than the previous layout,
- hiding edge labels by default removes a major source of paint cost on dense graphs,
- and orientation control lets the user pick the more readable aspect ratio for a given theorem.

This does not solve every future dashboard problem, but it is the right immediate correction for the lag and poor proof geometry.

## 2026-03-14 dashboard performance fix: precomputed node positions

The previous browser-side layout attempt was still too expensive and also introduced a failure mode where the graph region could remain empty if the client-side layout path was not fully consistent.

So the stronger correction was:

- precompute theorem-local node positions in `scripts/08_build_tdg_dashboard.py`,
- store those positions directly in each theorem JSON under `dashboard_data/graphs/`,
- and render the graph with Cytoscape `preset` layout instead of any in-browser search procedure.

### Why this is the right fix

- theorem selection now becomes JSON fetch plus draw, not layout computation,
- orientation switching becomes a cheap coordinate swap,
- graph visibility no longer depends on optional client-side layout plugins,
- and the dashboard can scale much better to larger theorem TDGs.

### Additional frontend corrections

- reduced the default visible theorem list from 300 to 120,
- simplified the visual palette toward a more neutral monochrome dashboard,
- kept edge labels off by default,
- and removed the heaviest unnecessary rendering options.

This is materially better than the prior approach because it removes the biggest source of interaction latency rather than merely tuning around it.

## 2026-03-14 dashboard simplification pass

The previous dashboard still carried too much frontend complexity relative to the task.

So I replaced it with a deliberately simpler static viewer:

- plain Cytoscape rendering with precomputed positions,
- no browser-side graph layout search,
- no hover-heavy UI,
- minimal theorem list cards,
- simple theorem metadata,
- simple proof-text pane,
- and simple collapsible-witness highlighting.

I also reran `scripts/08_build_tdg_dashboard.py` after the position precomputation changes.

The guiding decision here was:

- make the dashboard fast and reliable first,
- then reintroduce richer UI only if it does not threaten responsiveness.
