# Stage 1 TDG Schema

## Core principle

This TDG is built from proof states, not from raw tactic adjacency alone.

For each traced tactic application, the builder reconstructs:

- actual input goal: the active goal consumed by the tactic
- actual input hypotheses: explicitly referenced local hypotheses available in the active goal context
- actual input premises: resolved global premise references
- actual output goals: new goals appearing after the tactic, excluding preserved sibling goals
- actual output hypotheses: new local hypotheses introduced in produced goals

Each proof object is given a theorem-local id and a producer node. TDG edges are then induced by object flow:

- a goal edge exists when one tactic consumes a goal object produced by an earlier node
- a hypothesis edge exists when one tactic explicitly consumes a local hypothesis object produced earlier
- a premise edge exists when a tactic consumes a resolved premise object rooted at `in`

## Special nodes

- `in`: producer for initial proof-state goals/hypotheses and theorem-external premises
- `out`: terminal sink for completed proofs

## Edge labels

- `goal->goal`
- `<hyp_name>->hyp`
- `premise->arg`
- `proof_complete`

## Important limitation

This is still an approximation of the paper's formal input/output signatures because Lean traces do not expose tactic semantics directly. However, it is now proof-state-driven and object-level, rather than a tactic-sequence heuristic.
