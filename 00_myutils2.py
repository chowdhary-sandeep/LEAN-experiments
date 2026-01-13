"""Utility functions for running proofs and extracting lemma dependencies."""

import importlib
import sys
import re
import time
from collections import defaultdict

if "myutils_reprover" in sys.modules:
    importlib.reload(sys.modules["myutils_reprover"])

from myutils_reprover import (
    create_theorem_from_complete_proof,
    extract_theorem_name,
)

from lean_dojo import Dojo
from tqdm import tqdm


# -----------------------------
# Helpers: indexing + parsing
# -----------------------------

# Heuristic "name" regex (ASCII + many Unicode letters)
_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'.]*|[^\W\d_][\w'.]*", re.UNICODE)

# Common keywords/noise you don't want to treat as lemma names
_STOP = {
    "by", "fun", "match", "with", "let", "in", "have", "show", "from",
    "intro", "intros", "rintro", "refine", "apply", "exact", "rw", "simp",
    "simp_all", "simp?", "aesop", "assumption", "constructor",
    "forall", "exists", "True", "False",
    "_", "?", "??", "*",
}

def load_corpus_premises(corpus_path="corpus.jsonl"):
    """
    Load corpus.jsonl and flatten it into a list of premises.
    Each premise dict will have:
      - full_name: from premise entry
      - defPath: from file's path field (for compatibility with premise_registry format)
      - path: from file's path field (original corpus field)
      - All other fields from the premise entry (code, start, end, kind, etc.)
    
    Args:
        corpus_path: Path to corpus.jsonl file
        
    Returns:
        List of premise dictionaries compatible with build_premise_index
    """
    import json
    premises = []
    
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            file_entry = json.loads(line)
            file_path = file_entry.get("path", "")
            file_premises = file_entry.get("premises", [])
            
            # Flatten: add each premise with file path info
            for prem in file_premises:
                # Create a new dict with all premise fields
                prem_dict = dict(prem)
                # Add defPath for compatibility (use path from file entry)
                prem_dict["defPath"] = file_path
                # Also keep original path field
                prem_dict["path"] = file_path
                premises.append(prem_dict)
    
    return premises


def build_premise_index(premise_registry, max_k=6):
    """
    Index premise registry by:
      - full name
      - base name
      - last-k suffix (joined by '.')
    Uses premise_registry_unique.jsonl which contains all annotated premise constants.
    Can also work with corpus data loaded via load_corpus_premises().
    """
    by_full = {}
    by_base = defaultdict(list)
    by_suffix = defaultdict(list)

    seen = set()
    for prem in premise_registry:
        full = prem.get("full_name", "")
        if not full:
            continue
        # Dedupe by full_name (premise registry should already be unique, but be safe)
        if full in seen:
            continue
        seen.add(full)

        by_full[full] = prem
        parts = full.split(".")
        by_base[parts[-1]].append(prem)
        
        # suffix index for dotted candidates (cheap + very effective)
        for k in range(2, min(max_k, len(parts)) + 1):
            suf = ".".join(parts[-k:])
            by_suffix[suf].append(prem)

    return by_full, by_base, by_suffix


def split_tactic_blocks(tactics_text):
    """
    Turn a proof script into tactic *blocks* suitable for dojo.run_tac.

    Key fix: lines like
        suffices ... from
          this...
    must be sent together, otherwise Lean expects more input.
    """
    raw = [ln.rstrip("\n") for ln in tactics_text.splitlines()]

    # drop empty lines
    raw = [ln for ln in raw if ln.strip()]

    # skip initial `by`
    if raw and raw[0].strip() == "by":
        raw = raw[1:]

    if not raw:
        return []

    def indent(s):  # leading spaces
        return len(s) - len(s.lstrip(" "))

    blocks = []
    cur = [raw[0]]
    prev_indent = indent(raw[0])

    for ln in raw[1:]:
        ind = indent(ln)
        prev = cur[-1].strip()

        # Continuation rules
        prev_ends_open = prev.endswith(("from", ":=", "=>", "do"))
        deeper_indent = ind > prev_indent

        if deeper_indent or prev_ends_open:
            cur.append(ln)
        else:
            blocks.append("\n".join(cur))
            cur = [ln]

        prev_indent = ind

    if cur:
        blocks.append("\n".join(cur))

    return blocks


def extract_lemma_candidates(tac_block):
    """
    Extract "surface" lemma candidates from a tactic block:
    - identifiers in rewrite/simp lists: rw [a, b], simp [c], simp only [d]
    - head identifiers after apply/refine/exact/rw/suffices/have
    - dotted names like Subtype.coe_injective.injOn
    """
    s = tac_block

    cands = set()

    # (1) Things inside [...] lists
    for m in re.finditer(r"\[(.*?)\]", s, flags=re.DOTALL):
        inner = m.group(1)
        # split by commas at top level (best-effort)
        parts = [p.strip() for p in inner.split(",")]
        for p in parts:
            if not p or p in {"*", "_"}:
                continue
            # drop leading arrows etc.
            p = p.lstrip("←→")
            # take first "name-like" chunk from this part
            nm = _NAME_RE.findall(p)
            if nm:
                cands.add(nm[0])

    # (2) Head identifier after common keywords
    for kw in ["apply", "refine", "exact", "rw", "simp", "suffices", "have"]:
        # capture the token right after keyword
        for m in re.finditer(rf"\b{kw}\b\s+([^\s\(\{{\[]+)", s):
            tok = m.group(1).strip()
            tok = tok.lstrip("←→")
            # strip trailing punctuation like ".2" ".1" ","
            tok = re.sub(r"[,\)\]\}]+$", "", tok)
            tok = re.sub(r"\.\d+$", "", tok)
            # accept only name-like tokens
            nm = _NAME_RE.findall(tok)
            if nm:
                cands.add(nm[0])

    # (3) Any dotted chains in the block (Subtype.coe_injective.injOn etc.)
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z0-9_']+)+)\b", s):
        cands.add(m.group(1))

    # filter noise
    out = set()
    for x in cands:
        if not x:
            continue
        if x in _STOP:
            continue
        # drop purely numeric / punctuation
        if all(ch.isdigit() or ch in "._'" for ch in x):
            continue
        out.add(x)

    return out


def _strip_dir_selectors(name: str) -> str:
    """Strip directional selectors: mem_rootSet.2 -> mem_rootSet"""
    return re.sub(r"\.\d+$", "", name)


def normalize_candidate(tok: str) -> list:
    """
    Turn surface tokens into plausible global names (try list in order).
    Uses heuristics based on naming patterns and common namespaces.
    """
    tok = tok.strip()
    tok = _strip_dir_selectors(tok)

    # local projections / not global lemmas - filter these out
    if tok.endswith(".coe_prop") or tok == "x.coe_prop":
        return []  # explicitly ignore as "local term"

    # local proof-term dot syntax -> global lemma
    # this.countable_of_injOn -> Set.MapsTo.countable_of_injOn (not Set.Countable!)
    if tok.startswith("this."):
        lemma_name = tok[5:]  # remove "this."
        if lemma_name == "countable_of_injOn":
            return ["Set.MapsTo.countable_of_injOn"]  # Correct namespace per user feedback
        # generic: try common namespaces for "this.*" patterns
        return [f"Set.MapsTo.{lemma_name}", tok]

    # Subtype.coe_injective.injOn -> Function.Injective.injOn (method projection)
    if tok.endswith(".injOn"):
        return ["Function.Injective.injOn", tok]

    # f.rootSet / f.rootSet_finite -> Polynomial.*
    # Handle both local variable prefixes (f.rootSet) and unqualified (rootSet)
    if "rootSet" in tok:
        # Extract the actual lemma name (after last dot if present)
        if "." in tok:
            lemma_part = tok.split(".")[-1]
        else:
            lemma_part = tok
            
        if lemma_part == "rootSet_finite" or tok.endswith(".rootSet_finite"):
            return ["Polynomial.rootSet_finite", tok]
        elif lemma_part == "rootSet" or tok.endswith(".rootSet"):
            return ["Polynomial.rootSet", tok]
        # catch-all for any rootSet variant
        return [f"Polynomial.{lemma_part}", tok]

    # Cardinal-related patterns (aleph0, mk_uLift, etc.)
    # Check before other patterns to avoid conflicts
    if tok == "mk_uLift":
        return ["Cardinal.mk_uLift", "mk_uLift"]
    elif "aleph0" in tok.lower():
        return [f"Cardinal.{tok}", tok]
    elif tok.startswith("mk_") and "uLift" in tok:
        return [f"Cardinal.{tok}", tok]

    # Set-related patterns
    if tok == "MapsTo":
        return ["Set.MapsTo", "MapsTo"]
    if "MapsTo" in tok and "." not in tok:
        return [f"Set.{tok}", tok]

    # common unqualified tokens with known namespaces
    if tok == "le_aleph0_iff_set_countable":
        return ["Cardinal.le_aleph0_iff_set_countable", tok]

    # Heuristic: if token contains common namespace indicators, try those namespaces
    # This is a fallback for patterns we haven't explicitly handled
    candidates = [tok]  # always try as-is first
    
    # Pattern-based heuristics for unqualified names
    if "." not in tok:
        # rootSet* -> Polynomial.*
        if "rootset" in tok.lower():
            candidates.append(f"Polynomial.{tok}")
        # *_aleph0_* -> Cardinal.*
        elif "aleph0" in tok.lower() or "aleph" in tok.lower():
            candidates.append(f"Cardinal.{tok}")
        # mk_* -> Cardinal.* (if not already handled)
        elif tok.startswith("mk_"):
            candidates.append(f"Cardinal.{tok}")
        # Capitalized unqualified names often belong to Set namespace
        elif tok[0].isupper() and len(tok) > 1:
            candidates.append(f"Set.{tok}")

    return candidates


def resolve_candidate(token, by_full, by_base, by_suffix, prefer_file=None):
    """
    Resolution order (mirrors theorem matching):
      1) exact full match
      2) exact suffix match (for dotted tokens)
      3) base-name match (fallback)
    Returns: (best_premise or None, matches list)
    """
    # exact full match
    if token in by_full:
        return by_full[token], [by_full[token]]

    # suffix match (only meaningful for dotted tokens)
    if "." in token and token in by_suffix:
        matches = list(by_suffix[token])
        return matches[0], matches

    # base fallback
    base = token.split(".")[-1]
    matches = list(by_base.get(base, []))
    if not matches:
        return None, []

    # prefer same file if provided (premise registry has defPath)
    if prefer_file is not None:
        pf = str(prefer_file).replace("\\", "/")
        same = [p for p in matches if p.get("defPath", "").replace("\\", "/") == pf]
        if same:
            matches = same

    # deterministic tie-break: smallest namespace
    matches = sorted(matches, key=lambda p: (p.get("full_name", "").count("."), p.get("full_name", "")))
    return matches[0], matches


# -----------------------------
# Main: run tactics + collect deps
# -----------------------------

def run_proof_tactics(
    i,
    data,
    theorem_registry,
    premise_registry,
    printing=True,
    print_states=False,
    show_new_lemmas_per_step=True,
):
    """
    Runs proof i in LeanDojo, while extracting "surface lemma candidates"
    and resolving them to Mathlib premise full-names via `premise_registry`.

    Args:
        i: Proof index in data
        data: List of proof data from complete_proofs.json
        theorem_registry: List of theorem dictionaries from theorem_registry_all.jsonl (for theorem matching)
        premise_registry: List of premise dictionaries from premise_registry_unique.jsonl (for premise resolution)
        printing: Whether to print progress
        print_states: Whether to print proof states
        show_new_lemmas_per_step: Whether to show new lemmas per step

    Returns a dict with:
      - success
      - theorem_full_name
      - theorem_file
      - tactic_blocks
      - candidates
      - resolved (best matches)
      - unresolved
      - ambiguous (candidates with >1 match)
    """
    if printing:
        print(f"Running tactics for proof index: {i}")

    # Use theorem_registry for theorem matching
    theorem = create_theorem_from_complete_proof(data[i], theorem_registry)
    if theorem is None:
        if printing:
            print("Could not map proof to a Mathlib theorem via theorem_registry.")
        return {"success": False, "reason": "no_theorem_match"}

    if printing:
        print(f"Theorem: {theorem}")

    # Build indices once per call (if you do this in a loop, build once outside!)
    # Use premise_registry for premise resolution
    by_full, by_base, by_suffix = build_premise_index(premise_registry)

    tactics_text = data[i][1]
    tactic_blocks = split_tactic_blocks(tactics_text)

    # Track lemma candidates across the run
    all_candidates = set()
    resolved_best = {}     # cand -> best edge
    ambiguous = {}         # cand -> list[premises]
    unresolved = set()
    normalized_names = {}  # cand -> list of normalized names tried (for debugging)

    # Use context manager to avoid leaked Dojo processes
    try:
        with Dojo(theorem) as (dojo, state):
            cur_state = state
            success = True

            pbar = tqdm(
                tactic_blocks,
                desc=f"proof[{i}] tactics",
                unit="tac",
                disable=not printing,
            )

            for idx, tac_block in enumerate(pbar):
                if printing:
                    print(f"\n>>> Applying tactic block #{idx}:")
                    print(tac_block)

                # Extract + resolve candidates BEFORE running (useful even on failure)
                cands = extract_lemma_candidates(tac_block)
                new_cands = cands - all_candidates
                all_candidates |= cands

                newly_resolved = []
                newly_ambiguous = []
                newly_unresolved = []

                for c in sorted(new_cands):
                    normed = normalize_candidate(c)
                    normalized_names[c] = normed  # Store normalized names for reporting

                    if not normed:
                        # local term / ignore
                        continue

                    best_edge = None
                    all_matches = []
                    chosen_name = None

                    for nm in normed:
                        best_edge, all_matches = resolve_candidate(
                            nm, by_full, by_base, by_suffix, prefer_file=theorem.file_path
                        )
                        if best_edge is not None:
                            chosen_name = nm
                            break

                    if best_edge is None:
                        unresolved.add(c)
                        newly_unresolved.append(c)
                    else:
                        resolved_best[c] = {
                            "chosen_name": chosen_name,
                            "full_name": best_edge.get("full_name", ""),
                            "defPath": best_edge.get("defPath", ""),
                        }

                        # dedup match list (should already be deduped, but safe)
                        uniq = {(m.get("full_name", ""), m.get("defPath", "")) for m in all_matches}
                        if len(uniq) > 1:
                            ambiguous[c] = [{"full_name": n, "defPath": p} for (n, p) in sorted(uniq)]
                            newly_ambiguous.append((c, len(uniq)))

                        newly_resolved.append((c, best_edge.get("full_name", ""), best_edge.get("defPath", "")))

                if printing and show_new_lemmas_per_step and (newly_resolved or newly_unresolved or newly_ambiguous):
                    print(">>> New lemma candidates observed:")
                    for c, full, fpath in newly_resolved[:20]:
                        print(f"    + {c}  ->  {full}   ({fpath})")
                    if len(newly_resolved) > 20:
                        print(f"    ... +{len(newly_resolved) - 20} more resolved")

                    for c, k in newly_ambiguous[:20]:
                        print(f"    ? {c}  (ambiguous: {k} matches)")

                    for c in newly_unresolved[:20]:
                        normed = normalized_names.get(c, [])
                        if normed:
                            print(f"    - {c}  (unresolved, tried: {normed})")
                        else:
                            print(f"    - {c}  (unresolved)")
                    if len(newly_unresolved) > 20:
                        print(f"    ... +{len(newly_unresolved) - 20} more unresolved")

                # Now actually run the tactic block
                try:
                    cur_state = dojo.run_tac(cur_state, tac_block)
                    if printing and print_states:
                        print(cur_state)
                except Exception as e:
                    if printing:
                        print(f"Error running tactic block #{idx}: {e}")
                    success = False
                    break

    except Exception as e:
        if printing:
            print(f"Error creating/entering Dojo for theorem {theorem}: {e}")
        return {"success": False, "reason": "dojo_init_failed", "error": str(e)}

    if printing:
        print("\n" + "=" * 80)
        print(f"Summary for proof index {i}")
        print(f"  success: {success}")
        print(f"  theorem: {theorem.full_name}")
        print(f"  file:    {theorem.file_path}")
        print(f"  tactic blocks: {len(tactic_blocks)}")
        print(f"  unique candidates: {len(all_candidates)}")
        print(f"  resolved: {len(resolved_best)}")
        print(f"  unresolved: {len(unresolved)}")
        print(f"  ambiguous: {len(ambiguous)}")
        if unresolved:
            print("  unresolved (sample):", sorted(list(unresolved))[:25])
            print("  normalized names tried (sample):")
            for c in sorted(list(unresolved))[:10]:
                normed = normalized_names.get(c, [])
                if normed:
                    print(f"    {c} -> {normed}")
        if ambiguous:
            print("  ambiguous (sample):", [(k, len(v)) for k, v in list(ambiguous.items())[:10]])

    return {
        "success": success,
        "theorem_full_name": theorem.full_name,
        "theorem_file": str(theorem.file_path),
        "tactic_blocks": tactic_blocks,
        "candidates": sorted(all_candidates),
        "resolved_best": {k: v for k, v in resolved_best.items()},
        "unresolved": sorted(unresolved),
        "unresolved_normalized": {c: normalized_names.get(c, []) for c in unresolved},  # Show what we tried
        "ambiguous": {k: [{"full_name": p.get("full_name", ""), "defPath": p.get("defPath", "")} for p in v] for k, v in ambiguous.items()},
    }


def extract_all_premises(i, data, theorem_registry=None, premise_registry=None, printing=False):
    """
    Extract all raw lemma/def candidates from a theorem's proof as they appear in tactics.
    No normalization or resolution - just raw extraction.
    
    Args:
        i: Proof index in data
        data: List of proof data from complete_proofs.json
        theorem_registry: Optional (not used, kept for compatibility)
        premise_registry: Optional (not used, kept for compatibility)
        printing: Whether to print progress
        
    Returns:
        List of tuples (tactic_block, candidate) in order of appearance, or None if data invalid.
        - tactic_block: The tactic block where the candidate appears
        - candidate: Raw candidate name as extracted from the tactic
    """
    if printing:
        print(f"Extracting raw candidates for proof index: {i}")
    
    if i >= len(data) or len(data[i]) < 2:
        if printing:
            print("Invalid proof data.")
        return None
    
    # Get proof text and split into tactic blocks
    tactics_text = data[i][1]
    tactic_blocks = split_tactic_blocks(tactics_text)
    
    if printing:
        print(f"Found {len(tactic_blocks)} tactic blocks")
    
    # Extract all raw candidates in order
    all_candidates_list = []  # List of (tactic_block, candidate) tuples
    
    for tac_block in tactic_blocks:
        # Extract candidates from this block (raw, no processing)
        cands = extract_lemma_candidates(tac_block)
        
        # Add each candidate with its tactic block
        for c in sorted(cands):  # Sort for consistent ordering
            all_candidates_list.append((tac_block, c))
    
    if printing:
        unique_candidates = len(set(c for _, c in all_candidates_list))
        print(f"Extracted {len(all_candidates_list)} total candidate usages")
        print(f"Found {unique_candidates} unique candidates")
    
    # Return list of tuples in order of appearance
    return all_candidates_list
