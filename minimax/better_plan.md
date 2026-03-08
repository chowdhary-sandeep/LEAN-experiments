# Mode 2 Verification — Better Plan (Start Fresh)

**For:** minimax 2.5 agent
**Working directory:** `E:\LeanATP Harness\minimax\` (WSL path: `/mnt/e/LeanATP Harness/minimax/`)
**Goal:** Implement Mode 2 source-prefix verification; target ≥99% pass rate vs 84-90% in Mode 1
**Start from scratch** — delete `test_corpus_mode2.py` and write a clean new implementation.

---

## STOP. Read This First: The 60-Second Cold-Start Trap

**You are almost certainly wasting most of your time restarting Lean.**

Every time you run `python3 test_corpus_mode2.py --count 10`, Lean loads Mathlib from scratch.
That takes **~70 seconds**. Then you run 10 checks taking ~5 seconds total. Then you stop.
Your utilisation is 5/75 = **6%**. The rest is cold start.

**The fix is trivial:** run with a larger batch.

```bash
# WRONG — never do this during development
python3 test_corpus_mode2.py --count 10 --workers 1    # 70s startup, 5s work, then die

# RIGHT — 70s startup is paid ONCE, then 500 checks run
python3 test_corpus_mode2.py --count 500 --workers 4   # 70s startup total, ~300s of work
```

**The existing `ReplPool` in `repl_client.py` already implements "memory freeze":**
- Workers start Lean once, let it load Mathlib (~70s), then stay alive
- Every `pool.map()` call branches from `base_sid=0` (the post-Mathlib snapshot state)
- No restart between checks — you pay 70s exactly once per worker, not once per run
- With 4 workers: 4 × 70s = 280s cold start, then thousands of checks at ~50ms each

This is Lean's equivalent of Kyle's Firecracker snapshot approach, implemented in pure Python.
If you want Firecracker for sub-second process restarts (not needed here), see
`E:\LeanATP Harness\breadboard\scripts\atp_firecracker_ci.sh` — but only AFTER you have
Mode 2 working correctly. Don't optimise what isn't the bottleneck.

**Golden rule: always `--count 500 --workers 4`. Never test with count < 100.**

---

## What Already Works (Don't Throw Away)

The existing `repl_client.py` in this directory is correct. Don't touch it.

From `test_corpus_mode2.py`, these functions are correct and working:
- `get_source()` — file reading with cache
- `find_theorem_bounds()` — finds start/end line of a theorem in source
- Data loading (`load_proofs()`)
- `_classify()` result handler
- The overall `run_mode2()` structure with `pool.map()`

These functions have bugs or are incomplete (rewrite them):
- `extract_private_defs()` — misses multi-line defs with `where` clauses
- `extract_variables()` — doesn't handle section nesting (variable in `section A` ≠ global)
- `build_mode2_command()` — statement renaming is subtly wrong, see below

---

## The Core Architectural Problem With Current Mode 2

The current code extracts individual elements (opens, variables, universes, private_defs)
and reassembles them globally. This is **wrong** because Lean source files use nested sections:

```lean
namespace Mathlib.Topology.Basic

section TopologicalSpace
variable {α : Type*} [TopologicalSpace α]

-- variable [TopologicalSpace α] is ONLY in scope INSIDE this section
-- theorem Foo uses it, and is also INSIDE this section
theorem Foo : ... := ...

end TopologicalSpace
end Mathlib.Topology.Basic
```

When you extract `variable {α : Type*} [TopologicalSpace α]` and emit it globally
(outside any section), Lean may reject it or emit it with different universe constraints.
The section scoping is the reason many `failed_to_synthesize` errors persist.

**The correct approach: Stripped Source Prefix.**

Instead of extracting elements and reassembling, take the entire source file up to the
theorem's line, and strip out only the declarations that would conflict with `import Mathlib`.

---

## The Stripped Prefix Approach (Implement This)

### What to KEEP from the prefix:
- `section` / `end` lines → preserves scoping
- `namespace` / `end` lines → preserves namespace context
- `open X` statements → preserves name resolution
- `variable (...)` / `variable [...]` lines → preserves typeclass context
- `universe u v w` lines → preserves universe level names
- `local notation` / `local infixl` etc. → preserves local syntax
- `private def` / `private abbrev` / `private class` / `private structure` → helper defs
- `set_option ...` lines → preserves options
- Comments → fine to keep

### What to STRIP from the prefix:
- `import` statements → `import Mathlib` already done
- Public `theorem` / `lemma` → already in Mathlib, would be "already declared"
- Public `def` / `instance` / `class` / `structure` / `abbrev` / `inductive` → same
- `#check` / `#eval` / `#print` / `#lint` commands → not valid in REPL command context
- Lines with `@[...] theorem` / `@[...] def` etc. → same as above
- `protected theorem` / `noncomputable def` etc. → same

### What the final command looks like:

```
noncomputable section
set_option quotPrecheck false

[stripped prefix verbatim — sections, opens, variables, private defs, etc.]

private theorem short_name_vt [params from statement] :=
  [proof]

end [all open sections/namespaces, innermost first]
end  ← the noncomputable section
```

Note: you must close all sections/namespaces that were opened in the prefix.
Track a stack of `section`/`namespace` names and emit matching `end` statements.

---

## Implementation: Step by Step

### Step 0: File paths

```python
CORPUS_FILE = Path("/mnt/e/LEAN-experiments/00_experiment1/jsons/traced_theorems_unified_v2.jsonl")
MATHLIB_ROOT = Path("/mnt/e/LEAN-experiments/00_experiment1/gitpython-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4")
RESULTS_DIR  = Path("/mnt/e/LeanATP Harness/artifacts")
```

Always check both paths:
```python
for p in [CORPUS_FILE, MATHLIB_ROOT]:
    assert p.exists(), f"Missing: {p}"
```

### Step 1: Find theorem line in source file

Keep the existing `find_theorem_bounds()`. It works.
One fix: the short_name lookup should also try the unqualified last segment AND handle
theorems that are prefixed with their namespace (e.g., `theorem Foo.bar` inside `namespace Foo`).

```python
def find_theorem_bounds(source: str, full_name: str) -> Optional[tuple[int, int]]:
    short_name = full_name.split(".")[-1]
    lines = source.splitlines()
    # Try exact short name first, then namespace-relative names
    names_to_try = [short_name]
    parts = full_name.split(".")
    if len(parts) >= 2:
        names_to_try.append(parts[-2] + "." + parts[-1])  # e.g. "Foo.bar"

    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("--") or stripped.startswith("/-"):
            continue
        for name in names_to_try:
            pat = rf'(?:theorem|lemma)\s+{re.escape(name)}\b'
            if re.search(pat, stripped):
                end = _find_decl_end(lines, i)
                return (i, end)   # 0-indexed
    return None
```

```python
def _find_decl_end(lines: list[str], start: int) -> int:
    """Find the line index where the declaration header ends (has :=  or  where  or  by)."""
    depth = 0
    for j in range(start, min(start + 50, len(lines))):
        line = lines[j]
        depth += line.count("(") + line.count("{") + line.count("[")
        depth -= line.count(")") + line.count("}") + line.count("]")
        if depth <= 0:
            if re.search(r':=\s*$|:=\s*by\b|\bwhere\b', line):
                return j
            if ":=" in line and depth <= 0:
                return j
    return start + 5
```

### Step 2: Build stripped prefix

```python
# Patterns for lines to strip (conflict with import Mathlib)
_STRIP_PUBLIC_DECL = re.compile(
    r'^(?:@\[.*?\]\s*)*'                      # optional attributes
    r'(?:private\s+)?'                         # NOT private — keep private defs
    r'(?:noncomputable\s+)?(?:protected\s+)?'  # modifiers
    r'(?:theorem|lemma|def|instance|class|structure|abbrev|inductive|'
    r'mutual|opaque)\s+'
)
_KEEP_PRIVATE_DECL = re.compile(
    r'^private\s+(?:def|abbrev|class|structure|inductive)\s+'
)
_STRIP_IMPORT = re.compile(r'^import\s+')
_STRIP_COMMAND = re.compile(r'^#(?:check|eval|print|lint|synth)\b')

def strip_prefix_for_repl(lines: list[str]) -> list[str]:
    """
    Take source lines and remove declarations that would conflict with
    `import Mathlib` already being loaded.
    Returns lines suitable for embedding in a REPL noncomputable section.
    """
    result = []
    in_block_comment = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Block comment tracking
        if not in_block_comment:
            if stripped.startswith("/-"):
                opens = stripped.count("/-")
                closes = stripped.count("-/")
                if opens > closes:
                    in_block_comment = True
                result.append(line)
                i += 1
                continue
        else:
            result.append(line)
            if "-/" in stripped:
                in_block_comment = False
            i += 1
            continue

        # Definitely strip these
        if _STRIP_IMPORT.match(stripped) or _STRIP_COMMAND.match(stripped):
            i += 1
            continue

        # Skip public declarations (but NOT private defs)
        if _STRIP_PUBLIC_DECL.match(stripped) and not _KEEP_PRIVATE_DECL.match(stripped):
            # Skip this line and all indented continuation lines
            i += 1
            while i < len(lines) and lines[i][0:1] in (" ", "\t"):
                i += 1
            continue

        result.append(line)
        i += 1

    return result
```

### Step 3: Track namespace/section stack to close them

```python
def get_open_stack(lines: list[str]) -> list[str]:
    """
    Walk the prefix lines and return the stack of open namespace/section names,
    innermost last. Used to emit matching `end` statements.
    """
    stack = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        m_ns = re.match(r'^namespace\s+(\S+)', stripped)
        m_sec = re.match(r'^section\s+(\S*)', stripped)
        m_end = re.match(r'^end\s*(\S*)', stripped)
        if m_ns:
            stack.append(("namespace", m_ns.group(1)))
        elif m_sec:
            name = m_sec.group(1) or "_anon"
            stack.append(("section", name))
        elif m_end:
            name = m_end.group(1)
            # pop matching entry from stack
            for k in range(len(stack) - 1, -1, -1):
                if name == "" or stack[k][1] == name:
                    stack.pop(k)
                    break
    return stack
```

### Step 4: Rename the theorem

This is the trickiest part. The corpus `statement` field contains the FULL theorem declaration
with its original name. We need to:

1. Remove `protected`, `noncomputable` modifiers
2. Change `theorem original_name` → `private theorem short_name_vt`
3. Handle `@[attr]` attribute lines before the theorem keyword

```python
def rename_theorem(statement: str, full_name: str) -> str:
    """
    Replace the theorem/lemma name with `private theorem {short_name}_vt`.
    Handles attributes on the preceding line, and strips noncomputable/protected.
    """
    short = full_name.split(".")[-1]
    new_name = f"{short}_vt"

    # Strip modifiers and rename
    _mods = r'(?:noncomputable\s+|protected\s+)*'
    stmt = re.sub(
        rf'^{_mods}(?:theorem|lemma)\s+\S+',
        f'private theorem {new_name}',
        statement.strip(),
        count=1,
    )
    # Handle @[attr]\ntheorem ... pattern
    stmt = re.sub(
        rf'(^@\[.*?\]\n?){_mods}(?:theorem|lemma)\s+\S+',
        rf'\1private theorem {new_name}',
        stmt, count=1, flags=re.MULTILINE,
    )
    return stmt
```

### Step 5: Build the full command

```python
def build_mode2_command(entry: dict) -> Optional[str]:
    full_name = entry.get("full_name", "")
    statement = (entry.get("statement") or "").strip()
    proof_text = (entry.get("proof_text") or "").strip()

    if not statement or not proof_text:
        return None

    # Strip #adaptation_note lines
    proof_text = re.sub(r'^\s*#adaptation_note\b[^\n]*\n?', '', proof_text, flags=re.MULTILINE)

    file_rel = entry.get("file", "").replace("\\", "/")
    if not file_rel:
        return None

    source_path = MATHLIB_ROOT / file_rel
    if not source_path.exists():
        return None

    source = source_path.read_text(encoding="utf-8")
    bounds = find_theorem_bounds(source, full_name)
    if not bounds:
        return None

    start_idx, _end_idx = bounds
    prefix_lines = source.splitlines()[:start_idx]   # everything BEFORE the theorem line

    stripped = strip_prefix_for_repl(prefix_lines)
    open_stack = get_open_stack(prefix_lines)   # what's still open at theorem position

    stmt = rename_theorem(statement, full_name)
    body = f"{stmt}\n{proof_text}" if stmt.rstrip().endswith(":=") else f"{stmt} :=\n{proof_text}"

    cmd = ["noncomputable section", "set_option quotPrecheck false"]
    cmd += stripped                             # verbatim stripped prefix
    cmd += [body]                               # renamed theorem with proof
    # Close everything that was open at the theorem's position
    for kind, name in reversed(open_stack):
        cmd.append(f"end {name}")
    cmd.append("end")  # close noncomputable section

    return "\n".join(cmd)
```

---

## Step 6: Run Your First Real Test

```bash
cd '/mnt/e/LeanATP Harness/minimax'

# Quick smoke test (10 theorems, 1 worker — only to check for Python errors, not perf)
python3 -u test_corpus_mode2.py --count 10 --workers 1 2>&1 | head -40

# Real test (500 theorems, 4 workers — always use this for actual results)
python3 -u test_corpus_mode2.py --count 500 --workers 4 2>&1 | tee /tmp/mode2_run1.log

# Compare vs Mode 1 on same slice
cd '/mnt/e/LeanATP Harness'
python3 -u verifier/test_corpus.py --count 500 --workers 4 2>&1 | tee /tmp/mode1_run1.log
```

Save results to `artifacts/mode2_results.json`.

---

## Expected Results and How to Interpret Them

| Scenario | What it means |
|----------|--------------|
| Mode 2 ≥ 95% | Success — stripped prefix approach works |
| Mode 2 ~ 90% (same as Mode 1) | Stripped prefix isn't helping; source file parsing bug |
| Mode 2 < Mode 1 | You're breaking previously-working theorems; check for extra `end` statements |
| `already been declared` errors | A public def/instance slipped through the strip filter |
| `unknown namespace` errors | Namespace stack tracking is wrong |
| `unknown identifier` errors | Private def not being captured; check strip_prefix_for_repl |

If you get many `already been declared` errors: your `_STRIP_PUBLIC_DECL` regex is
not matching some declarations. Print the raw lines that cause them and fix the regex.

If Mode 2 = Mode 1 exactly: `find_theorem_bounds` is failing for most theorems
(returning None), so you're probably falling back to... nothing. Check skip counts.

---

## Debugging: Check the Generated Commands

Add a `--debug` flag that prints the full generated command for the first N theorems:

```python
if args.debug:
    for entry, cmd in jobs[:3]:
        print(f"\n{'='*60}")
        print(f"THEOREM: {entry['full_name']}")
        print(f"{'─'*60}")
        print(cmd[:3000])
```

Look for:
- Is the stripped prefix reasonable? (opens, variables, sections — no big theorem bodies)
- Is the theorem renamed correctly? (`private theorem foo_vt`)
- Are all `namespace`/`section` blocks closed?

---

## Memory Freeze / Firecracker: What You Actually Need

**For Mode 2 development: nothing special.** The existing `ReplPool` in `repl_client.py`
already does the right thing. Lean loads Mathlib once per worker (~70s), then all subsequent
checks branch from `base_sid=0` without restarting. This is exactly the "memory freeze"
pattern — the loaded Lean state is frozen and shared across all checks.

**For Firecracker (optional, after Mode 2 works):**

Kyle's Firecracker infrastructure is in `E:\LeanATP Harness\breadboard\scripts\`.
It creates a KVM snapshot of the Lean process after `import Mathlib` and restores it
for new sessions in <1s instead of 70s. This is useful when you need a truly fresh
Lean environment for each check (no `sid` branching possible), such as for untrusted
user-submitted proofs.

To use it you need:
1. Actual Firecracker snapshot files (not in repo)
2. KVM access (`/dev/kvm` exists on this machine — `ls -la /dev/kvm` to verify)
3. Set env vars: `FIRECRACKER_SNAPSHOT`, `FIRECRACKER_SNAPSHOT_MEM`, `FIRECRACKER_SNAPSHOT_VSOCK`, `FIRECRACKER_ROOTFS`
4. Use `FirecrackerReplClient` from `breadboard/lean_repl.py` instead of `LeanReplClient`

**Skip Firecracker for now.** Solve Mode 2 correctness first. Once Mode 2 hits ≥95%,
copy the working code back to `verifier/test_corpus.py` in the parent directory and
note the improvement there.

---

## Repository Layout

```
E:\LeanATP Harness\
├── verifier/
│   ├── repl_client.py          ← The working REPL pool (copy this, don't modify)
│   ├── test_corpus.py          ← Mode 1 implementation (84-90% pass rate)
│   └── lean_runner.py          ← High-level interface
├── minimax/                    ← Your working directory
│   ├── repl_client.py          ← IDENTICAL copy of verifier/repl_client.py ✓
│   ├── test_corpus_mode2.py    ← YOUR FILE — start fresh from this plan
│   └── better_plan.md          ← This file
├── artifacts/                  ← Save all results here
│   └── mode2_results.json
└── breadboard/                 ← Kyle's infrastructure (Firecracker, HTTP API)
    └── scripts/
        ├── atp_firecracker_ci.sh
        └── atp_snapshot_pool_health.py
```

Data:
```
E:\LEAN-experiments\00_experiment1\
├── jsons\
│   └── traced_theorems_unified_v2.jsonl   ← Corpus (126,792 theorems)
└── gitpython-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5\mathlib4\
    └── Mathlib\                            ← Source tree (same commit as corpus)
```

WSL paths (use these in Python):
```
/mnt/e/LEAN-experiments/00_experiment1/jsons/traced_theorems_unified_v2.jsonl
/mnt/e/LEAN-experiments/00_experiment1/gitpython-mathlib4-.../mathlib4/
/mnt/e/LeanATP Harness/minimax/
```

---

## Key Facts About the Corpus

- Entry format: JSON with fields `full_name`, `statement`, `proof_text`, `file`, `namespace`, `open_namespaces`, `tactics`
- `file` field: relative path like `Mathlib/Algebra/Ring/Basic.lean`
- `full_name`: fully qualified, e.g. `Mathlib.Algebra.Ring.Basic.foo` or `foo` (short names exist too)
- `proof_type == "tactic"` means `proof_text` is a tactic block; filter to this type
- `proof_text` minimum length 20 chars to skip trivial/empty proofs
- `statement` ALREADY ENDS with `:=` sometimes (and sometimes not) — handle both
- The SAME toolchain as corpus: `leanprover/lean4:v4.10.0-rc1` — no version mismatches

## Key Facts About the Lean REPL

- Entry file in `repl_client.py` already runs `import Mathlib` before REPL starts
- So `base_sid = 0` is post-Mathlib state — never resend `import Mathlib`
- `session.setup([])` — empty list, no extra setup commands
- Each `session.check(cmd)` returns `ReplResponse(sid, error, stdout_lines)`
- `response.error is None` = no error (check `has_sorry` too)
- `response.has_sorry = True` = sorry present (should count as fail or separate)
- Timeout 90s per check is appropriate
- `pool.map(cmds, timeout=90.0)` — the timeout is per-command, 4 workers run in parallel

---

## Success Criteria

| Milestone | Pass Rate | Action |
|-----------|-----------|--------|
| Smoke test (10 theorems) | Any | Verify Python runs without crash |
| First 500 sequential | ≥ 92% | Mode 2 is working; compare failure breakdown vs Mode 1 |
| First 500 sequential | ≥ 97% | Excellent; run random 500 too |
| Random 500 | ≥ 92% | All targets met; copy to main verifier |

If you hit a wall at ~90% (same as Mode 1): the problem is likely `find_theorem_bounds`
failing for many entries — theorems not being found, so their stripped prefix is empty.
Add a counter for `bounds = None` and investigate which theorems fail.

---

## Quick Start Commands (Copy-Paste)

```bash
# In WSL terminal — run everything from here
cd '/mnt/e/LeanATP Harness/minimax'

# 1. Smoke test (should complete in ~90s)
python3 -u test_corpus_mode2.py --count 10 --workers 1 2>&1

# 2. Real benchmark (should complete in ~8 min)
python3 -u test_corpus_mode2.py --count 500 --workers 4 2>&1 | tee /tmp/mode2_500.log

# 3. Debug first 3 commands (add --debug flag to your script)
python3 -u test_corpus_mode2.py --count 3 --workers 1 --debug 2>&1

# 4. Compare with Mode 1
cd '/mnt/e/LeanATP Harness'
python3 -u verifier/test_corpus.py --count 500 --workers 4 2>&1 | tee /tmp/mode1_500.log
```
