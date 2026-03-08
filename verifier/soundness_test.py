#!/usr/bin/env python3
"""
soundness_test.py  —  Verifier Soundness Experiment

Protocol:
  Phase 1: Run the first N_CANDIDATES corpus entries through the verifier.
           Collect those that PASS with proof_text >= MIN_PROOF_LEN chars.
           Pick the top N_TARGET by proof length (longer = richer target).

  Phase 2: For each selected entry, apply one distortion strategy to the
           proof_text.  Run the distorted entry through the EXACT SAME
           verifier pipeline (build_check_command → REPL pool → _classify)
           with no special treatment or knowledge of the injected error.

  Outcome: DETECTED  = verifier rejected distorted proof  (correct/sound)
           MISSED    = verifier accepted distorted proof  (false positive / unsound)

Distortion strategies (tried in priority order per theorem):
  Targeted (semantic errors):
    flip_mp_mpr        —  .mp ↔ .mpr  (wrong iff direction)
    flip_field_1_2     —  .1 ↔ .2    (wrong And/Prod component)
    ring_to_linarith   —  ring → linarith  (wrong tactic family for ring goal)
    omega_to_ring      —  omega → ring    (ring can't close ℕ/ℤ inequalities)
    flip_left_right    —  left → right   (wrong Or constructor)
    insert_symm        —  exact h → exact h.symm  (wrong direction)
    strip_symm         —  remove .symm  (reverses a deliberate direction flip)
    wrong_comm         —  mul_comm → add_comm (wrong algebraic law)
    norm_num_to_omega  —  norm_num → omega (omega fails on ℝ/ℚ goals)
    simp_to_exact_rfl  —  simp [...] → exact rfl (wrong closer)
  Fallback (structural, near-guaranteed fail):
    remove_last_tactic —  drop the last substantive tactic line
    truncate_half      —  keep only first half of tactic lines
"""

import json
import re
import sys
import time
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).parent))
from repl_client import ReplPool
from test_corpus import build_check_command, load_tactic_proofs, _classify

RESULTS_PATH = Path(__file__).parent.parent / "artifacts" / "soundness_test_results.json"
N_CANDIDATES = 100    # probe this many to find passing ones
N_TARGET = 20         # distort this many
MIN_PROOF_LEN = 150   # chars — ensures multi-tactic proofs
WORKERS = 4


# ─────────────────────────────────────────────────────────────────────────────
# Distortion functions
# ─────────────────────────────────────────────────────────────────────────────

DistortFn = Callable[[str], Optional[str]]


def _changed(orig: str, new: Optional[str]) -> Optional[str]:
    """Return new only if it's non-empty and actually different from orig."""
    if new and new.strip() and new.strip() != orig.strip():
        return new
    return None


def _d_flip_mp_mpr(proof: str) -> Optional[str]:
    """.mp → .mpr or .mpr → .mp (wrong direction of iff application)."""
    has_mp  = bool(re.search(r'\.mp\b',  proof))
    has_mpr = bool(re.search(r'\.mpr\b', proof))
    if has_mp and not has_mpr:
        return _changed(proof, re.sub(r'\.mp\b', '.mpr', proof, count=1))
    if has_mpr and not has_mp:
        return _changed(proof, re.sub(r'\.mpr\b', '.mp', proof, count=1))
    return None


def _d_flip_field_1_2(proof: str) -> Optional[str]:
    """h.1 → h.2 (first occurrence); gets the wrong component of a pair/And."""
    m = re.search(r'(\b\w+)\.1\b', proof)
    if m:
        return _changed(proof, proof[:m.start()] + m.group(1) + '.2' + proof[m.end():])
    m = re.search(r'(\b\w+)\.2\b', proof)
    if m:
        return _changed(proof, proof[:m.start()] + m.group(1) + '.1' + proof[m.end():])
    return None


def _d_ring_to_linarith(proof: str) -> Optional[str]:
    """ring → linarith.  linarith can't close polynomial/ring identities."""
    if re.search(r'(?<![a-zA-Z_])ring(?![a-zA-Z_])', proof):
        return _changed(proof, re.sub(r'(?<![a-zA-Z_])ring(?![a-zA-Z_])', 'linarith', proof, count=1))
    return None


def _d_omega_to_ring(proof: str) -> Optional[str]:
    """omega → ring.  ring can't close ℕ/ℤ inequality goals."""
    if re.search(r'\bomega\b', proof):
        return _changed(proof, re.sub(r'\bomega\b', 'ring', proof, count=1))
    return None


def _d_flip_left_right(proof: str) -> Optional[str]:
    """left → right or Or.inl → Or.inr (wrong disjunct in an Or proof)."""
    if re.search(r'^\s*left\s*$', proof, re.MULTILINE):
        return _changed(proof, re.sub(
            r'(^\s*)left(\s*$)', r'\1right\2', proof, count=1, flags=re.MULTILINE))
    if 'Or.inl' in proof:
        return _changed(proof, proof.replace('Or.inl', 'Or.inr', 1))
    return None


def _d_insert_symm(proof: str) -> Optional[str]:
    """exact h → exact h.symm  (or apply → apply h.symm); wrong direction."""
    m = re.search(r'\b(exact|apply)\s+([a-zA-Z_α-ω]\w*)\b', proof)
    if m and m.group(2) not in ('rfl', 'trivial', 'this', 'id', 'fun', 'True'):
        repl = f"{m.group(1)} {m.group(2)}.symm"
        return _changed(proof, proof[:m.start()] + repl + proof[m.end():])
    return None


def _d_strip_symm(proof: str) -> Optional[str]:
    """Remove first .symm — reverses an intentional direction flip in the proof."""
    if '.symm' in proof:
        idx = proof.index('.symm')
        return _changed(proof, proof[:idx] + proof[idx + len('.symm'):])
    return None


def _d_wrong_comm(proof: str) -> Optional[str]:
    """mul_comm → add_comm (or vice versa) — wrong algebraic law."""
    if 'mul_comm' in proof:
        return _changed(proof, proof.replace('mul_comm', 'add_comm', 1))
    if 'add_comm' in proof:
        return _changed(proof, proof.replace('add_comm', 'mul_comm', 1))
    return None


def _d_norm_num_to_omega(proof: str) -> Optional[str]:
    """norm_num → omega.  omega can't handle ℝ/ℚ or non-linear numeric goals."""
    if re.search(r'\bnorm_num\b', proof):
        return _changed(proof, re.sub(r'\bnorm_num\b', 'omega', proof, count=1))
    return None


def _d_simp_to_exact_rfl(proof: str) -> Optional[str]:
    """Replace first `simp [...]` with `exact rfl` — wrong closer for non-rfl goals."""
    m = re.search(r'\bsimp\b[^\n]*', proof)
    if m:
        return _changed(proof, proof[:m.start()] + 'exact rfl' + proof[m.end():])
    return None


def _d_remove_last_tactic(proof: str) -> Optional[str]:
    """Drop the last substantive tactic line — leaves unsolved goals."""
    lines = proof.split('\n')
    for i in range(len(lines) - 1, -1, -1):
        s = lines[i].strip()
        if s and not s.startswith('--') and s not in ('}', ')', ']', 'done', '·'):
            new = '\n'.join(lines[:i] + lines[i + 1:])
            return _changed(proof, new)
    return None


def _d_truncate_half(proof: str) -> Optional[str]:
    """Keep only first half of non-trivial tactic lines."""
    lines = [l for l in proof.split('\n') if l.strip() and not l.strip().startswith('--')]
    if len(lines) < 4:
        return None
    keep = max(2, len(lines) // 2)
    return _changed(proof, '\n'.join(lines[:keep]))


# Priority order: targeted (semantic) first, structural fallbacks last
DISTORTIONS: list[tuple[str, DistortFn]] = [
    ("flip_mp_mpr",        _d_flip_mp_mpr),
    ("flip_field_1_2",     _d_flip_field_1_2),
    ("ring_to_linarith",   _d_ring_to_linarith),
    ("omega_to_ring",      _d_omega_to_ring),
    ("flip_left_right",    _d_flip_left_right),
    ("insert_symm",        _d_insert_symm),
    ("strip_symm",         _d_strip_symm),
    ("wrong_comm",         _d_wrong_comm),
    ("norm_num_to_omega",  _d_norm_num_to_omega),
    ("simp_to_exact_rfl",  _d_simp_to_exact_rfl),
    # Fallbacks — near-guaranteed to cause Lean failure
    ("remove_last_tactic", _d_remove_last_tactic),
    ("truncate_half",      _d_truncate_half),
]


def choose_distortion(proof_text: str) -> Optional[tuple[str, str]]:
    """
    Try each distortion in priority order.
    Return (strategy_name, distorted_proof) for the first applicable one.
    Prefer targeted semantic errors; fall back to structural removal only if needed.
    """
    for name, fn in DISTORTIONS:
        result = fn(proof_text)
        if result:
            return name, result
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def run_soundness_test() -> list[dict]:
    print("\n" + "=" * 60)
    print("SOUNDNESS TEST  —  Phase 1: Finding Passing Theorems")
    print("=" * 60)

    candidates = load_tactic_proofs(N_CANDIDATES, use_random=False, min_proof_len=MIN_PROOF_LEN)
    print(f"Loaded {len(candidates)} candidates (proof_len >= {MIN_PROOF_LEN} chars, sequential)")

    pool = ReplPool(size=WORKERS)
    pool.start()
    print(f"{WORKERS} workers ready. Running Phase 1...")

    valid_entries, cmds = [], []
    for entry in candidates:
        cmd = build_check_command(entry)
        if cmd:
            valid_entries.append(entry)
            cmds.append(cmd)

    t0 = time.time()
    responses = pool.map(cmds, timeout=90.0)
    print(f"Phase 1 complete in {time.time() - t0:.1f}s")

    passing = [e for e, r in zip(valid_entries, responses) if _classify(r) == "pass"]
    print(f"Passing: {len(passing)} / {len(valid_entries)}")

    # Pick longest proofs first
    passing.sort(key=lambda e: len(e.get("proof_text", "")), reverse=True)
    selected = passing[:N_TARGET]
    print(f"\nSelected {len(selected)} theorems (sorted by proof length):")
    for e in selected:
        print(f"  {len(e.get('proof_text',''))} chars  {e.get('full_name', '?')}")

    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("SOUNDNESS TEST  —  Phase 2: Distorting and Re-Verifying")
    print("=" * 60)

    to_test = []   # (entry, strategy, orig_proof, distorted_proof, cmd)
    for entry in selected:
        orig = entry.get("proof_text", "")
        choice = choose_distortion(orig)
        if choice is None:
            print(f"  [SKIP-no-distortion]  {entry.get('full_name','?')}")
            continue
        strategy, dist_proof = choice
        dist_entry = dict(entry)
        dist_entry["proof_text"] = dist_proof
        cmd = build_check_command(dist_entry)
        if not cmd:
            print(f"  [SKIP-cmd-fail]  {entry.get('full_name','?')}")
            continue
        to_test.append((entry, strategy, orig, dist_proof, cmd))
        print(f"  strategy={strategy:<22}  {entry.get('full_name','?')}")

    print(f"\nRunning {len(to_test)} distorted proofs through verifier...")
    dist_cmds = [x[4] for x in to_test]
    t0 = time.time()
    dist_responses = pool.map(dist_cmds, timeout=90.0)
    print(f"Phase 2 complete in {time.time() - t0:.1f}s")

    pool.stop()

    # ─────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    results = []
    detected = missed = 0

    for (entry, strategy, orig_proof, dist_proof, _cmd), resp in zip(to_test, dist_responses):
        verdict = _classify(resp)
        outcome = "DETECTED" if verdict != "pass" else "MISSED"
        error_msg = verdict[5:].split('\n')[0][:120] if verdict.startswith("fail:") else ""

        if outcome == "DETECTED":
            detected += 1
            print(f"  DETECTED  [{strategy}]")
            print(f"    {entry.get('full_name','?')}")
            print(f"    error: {error_msg[:100]}")
        else:
            missed += 1
            print(f"  *** MISSED (FALSE PASS) ***  [{strategy}]")
            print(f"    {entry.get('full_name','?')}")
            print(f"    Distorted proof was accepted as valid!")

        results.append({
            "full_name":          entry.get("full_name", ""),
            "proof_len":          len(orig_proof),
            "distortion":         strategy,
            "original_proof":     orig_proof,
            "distorted_proof":    dist_proof,
            "verifier_verdict":   verdict,
            "outcome":            outcome,
            "error_message":      error_msg,
        })

    total = detected + missed
    print(f"\n{'─'*40}")
    print(f"Total tested:  {total}")
    print(f"DETECTED:      {detected}  ({detected/total*100:.0f}%)")
    print(f"MISSED:        {missed}   ({missed/total*100:.0f}%)")
    print(f"Soundness rate: {detected/total*100:.1f}%")
    print("=" * 60)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "n_candidates":    N_CANDIDATES,
            "n_passing_found": len(passing),
            "n_distorted":     total,
            "detected":        detected,
            "missed":          missed,
            "soundness_rate":  round(detected / total, 4) if total else 0,
            "results":         results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved → {RESULTS_PATH}")
    return results


if __name__ == "__main__":
    run_soundness_test()
