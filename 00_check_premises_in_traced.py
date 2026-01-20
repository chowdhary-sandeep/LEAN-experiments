"""
Check tripartite_edges.jsonl for entries with non-empty premises to understand
how Lean resolves lemma names to their fully qualified forms.
"""
import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("="*70)
print("SEARCHING FOR ENTRIES WITH NON-EMPTY PREMISES")
print("="*70)

with open("tripartite_edges.jsonl", "r", encoding="utf-8") as f:
    found = 0
    total = 0
    for i, line in enumerate(f):
        total = i + 1
        entry = json.loads(line)
        if entry.get("premises") and len(entry["premises"]) > 0:
            print(f"\n--- Entry {i} ---")
            print(f"theorem: {entry['theorem']}")
            print(f"tactic: {entry['tactic']}")
            print(f"annotated_tactic: {entry.get('annotated_tactic', 'N/A')}")
            print(f"premises: {entry['premises']}")
            print(f"state_before:\n{entry['state_before'][:300]}...")
            found += 1
            if found >= 10:
                break

print(f"\n\nFound {found} entries with non-empty premises out of {total} checked")

# Also check if the annotated_tactic ever contains fully qualified names
print("\n\n" + "="*70)
print("CHECKING IF ANNOTATED_TACTIC CONTAINS QUALIFIED NAMES")
print("="*70)

with open("tripartite_edges.jsonl", "r", encoding="utf-8") as f:
    examples = []
    for i, line in enumerate(f):
        if i > 5000:
            break
        entry = json.loads(line)
        tactic = entry.get("tactic", "")
        annotated = entry.get("annotated_tactic", "")
        
        # Check if they differ
        if tactic != annotated:
            examples.append({
                "theorem": entry["theorem"],
                "tactic": tactic,
                "annotated": annotated
            })
            if len(examples) >= 10:
                break

print(f"Found {len(examples)} cases where tactic != annotated_tactic")
for ex in examples:
    print(f"\nTheorem: {ex['theorem']}")
    print(f"  tactic:    {ex['tactic'][:100]}")
    print(f"  annotated: {ex['annotated'][:100]}")

# Look for tactics using add_comm specifically
print("\n\n" + "="*70)
print("LOOKING FOR TACTICS USING 'add_comm'")
print("="*70)

with open("tripartite_edges.jsonl", "r", encoding="utf-8") as f:
    found = 0
    for i, line in enumerate(f):
        entry = json.loads(line)
        tactic = entry.get("tactic", "")
        if "add_comm" in tactic:
            print(f"\n--- Entry {i} ---")
            print(f"theorem: {entry['theorem']}")
            print(f"file: {entry.get('file', 'N/A')}")
            print(f"tactic: {tactic}")
            print(f"annotated_tactic: {entry.get('annotated_tactic', 'N/A')}")
            print(f"premises: {entry.get('premises', [])}")
            print(f"state_before (types):\n{entry['state_before'][:400]}")
            found += 1
            if found >= 5:
                break

print(f"\nFound {found} tactics using 'add_comm'")
