# Parallel Agent Evolution Plan

## Goal
5 independent Sonnet subagents, each with its own copy of `verifier/test_corpus.py`, running 5 improvement iterations on 500 theorems (4 workers each). Target: push individual agent pass rate toward 80% from current ~60%. After convergence, best ideas merged back to main line.

## Directory Structure
```
E:\LeanATP Harness\agents\
  agent1\verifier\  (copy of current verifier/)
  agent2\verifier\
  agent3\verifier\
  agent4\verifier\
  agent5\verifier\
```
Each agent's `verifier/` is a full standalone copy (test_corpus.py, repl_client.py, lean_runner.py).

## Agent Focus Areas

| Agent | Specialization | Strategy |
|---|---|---|
| **Agent 1** | Variable extraction | Improve `_extract_variables()` (state_before fallback) + `_normalize_and_dedup_vars()`. Target `redundant binder annotation` and `type_mismatch` errors. |
| **Agent 2** | Open namespace recovery | Improve `_get_source_opens()` + fallback logic. Target `unknown namespace` and `function_expected` errors from missing opens. |
| **Agent 3** | CategoryTheory universe | Handle `Category.{v,u}`, `Functor.{v,u}`, universe polymorphism. Target `invalid use of explicit universe params` (61 failures) and `type_mismatch` (20). |
| **Agent 4** | Error-driven fixes | Profile top-N remaining errors, implement targeted pattern fixes. Broad coverage. |
| **Agent 5** | Integration + ceiling | Combine approaches, try creative solutions (e.g. stripping sections, section-aware variable scoping, `set_option` workarounds). |

## Run Protocol (per agent)
1. Start with current `test_corpus.py` (baseline: ~38% with bugs, ~60% with all pre-Run11 fixes)
2. Run 500 theorems, 4 workers: `python3 -u test_corpus.py --count 500 --workers 4`
3. Analyze failure breakdown
4. Modify `test_corpus.py` with targeted fix
5. Repeat steps 2–4 up to **5 times**
6. Report final pass rate + 3 best fixes found

## Parallelism & Resource Management
- **Launch stagger**: 60s between each agent start to avoid lake lock contention
- **Workers per agent**: 4 (total 20 workers max, 32 cores available)
- **Peak load**: ~20 Lean procs × ~1.5 cores = ~30 cores — acceptable
- **Output**: each agent writes to `/tmp/agentN_runK.txt` for monitoring

## Convergence Criteria
- Agent runs all 5 iterations OR achieves >75% pass rate (early stop)
- If an iteration regresses by >5%, agent reverts to previous version

## Merge Strategy (post-completion)
- Read all agent findings
- Rank improvements by pass rate gain and orthogonality (non-overlapping fixes)
- Merge top improvements into main `verifier/test_corpus.py`
- Run final validation on 1000 theorems

## Held-out Test Set
- All agents train on theorems 1–500 (first 500 sequential entries)
- Held-out evaluation: theorems 501–1000 (use `--count 1000` with `--random False`)
- Agents do NOT see held-out set during training (no `--random` flag)

## What Agents Will NOT Do
- Agents do NOT modify `repl_client.py` or `lean_runner.py` (infrastructure)
- Agents do NOT push to git
- Agents do NOT access the internet

## Timeline
- Setup (directory + copy): ~2 min
- Per agent × 5 runs: ~8 min each (4 workers × 500 theorems + worker init)
- Total wall time: ~50 min (all 5 agents in parallel, staggered 60s)

---
*Awaiting user approval before execution.*
