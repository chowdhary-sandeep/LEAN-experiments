"""
Create compact app_network_data.jsonl from traced_theorems_unified_v2.jsonl.

Keeps only fields needed by the dashboard:
  - full_name, statement, proof_text, proof_type
  - For tactic proofs: compact tactics (state_before, state_after, tactic, is_terminal)
    with states truncated to 150 chars (sufficient for DAG node IDs and tooltips)

Drops: file, position, namespace, open_namespaces, all_premises, metrics, quality,
       annotated_tactic, context, premises, num_goals_before, num_goals_after
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
INPUT = SCRIPT_DIR / "jsons" / "traced_theorems_unified_v2.jsonl"
OUTPUT = SCRIPT_DIR / "app" / "data" / "app_network_data.jsonl"

STATE_TRUNC = 150   # chars for state text (node ID dedup + tooltip)
TACTIC_TRUNC = 120  # chars for tactic string

def process(max_lines=None):
    total = tactic_count = other_count = 0
    out_bytes = 0

    with open(INPUT, "r", encoding="utf-8") as fin, \
         open(OUTPUT, "w", encoding="utf-8") as fout:

        for raw in fin:
            if not raw.strip():
                continue
            if max_lines and total >= max_lines:
                break

            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue

            full_name = entry.get("full_name", "")
            if not full_name:
                continue

            compact = {
                "full_name": full_name,
                "statement":  entry.get("statement",  ""),
                "proof_text": entry.get("proof_text", ""),
                "proof_type": entry.get("proof_type", "unknown"),
            }

            if entry.get("proof_type") == "tactic" and entry.get("tactics"):
                compact["tactics"] = [
                    {
                        "state_before": t.get("state_before", "")[:STATE_TRUNC],
                        "state_after":  t.get("state_after",  "")[:STATE_TRUNC],
                        "tactic":       t.get("tactic", "")[:TACTIC_TRUNC],
                        "is_terminal":  t.get("is_terminal", False),
                    }
                    for t in entry["tactics"]
                ]
                tactic_count += 1
            else:
                other_count += 1

            line = json.dumps(compact, ensure_ascii=False, separators=(",", ":")) + "\n"
            fout.write(line)
            out_bytes += len(line.encode("utf-8"))
            total += 1

            if total % 20000 == 0:
                print(f"  {total:,} theorems | {out_bytes/1024/1024:.1f} MB written so far", flush=True)

    print(f"\nDone.")
    print(f"  Total:          {total:,} theorems")
    print(f"  Tactic proofs:  {tactic_count:,}")
    print(f"  Other:          {other_count:,}")
    print(f"  Output size:    {out_bytes/1024/1024:.1f} MB")
    print(f"  Output path:    {OUTPUT}")
    return out_bytes

if __name__ == "__main__":
    sample = "--sample" in sys.argv   # run on first 5000 to estimate
    print(f"Processing {'first 5000' if sample else 'ALL'} theorems...")
    process(max_lines=5000 if sample else None)
