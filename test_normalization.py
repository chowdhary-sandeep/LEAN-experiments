"""Test normalization and resolution for the unresolved cases."""

import json
import sys
import importlib.util

# Load the module
module_name = 'myutils2'
file_path = '00_myutils2.py'
spec = importlib.util.spec_from_file_location(module_name, file_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)

from myutils2 import normalize_candidate, resolve_candidate, build_edges_index

# Test cases from the unresolved list
test_cases = [
    'MapsTo',
    'f.rootSet',
    'f.rootSet_finite',
    'le_aleph0_iff_set_countable',
    'mk_uLift',
    'this.countable_of_injOn'
]

print("Testing normalization:")
print("=" * 80)
for tok in test_cases:
    normed = normalize_candidate(tok)
    print(f"{tok:30s} -> {normed}")

# Load edges and test resolution
print("\n" + "=" * 80)
print("Loading edges...")
edges = []
with open("tripartite_edges_all.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            edges.append(json.loads(line))

print(f"Loaded {len(edges)} edges")
print("\nBuilding index...")
by_full, by_base, by_suffix = build_edges_index(edges)

print("\nTesting resolution:")
print("=" * 80)
for tok in test_cases:
    normed = normalize_candidate(tok)
    print(f"\n{tok}:")
    print(f"  Normalized to: {normed}")
    
    for nm in normed:
        best, matches = resolve_candidate(nm, by_full, by_base, by_suffix)
        if best:
            print(f"  ✓ {nm} -> {best.get('theorem', '')} ({best.get('file', '')})")
            break
        else:
            print(f"  ✗ {nm} -> No match")
    else:
        print(f"  ✗ All normalized names failed to match")
