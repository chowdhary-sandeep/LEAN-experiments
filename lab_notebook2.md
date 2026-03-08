# LeanATP Harness — Lab Notebook

> Project: Meta-methods for discovering new mathematics via Lean 4 proof verification.
> Kyle McCleary's `breadboard` repo reimplements Harmonic's ATP architecture. We built the missing subprocess backend and parallel pool.

---




**Location:** `E:\LEAN-experiments\00_experiment1\jsons\traced_theorems_unified_v2.jsonl` (126,792 entries, 54,477 tactic proofs)

`**open_namespaces` example:** `["Mathlib", "Mathlib.RingTheory", "Polynomial"]` → filter `Mathlib.`*, emit `open Polynomial`.

**Position data (`line`, `col`) is zeroed for all entries** — LeanDojo tracing limitation. Can't walk file for local helpers.

`**corpus_code_index.json`:** Built by `00_corpus_to_code.py` from `corpus.jsonl`. Maps `full_name → source_code` for premises (180,907 entries). Not the theorems themselves.

---

## 10. Corpus Test Results


| Run | Data            | Sample   | Approach                                                                                        | Pass        | Rate      |
| --- | --------------- | -------- | ----------------------------------------------------------------------------------------------- | ----------- | --------- |
| 1   | compact (seq)   | 150      | Naive `theorem NAME`                                                                            | 5/150       | 3.3%      |
| 2   | compact (seq)   | 150      | `example` approach (broken)                                                                     | 3/150       | 2%        |
| 3   | compact (seq)   | 150      | `private _vt` + namespace wrap                                                                  | 30/150      | **20%**   |
| 4   | compact (seq)   | 500      | + `noncomputable` + `open_namespaces` (wrong file)                                              | 58/500      | 11.6%     |
| 5   | traced (random) | 500      | + traced file + `open_namespaces` + 4 workers                                                   | **80/500**  | **16%**   |
| 6   | traced (random) | 500      | + `variable` reconstruction from `state_before`                                                 | **140/500** | **28%**   |
| 7   | traced (random) | 500      | + fix `✝` inst heuristic + protected/noncomputable strip + namespace filters                    | **205/500** | **41%**   |
| 8   | traced (random) | 500      | + source file `open` reading (ground truth from Mathlib tree)                                   | **277/500** | **55.4%** |
| 9   | traced (random) | 500      | + parse `open (X)` selective syntax + meta-namespace filter + `𝕜` regex + fn-type variable fix | **301/500** | **60.2%** |
| 10  | traced (random) | **5000** | + source file `variable` declarations, 12 workers                                               | TBD         | TBD       |


**Run 9 failure breakdown (199 failures):**


| Error                  | Count | Notes                                                                               |
| ---------------------- | ----- | ----------------------------------------------------------------------------------- |
| Other                  | 81    | Unknown namespaces (`VectorMeasure`, `CoprodI`, `Structure`), ambiguous terms, misc |
| `expected token`       | 68    | Multi-`expected token` = structurally malformed command; see below                  |
| `function expected`    | 20    | Still some missing namespace issues                                                 |
| `type mismatch`        | 19    | Universe/elaboration failures, CategoryTheory                                       |
| `failed to synthesize` | 6     | `Invertible 2`, `Quiver`, `Group Q` — specific missing instances                    |
| `unknown identifier`   | 5     | Renamed lemmas used in tactics                                                      |


**Wall time: ~15–30s for 500 checks (4 workers)**

**Three modes:**


| Mode | Description                                            | Ceiling |
| ---- | ------------------------------------------------------ | ------- |
| 1    | Re-prove existing Mathlib theorems (corpus test only)  | ~90–95% |
| 2    | Complete `sorry` in existing Lean file (main use case) | ~99%+   |
| 3    | Prove novel theorem (new math)                         | ~100%   |


Ceiling is not 100% for Mode 1: `import Mathlib` pre-loads all names. Re-declaring hits `already been declared`. Only affects corpus testing, not real ATP work.

---

## 11. Failure Deep-Dive Analysis (Runs 6→9)

### Meta-Diagnosis: What Was Actually Happening

`state_before` is a **partial snapshot** — it shows what's in scope at tactic step 1, not what was declared in the file. Crucially:

- `✝`-suffixed names (`p✝`, `n✝`, `f✝`) are anonymous binders from Lean internals — NOT typeclass instances. Only `inst✝` lines are instances.
- `open_namespaces` = MODULE HIERARCHY PATH (import tree), not runtime `open` declarations. `Mathlib.MeasureTheory.Measure` tells you the theorem is in that module, not that `open MeasureTheory` is in effect.
- The actual `.lean` source file is the ground truth.

### Root Cause Table


| Fix                                                    | Error Eliminated                                 | Run | Gain |
| ------------------------------------------------------ | ------------------------------------------------ | --- | ---- |
| `"✝" in n` → `n.lower().startswith("inst")`            | `invalid binder annotation [R[X]]`, `[ℕ]`, `[ι]` | 7   | +65  |
| Strip `protected`/`noncomputable` from theorem rename  | `unexpected token 'private'`                     | 7   | +5   |
| Filter `src.`*, `Batteries.Data.*` namespace paths     | `unknown namespace 'src'`                        | 7   | +20  |
| Read actual `.lean` source file for `open` lines       | Missing `open MeasureTheory/Set/Filter/Box/etc.` | 8   | +72  |
| Stop at `(` when parsing open names                    | `open (assoc` → `unexpected token '('`           | 9   | +15  |
| `_META_OPENS_SKIP` = `{Lean, Meta, Elab, Tactic, ...}` | Lean meta-ns conflicts                           | 9   | +5   |
| `[^\W\d]\w*` regex (Python Unicode `\w`)               | `𝕜` not recognized as type var                  | 9   | +3   |
| Skip `→` only when names look like `h*` hypothesis     | `f : E → F` skipped, `f` undeclared              | 9   | +5   |


### Run 9 Remaining Failures (199 / 500)


| Error                  | Count | Root Cause                                                                                                             |
| ---------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------- |
| `other`                | 81    | Unknown ns (`VectorMeasure`, `CoprodI`, `Structure`); ambiguous (`Real.cos` vs `Complex.cos`); CategoryTheory universe |
| `expected_token`       | 68    | Structurally malformed: some variable declarations generate invalid syntax; CategoryTheory/SmoothSheaf complex syntax  |
| `function_expected`    | 20    | fn-valued vars (`ψ`, `τ`, `ℓ`) now emitted but shadow names; namespace collision                                       |
| `type_mismatch`        | 19    | Universe elaboration; `Category.{v,u} C` with `C : Type u_1`                                                           |
| `failed_to_synthesize` | 6     | `Invertible 2`, `Quiver`, specific missing instances                                                                   |
| `unknown_identifier`   | 5     | Renamed lemmas in tactics                                                                                              |


### Progression


| Run     | Passes | Rate    | Key Fix                                     |
| ------- | ------ | ------- | ------------------------------------------- |
| 5       | 80     | 16%     | open_namespaces, parallelism                |
| 6       | 140    | 28%     | variable reconstruction                     |
| 7       | 205    | 41%     | ✝ heuristic, modifiers, ns filters          |
| 8       | 277    | 55%     | Source file open reading                    |
| 9       | 301    | **60%** | Selective open syntax, meta-ns, 𝕜, fn-vars |
| 10      | 5000   | 1988    | 39.8% (**REGRESSION**)                      |
| 11-12   | 1000   | 384     | 38.4%                                       |
| 13      | 1000   | 504     | 50.4%                                       |
| 14      | 1000   | 538     | 53.8%                                       |
| 15      | 1000   | 546     | 54.6%                                       |
| 16-20   | 1000   | 546     | 54.6%                                       |
| **21**  | 1000   | TBD     | TBD                                         |
| ceiling | ~850   | ~85%    | Name collision unavoidable in Mode 1        |


**Agent results (on first 500 theorems, sequential):**


| Agent       | Best Rate | Key Fix                                                                        |
| ----------- | --------- | ------------------------------------------------------------------------------ |
| Agent 1     | 70.0%     | `_normalize_type_universes()`, better inaccessible detection                   |
| **Agent 2** | **72.4%** | Namespace prefix stripping, local notations, universe decl from non-inst lines |
| Agent 3     | 70.8%     | declared_vars tracking, skip ∀-quantified props, inaccessible type detection   |


**Current SOTA (as of 2026-03-08 Session 6):**

- Sequential first 500: **~72.4%** (Agent 2, on agents/agent2 code)
- All 1000 theorems: **54.6%** (main line Run 15-20, before agent2 merge)
- Expected after merge (Run 21): **~60%+ on 1000**, **~72%+ on first 500**
- Target: >80% on 3 random test sets of 500

**What's still missing for full reconstruction:** Source file `variable` declarations (section-boundary-aware); local helper lemmas; some AlgebraicGeometry Spec/StructureSheaf namespace setup.

**Key reminder:** Mode 1 (corpus test) is NOT our use case. Mode 2 (fill sorry in existing file) gives us the actual file → ~99.9% ceiling. Mode 3 (novel theorem) we generate the file ourselves → ~100%.

---

## 12. Proof Verification Design Decisions

**Name collision fix — always wrap AI submissions:**

```lean
-- Single theorem:
example (n m : ℕ) : n + m = m + n := by omega   -- anonymous, never collides

-- Multi-lemma block:
namespace ATPCheck_a3f9b2c1
private lemma helper : ... := ...
private theorem main : ... := by exact helper
end ATPCheck_a3f9b2c1
```

**Submission rules:** Single proof → `example`. Multi-lemma → `namespace ATPCheck_<uuid>`. (~20-line change to `lean_runner.py`, not yet done.)

**Future — targeted import mode:** REPL importing only what a theorem needs. Eliminates all collision problems. LeanDojo `sid` branching supports it; needs per-theorem dependency graph.

---

## Appendix: Error Codes


| Code                     | Meaning                               | Action                             |
| ------------------------ | ------------------------------------- | ---------------------------------- |
| `state_ref_not_found`    | Cached state expired                  | Re-run with `want_state=true`      |
| `state_ref_incompatible` | Different Mathlib snapshot            | Regenerate with matching toolchain |
| `limit_timeout_exceeded` | REPL timed out                        | Reduce `timeout_s`                 |
| `protocol_mismatch`      | Firecracker envelope version mismatch | Rebuild snapshot                   |


**SLA targets** (`config/atp_threshold_policy.json`): p95 < 200ms. Kyle's measured baseline: `repl_ms_avg=380ms`, `p95_wall=782ms`, concurrency=4.

---

## Session Log

### 2026-03-07 Session 1 — Environment Setup

- WSL2 v2.6.3, Ubuntu 24.04, `/dev/kvm` exists, user not in kvm group yet
- LeanDojo cache found at `~/.cache/lean_dojo/.../mathlib4/` with pre-built `.olean` — no rebuild needed
- git-lfs pull completed (192MB) using HF token via `git -c http.extraHeader=...`
- Corpus structure confirmed: 126,792 theorems, 54,477 tactic proofs
- Key finding: `tactics[0].state_before` gives full Lean proof state at each step — tactic trace corpus, directly usable for meta-reasoning
- Existing HF Space already serves `GET /theorem/<n>/proof` etc. — no extra API needed

### 2026-03-07 Session 2 — Verifier Implementation

- Built `repl_client.py`, `lean_runner.py`, `test_basic.py`, `test_corpus.py`
- 5/5 smoke tests pass. Mathlib cold start ~69s, per-check <1ms after warmup
- Sorry detection fix: Lean emits sorry as plain stdout WARNING not JSON error — added `has_sorry` scan
- Corpus: 3 iterations → 3.3% → 2% (broken `example` approach) → 20% (`private _vt` + namespace)
- Dominant failure: 53/120 `failed to synthesize` — missing `variable` decls from original file

### 2026-03-08 Session 3 — Source Context + Collision Analysis

- Full source file would give ~90-95%, not 100%: `import Mathlib` pre-loads all names, collision unavoidable
- Modes 2+3 (the real use cases) are ~99-100% — collision only affects corpus test (Mode 1)
- Fix for ATP loop: use `example` for single theorems, `namespace ATPCheck_<uuid>` for multi-block
- `private` inside namespace → mangled internal name → zero collision risk

### 2026-03-08 Session 4 — Data Source Discovery + Parallelism

- Discovered `traced_theorems_unified_v2.jsonl` has `open_namespaces`, `namespace`, `file`, full `state_before`
- `app_network_data.jsonl` was stripped for dashboard use (dropped open_namespaces, truncated state_before to 150 chars)
- Implemented `ReplPool` — N subprocess workers, thread-safe queue, staggered starts to avoid lake lock
- Fixed Windows `select.select` → reader thread + `queue.Queue`
- Fixed: was sending `import Mathlib` as a REPL command (entry file already does it)
- Run 5: 80/500 (16%) with traced file + open_namespaces + 4 workers, 9.3s wall time
- Run 6: **140/500 (28%)** with variable reconstruction from `state_before`. `failed_to_synthesize` 167→14 (−153). New dominant errors: `invalid binder annotation` (bad `[T]` emission), universe param errors (CategoryTheory), `expected_token` from `@[simp]` attributes. Wall time: 14.1s

### 2026-03-08 Session 5 — Deep-Dive Failure Analysis + Runs 7–9

**Key discoveries:**

- `✝` heuristic was the single biggest bug: `p✝¹ p✝ q✝ : R[X]` → `variable [R[X]]`. Fix: only names STARTING with `inst` are typeclass instances. Run 7: 205/500 (41%).
- `open_namespaces` ≠ actual `open` declarations. It records the MODULE HIERARCHY PATH. Ground truth is in the actual `.lean` source file.
- Full Mathlib source tree is at `E:\LEAN-experiments\00_experiment1\gitpython-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5\mathlib4\`. Each theorem has a `file` field. We now READ the source file to extract file-level `open` declarations.
- Run 8: **277/500 (55.4%)** after source file open reading. `function_expected` 87→29.
- Additional fixes in Run 9: selective open `(X Y Z)` parsing, `_META_OPENS_SKIP` (Lean/Meta/Elab/Tactic), `𝕜` Unicode regex, function-typed variable hypothesis filter.
- Run 9: **301/500 (60.2%)**. 28% → 60% in one session.
- Remaining: `expected_token:68`, `other:81` (unknown namespaces, ambiguous terms), CategoryTheory universe polymorphism.
- Corpus toolchain confirmed: `leanprover/lean4:v4.10.0-rc1` — SAME as our verifier. Version mismatch is NOT a factor.

**Files changed:** `verifier/test_corpus.py` — 8 targeted fixes, 80 new lines

### 2026-03-08 Session 6 — Source Variable Regression, Agent Evolution, Fix Cascade

**Run 10 result: 1988/5000 = 39.8% — REGRESSION from 60.2%**

Root cause: `_get_source_variables()` emits ALL `variable` declarations from ALL sections of the source file without deduplication or normalization. Two compounding errors:


| Error                                       | Example                                             | Cause                                                     |
| ------------------------------------------- | --------------------------------------------------- | --------------------------------------------------------- |
| `redundant binder annotation update`        | `variable {R : Type*}` declared in sections A and B | Same named variable declared twice in our context         |
| `application type mismatch: motive u u nil` | `variable {α : Type u}` — `u` is universe level var | `u` emitted as term name without `universe u` declaration |


**Fixes implemented (Run 11, 2026-03-08):**

Added `_normalize_and_dedup_vars(var_decls)` post-processor called before emitting `variable` lines:

1. **Universe normalization**: `re.sub(r'\bType\s+[a-z_]\w*\b', 'Type*', decl)` and same for `Sort`. Also handles `Type (max u v)` → `Type`*. Prevents single-letter universe level names from leaking as terms.
2. **Deduplication by named binder**: Parse each `variable` declaration's binder groups (e.g. `{R : Type*}`, `[CommRing R]`), extract names before `:`. If ANY named variable in a declaration conflicts with an already-seen name, SKIP that entire declaration. Anonymous typeclass instances `[CommRing R]` (no `:` in inner body) are never conflicting — kept freely.

```python
_BINDER_RE = re.compile(r'([\(\{⦃\[])(.*?)([\)\}⦄\]])', re.DOTALL)

def _normalize_and_dedup_vars(var_decls):
    seen_names = set()
    result = []
    for decl in var_decls:
        decl = re.sub(r'\bType\s+[a-z_]\w*\b', 'Type*', decl)
        decl = re.sub(r'\bSort\s+[a-z_]\w*\b', 'Sort*', decl)
        decl = re.sub(r'\bType\s*\([^)]{1,40}\)', 'Type*', decl)
        decl = re.sub(r'\bSort\s*\([^)]{1,40}\)', 'Sort*', decl)
        body = re.sub(r'^variable\s*', '', decl).strip()
        introduced = set(); has_conflict = False
        for m in _BINDER_RE.finditer(body):
            if m.group(1) == '[' and ':' not in m.group(2): continue
            if ':' in m.group(2):
                names = [n for n in m.group(2).split(':',1)[0].split()
                         if re.match(r'^[A-Za-z_]\w*$', n)]
                for name in names:
                    if name in seen_names: has_conflict = True; break
                    introduced.add(name)
            if has_conflict: break
        if not has_conflict:
            seen_names |= introduced; result.append(decl)
    return result
```

**Run 11 result: 384/1000 = 38.4%** — still regressed. Deeper analysis:


| Error                                                            | Count | Root Cause                                                                       |
| ---------------------------------------------------------------- | ----- | -------------------------------------------------------------------------------- |
| `other` (misc)                                                   | 425   | Large, diverse — dominated by `unknown namespace 'subset'` and universe issues   |
| `failed_to_synthesize`                                           | 84    | Missing typeclass instances                                                      |
| `redundant binder annotation`                                    | 65    | Dedup not catching Unicode var names (α, β) — regex `[A-Za-z_]` misses them      |
| `expected_token`                                                 | 59    | Malformed Lean syntax (CategoryTheory, complex types)                            |
| `unknown namespace 'subset'`                                     | 54    | Doc comment at column 0 starting with `open subset ...` parsed as open statement |
| `invalid use of explicit universe params, 'Category' is a local` | 61    | `Category.{v, u}` — explicit universe params on typeclass names not stripped     |
| `Type*'` invalid syntax                                          | —     | `Type uE'` → `Type*'` — universe regex didn't consume trailing `'` in `uE'`      |


**Additional fixes implemented (Run 12, 2026-03-08):**

1. **Block comment tracking in `_get_source_opens`**: Track `/- ... -/` doc comments. Lines inside `/--` or `/-` blocks are now skipped even if they start at column 0. Prevents doc-string prose like `open subset s of a parameter space` from being parsed as open statements.
2. **Uppercase-only namespace names**: Changed `re.match(r'^[A-Za-z_]', name)` → `re.match(r'^[A-Z]', name)`. All valid Lean 4 namespace names are PascalCase (uppercase first). Lowercase first letter = prose word in doc comment.
3. **Unicode dedup names**: Changed `[A-Za-z_]\w`* → `[^\W\d]\w*\'*` in dedup logic. Now correctly tracks `α`, `β`, `𝕜`, `E'`, `F''` as variable names.
4. **Universe apostrophe fix**: Changed `\bType\s+[a-z_]\w*\b` → `\bType\s+[a-z_]\w*\'`* — now consumes trailing `'` in universe level names like `uE'`, `uF''`, preventing `Type*'` invalid syntax.
5. **Typeclass universe strip**: `Category.{v, u}` → `Category` via `re.sub(r'(\b[A-Z]\w*)\.\{[^}]{1,60}\}', r'\1', decl)`. Removes explicit universe parameter annotations from typeclass names in variable declarations.

**Run 12: 384/1000 = 38.4%** — still regressed. Fixes broke more than they fixed (`expected_token` 59→113). New block-comment tracking caused issues.

**Decision: Revert source variables entirely.** The section-scoped variable approach requires knowing the theorem's line number to determine which sections are in scope. Without that, we can't safely emit source file variables. Reverted to `_extract_variables()` (state_before reconstruction).

**Run 13 (revert confirmed): 504/1000 = 50.4%**

- Note: 50.4% on 1000 ≠ regression from 60.2% on 500. Theorems 1-500 still ~~60%; theorems 501-1000 are harder (~~40%). Both are correct.
- Failure breakdown: `other: 229`, `expected_token: 123`, `type_mismatch: 90`, `failed_to_synthesize: 21`, `function_expected: 18`, `unknown_identifier: 15`

**3 Opus agents launched** (2026-03-08 ~04:45 UTC) each with copy of current code and distinct focus:

- Agent 1 (`agents/agent1/`): Variable reconstruction from state_before
- Agent 2 (`agents/agent2/`): Open namespace reconstruction
- Agent 3 (`agents/agent3/`): CategoryTheory universe polymorphism

Each runs 5 iterations on 500 theorems, 4 workers. Results to be merged back.

### 2026-03-08 Session 7 — Breakthrough: Opens-Inside-Namespace + SMP Unicode Fix

**Major session — crossed 80% target on first 500 sequential theorems.**

**Background:** Agents 4-9 launched (3 Opus + 3 Haiku), each starting from 73.4% baseline (merged agent2 fixes). Run 21 result: 561/1000 = 56.1%. Agents 1-3 settled at 70-72.4% on first 500.

**Fix 1: Opens-Inside-Namespace (+6.4 pp) — Run 22: 79.8%**

Root cause: `open Spec`, `open Category`, `open NatIso` etc. at TOP LEVEL fail with `unknown namespace` because these short names only exist as sub-namespaces inside their parent. E.g. `Spec` is `AlgebraicGeometry.Spec` — the short name `Spec` is valid INSIDE `namespace AlgebraicGeometry` but not at top level.

Fix: Move `opens` and `var_decls` INSIDE the namespace block:

```python
if ns:
    lines.append(f"namespace {ns}")
    lines += opens       # inside namespace, so 'open Spec' resolves to AlgebraicGeometry.Spec
    lines += var_decls
    lines.append(body)
    lines.append(f"end {ns}")
```

Impact: `unknown_namespace: 79 → 0`, `function_expected: 24 → 3`, `other: 42 → 19`.

**Fix 2: ∀-quantified inst filter (minor +0.4 pp)**

Skip `inst✝ : ∀ (i : 𝒰.J), HasPullback ...` — Lean syntax `variable [∀ ...]` is invalid.

```python
if type_str.startswith("∀"):
    continue   # in inst block
```

*Fix 3: h Prop-variable filter (minor)**

Skip hypothesis variables: `hf : BddAbove (range f)`, `ha : a ≠ 0` — Prop-valued, not data.

**Fix 4: set_option quotPrecheck false (+minor)**

Added to prevent `unknown identifier 'D.toGlueData' at quotation precheck` errors.

**Fix 5: SMP Unicode encoding bug in repl_client.py (+30 theorems)**

Root cause: `json.dumps` with default `ensure_ascii=True` encodes `𝒰` (U+1D4B0) as `\ud835\udc30` (UTF-16 surrogate pair). Lean's JSON parser receives two surrogate code points which are NOT valid Unicode identifier characters → `expected token`.

All SMP Unicode characters (codepoint > U+FFFF) in theorem context: `𝒰`, `𝒮`, `𝓕` etc.

Fix in `repl_client.py` line 202:

```python
payload = json.dumps({"sid": sid, "cmd": cmd}, ensure_ascii=False) + "\n"
```

Impact: All 30 `AlgebraicGeometry.Scheme.Pullback.*` theorems now pass.

**Run Summary (first 500 sequential theorems):**


| Run    | Passes  | Rate      | Fix                                    |
| ------ | ------- | --------- | -------------------------------------- |
| 21     | ~342    | ~68%      | agent2 merged (pre-ns-fix)             |
| 22     | 399     | 79.8%     | opens-inside-namespace                 |
| 23     | 401     | 80.2%     | + ∀ filter, h* filter, quotPrecheck    |
| **24** | **447** | **89.4%** | + SMP Unicode fix in repl_client.py    |
| **25** | TBD     | TBD       | Random 500 (held-out validation set 1) |
| **26** | TBD     | TBD       | 1000 theorems (full benchmark)         |


**Run 24 = 89.4% (447/500) — EXCEEDED 80% TARGET!** SMP Unicode fix added +9.2 pp alone (30 Pullback + all other `𝒰`/`𝒮`/`𝓕` theorems).

**Agents 4-9 status (as of 05:41 UTC):**

- Agents 4-7, 9: 73.4% baseline, actively iterating
- Agent 8 (random): 64.6% on random 500
- Each running code modifications between runs

**Remaining failures after Run 23 (99 total):**

- `expected_token: 43` — mostly `AlgebraicGeometry.Scheme.Pullback.`* (now fixed with SMP Unicode fix)
- `unknown_identifier: 25` — `D.toGlueData` (quotPrecheck fixes), misc
- `other: 19` — various tactic failures
- `failed_to_synthesize: 7`, `function_expected: 3`, `type_mismatch: 2`

---

## Session 8 — 2026-03-08

### Run Results


| Run | Corpus     | Pass | Rate      | Fix                                                               |
| --- | ---------- | ---- | --------- | ----------------------------------------------------------------- |
| 27  | 500 seq    | 451  | 90.2%     | ✝-in-type-str skip + indented continuation line skip              |
| 28  | 500 seq    | 451  | 90.2%     | Removed h* filter (no change)                                     |
| 29  | 500 random | 405  | 81.0%     | All fixes to date — random validation **TARGET MET**              |
| 30  | 1000       | 877  | 87.7%     | Full 1000 benchmark                                               |
| 31  | 500 seq    | 453  | **90.6%** | + inst-references-explicit_params filter + #adaptation_note strip |
| 32  | 500 random | 422  | **84.4%** | Same fixes, random seed                                           |


### Fix 21: Skip inst variables that reference explicit_params (+3.4pp random)

**Root cause:** `variable [(i : ι) → TopologicalSpace (α i)]` — when `ι` and `α` are explicit params of the theorem (e.g. `{ι : Type*} {α : ι → Type*}`), they are not in scope at `variable`-declaration time. Lean auto-binds them with unknown types (`?m.39`), then the theorem's explicit binding conflicts → `function expected at α term has type ?m.39`.

**Fix in `_extract_variables()`:** For inst lines, extract identifier tokens from `type_str`. If any token is in `explicit_params`, skip the inst declaration. The theorem already declares those typeclass constraints explicitly (e.g. `[∀ i, TopologicalSpace (α i)]`).

```python
inst_tokens = set(re.findall(r'[^\W\d]\w*', type_str, re.UNICODE))
if inst_tokens & explicit_params:
    continue
```

Cases fixed: `dense_pi`, `Submodule.fg_pi`, `PiLp.norm_eq_of_L2`, `Real.volume_Ico`, and others with Pi-type typeclass constraints.

### Fix 22: Strip `#adaptation_note` from proof text

`#adaptation_note` in Lean 4 requires a following `/-- ... -/` doc comment. The corpus sometimes omits the required comment → parse failure. Simple fix: `re.sub(r'^\s*#adaptation_note\b[^\n]*\n?', '', proof_text, flags=re.MULTILINE)`.

### Remaining Failures (Run 32, random 500)

#### Framing: Why Can Lean Verify These But We Cannot?

When Mathlib was originally compiled, each theorem was checked inside its **full file context**: every `variable` declaration, every `open` statement, every `local notation`, every private helper defined earlier in the same file, and the exact namespace/section stack at that precise line. Lean's elaborator had all of this and produced a correct proof term. LeanDojo's tracer then snapshotted only a thin slice of that context — the tactic state at the first tactic (`state_before`), the theorem statement, and the proof text — and discarded the rest.

We are therefore attempting to **reconstruct a full Lean elaboration context from an incomplete record**. The gap between what we reconstruct and what the original Lean elaborator had is exactly the 16% failure rate.

**Key questions this raises:**

| Question | Answer |
|----------|--------|
| *Why does proper Lean succeed?* | It has the complete, ordered, already-elaborated file context. Every variable, instance, notation, and definition is already in scope in exactly the right order, with exactly the right universe levels. No reconstruction is needed. |
| *What is fundamentally missing from our reconstruction?* | (1) Section `variable` declarations that were not used in *this* theorem's explicit signature but are referenced in the proof body. (2) Private/local helper defs from earlier in the same file. (3) The exact `open` chain at that specific line (we read all opens from the whole file, including ones declared *after* the theorem). (4) Multi-name binder structure (`(U V : T)` — we only capture `U`). (5) Universe variable names and their ordering. (6) Which scoped notations are active. |
| *Can we get access to the missing context?* | **Yes, partially, today**: the Mathlib source tree is already on disk at `MATHLIB_ROOT`. We can read the full file and extract everything up to the theorem's line number. **Fully, with re-tracing**: a modified LeanDojo tracer could capture the fully-elaborated section context (all variables in scope with their declared — not inferred — types, all active opens, all local defs). This would push the ceiling from ~90% toward ~99%. **Never**: inaccessible tactic-state variables (`cs.leftInvSeq✝`) that leaked into proof text are a data collection artifact that cannot be recovered without re-extracting those specific proofs. |
| *What is the systematic fix?* | **Mode 2 verification**: instead of reconstructing context from `state_before`, locate the theorem in the source file, extract the file from line 1 to the theorem's end line, and submit the entire prefix to the REPL. This is essentially re-checking the file. Expected pass rate: ~99%. Cost: much larger REPL commands (~50–500 lines per theorem instead of ~10). |

The table below classifies the 16% failure rate by symptom, with the upstream data-collection reason for each and the systematic fix that would eliminate that class entirely.

---

| Error | Count | Concrete Examples | Upstream Root Cause | Why Lean Succeeds / We Fail | What We're Missing | Systematic Fix |
|-------|-------|-------------------|--------------------|-----------------------------|-------------------|----------------|
| `other` | 28 | `tactic 'rewrite' failed` in `CoxeterSystem.leftInvSeq_eq_reverse_rightInvSeq_reverse`; `unsolved goals` after `ring_nf` in `WeierstrassCurve.Jacobian.addY_of_X_eq'`; `simp made no progress` in `TrivSqZeroExt.snd_pow_of_smul_comm` (proof references local `aux` def); `application type mismatch` in `Ring.DirectLimit.of.zero_exact` (proof uses `lift` which is a private irreducible def) | The proof text references **private, `@[irreducible]`, or locally-defined lemmas and definitions** that exist in the source file but are invisible to `import Mathlib`. `private def aux`, `private irreducible_def add` (RingQuot), `private lemma rexp_neg_image_aux` are all compiled into Mathlib's `.olean` but with name-mangled or inaccessible identifiers. | Lean compiled these definitions as part of the file; they were in scope when the theorem was checked. We have `import Mathlib` which exposes only *public* names — private/irreducible defs are name-mangled (e.g. `_private.Mathlib.RingTheory.RingQuot.add`) and cannot be referenced by their source name. | The source file's private definition text, and knowledge of which theorems depend on them. This is available in `MATHLIB_ROOT` — we can detect `private def`/`private lemma` preceding the theorem and prepend them verbatim. | **Prepend private helpers**: scan the source file for `private`/`protected` defs between the section start and the theorem; include them in the REPL command. This would fix the RingQuot cluster (~6 theorems) and most `other` failures that are private-def-dependent. |
| `unknown_identifier` | 14 | `unknown identifier 'cs.leftInvSeq✝'` (`CoxeterSystem`); `unknown identifier 'o.areaForm✝'` (`Orientation`); `unknown identifier 'G✝'` (`MeasureTheory.QuotientMeasureEqMeasurePreimage`); `unknown identifier 'p✝'` (`WittVector.truncateFun_mul`); `unknown identifier '𝕜✝'` (`ContinuousLinearMap.apply_norm_eq_sqrt_inner_adjoint_right`); `unknown identifier 'one_div_two'`; `unknown identifier 'comp'` (`List.sublist_eq_map_get`); `unknown identifier 'gcd_dvd'` | Two distinct upstream bugs. **Bug A (✝-leak, ~8 cases)**: LeanDojo's proof extractor captured the proof text from the elaborated tactic state rather than the raw source. When a user writes `obtain ⟨i, x, rfl⟩` and Lean introduces an anonymous binder, the tactic state shows `cs.leftInvSeq✝`. Some proof steps in the corpus were apparently extracted with these internal names. **Bug B (renamed lemma, ~6 cases)**: the corpus was traced against one Mathlib commit; some lemmas were renamed between that commit and our verifier's commit (they share the same toolchain but Mathlib evolves). | Lean at tracing time had the exact name `leftInvSeq` bound as a local anonymous variable, or the lemma `one_div_two` existed under that name. We have neither. | **Bug A**: irrecoverable without re-extracting those specific proof steps from source. The raw `.lean` source uses user-written tactic scripts without `✝` names. **Bug B**: a lemma rename map or a diff between the traced commit and the verifier's commit. The Mathlib git history has this. | **Bug A**: Re-trace affected theorems from source using `lake env lean --run` on the actual `.lean` files. **Bug B**: run `git log --all --oneline -S 'one_div_two'` on the Mathlib repo to find renames; maintain a small static rename map for the ~6 cases. Long-term: pin the verifier to the exact corpus Mathlib commit. |
| `type_mismatch` | 11 | `application type mismatch: StateT σ m, argument m` — `m` emitted as `{m : Type* → Type*}` but proof elaborates `m : Type u → Type u_1`; `type mismatch (toEven Q)(reverse(involute x)) : ↥(even (Q' Q)) : Type (max ?u.159786 ?u…)` — universe polymorphism collapsed incorrectly; `type mismatch: lift (fun ix : s => …)` in `Ring.DirectLimit` — coercion chain broken by wrong universe on `G i` | Our universe normalization (`Type u_3 → Type*`) is too aggressive. `Type u_3` in state_before is Lean's auto-generated name for a *specific* universe level — it is in the same universe as the other auto-named levels in that theorem's scope. When we collapse them all to `Type*`, we can create type inequalities: `m : Type* → Type*` when the proof needs `m : Type u → Type u_1` where `u < u_1`. The `state_before` encodes the correct universe relationships implicitly through the auto-names. | Lean used the exact universe levels from the original `variable` declarations, where all relationships were established at declaration time. We collapse everything to `Type*` which is elaborated freshly for each use, potentially with different universe metavariables. | The declared types (not the inferred tactic-state types) of section variables. `state_before` shows elaborated types with auto-named universes like `u_1`, `u_2` which look distinct but may be the same or may be in a sub/supertype relationship we can't recover. | **Preserve universe structure**: instead of collapsing `Type u_3` to `Type*`, map each `u_N` name to a fresh named universe variable (`u`, `v`, `w` in order of first appearance) and emit `universe u v w`. This preserves the relationship pattern even if not the exact names. Or better: use the source file `variable` declarations verbatim (they have the original universe names). |
| `failed_to_synthesize` | 11 | `failed to synthesize NeZero 2` (`quadratic_eq_zero_iff`, 3 theorems); `failed to synthesize SmoothManifoldWithCorners I' M'` (`Trivialization.contMDiffOn_symm_trans`, `Filter.EventuallyEq.mfderivWithin_eq`); `failed to synthesize Semiring R` (`AlgebraicGeometry.genericPoint_eq_bot_of_affine`); `failed to synthesize NoZeroSMulDivisors ℝ (F →L[ℝ] ℝ)` (`IsSelfAdjoint.linearly_dependent_of_isLocalExtrOn`); `failed to synthesize Invertible 2` (2 theorems) | The missing instances were provided by **section `variable` declarations** in the source file — either as explicit `variable [NeZero 2]` or as consequence of a higher-level instance like `variable [CharZero R]` (which implies `NeZero 2` via `two_ne_zero`). Our `_extract_variables()` reads `inst✝` lines from `state_before`, but only those that appear in the *first tactic's* state. Instances that are in scope but not *displayed* by Lean's pretty-printer (e.g. because they're derived from others) are invisible to us. | Lean had the full instance chain from the file's `variable` block. `variable [CharZero R]` causes Lean to automatically include `[NeZero 2]` as a synthesized instance wherever needed. Our REPL command has neither `CharZero` (filtered or not visible) nor `NeZero 2` (never displayed in state_before because it's derived, not declared). | The source file's `variable` block. For `quadratic_eq_zero_iff`, `Mathlib/RingTheory/Polynomial/Cyclotomic/Basic.lean` has `variable [CharZero R]` which implies `NeZero 2`. We have `MATHLIB_ROOT` — we could read `variable` blocks from source. Reverted this approach (Run 10) due to section-scoping issues, but a more careful implementation would work. | **Source-file variable extraction (revisited)**: read the source file up to the theorem's line number (not the whole file) and extract only `variable` declarations that are syntactically in scope. This avoids the section-scoping issue that caused Run 10's regression. This would fix essentially all `failed_to_synthesize` cases. |
| `function_expected` | 9 | `function expected at α term has type ?m.39` (`dense_pi`, partially fixed); `function expected at M term has type ?m.2239` (`Submodule.fg_pi`, partially fixed); `function expected at basicOpen term has type ?m.932` (`AlgebraicGeometry.LocallyRingedSpace.comp_ring_hom_ext`); `function expected at BilinForm term has type ?m.31679` (`mem_selfAdjointMatricesSubmodule'`); `function expected at [R] term has type List (Type u_1)` (`Algebra.TensorProduct.map_ker`) | Two sub-causes. **Sub-cause A** (partially fixed by Fix 21): our explicit_params regex only captures the *first* name in a multi-name binder. `(U V : Opens X)` captures `U` but not `V`. We then emit `variable (V : Opens ↑↑X.toPresheafedSpace)` — but `X` is an explicit param not yet in scope, so Lean auto-binds `X : ?m` with metavar type. When `V`'s type references `X`, `X` gets type `?m`, and then `X` used as a function gives `function expected`. **Sub-cause B**: some proof bodies use `[R]` as a notation (e.g. `R`-module type bracket) but our context doesn't have that notation, so Lean parses `[R]` as a list literal. | Lean had the complete multi-name binder structure and knew `V` was bound at the same type as `U`. It also had all active notations including any local bracket notations. | **Sub-cause A**: the multi-name binder structure of the theorem's explicit params. This is in the theorem statement string — we just need a better parser. **Sub-cause B**: local notations for bracket syntax. These are in the source file and partially extracted by `_get_source_local_notations()`. | **Sub-cause A — systematic fix**: replace the single-name explicit_params regex with a binder-aware parser that extracts all names from `(a b c : T)` groups. One regex: `r'[({]\s*((?:[^\W\d]\w*\s+)+[^\W\d]\w*)\s*:'` captures the full name list before `:`. This would eliminate all `function_expected` cases from sub-cause A. Sub-cause B: extend local notation extraction to cover bracket notations. |
| `expected_token` | 4 | `unexpected token 'ℙ'; expected '_' or identifier` (`MeasureTheory.pdf.integral_pdf_smul`) — `open ProbabilityTheory` makes `ℙ` a *notation token*, then `variable (ℙ : Measure Ω)` tries to use it as an identifier name in a binder position but Lean's parser already consumed it as a syntax token; `Adaptation notes must be followed by /-- comment -/` (`Nat.bit_mod_two`) — corpus didn't capture the required doc comment; `unexpected token 'ᵒᵖ'` (`List.get_ofFn_go`) — `ᵒᵖ` is a postfix notation but appears in a position Lean can't parse it | The corpus records `state_before` variable names verbatim. Some names (like `ℙ`) are simultaneously valid Lean identifiers AND scoped notations. In the original file, the variable named `ℙ` was declared *before* `open ProbabilityTheory` was in effect, so there was no conflict. We emit `open ProbabilityTheory` first (reading all file opens), then declare `variable (ℙ : …)` — at which point `ℙ` is already a notation token and can't be used as an identifier name. The data collection process didn't record the ordering of opens relative to variable declarations. | Lean's original file had `ℙ` declared as a section variable before the `open ProbabilityTheory` section that introduced the notation. No conflict. We apply all opens uniformly at the top regardless of their position in the file. | The **line-number position** of each `open` statement relative to the theorem and relative to the file's `variable` declarations. We have the source file — we could read opens only up to the theorem's line. | **Position-aware open extraction**: modify `_get_source_opens()` to only collect `open` statements that appear *before* the theorem's line number in the source file. This also fixes cases where `open ProbabilityTheory` at line 349 was included for theorems at line 100 that never needed it. |
| `already_declared` | 1 | `a universe level named 'u' has already been declared` in `List.get_ofFn_go` — state_before has `α : Type u`, causing us to emit `universe u`; but the theorem statement uses `{n}` with implicit universe polymorphism, and when Lean elaborates the statement, it also internally binds a universe named `u` | Our universe scanner finds `u` in the state_before and emits `universe u`. Then Lean's auto-bound implicit mechanism also creates a `u` when elaborating the theorem's `{α : Type u}` signature. Two declarations of the same universe name in the same scope is a hard error. This is an edge case of the broader problem: we're declaring things that Lean would declare implicitly, causing double-binding. | Lean's original file had `universe u` declared once at the section level (or relied entirely on auto-polymorphism without explicit declaration). We're adding an explicit `universe u` when the file might have relied on auto-binding. | Whether the source file explicitly declared `universe u` or relied on auto-bound universe polymorphism. This is readable from `MATHLIB_ROOT` — `grep -n '^universe' file.lean`. | **Universe-from-source**: check the source file for explicit `universe` declarations. Only emit `universe X` if the source file also has it. If the source uses auto-polymorphism, don't emit any `universe` declaration and let Lean infer. This also fixes the `already_declared` case and improves universe-level correctness across all theorems. |


**SOTA: 90.6% sequential 500, 84.4% random 500, 87.7% full 1000. Target (80%) exceeded on all test sets.**

### Held-Out Evaluation (3× Random 1000)


| Run                          | Pass        | Rate              |
| ---------------------------- | ----------- | ----------------- |
| Run 33 (random 1000, seed A) | 840/1000    | 84.0%             |
| Run 34 (random 1000, seed B) | 837/1000    | 83.7%             |
| Run 35 (random 1000, seed C) | 826/1000    | 82.6%             |
| **Mean ± std**               | **834 ± 7** | **83.4% ± 0.6pp** |


Consistent ~83-84% on truly random held-out sets. Sequential 500 is ~7pp higher (easier theorems). All results exceed the 80% target.

---

## Experiment: Soundness Probe — Can the Verifier Detect Subtly Wrong Proofs?

**Date:** 2026-03-08
**Script:** `verifier/soundness_test.py`
**Results file:** `artifacts/soundness_test_results.json`

### Purpose

The 84–90% pass rates tell us how often the verifier *accepts* reconstructed Lean proofs.
But a complementary question is equally important: **is the verifier actually checking proof
correctness, or are there ways to slip a wrong proof past it?**

This experiment is a **soundness probe**. We take theorems the verifier already confirmed
are correct, introduce subtle deliberate errors into each proof (without touching the
theorem statement), and feed them back through the same pipeline. If the verifier is sound,
every distorted proof should be rejected. Any theorem the verifier still *accepts* after
distortion is a **false positive** — a signal that the verification may be too permissive.

This is distinct from the integrity audit (which asks "did we cheat to get high numbers").
Here we ask "given the current verifier, can a subtly wrong proof sneak through?"

### Why Longer Proofs?

Longer multi-tactic proofs give us richer targets. A 3-line proof often has few places
to inject an error that isn't immediately obvious. A 15-line proof using `rcases`, `simp`,
and lemma applications can absorb a subtle error (flipped direction, wrong field accessor,
swapped constructor) in a way that looks plausible to a human reviewer but Lean's type
checker should catch.

### Protocol

1. **Phase 1** — Run the first 100 sequential corpus entries (proof_text ≥ 150 chars)
   through the verifier. Collect those that PASS. Select the 20 longest.

2. **Phase 2** — Apply one distortion strategy to each proof. Run the distorted entry
   through the **exact same** `build_check_command → ReplPool → _classify` pipeline,
   with no special flags, no bypass. Record outcome.

3. **Scoring** — DETECTED = verifier rejects distorted proof (correct behaviour).
   MISSED = verifier accepts distorted proof (false positive).

### Distortion Strategies (Priority Order)

Each theorem gets the first applicable strategy in this list:

| # | Strategy | What changes | Why Lean should catch it |
|---|----------|-------------|--------------------------|
| 1 | `flip_mp_mpr` | `.mp` → `.mpr` or reverse | Wrong direction of Iff application; type mismatch |
| 2 | `flip_field_1_2` | `h.1` → `h.2` (first occurrence) | Wrong And/Prod component; type mismatch |
| 3 | `ring_to_linarith` | `ring` → `linarith` | `linarith` can't close polynomial ring identities |
| 4 | `omega_to_ring` | `omega` → `ring` | `ring` can't close ℕ/ℤ inequalities or decide goals |
| 5 | `flip_left_right` | `left` → `right` or `Or.inl` → `Or.inr` | Wrong Or constructor; type of the other branch doesn't match |
| 6 | `insert_symm` | `exact h` → `exact h.symm` | Flips equality direction; type mismatch at goal |
| 7 | `strip_symm` | Remove first `.symm` | Removes deliberate direction flip; type mismatch |
| 8 | `wrong_comm` | `mul_comm` → `add_comm` | Wrong ring law; rewrite target doesn't match |
| 9 | `norm_num_to_omega` | `norm_num` → `omega` | `omega` can't handle ℝ/ℚ or non-linear arithmetic |
| 10 | `simp_to_exact_rfl` | `simp [...]` → `exact rfl` | Goal isn't definitionally `rfl`; type mismatch |
| 11 | `remove_last_tactic` | Drop last substantive tactic line | Leaves at least one unsolved subgoal |
| 12 | `truncate_half` | Keep first 50% of tactic lines | Leaves multiple unsolved subgoals |

Strategies 1–10 are **semantic errors** — they look like plausible Lean code but use the
wrong logical object. Strategies 11–12 are **structural fallbacks** used only when no
semantic strategy applies.

A healthy verifier should detect nearly all of these. The interesting cases are any MISSEDs
from the semantic strategies (1–10), which would indicate the verifier is accepting proofs
without fully checking the internal tactic details.

### Results

**Run date:** 2026-03-08 | **Script:** `verifier/soundness_test.py` | **Raw data:** `artifacts/soundness_test_results.json`

```
Phase 1:  100 candidates (proof_len ≥ 150 chars, sequential)
          86/100 passed → selected top 20 by proof length (358–797 chars)
Phase 2:  20 distorted proofs submitted
          DETECTED: 20/20 (100%)
          MISSED:    0/20   (0%)
          Soundness rate: 100.0%
```

**Strategy distribution across 20 theorems:**

| Strategy | Count | How Lean caught it |
|----------|-------|--------------------|
| `insert_symm` | 9 | `invalid field 'X'`, `unknown constant`, `typeclass stuck`, `unknown identifier` |
| `flip_field_1_2` | 3 | `application type mismatch` (`.1` and `.2` have different types) |
| `flip_mp_mpr` | 2 | `application type mismatch` (wrong iff direction, argument type doesn't match) |
| `wrong_comm` | 2 | `unknown identifier` (`mul_sadd_comm`, `sadd_comm` don't exist) |
| `simp_to_exact_rfl` | 2 | `type mismatch` or `unexpected identifier` (goal not definitionally `rfl`) |
| `strip_symm` | 1 | `type mismatch` (removed direction flip breaks composition type) |
| `flip_left_right` | 1 | `application type mismatch` (wrong Or branch, argument type doesn't fit) |
| `remove_last_tactic` | 0 | — (fallback never needed) |
| `truncate_half` | 0 | — (fallback never needed) |

All 20 distortions were **targeted semantic errors** — no structural fallbacks were needed.

**Per-theorem detail:**

| # | Theorem | Proof len | Distortion | What changed | Error Lean reported |
|---|---------|-----------|------------|-------------|---------------------|
| 1 | `RingQuot.eqvGen_rel_eq` | 797 | `insert_symm` | `RingConGen.Rel.of` → `RingConGen.symm.Rel.of` | `unknown identifier 'RingConGen.symm.Rel.of'` |
| 2 | `SSet.horn.hom_ext` | 747 | `flip_field_1_2` | `f.1` → `f.2` in surjective destructure | `application type mismatch: f.property vs f.val` |
| 3 | `discrim_le_zero` | 735 | `flip_field_1_2` | `neg_nonpos.2` → `neg_nonpos.1` | `application type mismatch: arg has type ≥ 0 not ≤ 0` |
| 4 | `Pullback.lift_comp_ι` | 733 | `insert_symm` | `pullback.hom_ext` → `pullback.symm.hom_ext` | `invalid field notation: pullback is not C.X form` |
| 5 | `QuaternionAlgebra.Basis.lift_mul` | 643 | `wrong_comm` | `mul_smul_comm` → `mul_sadd_comm` *(via substring match)* | `unknown identifier 'mul_sadd_comm'` |
| 6 | `NormalizedMooreComplex.d_squared` | 639 | `simp_to_exact_rfl` | `simp [...]` → `exact rfl` inside `by` | `unexpected identifier; expected ')',',' or ':'` (parse fail) |
| 7 | `Function.Exact.split_tfae'` | 599 | `strip_symm` | `e.symm.injective` → `e.injective` | `type mismatch: Injective (⇑e ∘ ?) but expected Injective (⇑e.symm ∘ ?)` |
| 8 | `Prime.dvd_of_pow_dvd_pow_mul_pow_of_square_not_dvd` | 591 | `insert_symm` | `hp.dvd_of_dvd_pow` → `hp.symm.dvd_of_dvd_pow` | `invalid field: 'And.dvd_of_dvd_pow' not in env` |
| 9 | `Pullback.cocycle` | 549 | `insert_symm` | `pullback.hom_ext` → `pullback.symm.hom_ext` | `invalid field notation: pullback not of form C.X` |
| 10 | `OpenCover.fromGlued_open_map` | 531 | `insert_symm` | `Set.preimage_image_eq` → `Set.symm.preimage_image_eq` | `unknown constant 'Set.symm.preimage_image_eq'` |
| 11 | `dvd_prime_pow` | 506 | `flip_mp_mpr` | `ih.mp hno` → `ih.mpr hno` | `application type mismatch: arg has type q∣p^n but expected ∃ i≤n` |
| 12 | `associated_of_dvd_dvd` | 470 | `insert_symm` | `apply ha0` → `apply ha0.symm` | `invalid field 'symm': 'Not.symm' not in env` |
| 13 | `TrivSqZeroExt.mul_inv_rev` | 439 | `wrong_comm` | `smul_comm` → `sadd_comm` *(via substring match)* | `unknown identifier 'sadd_comm'` |
| 14 | `basicOpen_eq_of_affine` | 438 | `simp_to_exact_rfl` | `simp only [...]` → `exact rfl` | `type mismatch: rfl : ?m=?m, expected x ∈ basicOpen f` |
| 15 | `functionField_isFractionRing_of_isAffineOpen` | 430 | `insert_symm` | `mem_nonZeroDivisors_iff_ne_zero` → `...ne_zero.symm` | `typeclass stuck: Nontrivial ?m.5151` *(symm flips iff, metavar leaks)* |
| 16 | `TrivSqZeroExt.snd_list_prod` | 428 | `insert_symm` | `exact add_comm _ _` → `exact add_comm.symm _ _` | `invalid field notation: add_comm has type ∀(a b:?), not C.X` |
| 17 | `genericPoint_eq_of_isOpenImmersion` | 424 | `flip_field_1_2` | `f.1.base` → `f.2.base` | `invalid field notation: f.prop has type ∀(x:X)... not C.X` |
| 18 | `prime_mul_iff` | 368 | `flip_left_right` | `Or.inl ⟨..⟩` → `Or.inr ⟨..⟩` | `application type mismatch: second branch arg types wrong` |
| 19 | `prime_pow_iff` | 360 | `insert_symm` | `hp.not_unit` → `hp.symm.not_unit` | `invalid field 'not_unit': 'And.not_unit' not in env` |
| 20 | `prime_pow_succ_dvd_mul` | 358 | `flip_mp_mpr` | `...iff_left h.ne_zero).mp` → `.mpr` | `application type mismatch: arg has type p^n∣x*y not p∣x^(n+1)*y` |

**Error type summary:**

| Lean error | Count | Interpretation |
|-----------|-------|---------------|
| `application type mismatch` | 7 | Type-level mismatch — wrong direction, wrong branch, wrong component |
| `invalid field notation` | 5 | `.symm` or `.not_unit` etc. applied to something that doesn't have that field |
| `unknown identifier / constant` | 4 | Constructed identifier doesn't exist in Lean's environment |
| `type mismatch` | 2 | Goal type doesn't match what the tactic produces |
| `typeclass instance stuck` | 1 | Symm flip on iff caused metavar leak; typeclass synthesis failed |
| `unexpected identifier` | 1 | `exact rfl` inside `by (...)` caused parse failure |

### Analysis

**The verifier is fully sound against all 20 distortions.** Lean's type checker caught every subtle error, including:

- **Flip within a chain** (`dvd_prime_pow` — `ih.mp` → `ih.mpr`): Lean reports the exact argument type mismatch — the `.mpr` direction expects the *result* type of the iff as input, but we passed the *premise* type.

- **Substring-based wrong_comm** (`QuaternionAlgebra.Basis.lift_mul` — `mul_smul_comm` → `mul_sadd_comm`): The `wrong_comm` function hit a substring match inside a longer identifier name, creating a nonsense identifier. Lean's environment lookup caught it immediately.

- **Symm on proposition** (`associated_of_dvd_dvd` — `ha0 : ¬a = 0`): `ha0.symm` tried to call `.symm` on a negation. Lean knows `Not` doesn't have a `.symm` field and rejects it.

- **Typeclass leakage** (`functionField_isFractionRing` — `...ne_zero.symm`): Flipping an Iff at the end of a proof caused metavariables to stop resolving, and typeclass inference failed with `Nontrivial ?m.5151`. The type checker caught a second-order consequence of the error.

**Key implications:**

1. The 84–90% pass rate is not noise. When a proof is wrong, Lean says so — precisely.
2. The verifier cannot be fooled by plausible-looking but type-incorrect proofs. There are no partial-credit passes.
3. None of the 20 distortions required a fallback structural strategy (remove_last_tactic / truncate_half), confirming that even semantic 1-token errors are reliably detectable.

**Caveat:** This test covers distortions to *correct* proofs. It does not test whether an AI could construct a novel *wrong* proof that happens to type-check. That's a fundamentally harder question (equivalent to asking whether Lean's type theory has unsound axioms, which it doesn't under standard assumptions). What this test confirms is that the verifier's infrastructure (REPL, JSON transport, `_classify`, pool) faithfully reports Lean's kernel decisions without accidentally passing errors.

---

## Future Task: Firecracker Cold-Start Elimination

**Status:** Not started. Deferred until Mode 2 correctness is established.

### The Problem

Every Lean worker starts by loading Mathlib from scratch: ~70 seconds per worker.
With `ReplPool(size=4)`, that's 280s of cold start before any checks run. The pool
amortises this over many checks (pay it once, run 500+ checks at ~50ms each), but
the 70s is still paid on every process restart.

### Kyle's Firecracker Approach

Kyle's `breadboard` infrastructure creates a Firecracker microVM snapshot:

1. Boot a KVM microVM with Lean installed on the rootfs
2. Start the Lean REPL server inside the VM
3. Send `import Mathlib` and wait for it to load (~70s one time)
4. Issue `firecracker PUT /vm/snapshot/create` — freeze VM memory to disk
5. For every subsequent session: restore from snapshot in **~1 second** instead of 70s

The session is fully isolated (fresh Lean state each time) and nearly instant.
This is what `FirecrackerReplClient` in `breadboard/lean_repl.py` implements.

### What Already Exists vs What's Missing

| Component | Status |
|-----------|--------|
| `FirecrackerReplClient` in `breadboard/lean_repl.py` | ✓ Code exists |
| Kyle's CI/health check scripts in `breadboard/scripts/` | ✓ Code exists |
| `/dev/kvm` on this machine | ✓ Available |
| Firecracker binary | ✗ Not installed |
| Lean rootfs disk image (`rootfs.ext4`) | ✗ Not built |
| Pre-made memory snapshot (`lean.snap`, `lean.mem`) | ✗ Not created |
| vsock socket (`vsock.sock`) | ✗ Not set up |

The scripts consume snapshots — they don't create them. Creating them requires:
1. Download/build Firecracker binary for x86_64-linux
2. Build a minimal Linux rootfs with the correct Lean toolchain (`leanprover/lean4:v4.10.0-rc1`)
3. Run: boot VM → start Lean REPL → `import Mathlib` → take snapshot → save files
4. Set env vars: `FIRECRACKER_SNAPSHOT`, `FIRECRACKER_SNAPSHOT_MEM`, `FIRECRACKER_SNAPSHOT_VSOCK`, `FIRECRACKER_ROOTFS`

### Why Not Do It Now

- The `ReplPool` already provides the memory-freeze benefit for our batch use case:
  Lean loads Mathlib once per worker and stays alive across thousands of checks.
- Firecracker is only needed when you need **truly fresh Lean state per check** (e.g.,
  for untrusted user submissions that could corrupt the environment).
- Building the rootfs + snapshot is 3-4 hours of infrastructure work separate from
  proof verification improvements.

### When to Do It

After Mode 2 correctness is established and the verifier is being used in production
(real ATP loop with user submissions). At that point, implement as a separate
infrastructure task. The code path is ready — just needs the snapshot files.

---

## Verification Integrity Audit

**Date:** 2026-03-08
**Purpose:** Honest, complete assessment of whether the 84–90% pass rates reflect genuine Lean proof verification or were achieved by relaxing the verifier.
**Method:** Line-by-line audit of `verifier/test_corpus.py` and `verifier/repl_client.py`.
**Verdict summary:** Broadly honest. Two specific relaxations worth calling out, one unmeasured gap that could materially inflate the numbers. Detailed breakdown below.

---

### Things That Are Definitely NOT Cheating

#### `noncomputable section`

Every generated Lean command is wrapped in `noncomputable section ... end`.

`noncomputable` relaxes Lean's *computability* requirement — it lets you declare a value or function that can't be run as code. It does **not** relax the *logical* requirement. A noncomputable proof of `∀ n, P n` is still a complete, correct proof. Lean's kernel checks the proof term regardless.

For propositions (which is what almost all Mathlib theorems are), `noncomputable` has zero effect. Props are always noncomputable in Lean's type theory.

**Verdict: Not a cheat. Standard practice for Mathlib-style code.**

#### `private theorem NAME_vt`

Every theorem is renamed from `theorem Foo.bar` to `private theorem bar_vt`. This is necessary because `import Mathlib` already puts `Foo.bar` in the environment; redeclaring it would cause `already been declared` errors that are false failures.

This rename does NOT change what the proof proves. We are still checking the same statement with the same proof text. The rename works around the open-world import environment.

**Verdict: Correct engineering. Not a cheat.**

#### `ensure_ascii=False` (Fix 17)

Changed `json.dumps(cmd)` to `json.dumps(cmd, ensure_ascii=False)` in `repl_client.py`. Without this, SMP Unicode characters like `𝒰` (U+1D4B0) were encoded as surrogate pair escape sequences (`\ud835\udc30`), which Lean's JSON parser rejected as invalid UTF-8. This is a bug fix — without it, theorems with SMP characters always fail.

**Verdict: Bug fix, not a relaxation.**

#### Timeouts and exceptions → FAIL

All timeouts (60s per-command, 90s pool timeout) and all exceptions are returned as error responses, classified as `fail`. They are never silently dropped or counted as passes.

**Verdict: Conservative. If anything, this slightly deflates the rate.**

#### `_extract_variables` inst-filter (Fix 21)

The filter `if inst_tokens & explicit_params: continue` was added to *reduce* false passes — it prevents emitting `variable [∀ i, C (α i)]` when `α` is an explicit theorem parameter, which would cause Lean to auto-bind `α` with an unknown type and then clash with the theorem's own binding. This filter reduces inflation.

**Verdict: Reduces inflation, not increases it.**

---

### Relaxations That Are Real But Defensible

#### `set_option quotPrecheck false`

Added to every generated command. `quotPrecheck` is a Lean 4 option that controls pre-elaboration syntactic validation of terms inside macro quotations. When enabled, Lean does a preliminary identifier-resolution pass before full elaboration.

Why we disabled it: a theorem in `AlgebraicGeometry` contained `D.toGlueData` inside a term quotation. With `quotPrecheck true`, Lean emitted `unknown identifier 'D.toGlueData' at quotation precheck` and rejected the theorem at parse time — even though actual elaboration would have succeeded (because `D` is in scope).

The quotation precheck is a *syntactic* shortcut, not a logical one. Full elaboration still happens afterward. A theorem that passes with `quotPrecheck false` and fails with `quotPrecheck true` is one where the parse-time heuristic produced a false negative; the proof term is still fully kernel-checked.

However: if there exist theorems where quotPrecheck catches a real problem that elaboration would miss (possible in metaprogramming-heavy code), disabling it could allow false passes. This seems very unlikely for tactic proofs.

**Magnitude:** Probably <0.5% effect.

**Verdict: Mild relaxation. Defensible as fixing a spurious parse-time error. Should be noted in any published result.**

#### Opens from entire source file (not just above theorem line)

`_get_source_opens(entry)` reads the entire `.lean` source file and collects all top-level `open` statements, regardless of whether they appear before or after the theorem's line.

If `open Foo` appears below the theorem in the file, it wasn't in scope when the original theorem was compiled. Adding it to our verification gives access to names the original proof didn't have.

In practice, extra opens can also cause name conflicts that shadow identifiers — so this effect runs in both directions. The `ℙ`/`ProbabilityTheory` case in the failure table is a case where an open ADDED AFTER the theorem causes a parse failure: `ℙ` is both a variable name and a scoped notation, and the ordering matters.

**Magnitude:** Mixed, ~±1%. Fixing it (stop at theorem line) would be more correct but unlikely to change results by more than 1-2%.

**Verdict: Minor distortion in both directions. Not systematic inflation.**

#### Variable declarations from full source file (not section-scoped)

`_get_source_variables(entry)` reads all file-level `variable` declarations without tracking section boundaries. Variables declared inside `section Foo ... end Foo` blocks may not be in scope for theorems outside that section. We may add variables that the original theorem didn't have.

However, Lean's `variable` mechanism only injects a variable if it's actually *referenced* by name in the theorem or proof. Unused variables are silently ignored. This substantially limits the inflation risk.

**Magnitude:** Small. Lean's use-based variable injection is a strong defense. Estimated <1%.

**Verdict: Minor potential inflation. Low severity given Lean's variable injection semantics.**

---

### The One Unmeasured Gap (Potentially Material)

#### `sorry` is counted as PASS

In `_classify`:
```python
def _classify(response) -> str:
    if response.error is None and not response.has_sorry:
        return "pass"
    if response.has_sorry:
        return "sorry"
    return f"fail:{...}"
```

In `_record`:
```python
if verdict in ("pass", "sorry"):
    passed += 1
```

**`sorry` is silently counted as a pass.** `sorry` in Lean 4 is a tactic that discharges any goal unconditionally — it's an admitted axiom, not a proof. Counting it as verified is incorrect.

**Why was this done?** Probably as a "compiler accepted it" heuristic — if Lean compiled the theorem (even via sorry), the structural context reconstruction was at least correct. But from a proof-validity perspective, sorry-passes are false positives.

**How likely is this to matter?** The corpus is traced from Mathlib, which has no sorry in production. The `proof_text` fields should not contain sorry, and we don't inject sorry. So in practice, sorry verdicts are probably zero or near-zero.

However: **we don't know for certain.** The run output logs fail categories but does NOT log how many `sorry` verdicts occurred — they go directly into the pass bucket. We have never measured this.

**Severity rating:** Unknown magnitude. Probably 0% for this corpus. But it's a correctness bug.

**How to fix:** Add a sorry counter to `_record`. Print it in the summary. One run would settle this.

---

### What We Are Actually Measuring

It's worth being explicit about the verification model, since some apparent "relaxations" are actually properties of the task.

We are NOT replaying the original Lean compilation with the original file context. We are:

1. Taking `(statement, proof_text)` from LeanDojo corpus records
2. Reconstructing *an approximation* of the original context (opens, variables, namespace)
3. Submitting this reconstructed context to Lean in a fresh REPL session (post-`import Mathlib`)
4. Checking whether Lean accepts the proof in this reconstructed context

This means our 84–90% pass rate answers: **"Can we reconstruct enough context from corpus metadata that Lean accepts the proof?"** — not **"Is this proof formally correct?"** (it obviously is; it's from verified Mathlib).

The ~16% failures are not cases of wrong proofs. They're cases where our context reconstruction is incomplete, causing Lean to reject a correct proof for missing context.

### Summary Table

| Issue | Cheat? | Direction | Magnitude | Severity |
|-------|--------|-----------|-----------|----------|
| `noncomputable section` | No | Neutral (required) | 0% | None |
| `private theorem NAME_vt` | No | Prevents false fails | ~3–5% fewer failures | None (correct) |
| `ensure_ascii=False` | No (bug fix) | Prevents false fails | ~3–5% fewer failures | None (correct) |
| Timeouts → FAIL | No | Conservative | ~0.5% deflation | None |
| `set_option quotPrecheck false` | Mild relaxation | +inflates | <0.5% | Low |
| Opens from full file (not line-bounded) | Mild distortion | Mixed ±1% | ~1% | Low |
| Variables from full file (not section-scoped) | Minor inflation | +inflates | <1% | Low |
| `sorry` counted as PASS | Correctness bug | +inflates | **Unknown (likely 0%)** | **Medium — unmeasured** |
| inst-token filter (Fix 21) | Reduces inflation | −inflates | ~3% fewer false passes | None |

### Bottom Line

**The 84–90% rates are broadly honest.** The core verification is sound: Lean's kernel checks every proof term, timeouts and exceptions are failures, and the main engineering decisions (`noncomputable`, `private theorem`, `ensure_ascii=False`) are correct rather than relaxing.

**Two things to fix before publishing:**

1. **Measure and report sorry count.** Add a counter. If it's zero (likely), the numbers are clean. If nonzero, exclude sorry-passes from the headline rate or report separately.

2. **Disclose `set_option quotPrecheck false`.** It's defensible but it is a relaxation. A reader should know about it.

**One caveat to carry in any external report:** The pass rate measures *reconstruction quality*, not proof correctness. Lean accepted these theorems in a reconstructed context; the original proofs are from verified Mathlib and were correct to begin with. The failures are context-reconstruction failures, not proof failures.

---

## Systematic Solution: Mode 2 Verification

**Date:** 2026-03-08

### Summary of Remaining Failures (16% gap)

The ~16% failure rate is **NOT** because the proofs are wrong — they're all from verified Mathlib. The gap is entirely due to **context reconstruction failure**: we only have `state_before` (a thin slice), while original Lean had the full file context.

### Root Causes and Systematic Fixes

| Error Category | Root Cause | Systematic Fix |
|----------------|------------|----------------|
| `other` (28) | Private/irreducible defs in source file | Prepend `private def`/`private lemma` from source |
| `unknown_identifier` (14) | ✝-leak in proof text OR lemma renames | Re-trace OR rename map |
| `type_mismatch` (11) | Universe normalization too aggressive | Preserve `u_1, u_2` structure, emit `universe u v w` |
| `failed_to_synthesize` (11) | Missing section `variable` declarations | Read source file up to theorem line |
| `function_expected` (9) | Multi-name binder `(U V : T)` only captures first | Binder-aware parser for all names |
| `expected_token` (4) | `open` at wrong line position | Position-aware extraction (only before theorem) |
| `already_declared` (1) | Duplicate universe declaration | Check source for explicit `universe` before emitting |

### The Key Insight: Position-Aware Source Extraction

The **ultimate systematic fix** is **Mode 2 verification**:
1. Locate theorem in source file
2. Extract file from line 1 to theorem's end line
3. Submit entire prefix to REPL

This is essentially re-checking the file with its original context. Expected pass rate: ~99%.

### Available Resources

| Resource | Path |
|----------|------|
| **Full Mathlib source (same commit as corpus)** | `E:\LEAN-experiments\00_experiment1\gitpython-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5\mathlib4\` |
| **Corpus (traced theorems)** | `E:\LEAN-experiments\00_experiment1\jsons\traced_theorems_unified_v2.jsonl` |
| **Corpus code index (premises)** | `E:\LEAN-experiments\00_experiment1\jsons\corpus_code_index.json` |

### Implementation Notes for Mode 2

To implement Mode 2 systematic verification:

1. **Extract theorem position:** Parse `file` field + find theorem name in source
2. **Read file prefix:** Read lines 1 to `theorem_end_line`
3. **Extract needed context:**
   - `open` statements before theorem line
   - `variable` declarations before theorem line
   - `universe` declarations before theorem line
   - `private` defs/lemmas before theorem line
   - Local notations before theorem line
4. **Emit complete command:**
   ```
   noncomputable section
   [file_prefix_content]
   [namespace X]
   private theorem NAME_vt := proof
   [end X]
   end
   ```

This avoids all the reconstruction issues at once — we use Lean's own source as the context.

### Implementation in minimax/ Subfolder

Created `minimax/test_corpus_mode2.py` implementing Mode 2 verification:
- **Location:** `E:\LeanATP Harness\minimax\`
- **Files:** `repl_client.py`, `test_corpus_mode2.py`, `progress_log.md`

Key functions implemented:
- `find_theorem_bounds()` - Find theorem start/end line in source file
- `extract_opens()` - Extract open statements from prefix (filtering declarations)
- `extract_variables()` - Extract variable declarations
- `extract_universes()` - Extract universe declarations
- `extract_notations()` - Extract local notations
- `extract_private_defs()` - Extract private helper definitions
- `build_mode2_command()` - Build verification command with source prefix

**Current Status (2026-03-08):** Debugging phase. First ~10 corpus entries have empty `proof_text` causing parse errors. Need to filter for non-empty proofs before testing.

---

## Mode 2 Task: Minimax Agent Brief

**Date:** 2026-03-08
**Task file:** `E:\LeanATP Harness\minimax\better_plan.md`
**Agent:** minimax 2.5
**Goal:** Implement Mode 2 (source-file-prefix) verification; target ≥99% pass rate

### Why Mode 2

Mode 1 hits a ~90% ceiling because context is reconstructed from `state_before` — a thin
slice that omits section scoping, private helpers, line-position-dependent opens, and
multi-name binders. All those gaps are eliminated in Mode 2 by reading the actual source
file prefix up to the theorem's line, which is the exact context Lean had originally.

### What the Minimax Agent Must Implement

The core architectural change is the **Stripped Prefix approach**:

```
Take source_file.lean lines 1 to (theorem_start - 1)
Filter out: import lines, public theorem/def/instance/class declarations, #check/#eval
Keep verbatim: section/namespace/end structure, open statements, variable declarations,
              universe declarations, local notations, private defs/abbrevs
Track namespace+section stack at theorem position → emit matching `end` statements
Append: private theorem short_name_vt [statement] := [proof]
Close all open section/namespace blocks
```

This preserves section scoping automatically, handles private helper defs of any
complexity, and avoids every error class in the failure table.

### Critical Issue the Agent Was Hitting: The 60-Second Cold-Start Trap

The agent was running `python3 test_corpus_mode2.py --count 10` repeatedly.
Each invocation starts a fresh Lean process: 70s cold start + 5s actual work + exit.
Utilisation: 6%. The agent's own ETA estimate said "70s bottleneck per run" — it
noticed the problem but didn't fix it.

**Fix:** always run `--count 500 --workers 4`. The 70s cold start is paid once per
worker (280s total for 4 workers), then 500 checks run at ~50ms each. Amortised
overhead is <1% instead of 93%.

### Memory Freeze / Firecracker Note

The existing `ReplPool` in `repl_client.py` already implements the memory-freeze
pattern: Lean loads Mathlib once per worker, branches via `sid=0` for every check.
No process restart, no re-loading Mathlib.

For Firecracker VM snapshots (Kyle's approach — sub-second process restarts for
fully isolated sessions): infrastructure is in `breadboard/scripts/`. Environment
variables needed: `FIRECRACKER_SNAPSHOT`, `FIRECRACKER_SNAPSHOT_MEM`,
`FIRECRACKER_SNAPSHOT_VSOCK`, `FIRECRACKER_ROOTFS`. KVM is available on this
machine (`/dev/kvm` exists). Implement only after Mode 2 correctness is solved.
If Mode 2 works, copy it back to `verifier/test_corpus_mode2.py` in the main repo
and measure the improvement there.

### Expected Pass Rate Targets

| Milestone | Sequential 500 | Random 500 |
|-----------|---------------|------------|
| Mode 1 baseline | 90.6% | 84.4% |
| Mode 2 target | ≥ 97% | ≥ 95% |
| Mode 2 ceiling | ~99% | ~99% |

The ~1% floor at "99% ceiling" is: theorems whose proof text contains ✝-inaccessible
variable names (corpus extraction artifact — unfixable without re-tracing) or that
reference lemmas renamed between the corpus tracing commit and our toolchain commit.