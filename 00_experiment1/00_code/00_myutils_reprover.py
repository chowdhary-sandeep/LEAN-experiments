"""Utility functions for creating Theorem objects from complete_proofs.json data."""

from pathlib import Path
from lean_dojo import Theorem, LeanGitRepo
import random
from collections import Counter


def extract_theorem_name(statement):
    """Extract just the theorem name, stopping at parameters/type annotations.
    
    Examples:
        "@[simp] lemma map_addZ : ..." -> "map_addZ"
        "commute_eps_left [Semiring R] (x : ...)" -> "commute_eps_left"
        "algHom_ext ⦃f g : ...⦄" -> "algHom_ext"
        "countable : Set.Countable ..." -> "countable"
        "theorem lintegral_iInf' : ..." -> "lintegral_iInf'"
        "isConj_iff₀ : ..." -> "isConj_iff₀"
    """
    if not statement:
        return ""
    
    # Normalize: replace newlines with spaces and strip
    statement = statement.replace('\n', ' ').replace('\r', ' ').strip()
    
    # Remove attributes like @[simp], @[ext], @[to_additive], etc.
    # Pattern: @[...] followed by optional whitespace
    import re
    statement = re.sub(r'@\[[^\]]+\]\s*', '', statement)
    
    # Remove prefixes (theorem, lemma, def, instance)
    for prefix in ["theorem", "lemma", "def", "instance"]:
        if statement.startswith(prefix):
            statement = statement[len(prefix):].strip()
            break
    
    # Extract name character by character, stopping at delimiters
    simple_name = ""
    i = 0
    while i < len(statement):
        char = statement[i]
        # Stop at these characters that indicate parameters/type annotations
        if char in ['[', '(', ':', '⦃']:
            break
        # Accumulate identifier characters:
        # - alphanumeric
        # - underscores, dots (for qualified names like Module.ext)
        # - primes (') for names like lintegral_iInf'
        # - Unicode characters (for subscripts like ₀, ₁, etc.)
        if char.isalnum() or char in ['_', '.', "'"] or (ord(char) > 127 and not char.isspace()):
            simple_name += char
        elif char.isspace():
            # If we've already started collecting a name, stop at whitespace
            if simple_name:
                break
        i += 1
    
    return simple_name.strip()


def create_theorem_from_complete_proof(proof_data, theorem_registry=None, edges=None,
                                        repo_url="https://github.com/leanprover-community/mathlib4", 
                                        commit="29dcec074de168ac2bf835a77ef68bbe069194c5"):
    """Create a Theorem object from complete_proofs.json data by mapping to theorem registry or edges.
    
    Args:
        proof_data: A list from complete_proofs.json, e.g., [theorem_statement, proof]
        theorem_registry: List of theorem dictionaries from theorem_registry_all.jsonl (preferred)
        edges: List of edge dictionaries from tripartite_edges_all.jsonl (fallback if registry not provided)
        repo_url: Repository URL
        commit: Commit hash
        
    Returns:
        Theorem object or None if not found
    """
    if not proof_data or len(proof_data) < 1:
        return None
    
    theorem_statement = proof_data[0].strip()
    
    # Extract simple name from statement
    simple_name = extract_theorem_name(theorem_statement)
    
    if not simple_name:
        return None
    
    # Prefer theorem_registry over edges (more complete and direct)
    if theorem_registry is not None:
        matching_theorems = []
        for thm_rec in theorem_registry:
            thm_name = thm_rec.get('theorem', '') or ''  # Handle None values
            if not thm_name:  # Skip if no theorem name
                continue
            # Check if the theorem name ends with the simple name (e.g., "RingTheory.countable" ends with "countable")
            if thm_name.endswith('.' + simple_name) or thm_name == simple_name:
                matching_theorems.append(thm_rec)
        
        if matching_theorems:
            # Use the first match
            thm_rec = matching_theorems[0]
            repo = LeanGitRepo(repo_url, commit)
            file_path = (thm_rec.get('file', '') or '').replace('\\', '/')  # Normalize Windows paths
            theorem_name = thm_rec.get('theorem', '') or ''  # Fully qualified name
            if not theorem_name or not file_path:
                return None
            
            return Theorem(repo=repo, file_path=Path(file_path), full_name=theorem_name)
    
    # Fallback to edges if registry not provided
    if edges is not None:
        matching_edges = []
        for edge in edges:
            edge_theorem = edge.get('theorem', '') or ''  # Handle None values
            if not edge_theorem:  # Skip if no theorem name
                continue
            # Check if the edge theorem name ends with the simple name
            if edge_theorem.endswith('.' + simple_name) or edge_theorem == simple_name:
                matching_edges.append(edge)
        
        if matching_edges:
            # Use the first match
            edge = matching_edges[0]
            repo = LeanGitRepo(repo_url, commit)
            file_path = (edge.get('file', '') or '').replace('\\', '/')  # Normalize Windows paths
            theorem_name = edge.get('theorem', '') or ''  # Fully qualified name from edges
            if not theorem_name or not file_path:
                return None
            
            return Theorem(repo=repo, file_path=Path(file_path), full_name=theorem_name)
    
    return None


def create_theorems_from_complete_proofs(complete_proofs_data, theorem_registry=None, edges=None,
                                          repo_url="https://github.com/leanprover-community/mathlib4", 
                                          commit="29dcec074de168ac2bf835a77ef68bbe069194c5"):
    """Create Theorem objects for all proofs in complete_proofs.json.
    
    Args:
        complete_proofs_data: List of proof data from complete_proofs.json
        theorem_registry: List of theorem dictionaries from theorem_registry_all.jsonl (preferred)
        edges: List of edge dictionaries from tripartite_edges_all.jsonl (fallback)
        repo_url: Repository URL
        commit: Commit hash
        
    Returns:
        List of (proof_data, theorem) tuples, where theorem may be None if not found
    """
    results = []
    for i, proof_data in enumerate(complete_proofs_data):
        theorem = create_theorem_from_complete_proof(proof_data, theorem_registry, edges, repo_url, commit)
        results.append((proof_data, theorem))
    
    return results


def debug_failed_matches(data, theorem_registry=None, edges=None, failed_indices=None, max_debug=10):
    """Debug failed matches by showing extracted names and potential matches.
    
    Args:
        data: List of proof data
        theorem_registry: List of theorem dictionaries from theorem_registry_all.jsonl (preferred)
        edges: List of edge dictionaries (fallback)
        failed_indices: List of indices that failed, or None to auto-detect
        max_debug: Maximum number of failures to debug
    """
    if failed_indices is None:
        # Find first few failures
        failed_indices = []
        for i, proof_data in enumerate(data[:max_debug * 10]):  # Check more to find failures
            if not create_theorem_from_complete_proof(proof_data, theorem_registry, edges):
                failed_indices.append(i)
                if len(failed_indices) >= max_debug:
                    break
    
    print(f"Debugging {len(failed_indices)} failed matches:\n")
    print("=" * 80)
    
    # Build search index
    search_list = theorem_registry if theorem_registry is not None else (edges or [])
    
    for idx in failed_indices[:max_debug]:
        proof_data = data[idx]
        theorem_statement = proof_data[0].strip() if proof_data else ""
        simple_name = extract_theorem_name(theorem_statement)
        
        print(f"\nIndex {idx}:")
        print(f"  Statement: {theorem_statement[:150]}...")
        print(f"  Extracted name: '{simple_name}'")
        
        # Search for similar names
        if simple_name and search_list:
            simple_name_base = simple_name.rstrip("'")
            similar = []
            for rec in search_list[:1000]:  # Check first 1000 for speed
                thm_name = rec.get('theorem', '')
                if not thm_name:
                    continue
                thm_base = thm_name.rstrip("'")
                if (simple_name_base in thm_base or thm_base.endswith('.' + simple_name_base) or 
                    simple_name_base in thm_base.split('.')[-1]):
                    similar.append(thm_name)
                    if len(similar) >= 5:
                        break
            if similar:
                print(f"  Similar names found: {similar}")
            else:
                print(f"  No similar names found in sample")
        print("-" * 80)


def test_matching_success(data, theorem_registry=None, edges=None, num_samples=1000, seed=42, debug_failures=False):
    """Test the matching success rate on random samples.
    
    Args:
        data: List of proof data from complete_proofs.json
        theorem_registry: List of theorem dictionaries from theorem_registry_all.jsonl (preferred)
        edges: List of edge dictionaries from tripartite_edges_all.jsonl (fallback)
        num_samples: Number of random samples to test
        seed: Random seed for reproducibility
        debug_failures: If True, show detailed debug info for failures
        
    Returns:
        Dictionary with success statistics
    """
    random.seed(seed)
    
    # Sample random indices
    if len(data) < num_samples:
        num_samples = len(data)
    
    random_indices = random.sample(range(len(data)), num_samples)
    
    success_count = 0
    failed_indices = []
    failed_names = []
    failed_statements = []
    
    print(f"Testing {num_samples} random samples...")
    print("=" * 60)
    
    for i, idx in enumerate(random_indices):
        proof_data = data[idx]
        theorem = create_theorem_from_complete_proof(proof_data, theorem_registry, edges)
        
        if theorem is not None:
            success_count += 1
        else:
            # Extract name for debugging
            theorem_statement = proof_data[0].strip() if proof_data else ""
            simple_name = extract_theorem_name(theorem_statement)
            failed_indices.append(idx)
            failed_names.append(simple_name)
            failed_statements.append(theorem_statement[:100] if theorem_statement else "")
        
        # Progress update
        if (i + 1) % 100 == 0:
            success_rate = (success_count / (i + 1)) * 100
            print(f"Progress: {i + 1}/{num_samples} | Success Rate: {success_rate:.1f}% | Success: {success_count}/{i + 1}")
    
    success_rate = (success_count / num_samples) * 100
    
    print("=" * 60)
    print(f"Final Results:")
    print(f"  Total tested: {num_samples}")
    print(f"  Successful matches: {success_count}")
    print(f"  Failed matches: {num_samples - success_count}")
    print(f"  Success rate: {success_rate:.1f}%")
    
    if failed_names:
        print(f"\n  Top 10 failed theorem names:")
        name_counts = Counter(failed_names)
        for name, count in name_counts.most_common(10):
            print(f"    '{name}': {count} failures")
        
        # Show debug info if requested
        if debug_failures and failed_indices:
            print(f"\n  Debugging first few failures:")
            debug_failed_matches(data, theorem_registry, edges, failed_indices[:5], max_debug=5)
    
    return {
        'total': num_samples,
        'success': success_count,
        'failed': num_samples - success_count,
        'success_rate': success_rate,
        'failed_indices': failed_indices[:20],
        'failed_names': failed_names[:20],  # First 20 for inspection
        'failed_statements': failed_statements[:20]
    }
