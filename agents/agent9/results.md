# Agent9 Variable Extraction Improvement — Results

## Summary

Over 5 iterations, `_extract_variables` in `verifier/test_corpus.py` was improved to handle
tricky cases in `state_before` parsing. Pass rate on 500 theorems increased from **73.4% → 76.4%**
(+15 net, +17 gained, -2 lost).

---

## Run Results

| Run | Pass | Fail | Pass % | Delta |
|-----|------|------|--------|-------|
| 1 (baseline) | 367 | 133 | 73.4% | — |
| 2 (iter 2) | 370 | 130 | 74.0% | +3 |
| 3 (iter 3) | 376 | 124 | 75.2% | +6 |
| 4 (iter 4 — regression) | 373 | 127 | 74.6% | -3 |
| 5 (iter 5 — fixed) | 382 | 118 | 76.4% | +9 |

### Failure Breakdown (Baseline vs Final)

| Category | Run 1 | Run 5 |
|---|---|---|
| expected_token | 47 | 44 |
| other | 40 | 28 |
| unknown_identifier | 25 | 25 |
| failed_to_synthesize | 10 | 10 |
| type_mismatch | 8 | 8 |
| function_expected | 3 | 3 |

---

## Changes Made (per iteration)

### Iteration 2: Skip `∀`-quantified inst lines and h* Prop hypotheses

**Problem 1**: `inst✝ : ∀ (i : 𝒰.J), HasPullback (𝒰.map i ≫ f) g` was being emitted as
`variable [∀ ...]`, which is invalid Lean 4 syntax (typeclass instances cannot be universally
quantified in `variable` declarations). This caused `expected_token` errors for ~31 entries
in the `AlgebraicGeometry.Scheme.Pullback.*` and `DirectLimit` families.

**Fix**: Added early `continue` when `type_str.startswith("∀")` for `inst` lines.

**Problem 2**: Lines like `hf : BddAbove (range f)`, `ha : a ≠ 0`, `hX : IrreducibleSpace X`
were being emitted as `variable (hf : BddAbove (range f))` etc. These are local Prop-valued
hypotheses, not data variables.

**Fix**: Added skip for lines where ALL names match `h[a-zA-Z0-9_]*` or `this` AND the type
does not contain `Type` or `Sort`.

**Problem 3**: `∀`-quantified regular hypotheses like `heq : ∀ (n : Fin E.order), u ↑n = init n`
were not caught by the existing `↔/∧/∨/¬` filter.

**Fix**: Added `if type_str.startswith("∀"): continue` for non-inst lines too.

**Problem 4**: Lines like `G : ι → Type w` (function-to-Type) had `→` in the type string so
the `Type/Sort` normalization branch was skipped (it required `"→" not in type_str`). This caused
`variable (G : ι → Type w)` with an unresolved universe name `w`.

**Fix**: Removed the `"→" not in type_str` guard from the `Type/Sort` branch so both pure types
(`R : Type u_1`) and function-to-types (`G : ι → Type w`) get normalized to `Type*`. Both are
now emitted as `variable {Name : normalized_type}`.

**Result**: +3 pass (373 → 370... wait: 367 → 370). Net 3 gains.

---

### Iteration 3: Skip lines with ✝ in type_str; skip inst refs to explicit_params-only vars

**Problem 1**: Lines like `a✝ b c : ℍ[R,c₁✝,c₂✝]` — `a✝` is an inaccessible shadow but
`b` and `c` are valid. The current code emitted `variable (b : ℍ[R,c₁✝,c₂✝])` where
`c₁✝` is an invalid Lean identifier. This caused failures for `QuaternionAlgebra.*` entries.

**Fix**: Added `if "✝" in type_str: continue` for non-inst lines. Any line where the TYPE
references an inaccessible variable is invalid in our context.

**Problem 2**: `inst✝ : NontriviallyNormedField 𝕜` where `𝕜` appears in the theorem's
explicit params `{𝕜 : Type*}` but NOT as a section-level `variable {𝕜 : Type*}` (because
the explicit_params check prevents emitting 𝕜 as a Type variable). This caused 26 entries
(e.g., `MellinConvergent.const_smul`, `SSet.Quasicategory.hornFilling`) to emit inst lines
referencing an unbound identifier.

**Fix**: Added a first-pass scan to collect `declared_type_vars` (names declared as
`variable {X : Type*}` in our section). Then, before emitting an inst line, extract the
free identifiers in the type and skip if any appear in `explicit_params - declared_type_vars`.

**Result**: +6 pass (370 → 376).

---

### Iteration 4: Multi-name explicit_params extraction (regression)

**Attempted Fix**: The original `explicit_params` regex `r"[({[]\s*([^\W\d]\w*'*)\s*:"` only
captures the **first** name in multi-name binders like `{X Y : Scheme}` or `(i j : ι)`.
Replaced with a full binder parser that captures all names.

**Regression cause**: The new regex `r"[({[](.*?)[)}\]]"` with DOTALL matches binder-like syntax
in the RETURN TYPE and PROOF BODY too. For example, `theorem foo (f : X → A) : (lift R f : Type)`
extracted `lift`, `R` as explicit params from the `: (lift R f : Type)` part of the return type.
This caused `R` to be placed in `explicit_params`, preventing `variable {R : Type*}` from being
emitted and causing inst lines that reference `R` to be incorrectly skipped.

**Result**: -3 (76 → 373), a regression.

---

### Iteration 5: Fixed multi-name extraction (correct binder parsing)

**Fix**: Rewrote explicit_params extraction to:
1. Strip `@[attr]` blocks (which may contain `:` and pollute extraction).
2. Find the `theorem/lemma/def/abbrev name` token.
3. Track bracket depth from there to find the first `:` at depth 0 that is the return-type
   separator (not `:=`).
4. Extract binder names only from the **parameter string** (before that `:` separator).

This correctly handles:
- `{X Y : Scheme}` → `{X, Y}`
- `(i j : 𝒰.J)` → `{i, j}`
- `theorem foo (f : X) : (lift R : Type)` → only `{f}`, not `lift` or `R`
- `@[reassoc (attr := simp)] lemma foo (e : V)` → `{e}`, not `reassoc`

**Also fixed**: The `inst` line check for free vs bound variables. For types like
`(i : ι) → AddCommGroup (G i)`, the `i` appears as a BOUND variable in the type expression.
The check `type_ids & (explicit_params - declared_type_vars)` was incorrectly treating bound `i`
as a free reference to the theorem's explicit `i` parameter. Fixed by stripping `(binder : T) →`
and `∀ binders,` patterns before extracting identifiers.

**Result**: +9 pass (373 → 382). 76.4% total.

---

## Entries Fixed (Baseline → Final)

Notable entries that went from FAIL to PASS:

- `AlgebraicGeometry.genericPoint_eq_of_isOpenImmersion` — was emitting `variable [IrreducibleSpace ↑↑Y.toPresheafedSpace]` where Y was in explicit_params. Fixed by iter5 explicit_params improvement.
- `AlgebraicGeometry.genericPoint_eq_bot_of_affine` — same family.
- `AlgebraicGeometry.IsAffineOpen.primeIdealOf_genericPoint` — same family.
- `SSet.Quasicategory.hornFilling` — was emitting `variable [S.Quasicategory]` where S is explicit param. Fixed by iter3 inst-refs-explicit_params check.
- `AlgebraicGeometry.Scheme.app_eq`, `presheaf_map_eqToHom_op`, `inv_app`, `Spec.map_inv` — fixed by explicit_params multi-name extraction.
- `SetLike.coe_list_dProd` — fixed by iter3 inaccessible type_str check.
- `AlgebraicGeometry.isReduced_of_isReduced_stalk` — fixed by iter2 ∀ inst skip.
- `AlgebraicGeometry.isReduced_of_isOpenImmersion`, `isIntegral_of_isOpenImmersion` — fixed by explicit_params fix.
- `AlgebraicGeometry.basicOpen_eq_bot_iff` — fixed.
- `QuaternionAlgebra.smul_coe`, `star_eq_self`, `star_eq_neg` — fixed by ✝-in-type_str skip.
- `Quaternion.normSq_coe` — fixed.

## Remaining Issues (not fixed)

1. **expected_token (44)**: The `AlgebraicGeometry.Scheme.Pullback.*` entries (~30) still fail.
   Analysis shows the `variable [∀ ...]` is now correctly skipped, but the `expected_token`
   errors come from proof tactics (e.g., `simp [pullbackSymmetry_hom_comp_fst_assoc, ...]`)
   where the lemma names no longer exist or have been renamed in the current Mathlib version.
   This is a corpus staleness issue, not a variable extraction issue.

2. **unknown_identifier (25)**: `AlgebraicGeometry.Scheme.GlueData.*` entries fail with
   `unknown identifier 'D.toGlueData' at quotation precheck`. Local notation
   `local notation "𝖣" => D.toGlueData` fails at quotation precheck in our context.
   Fix would require `set_option quotPrecheck false` before such notations.

3. **type_mismatch (8)**: The `Algebraic.cardinal_mk_*` entries have universe-level mismatches.
   The statement uses explicit universe levels `{u}` and `{v}` in `Cardinal.lift.{u}`, but our
   generated `variable {R : Type*}` uses anonymous universe levels that don't match.

4. **other (28)**: Mix of pre-existing issues: namespace resolution failures
   (`unknown namespace 'StructureSheaf'`, `'NormalizedMooreComplex'`), ambiguous names
   (`GradedMonoid` has two interpretations), invalid field notation for `X.Hom Y` style types,
   and a few proof-level failures (unsolved goals, tactic timeouts).

---

## Code Changes Location

All changes are in `_extract_variables` function in
`E:\LeanATP Harness\agents\agent9\verifier\test_corpus.py` (lines ~405–590).

Key diffs:
- Iter 2: inst `∀` type skip; h* Prop-hypothesis skip; `∀`-quantified hypothesis skip;
  `→ Type` normalization fix (lines ~513–516, ~543–548, ~578–580, ~592–609).
- Iter 3: `✝` in `type_str` skip; inst refs explicit_params check with `declared_type_vars`
  pre-pass (lines ~430–484, ~537–541, ~517–527).
- Iter 5: `explicit_params` extraction rewrite with proper binder parsing and `@[attr]`
  stripping; free-vs-bound identifier fix for inst check (lines ~430–461, ~523–527).
