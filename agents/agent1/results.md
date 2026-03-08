# LeanATP Harness — Agent1 Results

## Pass Rate by Iteration

| Iteration | Pass Count | Total | Pass Rate | Change |
|-----------|-----------|-------|-----------|--------|
| Baseline (run 1) | 342 | 500 | 68.4% | — |
| Iteration 2 | 349 | 500 | 69.8% | +7 |
| Iteration 3 | 350 | 500 | 70.0% | +1 |
| Iteration 4 | 359 | 500 | 71.8% | +9 |
| Iteration 5 | 372 | 500 | 74.4% | +13 |

**Total improvement: +30 theorems (+6.0 percentage points)**

---

## Fixes Made

### Iteration 2: Universe normalization in typeclass inst lines + inaccessible arg filtering

**Problem 1 — `Category.{v, u} C` → `application type mismatch` (39 failures)**

The `_extract_variables` function emitted `variable [Category.{v, u} C]` from `inst✝ : Category.{v, u} C`. The `{v, u}` are unnamed universe levels that are not in scope, causing `application type mismatch`. Fixed by introducing `_normalize_type_universes()` that strips `.{...}` universe params from qualified names.

**Problem 2 — `variable [Semiring R✝]` → `expected token` (~20 failures)**

When an `inst✝` line references inaccessible variables (like `inst✝⁴ : Semiring R✝`), the name `R✝` is not a valid Lean identifier. The fix: introduced `_type_has_inaccessible_args()` that detects `✝`-suffixed names in typeclass type strings and skips those inst lines entirely.

**Problem 3 — `G : ι → Type w` not normalized**

The universe normalization only ran on lines where `"→" not in type_str`. Changed the condition so that `Type w` → `Type*` normalization also applies to function types like `ι → Type w`.

### Iteration 3: Multi-name binder detection in `explicit_params`

**Problem — Variables like `g` from `(f g : Type)` not recognized as explicit params**

The original regex `[({[]\s*(\w+)\s*:` only captured the FIRST name in a multi-name binder. Updated to capture ALL names from binder groups, preventing redundant `variable` declarations for names that are already explicit theorem params.

### Iteration 4: Named universe declarations + `~ᵤ` local notation

**Problem 1 — `Type uR` in statements → `expected token` (5 failures)**

Theorems like `RingQuot.Rel.neg` have `{R : Type uR}` in their statements. The `uR` is a named universe variable that must be declared with `universe uR`. Added detection of named universe vars in statements and emit `universe X Y ...` before the section.

**Problem 2 — `~ᵤ` Associated notation → `expected token` (9 failures)**

The `~ᵤ` operator is defined as `local infixl:50 " ~ᵤ " => Associated` in `Mathlib/Algebra/Associated.lean` — it's a LOCAL notation only available within that file. When our harness sends theorems using this notation, the `\u1d64` character (`ᵤ`) is encoded in JSON and Lean doesn't find the notation. Fixed by detecting `~ᵤ` in the theorem text and prepending `local infixl:50 " ~ᵤ " => Associated` to the generated command.

### Iteration 5: `open AlgebraicGeometry` for namespace-implied context

**Problem — `variable (X : Scheme)` fails with `invalid field notation`**

AlgebraicGeometry theorems defined inside `namespace AlgebraicGeometry` can use `Scheme`, `Opens`, `Hom`, etc. without qualification. Our generated code lacks this namespace context because the source files don't have `open AlgebraicGeometry` (they ARE the `AlgebraicGeometry` namespace).

Fixed by adding `open AlgebraicGeometry` to any theorem whose `full_name` starts with `AlgebraicGeometry` or whose `open_namespaces` includes an `AlgebraicGeometry.*` entry. This resolved 13 additional theorems (7 `invalid field notation` → PASS, plus several `failed_to_synthesize` that benefited from correct Scheme type resolution).

---

## Failure Breakdown at Iteration 5 (128 remaining)

| Category | Count | Notes |
|----------|-------|-------|
| expected_token | 55 | ~49 from astral Unicode (U+1D400+) in stmt/proof (unrecoverable with current REPL) |
| other | 32 | Mixed: ambiguous names (5), typeclass stuck (3), StructureSheaf namespace (3), etc. |
| unknown_identifier | 14 | Mostly local defs, sub/mul/neg in RingQuot proofs |
| function_expected | 12 | TrivSqZeroExt `tsze` local abbreviation, FreeAlgebra.liftAux |
| failed_to_synthesize | 11 | CommRing/Semiring for CommRingCat, NeZero 2 type annotation |
| type_mismatch | 4 | lift.{v, u_1} cardinal universe issues |

**Fundamentally unrecoverable (52):** Theorems with astral-plane Unicode characters (U+1D400–U+1D7FF like `𝒰`, `𝒜`, `𝓕`) in their statements. The REPL client uses `json.dumps` without `ensure_ascii=False`, encoding these as UTF-16 surrogate pairs (`\ud835\udcb0`) which Lean's parser cannot handle. These cannot be fixed in `test_corpus.py` since `repl_client.py` is not modifiable.

---

## 3 Best Findings

### Finding 1: `open AlgebraicGeometry` is required for any theorem in the AlgebraicGeometry namespace hierarchy

AlgebraicGeometry source files are themselves INSIDE `namespace AlgebraicGeometry`, so `Scheme`, `Hom`, `Opens`, etc. are directly accessible without a file-level `open` statement. The `_get_source_opens()` function correctly finds only EXPLICIT `open` declarations from source files, which means for AlgebraicGeometry theorems the namespace-implicit context was missing. Adding `open AlgebraicGeometry` when `full_name.startswith("AlgebraicGeometry")` fixed 13 theorems in one iteration (+3.6pp).

### Finding 2: Inaccessible binders (`R✝`, `M✝`) in typeclass inst type strings cause invalid Lean syntax

When LeanDojo traces a proof in a file where some variables are shadowed (e.g., the outer context has `R : Type uR` but the inner theorem uses a fresh `R`), the outer variables get `✝`-suffixed names like `R✝`, `M✝`. These appear as arguments in typeclass inst lines: `inst✝⁴ : Semiring R✝`. Emitting `variable [Semiring R✝]` is invalid because `R✝` is not a valid Lean 4 identifier. The fix required a dedicated `_type_has_inaccessible_args()` function to detect these and skip the entire inst line.

### Finding 3: Local file notations (`~ᵤ`) are serialized in proof states but aren't globally accessible

The `~ᵤ` operator (TILDE + LATIN SUBSCRIPT SMALL LETTER U, U+007E + U+1D64) is defined as `local infixl:50 " ~ᵤ " => Associated` in Mathlib's `Associated.lean`. When LeanDojo traces theorems in that file, the state_before and statements use `~ᵤ` naturally. But our harness sends these theorems to a fresh Lean session where `~ᵤ` is undefined. The fix is to detect `~ᵤ` in the theorem text and prepend the same `local infixl:50 " ~ᵤ " => Associated` declaration. This pattern generalizes: any local notation in the corpus can be re-declared in the generated command.

---

## Key Code Snippets

### Fix 1: Universe normalization + inaccessible arg detection

```python
def _normalize_type_universes(type_str: str) -> str:
    result = re.sub(r'(\b[A-Z]\w*)\.\{[^}]{1,60}\}', r'\1', type_str)
    result = re.sub(r'\bType\s+\([^)]{1,40}\)', 'Type*', result)
    result = re.sub(r'\bSort\s+\([^)]{1,40}\)', 'Sort*', result)
    result = re.sub(r'\bType\s+[a-z_]\w*\'*', 'Type*', result)
    result = re.sub(r'\bSort\s+[a-z_]\w*\'*', 'Sort*', result)
    return result

def _type_has_inaccessible_args(type_str: str) -> bool:
    for m in re.finditer(r'\b(\w+)✝', type_str):
        if not m.group(1).lower().startswith('inst'):
            return True
    return False
```

Applied in `_extract_variables`:
```python
if any(n.lower().startswith("inst") for n in names):
    if _type_has_inaccessible_args(type_str):
        continue   # Skip inst lines referencing R✝, M✝ etc.
    norm_type = _normalize_type_universes(type_str)
    variables.append(f"variable [{norm_type}]")
    continue
```

### Fix 2: `~ᵤ` local notation + named universe declarations

```python
# In build_check_command:
_named_univ = set(re.findall(r'\bType\s+([a-z][A-Za-z0-9]*)\b', statement))
_named_univ |= set(re.findall(r'\bSort\s+([a-z][A-Za-z0-9]*)\b', statement))
_named_univ = {u for u in _named_univ if not re.match(r'^u_\d+$', u)}

_text_full = statement + (proof_text or "")
_needs_assoc_notation = "~ᵤ" in _text_full

lines = ["noncomputable section"]
if _named_univ:
    lines.append(f"universe {' '.join(sorted(_named_univ))}")
if _needs_assoc_notation:
    lines.append('local infixl:50 " ~ᵤ " => Associated')
```

### Fix 3: `open AlgebraicGeometry` for namespace-implied context

```python
# In _open_stmts:
full_name = entry.get("full_name", "")
open_ns_list = entry.get("open_namespaces") or []
if (full_name.startswith("AlgebraicGeometry")
        or any("AlgebraicGeometry" in ns for ns in open_ns_list
               if not ns.startswith("Mathlib"))):
    _add("open AlgebraicGeometry")
```
