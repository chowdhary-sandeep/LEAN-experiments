import pathlib, ast, re

base = pathlib.Path(r"E:/LEAN-experiments/00_experiment1")
tq   = chr(34) * 3
excl = chr(33)


def syntax_check_write(path, text):
    try:
        ast.parse(text)
        print(f"  Parse: OK")
        path.write_text(text, encoding="utf-8")
        print(f"  Written {len(text):,} chars -> {path.name}")
    except SyntaxError as e:
        lnum   = e.lineno
        mlines = text.splitlines()
        print(f"  SYNTAX ERROR at line {lnum}: {e.msg}")
        for i in range(max(0, lnum - 5), min(len(mlines), lnum + 5)):
            print(f"    {i+1:4}: {repr(mlines[i][:100])}")


def section_sep(title):
    bar = "# " + "=" * 73
    return f"\n\n{bar}\n# {title}\n{bar}\n\n"


def replace_docstring(src, body):
    """Swap the leading module triple-quoted docstring for body."""
    new_doc = tq + "\n" + body + "\n" + tq
    return re.sub(tq + r".*?" + tq, new_doc, src, count=1, flags=re.DOTALL)


# ── NOTE: Group A (quick_fix) ─────────────────────────────────────────────────
# quick_fix_after_00_build_unified_v2.py has already been absorbed.
# 00_code/00_build_unified_v2.py contains apply_fix_if_needed() + _needs_fix()
# which only rewrites the JSONL when tactic/hyp premises are detected.
# Run:  python 00_code/00_build_unified_v2.py --fix
print("-- Group A: quick_fix already absorbed into 00_code/00_build_unified_v2.py (--fix flag) --")


# ── GROUP C: 05 + 06 → experiment5_mdl_gain.py ───────────────────────────────
print("\n-- GROUP C: experiment5_mdl_gain.py --")

src05 = (base / "05_mdl_gain_analysis.py").read_text(encoding="utf-8")
src06 = (base / "06_comprehensive_with_mdl.py").read_text(encoding="utf-8")

doc5 = (
    "Experiment 5 - MDL Gain Analysis\n\n"
    "Phase 1: Compute MDL gain for every theorem, compare against 4 baselines.\n"
    "         Saves mdl_gain_results.csv and 3 diagnostic plots.\n\n"
    "Phase 2: Comprehensive figure + interactive Plotly HTML combining all findings\n"
    "         with the MDL gain section.\n\n"
    "Source scripts: 05_mdl_gain_analysis.py + 06_comprehensive_with_mdl.py"
)
phase1_c = replace_docstring(src05, doc5)

# Phase 2: skip 06's 52-line imports/config preamble
lines06        = src06.splitlines()
phase2_lines_c = lines06[52:]

lb  = "(?<" + excl + "[_a-zA-Z0-9])"
la  = "(?" + excl + "_html|[_a-zA-Z0-9])"
pat = re.compile(lb + "fig" + la)

renamed_c = []
for ln in phase2_lines_c:
    ln = ln.replace("df_mdl", "df")
    ln = pat.sub("fig2", ln)
    renamed_c.append(ln)

merged_c = (
    phase1_c.rstrip()
    + section_sep("PHASE 2 - Comprehensive Figure + Interactive HTML")
    + "\n".join(renamed_c) + "\n"
)
syntax_check_write(base / "experiment5_mdl_gain.py", merged_c)


# ── GROUP B-1: 03 + 04 → experiment1_compression_visualize.py ────────────────
print("\n-- GROUP B-1: experiment1_compression_visualize.py --")

src03 = (base / "03_crystallization_analysis.py").read_text(encoding="utf-8")
src04 = (base / "04_create_comprehensive_figure.py").read_text(encoding="utf-8")

doc3 = (
    "Experiment 1 - Compression Visualize\n\n"
    "Phase 1: Mine premise co-occurrence patterns (crystallization analysis).\n"
    "         Computes candidates and compression savings; saves landscape figure.\n\n"
    "Phase 2: Multi-panel comprehensive figure for all experiments (Exps 1-4).\n"
    "         Uses Phase 1 functions instead of re-implementing them.\n\n"
    "Source scripts: 03_crystallization_analysis.py + 04_create_comprehensive_figure.py"
)
phase1_b1 = replace_docstring(src03, doc3)

# From 04: skip imports/config/load_crystallization_data; keep load_theorem_data onward
lines04   = src04.splitlines()
ltd_start = next(i for i, l in enumerate(lines04) if l.strip().startswith("def load_theorem_data"))
lcd_start = next(i for i, l in enumerate(lines04) if l.strip().startswith("def load_crystallization_data"))
ccf_start = next(i for i, l in enumerate(lines04) if l.strip().startswith("def create_comprehensive_figure"))

# Extra imports 04 needs that 03 doesn't have
extra_imports_b1 = (
    "import matplotlib.patches as mpatches\n"
    "from matplotlib.gridspec import GridSpec\n"
)

portion_ltd  = "\n".join(lines04[ltd_start:lcd_start])   # load_theorem_data
portion_rest = "\n".join(lines04[ccf_start:])             # create_comprehensive_figure + __main__

# Replace load_crystallization_data() call with direct calls to Phase 1 functions
REPLACE_CRYST = (
    "    # Run crystallization analysis using Phase 1 functions\n"
    "    theorem_premises    = extract_theorem_premise_sets(DATA_FILE)\n"
    "    frequent_patterns   = find_frequent_premise_sets(\n"
    "        theorem_premises, min_set_size=2, max_set_size=5, min_support=2)\n"
    "    cryst_candidates    = analyze_crystallization_candidates(frequent_patterns)"
)
portion_rest = portion_rest.replace(
    "    cryst_candidates = load_crystallization_data()", REPLACE_CRYST
)

phase2_b1 = extra_imports_b1 + "\n" + portion_ltd + "\n\n" + portion_rest + "\n"

merged_b1 = (
    phase1_b1.rstrip()
    + section_sep("PHASE 2 - Comprehensive Multi-Panel Figure")
    + phase2_b1
)
syntax_check_write(base / "experiment1_compression_visualize.py", merged_b1)


# ── GROUP B-2: 01 + 02 → experiment1_compression.py ─────────────────────────
print("\n-- GROUP B-2: experiment1_compression.py --")

src01 = (base / "01_within_proof_DAG_pipeline_v3_claude.py").read_text(encoding="utf-8")
src02 = (base / "02_make_final_summary_plots.py").read_text(encoding="utf-8")

doc1 = (
    "Experiment 1 - Compression Pipeline\n\n"
    "Phase 1: Main 5-phase analysis pipeline — uniform/Shannon/pattern encoding,\n"
    "         tactic n-grams, per-theorem compression. Appends to papers/0_plan.md.\n\n"
    "Phase 2: Final summary plots (hardcoded results from Phase 1 run).\n"
    "         Requires: FIGS_DIR (defined above). Run after Phase 1 completes.\n\n"
    "Source scripts: 01_within_proof_DAG_pipeline_v3_claude.py + 02_make_final_summary_plots.py"
)
phase1_b2 = replace_docstring(src01, doc1)

# From 02: skip its imports/config preamble — start at RESULTS = {
lines02       = src02.splitlines()
results_start = next(i for i, l in enumerate(lines02) if l.strip().startswith("RESULTS = {"))

# 02 uses mpatches; 01 doesn't import it
extra_imports_b2 = "import matplotlib.patches as mpatches\n\n"

phase2_b2 = extra_imports_b2 + "\n".join(lines02[results_start:]) + "\n"

merged_b2 = (
    phase1_b2.rstrip()
    + section_sep("PHASE 2 - Final Summary Plots")
    + phase2_b2
)
syntax_check_write(base / "experiment1_compression.py", merged_b2)
