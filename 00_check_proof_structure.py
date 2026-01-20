"""
Check the structure of complete_proofs.json to see what fields are available.
"""
import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("Loading complete_proofs.json...")
with open("complete_proofs.json", "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Type: {type(data)}")
print(f"Length: {len(data)}")

# Show first entry's structure
if isinstance(data, list) and len(data) > 0:
    first = data[0]
    print(f"\n--- FIRST ENTRY TYPE: {type(first)} ---")
    
    if isinstance(first, dict):
        print("Keys:", list(first.keys()))
        for key in first.keys():
            val = first[key]
            if isinstance(val, str) and len(val) > 200:
                print(f"  {key}: {val[:200]}...")
            elif isinstance(val, list) and len(val) > 5:
                print(f"  {key}: (list of {len(val)} items) {val[:3]}...")
            else:
                print(f"  {key}: {val}")
    elif isinstance(first, list):
        print(f"  It's a list with {len(first)} elements")
        for i, item in enumerate(first[:5]):
            if isinstance(item, str) and len(item) > 100:
                print(f"  [{i}]: {item[:100]}...")
            else:
                print(f"  [{i}]: {item}")
    else:
        print(f"  Value: {first}")

# Let's also check corpus.jsonl structure
print("\n\n" + "="*70)
print("CORPUS.JSONL STRUCTURE")
print("="*70)

with open("corpus.jsonl", "r", encoding="utf-8") as f:
    first_line = f.readline()
    corpus_entry = json.loads(first_line)
    
print("Keys:", list(corpus_entry.keys()))
for key in corpus_entry.keys():
    val = corpus_entry[key]
    if isinstance(val, str) and len(val) > 200:
        print(f"  {key}: {val[:200]}...")
    elif isinstance(val, list) and len(val) > 5:
        print(f"  {key}: (list of {len(val)} items)")
        if val:
            print(f"    First item: {val[0]}")
    else:
        print(f"  {key}: {val}")

# Check if corpus has traced_tactics with premise info
print("\n\n" + "="*70)
print("LOOKING FOR TRACED TACTICS IN CORPUS")
print("="*70)

with open("corpus.jsonl", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 5:
            break
        entry = json.loads(line)
        if "traced_tactics" in entry:
            tactics = entry["traced_tactics"]
            print(f"\nEntry {i}: has {len(tactics)} traced_tactics")
            if tactics:
                print(f"  First tactic keys: {tactics[0].keys() if isinstance(tactics[0], dict) else tactics[0]}")
                print(f"  First tactic: {tactics[0]}")

# Check tripartite_edges.jsonl
print("\n\n" + "="*70)
print("TRIPARTITE_EDGES.JSONL STRUCTURE")
print("="*70)

try:
    with open("tripartite_edges.jsonl", "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 3:
                break
            entry = json.loads(line)
            print(f"\nEntry {i}:")
            print(f"  Keys: {list(entry.keys())}")
            for key in entry.keys():
                val = entry[key]
                if isinstance(val, str) and len(val) > 100:
                    print(f"    {key}: {val[:100]}...")
                elif isinstance(val, list) and len(val) > 3:
                    print(f"    {key}: (list of {len(val)}) {val[:2]}...")
                else:
                    print(f"    {key}: {val}")
except FileNotFoundError:
    print("File not found")

# Check theorem_registry_all.jsonl
print("\n\n" + "="*70)
print("THEOREM_REGISTRY_ALL.JSONL STRUCTURE")
print("="*70)

try:
    with open("theorem_registry_all.jsonl", "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 3:
                break
            entry = json.loads(line)
            print(f"\nEntry {i}:")
            print(f"  Keys: {list(entry.keys())}")
            for key in entry.keys():
                val = entry[key]
                if isinstance(val, str) and len(val) > 100:
                    print(f"    {key}: {val[:100]}...")
                elif isinstance(val, list) and len(val) > 3:
                    print(f"    {key}: (list of {len(val)}) {val[:2]}...")
                elif isinstance(val, dict):
                    print(f"    {key}: (dict with keys {list(val.keys())[:5]})")
                else:
                    print(f"    {key}: {val}")
except FileNotFoundError:
    print("File not found")
