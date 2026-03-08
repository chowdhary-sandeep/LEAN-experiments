# Agent 3 — Lean 4 Proof Verification Harness Results

## Summary

| Iteration | Pass | Fail | Pass Rate | Notes |
|-----------|------|------|-----------|-------|
| Baseline  | 342  | 158  | 68.4%     | Starting point |
| Iter 1    | 343  | 157  | 68.6%     | `variable` normalization fixes |
| Iter 2    | 349  | 151  | 69.8%     | Inaccessible variable (✝) filtering |
| Iter 3    | 353  | 147  | 70.6%     | Hypothesis/∀-prop filtering; dependent typeclass fix (declared_vars) |
| Iter 4    | 354  | 146  | 70.8%     | Regression fix: ASCII-only boundary for undeclared type var detection |
| Iter 5    | 363  | 137  | **72.6%** | SMP character skip + `~ᵤ` Associated notation fix |

**Final result: 72.6% (363/500 PASS)**

---

## Changes Made (file: `verifier/test_corpus.py`)

### Iteration 1
- Normalize `Type u_N` → `Type*` in function-return-position types
  (e.g. `variable (A : ι → Type u_3)` → `variable (A : ι → Type*)`)

### Iteration 2
- Skip variable declarations where the type references inaccessible names (`✝`-suffixed)
  (e.g. `b : ℍ[R,c₁✝,c₂✝]` is now skipped)
- Skip typeclass instances whose type references inaccessible names
  (e.g. `[Semiring R✝]` is now skipped)
- Skip `∀`-quantified propositions (hypothesis lines like `Hg : ∀ (i j : ι) ...`)

### Iteration 3
- Track `declared_vars` to avoid emitting typeclass instances for undeclared type variables
  (e.g. `variable [NontriviallyNormedField 𝕜]` when `𝕜` is in `explicit_params` but not yet declared)
- Strip typed ∀ binders in typeclass instances:
  `∀ (i : T), HasPullback ...` → `∀ i, HasPullback ...`

### Iteration 4
- Fix regression: use ASCII-only word boundaries `(?<![A-Za-z0-9_])` when checking if a
  param appears in a typeclass type, to correctly handle unicode modifier chars like `ˣ`
  (e.g. `M` correctly found in `Mˣ` since `ˣ` is not in `[A-Za-z0-9_]`)

### Iteration 5
- **SMP character skip**: Skip any variable declaration (name or type) that contains
  Supplementary Multilingual Plane characters (codepoint > U+FFFF, e.g. `𝒰` U+1D4B0,
  `𝕜` U+1D55C). Python's `json.dumps` encodes these as UTF-16 surrogate pairs which
  Lean 4's REPL lexer cannot parse → `expected token` errors.

- **`~ᵤ` notation fix**: Add `local infixl:50 " ~ᵤ " => Associated` before the theorem
  when the statement or proof uses `~ᵤ` (the Associated relation notation). In Mathlib,
  this is declared with `local infixl` in `Algebra/Associated.lean`, so it doesn't survive
  into our generated check commands without being re-declared.
  Fixed 9 entries: `Associated.mul_left`, `Associated.mul_right`, `Associated.pow_pow`,
  `associated_of_dvd_dvd`, `Associated.eq_zero_iff`, `Associated.of_mul_right`,
  `Associated.of_pow_associated_of_prime`, `associated_iff_eq`, `Associates.mk_quot_out`.

---

## Remaining Failures (137 total)

### expected_token: 53 (mostly unfixable)
- **49 entries** have SMP characters in their theorem statement or proof body
  (e.g. `𝒰` U+1D4B0 in AlgebraicGeometry Pullback/OpenCover theorems, `𝓝` in ENNReal/Real).
  These are **fundamentally unfixable** via the REPL: `json.dumps` corrupts these characters
  into broken UTF-16 surrogate pair escapes (`\uD835\uDCxx`) which Lean's lexer rejects.
  The 49 unfixable entries are primarily: AlgebraicGeometry.Scheme.Pullback (30 entries),
  AlgebraicGeometry.Scheme.OpenCover (11 entries), ENNReal/NNReal/Real schlomilch/condensed
  (5 entries), MellinConvergent (3 entries).
- **4 remaining** are in other categories awaiting investigation.

### other: 42
- AlgebraicGeometry.Scheme entries with "invalid field notation" errors (7 entries)
- AlgebraicGeometry.StructureSheaf entries with "unknown namespace" errors (5 entries)
- Ring.DirectLimit entries with "cannot coerce to function" (4 entries)
- GradedMonoid entries with "invalid binder annotation" (3 entries: typeclass declared inside
  theorem's namespace is not accessible in file-level variable declarations)
- SetLike entries with "ambiguous" errors (3 entries)
- QuaternionAlgebra entries with proof failures (3 entries)
- Various type mismatch and typeclass issues

### failed_to_synthesize: 13
- TrivSqZeroExt entries (5): `Group` instance not synthesized for TrivSqZeroExt
- AlgebraicGeometry.Scheme entries (2): complex scheme/presheaf typeclass issues
- Other: quadratic, FreeAlgebra, summable_schlomilch

### function_expected: 12
- TrivSqZeroExt entries: `snd_pow`, `snd_list_prod`, `inv_inl`, `inv_inr`
- Ring.DirectLimit / AddCommGroup.DirectLimit
- LinearEquiv, FreeAlgebra, hofer, List.periodic_prod

### unknown_identifier: 9
- RingQuot entries: `add`, `mul`, `neg`, `sub`, `pow`, `smul` — operand names not in scope
- Algebra.adjoin_range_eq_range_freeAlgebra_lift: `adjoin_range_ι`
- AlgebraicGeometry.Scheme entries: `X.toPresheafedSpace` field access

### type_mismatch: 8
- AlgebraicGeometry entries: `IsIntegral X` where `X : Scheme` causes universe mismatch
- LinearRecurrence, List.dProd_monoid: parameter type mismatches in variable declarations

---

## Key Technical Findings

### SMP Characters in Lean REPL (Root Cause of ~35% of failures)
The JSON protocol uses `json.dumps` with default `ensure_ascii=True`. For Unicode codepoints
above U+FFFF (Supplementary Multilingual Plane), Python generates UTF-16 surrogate pair escapes
like `\uD835\uDCB0` for `𝒰` (U+1D4B0). Lean 4's REPL JSON parser does NOT recombine these
surrogate pairs, causing `expected token` parse errors.

Affected character classes:
- Mathematical Script letters: `𝒰 𝒜 𝒞 𝒢 𝒮 𝒯 𝒳 𝒴` (U+1D49C–U+1D4B3)
- Mathematical Double-Struck letters: `𝕜 𝕝 𝕂 𝔸 𝔹 𝔖` (U+1D538–U+1D55D)
- Mathematical Bold Script: `𝓝 𝓕 𝓤 𝓘 𝓟` (U+1D4D5–U+1D4E4)

The only fix would be to patch `repl_client.py` to use `json.dumps(..., ensure_ascii=False)`,
but that file was out of scope for modification.

### Local Notation Scope
`local infixl` declarations in Mathlib source files do not survive into REPL check commands.
Affected notation: `~ᵤ => Associated`. Fix: re-declare locally in generated check commands
when the notation appears in the theorem text.

### Typeclass Accessibility in Namespace Scope
Typeclasses defined inside `namespace Foo` (e.g. `GMonoid` in `namespace GradedMonoid`) are not
accessible in file-level `variable [...]` declarations that appear before `namespace Foo`. This
affects GradedMonoid and similar entries.
