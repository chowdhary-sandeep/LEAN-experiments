"""
Build a unified traced theorems file that contains all information in one place.

Output: traced_theorems_unified.jsonl
- One line per theorem
- Each line contains: theorem info, all tactics, all premises, parsed context
- Self-contained: no need to join multiple files

This replaces the need for:
- tripartite_edges.jsonl
- theorem_registry_all.jsonl  
- complete_proofs.json
- corpus.jsonl (for premise lookup)

Usage:
    python 00_build_unified_traced.py

Requires: LeanDojo traced_repo already loaded (run from notebook or load separately)
"""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# =============================================================================
# CONFIGURATION
# =============================================================================
OUTPUT_FILE = "traced_theorems_unified.jsonl"
CORPUS_FILE = "corpus.jsonl"
TRIPARTITE_FILE = "tripartite_edges.jsonl"  # If we don't have traced_repo, use existing files

# =============================================================================
# HELPERS: Parse state_before into structured context
# =============================================================================
def parse_state_context(state_before: str) -> dict:
    """
    Parse Lean state_before string into structured context.
    
    Example input:
        α : Type u
        β : Type v
        inst✝ : Mul β
        f g : FreeMagma α →ₙ* β
        h : ⇑f ∘ of = ⇑g ∘ of
        x : FreeMagma α
        ⊢ f x = g x
    
    Returns:
        {
            "variables": {"α": "Type u", "β": "Type v", "x": "FreeMagma α", ...},
            "hypotheses": {"h": "⇑f ∘ of = ⇑g ∘ of"},
            "typeclasses": ["Mul β"],
            "goal": "f x = g x"
        }
    """
    result = {
        "variables": {},
        "hypotheses": {},
        "typeclasses": [],
        "goal": ""
    }
    
    if not state_before:
        return result
    
    lines = state_before.strip().split('\n')
    goal_started = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Goal line
        if line.startswith('⊢'):
            goal_started = True
            result["goal"] = line[1:].strip()
            continue
        
        if goal_started:
            # Multi-line goal
            result["goal"] += " " + line
            continue
        
        # Variable/hypothesis declaration: "name : Type" or "name name2 : Type"
        if ' : ' in line:
            # Handle typeclass instances (inst✝, inst✝¹, etc.)
            if line.startswith('inst'):
                # inst✝ : Mul β  →  typeclass "Mul β"
                typeclass = line.split(' : ', 1)[1] if ' : ' in line else line
                result["typeclasses"].append(typeclass)
                continue
            
            # Regular variable/hypothesis
            parts = line.split(' : ', 1)
            if len(parts) == 2:
                names_part, type_part = parts
                # Could be multiple names: "x y : Type"
                names = names_part.split()
                for name in names:
                    name = name.strip()
                    if name:
                        # Heuristic: hypotheses usually start with 'h' or contain '='
                        if name.startswith('h') and not name[1:2].isupper():
                            result["hypotheses"][name] = type_part.strip()
                        else:
                            result["variables"][name] = type_part.strip()
    
    return result


def extract_surface_premises_from_tactic(tactic: str) -> list:
    """
    Extract surface-level premise names from a tactic string.
    
    Examples:
        "simp [add_comm, mul_assoc]" → ["add_comm", "mul_assoc"]
        "rw [← Nat.add_comm]" → ["Nat.add_comm"]
        "exact h.symm" → ["h.symm"]
    """
    # Pattern to match identifiers (including qualified names)
    # But exclude common keywords
    KEYWORDS = {
        'by', 'fun', 'match', 'with', 'let', 'in', 'have', 'show', 'from',
        'intro', 'intros', 'apply', 'exact', 'refine', 'rw', 'simp', 'simp_rw',
        'cases', 'rcases', 'obtain', 'induction', 'constructor', 'ext',
        'ring', 'linarith', 'omega', 'decide', 'trivial', 'rfl', 'refl',
        'only', 'using', 'at', 'with', 'congr', 'conv', 'calc',
        'if', 'then', 'else', 'do', 'return', 'where',
    }
    
    # Find all identifiers (including dotted names)
    pattern = r'\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\b'
    matches = re.findall(pattern, tactic)
    
    # Filter out keywords and short names that are likely local
    premises = []
    for m in matches:
        if m.lower() in KEYWORDS:
            continue
        if len(m) == 1:  # Single letter = local variable
            continue
        premises.append(m)
    
    return premises


def resolve_premise_name(surface_name: str, context: dict, corpus_index: dict) -> dict:
    """
    Resolve a surface premise name to its fully qualified form.
    
    Args:
        surface_name: e.g., "add_comm"
        context: parsed state context with types
        corpus_index: {suffix: [full_names]}
    
    Returns:
        {"surface_name": "add_comm", "full_name": "Nat.add_comm", "resolved_by": "type"}
    """
    result = {
        "surface_name": surface_name,
        "full_name": surface_name,  # Default: assume already qualified
        "resolved_by": "default"
    }
    
    # Already fully qualified?
    if surface_name in corpus_index.get("_exact_", set()):
        result["full_name"] = surface_name
        result["resolved_by"] = "exact"
        return result
    
    # Get suffix
    suffix = surface_name.rsplit('.', 1)[-1] if '.' in surface_name else surface_name
    
    # Look up possible qualified names
    candidates = corpus_index.get(suffix, [])
    
    if not candidates:
        result["resolved_by"] = "not_found"
        return result
    
    if len(candidates) == 1:
        result["full_name"] = candidates[0]
        result["resolved_by"] = "unique"
        return result
    
    # Multiple candidates - try to resolve by type context
    # Heuristic: check if any variable type matches a namespace
    type_namespaces = set()
    for var_type in context.get("variables", {}).values():
        # Extract namespace hints from types like "ℕ" → Nat, "ℤ" → Int
        if "ℕ" in var_type or "Nat" in var_type:
            type_namespaces.add("Nat")
        elif "ℤ" in var_type or "Int" in var_type:
            type_namespaces.add("Int")
        elif "BitVec" in var_type:
            type_namespaces.add("BitVec")
        # Add more type → namespace mappings as needed
    
    # Try to find a candidate matching the type namespace
    for candidate in candidates:
        for ns in type_namespaces:
            if candidate.startswith(ns + "."):
                result["full_name"] = candidate
                result["resolved_by"] = f"type_hint:{ns}"
                return result
    
    # Could not resolve uniquely - return first candidate with note
    result["full_name"] = candidates[0]
    result["resolved_by"] = f"ambiguous:{len(candidates)}_candidates"
    result["candidates"] = candidates[:5]  # Store first few candidates
    
    return result


# =============================================================================
# BUILD CORPUS INDEX
# =============================================================================
def build_corpus_index(corpus_file: str) -> dict:
    """
    Build an index of corpus premises for name resolution.
    
    Returns:
        {
            "_exact_": set of all exact full names,
            "add_comm": ["Nat.add_comm", "Int.add_comm", ...],
            ...
        }
    """
    print(f"Building corpus index from {corpus_file}...")
    
    index = {"_exact_": set()}
    
    with open(corpus_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            for prem in entry.get("premises", []):
                full_name = prem.get("full_name", "")
                if not full_name:
                    continue
                    
                # Exact index
                index["_exact_"].add(full_name)
                
                # Suffix index
                suffix = full_name.rsplit('.', 1)[-1] if '.' in full_name else full_name
                if suffix not in index:
                    index[suffix] = []
                if full_name not in index[suffix]:
                    index[suffix].append(full_name)
    
    print(f"  Indexed {len(index['_exact_']):,} exact names")
    print(f"  Indexed {len(index) - 1:,} unique suffixes")
    
    return index


# =============================================================================
# MAIN: Build unified file from tripartite_edges (existing data)
# =============================================================================
def build_from_existing_files():
    """
    Build unified file from existing tripartite_edges.jsonl.
    Use this if we don't have traced_repo loaded.
    """
    
    # Build corpus index
    corpus_index = build_corpus_index(CORPUS_FILE)
    
    # Group edges by theorem
    print(f"\nGrouping tactics by theorem from {TRIPARTITE_FILE}...")
    theorems = defaultdict(lambda: {
        "full_name": "",
        "file": "",
        "statement": "",
        "proof_text": "",
        "proof_type": "tactic",
        "tactics": [],
        "all_premises": defaultdict(lambda: {"count": 0, "tactics": []}),
        "num_tactics": 0,
        "num_premises": 0,
        "has_unicode_issues": False
    })
    
    with open(TRIPARTITE_FILE, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(tqdm(f, desc="Reading edges")):
            if not line.strip():
                continue
            
            edge = json.loads(line)
            thm_name = edge.get("theorem", "")
            
            if not thm_name:
                continue
            
            # Initialize theorem record
            if not theorems[thm_name]["full_name"]:
                theorems[thm_name]["full_name"] = thm_name
                theorems[thm_name]["file"] = edge.get("file", "")
            
            # Parse state context
            state_before = edge.get("state_before", "")
            context = parse_state_context(state_before)
            
            # Get tactic info
            tactic_text = edge.get("tactic", "")
            annotated = edge.get("annotated_tactic", tactic_text)
            
            # Check for unicode issues
            if "â" in tactic_text or "ð" in tactic_text:
                theorems[thm_name]["has_unicode_issues"] = True
            
            # Extract and resolve premises
            # First try from LeanDojo's premise annotations
            raw_premises = edge.get("premises", [])
            resolved_premises = []
            
            for p in raw_premises:
                if isinstance(p, dict):
                    full_name = p.get("full_name") or p.get("fullName", "")
                    if full_name:
                        resolved_premises.append({
                            "surface_name": full_name.rsplit('.', 1)[-1],
                            "full_name": full_name,
                            "def_path": p.get("def_path") or p.get("defPath", ""),
                            "def_pos": p.get("def_pos") or p.get("defPos", []),
                            "resolved_by": "leandojo_annotation"
                        })
            
            # If no LeanDojo annotations, try to extract from tactic text
            if not resolved_premises:
                surface_names = extract_surface_premises_from_tactic(tactic_text)
                for sn in surface_names:
                    resolved = resolve_premise_name(sn, context, corpus_index)
                    resolved_premises.append(resolved)
            
            # Build tactic record
            tactic_idx = len(theorems[thm_name]["tactics"])
            tactic_record = {
                "index": tactic_idx,
                "tactic": tactic_text,
                "annotated_tactic": annotated,
                "state_before": state_before,
                "state_after": edge.get("state_after", ""),
                "context": context,
                "premises": resolved_premises
            }
            
            theorems[thm_name]["tactics"].append(tactic_record)
            
            # Update aggregated premises
            for prem in resolved_premises:
                fn = prem["full_name"]
                theorems[thm_name]["all_premises"][fn]["count"] += 1
                theorems[thm_name]["all_premises"][fn]["tactics"].append(tactic_idx)
    
    # Finalize and write
    print(f"\nWriting {len(theorems):,} theorems to {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for thm_name, thm_data in tqdm(theorems.items(), desc="Writing"):
            # Finalize counts
            thm_data["num_tactics"] = len(thm_data["tactics"])
            thm_data["num_premises"] = len(thm_data["all_premises"])
            
            # Convert defaultdict to regular dict
            thm_data["all_premises"] = dict(thm_data["all_premises"])
            
            f.write(json.dumps(thm_data, ensure_ascii=False) + "\n")
    
    print(f"\nDone! Created {OUTPUT_FILE}")
    print(f"  Theorems: {len(theorems):,}")
    print(f"  Total tactics: {sum(t['num_tactics'] for t in theorems.values()):,}")


# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    build_from_existing_files()
