# Premise Dependency Graph Analysis

## Research Questions

### 1. General Statistics of the Theorem Dependency DAG

This analysis focuses on the theorem-to-premise dependency network (not import-based dependencies, but actual usage dependencies). We examine:

- **Network topology**: Structure, connectivity, and hierarchical organization of the theorem-premise dependency graph
- **Degree distributions**: How theorems depend on premises and how premises are used across theorems
- **Path analysis**: Longest dependency chains and topological levels in the DAG
- **Component analysis**: Weakly connected components and their sizes
- **Extreme nodes**: Identification of highly connected premises (frequently used) and theorems (using many premises)

**Interpretation and Extensions:**

The theorem-premise dependency DAG reveals the knowledge structure of the mathematical library. Understanding this structure helps identify:
- **Core premises**: Fundamental lemmas that are widely used across many theorems
- **Bottleneck theorems**: Theorems that depend on many premises, potentially indicating complexity
- **Dependency chains**: Long paths may indicate areas where intermediate lemmas could simplify proofs
- **Isolated components**: Groups of theorems/premises that are independent, suggesting modular structure

Future extensions could include:
- Temporal analysis: How the dependency network evolves as new theorems are added
- Complexity metrics: Correlating network position with proof complexity
- Refactoring opportunities: Identifying nodes that could be abstracted or simplified

### 2. Description Length Trade-off: New Lemmas vs. Null Models

**Problem Statement:**

When introducing a new lemma (node `v`) in the dependency DAG, there is a trade-off between:
- **Cost**: The description length `L(v)` required to define the new lemma (increases MDL)
- **Benefit**: Compression of downstream definitions by replacing multiple predecessor nodes with the new lemma

**Formal Definition:**

For a node `v` in the DAG:
- **Predecessors**: Nodes `i` such that there exists a path `i → ... → v`
- **Descendants**: Nodes `j` such that there exists a path `v → ... → j`

**Null Model (without `v`):**
- Each descendant `j` is defined in terms of its direct predecessors `nodes(i)`
- Description length: `L(j, old) = f(nodes(i))` where `f` encodes the definition using all predecessor nodes

**With New Lemma `v`:**
- Node `v` is defined: `L(v)` (cost)
- Descendants `j` can be redefined using `v` instead of some subset of `nodes(i)`
- Description length: `L(j, new) = f(v, remaining_nodes)` where `v` replaces some `nodes(i)`

**Trade-off Calculation:**

For each descendant `j`, the compression benefit is:
```
ΔL(j) = L(j, old) - L(j, new)
```

Total description length change:
```
ΔL_total = L(v) - Σ_j ΔL(j)
```

**Key Constraint:**

Not all predecessor-descendant pairs `(i, j)` are needed. For a given descendant `j`, only a subset of predecessors `i` are actually required in the definition. This selective dependency is what makes the compression possible.

**Interpretation and Extensions:**

This framework models the **abstraction vs. verbosity** trade-off in mathematical libraries:

- **When to introduce a lemma**: When `ΔL_total < 0` (net compression)
- **Optimal abstraction level**: Finding the right granularity of lemmas that maximizes compression
- **Redundancy detection**: Identifying cases where `L(v)` is small but compression is large (high-value abstractions)

**Extensions:**

1. **Multi-level abstraction**: Consider chains of abstractions `v₁ → v₂ → ... → vₖ` and compute total compression
2. **Context-dependent compression**: Some definitions may become longer when using `v` (e.g., if `v` requires additional type constraints), so `L(j, new)` can also increase
3. **Future node impact**: New nodes added later may benefit from `v`, changing the compression calculation dynamically
4. **Empirical validation**: Measure actual code size changes when refactoring to introduce new lemmas
5. **Optimal lemma discovery**: Algorithm to find nodes `v` that maximize `-ΔL_total` (maximum compression)

**Connection to MDL Principle:**

This aligns with the Minimum Description Length (MDL) principle: the best representation is the one that minimizes the total description length of the data (theorems) plus the model (lemmas). The dependency DAG structure provides a natural framework for computing these description lengths.

## Previous Work by Others

### LeanProver Community / Mathlib

The LeanProver community has explored theorem-level dependency graphs and related tooling:

#### Theorem-level Dependency Graph Discussion

In December 2025, there was a discussion on the Mathlib Zulip about theorem-level dependency graphs:

- **Thread**: [Theorem-level dependency graph](https://leanprover-community.github.io/archive/stream/239415-metaprogramming-/-tactics/topic/Theorem-level.20dependency.20graph.html)
  - Yury G. Kudryashov asked about tools similar to `lake exe graph` but for theorems, to help identify unused theorems and understand dependencies
  - Adam Topaz provided a solution using `Lean.Name.transitivelyUsedConstants` to get transitive dependencies of constants
  - A script was shared that extracts dependencies and generates dependency graphs
  - The discussion included generating lists of unused declarations and visualizing dependency graphs

- **Metaprogramming / Tactics Stream**: [Archive](https://leanprover-community.github.io/archive/stream/239415-metaprogramming-/-tactics/index.html)
  - Contains various discussions about metaprogramming, tactics, and dependency analysis tools

- **PhysLean Stream**: [New members](https://leanprover-community.github.io/archive/stream/479953-PhysLean/topic/New.20members.html)
  - Community discussions about contributing to PhysLean and related projects

### Key Techniques Mentioned

1. **`Lean.Name.transitivelyUsedConstants`**: Used to get transitive dependencies of constants in the environment
2. **Dependency graph generation**: Scripts to visualize theorem dependencies
3. **Unused declaration detection**: Tools to identify theorems that are not used in proofs

### Related Tools

- `lake exe graph`: Existing tool for file-level dependency graphs
- `#show_unused`: Command helpful for identifying unused declarations
- Custom scripts using Lean's metaprogramming capabilities to analyze theorem dependencies

## Premise Extraction Analysis: Issues and Improvements

### Overview

Analysis of premise extraction from tactics in `00_full_tactic_to_premises.json` reveals several categories of issues: Unicode encoding bugs, false positives (local terms misclassified as premises), and missing extractions.

### 1. Unicode Encoding Bug - "â" Instead of Actual Lemmas

**Problem:**
- `"rw [← mk_uLift, ← mk_uLift]"` → extracts `"â"` instead of `"mk_uLift"`
- `"rw [← lift_id #_, ← lift_id #R[X]]"` → extracts `"â"` instead of `"lift_id"`
- `"rw [← le_aleph0_iff_set_countable, ← lift_le_aleph0]"` → extracts `"â"` instead of the actual lemmas

**Root Cause:**
The Unicode left arrow `←` (U+2190) is being corrupted during normalization, likely due to encoding issues. The regex `p.lstrip("←→↔⟵⟶⟷⟹")` should strip it, but if normalization fails, the arrow becomes `"â"` and gets extracted as a candidate.

**Missing Premises:**
- `mk_uLift`
- `lift_id`
- `lift_le_aleph0`
- `le_aleph0_iff_set_countable` (when arrows are present)

**Example from JSON:**
```json
{
  "  rw [← mk_uLift, ← mk_uLift]": {
    "extracted_premises": {
      "â": 1
    }
  }
}
```

### 2. Local Terms Misclassified as Premises (False Positives)

#### 2.1 Local Variable Access Patterns

**Problem:**
- `"x.coe_prop"` from `choose g hg₁ hg₂ using fun x : { x : A | IsAlgebraic R x } => x.coe_prop`
- `"f.rootSet"` and `"f.rootSet_finite"` from `f.rootSet A` and `f.rootSet_finite A`

**Analysis:**
These are accessing properties of local variables (`x`, `f`), not global lemmas. They should be filtered out.

**Example from JSON:**
```json
{
  "  choose g hg₁ hg₂ using fun x : { x : A | IsAlgebraic R x } => x.coe_prop": {
    "extracted_premises": {
      "x.coe_prop": 1
    }
  }
}
```

#### 2.2 Local Proof Terms

**Problem:**
- `"this.countable_of_injOn"` from `suffices MapsTo (↑) (g ⁻¹' {f}) (f.rootSet A) from this.countable_of_injOn ...`

**Analysis:**
`this` is a local proof term referring to a hypothesis, not a global lemma. Should be filtered.

**Example from JSON:**
```json
{
  "  suffices MapsTo (↑) (g ⁻¹' {f}) (f.rootSet A) from\n    this.countable_of_injOn Subtype.coe_injective.injOn (f.rootSet_finite A).countable": {
    "extracted_premises": {
      "this.countable_of_injOn": 1,
      "f.rootSet": 1,
      "f.rootSet_finite": 1
    }
  }
}
```

#### 2.3 Type/Class Names in Type Annotations

**Problem:**
- `"MapsTo"` from `MapsTo (↑) (g ⁻¹' {f}) (f.rootSet A)`

**Analysis:**
This is a type/class name being used in a type annotation, not necessarily a premise being applied. Context-dependent: could be a premise if it's a lemma, but here it's likely a type.

**Example from JSON:**
```json
{
  "  suffices MapsTo (↑) (g ⁻¹' {f}) (f.rootSet A) from ...": {
    "extracted_premises": {
      "MapsTo": 1
    }
  }
}
```

### 3. Correct Extractions (Working as Expected)

**Good Examples:**

1. **Direct lemma applications:**
   - `"lift_mk_le_lift_mk_mul_of_lift_mk_preimage_le"` from `refine lift_mk_le_lift_mk_mul_of_lift_mk_preimage_le g fun f => ?_` ✓
   - `"cardinal_mk_lift_le_mul"` from `exact cardinal_mk_lift_le_mul R A` ✓

2. **Multiple lemmas in rewrite lists:**
   - `"le_aleph0_iff_set_countable"` and `"lift_le_aleph0"` from `rw [lift_le_aleph0, le_aleph0_iff_set_countable]` ✓

3. **Dotted lemma names:**
   - `"Subtype.coe_injective.injOn"` from `Subtype.coe_injective.injOn` ✓

4. **Projections on lemmas:**
   - `"mem_rootSet"` and `"mem_rootSet.2"` from `exact mem_rootSet.2 ⟨hg₁ x, hg₂ x⟩` ✓
   - Both the base lemma and projection are correctly extracted

**Example from JSON:**
  ```json
{
  "  rw [lift_le_aleph0, le_aleph0_iff_set_countable]": {
    "extracted_premises": {
      "le_aleph0_iff_set_countable": 1,
      "lift_le_aleph0": 1
    },
    "premise_percentages": {
      "le_aleph0_iff_set_countable": 50.0,
      "lift_le_aleph0": 50.0
    }
  }
}
```

### 4. Edge Cases and Missing Patterns

#### 4.1 Type Annotations/Placeholders

**Observation:**
- `#_`, `#R[X]` in `rw [← lift_id #_, ← lift_id #R[X]]` are correctly ignored (not lemmas)
- These are type annotations/placeholders, not premises

#### 4.2 Projections on Local Terms vs Global Lemmas

**Issue:**
- `mem_rootSet.2` is correctly extracted (projection on global lemma)
- But `this.countable_of_injOn` should be filtered (projection on local term)
- Need to distinguish: `LemmaName.2` (global) vs `localVar.property` (local)

#### 4.3 Implicit Lemmas

**Missing:**
- Some tactics use lemmas implicitly (e.g., `simp` without an explicit list)
- These won't be extracted by the current regex-based approach
- Would require running tactics to see what they actually use

#### 4.4 Qualified Names in Different Contexts

**Observation:**
- `Subtype.coe_injective.injOn` - correctly extracted (global qualified name)
- But `f.rootSet` should be filtered (local variable access)
- Current code tries to handle `rootSet` patterns but `f.rootSet` isn't caught

### 5. Recommendations for Improvement

#### High Priority

1. **Fix Unicode Normalization**
   - Ensure `←` (U+2190) is properly handled and stripped
   - Test with various Unicode arrow representations
   - Add encoding validation in `normalize_unicode_symbols()`

2. **Filter Local Variable Access Patterns**
   - Detect patterns like `variableName.property` and `this.method`
   - Add regex patterns to identify local variable prefixes (single lowercase letters, common names like `x`, `f`, `g`, `h`, `this`)
   - Filter before adding to candidates set

3. **Filter Type/Class Names in Type Annotations**
   - `MapsTo` in `MapsTo (↑) ...` is likely a type
   - Context-aware filtering: if it appears in a type annotation position, consider filtering
   - May need more sophisticated parsing

#### Medium Priority

4. **Better Handling of `#` Placeholders**
   - Already handled correctly, but document the behavior
   - Ensure `#_` and `#TypeName` patterns are consistently ignored

5. **Distinguish Projections on Lemmas vs Local Terms**
   - `Lemma.2` vs `local.property`
   - Use context: if the base name is a known lemma, extract; if it's a local variable, filter

#### Low Priority

6. **Handle Implicit Lemmas**
   - Would require running tactics to see what they actually use
   - Significant performance impact, probably not worth it for surface-level extraction

7. **Better Context Awareness**
   - Understand when a name is a type vs a lemma
   - Would require more sophisticated parsing or proof context

### Summary

**False Detections (Should be Filtered):**
- `"â"` (Unicode corruption)
- `"x.coe_prop"` (local variable access)
- `"this.countable_of_injOn"` (local proof term)
- `"f.rootSet"`, `"f.rootSet_finite"` (local variable properties)
- `"MapsTo"` (likely a type name in this context)

**Missing (Should be Extracted):**
- `"mk_uLift"` (due to Unicode issue)
- `"lift_id"` (due to Unicode issue)
- Actual lemmas behind local terms like `this.countable_of_injOn` (would need proof context to resolve)

**Correctly Extracted:**
- Most direct lemma applications (`exact`, `refine`, `rw` with proper syntax)
- Dotted lemma names (`Subtype.coe_injective.injOn`)
- Projections on lemmas (`mem_rootSet.2`)

**Main Issues:**
1. Unicode handling - arrows corrupting extraction
2. Filtering local terms vs global lemmas - need better pattern detection
3. Context awareness - distinguishing types from lemmas, local from global

---

## High-Frequency Tactics Analysis (Lines 71-431)

### Overview

Analysis of the most frequently occurring tactic blocks reveals systematic issues with local hypothesis detection. The top tactics by frequency are dominated by patterns using local terms.

### 1. High-Frequency False Positives

#### 1.1 The `"this"` Problem (Most Common False Positive)

**Examples:**
| Tactic | Extracted | Count | % of Proofs |
|--------|-----------|-------|-------------|
| `rw [this]` | `"this"` | 145 | 0.27% |
| `rw [this]` (indented) | `"this"` | 65 | 0.12% |
| `exact this` | `"this"` | 47 | 0.09% |
| `rw [this]` (double indent) | `"this"` | 20 | 0.04% |
| `simp_rw [this]` | `"this"` | 19 | 0.03% |
| `exact this` (indented) | `"this"` | 16 | 0.03% |
| `simp [this]` (indented) | `"this"` | 16 | 0.03% |

**Analysis:**
- `this` is a Lean keyword referring to the most recent hypothesis or goal
- Not a global lemma; always refers to local proof context
- **Total: 328+ occurrences** across these patterns alone

**Impact:** Very high — `this` is one of the most frequent "premises" extracted

#### 1.2 Single-Letter Hypothesis Names

**Examples:**
| Tactic | Extracted | Count | % of Proofs |
|--------|-----------|-------|-------------|
| `exact h` | `"h"` | 59 | 0.11% |
| `simp [h]` (bullet) | `"h"` | 56 | 0.10% |
| `rw [h]` | `"h"` | 47 | 0.09% |
| `simp [h]` | `"h"` | 35 | 0.06% |
| `apply h` | `"h"` | 32 | 0.06% |
| `by simp [h]` | `"h"` | 25 | 0.05% |
| `exact h` (indented) | `"h"` | 21 | 0.04% |
| `apply h` (indented) | `"h"` | 21 | 0.04% |
| `simp [h]` (indented) | `"h"` | 20 | 0.04% |
| `exact h` (bullet) | `"h"` | 19 | 0.03% |
| `split_ifs with h <;> simp [h]` | `"h"` | 16 | 0.03% |
| `rw [h]` (indented) | `"h"` | 15 | 0.03% |

**Analysis:**
- `h` is the most common hypothesis name in Lean proofs
- Almost always a local hypothesis, not a global lemma
- **Total: 366+ occurrences** of `"h"` alone

#### 1.3 Other Local Hypothesis Patterns

**Examples:**
| Tactic | Extracted | Issue |
|--------|-----------|-------|
| `simp [h0]` | `"h0"` | Numbered hypothesis |
| `simp [hG]` | `"hG"` | Named local hypothesis |
| `simpa ... using hf.add hg.neg` | `"hf.add"`, `"hg.neg"` | Local hypothesis method calls |

### 2. Unicode Corruption Patterns

**Examples:**
| Tactic | Extracted | Should Be |
|--------|-----------|-----------|
| `refine ⟨fun h => ?_, fun h => ?_⟩` | `"â"` | (nothing - constructor syntax) |
| `refine ⟨fun h => ?_, ?_⟩` | `"â"` | (nothing) |
| `rw [← this]` | `"â"` | `"this"` (then filter as local) |
| `rw [← sub_eq_zero]` | `"â"` | `"sub_eq_zero"` |
| `refine ⟨fun h ↦ ?_, fun h ↦ ?_⟩` | `"â"` | (nothing) |
| `refine ⟨fun h ↦ ?_, ?_⟩` | `"â"` | (nothing) |

**Root Cause:** 
- Unicode characters `⟨⟩` (angle brackets), `←` (left arrow), `↦` (maps to) are being corrupted
- Corruption produces `"â"` which gets extracted as a "premise"
- **Total: 138+ occurrences** of `"â"` in top tactics

### 3. Correct Extractions (Real Lemmas)

**Examples:**
| Tactic | Extracted | Count | Notes |
|--------|-----------|-------|-------|
| `apply le_antisymm` | `"le_antisymm"` | 165 | ✓ Real lemma |
| `rw [add_comm]` | `"add_comm"` | 47 | ✓ Real lemma |
| `rw [mul_comm]` | `"mul_comm"` | 42 | ✓ Real lemma |
| `refine le_antisymm ?_ ?_` | `"le_antisymm"` | 34 | ✓ Real lemma |
| `induction θ using Real.Angle.induction_on` | `"Real.Angle.induction_on"` | 23 | ✓ Real qualified lemma |
| `exact Iff.rfl` | `"Iff.rfl"` | 22 | ✓ Real lemma |
| `exact le_rfl` | `"le_rfl"` | 20 | ✓ Real lemma |
| `induction p using Polynomial.induction_on'` | `"Polynomial.induction_on"` | 20 | ✓ Real lemma |
| `rw [eq_top_iff]` | `"eq_top_iff"` | 19 | ✓ Real lemma |
| `apply forall_congr'` | `"forall_congr'"` | 18 | ✓ Real lemma |
| `apply Subtype.ext` | `"Subtype.ext"` | 18 | ✓ Real lemma |
| `apply Subset.antisymm` | `"Subset.antisymm"` | 16 | ✓ Real lemma |

### 4. Edge Cases: Mixed Local/Global

**Examples:**
| Tactic | Extracted | Analysis |
|--------|-----------|----------|
| `rw [neg_inj, oangle_rev, ← ...] at h ⊢` | `"neg_inj"`, `"oangle_rev"`, `"â"` | Mixed: 2 real lemmas + Unicode bug |
| `simp [integral, hG]` | `"integral"`, `"hG"` | Mixed: 1 possible definition + 1 local |
| `simpa ... using hf.add hg.neg` | `"hf.add"`, `"hg.neg"`, `"sub_eq_add_neg"` | Mixed: 1 real lemma + 2 local method calls |

### 5. The `"only"` Problem

**Example:**
  ```json
{
  "  simp only": {
    "extracted_premises": {
      "only": 17
    }
  }
}
```

**Analysis:**
- `only` is a keyword modifier for `simp`, not a lemma
- Should not be extracted at all
- This happens because the regex captures the word after `simp`

---

## Comprehensive Plan: Parsing Lean 4/Mathlib Proofs

### Background: Lean 4 Proof Structure

Based on the [Lean Reference Manual](https://leanprover.github.io/reference/), proofs in Lean can contain several distinct categories of identifiers:

#### Reference: Lean Syntax Categories

From [Chapter 6: Tactics](https://leanprover.github.io/reference/tactics.html):

1. **Tactics**: Commands that manipulate proof goals
   - Basic: `intro`, `apply`, `exact`, `refine`, `have`, `let`, `show`
   - Rewriting: `rw`, `simp`, `simp_rw`, `conv`
   - Induction: `induction`, `cases`, `rcases`, `obtain`
   - Automation: `ring`, `linarith`, `omega`, `decide`, `trivial`

2. **Terms/Expressions**: Values used in proofs
   - Global lemmas/theorems: Named results from libraries
   - Local hypotheses: Introduced by `intro`, `have`, etc.
   - Definitions: Named values from `def`, `let`
   - Type class instances: Resolved automatically

3. **Syntax Elements**: Not premises
   - Keywords: `by`, `fun`, `match`, `with`, `let`, `in`, `do`
   - Modifiers: `only`, `using`, `at`, `with`
   - Punctuation: `⟨⟩`, `←`, `→`, `↦`, `⊢`

### Meta-Rules for Detection

#### Rule 1: Keyword/Modifier Blacklist

**Filter these unconditionally:**
```python
KEYWORDS = {
    # Tactic keywords
    "by", "fun", "match", "with", "let", "in", "have", "show", "from",
    "do", "return", "if", "then", "else", "where",
    
    # Tactic names (not premises)
    "intro", "intros", "rintro", "apply", "exact", "refine", "rw", "simp",
    "simp_all", "simp_rw", "aesop", "assumption", "constructor", "cases",
    "rcases", "obtain", "induction", "ring", "linarith", "omega", "trivial",
    "decide", "norm_num", "positivity", "polyrith", "nlinarith",
    
    # Modifiers (not premises)
    "only", "using", "at", "with",
    
    # Logic keywords
    "forall", "exists", "True", "False", "And", "Or", "Not",
    
    # Placeholders
    "_", "?", "??", "*",
}
```

#### Rule 2: Local Hypothesis Detection

**Pattern: Single lowercase letter or common hypothesis names**
```python
LOCAL_HYPOTHESIS_PATTERNS = [
    r"^[a-z]$",           # Single lowercase letter: h, x, f, g, etc.
    r"^[a-z]\d+$",        # Letter + number: h1, h2, x0, etc.
    r"^h[A-Z][a-z]*$",    # h + capitalized: hP, hQ, hG, hF, etc.
    r"^this$",            # The special "this" keyword
    r"^ih$",              # Induction hypothesis
    r"^IH$",              # Induction hypothesis (caps)
]
```

#### Rule 3: Local Variable Access Detection

**Pattern: `localVar.property` where `localVar` is lowercase**
```python
def is_local_variable_access(name):
    """Detect patterns like x.coe_prop, f.rootSet, this.method"""
    if "." not in name:
        return False
    prefix = name.split(".")[0]
    # Single lowercase letter or "this"
    if len(prefix) == 1 and prefix.islower():
        return True
    if prefix == "this":
        return True
    # Common local variable names
    if prefix in {"hf", "hg", "hp", "hq", "hs", "ht", "hu", "hv", "hw"}:
        return True
    return False
```

#### Rule 4: Qualified Name Detection (Global Lemmas)

**Pattern: `Namespace.Name` where `Namespace` is capitalized**
```python
def is_qualified_global_name(name):
    """Detect patterns like Subtype.ext, Real.Angle.induction_on"""
    if "." not in name:
        return False
    parts = name.split(".")
    # First part should be capitalized (namespace)
    if parts[0] and parts[0][0].isupper():
        return True
    return False
```

#### Rule 5: Projection Detection

**Pattern: `Name.1`, `Name.2`, `Name.mp`, `Name.mpr`**
```python
PROJECTIONS = {"1", "2", "mp", "mpr", "symm", "trans", "refl"}

def handle_projection(name):
    """Handle lemma projections like mem_rootSet.2"""
    if "." not in name:
        return name
    parts = name.rsplit(".", 1)
    if parts[1] in PROJECTIONS:
        # Return base name (the actual lemma)
        return parts[0]
    return name
```

#### Rule 6: Unicode Arrow Handling

**Fix the encoding issue:**
```python
def normalize_arrows(text):
    """Properly handle Unicode arrows before extraction"""
    # Ensure proper encoding
    if isinstance(text, bytes):
        text = text.decode('utf-8')
    
    # Strip arrows from start of tokens
    ARROWS = "←→↔⟵⟶⟷⟹↦"
    
    # Handle angle brackets (constructor syntax)
    BRACKETS = "⟨⟩"
    
    return text
```

### Classification Schema

Based on the analysis, categorize extracted items into:

#### Category 1: Global Lemmas (KEEP)
- Qualified names: `Subtype.ext`, `Real.Angle.induction_on`
- Known lemma names: `le_antisymm`, `add_comm`, `mul_comm`
- Lemma projections: `mem_rootSet.2` → `mem_rootSet`

#### Category 2: Local Hypotheses (FILTER)
- Single letters: `h`, `x`, `f`, `g`, `a`, `b`, etc.
- Numbered: `h1`, `h2`, `x0`, etc.
- Named locals: `hf`, `hg`, `hP`, `hQ`, etc.
- Special: `this`, `ih`, `IH`

#### Category 3: Local Variable Access (FILTER)
- Patterns: `x.property`, `f.method`, `this.something`
- Detected by: lowercase prefix + dot + anything

#### Category 4: Keywords/Modifiers (FILTER)
- Tactic names: `simp`, `rw`, `apply`, etc.
- Modifiers: `only`, `using`, `at`, `with`
- Syntax keywords: `by`, `fun`, `match`, etc.

#### Category 5: Corrupted Unicode (FIX)
- `"â"` and similar garbage from encoding issues
- Fix by improving Unicode handling, then re-extract

#### Category 6: Type/Definition Names (CONTEXT-DEPENDENT)
- May be premises in some contexts
- Examples: `integral`, `MapsTo`
- Requires deeper analysis to classify

### Proposed JSON Structure

```json
{
  "tactic_block": "apply le_antisymm",
  "tactic_type": "apply",
  "extracted_items": {
    "global_lemmas": ["le_antisymm"],
    "local_hypotheses": [],
    "local_var_access": [],
    "filtered_keywords": [],
    "unknown": []
  },
  "counts": {
    "total": 165,
    "percentage": 0.30
  },
  "quality": {
    "has_unicode_issues": false,
    "all_classified": true
  }
}
```

### Implementation Plan

#### Phase 1: Filtering (Immediate)
1. Add `"this"` to `_STOP` set
2. Add single-letter filter: `^[a-z]$`
3. Add numbered hypothesis filter: `^[a-z]\d+$`
4. Add `"only"` to `_STOP` set

#### Phase 2: Unicode Fix (High Priority)
1. Fix `normalize_unicode_symbols()` to handle `←`, `⟨⟩`, `↦` properly
2. Test with various Unicode representations
3. Re-run extraction

#### Phase 3: Classification (Medium Priority)
1. Implement `is_local_variable_access()` filter
2. Implement `is_qualified_global_name()` detector
3. Implement `handle_projection()` normalizer

#### Phase 4: Validation (After Implementation)
1. Re-run extraction with new filters
2. Compare statistics before/after
3. Manual review of edge cases
4. Document remaining issues

### Expected Impact

**Current State (Top 20 tactics):**
- False positives: ~70% (`this`, `h`, `â`, `only`)
- Correct: ~30% (real lemmas)

**After Implementation:**
- False positives: <10% (edge cases)
- Correct: >90% (real lemmas + filtered locals)

### References

- [Lean Reference Manual - Tactics](https://leanprover.github.io/reference/tactics.html)
- [Mathlib Tactics Documentation](https://leanprover-community.github.io/mathlib_docs/tactics.html)
- [Lean 4 Metaprogramming](https://leanprover.github.io/lean4/doc/metaprogramming/)

---

## Post-Implementation Analysis: Remaining Issues (January 2026)

After running categorized extraction on 54,475 proofs (168,245 unique tactic blocks), we identified several remaining issues.

### 1. Leading/Trailing Whitespace in Tactic Blocks

**Problem:** Tactic blocks retain indentation, creating duplicates:
```
'  constructor'    # 1440 occurrences
'    constructor'  # different entry
'  · simp'         # bullet + indent
```

**Impact:** Same tactic appears multiple times with different whitespace, fragmenting statistics.

**Fix:** Strip leading/trailing whitespace from tactic blocks before categorization.

### 2. Missing Tactics in Keyword Blacklist

**Currently classified as `global_lemmas` but are actually tactics:**

| Item | Count | Should Be |
|------|-------|-----------|
| `filter_upwards` | 1036 | `keywords_modifiers` |
| `split_ifs` | 865 | `keywords_modifiers` |
| `mod_cast` | 354 | `keywords_modifiers` |
| `tfae_have` | 236 | `keywords_modifiers` |
| `infer_instance` | 88 | `keywords_modifiers` |
| `tfae_finish` | 50 | `keywords_modifiers` |

**Currently in `other` category but are tactics:**

| Item | Count | Should Be |
|------|-------|-----------|
| `rwa` | 2703 | `keywords_modifiers` |
| `classical` | 1162 | `keywords_modifiers` |
| `haveI` | 1148 | `keywords_modifiers` |
| `mono` | 1146 | `keywords_modifiers` |
| `erw` | 1095 | `keywords_modifiers` |
| `replace` | 912 | `keywords_modifiers` |

### 3. Projection Suffixes Appearing Standalone

**In `other` category as standalone items:**

| Item | Count | Analysis |
|------|-------|----------|
| `mpr` | 2938 | Projection suffix `.mpr` extracted alone |
| `mp` | 2722 | Projection suffix `.mp` extracted alone |
| `le` | 1987 | Could be projection or standalone |
| `ne` | 1707 | Projection suffix `.ne` |
| `assoc` | 922 | Could be lemma suffix `_assoc` |
| `inr` | 919 | Constructor `Or.inr` or `Sum.inr` |
| `inl` | 907 | Constructor `Or.inl` or `Sum.inl` |

**Fix:** Filter standalone `mp`, `mpr`, `ne`, `le` when they appear alone (not as lemma suffix).

### 4. Single Uppercase Letters = Type Variables

**In `other` category (should be `type_variables`):**

| Item | Count | Meaning |
|------|-------|---------|
| `R` | 3902 | Ring/Semiring type |
| `A` | 2972 | Algebra/Type |
| `F` | 2510 | Field/Function type |
| `K` | 2481 | Field type |
| `X` | 2227 | General type |
| `I` | 2200 | Ideal/Index type |
| `S` | 2184 | Set/Semiring type |
| `L` | 1967 | Lattice/Type |
| `M` | 1839 | Module type |
| `C` | 1813 | Category type |
| `E` | 1713 | Type |
| `B` | 1675 | Type |
| `G` | 1416 | Group type |
| `P` | 1396 | Predicate/Type |

**Fix:** Add new category `type_variables` for single uppercase letters.

### 5. Namespace Names Appearing as Items

**In `other` category (should be `namespaces`):**

| Item | Count | Analysis |
|------|-------|----------|
| `ENNReal` | 2447 | Extended non-negative reals namespace |
| `Function` | 1756 | Function namespace |
| `Submodule` | 1484 | Submodule namespace |
| `LinearMap` | 1329 | LinearMap namespace |
| `Subtype` | 1215 | Subtype namespace |
| `Pi` | 1151 | Pi namespace |
| `Ideal` | 1012 | Ideal namespace |
| `Finsupp` | 838 | Finsupp namespace |

**Fix:** Add new category `namespaces` for known Mathlib namespaces.

### 6. Local Hypothesis Patterns Missed

**Currently in `global_lemmas` but are local hypotheses:**

Pattern: `h` + underscore + descriptive suffix
- `hp_pos` (80), `h_eq` (124), `h_top` (59), `h_zero` (84)
- `ha_top` (11), `hb_top` (1), `h_cover` (10)
- `h_rpow` (9), `h_frac` (3), `h_sum_nnreal` (2)

Pattern: Hypothesis with projection
- `hw'.symm`, `hp_pos.ne`, `h_add.le`, `hp_pos.ne'`
- `h_rpow_add_rpow_le_add` (4)

**Fix:** Extend `_LOCAL_HYPOTHESIS_PATTERNS` to catch:
- `h[a-z]?_[a-z]+` patterns (e.g., `h_eq`, `ha_top`)
- `h` + any suffix + `.` + projection

### 7. Corrupted Unicode Still Present

| Item | Count |
|------|-------|
| `â` | 35039 |
| `ð` | 205 |

**Root cause:** `←` (U+2190) corrupting to `â` during UTF-8 processing.

**Fix:** Ensure proper UTF-8 handling throughout; filter corrupted chars earlier.

### Summary: Fixes Needed

1. **Strip whitespace** from tactic blocks
2. **Add missing tactics** to `_KEYWORDS_MODIFIERS`:
   - `filter_upwards`, `split_ifs`, `mod_cast`, `tfae_have`, `tfae_finish`, `infer_instance`
   - `rwa`, `classical`, `haveI`, `mono`, `erw`, `replace`, `push_cast`, `norm_cast`
3. **Add new category `type_variables`** for single uppercase letters
4. **Add new category `namespaces`** for known Mathlib namespaces
5. **Extend local hypothesis patterns** to catch `h_*` and `h*.projection`
6. **Filter standalone projections** (`mp`, `mpr`, `ne` when alone)
7. **Better Unicode handling** to prevent corruption

---

## Post-Implementation Results (January 2026 - Second Pass)

After implementing the fixes above, here are the updated statistics:

### Global Summary (54,475 proofs, 165,263 unique tactic blocks after normalization)

| Category | Unique | Total Occurrences | % of Total |
|----------|--------|-------------------|------------|
| global_lemmas | 82,435 | 383,423 | 28.3% |
| local_hypotheses | 3,012 | 281,546 | 20.8% |
| local_var_access | 12,719 | 33,115 | 2.4% |
| keywords_modifiers | 159 | 371,187 | 27.4% |
| type_class_annotations | 35 | 3,895 | 0.3% |
| type_variables | 26 | 42,031 | 3.1% |
| namespaces | 54 | 45,651 | 3.4% |
| corrupted_unicode | 2 | 35,244 | 2.6% |
| other | 13,998 | 156,337 | 11.6% |
| **TOTAL** | **112,440** | **1,352,429** | 100% |

### Signal vs Noise

| Category | Unique | Total |
|----------|--------|-------|
| Global lemmas (signal) | 82,435 | 383,423 |
| Filtered items (noise) | 15,892 | 721,092 |
| Context items (types/namespaces) | 115 | 91,577 |
| Other (unclassified) | 13,998 | 156,337 |

**Signal/noise ratio: 0.53x**

### Improvements from First Pass

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Unique tactic blocks | 168,245 | 165,263 | -2,982 (whitespace normalization) |
| `filter_upwards` classified | global_lemmas | keywords_modifiers | ✓ Fixed |
| `split_ifs` classified | global_lemmas | keywords_modifiers | ✓ Fixed |
| Type variables (A, B, R, etc.) | other | type_variables | ✓ New category |
| Namespaces (ENNReal, etc.) | other | namespaces | ✓ New category |
| `h_eq`, `h_pos`, etc. | global_lemmas | local_hypotheses | ✓ Fixed |

### Top 10 Tactic Blocks (After Normalization)

1. `rfl` (1,581 occurrences, 2.90%)
2. `constructor` (1,550, 2.85%)
3. `simp` (1,438, 2.64%)
4. `ext` (1,175, 2.16%)
5. `· simp` (775, 1.42%)
6. `by simp` (643, 1.18%)
7. `classical` (571, 1.05%)
8. `ext x` (537, 0.99%)
9. `congr` (437, 0.80%)
10. `· rfl` (349, 0.64%)

### Top 20 Global Lemmas

1. `mul_comm` (1,669)
2. `mul_assoc` (1,424)
3. `mul_one` (1,203)
4. `add_comm` (1,107)
5. `comp_apply` (1,070)
6. `one_mul` (977)
7. `le_antisymm` (857)
8. `congr_arg` (752)
9. `le_trans` (717)
10. `zero_add` (699)

### Items Still in "Other" (Need Further Classification)

| Item | Count | Likely Category |
|------|-------|-----------------|
| `comp` | 1,876 | Could be lemma suffix or standalone |
| `map` | 1,832 | Could be lemma suffix or standalone |
| `Fin` | 1,375 | Should be namespace |
| `range` | 1,057 | Could be lemma or standalone |
| `Ne` | 882 | Should be type_class |
| `elim` | 875 | Could be lemma suffix |
| `succ` | 871 | Could be lemma or constructor |
| `univ` | 834 | Could be lemma or standalone |
| `_root_` | 829 | Should be filtered (Lean internal) |
| `card` | 782 | Could be lemma or standalone |

### Remaining Issues

1. **Corrupted Unicode still present** (35,244 occurrences of `â` and `ð`)
   - Root cause: UTF-8 encoding of `←`, `⟨`, `⟩` being corrupted
   - Need to fix at source (JSON loading) or earlier in pipeline

2. **"Other" category still large** (13,998 unique, 156,337 total)
   - Many are lemma suffixes appearing standalone (`comp`, `map`, `elim`)
   - Some are namespaces not yet in list (`Fin`, `Equiv`, `Classical`)
   - Some are type classes (`Ne`, `MeasurableSet`, `Tendsto`)

3. **Standalone words that could be either lemmas or non-lemmas**
   - `range`, `univ`, `card`, `id`, `injective`, `mul`
   - Context-dependent classification needed

---

## Corpus Matching Analysis (January 2026)

### Matching Strategy

Since extracted lemmas are often **unqualified** (e.g., `add_comm`) while corpus contains **fully qualified names** (e.g., `Nat.add_comm`, `Int.add_comm`), we use two-phase matching:

1. **Exact match**: `lemma == corpus_name`
2. **Suffix match**: `corpus_name` ends with `.lemma`

### Matching Results

| Match Type | Occurrences | % of Total | Unique | % of Total |
|------------|-------------|------------|--------|------------|
| Exact | 139,689 | 36.4% | 24,628 | 29.9% |
| Suffix | 189,752 | 49.5% | 39,592 | 48.0% |
| **Total Matched** | **329,441** | **85.9%** | **64,220** | **77.9%** |
| No Match | 53,982 | 14.1% | 18,215 | 22.1% |

### Top Exact Matches (Already Qualified)

| Lemma | Count |
|-------|-------|
| `mul_comm` | 1,669 |
| `mul_assoc` | 1,424 |
| `mul_one` | 1,203 |
| `one_mul` | 977 |
| `le_antisymm` | 857 |
| `Function.comp_apply` | 587 |

### Top Suffix Matches (Unqualified → Multiple Namespaces)

| Lemma | Count | # Variants | Example Variants |
|-------|-------|------------|------------------|
| `add_comm` | 1,107 | 6 | `Nat.add_comm`, `Int.add_comm`, `BitVec.add_comm` |
| `comp_apply` | 1,070 | 74 | `Function.comp_apply`, `ContinuousOrderHom.comp_apply` |
| `congr_arg` | 752 | 26 | `ContinuousMap.Homotopy.congr_arg`, `Dilation.congr_arg` |
| `ext_iff` | 598 | 150 | `String.ext_iff`, `Fin.ext_iff`, many more |
| `coe_mk` | 486 | 111 | `ContinuousLinearMap.coe_mk`, many more |

**Insight:** Common lemma names appear in many namespaces. `ext_iff` alone has 150 variants!

### No-Match Analysis (18,215 unique items)

#### Category 1: Constructors (Not Lemmas)
| Item | Count | Analysis |
|------|-------|----------|
| `Or.inr` | 544 | Constructor of `Or` type |
| `Or.inl` | 542 | Constructor of `Or` type |

**Fix:** Add constructors like `Or.inl`, `Or.inr`, `Sum.inl`, `Sum.inr` to a `constructors` category.

#### Category 2: Tactics That Slipped Through
| Item | Count | Should Be |
|------|-------|-----------|
| `conv_rhs` | 331 | `keywords_modifiers` (tactic) |
| `conv_lhs` | 276 | `keywords_modifiers` (tactic) |
| `nth_rw` | 198 | `keywords_modifiers` (tactic) |
| `apply_fun` | 173 | `keywords_modifiers` (tactic) |
| `aesop_cat` | 153 | `keywords_modifiers` (tactic) |
| `mfld_simps` | 148 | `keywords_modifiers` (simp set) |
| `slice_lhs` | 141 | `keywords_modifiers` (tactic) |

**Fix:** Add these to `_KEYWORDS_MODIFIERS`.

#### Category 3: Wrong Namespace (Might Be Valid)
| Item | Count | Analysis |
|------|-------|----------|
| `Category.assoc` | 488 | Should be `CategoryTheory.Category.assoc` |
| `Category.comp_id` | 172 | Should be `CategoryTheory.Category.comp_id` |
| `Category.id_comp` | 153 | Should be `CategoryTheory.Category.id_comp` |
| `Functor.map_comp` | 148 | Should be `CategoryTheory.Functor.map_comp` |
| `Pi.zero_apply` | 182 | Not in corpus (missing?) |
| `Pi.smul_apply` | 155 | Not in corpus (missing?) |

**Insight:** Category theory lemmas need `CategoryTheory.` prefix. `Pi.*` lemmas might be in a different module.

#### Category 4: Standalone Suffixes
| Item | Count | Analysis |
|------|-------|----------|
| `trans_lt` | 465 | Likely `lt_trans` or `Nat.trans_lt`? |
| `symm.trans` | 145 | Projection chain, filter as `local_var_access` |
| `eq_or_lt` | 143 | Might be `lt_or_eq` or `Nat.eq_or_lt` |

#### Category 5: Missed Local Hypotheses
| Item | Count |
|------|-------|
| `h_1` | 44 |
| `h_2` | 29 |
| `h_measM_f` | 11 |
| `h_C` | 10 |
| `h_Union` | 10 |

**Fix:** Extend `_LOCAL_HYPOTHESIS_PATTERNS` to catch `h_[A-Z]`, `h_[0-9]+` patterns.

### Recommendations

1. **Add missing tactics** to filter:
   ```python
   ADDITIONAL_TACTICS = {
       "conv_rhs", "conv_lhs", "nth_rw", "apply_fun", "aesop_cat",
       "mfld_simps", "slice_lhs", "slice_rhs", "field_simp", "ring_nf"
   }
   ```

2. **Add constructors category**:
   ```python
   CONSTRUCTORS = {"Or.inl", "Or.inr", "Sum.inl", "Sum.inr", "And.intro"}
   ```

3. **Extend local hypothesis patterns**:
   ```python
   # Add: h_[A-Z], h_[0-9]+, h_[a-z]+[A-Z]
   r"^h_[A-Z].*$",
   r"^h_\d+$",
   ```

4. **Consider namespace resolution**: For unqualified lemmas, the suffix match gives us possible namespaces. Could use context (imports, open namespaces) to resolve.

### File Outputs

- `lemma_candidate_counter.json`: 64,220 matched lemmas (exact + suffix)
- `lemma_candidate_counter_filtered_out.json`: 18,215 unmatched items
- `lemma_suffix_matches.json`: Details of which qualified names match each unqualified lemma
