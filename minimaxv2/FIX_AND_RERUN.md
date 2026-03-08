# Fix Applied — Rerun Required

## What happened (Run 3: 7.5%)

Root cause: **379 `expected_token` errors from orphaned doc comments.**

In Lean 4, doc comments look like `/-- This describes foo. -/` and must be
immediately followed by a declaration. The old code kept them verbatim in the
prefix, but then stripped the declaration that followed — leaving orphaned doc
comments that Lean rejects with `unexpected token '/--'`.

## Fix applied to test_corpus_mode2.py

Added doc-comment stripping in `strip_prefix_for_repl()`:
```python
# /-- ... -/ stripped entirely — orphaned doc comments cause expected_token errors
if s.startswith("/--"):
    if "-/" in s:
        i += 1  # single-line
    else:
        i += 1
        while i < len(lines) and "-/" not in lines[i]:
            i += 1
        i += 1  # skip closing -/
    continue
```

This runs BEFORE the block-comment handler so `/--` is never mistaken for `/-`.

## Your task: rerun

Syntax is already verified (SYNTAX_OK). Just run:

```bash
wsl.exe -d Ubuntu -- bash -c "cd '/mnt/e/LeanATP Harness/minimaxv2' && python3 -u test_corpus_mode2.py --count 500 --workers 4 2>&1 | tee /tmp/mode2_v4.log"
```

Expected: ~87–93% (379 expected_token errors fixed; remaining ~60 failures are
the same categories as Mode 1: unknown_identifier, already_declared, type_mismatch).

## After run completes

Write result to `/tmp/mode2_result.txt` and report pass rate vs Mode 1 baseline (90.6%).
