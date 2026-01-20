"""Check which add_comm variants exist in corpus."""
import json

names = set()
with open("corpus.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        entry = json.loads(line)
        for p in entry.get("premises", []):
            names.add(p.get("full_name", ""))

add_comm_variants = sorted([n for n in names if "add_comm" in n.lower()])
print(f"Found {len(add_comm_variants)} variants containing 'add_comm':")
for v in add_comm_variants[:30]:
    print(f"  {v}")
