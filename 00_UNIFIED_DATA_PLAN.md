# Unified Traced Theorems Data Plan

## Research Summary

Based on LeanDojo documentation, Lean 4 reference, and ML benchmark best practices.

---

## What LeanDojo Already Provides

| Data | Source | Available In |
|------|--------|--------------|
| Theorem full name | `TracedTheorem.theorem.full_name` | ✅ Already have |
| File path | `TracedTheorem.theorem.file_path` | ✅ Already have |
| Statement | `TracedTheorem.get_theorem_statement()` | ❌ **Need to add** |
| Start/end positions | `TracedTheorem.theorem.start, .end` | ❌ **Need to add** |
| Tactic string | `TracedTactic.tactic` | ✅ Already have |
| State before/after | `TracedTactic.state_before/after` | ✅ Already have |
| Annotated tactic | `TracedTactic.get_annotated_tactic()` | ✅ Already have |
| Premise provenance | Premise dicts with `full_name`, `def_path`, `def_pos` | ⚠️ Often empty |
| Proof AST | `TracedTheorem.get_proof_node()` | ❌ Could add |
| Comments/docstring | `TracedTheorem.comments` | ❌ Could add |

---

## Proposed Unified Schema (v2)

### Per-Theorem Record

```json
{
    // ═══════════════════════════════════════════════════════════════
    // IDENTITY & LOCATION
    // ═══════════════════════════════════════════════════════════════
    "full_name": "Nat.add_comm",
    "file": "Mathlib/Algebra/Group/Defs.lean",
    "repo": "mathlib4",
    "commit": "abc123...",
    
    "position": {
        "start": {"line": 123, "column": 1},
        "end": {"line": 125, "column": 42}
    },
    
    // ═══════════════════════════════════════════════════════════════
    // STATEMENT & PROOF
    // ═══════════════════════════════════════════════════════════════
    "statement": "∀ (n m : ℕ), n + m = m + n",
    "statement_pretty": "theorem Nat.add_comm (n m : ℕ) : n + m = m + n",
    
    "proof_type": "tactic",      // "tactic" | "term" | "mixed" | "sorry"
    "proof_text": "by\n  induction n with\n  | zero => simp\n  | succ => ...",
    
    // ═══════════════════════════════════════════════════════════════
    // DOCUMENTATION
    // ═══════════════════════════════════════════════════════════════
    "docstring": "Addition is commutative for natural numbers.",
    "attributes": ["simp", "comm"],
    
    // ═══════════════════════════════════════════════════════════════
    // NAMESPACE & IMPORT CONTEXT (for name resolution!)
    // ═══════════════════════════════════════════════════════════════
    "namespace": "Nat",
    "imports": ["Init.Data.Nat.Basic", "Mathlib.Algebra.Group.Defs"],
    "open_namespaces": ["Nat", "Function"],
    
    // ═══════════════════════════════════════════════════════════════
    // TRACED TACTICS (ordered list)
    // ═══════════════════════════════════════════════════════════════
    "tactics": [
        {
            "index": 0,
            "tactic": "induction n with",
            "annotated_tactic": "induction n with",
            
            // Raw state strings
            "state_before": "n m : ℕ\n⊢ n + m = m + n",
            "state_after": "case zero\nm : ℕ\n⊢ 0 + m = m + 0\n...",
            
            // PRE-PARSED context (saves downstream parsing!)
            "context": {
                "variables": {
                    "n": {"type": "ℕ", "is_hypothesis": false},
                    "m": {"type": "ℕ", "is_hypothesis": false}
                },
                "hypotheses": {},
                "typeclasses": [],
                "goal": "n + m = m + n",
                "goal_type": "Eq"
            },
            
            // PREMISES with full resolution
            "premises": [
                {
                    "surface_name": "add_comm",
                    "full_name": "Nat.add_comm",
                    "def_path": "Mathlib/Algebra/Group/Defs.lean",
                    "def_pos": [123, 1],
                    "resolution_method": "namespace_match",
                    "confidence": 1.0
                }
            ],
            
            // Tactic metadata
            "is_terminal": false,
            "creates_goals": 2
        }
        // ... more tactics
    ],
    
    // ═══════════════════════════════════════════════════════════════
    // AGGREGATED PREMISE INFO (reverse index)
    // ═══════════════════════════════════════════════════════════════
    "all_premises": {
        "Nat.add_comm": {
            "count": 2,
            "tactics": [0, 3],
            "def_path": "...",
            "is_from_same_file": true
        }
    },
    
    // ═══════════════════════════════════════════════════════════════
    // DEPENDENCY GRAPH INFO
    // ═══════════════════════════════════════════════════════════════
    "dependencies": {
        "direct": ["Nat.zero_add", "Nat.succ_add"],
        "transitive_count": 15
    },
    
    // ═══════════════════════════════════════════════════════════════
    // COMPLEXITY METRICS (useful for ML training!)
    // ═══════════════════════════════════════════════════════════════
    "metrics": {
        "num_tactics": 5,
        "num_premises": 3,
        "proof_depth": 2,
        "statement_tokens": 12,
        "proof_tokens": 45,
        "unique_tactic_types": ["induction", "simp", "rfl"],
        "has_unicode_issues": false
    },
    
    // ═══════════════════════════════════════════════════════════════
    // DATA QUALITY FLAGS
    // ═══════════════════════════════════════════════════════════════
    "quality": {
        "fully_traced": true,
        "all_premises_resolved": true,
        "has_ambiguous_premises": false,
        "missing_state_info": false
    }
}
```

---

## What's New vs Current Implementation

| Field | Current | Proposed | Why Useful |
|-------|---------|----------|------------|
| `statement` | ❌ Missing | ✅ Add | Need for ML training, understanding what theorem does |
| `proof_text` | ❌ Missing | ✅ Add | Raw proof for display/debugging |
| `namespace` | ❌ Missing | ✅ Add | Critical for name resolution! |
| `imports` | ❌ Missing | ✅ Add | Know which modules are available |
| `open_namespaces` | ❌ Missing | ✅ Add | Resolve unqualified names |
| `position` | ❌ Missing | ✅ Add | Link back to source code |
| `docstring` | ❌ Missing | ✅ Add | Documentation for humans |
| `dependencies` | ❌ Missing | ✅ Add | Build dependency graph |
| `metrics` | ❌ Missing | ✅ Add | Filter by complexity, training selection |
| `repo/commit` | ❌ Missing | ✅ Add | Version tracking |
| `context.variables.is_hypothesis` | ❌ Missing | ✅ Add | Distinguish vars from hypotheses |
| `resolution_method` | ⚠️ Basic | ✅ Enhance | Know HOW name was resolved |
| `confidence` | ❌ Missing | ✅ Add | Flag uncertain resolutions |

---

## Name Resolution Strategy (Enhanced)

### Resolution Methods (Priority Order)

1. **LeanDojo Annotation** (confidence: 1.0)
   - If `TracedTactic.get_annotated_tactic()` returns premise with `full_name`
   - This is the ground truth from Lean's elaborator

2. **Exact Match** (confidence: 1.0)
   - Surface name already fully qualified
   - Exists in corpus exactly

3. **Namespace Context** (confidence: 0.95)
   - Use `open_namespaces` to resolve
   - E.g., if `open Nat` and `add_comm` used → `Nat.add_comm`

4. **Type-Based** (confidence: 0.8)
   - From `context.variables`, identify types
   - If `n : ℕ`, prefer `Nat.*` namespace

5. **Import-Based** (confidence: 0.7)
   - If only one imported module has that name

6. **Unique Suffix** (confidence: 0.6)
   - Only one theorem in corpus ends with that name

7. **Ambiguous** (confidence: 0.3)
   - Multiple candidates, cannot resolve
   - Store `candidates` list for manual review

### Resolution Data Flow

```
┌─────────────────────┐
│ Tactic: rw [add_comm] │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ 1. Check LeanDojo annotation            │
│    → empty? Continue...                 │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ 2. Check if already qualified           │
│    "add_comm" not qualified → Continue  │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ 3. Check open_namespaces: ["Nat"]       │
│    → Try "Nat.add_comm" in corpus       │
│    → FOUND! Use this                    │
└──────────┬──────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│ Result:                                 │
│   surface_name: "add_comm"              │
│   full_name: "Nat.add_comm"             │
│   resolution_method: "namespace_match"  │
│   confidence: 0.95                      │
└─────────────────────────────────────────┘
```

---

## Additional Files to Generate

### 1. `premise_index.json` - Fast Lookup

```json
{
    "by_suffix": {
        "add_comm": ["Nat.add_comm", "Int.add_comm", "BitVec.add_comm"],
        "mul_assoc": ["Nat.mul_assoc", "Int.mul_assoc", ...]
    },
    "by_full_name": {
        "Nat.add_comm": {
            "def_path": "...",
            "def_pos": [...],
            "type": "theorem",
            "statement": "∀ n m, n + m = m + n"
        }
    }
}
```

### 2. `dependency_graph.json` - Theorem Dependencies

```json
{
    "nodes": ["Nat.add_comm", "Nat.zero_add", ...],
    "edges": [
        {"from": "Nat.add_comm", "to": "Nat.zero_add"},
        ...
    ]
}
```

### 3. `theorem_stats.json` - Global Statistics

```json
{
    "total_theorems": 54475,
    "total_tactics": 168245,
    "total_premises": 180907,
    "proof_types": {"tactic": 45000, "term": 9000, "mixed": 475},
    "resolution_stats": {
        "leandojo_annotation": 322,
        "exact_match": 32979,
        "namespace_match": 25000,
        ...
    },
    "top_premises": [
        {"name": "Nat.add_comm", "usage_count": 1669},
        ...
    ]
}
```

---

## Implementation Steps

### Phase 1: Enhance Data Extraction (from traced_repo)

```python
# In demo-lean4.ipynb, add these extractions:

for tt in traced_thms:
    # NEW: Get theorem statement
    statement = tt.get_theorem_statement()
    
    # NEW: Get position info
    start_pos = tt.theorem.start
    end_pos = tt.theorem.end
    
    # NEW: Get docstring (if available)
    docstring = tt.comments if hasattr(tt, 'comments') else ""
    
    # NEW: Get file imports/namespaces from TracedFile
    tf = traced_repo.get_traced_file(file_path)
    imports = [str(i) for i in tf.imports] if hasattr(tf, 'imports') else []
```

### Phase 2: Enhanced Name Resolution

```python
def resolve_premise_v2(surface_name, context, open_namespaces, imports, corpus_index):
    """Enhanced resolution with multiple strategies."""
    
    # Strategy 1: Already qualified
    if surface_name in corpus_index["_exact_"]:
        return {"full_name": surface_name, "method": "exact", "confidence": 1.0}
    
    # Strategy 2: Namespace context
    for ns in open_namespaces:
        candidate = f"{ns}.{surface_name}"
        if candidate in corpus_index["_exact_"]:
            return {"full_name": candidate, "method": "namespace", "confidence": 0.95}
    
    # Strategy 3: Type-based resolution
    # ... (check variable types)
    
    # Strategy 4: Import-based
    # ... (check which imports have this name)
    
    # Fallback: suffix match
    candidates = corpus_index.get(surface_name, [])
    if len(candidates) == 1:
        return {"full_name": candidates[0], "method": "unique_suffix", "confidence": 0.6}
    elif candidates:
        return {"full_name": candidates[0], "method": "ambiguous", 
                "confidence": 0.3, "candidates": candidates}
    
    return {"full_name": surface_name, "method": "not_found", "confidence": 0.0}
```

### Phase 3: Build Unified File

```python
# Single unified output with all info
{
    "metadata": {
        "created": "2026-01-17",
        "source": "mathlib4",
        "commit": "...",
        "stats": {...}
    },
    "theorems": [...]  # JSONL format, one per line
}
```

---

## Quality Metrics to Track

| Metric | Target | Current |
|--------|--------|---------|
| Premise resolution rate | >95% | ~70% |
| High-confidence resolutions | >85% | ~43% |
| Theorems with full statement | 100% | 0% |
| Theorems with proof_text | 100% | ~50% |
| Theorems with dependencies | 100% | 0% |
| Unicode corruption rate | <1% | ~3% |

---

## Files to Create/Update

1. **`00_build_unified_traced_v2.py`** - Enhanced builder with all new fields
2. **`traced_theorems_unified_v2.jsonl`** - Main output file
3. **`premise_index.json`** - Fast premise lookup
4. **`dependency_graph.json`** - Theorem dependency graph
5. **`theorem_stats.json`** - Global statistics

---

## References

- [LeanDojo Documentation](https://leandojo.readthedocs.io/en/stable/traced_data.html)
- [LeanDojo Limitations](https://leandojo.readthedocs.io/en/stable/limitations.html)
- [Lean 4 Reference - Namespaces](https://lean-lang.org/doc/reference/latest/Source-Files-and-Modules/)
- [Lean.ResolveName API](https://leanprover-community.github.io/mathlib4_docs/Lean/ResolveName.html)
- [Mathlib4 Naming Conventions](https://leanprover-community.github.io/contribute/naming.html)
