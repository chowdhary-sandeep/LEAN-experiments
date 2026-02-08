# Data Files Reference

Quick reference for main data locations in this project.

---

## Primary Data Files

### 1. Theorem Data (Main Source)
**Location:** `jsons/traced_theorems_unified_v2.jsonl`

- **What:** Complete Mathlib theorem dataset (126,792 theorems)
- **Format:** JSONL (one theorem per line)
- **Key fields:**
  - `full_name`: Theorem identifier
  - `proof_type`: "tactic" or "term"
  - `tactics[]`: Ordered proof steps (for tactic proofs)
  - `all_premises`: Dictionary of premises used
  - `metrics`: num_tactics, num_premises, statement_length
- **Size:** ~500 MB
- **Built by:** `00_build_unified_v2.py`

**Example record:**
```json
{
  "full_name": "Nat.add_comm",
  "proof_type": "tactic",
  "tactics": [
    {"index": 0, "tactic": "rw [...]", "state_before": "...", "premises": [...]}
  ],
  "all_premises": {"Nat.add_assoc": {"count": 2, ...}},
  "metrics": {"num_tactics": 3, "num_premises": 5, "statement_length": 42}
}
```

---

### 2. Theorem-Premise Network (DAG)
**Location:** `cache/bundle.pkl`

- **What:** Cached networkx DiGraph of theorem dependencies
- **Format:** Python pickle (NetworkX graph object)
- **Structure:**
  - Nodes: theorem/premise names
  - Edges: premise → theorem (meaning "theorem uses premise")
  - Node attributes: `node_type` ("theorem" or "premise")
- **Statistics:** 99,412 nodes, 358,810 edges
- **Built by:** `00_theorem_premise_network.py`

**Load with:**
```python
import pickle
with open("cache/bundle.pkl", "rb") as f:
    bundle = pickle.load(f)
G = bundle["G_original"]
```

---

### 3. MDL Gain Results
**Location:** `mdl_gain_results.csv`

- **What:** Computed MDL gain for all 126,792 theorems
- **Format:** CSV with headers
- **Key columns:**
  - `theorem`: Full theorem name
  - `mdl_gain`: Compression value (bits) - positive = compressive, negative = overhead
  - `in_degree`: Number of times theorem is cited
  - `pattern_length`: Characteristic proof length (tactics)
  - `num_uses`: Same as in_degree
  - `cost`: Description length cost to define theorem (bits)
  - `savings`: Total savings from uses (bits)
- **Size:** ~10 MB
- **Built by:** `05_mdl_gain_analysis.py`

**Key insight:** 99.5% have negative MDL gain (long-tail distribution - most theorems have 0-1 citations)

---

### 4. Crystallization Results
**Location:** Not saved to file (computed on-demand)

- **Script:** `03_crystallization_analysis.py`
- **What:** Premise co-occurrence patterns (which premise sets appear together frequently)
- **Key finding:** 1.69M patterns found, top pattern `{mul_assoc, mul_comm}` in 307 theorems
- **Note:** Run script to regenerate (takes ~5 minutes on full dataset)

---

## Supporting Files

### Corpus & Indices
- `jsons/corpus.jsonl` - All available premise definitions
- `jsons/premise_index_v2.json` - Name resolution index
- `jsons/theorem_stats_v2.json` - Build statistics

### Visualizations
- `figs/COMPREHENSIVE_WITH_MDL.png` - Complete experimental summary (15 panels)
- `figs/COMPREHENSIVE_MDL_INTERACTIVE.html` - Interactive version (hover for theorem names)
- `figs/crystallization_premise_cooccurrence.png` - Co-occurrence analysis
- `figs/mdl_*.png` - MDL gain analysis (3 figures)

### Reports
- `papers/FINDINGS.md` - Comprehensive analysis report
- `papers/0_plan.md` - Experimental plan + all results appended
- `papers/discovery_dynamics_research_plan.md` - Original research proposal

---

## Quick Data Access Patterns

### Get all tactic proofs:
```python
import json
theorems = []
with open("jsons/traced_theorems_unified_v2.jsonl") as f:
    for line in f:
        thm = json.loads(line)
        if thm["proof_type"] == "tactic":
            theorems.append(thm)
```

### Get theorem citation count:
```python
import pandas as pd
df = pd.read_csv("mdl_gain_results.csv")
top_cited = df.nlargest(10, 'in_degree')
```

### Get premise co-occurrences:
```python
# Run crystallization analysis
!python 03_crystallization_analysis.py
# Results printed to console + figure saved to figs/
```

---

## Data Provenance

**Original source:** LeanDojo Mathlib traced repository
**Mathlib version:** Snapshot from build (2024-2025)
**Total theorems:** 126,792 (54,477 tactic, 72,315 term)
**Processing date:** 2026-02-07 to 2026-02-08

**Pipeline:**
1. LeanDojo traced repo → `00_build_unified_v2.py` → `jsons/*.jsonl`
2. JSONL → `00_theorem_premise_network.py` → `cache/bundle.pkl` (DAG)
3. JSONL + DAG → `05_mdl_gain_analysis.py` → `mdl_gain_results.csv`
4. JSONL → `03_crystallization_analysis.py` → patterns (on-demand)

---

**Last updated:** 2026-02-08
