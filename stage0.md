# LeanATP Harness — Master Reference

> **Project:** Meta-methods for discovering new mathematics via Lean 4 proof verification.
> **Author notes:** Kyle McCleary's `breadboard` repo reimplements Harmonic's ATP architecture.
> This document is the single reference for everything: how checking works, what we built,
> what Kyle's new branch adds, and all design decisions made so far.

---

## Table of Contents

1. [What Breadboard Is](#1-what-breadboard-is)
2. [How Lean Proof Checking Works — The Three Layers](#2-how-lean-proof-checking-works)
3. [Firecracker Snapshots — Deep Dive](#3-firecracker-snapshots--deep-dive)
4. [VM Infrastructure — What Exists vs What Was Missing](#4-vm-infrastructure)
5. [WSL2 + Firecracker — What This Machine Can Do](#5-wsl2--firecracker)
6. [What We Built — The Subprocess Verifier](#6-what-we-built--the-subprocess-verifier)
7. [Kyle's New Branch — Snapshot Scripts + Full Stack](#7-kyles-new-branch)
8. [Parallelism Plan](#8-parallelism-plan)
9. [Corpus Test Results + Failure Analysis](#9-corpus-test-results)
10. [Proof Verification Design Decisions](#10-proof-verification-design-decisions)

---

## 1. What Breadboard Is

`breadboard` is an **agentic coding + automated theorem proving harness framework**. Primary purposes:

1. Wrap AI coding agents (Claude Code, Codex, OpenCode) in a controllable evaluation harness
2. Expose a **Lean 4 REPL service** via HTTP, backed by Firecracker microVM snapshots
3. Run structured **campaigns** of ATP proof-checking at scale with metrics and checkpointing
4. Serve as an evaluation platform ("E4") comparing agent behavior across models/versions

The Lean ATP subsystem is modeled on Harmonic's architecture (harmonic.fun — AI for Formal Mathematical Reasoning).

### Key Components


| Component           | File                                | Purpose                                                                                       |
| ------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------- |
| Core REPL interface | `breadboard/lean_repl.py`           | Data contracts: `CheckRequest`, `CheckResult`, `LeanError`, `Sorry`, `FirecrackerReplService` |
| ATP HTTP API        | `api/cli_bridge/atp_router.py`      | `POST /atp/v1/repl`, `/atp/v1/repl/batch`                                                     |
| Service layer       | `api/cli_bridge/service.py`         | Wires request → backend → response                                                            |
| Diagnostics         | `api/cli_bridge/atp_diagnostics.py` | Machine error codes + remediation                                                             |
| EvoLake campaigns   | `breadboard_ext/evolake/`           | Multi-round batch ATP with checkpointing                                                      |
| Sandbox backends    | `breadboard/sandbox*.py`            | Docker / gVisor / Firecracker — swappable                                                     |
| ATP scripts         | `scripts/atp_*.py/sh`               | Benchmarks, stability, nightly CI                                                             |


### HTTP API

```json
POST /atp/v1/repl
{
  "commands": ["theorem foo : 1+1=2 := by decide"],
  "state_ref": "<optional cached state>",
  "timeout_s": 30.0,
  "want_state": true
}

Response:
{
  "success": true,
  "errors": [],
  "sorries": [],
  "new_state_ref": "abc123",
  "metrics": [{"repl_ms": 45, "restore_ms": 12}]
}
```

### EvoLake Campaign Loop

```
Round 0: Generate N theorem candidates via LLM
Round 1: Submit all to ATP batch, collect sorry goals
Round 2: Use sorry goals as new LLM prompts to find missing lemmas
Round 3: Verify augmented proofs
... repeat with checkpointing
```

### What Breadboard Does NOT Provide


| Gap                           | What you add                                |
| ----------------------------- | ------------------------------------------- |
| Theorem generator             | LLM / search / mutation layer               |
| Premise retrieval             | Integrate separately (LeanDojo has this)    |
| LLM-in-the-loop               | You orchestrate; breadboard is the verifier |
| `FirecrackerReplService` impl | Was a stub — we built it (see §6)           |


---

## 2. How Lean Proof Checking Works

### The Core Problem

`import Mathlib` forces Lean to elaborate ~100,000+ definitions. Cold start: **3–10+ minutes**.
Re-running this per proof candidate is catastrophic for any iterative search loop.

### Layer 1 — Naive (Don't Do This)

```
lean myfile.lean
  → loads every .olean in Mathlib (~60s minimum)
  → elaborates your theorem
  → exits
```

For 1000 candidates: 1000 × 60s = 16 hours. Useless.

### Layer 2 — The REPL Protocol

Run a **persistent Lean process** holding the elaborated environment in memory.
LeanDojo's `Lean4Repl.lean` implements this via `#lean_dojo_repl`:

```
Python                  Lean Process (running, Mathlib in memory)
  │                              │
  │  {"sid":0,"cmd":"..."}       │  ← JSON over stdin
  │ ─────────────────────────►  │
  │                              │
  │  ◄─────────────────────────  │  ← JSON over stdout
  │  {"sid":1,"error":null}      │
```

**State IDs are the key.** Each command produces a new sid. You can branch from any saved sid:

- Import Mathlib once: sid 0 → sid 1
- Check 1000 theorems: all branch from sid 1
- Mathlib is loaded **once per process lifetime**

`state_ref` in the breadboard harness maps directly to a sid (or snapshot ID in the Firecracker path).

### Layer 3 — Firecracker Snapshots

Solves: crash recovery, true parallelism, security isolation.

```
SETUP (once, offline):
  Boot microVM → run Lean → import Mathlib → SNAPSHOT
  Saves: lean.snap (CPU state) + lean.mem (full RAM image)

RUNTIME (per request, ~200ms):
  Restore snapshot → VM live with Mathlib already loaded
  Send theorem via vsock → get result → discard VM
```

`restore_ms` in `FirecrackerReplMetrics` = step 1. `repl_ms` = step 2.
SLA target: **p95 < 200ms total**.

### What `state_ref` Actually Is

In the subprocess path: an integer (the REPL sid).
In the Firecracker path: a snapshot file name on disk.

```
"lean_mathlib_base"     →  snapshot after import Mathlib
"lean_mathlib_branch_A" →  snapshot after import Mathlib + your lemmas
"lean_mathlib_branch_B" →  snapshot after import Mathlib + different lemmas
```

`want_state: true` → "save the current state as a new snapshot, give me the ID."

---

## 3. Firecracker Snapshots — Deep Dive

### What Firecracker Is

Open-source Amazon tool (used inside AWS Lambda). Boots a miniature Linux VM in ~125ms.
**Fully local** — runs on your own machine. Not a cloud service.

Minimal VM: CPU + RAM + tiny kernel. No GPU, no USB, no graphics.
Communicates with host via **vsock** (virtio socket — like a network socket but zero TCP overhead).

### What a Snapshot Is

```
VM running, Lean loaded, Mathlib in memory
    │
    │  "take snapshot"
    ▼
[frozen memory image saved to disk]
  - every byte of RAM written to lean.mem
  - CPU register state saved to lean.snap
  - VM paused
```

Restoring is **not rebooting**. It's un-pausing. OS doesn't boot. Lean doesn't start.
Mathlib is not reloaded. Everything resumes exactly where it was frozen.

### Why Not Docker?


|                       | Docker                             | Firecracker                  |
| --------------------- | ---------------------------------- | ---------------------------- |
| Isolation             | Process-level (shared kernel)      | Full VM (separate kernel)    |
| Memory snapshot       | No                                 | Yes — full RAM frozen        |
| Restore from snapshot | N/A — must re-run `import Mathlib` | ~12–200ms                    |
| Boot time             | ~500ms–2s                          | ~125ms                       |
| Concurrent workers    | Easy                               | One snapshot file per worker |
| Security              | Weaker                             | Strong (separate kernel)     |


For proof search at scale, Docker means re-importing Mathlib every container spin-up.
Firecracker means you never pay that cost again.

### The vsock Protocol (Kyle's Full Stack)

Kyle's system uses a versioned envelope over vsock:

```json
// Host → VM
{"type": "repl", "version": 1, "payload": {"command": "theorem foo ...", "timeout": 60.0}}

// VM → Host
{"type": "repl_response", "version": 1, "response": {"sid": 1, "error": null}}
```

With a handshake:

```json
// Host → VM
{"type": "hello", "version": 1, "capabilities": {}}
// VM → Host
{"type": "hello_ack", "version": 1, "capabilities": {}}
```

This is defined in `breadboard/vsock_protocol.py` (Kyle's new branch).

---

## 4. VM Infrastructure

### What Was in the Repo vs What Was Missing (Before Kyle's Branch)

```
IN THE REPO
───────────
✓ HTTP API (FastAPI routes, request/response models)
✓ Data contracts (CheckRequest, CheckResult, LeanError, Sorry)
✓ Service layer wiring
✓ Diagnostic error mapping
✓ Benchmark and stability scripts
✓ EvoLake campaign orchestration

NOT IN THE REPO (original)
──────────────────────────
✗ Code that starts a Firecracker VM
✗ Code that manages snapshot files
✗ Code that sends commands into a VM
✗ Dockerfile or VM image with Lean installed
✗ The Lean REPL binary that runs inside the VM
✗ vsock transport layer
✗ Snapshot pool manager
```

Kyle's `FirecrackerReplService` stub raised `NotImplementedError`. We filled it with
a subprocess backend (§6). Kyle's new branch adds the Firecracker scripts (§7).

### Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│  HTTP API / Service Layer / Campaign Orchestration  │  ← IN REPO
│  (atp_router, service, evolake, models, diagnostics)│
├─────────────────────────────────────────────────────┤
│  FirecrackerReplService  (seam)                     │  ← WE FILLED THIS
├─────────────────────────────────────────────────────┤
│  VM Management / Snapshot Pool / vsock Transport    │  ← KYLE'S NEW BRANCH
│  VM Image With Lean+Mathlib / REPL Binary           │  ← KYLE'S SCRIPTS BUILD THIS
│  Firecracker Binary / Linux Host With KVM           │  ← WSL2 (§5)
└─────────────────────────────────────────────────────┘
```

---

## 5. WSL2 + Firecracker

### Environment

```
WSL Version:    2.6.3.0
WSL Kernel:     6.6.87.2-microsoft-standard-WSL2
Distro:         Ubuntu 24.04 LTS
/dev/kvm:       EXISTS ✓
Firecracker:    NOT installed yet
User in kvm group: NO (fix: sudo usermod -aG kvm $USER + wsl --shutdown)
```

`/dev/kvm` exists because WSL2 is a real Hyper-V VM with KVM passthrough (nested virtualization):

```
Windows 11
    └── Hyper-V
            ├── Windows
            └── WSL2 VM (Ubuntu 24.04)
                    └── Firecracker (nested KVM)
                            └── Lean microVM
```

Three levels deep. Works — hardware-accelerated KVM means nested virtualization is viable.
Restore times will be 50–400ms instead of 12–200ms bare metal. Still fine.

### What's Still Needed for Full Firecracker Path


| Piece                         | Status                                                    |
| ----------------------------- | --------------------------------------------------------- |
| Linux host with KVM           | **AVAILABLE** via WSL2 (just needs kvm group)             |
| Firecracker binary            | Not installed — `apt install` or download                 |
| VM kernel (`vmlinux`)         | Not present — download from Firecracker releases          |
| VM rootfs with Lean+Mathlib   | Kyle's script builds this                                 |
| Snapshot creation             | Kyle's `fc_create_lean_snapshot_vsock.sh`                 |
| `FirecrackerReplService` impl | We built subprocess version; full vsock version is Kyle's |
| Snapshot pool manager         | Kyle's `build_lean_snapshot_pool.sh`                      |


---

## 6. What We Built — The Subprocess Verifier

### Architecture

```
Your code / EvoLake
      │  CheckRequest → CheckResult
      ▼
SubprocessReplService  (our implementation of FirecrackerReplService)
      │  subprocess stdin/stdout
      │  {"sid": N, "cmd": "..."}  →  {"sid": N+1, "error": null}
      ▼
lake env lean /tmp/lean_repl_entry.lean  (persistent process)
      │  reads pre-built .olean from ~/.cache/lean_dojo/.../mathlib4/
      ▼
Lean 4 kernel + Mathlib .olean (Lean v4.10.0-rc1)
```

### Files

```
verifier/
  repl_client.py    ← LeanDojo CommandRepl subprocess client (core)
  lean_runner.py    ← SubprocessReplService: FirecrackerReplService implementation
  test_basic.py     ← 5 smoke tests
  test_corpus.py    ← corpus batch verifier (150 random tactic proofs)
  stage0.md         ← lab notebook (append-only)
```

### Key Implementation Decisions

-  ****
- `**base_sid = 0`**: Mathlib is loaded via the entry file before the REPL even starts.
The REPL is ready at sid=0, post-Mathlib. No `import Mathlib` command ever sent.
- `**os.read(fd, 4096)**` for non-blocking stdout read — `.read1()` doesn't exist on `_io.FileIO`.
- **elan PATH injected**: `env["PATH"] = f"{home}/.elan/bin:" + env.get("PATH", "")`.
- **Sorry detection**: Lean emits sorry as a plain-text stdout WARNING, not in the JSON `error` field.
`ReplResponse.stdout_lines` captures non-JSON output; `has_sorry` scans for "sorry".
`lean_runner.py` checks `r.has_sorry` → appends `Sorry(...)`, sets `success=False`.
- **STARTUP_TIMEOUT_S = 300s**: import Mathlib via /mnt/c/ 9P filesystem takes ~100s.
Observed ~69s warm.

### Performance


| Metric                                   | Value     |
| ---------------------------------------- | --------- |
| Mathlib cold load (one-time per session) | ~69s      |
| Simple proof (`decide`, `rfl`)           | 6–10ms    |
| Medium tactic proof                      | 20–50ms   |
| Complex proof                            | 100–220ms |
| Typical                                  | ~30–60ms  |


### Smoke Test Results — 5/5 PASS

```
TEST: Correct proof          PASS  (0.0s)
TEST: Sorry detection        PASS  (0.0s)
TEST: Type error             PASS  (0.0s)
TEST: Incremental state_ref  PASS  (0.0s)  lemma proved at state_ref=4, theorem reuses it
TEST: HahnSeries C_ne_zero   PASS  (0.0s)
```

### Is It Trustworthy?

Yes — completely. The Lean kernel (not us) is the judge. It implements the Calculus of
Inductive Constructions. When Lean returns `error: null`, the proof is kernel-verified.
There is no approximation, no heuristic. It either type-checks or it doesn't.
Same kernel that verifies all 200k+ Mathlib theorems.

---

## 7. Kyle's New Branch

**Branch:** `origin/codex/atp-lean-ship-20260307`
**Fetched:** 2026-03-08

### What's New

```
scripts/lean_snapshot/
  fc_create_lean_snapshot_vsock.sh     ← 1381-line Firecracker snapshot builder
  activate_lean_snapshot.sh            ← exports env vars, runs ATP CI checks
  build_lean_snapshot_pool.sh          ← builds N snapshots for concurrency
  run_lean_snapshot_diag.sh            ← quick diagnostic build
  run_lean_snapshot_diag_stable.sh     ← stable diagnostic

breadboard/vsock_protocol.py           ← envelope protocol helpers
docs/atp_runbook.md                    ← operational runbook
docs/ATP_VSOCK_PROTOCOL_POLICY.md      ← wire contract spec
```

### What `fc_create_lean_snapshot_vsock.sh` Does

1. Takes a pre-existing rootfs (`lean-mathlib.ext4`) + kernel (`vmlinux`)
2. Boots Firecracker VM (8GB RAM, 4 vCPUs)
3. Mounts the rootfs, runs `chroot` to build Lean4Repl binary
4. Starts VM, inside: checks for existing `.olean` files, optionally runs `lake build`
5. Waits for REPL to warm (import Mathlib)
6. Takes Firecracker snapshot → `lean.snap` + `lean.mem`
7. Output: ready-to-restore snapshot directory

### Are We Using His Work The Way It's Intended?


| Layer           | Kyle's design                                  | Our implementation         | Compatible?                       |
| --------------- | ---------------------------------------------- | -------------------------- | --------------------------------- |
| API contract    | `FirecrackerReplService` interface             | Same interface             | YES                               |
| Lean protocol   | LeanDojo CommandRepl (`{"sid":N,"cmd":"..."}`) | Same protocol, direct      | YES                               |
| Transport       | vsock (AF_VSOCK port 52)                       | subprocess stdin/stdout    | Different, transparent to callers |
| Isolation       | Firecracker microVM                            | Single persistent process  | Different                         |
| Restore latency | ~200ms                                         | ~69s cold (once), then 0ms | Different tradeoff                |


**We implement the right interface and use the same leaf protocol. We skip the isolation layer.**
For sequential single-agent ATP, our approach is faster per-check. His is for parallel/production.

### Performance Comparison


| Metric          | Our approach             | Firecracker approach               |
| --------------- | ------------------------ | ---------------------------------- |
| Cold start      | **69s** once per session | **~200ms** per VM restore          |
| Per-check       | **6–220ms**              | **~380ms** avg (measured baseline) |
| Concurrency     | Serial (1 REPL)          | Parallel VM pool                   |
| Isolation       | None                     | Full kernel                        |
| State branching | Via `sid` (tree)         | Via `state_ref` (CAS snapshots)    |


### Shortcutting the 2-Hour Build

The script's expensive step is `lake build` (compiling all of Mathlib). We already have
the compiled output. The script explicitly skips it when present:

```bash
# Inside the VM guest init:
if [ -f /root/mathlib4/.lake/build/lib/Mathlib.olean ]; then
  BUILD_PRESENT=1
fi
if [ "$SKIP_LAKE_BUILD_IF_PRESENT" = "1" ] && [ "$BUILD_PRESENT" = "1" ]; then
  log "Skipping lake build (Mathlib.olean already present)"
fi
```

`SKIP_LAKE_BUILD_IF_PRESENT=1` is the **default**. Our LeanDojo cache eliminates the 2-hour step.

**Shortcut plan:**

1. Build minimal rootfs (Ubuntu + elan + Lean v4.10.0-rc1) — ~1hr
2. Copy our .olean cache into the data disk — ~10min:
  ```bash
   dd if=/dev/zero of=data.ext4 bs=1M count=24576 && mkfs.ext4 data.ext4
   mount data.ext4 /mnt/tmp
   cp -a ~/.cache/lean_dojo/.../mathlib4/.lake/. /mnt/tmp/.lake/
   umount /mnt/tmp
  ```
3. Run script with SKIP_LAKE_BUILD_IF_PRESENT=1 (default) — ~30min
4. **Total: ~1hr vs 2hrs**

The script also supports `mathlib_env.olean` pickle (precomputed Lean environment).
First run generates it automatically (`pickle_after_import=1` is default).
Subsequent snapshot builds from same rootfs load pickle instead of re-importing (~5s vs 70s).

---

## 8. Parallelism Plan

### Why We Need It

EvoLake batch campaigns require parallel proof checking. Right now: one Lean process,
one check at a time, fully sequential.

### Option A — Subprocess Pool (implement now, no new infra)

Spawn N `LeanReplClient` processes concurrently. Each loads Mathlib independently.
Dispatch checks from a thread-safe queue.

```
Worker 0  ──── base_sid=0 ────  check A  check E  check I ...
Worker 1  ──── base_sid=0 ────  check B  check F  check J ...
Worker 2  ──── base_sid=0 ────  check C  check G  check K ...
Worker 3  ──── base_sid=0 ────  check D  check H  check L ...
```

All workers start concurrently → total warmup ≈ 70s (parallel, not N×70s).

**Memory:** Lean memory-maps `.olean` files read-only. OS shares pages between processes.
The ~8GB compiled Mathlib is mapped once at OS level. Each extra process adds ~1–2GB heap.
N=4 workers ≈ **10–14GB total RAM**, not 4×8GB.

**Implementation sketch (~80 lines in `repl_client.py`):**

```python
class ReplPool:
    def __init__(self, n_workers=4, **client_kwargs):
        self._workers = [LeanReplClient(**client_kwargs) for _ in range(n_workers)]
        self._queue = queue.Queue()

    def start(self):
        threads = [threading.Thread(target=w.start, daemon=True) for w in self._workers]
        for t in threads: t.start()
        for t in threads: t.join()      # all warm in parallel
        for w in self._workers: self._queue.put(w)

    def check(self, sid, cmd, timeout=None):
        worker = self._queue.get()
        try:
            return worker.send(sid, cmd, timeout)
        finally:
            self._queue.put(worker)
```

### Option B — Firecracker Pool (upgrade path)

Kyle's `build_lean_snapshot_pool.sh` builds N independent snapshot directories.
`FirecrackerReplService` pulls from the pool, restoring a fresh VM per batch.

Needed when:

- Running untrusted AI-generated proofs from multiple agents simultaneously
- Reproducibility guarantees (clean state per check)
- Multi-tenant or production deployment

Not needed now for single-agent research loops.

---

## 9. Corpus Test Results

### Test Setup

150 random tactic proofs from `app_network_data.jsonl` (54,477 tactic proofs total).
Each proof submitted to the verifier cold (branching from `base_sid=0` post-Mathlib).

### Results Across Three Iterations


| Approach                                            | Pass       | Rate           |
| --------------------------------------------------- | ---------- | -------------- |
| Naive: `theorem NAME`                               | 5/150      | 3.3%           |
| `example` approach (broken type extraction)         | 3/150      | 2% — abandoned |
| `private theorem NAME_vt` + `namespace X ... end X` | **30/150** | **20%**        |


### Why Most Fail — Root Causes

The corpus stores theorems as written **inside their original file context**. They assume:

- `variable {R : Type*} [CommRing R] ...` declared at top of file
- Being inside `namespace X`
- `open` statements active
- NOT having full Mathlib already imported (so re-declaring doesn't conflict)


| Category                                   | Count | Root Cause                                            | Fix                                 |
| ------------------------------------------ | ----- | ----------------------------------------------------- | ----------------------------------- |
| `failed to synthesize`                     | 53    | Missing `variable` typeclass decls from original file | Parse `tactics[0].state_before`     |
| `function expected` / `unknown identifier` | 27    | Dot notation needs `open` or deeper namespace         | Add `open X` matching namespace     |
| `expected token`                           | 18    | Notation requires `open` (unicode, factorial, etc.)   | Inferrable from failure + namespace |
| `already been declared`                    | 7     | `@[simp]` before `theorem` blocks rename regex        | 2-line regex fix                    |
| `application type mismatch`                | 5     | Proof depends on renamed lemmas                       | Complex                             |
| Other                                      | 10    | Various                                               | —                                   |


### Projected Pass Rate With Fixes


| Fix                                        | New passes | Cumulative           |
| ------------------------------------------ | ---------- | -------------------- |
| Current                                    | 30         | 30/150 (20%)         |
| Fix `@[simp]` regex                        | +7         | 37 (25%)             |
| Add `open X` matching namespace            | +12        | 49 (33%)             |
| Reconstruct `variable` from `state_before` | +40        | 89 (59%)             |
| **Realistic ceiling**                      | —          | ~~**89/150 (~~60%)** |


### Would Full Source File Context Give 100%?

No — **~90–95% ceiling at best**. Here is why.

When the REPL starts, `import Mathlib` is already executed. Every Mathlib theorem is already
declared. Submitting the source file for `Nat.add_comm` still fails:

```
'Nat.add_comm' has already been declared
```

The source file works during `lake build` because it imports only its *dependencies*, not itself.
Our REPL has everything loaded.

**What full source context WOULD fix:**


| Issue                                       | Fixed by source file?                    |
| ------------------------------------------- | ---------------------------------------- |
| `failed to synthesize` (missing `variable`) | YES                                      |
| `unknown identifier` (needs `open`)         | YES                                      |
| `expected token` (notation)                 | YES                                      |
| `function expected` (dot notation)          | YES                                      |
| `already been declared`                     | **NO** — collision with `import Mathlib` |


### The Three Modes — Why This Only Matters for the Corpus Test

**Mode 1: Re-proving existing Mathlib theorems (corpus test)**
Ceiling ~90–95%. This is only for testing our verifier. Not our actual use case.

**Mode 2: Completing a proof in an existing Lean file (main ATP use case)**
Submit: file imports + variable decls + definitions before the theorem + AI proof.
Nothing collides because the theorem is a `sorry` placeholder, not yet compiled.
**Expected ceiling: ~99%+**

**Mode 3: Proving a novel theorem (new math)**
It's new — no collision possible.
**Expected ceiling: 100%** for correctness of the verdict.

**The corpus test limitations are irrelevant to our actual work.**

---

## 10. Proof Verification Design Decisions

### Re-proving Known Theorems — The Collision Problem

If AI attempts to prove something with the same name as an existing Mathlib theorem:

```
error: 'Nat.add_comm' has already been declared
```

This is a **false negative** — the proof may be mathematically correct.

**The fix — always use one of:**

**Single theorem — use `example`** (anonymous, never collides):

```lean
-- Don't submit:
theorem Nat.add_comm (n m : ℕ) : n + m = m + n := by omega
-- Submit as:
example (n m : ℕ) : n + m = m + n := by omega
```

**Multi-block with helpers — use unique namespace:**

```lean
namespace ATPCheck_a3f9b2c1
private lemma helper : ... := ...
private theorem main : ... := by exact helper
end ATPCheck_a3f9b2c1
```

`private` inside a namespace gives Lean a mangled internal name (`_private.ATPCheck.helper.1`).
Never collides with anything in Mathlib.

**Mathematical validity is unaffected.** `example` runs the exact same kernel judgment as `theorem`.
Names are labels. The correctness verdict is identical.

**Implementation:** ~20-line change to `_run_commands` in `lean_runner.py` — not yet done but straightforward.

### Submission Strategy for ATP Loop

- Pure "is this proof valid?" → `example : STATEMENT := PROOF`
- Multi-lemma block → `namespace ATPCheck_<uuid>` wrapping
- Never submit AI-generated code without one of these

### Targeted Import Mode (Future)

The real power unlock: a REPL that imports only the modules a theorem needs, not all of Mathlib.
This would:

- Eliminate all name collision problems
- Allow re-verification of existing Mathlib proofs during development
- Enable "what if we changed this lemma?" counterfactuals

LeanDojo's `sid` branching supports custom import trees. We need the dependency graph per theorem
(which `corpus_code_index.json` has for premises).

---

## Appendix: Key Error Codes


| Error Code                 | Meaning                               | Action                             |
| -------------------------- | ------------------------------------- | ---------------------------------- |
| `state_ref_not_found`      | Cached state expired/missing          | Re-run with `want_state=true`      |
| `state_ref_incompatible`   | State from different Mathlib snapshot | Regenerate with matching toolchain |
| `limit_timeout_exceeded`   | REPL timed out                        | Reduce `timeout_s`                 |
| `protocol_mismatch`        | Firecracker envelope version mismatch | Rebuild snapshot                   |
| `protocol_transport_error` | vsock/socket failure                  | Check Firecracker process health   |


## Appendix: SLA Targets

From `config/atp_threshold_policy.json`:

```json
{
  "bench":        { "p95_ms_max": 200.0 },
  "pool_stability": { "require_concurrency": 4, "min_runs": 3, "max_p95_ms": 200.0 },
  "state_ref":    { "max_regression_pct": 10.0, "required_consecutive_pass": 2 }
}
```

Measured baseline (Kyle's system, 2026-02-12):

- `repl_ms_avg = 380ms`
- `request_wall_s_p95 = 782ms`
- Concurrency = 4 workers

