---
title: Adjacent Possible of LEAN
emoji: 🧮
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
app_port: 7860
---

# Adjacent Possible of LEAN

Interactive ego network dashboard for Mathlib theorem-premise dependency graphs.

**Data files required in `data/`:**
- `bundle.pkl` — theorem-premise graph (required)
- `corpus_code_index.json` — proof text index (optional, enables proof panel)
- `traced_theorems_unified_v2.jsonl` — full proof traces (optional, enables within-proof DAG)
