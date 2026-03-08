# Your Task — Mode 2 Verification Run

The code is already written and ready. Your job is to run it and report results.

## What this does
`test_corpus_mode2.py` verifies 500 Lean theorems from Mathlib using Mode 2:
- Takes the verbatim source file prefix (everything before the theorem)
- Strips only what conflicts with `import Mathlib` (public decls, imports, `@[...]` attrs)
- Keeps sections/namespaces/opens/variables VERBATIM — preserving section scoping
- Wraps in `noncomputable section` and checks via Lean REPL

## Step 1 — Syntax check (fast, no Lean)
```bash
wsl.exe -d Ubuntu -- bash -c "cd '/mnt/e/LeanATP Harness/minimaxv2' && python3 -m py_compile test_corpus_mode2.py && echo SYNTAX_OK"
```

## Step 2 — Debug check (fast, no Lean startup, just prints generated commands)
```bash
wsl.exe -d Ubuntu -- bash -c "cd '/mnt/e/LeanATP Harness/minimaxv2' && python3 -u test_corpus_mode2.py --count 3 --debug 2>&1 | head -80"
```
The very first line of each generated command block MUST be `noncomputable section`.
If it is not, stop and report — do not run the full test.

## Step 3 — Full run (~8 minutes total: 70s Lean cold start + ~5 min for 500 checks)
```bash
wsl.exe -d Ubuntu -- bash -c "cd '/mnt/e/LeanATP Harness/minimaxv2' && python3 -u test_corpus_mode2.py --count 500 --workers 4 2>&1 | tee /tmp/mode2_v3.log"
```

During the first ~70 seconds you will see "Starting N workers..." with no further output.
This is Lean loading Mathlib — it is NORMAL. Do not restart. Just wait.

After warmup, checks run fast (~15s for 500). Then you'll see the final result:
```
Mode 2: X PASS Y FAIL (Z%)
```

## Step 4 — Report
Print the pass rate, failure category breakdown, and whether it beats Mode 1 baseline (90.6% sequential).

Write the result to `/tmp/mode2_result.txt`:
```
Run 3: X% (X pass / Y fail out of Z jobs, W skipped)
Failures: [categories]
```

## Background context
- Mode 1 baseline: 90.6% on first 500 sequential theorems
- Mode 2 goal: ≥90% (parity), ideally ≥95% (improvement from section scoping)
- Corpus: `/mnt/e/LEAN-experiments/00_experiment1/jsons/traced_theorems_unified_v2.jsonl`
- Mathlib source: `/mnt/e/LEAN-experiments/00_experiment1/gitpython-mathlib4-.../mathlib4/`
- Lean toolchain: `leanprover/lean4:v4.10.0-rc1`
- Workers stagger start by 4s each to avoid lake file lock — this is intentional

## Do NOT
- Do not modify `test_corpus_mode2.py`
- Do not run with `--count 10` or small counts (cold start dominates, results meaningless)
- Do not rewrite the approach — the code is correct, just run it
