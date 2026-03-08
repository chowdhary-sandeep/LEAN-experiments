# Agent4 Lean Proof Verification — Results Report

## Summary

Starting from a baseline of **73.4%** (367/500), we improved to **77.8%** (389/500) over 5 iterations — a net gain of **22 theorems** with **0 regressions**.

---

## Pass Rate by Iteration

| Iteration | Pass Count | Pass Rate | Net Change | Key Change |
|-----------|-----------|-----------|------------|------------|
| Run 1 (baseline) | 367/500 | 73.4% | — | Baseline |
| Run 2 (attempted source vars) | 251/500 | 50.2% | −116 | Switched to source file vars — REVERTED (caused mass regressions) |
| Run 3 | 368/500 | 73.6% | +1 | Dot-projection filter + `∀` stripping + `set_option quotPrecheck false` |
| Run 4 | 370/500 | 74.0% | +3 total | Multi-name binder fix + namespace open fix |
| Run 5 | **389/500** | **77.8%** | **+22 total** | `Type u_N → Type*` normalization in regular vars |

---

## What Types Were Causing `invalid binder annotation`

The `invalid binder annotation, type is not a class instance` error occurred when `_extract_variables` emitted `variable [type_str]` for typeclass instance lines where `type_str` was NOT a valid typeclass.

### Identified invalid type patterns:

**1. Dot-projection on variable (lowercase or short uppercase prefix):**
- `μ.IsAddLeftInvariant` — projection of measure variable, not a class
- `S.Quasicategory` — projection on a simplicial set variable `S`
- `X.HasMap`, `Y.HasMap`, `F.IsEquivalence`, `Gr.Full` — similar patterns

**2. Pi-type / quantified constraints (actually valid in Lean 4):**
- `(i : ι) → CommRing (G i)` — these ARE valid as `[∀ i, CommRing (G i)]` style
- We originally filtered these, causing regressions. They were preserved.

**3. Forall with dot-projected binder type:**
- `∀ (i : 𝒰.J), HasPullback (𝒰.map i ≫ f) g` — `𝒰.J` as explicit type annotation caused `expected token`
- Fix: strip the type annotation → `∀ i, HasPullback (𝒰.map i ≫ f) g`

### Why `GradedMonoid` entries failed with invalid binder annotation:

The `GMonoid A` class is in `GradedMonoid` namespace. The variable `A` was emitted as `variable (A : ι → Type u_3)` where `u_3` is an auto-generated universe level not in scope. This caused a metavariable `?m.51` that made `GMonoid A` fail to resolve as a class.

Fix: normalize `Type u_N` (auto-generated levels) to `Type*` in regular variable type strings.

---

## The Fix Code

### Fix 1: Dot-projection filter in `_extract_variables` (Run 3)

Added filtering in the inst✝ typeclass handling:

```python
tc_root = tc_type.split()[0] if tc_type.split() else ""
# Skip dot-projection methods on variables (not genuine typeclasses)
if "." in tc_root:
    prefix = tc_root.split(".")[0]
    if len(prefix) <= 2 or prefix[0].islower():
        continue
    if re.match(r'^[A-Z][a-z]?\.[A-Z]', tc_root):
        continue
# Forall with dot-projected binder type → strip type annotation
if tc_root.startswith("∀") or tc_root == "forall":
    if re.search(r'\(\w+\s*:\s*[\w𝒰]+\.\w+\)', tc_type):
        tc_type = re.sub(r'\((\w+)\s*:\s*[\w𝒰]+\.\w+\)', r'\1', tc_type)
```

### Fix 2: Multi-name binder extraction (Run 4)

Fixed `explicit_params` to capture ALL names in multi-name binders like `(i j k : T)`:

```python
explicit_params: set[str] = set()
for binder_match in re.finditer(r'[({⦃\[]\s*((?:[^\W\d]\w*\'*\s*)+):', statement):
    names_part = binder_match.group(1).strip()
    for name in names_part.split():
        if re.match(r"^[^\W\d]\w*'*$", name, re.UNICODE):
            explicit_params.add(name)
```

**Why this matters:** The old regex only captured the first name in `(i j : 𝒰.J)`. Both `i` and `j` were being emitted as `variable (i : 𝒰.J)` and `variable (j : 𝒰.J)` even though they were explicit params. This caused `expected token` errors.

### Fix 3: Namespace opening (Run 4)

Added automatic opening of the theorem's own namespace components:

```python
full_name = entry.get("full_name", "")
if full_name and "." in full_name:
    ns = full_name.rsplit(".", 1)[0]
    parts = ns.split(".")
    for part in parts:
        if part and part not in _META_OPENS_SKIP and re.match(r'^[A-Z]', part):
            _add(f"open {part}")
```

This fixed `AlgebraicGeometry.Scheme.app_eq` and similar entries where the source's `open AlgebraicGeometry` was needed but not extracted from the source file opens.

### Fix 4: `quotPrecheck false` option (Run 3)

Added `set_option quotPrecheck false` to suppress quotation precheck errors for dot-notation identifiers like `D.toGlueData` in proof bodies. Changed error types for some entries but didn't reduce total failures significantly.

### Fix 5: `Type u_N → Type*` normalization in regular variables (Run 5) — The Big Win

The biggest improvement came from normalizing auto-generated universe levels in ALL variable type strings:

```python
# In the "Regular variables" branch of _extract_variables:
type_str_norm = re.sub(r'\bType\s+u_\d+', 'Type*', type_str)
type_str_norm = re.sub(r'\bSort\s+u_\d+', 'Sort*', type_str_norm)
```

**Why this was critical:** For variables like `A : ι → Type u_3`, the type contains `→` so the code skipped the "Type universe" normalization branch and fell through to "Regular variables". The `u_3` was emitted verbatim as `variable (A : ι → Type u_3)`. Since `u_3` is an auto-generated Lean universe level (not a declared named universe), this caused downstream typeclass synthesis failures with metavariable errors like `?m.51`.

This single fix added 19 new passes.

---

## 3 Best Findings

### Finding 1: Auto-generated universe levels in function-type variables

**Pattern:** `A : ι → Type u_3` in state_before
**Problem:** The `u_3` is not a named universe level but Lean's display of an auto-generated universe. When emitted as `variable (A : ι → Type u_3)`, Lean treats `u_3` as an undeclared name, causing metavariable `?m.N` that propagates to make typeclass instances unresolvable.
**Impact:** ~19 theorems in 500 (primarily GradedMonoid, AlgebraicGeometry, ENNReal entries)
**Fix:** `re.sub(r'\bType\s+u_\d+', 'Type*', type_str)` in the regular variables branch

### Finding 2: Multi-name binders in theorem signatures

**Pattern:** `theorem foo (i j : 𝒰.J) : ...`
**Problem:** The explicit params regex `r"[({[]\s*([^\W\d]\w*'*)\s*:"` only captured the first name `i` from `(i j : 𝒰.J)`. Both `i` and `j` were emitted as separate `variable (i : 𝒰.J)` and `variable (j : 𝒰.J)` even though they're explicit theorem parameters. The `𝒰.J` as a standalone type in a variable declaration outside the namespace context caused parse errors.
**Impact:** Affected all 19+ AlgebraicGeometry.Scheme.Pullback entries
**Fix:** Changed to `re.finditer(r'[({⦃\[]\s*((?:[^\W\d]\w*\'*\s*)+):', statement)` to extract ALL names

### Finding 3: Source file variable switching causes massive regressions

**Attempted:** Replacing `_extract_variables` (state_before derived) with `_get_source_variables` (actual .lean source)
**Problem:** Source files have `variable` declarations spanning entire files with multiple sections. `_normalize_and_dedup_vars` deduplicates by first-seen name across sections. For theorems in later sections, the wrong (earlier section's) variable type gets selected — e.g., Quaternion theorems got `ℍ[R,c₁,c₂]` variables when they needed `ℍ[R]`.
**Impact:** Catastrophic — went from 73.4% to 50.2%
**Lesson:** State_before is more accurate for individual theorems than file-level variables. Source variables are useful only for specific constructs like `∀ i, HasPullback...` that don't appear cleanly in state_before.

---

## Remaining Failures (111/500)

| Error Type | Count | Notes |
|-----------|-------|-------|
| `expected token` | 44 | Pullback entries — `t 𝒰 f g i j` and related functions fail to typecheck |
| `unexpected token '  '` | 11 | OpenCover entries — `local notation "D_" =>` long line parsing issue |
| `failed to synthesize` | 7 | `NeZero 2`, scheme/ring typeclass inference failures |
| `unknown namespace 'StructureSheaf'` | 6 | API rename in newer Mathlib (hard fix) |
| `ambiguous` | 5 | `GradedMonoid` vs `SetLike.GradedMonoid` ambiguity after `open GradedMonoid` |
| `type mismatch` / `application type mismatch` | 9 | Deep proof/type issues |
| `function expected` | 3 | Term-mode proof construction failures |
| Other | ~16 | Various (`tactic 'rewrite' failed`, `unknown identifier`, etc.) |
