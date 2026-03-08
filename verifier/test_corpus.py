"""
test_corpus.py — Verify real Mathlib proofs from the local corpus.

Loads tactic proofs from app_network_data.jsonl and submits each to the
Lean verifier. All should pass (they are ground-truth Mathlib proofs).

Run:
  python test_corpus.py [--count 10] [--random]
  python test_corpus.py --count 100 --workers 4   # parallel with 4 Lean processes
"""

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from repl_client import ReplPool, ReplSession, LeanReplClient

DATA_FILE = Path(__file__).parent.parent / "adjacent-possible-of-lean" / "data" / "app_network_data.jsonl"


def load_tactic_proofs(count: int, use_random: bool = False, min_proof_len: int = 20) -> list[dict]:
    """Load tactic proofs from the corpus. Prefer ones with non-trivial proof text."""
    candidates = []
    with open(DATA_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("proof_type") == "tactic" and len(d.get("proof_text") or "") >= min_proof_len:
                candidates.append(d)

    if use_random:
        random.shuffle(candidates)
    return candidates[:count]


def build_check_command(entry: dict) -> str:
    """
    Build a Lean command that reconstructs the theorem + proof.

    Uses the statement as-is (it may include a short name written inside its original
    namespace) wrapped in the namespace derived from full_name so dot notation resolves.
    Renames the theorem to avoid "already been declared" collisions with imported Mathlib.
    """
    full_name = entry.get("full_name", "")
    statement = entry.get("statement", "").strip()
    proof_text = entry.get("proof_text", "").strip()

    if not statement or not proof_text:
        return None

    # Rename: replace "theorem/lemma NAME" with "private theorem NAME_vt" to avoid
    # collisions with Mathlib theorems of the same name.
    stmt = re.sub(
        r'^((?:noncomputable\s+|protected\s+)?)(?:theorem|lemma)\s+(\S+)',
        lambda m: f"{m.group(1)}private theorem {m.group(2)}_vt",
        statement.rstrip(),
        count=1,
    )
    if stmt.endswith(":="):
        body = f"{stmt}\n{proof_text}"
    else:
        body = f"{stmt} :=\n{proof_text}"

    # Wrap in the namespace derived from full_name so short names in the proof resolve.
    if full_name and "." in full_name:
        ns = full_name.rsplit(".", 1)[0]
        return f"namespace {ns}\n{body}\nend {ns}"
    return body


def _classify(response, cmd: str) -> str:
    """Return 'pass', 'sorry', or 'fail:<msg>'."""
    if response.error is None and not response.has_sorry:
        return "pass"
    if response.has_sorry:
        return "sorry"
    return f"fail:{(response.error or '').strip()[:120]}"


def run_corpus_test(count: int = 10, use_random: bool = False, workers: int = 1) -> None:
    print(f"\nLoading {count} tactic proofs from corpus...")
    entries = load_tactic_proofs(count, use_random=use_random)
    if not entries:
        print(f"ERROR: No tactic proofs found in {DATA_FILE}")
        sys.exit(1)
    print(f"Loaded {len(entries)} entries.\n")

    # Build (entry, cmd) pairs, skip entries with no statement/proof
    jobs: list[tuple[dict, str]] = []
    skipped_names: list[str] = []
    for entry in entries:
        cmd = build_check_command(entry)
        if cmd:
            jobs.append((entry, cmd))
        else:
            skipped_names.append(entry.get("full_name", "?"))

    for name in skipped_names:
        print(f"  SKIP  {name}  (missing statement or proof)")

    passed = 0
    failed = 0
    skipped = len(skipped_names)

    if workers > 1:
        # --- Parallel path ---
        print(f"Starting {workers} Lean workers (loading Mathlib in parallel)...")
        t0 = time.time()
        pool = ReplPool(size=workers)
        pool.start()
        print(f"All workers ready in {time.time()-t0:.1f}s\n")

        cmds = [cmd for _, cmd in jobs]
        t_batch = time.time()
        responses = pool.map(cmds, timeout=90.0)
        elapsed_batch = time.time() - t_batch

        for i, ((entry, cmd), resp) in enumerate(zip(jobs, responses)):
            name = entry.get("full_name", f"entry_{i}")
            verdict = _classify(resp, cmd)
            if verdict == "pass":
                print(f"  PASS  [{i+1}/{len(jobs)}] {name}")
                passed += 1
            elif verdict == "sorry":
                print(f"  SORRY [{i+1}/{len(jobs)}] {name}  — has sorry placeholder")
                passed += 1
            else:
                msg = verdict[len("fail:"):]
                print(f"  FAIL  [{i+1}/{len(jobs)}] {name}")
                print(f"         {msg}")
                failed += 1

        pool.stop()
        print(f"\n(Batch of {len(jobs)} checks took {elapsed_batch:.1f}s wall time with {workers} workers)")

    else:
        # --- Serial path: single ReplSession ---
        print("Starting Lean (single worker, loading Mathlib once)...")
        t0 = time.time()
        client = LeanReplClient()
        client.start()
        session = ReplSession(client)
        session.setup(["import Mathlib"])
        print(f"Lean ready in {time.time()-t0:.1f}s\n")

        for i, (entry, cmd) in enumerate(jobs):
            name = entry.get("full_name", f"entry_{i}")
            t0 = time.time()
            resp = session.check(cmd, timeout=90.0)
            elapsed = time.time() - t0
            verdict = _classify(resp, cmd)
            if verdict == "pass":
                print(f"  PASS  [{i+1}/{len(jobs)}] {name}  ({elapsed*1000:.0f}ms)")
                passed += 1
            elif verdict == "sorry":
                print(f"  SORRY [{i+1}/{len(jobs)}] {name}  — has sorry placeholder")
                passed += 1
            else:
                msg = verdict[len("fail:"):]
                print(f"  FAIL  [{i+1}/{len(jobs)}] {name}")
                print(f"         {msg}")
                failed += 1

        client.stop()

    print(f"\n{'='*60}")
    print(f"Corpus test: {passed} pass, {failed} fail, {skipped} skip / {len(entries)} total")
    print("=" * 60)

    if failed > 0:
        print("\nNOTE: Failures may indicate:")
        print("  - Theorem uses universe variables / implicit args not in scope")
        print("  - Proof depends on earlier declarations in same file")
        print("  - Lean version mismatch between corpus and verifier")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10, help="Number of proofs to verify")
    parser.add_argument("--random", action="store_true", help="Pick proofs randomly")
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel Lean processes (default: 1 = serial)")
    args = parser.parse_args()

    run_corpus_test(count=args.count, use_random=args.random, workers=args.workers)
