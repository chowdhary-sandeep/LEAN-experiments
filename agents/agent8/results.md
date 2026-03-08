# Agent 8 — Random Held-Out Test Set Evaluation

## Summary

The expected pass rate on a random held-out set of 500 theorems is approximately **63.3%**, compared to **73.4%** on the sequential first-500 theorems. This is a gap of roughly **10 percentage points**, indicating meaningful overfitting to the sequential slice.

---

## Pass Rates: 3 Random Runs

| Run | Theorems | PASS | FAIL | Pass Rate |
|-----|----------|------|------|-----------|
| Random Run 1 | 500 | 309 | 191 | 61.8% |
| Random Run 2 | 500 | 323 | 177 | 64.6% |
| Random Run 3 | 500 | 318 | 182 | 63.6% |
| **Average** | 500 | **317** | **183** | **63.3%** |

All runs used `--random` flag (Python `random.shuffle` seeded by time, ensuring different theorem selections each run). 0 theorems were skipped — all 500 had buildable proof commands.

---

## Comparison with Sequential (First 500) Baseline

The sequential baseline result comes from multiple other agents (agent4, agent5, agent6, agent7 run1, agent9 run1) which all produced identical results, confirming they ran on the first 500 theorems in deterministic order.

| Metric | Sequential (first 500) | Random (3-run avg) | Delta |
|--------|------------------------|-------------------|-------|
| Pass rate | 73.4% (367/500) | 63.3% (317/500) | -10.1 pp |
| Total failures | 133 | 183 avg | +50 more |

The 10 percentage point gap is statistically meaningful given the sample size (3 × 500 theorems). The random sets are consistently harder, not just noisier — all three random runs fell in the 61–65% range with low variance (±1.4 pp from the mean).

---

## Top 3 Error Categories on Random Sets

Averaged across the 3 random runs, with comparison to the sequential baseline:

| Category | Random Avg | Random % of Fails | Sequential | Sequential % of Fails | Change |
|----------|-----------|-------------------|------------|----------------------|--------|
| **expected_token** | 70.3 | 38% | 47 | 35% | +23 absolute, similar proportion |
| **other** | 61.0 | 33% | 40 | 30% | +21 absolute, similar proportion |
| **function_expected** | 18.3 | 10% | 3 | 2% | **+15 absolute, 5x proportional increase** |
| unknown_identifier | 25.7 | 14% | 25 | 19% | flat absolute, lower proportion |
| failed_to_synthesize | 3.7 | 2% | 10 | 8% | **-6 absolute, 3x lower in random** |
| type_mismatch | 4.3 | 2% | 8 | 6% | lower in random |

### Category 1: `expected_token` (38% of random failures)

The single largest failure category. These are parse/syntax errors in the generated Lean command wrapper — the proof body Lean can't even parse. Raw count increases from 47 (sequential) to 70 average (random), but the proportion stays roughly constant (~35–38%), suggesting this is a uniform background rate across all theorem types, not specific to the random set.

Sub-patterns within this category are diverse: multi-line `expected token` cascades suggest a single syntactic trigger causes multiple reported errors per theorem.

### Category 2: `other` (33% of random failures)

The "other" bucket contains errors not matched by the six named patterns. Drilling into the raw error messages from random Run 1, the top sub-categories are:

- **unknown namespace** errors: 27 occurrences total, e.g. `unknown namespace 'Category'` (7×), `'Structure'` (4×), `'AEEqFun'` (3×), `'Parser.Term'` (3×). These are namespace opens from the source file scanner that do not resolve when opened bare in a proof context.
- **invalid binder annotation** (7 occurrences): type is not a class instance — variable inference from `state_before` incorrectly wraps a non-typeclass type in `[...]`.
- **quotation precheck** errors (12+ occurrences): identifiers like `op`, `R`, `p`, `k` are free variables in `conv` or `simp` patterns but are not declared in scope. Sequential baseline had 14 occurrences all for a single identifier (`D.toGlueData`), while random set shows the problem is more general.
- **ambiguous, possible interpretations** (6 occurrences): notation or identifiers that resolve to multiple definitions without the right `open` context.
- **cannot coerce to sort** (4 occurrences): absent from sequential entirely.

### Category 3: `function_expected` (10% of random failures — 5x higher than sequential)

This is the sharpest proportional increase from sequential to random. Sequential: 3 occurrences (2% of fails). Random: 15–24 per run, averaging 18.3 (10% of fails). These arise when a term that should be a function or type is instead a value, typically from:
- Namespace wrapping or coercion errors that turn a category/functor into a non-function term.
- Incorrect variable declarations from `state_before` where a type variable gets a wrong binder kind.
- `CategoryTheory` theorems in particular — CategoryTheory was the single largest failing namespace in random Run 1 (20 failures), vs. almost absent from the sequential failures.

---

## Patterns Unique to Random / Harder Theorems

### 1. CategoryTheory theorems are disproportionately hard

In random Run 1, `CategoryTheory.*` accounted for 20 of 191 failures (10.5%). The sequential baseline was dominated by `AlgebraicGeometry.*` (75 of 133, or 56%), a specific cluster of theorems whose failures are concentrated in one area. The random set distributes failures across many more namespaces, revealing the `CategoryTheory` cluster as a second major weak point: the `function_expected` and `unknown namespace 'Category'` errors both trace back here.

### 2. `function_expected` explosion in CategoryTheory context

The 5x increase in `function_expected` errors for random sets corresponds to CategoryTheory theorems that use dot-notation heavily and whose namespaces (`Category`, `Limits`, `MonoidalCategory`, `Structure`, `WidePullback`) are not being correctly opened. The source file open-scanner correctly identifies these opens, but some nested namespace names (bare `Category`, `Structure`, `Limits`) are sub-namespaces that need to be opened relative to their parent, not at top-level.

### 3. Quotation precheck errors generalize beyond the sequential cluster

Sequential baseline had 14 quotation precheck errors, all for `D.toGlueData` — a single problematic identifier from `AlgebraicGeometry` theorems concentrated in the first 500. Random runs hit the same class of error but for diverse identifiers (`op`, `R`, `p`, `k`, `cs.simple`, `z`). This means the fix applied for `D.toGlueData` was specific to that case and has not generalized.

### 4. `cannot coerce to sort` — absent in sequential, present in random

4 occurrences per random run on average, 0 in sequential. These suggest edge cases where a type universe variable is being coerced to a sort in a way that the sequential first-500 theorems did not exercise. Likely involves `Type*`/`Sort*` normalization interacting with unusual typeclass hierarchies.

### 5. Sequential baseline is skewed by an AlgebraicGeometry cluster

73.4% sequential pass rate is somewhat misleading: 75 of 133 failures (56%) are from `AlgebraicGeometry.*` theorems. This cluster has a specific known failure mode (`D.toGlueData` quotation precheck + `StructureSheaf` namespace). Fixing this one cluster would push sequential rate to ~88%. The random rate of ~63% is a more realistic estimate of general corpus performance.

---

## Conclusion

**Expected generalization pass rate: ~63% on random held-out theorems.**

The 10 pp gap between sequential (73.4%) and random (~63.3%) is real, not noise. Sequential performance is inflated by the lack of CategoryTheory theorems in the first 500 and by the fact that `AlgebraicGeometry` failures, though large in count, represent a single fixable cluster.

To improve the random pass rate, the three highest-leverage areas are:
1. Fix `function_expected` errors in CategoryTheory context — likely namespace opening for bare sub-namespaces (`Category`, `Limits`, `Structure`, `MonoidalCategory`).
2. Generalize the quotation precheck fix beyond `D.toGlueData` to arbitrary free variables.
3. Reduce `unknown namespace` errors in the `other` category — 27 occurrences across run 1 alone, from namespaces that exist but cannot be opened at top-level.
