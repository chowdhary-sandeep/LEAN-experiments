"""
One-time fix: Recreate traced_theorems_unified_v2.jsonl with tactic/hypothesis premises
filtered out, using the existing JSONL (no traced repo needed).

This script will be UNNECESSARY to run in future: 00_build_unified_v2.py already
filters common tactics and hypothesis names when building premises, so any new
build from traced_repo will produce correct JSONL without running this script.
Use this only to fix an existing traced_theorems_unified_v2.jsonl that was
built before that filter was added.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from collections import defaultdict

# Same filter as in 00_build_unified_v2.py
TACTIC_OR_HYP_FILTER = frozenset({
    "simpa", "symm", "rwa", "mpr", "mp", "rfl", "refl", "simp", "rw", "apply", "exact",
    "intro", "intros", "refine", "cases", "rcases", "obtain", "induction", "constructor",
    "ring", "linarith", "omega", "trivial", "decide", "aesop", "ext", "congr", "have",
    "show", "from", "by", "left", "right", "split", "contrapose", "push_neg", "norm_num",
    "positivity", "polyrith", "nlinarith", "field_simp", "assumption", "tidy", "gcongr",
    "rel_simp", "erw", "era", "convert", "ac_rfl", "native_decide",
    "hx", "hf", "hs", "ha", "hb", "hc", "hd", "he", "hh", "hi", "hj", "hk", "hl", "hm",
    "hn", "ho", "hp", "hq", "hr", "ht", "hu", "hv", "hw", "hy", "hz", "h1", "h2", "h3",
    "ih", "IH", "this", "that",
})


def _is_tactic_or_hyp(name):
    """True if premise name (or its suffix) is a known tactic or hypothesis pattern."""
    if not name:
        return True
    suffix = (name.split(".")[-1] or "").strip()
    return suffix.lower() in TACTIC_OR_HYP_FILTER


def filter_premises(premises_list):
    """Return list of premises with tactic/hyp entries removed."""
    return [p for p in premises_list if not _is_tactic_or_hyp(p.get("full_name") or p.get("surface_name", ""))]


def fix_theorem_record(entry):
    """Filter premises and all_premises, recompute metrics and quality. Mutates entry in place."""
    tactics_list = entry.get("tactics") or []
    all_premises = defaultdict(lambda: {"count": 0, "tactics": [], "confidence_sum": 0.0})

    for idx, tac in enumerate(tactics_list):
        premises = tac.get("premises") or []
        filtered = filter_premises(premises)
        tac["premises"] = filtered

        for prem in filtered:
            fn = prem.get("full_name")
            if not fn or _is_tactic_or_hyp(fn):
                continue
            all_premises[fn]["count"] += 1
            all_premises[fn]["tactics"].append(idx)
            all_premises[fn]["confidence_sum"] += prem.get("confidence", 0)

    # Rebuild all_premises in output format
    entry["all_premises"] = {
        k: {
            "count": v["count"],
            "tactics": v["tactics"],
            "avg_confidence": round(v["confidence_sum"] / max(1, v["count"]), 4),
        }
        for k, v in all_premises.items()
    }

    # Recompute metrics
    metrics = entry.get("metrics") or {}
    metrics["num_premises"] = len(all_premises)
    metrics["avg_premise_confidence"] = (
        sum(v["confidence_sum"] / max(1, v["count"]) for v in all_premises.values()) / max(1, len(all_premises))
        if all_premises else 0
    )
    entry["metrics"] = metrics

    # Recompute quality.all_premises_resolved
    quality = entry.get("quality") or {}
    quality["all_premises_resolved"] = all(
        p.get("confidence", 0) > 0
        for t in tactics_list
        for p in t.get("premises", [])
    )
    entry["quality"] = quality

    return entry


def main():
    script_dir = Path(__file__).resolve().parent
    jsons_dir = script_dir / "jsons"
    data_file = jsons_dir / "traced_theorems_unified_v2.jsonl"

    if not data_file.exists():
        print(f"Error: {data_file} not found.", file=sys.stderr)
        sys.exit(1)

    print("Quick fix: filtering tactic/hypothesis premises from traced_theorems_unified_v2.jsonl")
    print(f"  Reading: {data_file}")
    n = 0
    with open(data_file, "r", encoding="utf-8") as f_in:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".jsonl", delete=False, dir=jsons_dir) as f_out:
            tmp_path = f_out.name
            for line in f_in:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fix_theorem_record(entry)
                f_out.write(json.dumps(entry, ensure_ascii=False) + "\n")
                n += 1

    os.replace(tmp_path, data_file)
    print(f"  Wrote {n:,} theorem records to {data_file}")
    print("Done.")


if __name__ == "__main__":
    main()
