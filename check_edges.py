"""Check if specific theorem names exist in edges."""

import json

# Names to search for
search_names = [
    "Set.MapsTo",
    "Polynomial.rootSet",
    "Polynomial.rootSet_finite",
    "Cardinal.le_aleph0_iff_set_countable",
    "Cardinal.mk_uLift",
    "Set.MapsTo.countable_of_injOn"
]

print("Loading edges...")
edges = []
with open("tripartite_edges_all.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            edges.append(json.loads(line))

print(f"Loaded {len(edges)} edges\n")

# Build set of all theorem names
theorem_names = set()
for edge in edges:
    name = edge.get("theorem", "")
    if name:
        theorem_names.add(name)

print("Searching for names:")
print("=" * 80)
for name in search_names:
    if name in theorem_names:
        # Find the edge
        for edge in edges:
            if edge.get("theorem", "") == name:
                print(f"FOUND: {name}")
                print(f"  File: {edge.get('file', '')}")
                break
    else:
        print(f"X {name} - NOT FOUND")
        # Try partial matches
        matches = [n for n in theorem_names if name in n or n in name]
        if matches:
            print(f"  Similar names found: {matches[:5]}")
