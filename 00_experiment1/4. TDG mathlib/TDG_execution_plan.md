# TDG Execution Plan for mathlib

## Meta Adjustment After Supervising The First Agent Run

The first external run in this folder produced useful scaffolding but failed mainly because stage 2 and stage 3 moved ahead of a trustworthy stage 1. This plan therefore has one additional non-negotiable constraint:

- **All later stages must preserve explicit witness structure and must not infer more graph semantics than stage 1 can justify.**

Practical consequences:

- stage 1 should prefer conservative edges over aggressive edge recovery,
- stage 2 must store canonical candidate graphs plus explicit witness mappings,
- stage 3 must operate only on concrete candidate + witness + host triples,
- and no corpus-wide claims should be made from stage 2 or 3 until stage 1 examples survive manual inspection.

This is not a cosmetic adjustment. It is the main lesson learned from the previous failure.

## Purpose

This document is a concrete execution plan for an AI agent to implement the paper:

- `E:\LEAN-experiments\00_experiment1\4. TDG mathlib\Automated Discovery of Tactic Libraries for Interactive Theorom Proving.pdf`

but adapted to the local Lean/mathlib corpus.

The implementation target is:

1. Construct **Tactic Dependency Graphs (TDGs)** for mathlib tactic proofs.
2. Validate TDGs against raw local trace data with **manual agentic checking**.
3. Identify **isomorphic embeddings** across the corpus.
4. Identify **collapsible embeddings** across the corpus.
5. Optionally continue to tactic candidate synthesis, proof refactoring, corpus compression, and downstream automation experiments, following the paper.

This plan is intentionally explicit. The agent should not need to guess:

- what data to use,
- how to stage the work,
- what must be verified manually before moving on,
- what plots to generate,
- or what “non-cheating” validation means for this project.

---

## Paper Concepts To Preserve

The implementation should preserve the paper’s core abstractions and sequencing:

1. **Proof-state / tactic trace view**
2. **TDG construction**
3. **Isomorphic embedding detection**
4. **Collapsible embedding detection**
5. **Refactoring-valid tactic candidate extraction**
6. **Library learning / compression objective**
7. **Optional downstream use in proof automation**

The most important paper definitions to preserve operationally are:

- **TDG of proof script**
- **Tactic TDG**
- **Isomorphic embedding**
- **Collapsible embedding**

The paper’s refactoring and tactic-learning algorithms are later-stage targets. The immediate must-have stages are TDG construction plus embedding analysis, but the agent should structure the code so later stages can be added without rewriting stage 1.

---

## Local Data Inventory

## Primary mathlib data to use

These are the main local inputs. Yes: `E:\LEAN-experiments\00_experiment1\jsons` is the primary data folder and should be treated as the default source of truth.

- `E:\LEAN-experiments\00_experiment1\jsons\traced_theorems_unified_v2.jsonl`
  - Main theorem-level proof trace dataset.
  - Contains theorem metadata, tactic proof text, per-tactic before/after states, contexts, and resolved premises.
  - This is the core input for stage 1 TDG construction.

- `E:\LEAN-experiments\00_experiment1\jsons\corpus.jsonl`
  - Premise / declaration inventory with source code and source positions.
  - Needed for premise metadata, theorem lookup, and source-level spot checking.

- `E:\LEAN-experiments\00_experiment1\jsons\corpus_code_index.json`
  - Auxiliary code index for fast lookup into the corpus.
  - Useful for joining theorem names to code snippets and file locations.

- `E:\LEAN-experiments\00_experiment1\jsons\premise_index_v2.json`
  - Global premise index.
  - Useful for normalizing references and verifying premise-name resolution coverage.

- `E:\LEAN-experiments\00_experiment1\jsons\theorem_stats_v2.json`
  - Corpus summary.
  - Confirms rough scale:
    - `total_theorems = 126,797`
    - `tactic_proofs = 54,477`
    - `term_proofs = 72,315`
    - `total_tactics = 276,014`
    - `total_premises = 784,726`

## Supporting local notes and scripts that should inform the implementation

- `E:\LEAN-experiments\00_experiment1\construction_notes_for_jsons\construction_notes_traced_theorems_unified_v2.md`
  - Explains how the unified traced theorem JSONL was built.
  - Important for understanding what the `tactics`, `premises`, and `all_premises` fields really mean.

- `E:\LEAN-experiments\00_experiment1\construction_notes_for_jsons\premise_inclusion_analysis.md`
  - Clarifies what gets included in theorem-premise graphs.
  - Useful when deciding whether theorem-level premise links should become TDG annotations or separate auxiliary edges.

- `E:\LEAN-experiments\00_experiment1\construction_notes_for_jsons\term_proofs_explained.md`
  - Confirms term proofs are structurally different and should be excluded in the initial TDG pass.

- `E:\LEAN-experiments\00_experiment1\01_make_internal_proof_DAGs.py`
  - Existing script for within-proof tactic/state graph extraction and visualization.
  - Not the final TDG implementation, but useful as a prior reference for local proof-state parsing and graph rendering.

- `E:\LEAN-experiments\00_experiment1\01_minimum_description\01_within_proof_DAG_pipeline_v3_claude.py`
  - Likely contains additional graph-construction logic worth mining.

- `E:\LEAN-experiments\00_experiment1\03_future_prediction\lab_notebook_gpt.md`
  - Recent notebook work is not directly about TDGs, but it is a model for how to keep a rigorous running notebook and stage outputs.

## Other data that may be required

The JSONs are enough to begin TDG construction and embedding mining, but they may not be enough for full end-to-end Lean replay and proof refactoring validation.

The agent must explicitly check for:

- the exact **mathlib source checkout** corresponding to the extracted traces,
- the corresponding **Lean toolchain version**,
- and, if available, the **LeanDojo traced repository** or equivalent traced environment.

Why this matters:

- Stage 1 TDG construction can proceed from `traced_theorems_unified_v2.jsonl`.
- Full stage 4 refactoring validation is much stronger if the agent can replay refactored proofs in Lean.
- If replay infrastructure is absent, the agent should still complete stages 1-3 and mark replay as a blocked-but-separate later stage.

---

## Recommended Output Folder Structure

All implementation for this analysis should live under:

- `E:\LEAN-experiments\00_experiment1\4. TDG mathlib`

Recommended subfolders:

- `data\`
  - Cached parsed theorem records
  - TDGs
  - Node / edge tables
  - Sample sets for manual validation
  - Candidate embeddings
  - Collapsible embedding tables

- `figs\`
  - Paper-style proof/TDG figures
  - Corpus summary plots
  - Embedding-frequency plots
  - Compression / library-learning plots if later stages are implemented

- `notebooks\`
  - Running markdown notebook or audit logs

- `scripts\`
  - Stage-specific scripts

- `reports\`
  - Manual validation reports
  - Error analyses

If the agent keeps everything flat instead of using subfolders, it will become hard to audit. Avoid that.

---

## Global Execution Rules

## Rule 1: Start with tactic proofs only

Initial implementation scope must be:

- `proof_type == "tactic"`
- nonempty `tactics` list

Do not include term proofs in the first pass.

Reason:

- The paper is about tactic-style proofs.
- Local data for term proofs is not represented at the same per-step resolution.

## Rule 2: Always keep theorem-level raw evidence

For every derived TDG, the implementation must preserve links back to:

- theorem full name,
- file path,
- proof text,
- tactic index,
- raw tactic string,
- raw `state_before`,
- raw `state_after`,
- raw resolved premises.

No derived graph object should lose its provenance.

## Rule 3: Manual validation is mandatory between major stages

The agent must not move from:

- stage 1 to stage 2,
- or from stage 2 to stage 3,

without producing and checking a manual validation sample.

## Rule 4: Keep a persistent notebook

The agent should maintain a markdown notebook in this folder, similar in spirit to the notebooking style used elsewhere in the project. Every stage should log:

- what was attempted,
- what assumptions were made,
- what errors were found,
- what was corrected,
- and what acceptance criteria were met.

---

# Stage 0: Corpus Audit And Environment Confirmation

## Goal

Confirm the local data is sufficient and understand the exact schema before any TDG logic is written.

## Inputs

- `jsons\traced_theorems_unified_v2.jsonl`
- `jsons\corpus.jsonl`
- `jsons\corpus_code_index.json`
- `jsons\premise_index_v2.json`
- `jsons\theorem_stats_v2.json`
- local construction notes listed above
- paper PDF

## Required actions

1. Read the paper sections on:
   - proof state
   - tactic definition
   - proof script
   - TDG
   - tactic TDG
   - isomorphic embedding
   - collapsible embedding
   - refactoring algorithm
   - grammar-guided learning

2. Inspect several hundred records from `traced_theorems_unified_v2.jsonl`.

3. Confirm the semantics of fields:
   - `full_name`
   - `file`
   - `statement`
   - `proof_text`
   - `tactics`
   - `all_premises`
   - `metrics`
   - `quality`

4. Confirm per-tactic available fields:
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

5. Quantify how many theorem records are usable for TDG construction after filtering for:
   - tactic proof
   - nonempty tactics
   - parseable before/after states

6. Check whether exact mathlib source and Lean toolchain are locally available for replay.

## Deliverables

- `reports\00_data_audit.md`
- `data\00_corpus_schema_summary.json`
- `data\00_sample_theorem_records.jsonl`

## Manual validation checkpoint

The agent must manually inspect at least:

- 25 random tactic-proof theorem records
- 10 edge-case records
  - very short proofs
  - very long proofs
  - many-subgoal proofs
  - proofs with `case`, `constructor`, `simp`, `aesop`, `rw`, `have`, `refine`, `exact?`, `all_goals`, or tactical combinators if present

The audit report must explicitly list what kinds of tactics are common and what kinds are hard to model.

## Acceptance criteria

- The agent can state exactly which local files are primary inputs.
- The agent can describe the schema without guessing.
- The agent knows whether replay is possible now or deferred.

---

# Stage 1: TDG Construction For mathlib

## Goal

Construct paper-style TDGs for Lean/mathlib tactic proofs from the local trace corpus.

## Core adaptation challenge

The paper’s implementation uses Rocq/SerAPI and explicit tactic signatures. For mathlib, the agent must infer an equivalent dependency representation from Lean trace data.

The plan should preserve the paper’s spirit:

- nodes are tactic applications,
- edges record dependence of later tactic inputs on earlier tactic outputs,
- irrelevant syntactic variation is abstracted away,
- branch structure is preserved enough to support later embedding analysis.

## Stage 1A: Define the local TDG schema

Each theorem TDG should include:

- theorem metadata
  - theorem full name
  - file
  - proof text
  - source positions if available

- node table
  - `node_id`
  - `tactic_index`
  - normalized tactic name
  - raw tactic string
  - annotated tactic string
  - goals before / after
  - branch metadata
  - theorem provenance

- edge table
  - `src_node_id`
  - `dst_node_id`
  - dependency type
  - label
  - confidence
  - evidence

- optional special nodes for tactic-TDG conversion later
  - `in`
  - `out`

## Stage 1B: Normalize tactic invocations

The agent must define a normalization function for Lean tactics.

At minimum store:

- raw tactic text
- head tactic name
- normalized head tactic name

Examples of likely normalization rules:

- strip arguments from the label used for node matching
- separate raw text from normalized name
- keep combinators visible as tactic kinds when they are atomic in the trace
- if the trace already decomposes `;`, preserve decomposed steps
- otherwise, explicitly record “compound tactic” as a separate category

Do not over-normalize at first. Keep enough information to revisit decisions later.

## Stage 1C: Parse proof states

For each tactic step, parse:

- `state_before`
- `state_after`

into structured objects:

- goals
- hypotheses per goal if recoverable
- active target proposition
- local names

The parser should:

- preserve the raw string,
- produce a canonical normalized form for comparison,
- and compute goal/hypothesis diffs.

Important:

- Parsing should be loss-aware.
- If a field cannot be extracted robustly, mark it unknown rather than inventing structure.

## Stage 1D: Infer actual inputs and outputs of each tactic step

This is the most important part of stage 1.

For each tactic application, infer:

- consumed goal(s)
- produced goal(s)
- introduced hypothesis names
- discharged goals
- reused local hypotheses
- referenced global premises

Recommended operational approximation:

1. Use `state_before` and `state_after` to detect:
   - goals removed
   - goals preserved
   - goals introduced

2. Use the raw tactic text plus parsed names to detect likely local inputs:
   - hypothesis names referenced in the tactic text
   - explicit theorem/premise names from `premises`

3. Use goal-state differencing to identify outputs:
   - new goals
   - new hypotheses
   - rewritten targets

4. Attach confidence scores:
   - high confidence when explicit textual or premise evidence exists
   - lower confidence when inferred only from state differencing

## Stage 1E: Build the TDG edges

The implementation must create edges at least for:

- goal-flow dependencies
  - a tactic produces a subgoal later consumed by another tactic

- hypothesis-flow dependencies
  - a tactic introduces a local hypothesis later used by another tactic

- premise-use annotations
  - global theorem/definition references used at a tactic

Recommended edge label taxonomy:

- `goal_to_goal`
- `goal_to_hyp`
- `hyp_to_goal`
- `hyp_to_hyp`
- `premise_use`
- `branch_control`

The exact taxonomy can be refined later, but it must be explicit and documented.

## Stage 1F: Preserve DAG-ness

The resulting TDG must be a DAG.

If the first implementation yields cycles, the agent must diagnose why. Possible causes:

- incorrect goal matching across branches,
- over-aggressive state reuse,
- local-name aliasing,
- or conflation of preserved goals with newly produced goals.

Cycles are a debugging signal here, not an acceptable final product.

## Stage 1G: Output files

Produce at least:

- `data\stage1_tdg_nodes.parquet`
- `data\stage1_tdg_edges.parquet`
- `data\stage1_tdg_by_theorem.pkl`
- `data\stage1_tdg_schema.md`

If parquet is inconvenient, JSONL plus pickle is acceptable, but columnar tables are preferred for analysis.

---

# Stage 1 Manual Validation: Agentic Raw-Data Check

## Goal

Ensure the TDGs are faithful to the local trace data before any embedding mining.

## Required validation sample

The agent must sample at least:

- 50 theorem proofs total
- stratified by proof size:
  - 10 tiny
  - 20 medium
  - 20 large

Within those, inspect at least:

- 200 tactic nodes
- 300 edges

## Manual checks for each sampled theorem

For each sampled theorem:

1. Compare the raw proof text against the reconstructed node sequence.
2. Check whether each node corresponds to a real tactic step.
3. Check whether `state_before` and `state_after` differences are sensible.
4. Check whether branch splits are represented correctly.
5. Check whether key dependencies are real:
   - introduced hypothesis later consumed
   - subgoal created then solved
   - premise use aligns with tactic text

## Required report

Create:

- `reports\stage1_manual_validation.md`

This report must include:

- examples that are clearly correct,
- examples that are clearly wrong,
- common failure modes,
- fixes applied,
- before/after examples of corrected TDGs.

## Hard acceptance gate

Do not proceed to stage 2 until:

- sampled node alignment is satisfactory,
- sampled edge alignment is satisfactory,
- and the report explicitly says which edge types are still noisy.

Suggested threshold:

- node correctness on manual sample: `>= 95%`
- high-confidence edge correctness on manual sample: `>= 90%`

If not achieved, iterate stage 1.

---

# Stage 1 Visualization Requirements

## Goal

Produce paper-style figures immediately after TDG construction.

The agent must recreate figures in the style of the paper, especially examples like:

- syntactically different proofs sharing a TDG
- refactoring of a proof using a learned tactic
- three-panel diagrams with “original proof / learned tactic / refactored proof”

## Mandatory plot families

1. **Single-proof TDG examples**
   - selected clean proofs from mathlib
   - show node labels and edge labels

2. **Pair-of-proofs with same or near-same TDG**
   - analogous to paper Figures 1 and 2

3. **Refactoring triptych**
   - analogous to paper Figure 11
   - panel (a): original proof TDG
   - panel (b): extracted tactic TDG
   - panel (c): refactored proof TDG

4. **Corpus summary plots**
   - proof size distribution
   - number of goals per theorem
   - tactic frequency
   - TDG node-count / edge-count distribution

## Style guidance for paper-like plots

Replicate the visual language, not necessarily the exact font:

- horizontal left-to-right DAG layouts
- light blue tactic boxes
- light circular or elliptical special nodes for state entry/exit if used
- visible edge labels
- small-multiple panels
- publication-quality SVG or PDF output

Recommended tooling:

- Graphviz for DAG layout
- matplotlib for composed figures
- SVG export preferred

Required outputs:

- `figs\stage1_single_proof_examples\...`
- `figs\stage1_pair_examples\...`
- `figs\stage1_refactoring_triptychs\...`
- `figs\stage1_corpus_summary\...`

---

# Stage 2: Isomorphic Embedding Mining Across Corpus

## Goal

Find common isomorphic TDG subgraphs across the mathlib corpus.

This stage corresponds to the paper’s “common subgraph” discovery step, before collapsibility filtering.

## Inputs

- validated stage 1 TDGs

## Stage 2A: Define candidate subgraph representation

A candidate must specify:

- node multiset with tactic labels
- edge set with dependency labels
- a designated root if needed for expansion
- frequency statistics
- witness mappings into theorem TDGs

## Stage 2B: Decide matching granularity

The agent must decide and document whether matching uses:

- tactic head names only,
- tactic head names plus coarse tactic class,
- or tactic head names plus selected edge labels.

Recommended first pass:

- node labels: normalized tactic head
- edge labels: preserved dependency label pairs
- no theorem names or literal proposition strings in matching labels

Reason:

- matching should discover reusable proof patterns, not theorem-specific identities

## Stage 2C: Generate candidates

The paper uses grammar-guided expansion. The Lean/mathlib implementation should be structured to support this, even if the first pass uses a simpler method.

Recommended implementation order:

1. Start with single-node frequent tactic seeds.
2. Learn local expansion rules from observed tactic-to-tactic dependency patterns.
3. Expand candidates by adding:
   - one new node plus dependency edges
   - or one new dependency to an existing node pair if needed

This should mimic the paper’s graph-grammar idea rather than brute-forcing arbitrary subgraphs.

## Stage 2D: Compute witnesses

For each candidate subgraph, store explicit witness mappings:

- candidate node -> theorem TDG node

Use an injective mapping as in the paper’s isomorphic embedding definition.

At this stage, do not yet require collapsibility.

## Stage 2E: Frequency and support thresholds

Minimum first-pass thresholds:

- support at least 2 theorems
- preferably also report support at:
  - 3+
  - 5+
  - 10+

If search space explodes, add constraints such as:

- candidate size cap for first pass
- beam search by support or compression proxy
- grammar-based pruning

## Deliverables

- `data\stage2_isomorphic_candidates.parquet`
- `data\stage2_isomorphic_witnesses.parquet`
- `reports\stage2_embedding_mining.md`

---

# Stage 2 Manual Validation: Witness Check

## Goal

Verify that mined isomorphic embeddings are real and not artifacts of over-normalization or noisy TDGs.

## Required manual sample

Inspect at least:

- 30 candidate subgraphs
- with at least 3 witness theorems each where possible

For each candidate:

1. Render the candidate subgraph.
2. Render at least 2 witness embeddings inside original theorem TDGs.
3. Compare the raw proof snippets.
4. Judge whether the match is semantically meaningful.

## Required report

- `reports\stage2_manual_embedding_validation.md`

This report must classify false positives into categories:

- tactic-name-only accidental matches
- branch-shape mismatches
- edge-label mismatches
- state-differencing mistakes from stage 1

## Acceptance criteria

Proceed to stage 3 only if manually checked embeddings are mostly meaningful and reusable.

Suggested threshold:

- meaningful embedding rate on sample: `>= 80%`

If lower, revise normalization or edge labels before continuing.

---

# Stage 3: Collapsible Embedding Identification

## Goal

Filter stage 2 embeddings to the subset that satisfies the paper’s collapsibility condition.

This is the key correctness filter for tactic extraction/refactoring.

## Requirements

The implementation must check both conditions from the paper operationally:

1. **Path closure**
   - if two matched nodes have an intermediate path node in the host TDG, that intermediate node must also lie inside the embedding

2. **Internal edge completeness**
   - if host TDG contains an edge between two matched host nodes, the candidate must also contain the corresponding edge

These should be checked explicitly, not approximated vaguely.

## Inputs

- stage 2 candidate graph
- witness mapping
- host theorem TDG

## Outputs

For each witness:

- `is_collapsible`
- failure reason if false
  - `intermediate_path_violation`
  - `missing_internal_edge`
  - `other`

## Deliverables

- `data\stage3_collapsible_candidates.parquet`
- `data\stage3_collapsible_witnesses.parquet`
- `reports\stage3_collapsibility.md`

---

# Stage 3 Manual Validation: Positive And Negative Cases

## Goal

Verify that the collapsibility filter is behaving like the paper, not just passing everything or rejecting everything.

## Required sample

Manually inspect:

- 20 accepted embeddings
- 20 rejected embeddings

For each:

1. draw the candidate subgraph and host context,
2. inspect the witness mapping,
3. confirm whether contraction into one tactic call is logically plausible,
4. confirm the rejection reason if rejected.

## Required report

- `reports\stage3_manual_collapsibility_validation.md`

This report must include:

- at least 5 clean positive examples
- at least 5 clean negative examples
- discussion of edge cases

## Acceptance criteria

Proceed only if the agent is confident collapsibility is being enforced correctly.

---

# Stage 4: Tactic Candidate Extraction And Lean-Oriented Refactoring

## Goal

Translate collapsible common subgraphs into candidate custom tactics and refactor proofs with them.

This is where the mathlib adaptation becomes more delicate.

## Important warning

For Lean/mathlib, fully executable tactic synthesis may be harder than in the Rocq paper because:

- tactic syntax differs,
- local binder and goal naming conventions differ,
- and not every abstract subgraph will map cleanly back to a compact Lean tactic block.

Therefore stage 4 should be split into two submodes:

1. **Abstract refactoring**
   - TDG-level contraction only
2. **Executable Lean refactoring**
   - generate Lean tactic definitions and refactored proof text

The agent should complete abstract refactoring first.

## Stage 4A: Abstract tactic representation

For each accepted collapsible candidate, define:

- tactic name
- formal inputs
- formal outputs
- tactic body as ordered tactic sequence
- witness theorems where it applies

## Stage 4B: Induced proof reconstruction

The paper notes that a TDG induces many topological orderings subject to branch constraints.

The Lean implementation must:

- track branch boundaries caused by goal splits,
- ensure tactics solving the same subgoal remain in the same branch,
- linearize the contracted TDG into a valid tactic script ordering.

## Stage 4C: Refactor theorem proofs

For each witness theorem:

1. contract the matched subgraph,
2. replace it with one custom tactic node,
3. reconstruct the refactored proof script,
4. store the before/after scripts.

## Stage 4D: Replay validation if environment exists

If exact mathlib source + Lean toolchain are available:

1. insert learned tactic definitions before affected theorem(s),
2. write refactored theorem file(s),
3. run Lean to validate,
4. record pass/fail.

If replay is not available:

- still produce abstract refactorings and mark executable replay as pending.

## Deliverables

- `data\stage4_tactic_candidates.jsonl`
- `data\stage4_refactored_proofs.jsonl`
- `reports\stage4_refactoring.md`

---

# Stage 5: Library Learning / Compression Search

## Goal

Move from “find one reusable pattern” to “assemble a tactic library that compresses the corpus.”

This follows the paper’s later tactic-learning loop.

## Requirements

Implement at least the following ideas:

1. effectiveness / compression metric
2. candidate search
3. grammar-guided expansion
4. upper-bound pruning
5. iterative library growth:
   - learn best tactic
   - refactor corpus
   - repeat

## Recommended metrics

Track:

- candidate size
- number of embeddings
- number of disjoint collapsible embeddings
- estimated compression gain
- realized compression after refactoring

## Deliverables

- `data\stage5_library_candidates.parquet`
- `data\stage5_selected_library.json`
- `reports\stage5_library_learning.md`

---

# Stage 6: Evaluation Protocol For mathlib

## Goal

Evaluate whether the learned tactic library is useful on held-out mathlib proofs.

## Recommended evaluation questions

Mirror the paper as closely as the local setup allows:

- How many tactics are learned?
- How large are they?
- How often can they be used?
- How much proof compression do they achieve on held-out proofs?
- How data efficient is the learner?
- What is the runtime impact of grammar learning and pruning?

## Train/test split

Recommended first split:

- 65% training
- 35% test

Also run:

- 25 / 75
- 40 / 60
- 50 / 50
- 80 / 20

## Evaluation outputs

- tactic counts
- average tactic size
- max tactic size
- total usage count
- compression power
- learned-library growth curves
- runtime curves

## Deliverables

- `reports\stage6_eval.md`
- `figs\stage6_eval\...`

---

# Stage 7: Optional Downstream Automation Integration

## Goal

If replay works and a Lean automation agent exists, test whether learned tactics improve automation.

## If implemented

Follow the paper’s basic pattern:

1. refactor proofs using learned tactics,
2. build an index of available custom tactics before each theorem,
3. extract one or more usage examples per tactic,
4. provide definitions plus examples to the proving agent,
5. compare success with and without learned tactics.

This is optional for the first milestone. Do not block stages 1-6 on this.

---

# Exact Manual Verification Policy Between Stages

The agent must perform manual verification after:

- stage 0 audit
- stage 1 TDG construction
- stage 2 isomorphic embedding mining
- stage 3 collapsibility filtering
- stage 4 refactoring

For each checkpoint, the agent must create:

- one markdown report,
- one machine-readable sample table,
- and one figure bundle of representative examples.

The manual checks are not optional because:

- the stage 1 data is inferred from traces, not directly given as TDGs,
- Lean tactic semantics differ from the Rocq environment in the paper,
- and false positives in embeddings will compound in later stages.

---

# Plot Plan

## Mandatory figures to generate

### Figure family A: raw-to-TDG examples

- theorem proof text snippet
- tactic sequence
- resulting TDG

### Figure family B: proof-pair shared structure

- two syntactically different mathlib proofs
- one common subgraph / one common TDG pattern

### Figure family C: three-panel refactoring figure

Exactly analogous in spirit to the paper image:

- `(a)` original proof TDG
- `(b)` learned tactic TDG
- `(c)` refactored proof TDG

### Figure family D: corpus statistics

- proof sizes
- tactic frequencies
- TDG sizes
- candidate support distribution

### Figure family E: later-stage evaluation

- compression by domain slice
- number of tactics learned
- runtime curves
- ablation plots if grammar/pruning is implemented

---

# Domain Slicing Recommendation For mathlib

mathlib is much larger and more heterogeneous than the paper’s Rocq domains. Do not start with the full corpus for all experiments.

Recommended slicing strategy:

1. global exploratory run on all tactic proofs
2. then domain-restricted runs using file prefixes or namespaces, for example:
   - `Mathlib/Algebra/...`
   - `Mathlib/Order/...`
   - `Mathlib/Data/...`
   - `Mathlib/Topology/...`
   - `Mathlib/MeasureTheory/...`

Why:

- tactic patterns are more likely to repeat within subdomains,
- search is cheaper,
- manual validation is easier,
- and learned tactics are more interpretable.

The agent should produce both:

- whole-corpus statistics
- and namespace/domain-sliced statistics

---

# Known Risks And How To Handle Them

## Risk 1: Goal matching across before/after states is noisy

Mitigation:

- canonicalize goals
- use exact and fuzzy matching
- keep confidence scores
- prefer high-confidence edges in early embedding mining

## Risk 2: Local hypothesis names are unstable

Mitigation:

- preserve raw names
- also compute normalized hypothesis signatures based on proposition text where possible

## Risk 3: Compound Lean tactics are hard to decompose

Mitigation:

- first treat them atomically
- only decompose when trace structure clearly supports it

## Risk 4: Target-conditioned patterns become too generic or too specific

Mitigation:

- tune node-label normalization
- use domain slicing
- require minimum support

## Risk 5: Full Lean replay is unavailable

Mitigation:

- separate abstract TDG validation from executable refactoring validation
- do not block early stages on replay

---

# First Concrete Milestone

The first milestone should end when the following are complete:

1. audited mathlib trace corpus
2. stage 1 TDG construction on tactic proofs
3. stage 1 manual validation report
4. stage 1 paper-style figures
5. stage 2 isomorphic embedding mining
6. stage 2 manual validation report
7. stage 3 collapsible embedding mining
8. stage 3 manual validation report

At that point, the project has faithfully reproduced the conceptual core of the paper for mathlib.

---

# Minimal Script Roadmap

Recommended script names:

- `scripts\00_audit_mathlib_tdg_inputs.py`
- `scripts\01_build_mathlib_tdgs.py`
- `scripts\02_validate_stage1_samples.py`
- `scripts\03_plot_stage1_examples.py`
- `scripts\04_mine_isomorphic_embeddings.py`
- `scripts\05_validate_stage2_embeddings.py`
- `scripts\06_compute_collapsible_embeddings.py`
- `scripts\07_validate_stage3_collapsibility.py`
- `scripts\08_refactor_with_candidate_tactics.py`
- `scripts\09_plot_refactoring_examples.py`
- `scripts\10_learn_tactic_library.py`
- `scripts\11_evaluate_library.py`

Each script should:

- accept explicit input/output paths,
- write logs,
- and save machine-readable outputs.

---

# Final Instruction To The Agent

Do not jump directly to corpus-wide tactic learning.

The correct order is:

1. understand the paper,
2. audit the local Lean/mathlib data,
3. build TDGs,
4. manually verify TDGs,
5. mine isomorphic embeddings,
6. manually verify embeddings,
7. enforce collapsibility,
8. manually verify collapsibility,
9. only then move to refactoring and library learning.

If any stage produces outputs that do not survive manual inspection, stop, revise, and rerun before continuing.
