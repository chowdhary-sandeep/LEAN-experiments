# Premise Inclusion Analysis: What Gets Included in the Graph?

## Questions

1. **Do we consider premises that occur in proofs of tactic-type theorem proofs and include them in the graph?**
2. **What about premises which are tactic-type proofs themselves?**

## Answer: YES to Both!

Based on analysis of the code flow:

---

## Flow Analysis

### Step 1: Building `traced_theorems_unified_v2.jsonl` (`00_build_unified_v2.py`)

**Lines 185-191**: Only theorems with `proof_type == "tactic"` are processed
```python
proof_type = entry.get("proof_type", "")
if proof_type != "tactic":
    theorems_skipped += 1
    if proof_type == "term":
        n_term += 1
    continue
```

**Lines 539-622**: For each tactic in the proof:
- Extract premises from tactic text using `extract_surface_premises()`
- Resolve premises using `PremiseResolver`
- Filter out tactics/hypotheses using `_is_tactic_or_hyp()`
- Aggregate all premises in `all_premises` dictionary

**Lines 599-606**: Premises are aggregated across all tactics:
```python
for prem in resolved_premises:
    fn = prem["full_name"]
    if _is_tactic_or_hyp(fn):
        continue
    all_premises[fn]["count"] += 1
    all_premises[fn]["tactics"].append(idx)
    all_premises[fn]["confidence_sum"] += prem.get("confidence", 0)
```

**Lines 647-654**: `all_premises` is saved in the theorem record:
```python
"all_premises": {
    k: {
        "count": v["count"],
        "tactics": v["tactics"],
        "avg_confidence": round(v["confidence_sum"] / max(1, v["count"]), 4)
    }
    for k, v in all_premises.items()
}
```

**Key Point**: `all_premises` contains **ALL resolved premises** extracted from the tactic proof, regardless of whether those premises are themselves theorems, definitions, or other types.

---

### Step 2: Building the Graph (`00_theorem_premise_network.py`)

**Lines 185-191**: Only processes theorems with `proof_type == "tactic"`:
```python
proof_type = entry.get("proof_type", "")
if proof_type != "tactic":
    theorems_skipped += 1
    if proof_type == "term":
        n_term += 1
    continue
```

**Lines 202-225**: For each theorem, processes its `all_premises`:
```python
# Get premises from all_premises dictionary
all_premises = entry.get("all_premises", {})

# Iterate over premise full_names (keys of all_premises dict)
for premise_full_name in all_premises.keys():
    if not premise_full_name or _is_tactic_or_hyp(premise_full_name):
        continue
    
    # Add premise node (source)
    # If node already exists as a theorem, keep it as theorem (theorem can be used as premise)
    if premise_full_name not in G:
        G.add_node(premise_full_name, node_type="premise")
        premises_seen.add(premise_full_name)
    elif G.nodes[premise_full_name].get("node_type") == "theorem":
        # This premise is actually a theorem - don't change its type
        premises_seen.add(premise_full_name)  # Still count as premise usage
    
    # Add edge: premise (source) -> theorem (target)
    if premise_full_name != theorem_full_name:
        G.add_edge(premise_full_name, theorem_full_name)
```

---

## Answer to Question 1

**Do we consider premises that occur in proofs of tactic-type theorem proofs and include them in the graph?**

**YES!** 

- Premises extracted from tactic proofs are included in `all_premises`
- `all_premises` is saved in `traced_theorems_unified_v2.jsonl`
- When building the graph, we iterate over `all_premises.keys()` and add edges
- **Every premise used in a tactic proof becomes a node and edge in the graph**

**Example Flow:**
1. Theorem `Nat.add_comm` has tactic proof: `by simp [add_zero, add_succ]`
2. Premises extracted: `["add_zero", "add_succ"]`
3. Resolved to: `["Nat.add_zero", "Nat.add_succ"]`
4. Saved in `all_premises` of `Nat.add_comm`
5. Graph building: Adds nodes `Nat.add_zero`, `Nat.add_succ` and edges `Nat.add_zero -> Nat.add_comm`, `Nat.add_succ -> Nat.add_comm`

---

## Answer to Question 2

**What about premises which are tactic-type proofs themselves?**

**YES! They are included, and handled specially:**

**Case 1: Premise is a theorem with tactic proof (already in graph as theorem)**
- When we encounter `premise_full_name` that already exists as a theorem node:
  - **The node keeps its `node_type="theorem"`** (line 217-219)
  - **The edge is still added**: `premise_theorem -> using_theorem` (line 225)
  - This creates a **theorem -> theorem** edge in the graph

**Case 2: Premise is a theorem with tactic proof (not yet in graph)**
- If the premise hasn't been seen yet:
  - It's added as `node_type="premise"` initially (line 215)
  - Later, when we process that theorem's entry:
    - It gets added as `node_type="theorem"` (line 199)
    - The node type is **not changed back** if it was already a premise (line 217-219 handles this)

**Key Insight**: The graph can have:
- **Premise -> Theorem** edges (premise used by theorem)
- **Theorem -> Theorem** edges (theorem used as premise by another theorem)

---

## Example Scenario

Consider three theorems:

1. **`Nat.add_zero`** (tactic proof): `by rfl`
   - Premises: `[]` (no premises)
   - Added to graph as theorem node

2. **`Nat.add_succ`** (tactic proof): `by simp [add_zero]`
   - Premises: `["Nat.add_zero"]`
   - `Nat.add_zero` is already a theorem node
   - Edge added: `Nat.add_zero -> Nat.add_succ` (theorem -> theorem)

3. **`Nat.add_comm`** (tactic proof): `by simp [add_zero, add_succ]`
   - Premises: `["Nat.add_zero", "Nat.add_succ"]`
   - Both are already theorem nodes
   - Edges added:
     - `Nat.add_zero -> Nat.add_comm` (theorem -> theorem)
     - `Nat.add_succ -> Nat.add_comm` (theorem -> theorem)

**Result**: The graph shows the dependency chain where theorems use other theorems as premises.

---

## What About Term Proofs?

**Term proofs are NOT processed:**

1. **In `00_build_unified_v2.py`**: 
   - Term proofs have `proof_type == "term"`
   - `proof_text = ""` (line 521)
   - No tactics, so no premises extracted

2. **In `00_theorem_premise_network.py`**:
   - Only `proof_type == "tactic"` theorems are processed (line 187)
   - Term proof theorems are skipped

**However**: If a theorem with a term proof is used as a premise in a tactic proof:
- It WILL be included in the graph (as a premise node)
- But its own premises won't be extracted (because it's a term proof)

---

## Summary

| Scenario | Included in Graph? | Node Type | Edge Type |
|----------|-------------------|-----------|-----------|
| Premise from tactic proof | ✅ YES | `premise` or `theorem` | `premise -> theorem` |
| Premise that is a theorem (tactic proof) | ✅ YES | `theorem` | `theorem -> theorem` |
| Premise that is a theorem (term proof) | ✅ YES (as premise) | `premise` or `theorem` | `premise/theorem -> theorem` |
| Theorem with term proof | ❌ NO (skipped) | N/A | N/A |
| Theorem with tactic proof | ✅ YES | `theorem` | Can be target of edges |

**Key Points:**
1. ✅ **All premises extracted from tactic proofs are included**
2. ✅ **Premises that are theorems (with tactic proofs) are included and create theorem->theorem edges**
3. ✅ **The graph captures the full dependency structure of tactic proofs**
4. ❌ **Term proofs don't contribute premises to the graph**

---

## Code References

- **Premise extraction**: `00_build_unified_v2.py` lines 359-378, 583-595
- **Premise aggregation**: `00_build_unified_v2.py` lines 599-606, 647-654
- **Graph building**: `00_theorem_premise_network.py` lines 185-225
- **Theorem-as-premise handling**: `00_theorem_premise_network.py` lines 213-219
