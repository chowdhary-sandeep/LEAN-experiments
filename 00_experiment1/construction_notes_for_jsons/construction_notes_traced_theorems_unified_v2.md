# Construction Notes: traced_theorems_unified_v2.jsonl

## Overview

This document describes how `traced_theorems_unified_v2.jsonl` is constructed from LeanDojo's traced repository. The file contains theorem statements, proofs, tactics, and **resolved premises** extracted from proof text.

## Key Insight

**We parse proofs manually to extract premises, then filter out wrongly parsed premises (such as tactics), then create the unified file.**

The corpus (`corpus.jsonl`) is used as a **lookup table** for resolving surface premise names to fully qualified names, but the actual premise extraction happens by parsing the proof text (tactics) manually.

## Process Flow

### Step 1: Build Corpus (corpus.jsonl)

**Purpose**: Create a lookup table of all available premises (theorems, definitions, etc.) that can be used for resolution.

**Process**:
1. Iterate through all traced files in topological order
2. For each traced file, call `tf.get_premise_definitions()`
   - This returns **all theorems and definitions** defined in the file
   - Includes theorems with **both tactic proofs and term proofs**
   - Returns structured data with `full_name`, `def_path`, etc.
3. Export to `corpus.jsonl` with format:
   ```json
   {
     "path": "Mathlib/Algebra/Group/Defs.lean",
     "imports": ["..."],
     "premises": [
       {
         "full_name": "Mathlib.Algebra.Group.Defs.mul_assoc",
         "def_path": "...",
         ...
       },
       ...
     ]
   }
   ```

**Key Point**: The corpus includes **theorems** (from `get_premise_definitions()`), so when we resolve a premise name parsed from a tactic, we can match it against theorem names in the corpus if it's actually a theorem being used as a premise.

### Step 2: Initialize PremiseResolver

**Purpose**: Build indices from corpus for fast lookup during resolution.

**Process**:
1. Load `corpus.jsonl` line by line
2. For each premise entry:
   - Add `full_name` to exact match index (`_exact_` set)
   - Index by suffix (last component after `.`) for fuzzy matching
3. Result: Fast lookup structures for exact matches and suffix-based resolution

### Step 3: Process Each Theorem

For each theorem in the traced repository:

#### 3.1 Extract Basic Information
- Theorem name (`full_name`)
- File path
- Statement
- Proof type (tactic vs term)
- Position information
- Namespace context

#### 3.2 Process Tactics (if tactic proof)

For each tactic in the proof:

**3.2.1 Get Tactic Information**
- Raw tactic string
- State before/after
- LeanDojo annotated tactic (if available)
- LeanDojo premises (if available)

**3.2.2 Extract Premises from Tactic Text**

This is where **manual parsing** happens:

```python
def extract_surface_premises(tactic: str) -> list:
    """
    Pseudocode:
    
    1. Use regex pattern to find all identifiers in tactic string:
       pattern = r'\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\b'
       - Matches: identifiers like "add_comm", "Mathlib.Algebra.Group.Defs.mul_assoc"
       - Captures: qualified names (with dots) and simple names
    
    2. For each match:
       a. Skip if it's a tactic keyword (e.g., "simp", "rw", "apply", "exact")
       b. Skip if it's a single letter (likely a local variable)
       c. Skip if it matches hypothesis pattern (e.g., "h1", "h2", "ih", "IH")
       d. Otherwise, add to premises list
    
    3. Deduplicate while preserving order
    
    4. Return list of surface premise names
    """
    
    # Example tactic: "simp [add_comm, mul_assoc]"
    # Extracted: ["add_comm", "mul_assoc"]
    
    # Example tactic: "apply Nat.add_comm"
    # Extracted: ["Nat", "add_comm"]  (both captured, but "apply" filtered out)
    
    # Example tactic: "rw [h1, h2]"
    # Extracted: []  (all filtered: "rw" is keyword, "h1"/"h2" are hypotheses)
```

**3.2.3 Filter Out Wrongly Parsed Premises**

After extraction, we filter using `_is_tactic_or_hyp()`:

```python
def _is_tactic_or_hyp(name):
    """
    Pseudocode:
    
    1. Extract suffix (last component after '.')
    2. Check if suffix is in TACTIC_OR_HYP_FILTER set:
       - Tactics: "simp", "rw", "apply", "exact", "intro", "cases", etc.
       - Hypotheses: "h1", "h2", "ih", "IH", "this", "that", etc.
    3. Return True if it's a tactic/hypothesis, False otherwise
    """
```

**Filtered Items**:
- **Tactics**: `simpa`, `symm`, `rwa`, `mpr`, `mp`, `rfl`, `refl`, `simp`, `rw`, `apply`, `exact`, `intro`, `intros`, `refine`, `cases`, `rcases`, `obtain`, `induction`, `constructor`, `ring`, `linarith`, `omega`, `trivial`, `decide`, `aesop`, `ext`, `congr`, `have`, `show`, `from`, `by`, `left`, `right`, `split`, `contrapose`, `push_neg`, `norm_num`, `positivity`, `polyrith`, `nlinarith`, `field_simp`, `assumption`, `tidy`, `gcongr`, `rel_simp`, `erw`, `era`, `convert`, `ac_rfl`, `native_decide`
- **Hypotheses**: `hx`, `hf`, `hs`, `ha`, `hb`, `hc`, `hd`, `he`, `hh`, `hi`, `hj`, `hk`, `hl`, `hm`, `hn`, `ho`, `hp`, `hq`, `hr`, `ht`, `hu`, `hv`, `hw`, `hy`, `hz`, `h1`, `h2`, `h3`, `ih`, `IH`, `this`, `that`

**3.2.4 Resolve Premises**

Two priority levels:

**Priority 1: LeanDojo Annotations** (if available)
- Use `leandojo_premises` from `tac.get_annotated_tactic()`
- These are already fully qualified with high confidence
- Filter out tactics/hypotheses using `_is_tactic_or_hyp()`

**Priority 2: Manual Resolution** (if no LeanDojo annotations)
- For each surface name from `extract_surface_premises()`:
  - Call `resolver.resolve(surface_name, context, open_namespaces)`
  - Resolution methods (in priority order):
    1. **LeanDojo hint**: If provided and in corpus
    2. **Exact match**: Surface name already fully qualified
    3. **Namespace match**: Try `{namespace}.{surface_name}` for each open namespace
    4. **Type inference**: Infer namespace from variable types in context
    5. **Unique suffix**: If only one candidate with matching suffix
    6. **Ambiguous**: Return first candidate with list of alternatives
  - Filter out tactics/hypotheses using `_is_tactic_or_hyp()`

**3.2.5 Aggregate Premises**

- Track each premise across all tactics
- Count occurrences
- Track which tactics use each premise
- Compute average confidence

#### 3.3 Build Theorem Record

Structure:
```json
{
  "full_name": "Mathlib.Algebra.Group.Defs.mul_assoc",
  "file": "Mathlib/Algebra/Group/Defs.lean",
  "position": {"start": {...}, "end": {...}},
  "namespace": "Mathlib.Algebra.Group.Defs",
  "open_namespaces": [...],
  "statement": "...",
  "proof_type": "tactic",
  "proof_text": "...",
  "tactics": [
    {
      "index": 0,
      "tactic": "simp [add_comm]",
      "annotated_tactic": "...",
      "state_before": "...",
      "state_after": "...",
      "context": {...},
      "premises": [
        {
          "surface_name": "add_comm",
          "full_name": "Mathlib.Algebra.Group.Defs.add_comm",
          "resolution_method": "namespace_match",
          "confidence": 0.95
        }
      ],
      "is_terminal": false,
      "num_goals_before": 1,
      "num_goals_after": 0
    },
    ...
  ],
  "all_premises": {
    "Mathlib.Algebra.Group.Defs.add_comm": {
      "count": 3,
      "tactics": [0, 2, 5],
      "avg_confidence": 0.95
    },
    ...
  },
  "metrics": {...},
  "quality": {...}
}
```

### Step 4: Write to JSONL

Each theorem record is written as one line in `traced_theorems_unified_v2.jsonl`.

## Key Design Decisions

1. **Manual Parsing**: We parse proof text (tactics) manually using regex, rather than relying solely on LeanDojo annotations, because:
   - LeanDojo annotations may be incomplete
   - We want to capture all premise usages, even if not annotated
   - Manual parsing gives us more control over extraction

2. **Filtering**: We explicitly filter out tactics and hypotheses because:
   - Regex extraction is imprecise and captures many false positives
   - Tactics like "simp" and "rw" are not premises
   - Hypothesis names like "h1" are local, not global premises

3. **Corpus as Lookup**: The corpus includes theorems because:
   - Theorems can be used as premises in other proofs
   - When we parse "add_comm" from a tactic, it might be a theorem name
   - The corpus provides the full qualified name for resolution

4. **Resolution Priority**: We prioritize LeanDojo annotations over manual resolution because:
   - LeanDojo annotations are more accurate (from AST analysis)
   - Manual resolution is fallback when annotations unavailable
   - Confidence scores reflect this priority

## Example: Complete Flow

**Input**: Tactic `"simp [add_comm, mul_assoc]"` in proof context

**Step 1 - Extract**:
```python
extract_surface_premises("simp [add_comm, mul_assoc]")
# Returns: ["add_comm", "mul_assoc"]
# Note: "simp" filtered out (tactic keyword)
```

**Step 2 - Filter**:
```python
_is_tactic_or_hyp("add_comm")  # False (not in filter)
_is_tactic_or_hyp("mul_assoc")  # False (not in filter)
# Both pass filter
```

**Step 3 - Resolve**:
```python
resolver.resolve("add_comm", context, open_namespaces)
# Tries: "Mathlib.Algebra.Group.Defs.add_comm" (namespace match)
# Returns: {
#   "surface_name": "add_comm",
#   "full_name": "Mathlib.Algebra.Group.Defs.add_comm",
#   "resolution_method": "namespace_match",
#   "confidence": 0.95
# }
```

**Step 4 - Write**:
Premise included in `tactics[].premises` and aggregated in `all_premises`.

## Statistics Tracked

- Total theorems processed
- Tactic proofs vs term proofs
- Total tactics processed
- Total premises extracted
- Resolution method breakdown (leandojo_annotation, exact_match, namespace_match, etc.)
- High confidence (>=0.6) vs low confidence (<0.6) resolutions

## Output Files

1. **traced_theorems_unified_v2.jsonl**: Main output with all theorem records
2. **theorem_stats_v2.json**: Statistics summary
3. **premise_index_v2.json**: Index of all resolved premises
4. **corpus.jsonl**: Lookup table of available premises (built first)

## Notes

- **Term proofs**: For theorems with term proofs (not tactic proofs), we don't extract premises from tactics (there are none). The proof text is stored but not parsed.
- **Confidence scores**: Reflect resolution method reliability (1.0 for LeanDojo, 0.95 for namespace match, 0.6 for unique suffix, etc.)
- **Cross-references**: The corpus includes theorems, so when theorem A uses theorem B as a premise, we can resolve "B" to its full name "Mathlib.X.Y.B" using the corpus lookup.
