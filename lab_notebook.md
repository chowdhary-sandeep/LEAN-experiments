# LeanATP Harness — Lab Notebook

> Project: Meta-methods for discovering new mathematics via Lean 4 proof verification.
> Kyle McCleary's `breadboard` repo reimplements Harmonic's ATP architecture. We built the missing subprocess backend and parallel pool.

---

## 1. Breadboard Overview

Agentic coding + ATP harness. Exposes Lean 4 REPL via HTTP, backed by Firecracker snapshots. Runs EvoLake batch campaigns. Based on Harmonic's architecture.

**We do NOT use the HTTP API** — we bypass it and talk to the Lean subprocess directly.


| Component         | File                           | Purpose                                                  |
| ----------------- | ------------------------------ | -------------------------------------------------------- |
| REPL interface    | `breadboard/lean_repl.py`      | `CheckRequest`, `CheckResult`, `FirecrackerReplService`  |
| HTTP API          | `api/cli_bridge/atp_router.py` | `POST /atp/v1/repl`, `/atp/v1/repl/batch` (unused by us) |
| EvoLake campaigns | `breadboard_ext/evolake/`      | Multi-round batch ATP with checkpointing                 |


**EvoLake loop:** Generate candidates → ATP batch → collect sorry goals → LLM fills gaps → verify → repeat.

**Breadboard gaps we filled:** `FirecrackerReplService` was a stub raising `NotImplementedError`. No VM code, no snapshot management, no vsock transport. We built a subprocess backend.

---

## 2. How Lean Proof Checking Works

**Problem:** `import Mathlib` = ~100k definitions, 60s+ cold start. 1000 proofs × 60s = 16hrs.


| Layer                  | Mechanism                                                   | Cost                          |
| ---------------------- | ----------------------------------------------------------- | ----------------------------- |
| Naive                  | `lean myfile.lean` — loads .olean, checks, exits            | 60s per proof                 |
| **REPL** (what we use) | Persistent process, JSON over stdin/stdout, state branching | 60s once, then 6–220ms        |
| Firecracker            | Freeze RAM to disk, restore ~200ms per VM                   | ~200ms restore + ~380ms check |


**REPL protocol** (`{"sid": N, "cmd": "..."}` → `{"sid": N+1, "error": null}`). State IDs branch — `import Mathlib` once → sid=0, all 1000 checks branch from sid=0. Mathlib loaded once per process.

`state_ref` = sid integer (subprocess) or snapshot filename (Firecracker).

---

## 3. Firecracker Snapshots

Boots miniature Linux VM in ~125ms (Amazon open-source, local). Communicates via vsock (AF_VSOCK port 52). Snapshot = frozen RAM. Restore = un-pause (no reboot, no reimport).


|                 | Docker                       | Firecracker           |
| --------------- | ---------------------------- | --------------------- |
| Memory snapshot | No                           | Yes — full RAM frozen |
| Restore         | Must re-run `import Mathlib` | ~12–200ms             |
| Security        | Process-level                | Full VM kernel        |


**Kyle's vsock envelope:** `{"type":"repl","version":1,"payload":{"command":"...","timeout":60.0}}` → `{"type":"repl_response","version":1,"response":{"sid":1,"error":null}}`. Defined in `breadboard/vsock_protocol.py`.

---

## 4. Architecture

```
┌───────────────────────────────────────────────────────┐
│  HTTP API / Service / EvoLake / Diagnostics / Models  │  ← IN BREADBOARD REPO
├───────────────────────────────────────────────────────┤
│  FirecrackerReplService  (seam / interface)           │  ← WE IMPLEMENTED THIS
├───────────────────────────────────────────────────────┤
│  VM Management / Snapshot Pool / vsock Transport      │  ← KYLE'S NEW BRANCH
│  VM Image (Lean+Mathlib) / REPL Binary                │  ← KYLE'S SCRIPTS BUILD
│  Firecracker / Linux with KVM                         │  ← WSL2 provides KVM
└───────────────────────────────────────────────────────┘
```

---

## 5. WSL2 Environment


| Item                             | Status                                                   |
| -------------------------------- | -------------------------------------------------------- |
| WSL2 Ubuntu 24.04, kernel 6.6.87 | Available                                                |
| `/dev/kvm`                       | EXISTS ✓ (Hyper-V KVM passthrough)                       |
| kvm group                        | Missing — `sudo usermod -aG kvm $USER && wsl --shutdown` |
| Firecracker binary               | Not installed                                            |
| VM rootfs with Lean+Mathlib      | Kyle's `fc_create_lean_snapshot_vsock.sh` builds it      |
| Snapshot pool                    | Kyle's `build_lean_snapshot_pool.sh`                     |


Nesting: Windows → Hyper-V → WSL2 → Firecracker → Lean microVM. Restore times ~50–400ms vs 12–200ms bare metal.

---

## 6. What We Built — Subprocess Verifier

```
Your code / EvoLake
      │  CheckRequest → CheckResult
      ▼
SubprocessReplService  (our FirecrackerReplService implementation)
      │  {"sid": N, "cmd": "..."}  →  {"sid": N+1, "error": null}
      ▼
lake env lean /tmp/lean_repl_entry.lean  (persistent process)
      ▼
Lean 4 kernel + Mathlib .olean  (v4.10.0-rc1, ~/.cache/lean_dojo/...)
```

**Files:**

```
verifier/
  repl_client.py   ← LeanReplClient, ReplSession, ReplPool (parallel)
  lean_runner.py   ← SubprocessReplService + sorry detection
  test_basic.py    ← 5 smoke tests (5/5 PASS)
  test_corpus.py   ← corpus batch verifier, --workers N for parallel
```

**Key implementation details:**


| Decision          | Detail                                                                                        |
| ----------------- | --------------------------------------------------------------------------------------------- |
| `base_sid = 0`    | Entry file runs `import Mathlib` before REPL starts. Don't send it as a command (would fail). |
| Sorry detection   | Lean emits sorry as plain stdout WARNING, not JSON `error`. `has_sorry` scans `stdout_lines`. |
| Non-blocking read | Reader thread feeds `queue.Queue` — `select.select` doesn't work with pipes on Windows        |
| elan PATH         | `env["PATH"] = f"{home}/.elan/bin:" + env.get("PATH", "")`                                    |
| Startup timeout   | 300s — import Mathlib via /mnt/c/ 9P takes ~100s, observed ~69s warm                          |
| Parallel workers  | `ReplPool`: N workers started with 4s stagger (avoids `lake env` exclusive file lock)         |


**Performance:**


| Metric                               | Value                |
| ------------------------------------ | -------------------- |
| Mathlib cold load (once per session) | ~69s                 |
| Simple proof (`decide`, `rfl`)       | 6–10ms               |
| Medium tactic                        | 20–50ms              |
| Complex proof                        | 100–220ms            |
| 500 checks, 4 workers (wall time)    | **9.3s** (~75ms avg) |


**Trustworthy?** Yes. Lean kernel (CIC) is the judge. `error: null` = kernel-verified. No approximation. Same kernel as all 200k+ Mathlib theorems.

### What a Theorem Needs to Verify Consistently

Bare `statement + proof_text` fails ~80% — theorems are written inside their original file context. Must reconstruct:


| Context                             | Source                                                                         | Fixes                      |
| ----------------------------------- | ------------------------------------------------------------------------------ | -------------------------- |
| `variable {R : Type*} [CommRing R]` | Parse `state_before` above `⊢` (inst✝ → `[T]`, `X : Type u_N` → `{X : Type*}`) | 167 `failed to synthesize` |
| `open Polynomial`                   | `open_namespaces` field (traced file) — filter out `Mathlib.`* entries         | 45+ `unknown identifier`   |
| `open scoped BigOperators`          | Scan proof/statement for `∑`/`∏`/`‖·‖`/`!`                                     | `expected token`           |
| `noncomputable section`             | Always prepend, costs nothing if not needed                                    | Several algebra failures   |
| Local helper defs                   | Position data zeroed in corpus — can't walk file. Affects ~5 cases.            | 5 `type mismatch`          |


**Reconstruction template:**

```lean
noncomputable section
open scoped BigOperators   -- if ∑/∏ detected

variable {R : Type*} [CommRing R]   -- from state_before

namespace Polynomial
open Polynomial
private theorem coeff_mul_vt ... :=   -- _vt suffix avoids name collision
  <proof_text>
end Polynomial
end
```

---

## 7. Kyle's New Branch

**Branch:** `origin/codex/atp-lean-ship-20260307`


| File                                                     | Purpose                                |
| -------------------------------------------------------- | -------------------------------------- |
| `scripts/lean_snapshot/fc_create_lean_snapshot_vsock.sh` | 1381-line Firecracker snapshot builder |
| `scripts/lean_snapshot/build_lean_snapshot_pool.sh`      | Builds N snapshots for concurrency     |
| `breadboard/vsock_protocol.py`                           | Envelope protocol helpers              |
| `docs/atp_runbook.md`                                    | Operational runbook                    |


**fc_create flow:** rootfs + vmlinux → boot VM (8GB/4vCPU) → build Lean4Repl → wait for Mathlib warm → snapshot → `lean.snap` + `lean.mem`.

**Kyle vs us:**


| Layer         | Kyle                     | Us                      | Compatible?            |
| ------------- | ------------------------ | ----------------------- | ---------------------- |
| Interface     | `FirecrackerReplService` | Same                    | YES                    |
| Lean protocol | LeanDojo CommandRepl     | Same, direct            | YES                    |
| Transport     | vsock (AF_VSOCK:52)      | subprocess stdin/stdout | Different, transparent |
| Cold start    | ~200ms per restore       | ~69s once               | Different tradeoff     |
| Per-check     | ~380ms avg               | 6–220ms                 | Ours faster per-check  |


**Shortcutting the 2-hour build:** `SKIP_LAKE_BUILD_IF_PRESENT=1` is the default — script skips `lake build` if `Mathlib.olean` exists. Our LeanDojo cache has it.
Plan: build rootfs (~~1hr) → copy .olean cache into data.ext4 (~~10min) → run script (~~30min) = **~~1hr total**. Also: `mathlib_env.olean` pickle generated on first run (~5s reload vs 70s reimport).

---

## 8. Parallelism

**Implemented:** `ReplPool` in `repl_client.py`. N workers boot in parallel (~70s regardless of N). Thread-safe `queue.Queue` dispatch. OS deduplicates read-only `.olean` pages — N=4 ≈ **10–14GB RAM**, not 4×8GB.

```bash
python test_corpus.py --count 500 --workers 4 --random
```

**Option B — Firecracker pool (future):** Kyle's `build_lean_snapshot_pool.sh`. Use when: untrusted multi-agent AI code, clean-state guarantees, production. Not needed now.

---

## 9. Corpus Data

**We were testing against the wrong file.** `_app_data_creater.py` stripped fields for a web dashboard:


| File                                          | Fields                                             | `open_namespaces`? | `state_before`         |
| --------------------------------------------- | -------------------------------------------------- | ------------------ | ---------------------- |
| `app_network_data.jsonl`                      | `full_name`, `statement`, `proof_text`, `tactics`  | **NO — stripped**  | Truncated to 150 chars |
| `traced_theorems_unified_v2.jsonl` ← use this | All above + `file`, `namespace`, `open_namespaces` | **YES**            | Full, untruncated      |


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