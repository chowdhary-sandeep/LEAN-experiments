from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(r"E:\LEAN-experiments\00_experiment1\4. TDG mathlib")
JSONS_DIR = Path(r"E:\LEAN-experiments\00_experiment1\jsons")
TRACED_THEOREMS_PATH = JSONS_DIR / "traced_theorems_unified_v2.jsonl"
CORPUS_PATH = JSONS_DIR / "corpus.jsonl"
CORPUS_CODE_INDEX_PATH = JSONS_DIR / "corpus_code_index.json"
PREMISE_INDEX_PATH = JSONS_DIR / "premise_index_v2.json"
THEOREM_STATS_PATH = JSONS_DIR / "theorem_stats_v2.json"


TACTIC_KEYWORDS = {
    "all_goals",
    "aesop",
    "apply",
    "assumption",
    "by",
    "calc",
    "case",
    "cases",
    "change",
    "choose",
    "constructor",
    "contrapose",
    "congr",
    "convert",
    "exact",
    "ext",
    "field_simp",
    "first",
    "fun",
    "guard_hyp",
    "guard_target",
    "have",
    "induction",
    "intro",
    "intros",
    "left",
    "let",
    "linarith",
    "nlinarith",
    "norm_num",
    "omega",
    "obtain",
    "positivity",
    "rcases",
    "refine",
    "rename_i",
    "repeat",
    "revert",
    "rfl",
    "rintro",
    "right",
    "ring",
    "rw",
    "rwa",
    "set",
    "show",
    "simp",
    "simpa",
    "skip",
    "specialize",
    "split",
    "split_ifs",
    "subst",
    "suffices",
    "symm",
    "tidy",
    "trivial",
}

IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_']*")
DECL_RE = re.compile(r"^([^\s:][^:]*?)\s*:\s*(.*)$")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_goal_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_decl_names(name_blob: str) -> list[str]:
    return [part.strip() for part in name_blob.split() if part.strip()]


@dataclass
class GoalBlock:
    index: int
    case_label: str | None
    hypotheses: list[str]
    hypothesis_names: list[str]
    hypothesis_map: dict[str, str]
    target: str

    @property
    def signature(self) -> str:
        return normalize_goal_text(self.target)

    @property
    def detailed_signature(self) -> str:
        prefix = f"{self.case_label}|" if self.case_label else ""
        hyp_sig = "|".join(sorted(self.hypothesis_names))
        return f"{prefix}{hyp_sig}|{self.signature}"


def _split_state_into_segments(lines: list[str]) -> list[list[str]]:
    case_positions = [i for i, line in enumerate(lines) if line.startswith("case ")]
    if not case_positions:
        return [lines] if lines else []
    segments = []
    for idx, start in enumerate(case_positions):
        end = case_positions[idx + 1] if idx + 1 < len(case_positions) else len(lines)
        segments.append(lines[start:end])
    return segments


def parse_goal_block(segment: list[str], index: int) -> GoalBlock | None:
    if not segment:
        return None
    case_label = None
    lines = list(segment)
    if lines[0].startswith("case "):
        case_label = lines[0][5:].strip()
        lines = lines[1:]
    turnstile_index = None
    for i, line in enumerate(lines):
        if "⊢" in line:
            turnstile_index = i
            break
    if turnstile_index is None:
        return None
    hypothesis_lines = [line for line in lines[:turnstile_index] if line.strip()]
    target_lines = lines[turnstile_index:]
    first_target = target_lines[0]
    target_lines[0] = first_target.split("⊢", 1)[1].strip()
    target = "\n".join(line.rstrip() for line in target_lines).strip()
    hypothesis_names: list[str] = []
    hypothesis_map: dict[str, str] = {}
    for line in hypothesis_lines:
        match = DECL_RE.match(line)
        if not match:
            continue
        decl_names = normalize_decl_names(match.group(1))
        decl_type = normalize_goal_text(match.group(2))
        hypothesis_names.extend(decl_names)
        for name in decl_names:
            hypothesis_map[name] = decl_type
    return GoalBlock(
        index=index,
        case_label=case_label,
        hypotheses=hypothesis_lines,
        hypothesis_names=hypothesis_names,
        hypothesis_map=hypothesis_map,
        target=target,
    )


def parse_state(state: str) -> list[GoalBlock]:
    normalized = state.strip() if state else ""
    if not normalized or normalized == "no goals":
        return []
    goals: list[GoalBlock] = []
    raw_segments = [segment for segment in re.split(r"\n\s*\n", state.replace("\r\n", "\n")) if segment.strip()]
    if len(raw_segments) > 1:
        for index, raw_segment in enumerate(raw_segments):
            lines = [line.rstrip() for line in raw_segment.split("\n") if line.strip()]
            goal = parse_goal_block(lines, index)
            if goal is not None:
                goals.append(goal)
        return goals
    lines = [line.rstrip() for line in state.replace("\r\n", "\n").split("\n") if line.strip()]
    for index, segment in enumerate(_split_state_into_segments(lines)):
        goal = parse_goal_block(segment, index)
        if goal is not None:
            goals.append(goal)
    return goals


def extract_tactic_head(tactic: str) -> str:
    cleaned = tactic.strip()
    while cleaned.startswith(("·", "|", ";")):
        cleaned = cleaned[1:].lstrip()
    if cleaned.startswith("case "):
        return "case"
    match = IDENT_RE.search(cleaned)
    return match.group(0) if match else "unknown"


def extract_identifier_refs(tactic: str) -> list[str]:
    refs: list[str] = []
    for token in IDENT_RE.findall(tactic):
        if token in TACTIC_KEYWORDS:
            continue
        refs.append(token)
    return refs


def load_records(limit: int | None = None) -> Iterable[dict]:
    count = 0
    with TRACED_THEOREMS_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            yield json.loads(line)
            count += 1
            if limit is not None and count >= limit:
                return


def iter_tactic_records(limit: int | None = None) -> Iterable[dict]:
    yielded = 0
    for record in load_records():
        if record.get("proof_type") != "tactic" or not record.get("tactics"):
            continue
        yield record
        yielded += 1
        if limit is not None and yielded >= limit:
            return


def score_parseability(record: dict) -> dict:
    tactics = record.get("tactics", [])
    parseable_before = 0
    parseable_after = 0
    multi_goal_steps = 0
    tactic_head_counter: Counter[str] = Counter()
    for tactic in tactics:
        tactic_head_counter[extract_tactic_head(tactic.get("tactic", ""))] += 1
        before_goals = parse_state(tactic.get("state_before", ""))
        after_goals = parse_state(tactic.get("state_after", ""))
        if before_goals:
            parseable_before += 1
        if tactic.get("state_after", "").strip() in {"", "no goals"} or after_goals:
            parseable_after += 1
        if max(tactic.get("num_goals_before", 0), tactic.get("num_goals_after", 0)) > 1:
            multi_goal_steps += 1
    return {
        "num_tactics": len(tactics),
        "parseable_before": parseable_before,
        "parseable_after": parseable_after,
        "multi_goal_steps": multi_goal_steps,
        "tactic_heads": tactic_head_counter,
    }


def goal_match_key(goal: GoalBlock) -> tuple[str | None, str]:
    return (goal.case_label, goal.signature)


def theorem_slug(full_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", full_name)
    return safe[:180]
