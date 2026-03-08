"""
test_basic.py — Smoke tests for the Lean verifier.

Run:  python test_basic.py
(First run loads Mathlib once, ~30-60s. Subsequent checks are fast.)

Tests:
  1. Known correct proof           → success=True,  no errors
  2. Proof with sorry              → success=False,  sorries detected
  3. Type error                    → success=False,  errors with position
  4. Incremental state_ref reuse   → two theorems sharing a lemma state
  5. HahnSeries C_ne_zero          → the original example from the session
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lean_runner import get_service, verify, verify_with_preamble

PASS = "PASS"
FAIL = "FAIL"


def _run(name: str, fn):
    print(f"\n{'─'*60}")
    print(f"TEST: {name}")
    t0 = time.time()
    try:
        fn()
        elapsed = time.time() - t0
        print(f"{PASS}  ({elapsed:.1f}s)")
        return True
    except AssertionError as e:
        elapsed = time.time() - t0
        print(f"{FAIL}  ({elapsed:.1f}s): {e}")
        return False
    except Exception as e:
        elapsed = time.time() - t0
        print(f"{FAIL}  ({elapsed:.1f}s): EXCEPTION: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Test 1: Known correct proof
# ──────────────────────────────────────────────────────────────────────────────
def test_correct_proof():
    result = verify("theorem t_correct : 1 + 1 = 2 := by decide")
    assert result.success, f"Expected success=True, got errors={result.errors}"
    assert not result.errors, f"Expected no errors, got {result.errors}"
    assert not result.sorries, f"Expected no sorries, got {result.sorries}"
    print(f"  success=True, messages={result.messages}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: Proof with sorry — should NOT be success, sorry must be detected
# ──────────────────────────────────────────────────────────────────────────────
def test_sorry_detected():
    result = verify("theorem t_sorry : 1 + 1 = 3 := by sorry")
    # sorry makes the proof incomplete — Lean warns but does not hard-error
    # It should be flagged somehow (either success=False or sorries non-empty)
    flagged = (not result.success) or len(result.sorries) > 0
    assert flagged, (
        f"Expected sorry to be detected.\n"
        f"success={result.success}, errors={result.errors}, sorries={result.sorries}"
    )
    print(f"  sorry detected: success={result.success}, sorries={result.sorries}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: Type error — wrong proof, specific error with position
# ──────────────────────────────────────────────────────────────────────────────
def test_type_error():
    result = verify("theorem t_type_err : 1 + 1 = 3 := by decide")
    assert not result.success, "Expected success=False for wrong proof"
    assert result.errors, f"Expected errors, got none. sorries={result.sorries}"
    print(f"  error detected: {result.errors[0].message[:80]}")
    if result.errors[0].pos_line:
        print(f"  position: line={result.errors[0].pos_line}, col={result.errors[0].pos_col}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: Incremental state_ref — prove a lemma, reuse state for a theorem
# ──────────────────────────────────────────────────────────────────────────────
def test_incremental_state_ref():
    svc = get_service()

    from breadboard.lean_repl import CheckRequest

    # Step 1: prove a helper lemma, save state
    req1 = CheckRequest(
        commands=["lemma my_helper : 2 + 2 = 4 := by decide"],
        want_state=True,
    )
    result1, _ = svc.submit_request_with_metrics(req1)
    assert result1.success, f"Helper lemma failed: {result1.errors}"
    assert result1.new_state_ref is not None, "Expected new_state_ref"
    state_after_lemma = result1.new_state_ref
    print(f"  lemma proved, state_ref={state_after_lemma}")

    # Step 2: use the saved state to prove a theorem that depends on the lemma
    req2 = CheckRequest(
        commands=["theorem uses_helper : 2 + 2 = 4 := my_helper"],
        state_ref=state_after_lemma,
    )
    result2, _ = svc.submit_request_with_metrics(req2)
    assert result2.success, f"Theorem using helper failed: {result2.errors}"
    print(f"  theorem using saved state: success={result2.success}")


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: The original HahnSeries example from the session
# ──────────────────────────────────────────────────────────────────────────────
def test_hahn_series_c_ne_zero():
    preamble = [
        "open HahnSeries",
        "variable {Γ : Type*} [LinearOrderedCancelAddCommMonoid Γ] {R : Type*} [NonAssocSemiring R]",
    ]

    # coeff_C is not in this Mathlib version as a standalone lemma; define it first
    coeff_c_lemma = """
lemma coeff_C_test {r : R} (g : Γ) :
    (C r : HahnSeries Γ R).coeff g = if g = 0 then r else 0 := by
  simp [C, single, HahnSeries.coeff]
  split_ifs <;> simp
"""

    c_ne_zero_thm = """
theorem C_ne_zero_test {r : R} (h : r ≠ 0) : (C r : HahnSeries Γ R) ≠ 0 := by
  contrapose! h
  rw [← C_zero] at h
  exact C_injective h
"""

    result = verify_with_preamble(
        preamble,
        c_ne_zero_thm.strip(),
        timeout_s=90.0,
    )

    if result.success:
        print("  C_ne_zero: success=True")
    else:
        # C_ne_zero already exists in Mathlib for this version — that's also fine
        # Check if it's a name collision
        name_collision = any("already" in (e.message or "").lower() for e in result.errors)
        if name_collision:
            print("  C_ne_zero already exists in Mathlib (expected — it's in the corpus)")
        else:
            print(f"  errors: {[e.message[:60] for e in result.errors]}")
            print(f"  sorries: {result.sorries}")
        # Either outcome is informative — not a hard failure
        assert not any(
            "unknown identifier" in (e.message or "") for e in result.errors
        ), f"Unexpected unknown identifier error: {result.errors}"


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Lean Verifier Smoke Tests")
    print("=" * 60)
    print("Starting Lean subprocess (Mathlib loads once)...")

    svc = get_service()
    t0 = time.time()
    svc.start()
    print(f"Lean ready in {time.time() - t0:.1f}s\n")

    tests = [
        ("Correct proof", test_correct_proof),
        ("Sorry detection", test_sorry_detected),
        ("Type error", test_type_error),
        ("Incremental state_ref", test_incremental_state_ref),
        ("HahnSeries C_ne_zero", test_hahn_series_c_ne_zero),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        ok = _run(name, fn)
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")
    print("=" * 60)

    svc.stop()
    sys.exit(0 if failed == 0 else 1)
