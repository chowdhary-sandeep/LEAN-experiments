import json

# Read line 76603 (0-indexed: 76602)
with open('traced_theorems_unified_v2.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()
    line = lines[76602]  # Line 76603 (0-indexed)

# Parse and pretty print with tabs
data = json.loads(line)
def keys(o, i=0):
    t = "    " * i
    if isinstance(o, dict):
        return "\n".join(
            f"{t}{k}" if not isinstance(v, (dict, list))
            else f"{t}{k}:\n{keys(v, i+1)}"
            for k, v in o.items()
        )
    if isinstance(o, list) and o:
        return keys(o[0], i)
    return ""

print(keys(data))