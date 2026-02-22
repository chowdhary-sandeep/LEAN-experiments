"""
Build experiment_results.json — aggregates all measures from plots into one shareable file.
Sources:
  - experiment2_search_proof_results.json
  - experiment2_phase_transition_results.json
  - papers/0_plan.md (experiment3 compression data, extracted here as literals)
"""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent

# -- Load existing results -------------------------------------------------------
with open(BASE / "experiment2_search_proof_results.json") as f:
    exp2_dynamics = json.load(f)

with open(BASE / "experiment2_phase_transition_results.json") as f:
    exp2_phase = json.load(f)

pt = exp2_phase  # alias

# -- Helpers --------------------------------------------------------------------
def traj_summary(traj, name):
    steps  = [d["step"]     for d in traj]
    knowns = [d["known"]    for d in traj]
    adjs   = [d["adjacent"] for d in traj]
    peak_adj = max(adjs) if adjs else 0
    return {
        "strategy":          name,
        "total_steps":       len(traj),
        "final_known":       knowns[-1] if knowns else 0,
        "final_adjacent":    adjs[-1]   if adjs   else 0,
        "peak_adjacent":     peak_adj,
        "peak_adjacent_step": steps[adjs.index(peak_adj)] if adjs else 0,
    }

def compact_phase(data):
    compact = {}
    for key, entries in data["results"].items():
        strat, recall = key.split("__")
        compact.setdefault(strat, {}).setdefault(recall, [])
        for e in entries:
            by_budget = {
                b_str: {
                    "coverage":    bdata.get("coverage",    0),
                    "discoveries": bdata.get("discoveries", 0),
                    "recalls":     bdata.get("recalls",     0),
                }
                for b_str, bdata in e["by_budget"].items()
            }
            compact[strat][recall].append({
                "memory_size": e["memory_size"],
                "label":       e["label"],
                "by_budget":   by_budget,
            })
    return compact

# -- Panel A: Adjacent Possible Dynamics ----------------------------------------
bfs_traj    = exp2_dynamics["experiment1_adjacent_possible"]["bfs"]
rand_traj   = exp2_dynamics["experiment1_adjacent_possible"]["random"]
greedy_traj = exp2_dynamics["experiment1_adjacent_possible"]["greedy"]

panel_A = {
    "description": (
        "Adjacent Possible Dynamics: how the discoverable frontier |A_t| evolves "
        "as theorems are accumulated under BFS, Random, Greedy strategies."
    ),
    "strategies": {
        "bfs":    traj_summary(bfs_traj,    "bfs"),
        "random": traj_summary(rand_traj,   "random"),
        "greedy": traj_summary(greedy_traj, "greedy"),
    },
    "coverage_summary": exp2_dynamics["experiment1_adjacent_possible"]["summary"],
    "interpretation": (
        "Explosive growth phase: |A_t| rises rapidly then contracts as easy results exhaust. "
        "Peak ~15,000 options at once. BFS and Greedy trajectories overlap."
    ),
    "trajectories_note": "Full step-by-step trajectories available in experiment2_search_proof_results.json",
}

# -- Panel B: Knowledge Accumulation --------------------------------------------
panel_B = {
    "description": "Cumulative theorems known over discovery steps for BFS / Random / Greedy.",
    "bfs_steps_to_97pct_coverage":    32,
    "random_steps_to_97pct_coverage": 49000,
    "greedy_coverage_at_10k_steps":   0.584,
    "ceiling_pct":  97.9,
    "ceiling_note": (
        "Remaining 2.1% are orphan theorems with no path from any root node."
    ),
}

# -- Panel C: Dilution ----------------------------------------------------------
panel_C = {
    "description": (
        "Dilution ('Hiding in Plain Sight'): |A_t| at the moment each theorem "
        "first becomes provable. High dilution = hard to find."
    ),
    "accessibility_time_stats": exp2_dynamics["experiment2_accessibility"]["accessibility_stats"],
    "dilution_stats":           exp2_dynamics["experiment2_accessibility"]["dilution_stats"],
    "interpretation": (
        "Most theorems become provable in ~10 BFS steps but are hidden "
        "among ~10,000 competing alternatives at that moment."
    ),
}

# -- Panel D: Gateway Theorem Identification ------------------------------------
panel_D = {
    "description": (
        "Gateway Theorem Identification: removal impact = fraction of descendants "
        "that become unreachable if a theorem is removed."
    ),
    "removal_impact_stats": exp2_dynamics["experiment3_bottlenecks"]["removal_impact_stats"],
    "top_bottlenecks":      exp2_dynamics["experiment3_bottlenecks"]["top_bottlenecks"],
    "interpretation": (
        "No bow-tie structure detected. Robust interconnection with many paths. "
        "A few key gateways (impact=1.0) sever ALL descendants."
    ),
}

# -- Panels E/F/G/H: Phase Transitions ------------------------------------------
panels_EFGH = {
    "description": (
        "Phase Transition Analysis: coverage vs memory size K, "
        "for 4 strategies x 3 recall modes x 17 memory sizes x 4 compute budgets."
    ),
    "dataset": {
        "total_theorems":    pt["total_theorems"],
        "root_count":        pt["root_count"],
        "baseline_coverage": pt["baseline_coverage"],
    },
    "strategies":    pt["strategies"],
    "recall_modes":  pt["recall_modes"],
    "memory_sizes":  pt["memory_sizes"],
    "budgets":       pt["budgets"],
    "results":       compact_phase(pt),
    "key_findings": {
        "E_no_recall": (
            "K<1,000: all strategies converge to ~48% baseline. "
            "Memory is the binding constraint, not strategy."
        ),
        "F_matched_recall": (
            "Greedy+recall lifts small-K coverage by ~5 pp. "
            "Most effective in mid-K range (1k-50k)."
        ),
        "G_hub_recall": (
            "Hub recall (highest out-degree) dominates: all strategies converge. "
            "'What to remember' matters more than 'what to explore next.'"
        ),
        "H_heatmap_note": (
            "Coverage heatmap at 60k budget: strategy rows x memory-size columns. "
            "Values represent fraction of theorems discovered."
        ),
    },
}

# -- Panel I: Memory-Constrained Discovery (Random) ----------------------------
panel_I = {
    "description": "Memory-Constrained Discovery (Random walk): coverage degrades as K shrinks.",
    "memory_coverage": exp2_dynamics["experiment6_memory_constrained"]["memory_coverage"],
    "interpretation": (
        "Smooth degradation — no sharp phase transition. "
        "K=inf: 58.4%, K=10k: 49.5%, K=1k: 48.5%, K=100: 48.4%."
    ),
}

# -- Panels J/K: Recall Benefit / Recall Fraction --------------------------------
panels_JK = {
    "description": (
        "J: Coverage gain from recall (matched/hub) vs no-recall baseline. "
        "K: Fraction of total steps spent on recall vs discovery."
    ),
    "recall_gain_peak_K_range": "5k-50k",
    "hub_vs_matched":  "Hub recall gives larger gains than matched for most strategies.",
    "recall_fraction": {
        "small_K": "80-95% of steps are recalls at small K (memory overflows constantly)",
        "large_K": "0% recalls at large K (memory holds everything)",
        "crossover_K": "~30k-50k (recall transitions from burden to unnecessary)",
    },
}

# -- Panel L: Best Coverage by Strategy x Memory --------------------------------
panel_L = {
    "description": (
        "Best coverage across recall modes for each strategy at K=500/5k/50k, @60k budget."
    ),
    "key_finding": (
        "Strategy choice matters most when memory is scarce — precisely the "
        "realistic regime for bounded agents. Greedy+recall wins at small K (~55% vs 48% baseline)."
    ),
}

# -- Experiment 3: Compression Analysis (from papers/0_plan.md) -----------------
# Numbers recorded 2026-02-07 from 01_within_proof_DAG_pipeline_v3_claude.py run
experiment3_compression = {
    "description": (
        "Theorem-Level Compression Analysis: uniform vs Shannon encoding "
        "across full Mathlib (126,792 theorems, 54,477 tactic proofs)."
    ),
    "dataset": {
        "total_theorems":         126792,
        "tactic_proofs_analyzed": 54473,
    },
    "corpus_encoding": {
        "uniform": {
            "total_MB":      12.79,
            "statements_MB": 11.83,
            "tactics_MB":    0.27,
            "premises_MB":   0.69,
        },
        "shannon": {
            "total_MB":             12.57,
            "compression_ratio":    1.02,
            "space_saved_MB":       0.21,
            "compression_gain_pct": 1.7,
        },
    },
    "vocabulary_statistics": {
        "unique_tactics":               278,
        "unique_premises":              70863,
        "tactic_entropy_bits":          4.71,
        "tactic_entropy_uniform_bits":  8.12,
        "premise_entropy_bits":         13.77,
        "premise_entropy_uniform_bits": 16.11,
    },
    "tactic_transition_patterns": {
        "unique_bigrams":          5742,
        "unique_trigrams":         29806,
        "conditional_entropy_bits": 3.38,
        "predictability_gain_pct": 58.4,
    },
    "per_theorem_metrics": {
        "avg_compression_potential_bits":    0.05,
        "median_compression_potential_bits": 0.00,
        "max_compression_potential_bits":    1.19,
        "avg_redundancy_pct":               2.0,
    },
    "top_10_most_compressible_theorems": [
        {"rank": 1,  "name": "psp_from_prime_psp",
         "compression_potential_bits": 1.19, "redundancy_pct": 30},
        {"rank": 2,  "name": "hG",
         "compression_potential_bits": 1.15, "redundancy_pct": 38},
        {"rank": 3,  "name": "comm_1",
         "compression_potential_bits": 1.02, "redundancy_pct": 29},
        {"rank": 4,  "name": "inductionOn",
         "compression_potential_bits": 0.96, "redundancy_pct": 34},
        {"rank": 5,  "name": "trans_assoc_reparam",
         "compression_potential_bits": 0.94, "redundancy_pct": 27},
        {"rank": 6,  "name": "sign_two_nsmul_eq_sign_iff",
         "compression_potential_bits": 0.92, "redundancy_pct": 24},
        {"rank": 7,  "name": "mul",
         "compression_potential_bits": 0.90, "redundancy_pct": 23},
        {"rank": 8,  "name": "lintegral_comp_eq_lintegral_meas_le_mul_of_measurable",
         "compression_potential_bits": 0.89, "redundancy_pct": 19},
        {"rank": 9,  "name": "exists_sum_eq_one_iff_pairwise_coprime",
         "compression_potential_bits": 0.88, "redundancy_pct": 23},
        {"rank": 10, "name": "integral_mul_of_integrable",
         "compression_potential_bits": 0.86, "redundancy_pct": 43},
    ],
    "key_findings": [
        "Human Mathlib organization is near-optimal: only 1.7% compression headroom via frequency optimization.",
        "58.4% of tactics are predictable from the previous tactic (conditional entropy 3.38 bits vs 4.71 uniform).",
        "Compression potential varies widely (0 to 1.19 bits); top theorems have highly repetitive tactic patterns.",
        "Average tactic redundancy across proofs: 2.0%.",
        "Top 3 theorems exceed 1.0 bit compression potential — strong crystallization candidates.",
    ],
}

# -- Network Analysis (from 00_theorem_premise_network.py + cache/bundle.pkl) ---
# Numbers from graph built 2026-02-22; tactic proofs only (proof_type='tactic')
network_analysis = {
    "description": (
        "Theorem-Premise Dependency DAG: nodes are theorems and premises, "
        "edge A->B means 'theorem B uses premise A in its proof'. "
        "Only tactic proofs included; tactics/hypothesis names filtered out."
    ),
    "graph_stats": {
        "total_nodes":      99412,
        "theorem_nodes":    32491,
        "premise_nodes":    66921,
        "edges":            358810,
        "root_nodes":       48081,   # in-degree == 0 (no prerequisites)
        "leaf_nodes":       28865,   # out-degree == 0 (nothing depends on them)
    },
    "source_data": {
        "total_theorems_in_corpus":   126792,
        "tactic_proofs_in_graph":      54477,
        "term_proofs_skipped":         72315,
        "total_tactics":              276014,
        "total_premises_references":  784726,
        "unique_premises":             70863,
        "high_confidence_premises":   445165,
        "low_confidence_premises":    339561,
        "resolution_methods": {
            "exact_match":        226168,
            "unique_suffix":       67298,
            "namespace_match":     88470,
            "ambiguous":          133621,
            "not_found":          205940,
            "leandojo_annotation": 13465,
            "type_inference_Nat":  13985,
            "type_inference_Int":   2472,
            "type_inference_Set":  20334,
            "type_inference_Real":  4118,
            "type_inference_List":  3127,
            "type_inference_Finset":4374,
            "type_inference_Matrix":  659,
            "type_inference_Polynomial":432,
            "type_inference_Rat":    188,
            "type_inference_Array":   56,
            "type_inference_BitVec":  19,
        },
    },
    "degree_distribution": {
        "out_degree": {
            "p50": 1, "p75": 2, "p90": 6, "p99": 46, "max": 1879,
            "note": "Out-degree = number of theorems that use this node as a premise",
        },
        "in_degree": {
            "p50": 1, "p75": 4, "p90": 10, "p99": 34, "max": 144,
            "note": "In-degree = number of premises a theorem depends on",
        },
    },
    "top_10_most_used_premises": [
        {"name": "Lean.Meta.dsimp",                                                  "used_by_n_theorems": 1879},
        {"name": "trans",                                                             "used_by_n_theorems": 1538},
        {"name": "Lean.Parser.Term.suffices",                                         "used_by_n_theorems": 1325},
        {"name": "mul_comm",                                                          "used_by_n_theorems": 1288},
        {"name": "Filter.NeBot.ne",                                                   "used_by_n_theorems": 1169},
        {"name": "CategoryTheory.ShortComplex.LeftHomologyData.IsPreservedBy.hg",     "used_by_n_theorems": 1116},
        {"name": "mul_assoc",                                                         "used_by_n_theorems": 1056},
        {"name": "mul_one",                                                           "used_by_n_theorems": 1006},
        {"name": "use",                                                               "used_by_n_theorems":  931},
        {"name": "Lean.Parser.Term.haveI",                                            "used_by_n_theorems":  907},
    ],
    "top_10_most_premise_dependent_theorems": [
        {"name": "Vitali.exists_disjoint_covering_ae",                                 "num_premises": 144},
        {"name": "PhragmenLindelof.horizontal_strip",                                  "num_premises": 138},
        {"name": "MeasureTheory.lintegral_comp_eq_lintegral_meas_le_mul_of_measurable","num_premises": 135},
        {"name": "MeasureTheory.hasFDerivAt_convolution_right_with_param",             "num_premises": 134},
        {"name": "mem_adjoin_of_smul_prime_smul_of_minpoly_isEisensteinAt",            "num_premises": 131},
        {"name": "Besicovitch.exist_finset_disjoint_balls_large_measure",              "num_premises": 130},
        {"name": "Besicovitch.exists_closedBall_covering_tsum_measure_le",             "num_premises": 118},
        {"name": "LieAlgebra.engel_isBot_of_isMin",                                    "num_premises": 115},
        {"name": "Zlattice.rank",                                                       "num_premises": 114},
        {"name": "MeasureTheory.hahn_decomposition",                                   "num_premises": 113},
    ],
    "key_findings": [
        "Sparse graph: 99,412 nodes, 358,810 edges — avg out-degree ~3.6.",
        "Heavy-tailed: top 1% of nodes have out-degree ≥46; max is 1,879 (Lean.Meta.dsimp).",
        "mul_comm and mul_assoc appear in the top 10 most-used premises (1,288 and 1,056 uses).",
        "48,081 root nodes (no prerequisites) — mathematical axioms and definitions.",
        "205,940 premise references unresolved (not_found) — 26% of all references.",
    ],
}

# -- MDL Gain Analysis (from 05_mdl_gain_analysis.py + mdl_gain_results.csv) ---
# CSV has 126,792 rows; computed 2026-02-22
mdl_gain_analysis = {
    "description": (
        "Minimum Description Length (MDL) gain per theorem: "
        "ΔL_MDL = savings(citations × proof_cost_saved) − cost(statement + proof encoding). "
        "Positive = theorem compresses the library; negative = adds cost."
    ),
    "encoding_parameters": {
        "tactic_vocab_size":    278,
        "theorem_count":        99412,
        "avg_bits_per_token":   6,
        "bits_per_tactic":      8.12,
        "bits_per_reference":   16.60,
    },
    "corpus_summary": {
        "theorems_analyzed":       126792,
        "theorems_positive_gain":     626,
        "theorems_negative_gain":  126166,
        "pct_positive":             0.49,
        "max_mdl_gain":         52649.56,
        "mean_mdl_gain":          -786.10,
        "total_savings_bits":   2949293.7,
    },
    "top_10_by_mdl_gain": [
        {"rank":  1, "name": "Nat.Partrec.Code.hG",                              "mdl_gain": 52649.56, "num_uses": 106,  "cost":  669.61},
        {"rank":  2, "name": "Profinite.NobelingProof.GoodProducts.injective",   "mdl_gain": 24296.22, "num_uses": 235,  "cost":  421.78},
        {"rank":  3, "name": "OreLocalization.mul_smul",                         "mdl_gain": 20919.47, "num_uses": 166,  "cost":  584.14},
        {"rank":  4, "name": "trans",                                             "mdl_gain": 11393.65, "num_uses": 1538, "cost":  534.60},
        {"rank":  5, "name": "norm_smul",                                         "mdl_gain": 10744.58, "num_uses": 173,  "cost":  429.19},
        {"rank":  6, "name": "mul_comm",                                          "mdl_gain":  9616.73, "num_uses": 1288, "cost":  372.60},
        {"rank":  7, "name": "Filter.NeBot.ne",                                   "mdl_gain":  8604.70, "num_uses": 1169, "cost":  461.70},
        {"rank":  8, "name": "Sum.LiftRel.mono",                                  "mdl_gain":  7775.10, "num_uses": 358,  "cost":  814.59},
        {"rank":  9, "name": "mul_assoc",                                         "mdl_gain":  7712.11, "num_uses": 1056, "cost":  477.90},
        {"rank": 10, "name": "Bimod.AssociatorBimod.hom_inv_id",                  "mdl_gain":  7679.19, "num_uses": 100,  "cost":  403.43},
    ],
    "degree_stats": {
        "in_degree_mean":  1.92,
        "out_degree_mean": 2.84,
        "in_degree_max":   1538,
        "out_degree_max":  144,
    },
    "key_findings": [
        "Only 626 of 126,792 theorems (0.49%) provide positive MDL gain — most theorems add net cost.",
        "Top theorem (Nat.Partrec.Code.hG): 52,649 bits saved, cited 106 times.",
        "trans and mul_comm rank #4 and #6 despite modest per-use savings, due to citation frequency (1538, 1288).",
        "Negative mean (−786 bits) reflects that most theorems are used rarely and cost more than they save.",
        "Total library savings from positive-gain theorems: ~2.95M bits.",
    ],
    "csv_schema": {
        "file":    "mdl_gain_results.csv",
        "columns": ["theorem", "mdl_gain", "cost", "savings", "num_uses",
                    "pattern_length", "savings_per_use", "in_degree", "out_degree", "proof_type"],
        "rows":    126792,
    },
}

# -- Pattern Mining / Crystallization (from 02_make_final_summary_plots.py + 06_comprehensive_with_mdl.py) ---
# Numbers from runs recorded in scripts; pattern_mb from 06_ script
crystallization_analysis = {
    "description": (
        "Tactic pattern mining and crystallization analysis: "
        "identifying repeated tactic sequences that could be abstracted into new lemmas. "
        "Three encoding schemes compared: Uniform, Shannon, Pattern-Abstraction."
    ),
    "encoding_comparison": {
        "uniform_MB":  12.79,
        "shannon_MB":  12.57,
        "pattern_MB":  12.52,
        "shannon_ratio":          1.02,
        "pattern_ratio":          1.02,
        "frequency_gain_pct":     1.7,
        "pattern_gain_pct":       0.37,
        "total_headroom_pct":     2.1,
        "interpretation": "Human Mathlib factorization is near-optimal — only 2.1% compression headroom.",
    },
    "tactic_predictability": {
        "tactic_entropy_uniform_bits": 8.12,
        "tactic_entropy_actual_bits":  4.71,
        "conditional_entropy_bits":    3.38,
        "predictability_pct":         58.4,
        "interpretation": "58.4% of tactics are predictable from the previous tactic.",
    },
    "pattern_mining": {
        "num_valuable_patterns":  9068,
        "total_tactic_savings":  81727,
        "compression_gain_pct":   0.37,
        "top_10_patterns": [
            {"pattern": "have -> have -> have",           "rank": 1,  "occurrences": 611, "tactic_savings": 1219},
            {"pattern": "have -> have -> have -> have",   "rank": 2,  "occurrences": 359, "tactic_savings": 1073},
            {"pattern": "· -> · -> ·",                   "rank": 3,  "occurrences": 507, "tactic_savings": 1011},
            {"pattern": "have x5",                        "rank": 4,  "occurrences": 221, "tactic_savings":  879},
            {"pattern": "have x6",                        "rank": 5,  "occurrences": 140, "tactic_savings":  694},
            {"pattern": "· -> · -> rw",                  "rank": 6,  "occurrences": 215, "tactic_savings":  427},
            {"pattern": "· -> · -> exact",               "rank": 7,  "occurrences": 213, "tactic_savings":  423},
            {"pattern": "exact x3",                       "rank": 8,  "occurrences": 164, "tactic_savings":  325},
            {"pattern": "refine -> · x2",                "rank": 9,  "occurrences": 249, "tactic_savings":  495},
            {"pattern": "apply -> · x2",                 "rank": 10, "occurrences": 144, "tactic_savings":  285},
        ],
    },
    "key_findings": [
        "Pattern abstraction yields only 0.37% additional compression beyond Shannon — human lemma choices are near-optimal.",
        "9,068 patterns have positive tactic savings; 81,727 total tactics could be eliminated.",
        "Repeated 'have' chains dominate: have³ (611×), have⁴ (359×), have⁵ (221×), have⁶ (140×).",
        "Long proofs do NOT imply high compression: short proofs with repetitive tactics dominate.",
        "Top finding: human mathematical factorization achieves information-theoretically optimal organization.",
    ],
}

# -- Assemble final JSON --------------------------------------------------------
output = {
    "meta": {
        "title":    "Discovery Dynamics in the Adjacent Possible — Experiment Results",
        "dataset":  "LeanDojo Mathlib4 (traced theorem proofs)",
        "date":     "2026-02-07 / 2026-02-22",
        "graph": {
            "total_theorems":    pt["total_theorems"],
            "root_nodes":        pt["root_count"],
            "baseline_coverage": pt["baseline_coverage"],
            "edge_semantics":    "Edge A->B means theorem B uses premise A in its proof.",
        },
        "source_scripts": [
            "experiment2_search_proof_dynamics.py",
            "experiment2_phase_transition.py",
            "experiment2_search_proof_visualize.py",
            "01_within_proof_DAG_pipeline_v3_claude.py",
            "00_code/00_theorem_premise_network.py",
            "05_mdl_gain_analysis.py",
            "02_make_final_summary_plots.py",
            "06_comprehensive_with_mdl.py",
        ],
        "figures": [
            "figs/experiment2_search_proof_comprehensive.png  (12-panel comprehensive figure)",
            "figs/experiment3_compression_comparison.png     (Encoding Scheme Comparison bar chart)",
            "figs/experiment3_compression_landscape.png      (Theorem-Level Compression Landscape 2x2)",
            "figs/FINAL_SUMMARY.png                          (6-panel description length summary)",
        ],
    },
    "panel_A_adjacent_possible_dynamics":       panel_A,
    "panel_B_knowledge_accumulation":           panel_B,
    "panel_C_dilution_hiding_in_plain_sight":   panel_C,
    "panel_D_gateway_theorem_identification":   panel_D,
    "panels_E_F_G_H_phase_transitions":         panels_EFGH,
    "panel_I_memory_constrained_discovery":     panel_I,
    "panels_J_K_recall_benefit_and_overhead":   panels_JK,
    "panel_L_best_coverage_by_strategy_memory": panel_L,
    "experiment3_compression_analysis":         experiment3_compression,
    "network_analysis":                         network_analysis,
    "mdl_gain_analysis":                        mdl_gain_analysis,
    "crystallization_analysis":                 crystallization_analysis,
}

out_path = BASE / "experiment_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

size_kb = out_path.stat().st_size / 1024
print(f"Saved:  {out_path}")
print(f"Size:   {size_kb:.1f} KB")
print("\nTop-level keys:")
for k in output:
    print(f"  {k}")
