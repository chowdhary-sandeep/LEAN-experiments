# Lab Notebook GPT

## 2026-03-13 20:xx CET - Entry 1

Objective for this pass:

- Analyze the project goals and the actual outputs in `03_future_prediction`.
- Judge how successful the experiment was, with emphasis on `r=0` as the non-cheating condition.
- Explain, if prediction failed, whether the reason looks structural in the theorem network, feature-set limited, evaluation-limited, or fundamentally hard.
- Save intermediate results into `data/` and `figs/`.

Repository inspection:

- Found one main script: `01_future_prediction_pipeline_v2.py`.
- Found one written summary: `01_future_pipeline_summary.md`.
- Found cached experiment objects in `data/`.
- Found generated plots in `figs/`.

Immediate observations from the written summary:

- Graph size after DAG cleaning: about 99k nodes and 358k edges.
- FVS removal is tiny: 42 nodes removed, so cycle-cleaning is not driving the result.
- Main reported claim:
  - `r=0`: outdegree / any-child prediction is moderately successful.
  - `r=0`: descendant-count prediction is poor.
  - `r=1` and `r=2`: descendant prediction improves sharply when immediate children or grandchildren are revealed.

Protocol checks in code:

- `strict_past_seen_graph = true` in the JSON config, so `r=0` uses only nodes with depth `< d` in the seen graph.
- That means same-depth leakage is intentionally blocked.
- `r=1` adds `k1`, which is effectively direct-child count.
- `r=2` adds grandchild count.

First concern noted:

- The script uses a single random 80/20 split inside each frontier depth.
- There is no repeated cross-validation or confidence interval in the original pipeline output.
- Deep frontiers have small sample sizes (`d=20` only 152 nodes, `d=30` only 31 nodes), so some headline numbers may be unstable.

## 2026-03-13 20:xx CET - Entry 2

Target-structure diagnostics computed directly from cached data:

- At `d=5`:
  - `Y1` zero fraction: `0.494`
  - `Y1` mean: `145.67`, median: `1`, p99: `2136.8`, max: `110483`
  - `Y2` zero fraction: `0.494`
  - `Y2` mean: `1.17`, median: `1`, p99: `11`, max: `119`
- At `d=10`:
  - `Y1` zero fraction: `0.433`
  - `Y1` mean: `170.14`, median: `1`, p99: `4386.6`, max: `41472`
  - `Y2` zero fraction: `0.433`
  - `Y2` mean: `1.21`, median: `1`, p99: `9`, max: `55`
- At `d=20`:
  - `Y1` zero fraction: `0.388`
  - `Y1` mean: `43.54`, median: `1`, p99: `752.82`, max: `831`
  - `Y2` zero fraction: `0.388`
  - `Y2` mean: `1.13`, median: `1`, p99: `6.49`, max: `7`

Interpretation:

- `Y1` is extremely heavy-tailed.
- Median frontier theorem has almost no downstream footprint, but a very small number of nodes explode into huge descendant trees.
- This already makes rank prediction hard at `r=0`, because the target is dominated by later branching cascades rather than by a smooth local signal.

Important structural identity:

- In a DAG, `Y1 > 0` if and only if `Y2 > 0`.
- So the two classification tasks `I[Y1>0]` and `I[Y2>0]` are actually identical in this setup.
- The pipeline even prints a warning that the labels are 100% identical.
- Scientifically, the only distinct questions are:
  - Can we predict whether a theorem gets used at all?
  - Conditional on getting used, can we predict how large its downstream subtree becomes?

## 2026-03-13 20:xx CET - Entry 3

Coupling between immediate future and long-run future:

All nodes:

- `Spearman(Y1, Y2)` is very high, from about `0.83` to `0.95`.
- This is partly driven by the shared zero/nonzero boundary.

Positive-case only (`Y1 > 0`):

- `Spearman(Y1, Y2)`:
  - `d=5`: `0.608`
  - `d=10`: `0.571`
  - `d=20`: `0.333`
  - `d=30`: `0.305`
- `Spearman(Y1, grandchild_count)`:
  - `d=5`: `0.887`
  - `d=10`: `0.877`
  - `d=20`: `0.786`
  - `d=30`: `0.790`

Interpretation:

- Immediate children carry some information about eventual downstream size, but not enough to determine it cleanly.
- Grandchildren carry much stronger information.
- This is consistent with the original experiment:
  - `r=1` gives moderate Y1 performance.
  - `r=2` gives strong Y1 performance.

Structural reading:

- The dominant uncertainty is not "will this theorem get used immediately?"
- The dominant uncertainty is "will those immediate children themselves keep reproducing?"
- That is a branching-process style uncertainty, and it only becomes visible around the second future layer.

## 2026-03-13 20:xx CET - Entry 4

Direct `r=0` feature-target correlations computed from the real feature set:

For `d=5`, the strongest univariate Spearman correlations with `Y1` or `Y2` are small, roughly `|rho| <= 0.12`.
For `d=10`, the same story holds, again roughly `|rho| <= 0.13`.
For `d=20`, correlations rise a bit but still only to about `|rho| <= 0.24`.

Examples repeatedly near the top:

- `indeg_seen`
- `upstream_2hop_edge_density`
- `upstream_2hop_node_count`
- `parentset_cooccurrence_max`
- `parent_descendant_count_seen_max`
- `parent_diversity`
- `parent_module_entropy`

Interpretation:

- The `r=0` feature set does contain signal, but it is weak and diffuse.
- No single upstream descriptor is strongly coupled to eventual downstream impact.
- That matches the moderate success on `Y2 > 0` and the failure on `Y1`.

## 2026-03-13 20:xx CET - Entry 5

Repeated-split stability check for `r=0` using 10 random splits per depth:

- `d=5`:
  - `Y2` PR-AUC mean `0.557`, std `0.017`, min `0.535`, max `0.590`
  - `Y1` Spearman mean `0.079`, std `0.064`, min `-0.040`, max `0.177`
- `d=10`:
  - `Y2` PR-AUC mean `0.611`, std `0.054`, min `0.519`, max `0.660`
  - `Y1` Spearman mean `-0.087`, std `0.088`, min `-0.179`, max `0.071`
- `d=20`:
  - `Y2` PR-AUC mean `0.675`, std `0.075`, min `0.561`, max `0.790`
  - `Y1` Spearman mean `-0.088`, std `0.216`, min `-0.463`, max `0.331`

Interpretation:

- The positive `r=0` result for `Y2 > 0` is real, though moderate rather than strong.
- The `Y1` result at `r=0` is not just weak; it is unstable around zero.
- At `d=20`, a single split can look mildly positive or strongly negative because the sample is small.
- This weakens any claim that `r=0` descendant prediction works even a little.

Current working conclusion:

- You succeeded on the "used at all?" question.
- You did not succeed on the "large downstream family?" question under the clean non-cheating regime.
- The failure looks mostly structural rather than just an optimizer issue.

## 2026-03-13 21:xx CET - Entry 6

Artifacts saved during this analysis:

Data:

- `data/intermediate_analysis_summary.md`
- `data/intermediate_analysis_manifest.json`
- `data/intermediate_target_structure.csv`
- `data/intermediate_y1_by_y2_bucket.csv`
- `data/intermediate_feature_correlations_r0.csv`
- `data/intermediate_feature_correlations_r0_summary.csv`
- `data/intermediate_repeated_split_metrics_r0.csv`
- `data/intermediate_repeated_split_summary_r0.csv`
- `data/intermediate_y2_feature_importance_r0.csv`
- `data/intermediate_y2_feature_importance_r0_summary.csv`

Figures:

- `figs/intermediate_target_and_stability.png`
- `figs/intermediate_y2_feature_importance_r0.png`

Consolidated scientific judgment:

1. On the broad goal "can I predict whether a theorem will have many children downstream?":

- In the strict non-cheating regime `r=0`, the answer is mostly no for total downstream family size (`Y1`).
- You can predict a weaker event: whether the theorem gets used at all (`Y2 > 0`, equivalently `Y1 > 0`).
- That weaker prediction is real but only moderate.

1. On success vs failure:

- Successful:
  - DAG cleaning and depth framing look sound.
  - The theorem graph is almost acyclic already, so the experiment is not being distorted by cycle repair.
  - `r=0` features do carry enough signal to predict first-step usage moderately above chance.
- Unsuccessful:
  - `r=0` does not robustly predict descendant magnitude.
  - Repeated-split stability puts `Y1` Spearman near zero or negative on average.
  - Any mild positive result on a single split is not reliable evidence of true predictability.

1. Why failure looks structural:

- The long-run target is generated by branching after the frontier node.
- Parent-side features are upstream summaries; they do not observe whether the first children will themselves become fertile.
- Immediate children help somewhat, and grandchildren help a lot. That pattern is exactly what we would expect if downstream impact is decided by future branching rather than by upstream ancestry alone.
- In other words, the missing information is not subtle: it is literally the first and second future generations.

1. Why this is probably not "impossible" in principle:

- Once `r=1` and especially `r=2` are allowed, prediction becomes much better.
- So the target is not random in the graph overall.
- It is specifically hard under the causal information restriction you imposed at `r=0`.

1. Most likely interpretation:

- The experiment did not fail because the model class was too weak.
- It failed because the chosen non-cheating information set does not contain enough bits about future branching persistence.
- Some additional `r=0` features may help at the margin, but the current evidence suggests they will not close the gap dramatically.

1. Best next scientific move:

- Reframe the claim more narrowly:
  - `r=0` can predict immediate adoption / first-step fertility moderately.
  - `r=0` cannot reliably predict eventual descendant mass.
- Then investigate whether richer non-cheating features can improve this, for example:
  - semantic content of theorem statements,
  - theorem type / tactic pattern,
  - local centrality / motif features,
  - temporal or corpus-position signals,
  - module-level adoption context.

Bottom line:

- This project is a partial success.
- It succeeds on predicting whether a theorem gets used at all.
- It fails, in the strict clean setting, to predict whether a theorem becomes a large downstream ancestor.
- The failure is best explained by network branching structure and missing forward-proxy information, not by obvious leakage problems or a completely broken pipeline.

## 2026-03-13 21:xx CET - Entry 7

Question added by user:

- Is it still non-cheating if features are computed on the full seen graph at depth `d`, as long as we do not expose the future/downstream nodes and links of the focal node itself?
- Since some downstream nodes can be shared with other theorems, should we remove all descendants of the focal node from the visible graph, even if those nodes are also downstream of other nodes?
- What kind of network prediction problem does this start to resemble?

My view:

Short answer:

- Yes, this makes conceptual sense.
- But there are two different meanings of "non-cheating," and they correspond to different scientific questions.

Two regimes:

1. Global-time non-cheating

- At depth `d`, use everything that already exists in the graph by that frontier.
- Forbid only nodes and edges that lie beyond the global horizon.
- Under this definition, using the whole seen graph is legitimate, even if some visible nodes later turn out to be descendants of the focal node in the full DAG.
- This is the standard temporal-forecasting interpretation.

2. Target-conditioned non-cheating

- For a focal node `v`, hide every node and edge in the descendant cone of `v`, even if some of those nodes are also visible through other routes.
- This is stricter.
- It asks whether `v`'s future impact can be predicted from information outside its own future cone.

These are both coherent, but they are not the same task.

Why the stricter proposal makes sense:

- If a visible node is also a descendant of `v`, it may leak information about how productive `v` eventually becomes.
- Even when that node is shared with another branch, its existence can still reveal properties of the future region that `v` participates in.
- So if the scientific target is specifically "predict from information causally outside the node's own future," then removing the full descendant cone is the cleanest formulation.

Why it might not make sense, depending on the goal:

- In a real forecasting setup, an observer at time `d` would not delete already-known facts from the world just because they lie in the target's future cone.
- So descendant-cone masking is less natural as a model of ordinary prediction from available information.
- In recombining DAGs, deleting shared descendants can remove information that is genuinely present through other branches, which makes the task partly about a graph intervention rather than just forecasting.

The core distinction:

- Temporal forecasting asks: "What could I know at time `d`?"
- Descendant-cone masking asks: "What could I know at time `d` after surgically removing all traces of this node's future?"

The second is cleaner for anti-leakage, but harsher and less realistic as a forecasting protocol.

What problem class this resembles:

- Temporal graph prediction.
- Influence prediction or cascade-size prediction.
- Branching-process forecasting.
- Target-conditioned graph censoring.

The closest compact label I would use:

- Temporal DAG influence prediction under target-conditioned censoring.

Why the stricter version may still fail:

- Once the target's descendant cone is removed, you are deleting exactly the region where most of the predictive information seems to live.
- Your existing results already suggest that downstream magnitude is decided mainly by early future branching.
- So if the masked task fails, that would not mean the phenomenon is random; it would mean the allowed information set is too weak for the target.

My recommendation:

- Treat these as two separate experiments:
  - global-time prediction using all nodes visible by depth `d`,
  - target-conditioned masked prediction with the focal descendant cone removed.
- Compare them directly.
- If the first works better than the second, then the predictive bits are present in contemporaneously visible structure but concentrated near the target's future cone.
- If both fail, then you likely need semantic or exogenous features rather than a different masking rule.

My present opinion:

- Your stricter masking idea is scientifically legitimate.
- It is not the only valid definition of non-cheating.
- It is a harder and less realistic observer model than standard temporal prediction.
- Poor performance under that rule should be interpreted as evidence that purely upstream topology does not contain enough information, not as evidence that downstream impact is fundamentally unpredictable in every sense.

## 2026-03-13 21:xx CET - Entry 8

User clarification and proposed labeling:

1. Existing approach

- Known world is all nodes up to depth `d`, regardless of source lineage.
- Features for target node `v` are computed from that global seen graph.
- User notes a conceptual awkwardness: this treats source nodes as if depth were temporally comparable across different branches, which is not literally true.
- My note: that objection is real, but the approach is still reasonable as a coarse partial-order notion of "what the system knows by frontier `d`."

2. Proposed new approach

- For each focal node `v`, define a masked graph
  - `G_v = G - descendants(v)`
- Then compute features for `v` on `G_v`.
- Target remains the original downstream quantity for `v`.
- User expectation: this may give the algorithm more usable non-cheating information than the existing approach.

My response to this precise version:

I agree this is a coherent and useful second protocol.

Important correction:

- Relative to the current strict implementation, this does not necessarily give *less* information.
- In fact it can give *more* information than the current `strict_past_seen_graph` approach, because your current `r=0` only exposes nodes with depth `< d`.
- Under protocol 2, if a node at depth `<= d` is not downstream of `v`, it can remain visible even if it is outside the current strict past cone used by the code.
- So yes, protocol 2 may materially help prediction.

Would protocol 2 be cheating?

- I do not think it is cheating, provided the rule is declared in advance and applied mechanically for every target node.
- It uses only graph structure after removing the focal node's own future cone.
- That means it avoids direct self-future leakage by construction.

But there is one subtle catch:

- To build `G_v = G - descendants(v)`, you must know which nodes are descendants of `v` in the full DAG.
- That uses future information at preprocessing time.
- This is not cheating in the evaluation sense if the masking is only used to define the admissible information set and none of the removed information is fed back as a feature.
- But conceptually it is a target-conditioned oracle mask.

So I would describe protocol 2 as:

- non-cheating for prediction,
- but oracle-defined for visibility.

That is acceptable if the scientific question is:

- "How much can be predicted about `v` from the rest of the graph once `v`'s own downstream cone is removed?"

Why protocol 2 could be better than protocol 1:

- Protocol 1 hides many nodes simply because they are beyond the global depth frontier, even if they are unrelated to `v`.
- Protocol 2 can preserve more of the ambient graph context, including other mature regions of the theorem network.
- Those regions may contain useful signals about module activity, neighboring branch fertility, and recombination structure.
- So protocol 2 may let the model use richer context without directly seeing the target node's own future.

Why protocol 2 could still be problematic:

- It is target-conditioned, so each node is evaluated on a different visible graph.
- That makes the task less like ordinary forecasting from a single shared world-state and more like a per-node counterfactual prediction problem.
- It may also preserve nodes that are globally "future" relative to the branch of `v`, as long as they are not descendants of `v`.
- So protocol 2 is not a pure temporal prediction protocol.

My current view of the comparison:

- Protocol 1:
  - shared global frontier,
  - temporally cleaner,
  - probably harsher because it discards unrelated context.
- Protocol 2:
  - target-conditioned masked graph,
  - not cheating in the predictive sense,
  - can provide more context,
  - but less interpretable as a single-time forecasting problem.

Best interpretation if protocol 2 works better:

- Then the extra predictive signal is coming from broader ambient graph context rather than from the focal node's own downstream cone.
- That would be a meaningful scientific result.
- It would say the theorem's future is partially encoded in the surrounding network state, even after removing its own descendants.

Best interpretation if protocol 2 still fails:

- Then purely structural graph context, even with broader visibility, is still not enough.
- At that point the missing bits are more likely semantic or exogenous than topological.

## 2026-03-13 22:xx CET - Entry 9

Implementation update requested by user:

- Existing approach renamed to protocol `1_`.
- New target-conditioned masked approach implemented as protocol `2_`.

Files created / renamed:

- Code:
  - `1_future_prediction_pipeline_v2.py`
  - `1_future_prediction_pipeline_v2.json`
  - `1_save_intermediate_analysis.py`
  - `2_future_prediction_pipeline_v2.py`
  - `2_future_prediction_pipeline_v2.json`
  - `2_save_intermediate_analysis.py`
- Existing summary renamed:
  - `1_future_pipeline_summary.md`
- Data and figure outputs for protocol 1 were renamed to `1_...`
- Protocol 2 outputs were saved as `2_...`

How protocol 2 was actually implemented:

- Frontier/evaluation is still by depth `d`.
- For each focal node `v`, features are computed under the rule:
  - visible graph for features = `G - descendants(v)`
- However, I did **not** allow arbitrary graph-wide features on this masked graph.

Reason for that restriction:

- If graph-wide statistics are allowed after target-conditioned masking, the model can infer how much of the graph disappeared.
- That can act as a proxy for the size of `descendants(v)`, which would be a hidden leakage channel.
- So I constrained protocol 2 to **local and ancestor-side masked features** only.

Protocol 2 feature family used:

- upstream / ancestor-side only:
  - `depth`
  - `indeg_seen`
  - `parent_indeg_max`
  - `parent_depth_max`
  - `parent_diversity`
  - `parent_lca_depth_pairwise_mean`
  - `upstream_2hop_node_count`
  - `upstream_2hop_edge_density`
  - `parent_module_entropy`
- masked forward context outside `v`'s cone:
  - `parent_outdeg_max`
  - `parent_outdeg_sum`
  - `parent_descendant_count_seen_max`
  - `parent_descendant_count_seen_mean`
  - `parent_beta_max`

Interpretation of those masked forward features:

- For each parent `p` of `v`, count only the children and descendants of `p` that remain after removing `descendants(v)`.
- So the model sees how productive the parents are outside the focal theorem's future cone.

My cheating check:

- To construct the mask, the code does use an oracle descendant set `descendants(v)`.
- But that oracle is used only to define which parts of the graph are hidden.
- The removed descendants, and graph-wide statistics of how much was removed, are not fed in as features.
- Under that interpretation, protocol 2 is non-cheating in the predictive sense, though target-conditioned by construction.

Protocol 2 main results from the direct run (`2_fvs_pipeline_v2_results.json`):

- Single-run metrics:
  - `d=5`: `Y2` PR-AUC `0.7697`, `Y1` Spearman `0.1945`
  - `d=7`: `Y2` PR-AUC `0.8051`, `Y1` Spearman `0.2557`
  - `d=9`: `Y2` PR-AUC `0.6550`, `Y1` Spearman `-0.0149`
  - `d=11`: `Y2` PR-AUC `0.7963`, `Y1` Spearman `0.2377`
  - `d=13`: `Y2` PR-AUC `0.7371`, `Y1` Spearman `0.4001`
  - `d=15`: `Y2` PR-AUC `0.6562`, `Y1` Spearman `0.3994`

Repeated-split stability from `2_intermediate_repeated_split_summary_r0.csv`:

- `d=5`:
  - `Y2` PR-AUC mean `0.764`, std `0.017`
  - `Y1` Spearman mean `0.198`, std `0.048`
- `d=10`:
  - `Y2` PR-AUC mean `0.690`, std `0.057`
  - `Y1` Spearman mean `0.025`, std `0.100`
- `d=20`:
  - `Y2` PR-AUC mean `0.748`, std `0.074`
  - `Y1` Spearman mean `-0.024`, std `0.213`

Comparison against protocol 1:

- For the binary "gets used at all" question (`Y2 > 0`), protocol 2 is clearly better.
  - Protocol 1 repeated-split means:
    - `d=5`: `0.557`
    - `d=10`: `0.611`
    - `d=20`: `0.675`
  - Protocol 2 repeated-split means:
    - `d=5`: `0.764`
    - `d=10`: `0.690`
    - `d=20`: `0.748`
- So the broader masked context outside the focal descendant cone is useful for predicting first-step adoption.

For the hard target `Y1`:

- Protocol 2 improves the shallow case somewhat:
  - at `d=5`, repeated-split mean Spearman rises from about `0.079` to about `0.198`
- But it does **not** solve the core problem:
  - at `d=10`, repeated-split mean is only `0.025`
  - at `d=20`, repeated-split mean is still negative on average (`-0.024`) and highly unstable

Feature importance under protocol 2:

- Top features for `Y2 > 0` include:
  - `parent_descendant_count_seen_max`
  - `parent_diversity`
  - `parent_outdeg_max`
  - `upstream_2hop_edge_density`
  - `parent_beta_max`

This is informative:

- The added value in protocol 2 seems to come from how fertile the parents are **outside** the focal theorem's own future cone.
- That supports your intuition that protocol 2 can provide useful extra ambient context without directly leaking the target's descendants.

Current scientific interpretation after implementing protocol 2:

- Your proposal was worthwhile.
- It is not equivalent to ordinary temporal forecasting, but it is coherent.
- It does help on the easier question:
  - "will this theorem be used at all?"
- It helps only modestly, and not robustly enough, on the harder question:
  - "will this theorem become a large downstream ancestor?"

Bottom-line update:

- Protocol 2 gives evidence that some predictive signal lives in the broader network context outside the focal node's own descendant cone.
- That is a real result.
- But even after giving the model that extra non-cheating context, long-run descendant magnitude remains mostly hard.
- So the main conclusion survives:
  - immediate adoption is structurally more predictable than eventual downstream mass.
