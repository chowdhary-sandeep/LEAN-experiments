# Stage 1 TDG Schema

## tdg_schema
```json
{
  "theorem": "theorem full name",
  "file": "source file path",
  "proof_text": "raw proof text",
  "num_tactics": "number of tactic nodes",
  "num_edges": "number of dependency edges",
  "nodes": "list of tactic nodes",
  "edges": "list of dependency edges"
}
```

## node_schema
```json
{
  "node_id": "unique node identifier",
  "theorem": "theorem full name",
  "file": "source file path",
  "tactic_index": "position in proof (0-based)",
  "raw_tactic": "raw tactic text",
  "normalized_tactic": "normalized tactic for matching",
  "tactic_head": "head tactic name (rw, simp, etc.)",
  "num_goals_before": "goals before execution",
  "num_goals_after": "goals after execution",
  "is_terminal": "whether this tactic closes proof",
  "state_before": "proof state before",
  "state_after": "proof state after",
  "context": "variables, hypotheses, typeclasses, goal",
  "premises": "list of premise references",
  "inputs": "inferred input hypotheses",
  "outputs": "inferred output hypotheses",
  "premise_refs": "premise names used",
  "target_changed": "whether goal target changed"
}
```

## edge_schema
```json
{
  "src_node": "source node ID",
  "dst_node": "destination node ID",
  "edge_type": "goal_to_goal|hyp_to_goal|premise_use",
  "label": "human-readable label",
  "confidence": "confidence score 0-1",
  "evidence": "why this edge exists"
}
```

