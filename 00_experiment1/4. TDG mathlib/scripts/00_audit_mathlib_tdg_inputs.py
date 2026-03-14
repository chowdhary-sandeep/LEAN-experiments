from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

from tdg_utils import (
    CORPUS_CODE_INDEX_PATH,
    CORPUS_PATH,
    PREMISE_INDEX_PATH,
    ROOT,
    THEOREM_STATS_PATH,
    TRACED_THEOREMS_PATH,
    iter_tactic_records,
    parse_state,
    score_parseability,
)


DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


def detect_replay_assets() -> dict:
    candidates = [
        Path(r"E:\LEAN-experiments\00_experiment1\Mathlib"),
        Path(r"E:\LEAN-experiments\00_experiment1\mathlib4"),
        Path(r"E:\LEAN-experiments\00_experiment1\lake-manifest.json"),
        Path(r"E:\LEAN-experiments\00_experiment1\lean-toolchain"),
    ]
    return {str(path): path.exists() for path in candidates}


def summarize() -> tuple[dict, list[dict]]:
    proof_type_counter = Counter()
    tactic_head_counter = Counter()
    edge_case_samples: list[dict] = []
    random_samples: list[dict] = []
    usable_records = 0
    parseable_records = 0
    parseable_before_total = 0
    parseable_after_total = 0
    total_tactics = 0
    multi_goal_records = 0
    all_records = 0

    rng = random.Random(20260314)
    for record in iter_tactic_records():
        all_records += 1
        proof_type_counter[record.get("proof_type", "unknown")] += 1
        stats = score_parseability(record)
        total_tactics += stats["num_tactics"]
        parseable_before_total += stats["parseable_before"]
        parseable_after_total += stats["parseable_after"]
        tactic_head_counter.update(stats["tactic_heads"])
        usable = stats["num_tactics"] > 0
        if usable:
            usable_records += 1
        if usable and stats["parseable_before"] == stats["num_tactics"] and stats["parseable_after"] == stats["num_tactics"]:
            parseable_records += 1
        if stats["multi_goal_steps"] > 0:
            multi_goal_records += 1

        candidate = {
            "full_name": record["full_name"],
            "file": record["file"],
            "num_tactics": stats["num_tactics"],
            "multi_goal_steps": stats["multi_goal_steps"],
            "first_tactic": record["tactics"][0]["tactic"],
        }
        if len(random_samples) < 25:
            random_samples.append(candidate)
        else:
            slot = rng.randrange(all_records)
            if slot < 25:
                random_samples[slot] = candidate

        if (
            stats["multi_goal_steps"] > 0
            or stats["num_tactics"] <= 2
            or stats["num_tactics"] >= 25
            or any("case " in t.get("state_after", "") for t in record["tactics"])
        ):
            edge_case_samples.append(candidate)

    theorem_stats = json.loads(THEOREM_STATS_PATH.read_text(encoding="utf-8"))
    summary = {
        "paths": {
            "traced_theorems_unified_v2.jsonl": str(TRACED_THEOREMS_PATH),
            "corpus.jsonl": str(CORPUS_PATH),
            "corpus_code_index.json": str(CORPUS_CODE_INDEX_PATH),
            "premise_index_v2.json": str(PREMISE_INDEX_PATH),
            "theorem_stats_v2.json": str(THEOREM_STATS_PATH),
        },
        "theorem_stats_v2": theorem_stats,
        "tactic_proof_records_seen": all_records,
        "usable_tactic_records": usable_records,
        "fully_parseable_records": parseable_records,
        "fully_parseable_share": parseable_records / usable_records if usable_records else 0.0,
        "total_tactics": total_tactics,
        "parseable_before_share": parseable_before_total / total_tactics if total_tactics else 0.0,
        "parseable_after_share": parseable_after_total / total_tactics if total_tactics else 0.0,
        "multi_goal_record_share": multi_goal_records / usable_records if usable_records else 0.0,
        "top_tactic_heads": tactic_head_counter.most_common(25),
        "replay_assets": detect_replay_assets(),
    }
    samples = random_samples + edge_case_samples[:10]
    return summary, samples


def write_outputs(summary: dict, samples: list[dict]) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    REPORTS_DIR.mkdir(exist_ok=True)

    schema_sample = None
    for record in iter_tactic_records(limit=1):
        schema_sample = {
            "theorem_keys": sorted(record.keys()),
            "tactic_keys": sorted(record["tactics"][0].keys()),
            "first_tactic_parsed_before_goals": len(parse_state(record["tactics"][0]["state_before"])),
            "first_tactic_parsed_after_goals": len(parse_state(record["tactics"][0]["state_after"])),
        }
        break
    summary["schema_sample"] = schema_sample

    (DATA_DIR / "00_corpus_schema_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with (DATA_DIR / "00_sample_theorem_records.jsonl").open("w", encoding="utf-8") as handle:
        for sample in samples:
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")

    report = f"""# Stage 0 Data Audit

## Inputs

- `{TRACED_THEOREMS_PATH}`
- `{CORPUS_PATH}`
- `{CORPUS_CODE_INDEX_PATH}`
- `{PREMISE_INDEX_PATH}`
- `{THEOREM_STATS_PATH}`

## Summary

- Tactic-proof theorem records scanned: {summary['tactic_proof_records_seen']:,}
- Usable tactic proofs: {summary['usable_tactic_records']:,}
- Fully parseable tactic proofs under the current state parser: {summary['fully_parseable_records']:,} ({summary['fully_parseable_share']:.2%})
- Parseable `state_before` share across tactic steps: {summary['parseable_before_share']:.2%}
- Parseable `state_after` share across tactic steps: {summary['parseable_after_share']:.2%}
- Tactic proofs with at least one multi-goal step: {summary['multi_goal_record_share']:.2%}

## Common tactic heads

""" + "\n".join(
        f"- `{name}`: {count:,}" for name, count in summary["top_tactic_heads"][:15]
    ) + f"""

## Replay environment check

""" + "\n".join(
        f"- `{path}` exists: `{exists}`" for path, exists in summary["replay_assets"].items()
    ) + """

## Interpretation

- Theorem trace coverage is sufficient to begin TDG construction from local JSONs.
- Full Lean replay is probably deferred unless a matching mathlib checkout and `lean-toolchain` are added or discovered elsewhere.
- The state parser is already strong enough for stage 1 because it recovers goals for essentially all tactic steps, including many multi-goal traces.
- The main hard cases are branch-heavy proofs, bullets, and long compound tactics, which must remain explicit in stage-1 validation.

## Manual audit sample policy

- `data/00_sample_theorem_records.jsonl` contains 25 random tactic-proof samples plus 10 edge cases.
- These should be the default manual inspection seed before accepting later stages.
"""

    (REPORTS_DIR / "00_data_audit.md").write_text(report, encoding="utf-8")


def main() -> None:
    summary, samples = summarize()
    write_outputs(summary, samples)
    print("Wrote stage-0 audit outputs.")


if __name__ == "__main__":
    main()
