# Supervised Report on the Minimax 2.5 TDG Run

## Scope

This report audits what the Minimax 2.5 agent actually produced in `E:\LEAN-experiments\00_experiment1\4. TDG mathlib`, compares it against the intended paper workflow in *Automated Discovery of Tactic Libraries for Interactive Theorom Proving*, and evaluates whether it detected the structures we wanted.

The standard used here is not the agent's own stage reports alone. I checked:

- created files and directory structure,
- stage output artifacts in `data/`, `reports/`, and `figs/`,
- implementation scripts in `scripts/`,
- whether the implementation matches the paper-level concepts:
  - tactic dependency graphs (TDGs),
  - isomorphic embeddings,
  - collapsible embeddings,
  - manual validation between stages,
  - paper-style plots/figures.

## Executive Judgment

The run was a **partial success at the scaffold/prototype level**, and an **unsuccessful execution of the full scientific pipeline**.

What succeeded:

- It created a coherent project structure.
- It audited the available mathlib-derived data and selected a plausible input source.
- It built a first-pass per-theorem graph representation from tactic traces.
- It mined recurring local tactic patterns that are probably real at a qualitative level.
- It wrote stage reports and basic intermediate artifacts that make the next iteration easier.

What did **not** succeed:

- Stage 1 is not yet a paper-faithful TDG construction.
- Stage 2 does not implement isomorphic embedding in the paper's sense.
- Stage 3 does not implement collapsible embedding identification in a trustworthy way.
- The claimed stage 2/3 discoveries should therefore **not** be treated as validated scientific results.
- The plotting requirement was not met: there are essentially no paper-style figures.

So the honest conclusion is:

> The agent detected some likely recurring tactic motifs, but it did **not** yet solve the intended TDG -> isomorphic embedding -> collapsible embedding discovery problem as specified by the paper.

## Created Outputs

### Top-level files

The run created or populated:

- `data/`
- `figs/`
- `reports/`
- `scripts/`
- `lab_notebook.md`
- `TDG_execution_plan.md`

### Data artifacts

Observed outputs in `data/`:

- `00_corpus_schema_summary.json`
- `00_sample_theorem_records.jsonl`
- `debug_state.txt`
- `debug_state2.txt`
- `sample_tactic_record.json`
- `stage1_stats.json`
- `stage1_tdg_by_theorem.jsonl`
- `stage1_tdg_by_theorem.pkl`
- `stage1_tdg_schema.md`
- `stage1_validation_samples.jsonl`
- `stage2_isomorphic_candidates.json`
- `stage2_mining_summary.json`
- `stage3_collapsible_candidates.json`

### Reports

Observed outputs in `reports/`:

- `00_data_audit.md`
- `stage1_manual_validation.json`
- `stage1_manual_validation.md`
- `stage2_embedding_mining.md`
- `stage3_collapsibility.md`

### Scripts

Observed outputs in `scripts/`:

- `00_audit_mathlib_tdg_inputs.py`
- `01_build_mathlib_tdgs.py`
- `02_validate_stage1_samples.py`
- `03_plot_corpus_stats.py`
- `04_mine_isomorphic_embeddings.py`
- `06_compute_collapsible_embeddings.py`

### Figures

The `figs/` directory does **not** contain the expected paper-style visual outputs. I found only:

- `figs/corpus_summary.json`

That is not a figure output. So the plotting stage was effectively not completed.

## Stage-by-Stage Evaluation

## Stage 0: Data Audit

### Verdict

**Mostly successful.**

### What it got right

The agent identified a plausible primary source for mathlib proof traces and tactic-level data. The audit aligns with the broader repository context: the main raw inputs for this line of work do indeed appear to live under:

- `E:\LEAN-experiments\00_experiment1\jsons`

The stage report also correctly converged on the theorem-trace corpus as the core input source.

The report's top-level counts are plausible:

- 54,477 tactic proofs
- 276,014 tactic steps total

This is consistent with a large tactic-proof subset of mathlib traces.

### Limitation

The audit was descriptive, not yet operationally complete. In particular:

- it did not fully establish replayability requirements,
- it did not pin down exact field semantics for all tactic-trace records,
- it did not fully tie stage-1 TDG semantics to the actual trace schema before implementation.

This is acceptable for a first pass, but it matters because later stages depend on the exact meaning of fields like before/after goals, local context changes, and premise references.

## Stage 1: TDG Construction

### Claimed outcome

The run claims it built theorem-level TDGs and manually validated 50 samples.

Artifacts:

- `data/stage1_tdg_by_theorem.jsonl`
- `data/stage1_tdg_by_theorem.pkl`
- `data/stage1_stats.json`
- `reports/stage1_manual_validation.md`

### Quantitative output

From `stage1_stats.json`:

- `total_processed`: 54,473
- `empty_proofs`: 4
- `node_count`: 276,014
- `edge_count`: 1,214,916

This indicates the builder ran over most of the intended corpus and produced a large graph dataset.

### What is genuinely useful here

As a prototype, this stage is useful. It gives:

- one node per tactic step,
- some notion of step-to-step flow,
- some notion of introduced hypotheses,
- some notion of premise usage,
- a serializable per-theorem graph corpus for later experimentation.

That is enough to support exploratory mining.

### Why this is not yet a faithful TDG

After reading `scripts/01_build_mathlib_tdgs.py`, the implemented graph is a **heuristic proof-step dependency graph**, not yet the paper's TDG in a rigorous sense.

Key issues:

1. **Encoding problems in parser logic**

The script appears to rely on mojibake versions of important symbols:

- bullet recognized as `Â·`
- goal turnstile recognized as `âŠ¢`

This is strong evidence that parsing is brittle and may silently mis-handle proof states depending on source encoding.

2. **Input/output inference is shallow**

The `infer_tactic_io` function infers:

- inputs = declarations kept across the tactic step,
- outputs = declarations added across the step.

That is only a rough proxy for tactic dependencies. It does not rigorously model the paper's semantics of tactic input/output objects in the proof state.

3. **Hypothesis edges are name-based heuristics**

The builder records where declarations were introduced, then adds `hyp_to_goal` edges by matching declaration names later. This is plausible as a first approximation, but it can overconnect or misattribute dependencies when names are reused, shadowed, or context changes are more subtle than simple set difference.

4. **Premise edges are based on surface references only**

Premise usage is added from nodes like `premise:<name>` whenever a tactic mentions a surface premise reference. That is useful metadata, but it is weaker than a validated dependency reconstruction.

5. **Goal-to-goal edges are mostly sequential**

The implementation mostly connects tactic `i` to tactic `i+1` when the target changes, which is much closer to proof-step adjacency than to a fully inferred dependency graph.

### Interpretation

Stage 1 should be considered:

- **successful as a first-pass graph extraction prototype**,
- **not yet successful as a validated TDG implementation of the paper**.

### About the manual validation claim

The report claims strong manual validation success, but the evidence is still thin. I did not find a rich sample-by-sample audit demonstrating:

- exact theorem names,
- extracted local graph,
- original trace snippet,
- human comparison,
- pass/fail rationale per sample.

So the validation currently reads more like a checklist summary than a convincing audit trail.

That means the scientific confidence in stage 1 is still moderate at best.

## Stage 2: Isomorphic Embedding Mining

### Claimed outcome

The run claims to discover frequent isomorphic TDG patterns across the corpus.

Artifacts:

- `data/stage2_isomorphic_candidates.json`
- `data/stage2_mining_summary.json`
- `reports/stage2_embedding_mining.md`

Reported examples include:

- `rw -> exact`
- `ext -> simp`
- `rw -> simp`
- `by_cases -> bullet`
- `constructor -> bullet`

### Did it detect something real?

**Probably yes at the motif level.**

Those patterns are believable recurring tactic idioms in mathlib. So at a qualitative level, the miner is finding non-random repeated local structures.

### Did it implement isomorphic embedding as intended?

**No.**

This is the most important negative finding in the audit.

After reading `scripts/04_mine_isomorphic_embeddings.py`, the stage-2 procedure is not performing paper-style isomorphic embedding discovery.

Main reasons:

1. **It extracts local connected subgraphs by bounded expansion, not explicit graph embeddings**

The algorithm grows small connected neighborhoods from each node. That is a pattern miner, but not yet a rigorous embedding enumerator.

2. **Pattern edges keep host graph node ids**

The extracted pattern edges are stored using original node indices from the host TDG instead of relabeling into canonical local pattern ids. That breaks the intended abstraction barrier between:

- the pattern,
- and its witness occurrence in a host graph.

3. **No witness mapping is stored**

The output stores:

- nodes,
- edges,
- support,
- sample theorem names.

But it does not store the embedding map from each pattern node into each host theorem graph. Without that, you do not actually have embeddings in the paper's sense.

4. **Only a corpus sample is mined**

The script samples up to 10,000 theorem TDGs instead of mining the full 54k corpus. That is not inherently wrong for a prototype, but it weakens any interpretation of support counts as corpus-level results.

### Interpretation

Stage 2 is best described as:

- **a frequent local tactic-pattern miner over heuristic TDGs**,
- **not a correct implementation of isomorphic embedding mining from the paper**.

### Scientific success level

There is still some success here:

- it found plausible recurrent tactic motifs,
- it suggests there is real repeated local proof structure in the corpus,
- it gives candidate motifs worth pursuing.

But the stage is **unsuccessful** if judged against the intended formal objective.

## Stage 3: Collapsible Embedding Identification

### Claimed outcome

The run claims:

- 431 collapsible patterns,
- 827 non-collapsible patterns,
- 18,253 total checks,

with examples like:

- `ext -> simp`
- `by_cases -> bullet`
- `rcases -> bullet`

Artifacts:

- `data/stage3_collapsible_candidates.json`
- `reports/stage3_collapsibility.md`

### Did it identify real collapsible embeddings?

**Not in a trustworthy way.**

After reading `scripts/06_compute_collapsible_embeddings.py`, the stage-3 logic does not have the necessary inputs to validate collapsibility correctly.

Main problems:

1. **It has no embedding witnesses to evaluate**

Collapsibility has to be checked for specific embeddings of a pattern inside a host TDG. But stage 2 never stored those witness mappings.

2. **It compares pattern node ids directly to host node ids**

The script effectively assumes that pattern nodes correspond to host nodes `0..n-1`. That is not a valid embedding test.

3. **Path-closure and internal-edge checks are therefore misapplied**

The checks themselves are conceptually related to collapsibility, but because they are run without a valid witness mapping, their outputs are not meaningful evidence that the embedding is collapsible in the paper's sense.

4. **The final labeling rule is heuristic**

Patterns are marked collapsible if at least 50% of sampled host checks pass. That may be a practical heuristic later, but here it is being applied on top of invalid host-pattern correspondence.

### Interpretation

Stage 3 should be treated as:

- **not scientifically valid yet**,
- **not evidence that the reported collapsible candidates are truly collapsible embeddings**.

This is the clearest failed stage in the run.

## Validation Quality Between Stages

### Intended requirement

The project plan called for manual or agentic verification between stages, especially:

- validating TDGs against raw traces,
- validating mined embeddings,
- validating collapsibility examples.

### What actually happened

Only stage 1 has anything resembling manual validation artifacts.

I did not find convincing manual verification packages for:

- stage 2 embedding instances,
- stage 3 collapsibility decisions.

So the run did **not** satisfy the intended "verify between stages before moving on" requirement in a strong sense.

## Figures and Visualization

### Intended requirement

The plan explicitly asked for paper-style figures analogous to the paper's TDG and refactoring visuals.

### What happened

That did not happen.

There are no rendered plots corresponding to:

- proof TDG examples,
- discovered subgraph motifs,
- collapsible embedding examples,
- support distributions,
- theorem-level example visualizations like the paper's figure.

This matters because the paper's claims are much easier to assess visually. Without these plots, manual supervision is substantially weaker.

## Did It Detect What We Wanted?

This depends on how strictly "what we wanted" is defined.

## If the target was:

"Produce a working end-to-end approximation that starts surfacing repeated tactic structures in mathlib."

Then the answer is:

- **Yes, partially.**

It likely detected genuinely recurring local motifs such as:

- `rw -> exact`
- `ext -> simp`
- `by_cases -> bullet`

These are plausible and worth keeping as candidate motifs.

## If the target was:

"Implement the paper's TDG pipeline faithfully enough that stage-2 and stage-3 outputs are scientifically interpretable."

Then the answer is:

- **No.**

The current run does not meet that bar.

## Bottom-line Success Assessment

### Stage 0 data audit

- **Success**

### Stage 1 heuristic TDG extraction

- **Partial success**

### Stage 1 as paper-faithful TDG construction

- **Not yet successful**

### Stage 2 frequent motif detection

- **Partial success**

### Stage 2 as isomorphic embedding mining

- **Unsuccessful**

### Stage 3 as collapsible embedding identification

- **Unsuccessful**

### End-to-end scientific objective

- **Not yet achieved**

## Why It Fell Short

The failure mode is not that the agent found nothing. The failure mode is more specific:

1. It moved from a rough graph extraction to mining too quickly.
2. It did not formalize the TDG semantics tightly enough before stage 2.
3. It did not preserve witness mappings, which are essential for later collapsibility checks.
4. It did not perform strong manual verification between stages.
5. It did not produce the visualization layer that would have made errors obvious earlier.

So this is mainly a **pipeline rigor failure**, not a complete absence-of-signal failure.

## What Is Worth Keeping

The following outputs are still useful starting points:

- `scripts/00_audit_mathlib_tdg_inputs.py`
- `scripts/01_build_mathlib_tdgs.py`
- `data/stage1_tdg_by_theorem.jsonl`
- `reports/00_data_audit.md`
- `reports/stage1_manual_validation.md`
- `data/stage2_isomorphic_candidates.json`

These are useful as:

- scaffolding,
- data inspection utilities,
- early graph corpus generation,
- candidate motif seeds for a corrected stage-2 miner.

## Recommended Next Actions

## Priority 1: Repair Stage 1 before trusting anything later

Do this before any further mining:

- fix encoding/parsing of bullets and goal markers,
- define the exact TDG node/edge semantics from the paper,
- store enough information per tactic step to justify each dependency edge,
- produce 20-50 theorem-level side-by-side validation cases with:
  - theorem name,
  - raw trace excerpt,
  - derived TDG snippet,
  - human judgment and rationale.

## Priority 2: Rebuild stage 2 around actual embeddings

The corrected miner must:

- enumerate or sample candidate subgraphs,
- canonicalize pattern node ids,
- store explicit witness maps from pattern nodes to host nodes,
- report support in terms of distinct host theorems and valid embeddings.

Without witness maps, stage 3 cannot be correct.

## Priority 3: Rebuild stage 3 only after witness-preserving stage 2 exists

The collapsibility checker must evaluate:

- one host theorem graph,
- one pattern,
- one concrete embedding witness,

and then test the paper's collapsibility conditions on that exact embedding.

## Priority 4: Add visualization

At minimum generate:

- TDG diagrams for 5 manually checked proofs,
- top motif diagrams,
- collapsible vs non-collapsible examples,
- support histograms / theorem coverage plots.

## Priority 5: Add stage-gate supervision

Do not advance stages automatically. Require a human/agentic signoff after:

- TDG correctness review,
- embedding correctness review,
- collapsibility correctness review.

## Final Conclusion

The Minimax 2.5 run was useful as an exploratory prototype and corpus-preparation effort. It probably surfaced some real recurring tactic motifs in mathlib. But it did **not** yet deliver a faithful implementation of the paper's central machinery, and its stage-3 conclusions should not be trusted as evidence of collapsible embeddings.

The right framing is:

- **good scaffolding,**
- **some real signal,**
- **core methodological gap remains.**

That means the run was worth doing, but it should be treated as a first supervised draft rather than a successful replication or transfer of the paper's method.
