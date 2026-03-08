# LeanATP Harness — Master Reference

> Project: Meta-methods for discovering new mathematics via Lean 4 proof verification.
> Kyle McCleary's `breadboard` repo reimplements Harmonic's ATP architecture. We built the missing subprocess backend and parallel pool.

---

## 1. Breadboard Overview

Agentic coding + ATP harness. Exposes Lean 4 REPL via HTTP, backed by Firecracker snapshots. Runs EvoLake batch campaigns. Modeled on Harmonic's architecture.

**We do NOT use the HTTP API** — we bypass it and call the REPL subprocess directly.

| Component | File | Purpose |
|---|---|---|
| REPL interface | `breadboard/lean_repl.py` | `CheckRequest`, `CheckResult`, `FirecrackerReplService` |
| HTTP API | `api/cli_bridge/atp_router.py` | `POST /atp/v1/repl`, `/atp/v1/repl/batch` |
| EvoLake campaigns | `breadboard_ext/evolake/` | Multi-round batch ATP with checkpointing |
| Sandbox backends | `breadboard/sandbox*.py` | Docker / gVisor / Firecracker — swappable |

**HTTP API shape** (for reference — not used by us):
```json
POST /atp/v1/repl
{"commands": ["theorem foo..."], "state_ref": "...", "timeout_s": 30.0, "want_state": true}
→ {"success": true, "errors": [], "sorries": [], "new_state_ref": "abc123", "metrics": [...]}
```

**EvoLake loop:** Generate candidates → ATP batch → collect sorry goals → LLM fills gaps → verify → repeat with checkpointing.

**What breadboard does NOT provide:** theorem generator, premise retrieval, LLM-in-the-loop, `FirecrackerReplService` implementation (was a stub — we built it).

---

## 2. How Lean Proof Checking Works

**Problem:** `import Mathlib` = ~100k definitions, 60s+ cold start. 1000 proofs × 60s = 16hrs. Unusable.

| Layer | Mechanism | Cost |
|---|---|---|
| Naive | `lean myfile.lean` — loads .olean, checks, exits | 60s per proof |
| **REPL** (what we use) | Persistent process, JSON over stdin/stdout, state branching | 60s once, then 6–220ms |
| Firecracker | Freeze RAM to disk, restore in ~200ms, discard VM after | ~200ms restore + ~380ms repl |

**REPL protocol (LeanDojo `Lean4Repl.lean`):**
```
Send:    {"sid": N, "cmd": "..."}
Receive: {"sid": N+1, "error": null}
```
State IDs are branching handles. `import Mathlib` once → sid=1. All 1000 theorem checks branch from sid=1. Mathlib loaded **once per process lifetime**.

`state_ref` in breadboard = sid integer (subprocess path) or snapshot filename (Firecracker path).

---

## 3. Firecracker Snapshots

Boots miniature Linux VM in ~125ms (Amazon open-source, runs locally, no cloud). Communicates via **vsock** (AF_VSOCK port 52).

**Snapshot = frozen RAM image.** Restore = un-pause. No reboot, no reimport.

| | Docker | Firecracker |
|---|---|---|
| Isolation | Process-level | Full VM (separate kernel) |
| Memory snapshot | No | Yes — full RAM frozen |
| Restore | Must re-run `import Mathlib` | ~12–200ms |
| Security | Weaker | Strong |

**Kyle's vsock envelope:**
```json
{"type": "repl", "version": 1, "payload": {"command": "theorem foo...", "timeout": 60.0}}
→ {"type": "repl_response", "version": 1, "response": {"sid": 1, "error": null}}
```
Handshake: `hello` / `hello_ack`. Defined in `breadboard/vsock_protocol.py`.

---

## 4. Architecture — What Exists vs What We Added

```
┌───────────────────────────────────────────────────────┐
│  HTTP API / Service / EvoLake / Diagnostics / Models  │  ← IN BREADBOARD REPO
├───────────────────────────────────────────────────────┤
│  FirecrackerReplService  (seam / interface)           │  ← WE IMPLEMENTED THIS
├───────────────────────────────────────────────────────┤
│  VM Management / Snapshot Pool / vsock Transport      │  ← KYLE'S NEW BRANCH
│  VM Image (Lean+Mathlib) / REPL Binary                │  ← KYLE'S SCRIPTS BUILD
│  Firecracker Binary / Linux Host With KVM             │  ← WSL2 provides KVM
└───────────────────────────────────────────────────────┘
```

**Original breadboard gaps** (before Kyle's branch): no VM start code, no snapshot management, no vsock transport, no VM image with Lean, no snapshot pool. `FirecrackerReplService` raised `NotImplementedError`.

---

## 5. WSL2 Environment

| Item | Status |
|---|---|
| WSL2 (Ubuntu 24.04, kernel 6.6.87) | Available |
| `/dev/kvm` | EXISTS ✓ (Hyper-V KVM passthrough) |
| kvm group membership | Missing — `sudo usermod -aG kvm $USER && wsl --shutdown` |
| Firecracker binary | Not installed |
| VM kernel (`vmlinux`) | Not present |
| VM rootfs with Lean+Mathlib | Kyle's script builds it |
| Snapshot pool manager | Kyle's `build_lean_snapshot_pool.sh` |

Nesting: Windows → Hyper-V → WSL2 VM → Firecracker → Lean microVM. Three levels, works fine. Restore times ~50–400ms vs 12–200ms bare metal.

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
  stage0.md        ← lab notebook
```

**Key implementation details:**

| Decision | Detail |
|---|---|
| `base_sid = 0` | Mathlib loaded via entry file before REPL starts. No `import Mathlib` command sent. |
| Sorry detection | Lean emits sorry as plain stdout WARNING, not JSON `error`. `has_sorry` scans `stdout_lines`. |
| Non-blocking read | `os.read(fd, 4096)` — `.read1()` doesn't exist on `_io.FileIO` |
| elan PATH | `env["PATH"] = f"{home}/.elan/bin:" + env.get("PATH", "")` |
| Startup timeout | 300s — import Mathlib via /mnt/c/ 9P takes ~100s, observed ~69s warm |

**Performance:**

| Metric | Value |
|---|---|
| Mathlib cold load (once per session) | ~69s |
| Simple proof (`decide`, `rfl`) | 6–10ms |
| Medium tactic | 20–50ms |
| Complex proof | 100–220ms |

**Trustworthy?** Yes — completely. The Lean kernel (CIC) is the judge. `error: null` = kernel-verified. No approximation. Same kernel as all 200k+ Mathlib theorems.

### What a Theorem Needs to Verify Consistently

Bare `statement + proof_text` fails ~80% — theorems are written inside their original file context. Must reconstruct:

| Context | Source | Fixes |
|---|---|---|
| `variable {R : Type*} [CommRing R]` | `state_before`: parse everything above `⊢` | 53 `failed to synthesize` |
| `open Polynomial` | `open_namespaces` field (see §9) or derive from `full_name` | 27 `unknown identifier` |
| `open scoped BigOperators` | Scan proof for `∑`/`∏`/`‖x‖`/`x!` | 18 `expected token` |
| `noncomputable section` | Always prepend, costs nothing | Several algebra failures |
| Local helper defs | Preceding defs in same file — position data zeroed, hard | 5 `type mismatch` |

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

**Pass rate progression:**

| Fix | Rate |
|---|---|
| Bare statement | ~3% |
| `private` rename + namespace wrap | 20% |
| + `open X` | ~28% |
| + `variable` from `state_before` | ~55% |
| + `open scoped` from symbol scan | ~60% |
| + `noncomputable` | ~62% |
| Ceiling (collision limit) | ~90–95% |

Ceiling is not 100%: `import Mathlib` pre-loads all Mathlib names. Re-declaring hits `already been declared` regardless. Only affects Mode 1 (corpus re-verification). Modes 2+3 are ~99–100%.

---

## 7. Kyle's New Branch

**Branch:** `origin/codex/atp-lean-ship-20260307`

| File | Purpose |
|---|---|
| `scripts/lean_snapshot/fc_create_lean_snapshot_vsock.sh` | 1381-line Firecracker snapshot builder |
| `scripts/lean_snapshot/build_lean_snapshot_pool.sh` | Builds N snapshots for concurrency |
| `scripts/lean_snapshot/activate_lean_snapshot.sh` | Exports env vars, runs ATP CI checks |
| `breadboard/vsock_protocol.py` | Envelope protocol helpers |
| `docs/atp_runbook.md` | Operational runbook |

**`fc_create_lean_snapshot_vsock.sh` flow:** rootfs + vmlinux → boot VM (8GB/4vCPU) → build Lean4Repl → wait for Mathlib warm → snapshot → `lean.snap` + `lean.mem`.

**Kyle vs us:**

| Layer | Kyle | Us | Compatible? |
|---|---|---|---|
| Interface | `FirecrackerReplService` | Same | YES |
| Lean protocol | LeanDojo CommandRepl | Same, direct | YES |
| Transport | vsock (AF_VSOCK:52) | subprocess stdin/stdout | Different, transparent |
| Isolation | Firecracker VM | Single process | Different |
| Cold start | ~200ms per restore | ~69s once | Different tradeoff |

**Performance:**

| Metric | Ours | Kyle's Firecracker |
|---|---|---|
| Cold start | 69s once | ~200ms per restore |
| Per-check | 6–220ms | ~380ms avg |
| Parallelism | ReplPool (N subprocesses) | VM pool |

**Shortcutting the 2-hour build:** `SKIP_LAKE_BUILD_IF_PRESENT=1` is the **default** in the script — it checks for existing `Mathlib.olean` and skips `lake build`. Our LeanDojo cache has it.

Plan: build rootfs (~1hr) → copy .olean cache into data.ext4 (~10min) → run script (~30min) = **~1hr total vs 2hrs**.

Also: `mathlib_env.olean` pickle — first run saves it automatically. Subsequent snapshot builds load pickle (~5s vs 70s reimport).

---

## 8. Parallelism

**Implemented:** `ReplPool` in `repl_client.py`.

**Option A — Subprocess pool (done):** N `LeanReplClient` processes, all boot in parallel (~70s regardless of N). Thread-safe `queue.Queue` dispatch. OS deduplicates read-only `.olean` pages — N=4 workers ≈ **10–14GB RAM**, not 4×8GB.

```bash
python test_corpus.py --count 100 --workers 4
```

**Option B — Firecracker pool (upgrade path):** Kyle's `build_lean_snapshot_pool.sh` builds N snapshot dirs. Use when: untrusted AI code from multiple agents, clean-state guarantees, production/multi-tenant. Not needed now.

---

## 9. Corpus Test Data — Key Finding

**We were testing against the wrong file.** `_app_data_creater.py` deliberately stripped fields for a web dashboard:

| File | Fields | `open_namespaces`? | `state_before` |
|---|---|---|---|
| `app_network_data.jsonl` (what we used) | `full_name`, `statement`, `proof_text`, `tactics` | **NO — stripped** | **Truncated to 150 chars** |
| `traced_theorems_unified_v2.jsonl` (use this) | All above + `file`, `namespace`, `open_namespaces` | **YES** | Full, untruncated |

**`traced_theorems_unified_v2.jsonl` location:** `E:\LEAN-experiments\00_experiment1\jsons\` (126,792 entries, 54,477 tactic proofs)

**`corpus_code_index.json`:** Built by `00_corpus_to_code.py` from `corpus.jsonl`. Maps `full_name → source_code` for **premises** (definitions used by theorems). 180,907 entries covering full Lean+Mathlib definition space. Not the theorems themselves.

**`open_namespaces` example:**
```json
"open_namespaces": ["Mathlib", "Mathlib.RingTheory", "Mathlib.RingTheory.Polynomial", "Polynomial"]
```
Directly tells us which `open X` statements to emit. **Position data (`line`, `col`) is zeroed for all 126k entries** — LeanDojo tracing limitation, not stripping. Can't walk backward in source file for local helpers.

**Revised enriched context plan:**
```python
enriched = {}
for entry in load_jsonl("traced_theorems_unified_v2.jsonl"):
    if entry["proof_type"] != "tactic": continue
    enriched[entry["full_name"]] = {
        "open_namespaces": entry["open_namespaces"],
        "state_before":    entry["tactics"][0]["state_before"] if entry["tactics"] else "",
        "file":            entry["file"],
        "namespace":       entry["namespace"],
    }
# Save as enriched_context.json (~20MB) — one-time preprocessing
```

**Expected pass rates with traced file:**

| Fix | Rate |
|---|---|
| Current (app_network_data.jsonl, private+namespace) | 20% |
| Switch to traced file + `open_namespaces` | ~43% |
| + `variable` from full `state_before` | ~70% |
| + `open scoped` from symbol scan | ~77% |
| + `noncomputable section` | ~79% |

---

## 10. Corpus Test Results

**Iteration history:**

| Run | Data | Sample | Approach | Pass | Rate |
|---|---|---|---|---|---|
| 1 | compact (seq) | 150 | Naive `theorem NAME` | 5/150 | 3.3% |
| 2 | compact (seq) | 150 | `example` approach (broken) | 3/150 | 2% |
| 3 | compact (seq) | 150 | `private _vt` + namespace wrap | 30/150 | **20%** |
| 4 | compact (seq) | 500 | + `noncomputable section` + `open_namespaces` (no traced file) | 58/500 | 11.6% |
| 5 | **traced (random)** | 500 | + traced file `open_namespaces` + 4 parallel workers | **80/500** | **16%** |

**Run 5 notes:**
- Wall time: **9.3s for 500 checks** (4 workers = ~75ms avg per check)
- Data: `traced_theorems_unified_v2.jsonl` — has full `open_namespaces`, untruncated `state_before`
- Workers started with 4s stagger to avoid `lake env` file lock contention
- Fixed: `select.select` → reader thread (Windows/WSL cross-platform fix)
- Fixed: was sending `import Mathlib` as a command — entry file already imports it → `setup([])`

**Run 5 failure breakdown (420 failures):**

| Error | Count | Cause | Next fix |
|---|---|---|---|
| `failed to synthesize` | 167 | Missing `variable` typeclass decls | Parse `state_before` above `⊢` |
| `expected token` | 95 | Notation / syntax — open scoped missing or wrong | Better symbol scan |
| Other | 75 | Various | — |
| `unknown identifier` / `function expected` | 78 | Still needs more `open` | Already partially fixed |
| `type mismatch` | 5 | Universe elaboration | Complex |

**Why 16% vs 20% (run 3)?** Run 3 was first 150 sequential entries (easier theorems). Run 5 is random across all 54k — includes hard algebra clusters. The `open_namespaces` fix did help (unknown_identifier 45 vs 49, but `expected_token` 95 vs 64 — some regressions from the new open stmts adding conflicting names). Next big unlock: variable reconstruction from `state_before` (167 failures = 40% of all failures).

**Three modes:**

| Mode | Description | Ceiling |
|---|---|---|
| 1 | Re-prove existing Mathlib theorems (corpus test only) | ~90–95% |
| 2 | Complete `sorry` in existing Lean file (main use case) | ~99%+ |
| 3 | Prove novel theorem (new math) | ~100% |

**Three modes:**

| Mode | Description | Ceiling |
|---|---|---|
| 1 | Re-prove existing Mathlib theorems (corpus test only) | ~90–95% |
| 2 | Complete `sorry` in existing Lean file (main use case) | ~99%+ |
| 3 | Prove novel theorem (new math) | ~100% |

---

## 11. Proof Verification Design Decisions

**Name collision fix — always wrap AI submissions:**

```lean
-- Single theorem:
example (n m : ℕ) : n + m = m + n := by omega   -- never collides

-- Multi-lemma block:
namespace ATPCheck_a3f9b2c1
private lemma helper : ... := ...
private theorem main : ... := by exact helper
end ATPCheck_a3f9b2c1
-- `private` → mangled internal name, never collides with Mathlib
```

`example` runs the exact same kernel judgment as `theorem`. Names are labels. Verdict identical.

**Submission rules for ATP loop:**
- Single proof → `example : STATEMENT := PROOF`
- Multi-lemma block → `namespace ATPCheck_<uuid>` wrapping
- Never submit raw AI code without one of these (~20-line change to `lean_runner.py`, not yet done)

**Future — targeted import mode:** REPL that imports only what a theorem needs. Eliminates all collision problems. Enables re-verification of existing proofs, "what if we changed this lemma?" counterfactuals. LeanDojo `sid` branching supports it; need dependency graph per theorem (`corpus_code_index.json` has premises).

---

## Appendix

**Error codes:**

| Code | Meaning | Action |
|---|---|---|
| `state_ref_not_found` | Cached state expired | Re-run with `want_state=true` |
| `state_ref_incompatible` | Different Mathlib snapshot | Regenerate with matching toolchain |
| `limit_timeout_exceeded` | REPL timed out | Reduce `timeout_s` |
| `protocol_mismatch` | Firecracker envelope version mismatch | Rebuild snapshot |
| `protocol_transport_error` | vsock failure | Check Firecracker process |

**SLA targets** (`config/atp_threshold_policy.json`): p95 < 200ms. Kyle's measured baseline: `repl_ms_avg=380ms`, `p95_wall=782ms`, concurrency=4.
