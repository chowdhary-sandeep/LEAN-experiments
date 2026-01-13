"""
Premises Extraction Code
========================
Extracts tripartite edges with AST-identified premises and definition excerpts
from LeanDojo traced repositories.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from tqdm import tqdm

# Note: This script requires `traced_repo` to be defined.
# Load it using:
#   from lean_dojo import *
#   traced_repo = TracedRepo.load_from_disk(path_to_traced_repo)


# -----------------------------
# 0) TARGET_FILES (your filter)
# -----------------------------
def get_target_files(traced_repo, filter_pattern="Mathlib\\Algebra"):
    """
    Get target files matching the filter pattern.
    
    Args:
        traced_repo: TracedRepo object
        filter_pattern: String pattern to match in file paths
        
    Returns:
        List of file paths (strings)
    """
    TARGET_FILES = []
    for traced_file in traced_repo.traced_files:
        p = str(traced_file.lean_file.path)
        if (filter_pattern in p) or (filter_pattern.replace("\\", "/") in p):
            TARGET_FILES.append(p)
    return TARGET_FILES


# -----------------------------
# 1) Helpers: JSON-safe positions + file reading + span slicing
# -----------------------------
def pos_to_json(pos):
    """Convert LeanDojo Pos (or similar) to JSON-serializable dict."""
    if pos is None:
        return None
    # LeanDojo Pos typically has .line and .column
    line = getattr(pos, "line", None)
    col  = getattr(pos, "column", None)
    if line is None and col is None:
        # fallback: string
        return str(pos)
    return {"line": int(line), "column": int(col)}


def read_text_cached(path: Path, cache: dict[Path, str]) -> str:
    """Read text file with caching."""
    if path in cache:
        return cache[path]
    txt = path.read_text(encoding="utf-8", errors="replace")
    cache[path] = txt
    return txt


def line_offsets(text: str):
    """Return list of starting indices for each 1-indexed line."""
    offs = [0]
    i = 0
    while True:
        j = text.find("\n", i)
        if j == -1:
            break
        offs.append(j + 1)
        i = j + 1
    return offs  # line 1 -> offs[0], line 2 -> offs[1], ...


def slice_span(text: str, start, end) -> str | None:
    """Slice text using start/end that may be Pos objects or dicts {line,column}."""
    if start is None or end is None:
        return None

    # Normalize start/end into (line, col)
    if isinstance(start, dict):
        sl, sc = start.get("line"), start.get("column")
    else:
        sl, sc = getattr(start, "line", None), getattr(start, "column", None)

    if isinstance(end, dict):
        el, ec = end.get("line"), end.get("column")
    else:
        el, ec = getattr(end, "line", None), getattr(end, "column", None)

    if None in (sl, sc, el, ec):
        return None

    offs = line_offsets(text)
    # guard against out-of-range lines
    if sl < 1 or el < 1 or sl > len(offs) or el > len(offs):
        return None

    s_idx = offs[sl - 1] + sc
    e_idx = offs[el - 1] + ec
    if not (0 <= s_idx <= e_idx <= len(text)):
        return None
    return text[s_idx:e_idx]


def compact_excerpt(s: str, max_chars: int = 280) -> str:
    """Compact a string excerpt, collapsing whitespace."""
    s = " ".join(s.split())  # collapse whitespace
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 1] + "…"


# -----------------------------
# 2) AST walker + Ident extraction (duck-typed)
# -----------------------------
def iter_ast_nodes(node):
    """Iterate over all AST nodes in a tree."""
    if node is None:
        return
    stack = [node]
    seen = set()
    while stack:
        cur = stack.pop()
        if cur is None:
            continue
        oid = id(cur)
        if oid in seen:
            continue
        seen.add(oid)
        yield cur

        if hasattr(cur, "children"):
            try:
                ch = getattr(cur, "children")
                if ch:
                    stack.extend(reversed(list(ch)))
                continue
            except Exception:
                pass

        try:
            attrs = vars(cur)
        except TypeError:
            attrs = {}
        for v in attrs.values():
            if v is None:
                continue
            if isinstance(v, (list, tuple)):
                for x in reversed(v):
                    if hasattr(x, "__class__"):
                        stack.append(x)
            else:
                if hasattr(v, "__class__"):
                    stack.append(v)


def extract_idents_from_tactic_ast(tac_ast):
    """Extract identifier nodes from a tactic AST."""
    out = []
    for n in iter_ast_nodes(tac_ast):
        cls = n.__class__.__name__
        has_full = hasattr(n, "full_name") or hasattr(n, "fullName")
        has_path = hasattr(n, "def_path") or hasattr(n, "defPath")
        looks_like_ident = ("Ident" in cls) or (has_full and has_path)
        if not looks_like_ident:
            continue

        full_name = getattr(n, "full_name", None) or getattr(n, "fullName", None)
        def_path  = getattr(n, "def_path", None)  or getattr(n, "defPath", None)
        if not full_name or not def_path:
            continue

        rec = {
            "full_name": full_name,
            "def_path": str(def_path).replace("\\", "/"),
        }

        # optional definition spans
        ds = getattr(n, "def_start", None) or getattr(n, "defStart", None)
        de = getattr(n, "def_end", None)   or getattr(n, "defEnd", None)
        if ds is not None:
            rec["def_start"] = pos_to_json(ds)
        if de is not None:
            rec["def_end"] = pos_to_json(de)

        out.append(rec)

    uniq = {}
    for r in out:
        uniq[(r["full_name"], r["def_path"])] = r
    return list(uniq.values())


# -----------------------------
# 3) Index only theorems defined in TARGET_FILES (optional mapping)
# -----------------------------
def build_local_def_index(traced_repo, target_files):
    """Build index of theorem definitions in target files."""
    idx = {}
    for file_path in tqdm(target_files, desc="Indexing target theorems", unit="file"):
        tf = traced_repo.get_traced_file(file_path)
        for tt in tf.get_traced_theorems():
            idx.setdefault(tt.theorem.full_name, str(tt.theorem.file_path))
    return idx


# -----------------------------
# 4) Extract edges + add premise excerpt when spans exist
# -----------------------------
def extract_premises_edges(
    traced_repo,
    target_files,
    output_file="tripartite_edges_ast_idents_algebra_with_excerpt.jsonl",
    src_root=None
):
    """
    Extract tripartite edges with AST-identified premises and excerpts.
    
    This function is READ-ONLY and does not modify the traced repo in any way.
    It only reads source files to extract definition excerpts.
    
    Args:
        traced_repo: TracedRepo object
        target_files: List of file paths to process
        output_file: Output JSONL file path
        src_root: Root directory for source files (defaults to traced_repo.root_dir)
    
    Returns:
        Number of edges written
    """
    if src_root is None:
        # Use root_dir attribute (read-only access)
        src_root = traced_repo.root_dir  # Path to traced repo root on disk
    
    src_root = Path(src_root)
    
    # Ensure we're working with absolute paths (read-only)
    if not src_root.is_absolute():
        src_root = src_root.resolve()
    
    # Build local definition index
    print("Building local definition index...")
    local_def_index = build_local_def_index(traced_repo, target_files)
    
    # Cache for file reads (speed)
    _file_cache = {}
    
    edges_written = 0
    t0 = time.time()
    
    with open(output_file, "w", encoding="utf-8") as f:
        for file_path in tqdm(target_files, desc="Processing files", unit="file"):
            tf = traced_repo.get_traced_file(file_path)
            traced_thms = [tt for tt in tf.get_traced_theorems() if tt.get_num_tactics() > 0]
    
            for tt in tqdm(traced_thms, desc=f"Theorems in {Path(file_path).name}", unit="thm", leave=False):
                for tac in tt.get_traced_tactics():
                    ast_idents = extract_idents_from_tactic_ast(getattr(tac, "ast", None))
    
                    premises = []
                    for p in ast_idents:
                        prem = dict(p)
                        prem["defined_in_target_file"] = local_def_index.get(prem["full_name"])
    
                        # Try to add excerpt if we have spans
                        ds = prem.get("def_start")
                        de = prem.get("def_end")
                        dp = prem.get("def_path")
    
                        excerpt = None
                        if dp and ds and de:
                            # def_path is like "Mathlib/Algebra/Free.lean"
                            # Note: def_path may already include .lean extension
                            if not dp.endswith('.lean'):
                                dp = dp + '.lean'
                            abs_path = (src_root / dp).resolve()
                            # Safety check: ensure we're reading from within src_root (read-only)
                            try:
                                abs_path.relative_to(src_root)
                            except ValueError:
                                # Path is outside src_root, skip for safety
                                continue
                            if abs_path.exists() and abs_path.is_file():
                                # Read-only file access
                                txt = read_text_cached(abs_path, _file_cache)
                                chunk = slice_span(txt, ds, de)
                                if chunk:
                                    excerpt = compact_excerpt(chunk, max_chars=320)
    
                        prem["def_excerpt"] = excerpt
                        premises.append(prem)
    
                    rec = {
                        "theorem": tt.theorem.full_name,
                        "file": str(tt.theorem.file_path),
                        "tactic": tac.tactic,
                        "state_before": tac.state_before,
                        "state_after": tac.state_after,
                        "premises_ast": premises,
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    edges_written += 1
    
    elapsed = time.time() - t0
    print(f"\nDone: wrote {edges_written} edges in {elapsed:.1f}s (~{edges_written/max(elapsed,1e-9):.1f} edges/s)")
    print(f"Output: {output_file}")
    
    return edges_written


