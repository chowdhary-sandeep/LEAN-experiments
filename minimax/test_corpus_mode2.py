"""
test_corpus_mode2.py — Mode 2: Stripped Source Prefix Verification

Key approach: Take source file lines 1 to (theorem_start - 1), strip only the
declarations that conflict with `import Mathlib`, keep everything else VERBATIM
(sections, namespaces, opens, variables, private defs). This preserves section
scoping automatically.

The command structure is:
  noncomputable section
  set_option quotPrecheck false
  [stripped prefix — verbatim, section/namespace structure intact]
  private theorem short_name_vt ... :=
    [proof]
  end [namespace_N]
  end [section_S]
  ...
  end   ← closes noncomputable section
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))
from repl_client import ReplPool, ReplSession, LeanReplClient

CORPUS_FILE = Path("/mnt/e/LEAN-experiments/00_experiment1/jsons/traced_theorems_unified_v2.jsonl")
MATHLIB_ROOT = Path("/mnt/e/LEAN-experiments/00_experiment1/gitpython-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4")

print(f"Corpus: {CORPUS_FILE}")
print(f"Mathlib: {MATHLIB_ROOT}")

# ── Strip patterns ────────────────────────────────────────────────────────────
# Lines to strip because they conflict with `import Mathlib` or are not valid
# commands in a noncomputable section context.

# Public declarations — already in Mathlib, would be "already declared"
# NOTE: ^(?:@\[.*?\]\s*)* does NOT cross newlines, so @[...] on its OWN LINE
# is handled separately by _STRIP_ATTR_LINE below.
_STRIP_PUBLIC_DECL = re.compile(
    r'^(?:noncomputable\s+|protected\s+)*'
    r'(?:theorem|lemma|def|instance|class|structure|abbrev|inductive|mutual|opaque)\s+'
)
# Private defs — keep these (they're helpers not in Mathlib's public namespace)
_KEEP_PRIVATE = re.compile(r'^private\s+')
# Import statements — already have Mathlib
_STRIP_IMPORT = re.compile(r'^import\s+')
# Hash commands — not valid in noncomputable section
_STRIP_HASH = re.compile(r'^#')
# Standalone attribute annotations at column 0 — orphaned after stripping their declaration
_STRIP_ATTR = re.compile(r'^@\[')
# Standalone attribute [...] commands
_STRIP_ATTRIBUTE_CMD = re.compile(r'^attribute\s*\[')


def strip_prefix_for_repl(lines: List[str]) -> List[str]:
    """
    Take source file lines and remove everything that would conflict with
    `import Mathlib` being loaded, or that is invalid in a noncomputable section.

    KEEP verbatim:
      section / end / namespace / end — preserves scoping structure
      open X — name resolution
      variable (...) — typeclass context, with section scoping preserved
      universe u v — universe declarations
      local notation / local infixl etc. — local syntax
      private def / private abbrev — helper definitions
      set_option — options
      comments — fine

    STRIP:
      import lines
      public theorem / lemma / def / instance / class / structure / abbrev / inductive
      @[...] lines at column 0 (attribute annotations for stripped declarations)
      attribute [...] standalone commands
      # commands (#check, #eval, #align, etc.)
    """
    result = []
    in_block_comment = False
    i = 0

    while i < len(lines):
        raw = lines[i]
        s = raw.strip()

        # ── Block comment tracking ──
        if not in_block_comment:
            if s.startswith("/-") and not s.startswith("--"):
                # Check if it closes on the same line
                opens  = s.count("/-")
                closes = s.count("-/")
                if opens > closes:
                    in_block_comment = True
                result.append(raw)
                i += 1
                continue
        else:
            result.append(raw)
            if "-/" in s:
                in_block_comment = False
            i += 1
            continue

        # ── Always strip: import, #commands, attribute [...], @[...] ──
        if (_STRIP_IMPORT.match(s) or _STRIP_HASH.match(s)
                or _STRIP_ATTR.match(s) or _STRIP_ATTRIBUTE_CMD.match(s)):
            i += 1
            continue

        # ── Strip public declarations (but keep private ones) ──
        if _STRIP_PUBLIC_DECL.match(s) and not _KEEP_PRIVATE.match(s):
            # Skip this line plus all indented continuation lines
            i += 1
            while i < len(lines) and lines[i][0:1] in (" ", "\t"):
                i += 1
            continue

        # Keep everything else verbatim
        result.append(raw)
        i += 1

    return result


def get_open_stack(lines: List[str]) -> List[Tuple[str, str]]:
    """
    Walk lines and return the stack of namespace/section names still open
    at the end (innermost last). Used to emit matching `end` statements.
    """
    stack: List[Tuple[str, str]] = []
    in_block = False

    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("--"):
            continue
        if not in_block:
            if s.startswith("/-"):
                if s.count("/-") > s.count("-/"):
                    in_block = True
                continue
        else:
            if "-/" in s:
                in_block = False
            continue

        m_ns  = re.match(r'^namespace\s+(\S+)', s)
        m_sec = re.match(r'^section\b\s*(\S*)', s)
        m_end = re.match(r'^end\b\s*(\S*)', s)

        if m_ns:
            stack.append(("namespace", m_ns.group(1)))
        elif m_sec:
            stack.append(("section", m_sec.group(1) or "_anon"))
        elif m_end:
            name = m_end.group(1)
            for k in range(len(stack) - 1, -1, -1):
                if not name or stack[k][1] == name:
                    stack.pop(k)
                    break

    return stack


def find_theorem_bounds(source: str, full_name: str) -> Optional[Tuple[int, int]]:
    """Find (start_idx, end_idx) 0-indexed for the theorem in the source."""
    short = full_name.split(".")[-1]
    lines = source.splitlines()

    # Try short name, and also penultimate.last (e.g. "Foo.bar" inside namespace Foo)
    names = [short]
    parts = full_name.split(".")
    if len(parts) >= 2:
        names.append(f"{parts[-2]}.{parts[-1]}")

    in_block = False
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith("--"):
            continue
        if not in_block:
            if s.startswith("/-"):
                if s.count("/-") > s.count("-/"):
                    in_block = True
                continue
        else:
            if "-/" in s:
                in_block = False
            continue

        for name in names:
            if re.search(rf'(?:theorem|lemma)\s+{re.escape(name)}\b', s):
                end = _find_decl_end(lines, i)
                return (i, end)
    return None


def _find_decl_end(lines: List[str], start: int) -> int:
    """Find the line index where the declaration header ends."""
    depth = 0
    for j in range(start, min(start + 60, len(lines))):
        line = lines[j]
        depth += line.count("(") + line.count("{") + line.count("[")
        depth -= line.count(")") + line.count("}") + line.count("]")
        if depth <= 0 and (":=" in line or re.search(r'\bwhere\b', line)):
            return j
    return start + 5


def rename_theorem(statement: str, full_name: str) -> str:
    """Rename theorem/lemma to `private theorem short_vt`."""
    short = full_name.split(".")[-1]
    new   = f"private theorem {short}_vt"
    mods  = r'(?:noncomputable\s+|protected\s+)*'
    stmt  = re.sub(rf'^{mods}(?:theorem|lemma)\s+\S+', new,
                   statement.strip(), count=1)
    stmt  = re.sub(rf'(^@\[.*?\]\n?){mods}(?:theorem|lemma)\s+\S+',
                   rf'\1{new}', stmt, count=1, flags=re.MULTILINE)
    return stmt


def build_mode2_command(entry: dict) -> Optional[str]:
    full_name  = entry.get("full_name", "")
    statement  = (entry.get("statement") or "").strip()
    proof_text = (entry.get("proof_text") or "").strip()

    if not statement or not proof_text:
        return None

    # Strip #adaptation_note lines from proof
    proof_text = re.sub(r'^\s*#adaptation_note\b[^\n]*\n?', '', proof_text,
                        flags=re.MULTILINE)

    file_rel = entry.get("file", "").replace("\\", "/")
    if not file_rel:
        return None

    source_path = MATHLIB_ROOT / file_rel
    if not source_path.exists():
        return None

    try:
        source = source_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    bounds = find_theorem_bounds(source, full_name)
    if not bounds:
        return None

    start_idx, _end_idx = bounds
    # Take all lines BEFORE the theorem — this is the context that was in scope
    prefix_lines = source.splitlines()[:start_idx]

    stripped   = strip_prefix_for_repl(prefix_lines)
    open_stack = get_open_stack(prefix_lines)

    stmt = rename_theorem(statement, full_name)
    body = (stmt + "\n" + proof_text
            if stmt.rstrip().endswith(":=")
            else stmt + " :=\n" + proof_text)

    # ── CRITICAL: noncomputable section MUST come FIRST ──
    # The stripped prefix lives INSIDE it, so section/namespace blocks opened
    # in the prefix can be closed naturally before we close the outer wrapper.
    cmd = ["noncomputable section", "set_option quotPrecheck false"]
    cmd += stripped        # verbatim prefix: sections, opens, variables, private defs
    cmd.append(body)       # renamed theorem with proof
    # Close all blocks still open at the theorem's position (innermost first)
    for _kind, name in reversed(open_stack):
        cmd.append(f"end {name}")
    cmd.append("end")      # close noncomputable section

    return "\n".join(cmd)


# ── Data loading ──────────────────────────────────────────────────────────────

def load_proofs(count: int, randomize: bool = False, min_len: int = 20) -> List[dict]:
    if not CORPUS_FILE.exists():
        print(f"ERROR: Corpus not found: {CORPUS_FILE}")
        sys.exit(1)
    candidates = []
    with open(CORPUS_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("proof_type") == "tactic" and len(d.get("proof_text") or "") >= min_len:
                candidates.append(d)
    if randomize:
        import random
        random.shuffle(candidates)
    return candidates[:count]


def _classify(resp) -> str:
    if resp.error is None and not resp.has_sorry:
        return "pass"
    if resp.has_sorry:
        return "sorry"
    return f"fail:{(resp.error or '').strip()[:120]}"


# ── Main ──────────────────────────────────────────────────────────────────────

def run_mode2(count: int = 500, randomize: bool = False,
              workers: int = 4, debug: bool = False):
    print(f"\n{'='*60}")
    print("MODE 2: Stripped Source Prefix Verification")
    print(f"{'='*60}")

    entries = load_proofs(count, randomize=randomize)
    print(f"Loaded {len(entries)} entries\n")

    jobs, skipped = [], 0
    for entry in entries:
        cmd = build_mode2_command(entry)
        if cmd:
            jobs.append((entry, cmd))
        else:
            skipped += 1

    print(f"Jobs: {len(jobs)}, Skipped: {skipped}\n")
    if not jobs:
        print("ERROR: No jobs!")
        sys.exit(1)

    if debug:
        for entry, cmd in jobs[:3]:
            print(f"\n{'='*60}")
            print(f"THEOREM: {entry['full_name']}")
            print(f"{'─'*60}")
            print(cmd[:4000])
            print()
        return

    passed = failed = 0
    fail_cats: dict = {}

    def record(verdict: str):
        nonlocal passed, failed
        if verdict in ("pass", "sorry"):
            passed += 1
        else:
            failed += 1
            msg = verdict[5:].split("\n")[0][:60]
            for pat, lab in [
                ("failed to synthesize",   "failed_to_synthesize"),
                ("unknown identifier",      "unknown_identifier"),
                ("function expected",       "function_expected"),
                ("expected token",          "expected_token"),
                ("already been declared",   "already_declared"),
                ("application type mismatch", "type_mismatch"),
            ]:
                if pat in msg:
                    fail_cats[lab] = fail_cats.get(lab, 0) + 1
                    return
            fail_cats["other"] = fail_cats.get("other", 0) + 1

    print(f"Starting {workers} workers...")
    t0 = time.time()
    pool = ReplPool(size=workers)
    pool.start()
    print(f"Ready in {time.time()-t0:.1f}s\n")

    cmds = [c for _, c in jobs]
    t_batch = time.time()
    responses = pool.map(cmds, timeout=90.0)
    elapsed = time.time() - t_batch

    for i, ((entry, _cmd), resp) in enumerate(zip(jobs, responses)):
        name    = entry.get("full_name", f"entry_{i}")
        verdict = _classify(resp)
        tag     = "PASS" if verdict == "pass" else "SORRY" if verdict == "sorry" else "FAIL"
        if tag != "PASS":
            print(f"  {tag} [{i+1}/{len(jobs)}] {name}")
            msg = verdict[5:] if verdict.startswith("fail:") else ""
            if msg:
                print(f"       {msg[:100]}")
        record(verdict)

    pool.stop()
    print(f"\nBatch: {elapsed:.1f}s with {workers} workers")

    total = len(jobs)
    print(f"\n{'='*60}")
    print(f"Mode 2: {passed} PASS {failed} FAIL ({passed/total*100:.1f}%)")
    if fail_cats:
        print("Failures:")
        for cat, n in sorted(fail_cats.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {n}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count",   type=int, default=500)
    parser.add_argument("--random",  action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--debug",   action="store_true")
    args = parser.parse_args()
    run_mode2(count=args.count, randomize=args.random,
              workers=args.workers, debug=args.debug)
