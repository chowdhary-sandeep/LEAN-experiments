"""
Build unified traced theorems file (v2) with ALL available information.

This module extracts from LeanDojo's traced_repo:
- Theorem statements
- Proof text
- Position info
- Tactics with full state context
- Resolved premises with confidence scores
- Complexity metrics
- Dependency information

Output: traced_theorems_unified_v2.jsonl

Usage from notebook:
    from 00_build_unified_v2 import build_unified_v2
    build_unified_v2(traced_repo)
"""

import json
import re
import sys
import time
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime

# Handle encoding for Windows
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except:
    pass

# =============================================================================
# CONFIGURATION
# =============================================================================
OUTPUT_FILE = "traced_theorems_unified_v2.jsonl"
CORPUS_FILE = "corpus.jsonl"
STATS_FILE = "theorem_stats_v2.json"
PREMISE_INDEX_FILE = "premise_index_v2.json"

# =============================================================================
# HELPERS: Parse state_before into structured context
# =============================================================================
def parse_state_context(state_before: str) -> dict:
    """
    Parse Lean state_before string into structured context.
    
    Returns:
        {
            "variables": {"n": {"type": "ℕ", "is_hypothesis": False}, ...},
            "hypotheses": {"h": "proof_term", ...},
            "typeclasses": ["Mul β", ...],
            "goal": "n + m = m + n",
            "goal_type": "Eq"  # extracted from goal
        }
    """
    result = {
        "variables": {},
        "hypotheses": {},
        "typeclasses": [],
        "goal": "",
        "goal_type": ""
    }
    
    if not state_before:
        return result
    
    lines = state_before.strip().split('\n')
    goal_started = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Goal line starts with ⊢
        if line.startswith('⊢'):
            goal_started = True
            result["goal"] = line[1:].strip()
            # Try to extract goal type (first identifier before space or paren)
            goal_match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)', result["goal"])
            if goal_match:
                result["goal_type"] = goal_match.group(1)
            continue
        
        if goal_started:
            # Multi-line goal continuation
            result["goal"] += " " + line
            continue
        
        # Variable/hypothesis declaration: "name : Type"
        if ' : ' in line:
            # Handle typeclass instances (inst✝, inst✝¹, etc.)
            if line.startswith('inst') or '✝' in line.split(' : ')[0]:
                typeclass = line.split(' : ', 1)[1] if ' : ' in line else line
                result["typeclasses"].append(typeclass)
                continue
            
            parts = line.split(' : ', 1)
            if len(parts) == 2:
                names_part, type_part = parts
                names = names_part.split()
                
                for name in names:
                    name = name.strip()
                    if not name:
                        continue
                    
                    # Heuristic: hypotheses start with h (lowercase) followed by non-uppercase
                    # or the type contains = or ≤ or other relations
                    is_hyp = (
                        (name.startswith('h') and len(name) > 1 and not name[1].isupper()) or
                        any(sym in type_part for sym in ['=', '≤', '≥', '<', '>', '∈', '⊆', '∣'])
                    )
                    
                    if is_hyp:
                        result["hypotheses"][name] = type_part.strip()
                    else:
                        result["variables"][name] = {
                            "type": type_part.strip(),
                            "is_hypothesis": False
                        }
    
    return result


def extract_namespace_from_path(file_path: str) -> str:
    """Extract likely namespace from file path."""
    # Mathlib/Algebra/Group/Defs.lean -> Mathlib.Algebra.Group.Defs
    path = str(file_path)
    if path.endswith('.lean'):
        path = path[:-5]
    # Replace separators
    ns = path.replace('\\', '.').replace('/', '.')
    # Remove common prefixes
    for prefix in ['traced_mathlib4.mathlib4.', 'mathlib4.', '.lake.packages.']:
        if ns.startswith(prefix):
            ns = ns[len(prefix):]
    return ns


def infer_open_namespaces(file_path: str, theorem_name: str) -> list:
    """Infer likely open namespaces from file path and theorem name."""
    namespaces = []
    
    if not file_path and not theorem_name:
        return namespaces
    
    # From file path
    if file_path:
        ns = extract_namespace_from_path(file_path)
        parts = ns.split('.') if ns else []
        
        # Add each level of the namespace hierarchy
        for i in range(len(parts)):
            if parts[:i+1]:
                namespaces.append('.'.join(parts[:i+1]))
    
    # From theorem name - extract namespace prefix
    if theorem_name and '.' in theorem_name:
        thm_ns = theorem_name.rsplit('.', 1)[0]
        if thm_ns and thm_ns not in namespaces:
            namespaces.append(thm_ns)
    
    return namespaces


# =============================================================================
# CORPUS EXPORT (so all 4 files can be built in output_dir)
# =============================================================================
def _export_corpus(traced_repo, output_dir: str) -> None:
    """Export premise definitions to output_dir/corpus.jsonl so resolver can load it."""
    import os
    import networkx as nx
    oup_path = os.path.join(output_dir, CORPUS_FILE)
    num_premises = 0
    with open(oup_path, "w", encoding="utf-8") as oup:
        G = traced_repo.traced_files_graph
        tf_nodes = list(reversed(list(nx.topological_sort(G))))
        for tf_node in tf_nodes:
            tf = G.nodes[tf_node]["traced_file"]
            imports = [str(_) for _ in G.successors(tf_node)]
            premises = tf.get_premise_definitions()
            num_premises += len(premises)
            oup.write(json.dumps({"path": str(tf.path), "imports": imports, "premises": premises}, ensure_ascii=False) + "\n")
    print(f"  Exported {num_premises:,} premises to {oup_path}")


# =============================================================================
# PREMISE RESOLUTION
# =============================================================================
class PremiseResolver:
    """Resolve surface premise names to fully qualified names."""
    
    def __init__(self, corpus_file: str = CORPUS_FILE):
        self.corpus_index = {"_exact_": set()}
        self.by_suffix = defaultdict(list)
        self._load_corpus(corpus_file)
    
    def _load_corpus(self, corpus_file: str):
        """Load corpus and build indices."""
        print(f"Loading corpus from {corpus_file}...")
        
        try:
            with open(corpus_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    for prem in entry.get("premises", []):
                        full_name = prem.get("full_name", "")
                        if not full_name:
                            continue
                        
                        self.corpus_index["_exact_"].add(full_name)
                        
                        # Index by suffix
                        suffix = full_name.rsplit('.', 1)[-1] if '.' in full_name else full_name
                        if full_name not in self.by_suffix[suffix]:
                            self.by_suffix[suffix].append(full_name)
            
            print(f"  Indexed {len(self.corpus_index['_exact_']):,} premises")
            print(f"  {len(self.by_suffix):,} unique suffixes")
        except FileNotFoundError:
            print(f"  WARNING: {corpus_file} not found, resolution will be limited")
    
    def resolve(self, surface_name: str, context: dict, open_namespaces: list, 
                leandojo_hint: str = None) -> dict:
        """
        Resolve a surface name to fully qualified form.
        
        Returns dict with: full_name, resolution_method, confidence, candidates (if ambiguous)
        """
        # Priority 1: LeanDojo annotation
        if leandojo_hint and leandojo_hint in self.corpus_index["_exact_"]:
            return {
                "surface_name": surface_name,
                "full_name": leandojo_hint,
                "resolution_method": "leandojo_annotation",
                "confidence": 1.0
            }
        
        # Priority 2: Already fully qualified
        if surface_name in self.corpus_index["_exact_"]:
            return {
                "surface_name": surface_name,
                "full_name": surface_name,
                "resolution_method": "exact_match",
                "confidence": 1.0
            }
        
        # Get suffix for lookup
        suffix = surface_name.rsplit('.', 1)[-1] if '.' in surface_name else surface_name
        candidates = self.by_suffix.get(suffix, [])
        
        if not candidates:
            return {
                "surface_name": surface_name,
                "full_name": surface_name,
                "resolution_method": "not_found",
                "confidence": 0.0
            }
        
        # Priority 3: Namespace context match
        for ns in open_namespaces:
            candidate = f"{ns}.{surface_name}"
            if candidate in self.corpus_index["_exact_"]:
                return {
                    "surface_name": surface_name,
                    "full_name": candidate,
                    "resolution_method": "namespace_match",
                    "confidence": 0.95
                }
        
        # Priority 4: Type-based resolution
        type_namespaces = self._infer_namespaces_from_types(context)
        for ns in type_namespaces:
            for cand in candidates:
                if cand.startswith(ns + "."):
                    return {
                        "surface_name": surface_name,
                        "full_name": cand,
                        "resolution_method": f"type_inference:{ns}",
                        "confidence": 0.8
                    }
        
        # Priority 5: Unique suffix match
        if len(candidates) == 1:
            return {
                "surface_name": surface_name,
                "full_name": candidates[0],
                "resolution_method": "unique_suffix",
                "confidence": 0.6
            }
        
        # Priority 6: Ambiguous - return first with candidates list
        return {
            "surface_name": surface_name,
            "full_name": candidates[0],
            "resolution_method": "ambiguous",
            "confidence": 0.3,
            "candidates": candidates[:5]
        }
    
    def _infer_namespaces_from_types(self, context: dict) -> set:
        """Infer possible namespaces from variable types in context."""
        namespaces = set()
        
        all_types = []
        for var_info in context.get("variables", {}).values():
            if isinstance(var_info, dict):
                all_types.append(var_info.get("type", ""))
            else:
                all_types.append(str(var_info))
        
        for type_str in all_types:
            # Common type → namespace mappings
            if "ℕ" in type_str or "Nat" in type_str:
                namespaces.add("Nat")
            if "ℤ" in type_str or "Int" in type_str:
                namespaces.add("Int")
            if "ℚ" in type_str or "Rat" in type_str:
                namespaces.add("Rat")
            if "ℝ" in type_str or "Real" in type_str:
                namespaces.add("Real")
            if "List" in type_str:
                namespaces.add("List")
            if "Set" in type_str:
                namespaces.add("Set")
            if "Finset" in type_str:
                namespaces.add("Finset")
            if "Array" in type_str:
                namespaces.add("Array")
            if "BitVec" in type_str:
                namespaces.add("BitVec")
            if "Matrix" in type_str:
                namespaces.add("Matrix")
            if "Polynomial" in type_str:
                namespaces.add("Polynomial")
        
        return namespaces


# =============================================================================
# EXTRACT PREMISES FROM TACTIC
# =============================================================================
TACTIC_KEYWORDS = {
    'by', 'fun', 'match', 'with', 'let', 'in', 'have', 'show', 'from',
    'intro', 'intros', 'rintro', 'apply', 'exact', 'refine', 'rw', 'simp',
    'simp_all', 'simp_rw', 'cases', 'rcases', 'obtain', 'induction', 
    'constructor', 'ext', 'ring', 'linarith', 'omega', 'decide', 'trivial',
    'rfl', 'refl', 'only', 'using', 'at', 'with', 'congr', 'conv', 'calc',
    'if', 'then', 'else', 'do', 'return', 'where', 'classical', 'aesop',
    'norm_num', 'positivity', 'polyrith', 'nlinarith', 'field_simp',
    'push_neg', 'contrapose', 'by_contra', 'by_cases', 'split', 'left', 'right',
}

def extract_surface_premises(tactic: str) -> list:
    """Extract potential premise names from tactic string."""
    # Pattern for identifiers (including qualified names)
    pattern = r'\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\b'
    matches = re.findall(pattern, tactic)
    
    premises = []
    for m in matches:
        # Skip keywords
        if m.lower() in TACTIC_KEYWORDS:
            continue
        # Skip single letters (local variables)
        if len(m) == 1:
            continue
        # Skip common local hypothesis names
        if re.match(r'^h\d*$', m) or m in {'this', 'ih', 'IH'}:
            continue
        premises.append(m)
    
    return list(dict.fromkeys(premises))  # Dedupe preserving order


# =============================================================================
# MAIN BUILD FUNCTION
# =============================================================================
def build_unified_v2(traced_repo, output_file: str = None,
                     corpus_file: str = CORPUS_FILE,
                     max_theorems: int = None,
                     output_dir: str = None):
    """
    Build unified traced theorems file from LeanDojo traced_repo.
    
    Args:
        traced_repo: LeanDojo TracedRepo object
        output_file: Output JSONL file path (default: under output_dir or cwd)
        corpus_file: Corpus file for premise resolution
        max_theorems: Limit number of theorems (for testing)
        output_dir: If set, output_file and stats file are written under this dir (e.g. "00_experiment1" or ".")
    
    Returns:
        dict with statistics
    """
    from tqdm import tqdm
    import os

    if output_dir is not None:
        os.makedirs(output_dir, exist_ok=True)
        # Save all 4 files into output_dir/jsons/ (e.g. 00_experiment1/jsons/)
        jsons_dir = os.path.join(output_dir, "jsons")
        os.makedirs(jsons_dir, exist_ok=True)
        out_file = os.path.join(jsons_dir, OUTPUT_FILE) if output_file is None else output_file
        stats_file = os.path.join(jsons_dir, STATS_FILE)
        corpus_file_used = os.path.join(jsons_dir, CORPUS_FILE)
    else:
        out_file = output_file if output_file is not None else OUTPUT_FILE
        stats_file = STATS_FILE
        corpus_file_used = corpus_file

    print("="*70)
    print("BUILDING UNIFIED TRACED THEOREMS (v2)")
    print("="*70)
    if output_dir:
        print(f"Output directory: {output_dir}")
        # Build corpus.jsonl in output_dir/jsons/ first (file 1 of 4)
        print("\nExporting corpus (corpus.jsonl)...")
        _export_corpus(traced_repo, jsons_dir)

    # Initialize resolver (uses corpus in output_dir when output_dir is set)
    resolver = PremiseResolver(corpus_file_used)
    
    # Collect all traced theorems
    print("\nCollecting traced theorems...")
    all_theorems = list(traced_repo.get_traced_theorems())
    print(f"  Found {len(all_theorems):,} theorems")
    
    if max_theorems:
        all_theorems = all_theorems[:max_theorems]
        print(f"  Limited to {max_theorems} for testing")
    
    # Statistics
    stats = {
        "total_theorems": 0,
        "tactic_proofs": 0,
        "term_proofs": 0,
        "total_tactics": 0,
        "total_premises": 0,
        "resolution_methods": Counter(),
        "high_confidence": 0,
        "low_confidence": 0,
        "created": datetime.now().isoformat(),
        "source_commit": str(getattr(traced_repo, 'commit', 'unknown')),
    }
    
    # Process theorems
    print(f"\nProcessing theorems...")
    t0 = time.time()
    
    with open(out_file, "w", encoding="utf-8") as f:
        for tt in tqdm(all_theorems, desc="Building unified"):
            stats["total_theorems"] += 1
            
            # Basic info
            try:
                thm_name = tt.theorem.full_name
                if thm_name is None:
                    thm_name = ""
            except:
                thm_name = ""
            
            try:
                file_path = str(tt.theorem.file_path)
            except:
                file_path = ""
            
            # Skip theorems without names
            if not thm_name:
                continue
            
            # Get theorem statement
            try:
                statement = tt.get_theorem_statement()
            except:
                statement = ""
            
            # Get proof info
            has_tactic = tt.has_tactic_proof() if hasattr(tt, 'has_tactic_proof') else False
            
            if has_tactic:
                stats["tactic_proofs"] += 1
                proof_type = "tactic"
                try:
                    proof_text = tt.get_tactic_proof()
                except:
                    proof_text = ""
            else:
                stats["term_proofs"] += 1
                proof_type = "term"
                proof_text = ""
            
            # Position info
            try:
                start_pos = {"line": tt.theorem.start[0], "column": tt.theorem.start[1]}
                end_pos = {"line": tt.theorem.end[0], "column": tt.theorem.end[1]}
            except:
                start_pos = {"line": 0, "column": 0}
                end_pos = {"line": 0, "column": 0}
            
            # Namespace info
            namespace = thm_name.rsplit('.', 1)[0] if thm_name and '.' in thm_name else ""
            open_namespaces = infer_open_namespaces(file_path, thm_name) if thm_name else []
            
            # Process tactics
            tactics_list = []
            all_premises = defaultdict(lambda: {"count": 0, "tactics": [], "confidence_sum": 0})
            
            if has_tactic:
                try:
                    traced_tactics = list(tt.get_traced_tactics())
                except:
                    traced_tactics = []
                
                for idx, tac in enumerate(traced_tactics):
                    stats["total_tactics"] += 1
                    
                    # Get tactic info
                    tactic_str = tac.tactic if hasattr(tac, 'tactic') else str(tac)
                    state_before = tac.state_before if hasattr(tac, 'state_before') else ""
                    state_after = tac.state_after if hasattr(tac, 'state_after') else ""
                    
                    # Get annotated tactic and LeanDojo premises
                    try:
                        annotated, leandojo_premises = tac.get_annotated_tactic()
                    except:
                        annotated = tactic_str
                        leandojo_premises = []
                    
                    # Parse context
                    context = parse_state_context(state_before)
                    
                    # Resolve premises
                    resolved_premises = []
                    
                    # First: use LeanDojo annotations if available
                    if leandojo_premises:
                        for p in leandojo_premises:
                            if isinstance(p, dict):
                                full_name = p.get('full_name') or p.get('fullName', '')
                                if full_name:
                                    prem_info = {
                                        "surface_name": full_name.rsplit('.', 1)[-1],
                                        "full_name": full_name,
                                        "def_path": p.get('def_path') or p.get('defPath', ''),
                                        "resolution_method": "leandojo_annotation",
                                        "confidence": 1.0
                                    }
                                    resolved_premises.append(prem_info)
                                    stats["resolution_methods"]["leandojo_annotation"] += 1
                                    stats["high_confidence"] += 1
                    
                    # Second: extract from tactic text and resolve
                    if not resolved_premises:
                        surface_names = extract_surface_premises(tactic_str)
                        for sn in surface_names:
                            resolved = resolver.resolve(sn, context, open_namespaces)
                            resolved_premises.append(resolved)
                            stats["resolution_methods"][resolved["resolution_method"]] += 1
                            if resolved["confidence"] >= 0.6:
                                stats["high_confidence"] += 1
                            else:
                                stats["low_confidence"] += 1
                    
                    stats["total_premises"] += len(resolved_premises)
                    
                    # Update all_premises aggregation
                    for prem in resolved_premises:
                        fn = prem["full_name"]
                        all_premises[fn]["count"] += 1
                        all_premises[fn]["tactics"].append(idx)
                        all_premises[fn]["confidence_sum"] += prem.get("confidence", 0)
                    
                    # Build tactic record
                    # NOTE: Tactics are in PROOF ORDER - tactic[i].state_after ≈ tactic[i+1].state_before
                    tactic_record = {
                        "index": idx,                           # Position in proof (0-indexed)
                        "tactic": tactic_str,                   # Raw tactic string
                        "annotated_tactic": annotated,          # With <a>premise</a> tags
                        "state_before": state_before,           # Proof state BEFORE this tactic
                        "state_after": state_after,             # Proof state AFTER this tactic
                        "context": context,                     # Parsed variables/hypotheses/goal
                        "premises": resolved_premises,          # Resolved premise names
                        "is_terminal": state_after.strip() in ["no goals", "goals accomplished"],
                        "num_goals_before": state_before.count("⊢"),  # How many goals before
                        "num_goals_after": state_after.count("⊢") if state_after.strip() not in ["no goals", "goals accomplished"] else 0
                    }
                    tactics_list.append(tactic_record)
            
            # Compute metrics
            metrics = {
                "num_tactics": len(tactics_list),
                "num_premises": len(all_premises),
                "statement_length": len(statement),
                "proof_length": len(proof_text) if proof_text else 0,
                "avg_premise_confidence": (
                    sum(p["confidence_sum"] / max(1, p["count"]) for p in all_premises.values()) 
                    / max(1, len(all_premises))
                ) if all_premises else 0
            }
            
            # Build theorem record
            theorem_record = {
                "full_name": thm_name,
                "file": file_path,
                "position": {"start": start_pos, "end": end_pos},
                "namespace": namespace,
                "open_namespaces": open_namespaces,
                "statement": statement,
                "proof_type": proof_type,
                "proof_text": proof_text,
                "tactics": tactics_list,
                "all_premises": {
                    k: {
                        "count": v["count"],
                        "tactics": v["tactics"],
                        "avg_confidence": round(v["confidence_sum"] / max(1, v["count"]), 4)
                    }
                    for k, v in all_premises.items()
                },
                "metrics": metrics,
                "quality": {
                    "has_statement": bool(statement),
                    "has_proof": bool(proof_text),
                    "fully_traced": len(tactics_list) > 0 if has_tactic else True,
                    "all_premises_resolved": all(
                        p.get("confidence", 0) > 0 
                        for t in tactics_list 
                        for p in t.get("premises", [])
                    )
                }
            }
            
            f.write(json.dumps(theorem_record, ensure_ascii=False) + "\n")
    
    elapsed = time.time() - t0
    
    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("="*70)
    print(f"Output: {out_file}")
    print(f"Time: {elapsed:.1f}s")
    print(f"\nTheorems: {stats['total_theorems']:,}")
    print(f"  Tactic proofs: {stats['tactic_proofs']:,}")
    print(f"  Term proofs: {stats['term_proofs']:,}")
    print(f"\nTactics: {stats['total_tactics']:,}")
    print(f"Premises: {stats['total_premises']:,}")
    print(f"\nResolution breakdown:")
    for method, count in stats["resolution_methods"].most_common():
        pct = count / max(1, stats["total_premises"]) * 100
        print(f"  {method}: {count:,} ({pct:.1f}%)")
    print(f"\nConfidence:")
    print(f"  High (>=0.6): {stats['high_confidence']:,}")
    print(f"  Low (<0.6): {stats['low_confidence']:,}")
    
    # Save stats (file 3 of 4)
    with open(stats_file, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"\nStats saved to: {stats_file}")

    # Save premise index in output_dir/jsons/ when set (file 4 of 4)
    if output_dir is not None:
        premise_index_path = os.path.join(jsons_dir, PREMISE_INDEX_FILE)
        with open(premise_index_path, "w", encoding="utf-8") as f:
            json.dump({
                "premises": sorted(resolver.corpus_index["_exact_"]),
                "by_suffix": {k: v for k, v in resolver.by_suffix.items()},
                "num_premises": len(resolver.corpus_index["_exact_"]),
                "num_suffixes": len(resolver.by_suffix),
            }, f, indent=2, ensure_ascii=False)
        print(f"Premise index saved to: {premise_index_path}")
    
    return stats


# =============================================================================
# COMMAND LINE ENTRY
# =============================================================================
if __name__ == "__main__":
    print("This module is meant to be imported into a notebook with traced_repo.")
    print("Usage:")
    print("  from 00_build_unified_v2 import build_unified_v2")
    print("  stats = build_unified_v2(traced_repo)")
