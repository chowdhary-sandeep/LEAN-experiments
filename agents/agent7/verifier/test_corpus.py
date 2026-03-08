"""
test_corpus.py — Verify real Mathlib proofs from the local corpus.

Loads tactic proofs and submits each to the Lean verifier.
Prefers traced_theorems_unified_v2.jsonl (has open_namespaces, full state_before)
over app_network_data.jsonl (stripped, state_before truncated to 150 chars).

Run:
  python test_corpus.py [--count 10] [--random]
  python test_corpus.py --count 500 --workers 4   # parallel with 4 Lean processes
"""

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from repl_client import ReplPool, ReplSession, LeanReplClient

# Prefer the rich file (has open_namespaces, namespace, file, full state_before)
# Try both Windows and WSL path forms
_TRACED_CANDIDATES = [
    Path(r"E:/LEAN-experiments/00_experiment1/jsons/traced_theorems_unified_v2.jsonl"),
    Path("/mnt/e/LEAN-experiments/00_experiment1/jsons/traced_theorems_unified_v2.jsonl"),
]
_COMPACT = Path(__file__).parent.parent / "adjacent-possible-of-lean" / "data" / "app_network_data.jsonl"
_TRACED = next((p for p in _TRACED_CANDIDATES if p.exists()), None)
DATA_FILE = _TRACED if _TRACED else _COMPACT
DATA_SOURCE = "traced" if _TRACED else "compact"

# Mathlib source tree from LeanDojo corpus — same commit as the corpus tracing.
# Contains the actual .lean files so we can read ground-truth open/variable context.
_MATHLIB_CANDIDATES = [
    "/mnt/e/LEAN-experiments/00_experiment1/gitpython-mathlib4-29dcec074de168ac2bf835a77ef68bbe069194c5/mathlib4",
]
MATHLIB_ROOT = next((p for p in _MATHLIB_CANDIDATES if os.path.isdir(p)), None)

# Lean meta-programming / compiler-internal namespaces — never open these in proof context
_META_OPENS_SKIP = frozenset({
    "Lean", "Meta", "Elab", "Tactic", "Parser", "PrettyPrinter",
    "Delaborator", "Macro", "Command", "Term", "Server", "Widget",
    "Lake", "Linter",
})

# Cache of source-file open lines: file_path -> [open statements]
_source_opens_cache: dict[str, list[str]] = {}


def _get_source_opens(entry: dict) -> list[str]:
    """
    Read the actual .lean source file and extract file-level open declarations.
    Returns list of 'open X' / 'open scoped X' strings.
    Cached per file path.
    """
    if not MATHLIB_ROOT:
        return []
    file_field = entry.get("file", "")
    if not file_field:
        return []
    # Normalize Windows backslashes
    file_rel = file_field.replace("\\", "/")
    full_path = os.path.join(MATHLIB_ROOT, file_rel)

    if full_path in _source_opens_cache:
        return _source_opens_cache[full_path]

    result: list[str] = []
    try:
        with open(full_path, encoding="utf-8") as fh:
            source = fh.read()
    except (OSError, UnicodeDecodeError):
        _source_opens_cache[full_path] = result
        return result

    seen: set[str] = set()
    in_block_comment = False

    for line in source.splitlines():
        stripped = line.strip()
        # Track /-- ... -/ block doc comments (can span multiple lines at column 0)
        if not in_block_comment:
            if stripped.startswith("/--") or stripped.startswith("/-"):
                in_block_comment = True
                # Check if it also closes on the same line
                if stripped.count("/-") == stripped.count("-/") and "-/" in stripped:
                    in_block_comment = False
                continue
        else:
            if "-/" in stripped:
                in_block_comment = False
            continue
        # Skip lines inside blocks (indented opens are local to a tactic/def/etc.)
        if line and line[0] in (" ", "\t"):
            continue
        # Skip comment lines
        if stripped.startswith("--"):
            continue
        # Match file-level: open X Y Z   or   open scoped X Y Z
        # Exclude "open X in" (local open), "open X (Y Z)" (selective), "open X hiding Y"
        m = re.match(r'^open(\s+scoped)?\s+(.+)', stripped)
        if m:
            scoped = m.group(1) or ""
            names_part = m.group(2).strip()
            # Skip local opens: "open X in ..."
            if re.search(r'\bin\b', names_part):
                continue
            for name in names_part.split():
                # Stop at modifying keywords or parenthetical syntax
                if name in ("in", "with", "hiding", "renaming", "--") or name.startswith("(") or name.startswith("--"):
                    break
                # Strip trailing punctuation (e.g., from multiline continuations)
                name = name.rstrip(",;)")
                # Lean namespace names are always PascalCase (uppercase first letter).
                # Lowercase words here are prose in doc strings or comments — skip.
                if not name or not re.match(r'^[A-Z]', name):
                    break
                # Skip Lean meta-programming namespaces — opening these in a regular
                # proof context brings in thousands of conflicting identifiers
                if name in _META_OPENS_SKIP:
                    continue
                key = f"open{scoped} {name}"
                if key not in seen:
                    result.append(key)
                    seen.add(key)

    _source_opens_cache[full_path] = result
    return result


# Cache of file-level local notation declarations: file_path -> [notation strings]
_source_notation_cache: dict[str, list[str]] = {}


def _get_source_local_notations(entry: dict) -> list[str]:
    """
    Read the .lean source file and extract file-level local notation declarations.
    These are needed for e.g. `local notation "tsze" => TrivSqZeroExt`.
    """
    if not MATHLIB_ROOT:
        return []
    file_rel = entry.get("file", "").replace("\\", "/")
    if not file_rel:
        return []
    full_path = os.path.join(MATHLIB_ROOT, file_rel)
    if full_path in _source_notation_cache:
        return _source_notation_cache[full_path]

    result: list[str] = []
    try:
        with open(full_path, encoding="utf-8") as fh:
            src_lines = fh.readlines()
    except (OSError, UnicodeDecodeError):
        _source_notation_cache[full_path] = result
        return result

    seen: set[str] = set()
    in_block = False
    i = 0
    while i < len(src_lines):
        line = src_lines[i]
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("/-"):
                in_block = not (stripped.count("/-") == stripped.count("-/") and "-/" in stripped)
                i += 1
                continue
        else:
            if "-/" in stripped:
                in_block = False
            i += 1
            continue
        if stripped.startswith("--"):
            i += 1
            continue
        if not line or line[0] not in (" ", "\t"):
            if re.match(r'^local\s+(?:notation|infixl|infixr|infix|prefix|postfix)\b', stripped):
                notation_lines = [stripped]
                j = i + 1
                while j < len(src_lines) and src_lines[j][0:1] in (" ", "\t"):
                    notation_lines.append(src_lines[j].strip())
                    j += 1
                key = " ".join(notation_lines)
                # Only include notations whose RHS does not reference section variables via
                # short-name dot-projection syntax (e.g. `D.toGlueData` where D is a var).
                # Safe: `local notation "tsze" => TrivSqZeroExt` (bare Mathlib name, no `.`)
                # Unsafe: `local notation "𝖣" => D.toGlueData` (single-char var + `.`)
                # Unsafe: `local notation "D_" => TopCat... <| D.toLRS...` (uses `D` var)
                rhs_match = re.search(r'=>\s*(.+)', key)
                if rhs_match:
                    rhs = rhs_match.group(1).strip()
                    # Skip if the RHS starts with a short (1-2 char) uppercase name + '.':
                    # these are almost always section variable dot-projections, not namespaces.
                    if re.match(r'^[A-Z][A-Za-z]?\.', rhs):
                        i = j
                        continue
                    # Skip if the RHS contains `<|` (complex function application with a var)
                    # These are always complex expressions referencing section variables.
                    if '<|' in rhs:
                        i = j
                        continue
                if key not in seen:
                    result.append(key)
                    seen.add(key)
                i = j
                continue
        i += 1

    _source_notation_cache[full_path] = result
    return result


# Cache of source-file variable lines: file_path -> [variable statements]
_source_vars_cache: dict[str, list[str]] = {}


def _get_source_variables(entry: dict) -> list[str]:
    """
    Read the actual .lean source file and extract file-level variable declarations.
    Returns list of raw 'variable ...' strings (including braces/brackets).
    Cached per file path.

    Key property: Lean 4's `variable` mechanism only injects a variable into a
    theorem if that variable's name is actually referenced. Unused variables are
    silently ignored, so over-including is safe.

    We collect non-indented `variable` lines + their indented continuations
    (multi-line variable blocks like `variable {R : Type*}\n  [CommRing R]`).
    """
    if not MATHLIB_ROOT:
        return []
    file_field = entry.get("file", "")
    if not file_field:
        return []
    file_rel = file_field.replace("\\", "/")
    full_path = os.path.join(MATHLIB_ROOT, file_rel)

    if full_path in _source_vars_cache:
        return _source_vars_cache[full_path]

    result: list[str] = []
    try:
        with open(full_path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except (OSError, UnicodeDecodeError):
        _source_vars_cache[full_path] = result
        return result

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        # File-level variable declaration (non-indented)
        if not line[0:1] in (" ", "\t") and stripped.startswith("variable"):
            # Collect this line + any indented continuation lines
            var_lines = [stripped]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip() == "":
                    j += 1
                    break
                if next_line[0:1] in (" ", "\t"):
                    var_lines.append(next_line.strip())
                    j += 1
                else:
                    break
            result.append(" ".join(var_lines))
            i = j
        else:
            i += 1

    _source_vars_cache[full_path] = result
    return result


_BINDER_RE = re.compile(r'([\(\{⦃\[])(.*?)([\)\}⦄\]])', re.DOTALL)


def _normalize_and_dedup_vars(var_decls: list[str]) -> list[str]:
    """
    Post-process raw variable declarations from the source file:
      1. Universe normalization: Type u / Sort v (named universe level vars) → Type* / Sort*
         These lower-case single-letter names are universe levels, not types.
         Emitting them without `universe u` causes 'application type mismatch'.
      2. Deduplication by named-binder name: if the same name (e.g. 'R', 'α') appears in
         two separate variable declarations, keep only the FIRST one.
         This prevents 'redundant binder annotation update' errors that arise when
         Mathlib source files re-declare the same variable across multiple sections.
    """
    seen_names: set[str] = set()
    result: list[str] = []

    for decl in var_decls:
        # --- Step 1: Universe normalization ---
        # "Type u", "Type uE'", "Type uE''" → "Type*"
        # Universe level vars start with lowercase and may have trailing apostrophes.
        decl = re.sub(r'\bType\s+[a-z_]\w*\'*', 'Type*', decl)
        decl = re.sub(r'\bSort\s+[a-z_]\w*\'*', 'Sort*', decl)
        # "Type (max u v)", "Sort (max u v)" → "Type*"
        decl = re.sub(r'\bType\s*\([^)]{1,40}\)', 'Type*', decl)
        decl = re.sub(r'\bSort\s*\([^)]{1,40}\)', 'Sort*', decl)
        # Strip explicit universe params from typeclass/type names: Category.{v, u} → Category
        # These named universe levels are not in scope and cause 'X is a local' errors.
        decl = re.sub(r'(\b[A-Z]\w*)\.\{[^}]{1,60}\}', r'\1', decl)

        # --- Step 2: Conflict detection ---
        body = re.sub(r'^variable\s*', '', decl).strip()
        introduced: set[str] = set()
        has_conflict = False

        for m in _BINDER_RE.finditer(body):
            open_b = m.group(1)
            inner = m.group(2).strip()
            # Anonymous typeclass instance [CommRing R] where 'CommRing R' has no
            # explicit name before ':' — fine to repeat, skip conflict check.
            if open_b == '[' and ':' not in inner:
                continue
            # Named binder: extract names before ':'
            if ':' in inner:
                names_part = inner.split(':', 1)[0].strip()
                names = [n for n in names_part.split()
                         if re.match(r'^[^\W\d]\w*\'*$', n, re.UNICODE)]
                for name in names:
                    if name in seen_names:
                        has_conflict = True
                        break
                    introduced.add(name)
            if has_conflict:
                break

        if not has_conflict:
            seen_names |= introduced
            result.append(decl)

    return result


def load_tactic_proofs(count: int, use_random: bool = False, min_proof_len: int = 20) -> list[dict]:
    candidates = []
    with open(DATA_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("proof_type") == "tactic" and len(d.get("proof_text") or "") >= min_proof_len:
                candidates.append(d)

    if use_random:
        random.shuffle(candidates)
    return candidates[:count]


def _open_stmts(entry: dict) -> list[str]:
    """
    Build open statements for the theorem's context.

    Priority:
    1. Source file opens (ground truth from actual .lean file, if MATHLIB_ROOT available)
    2. open_namespaces field (filtered) + fallback from full_name
    3. Notation-triggered scoped opens (BigOperators, Nat, Pointwise)
    """
    seen: set[str] = set()
    opens: list[str] = []

    def _add(stmt: str) -> None:
        if stmt not in seen:
            opens.append(stmt)
            seen.add(stmt)

    # 1. Ground-truth opens from actual source file
    source_opens = _get_source_opens(entry)
    if source_opens:
        for o in source_opens:
            _add(o)
    else:
        # 2a. From open_namespaces field (traced file only)
        # Filter out module-path entries and file-path garbage
        raw_opens = entry.get("open_namespaces") or []
        non_mathlib = [
            ns for ns in raw_opens
            if ns
            and not ns.startswith("Mathlib")
            and not ns.startswith("src")
            and ".lean" not in ns
            and not ns.startswith("Batteries.Data")
            and not ns.startswith("Std.Data")
        ]
        for ns in non_mathlib:
            _add(f"open {ns}")

        # 2b. Fallback: derive from full_name namespace
        if not non_mathlib:
            full_name = entry.get("full_name", "")
            if full_name and "." in full_name:
                ns = full_name.rsplit(".", 1)[0]
                leaf = ns.rsplit(".", 1)[-1] if "." in ns else ns
                if leaf:
                    _add(f"open {leaf}")

    # 3. Notation-triggered scoped opens (supplement regardless of source)
    text = (entry.get("statement") or "") + (entry.get("proof_text") or "")
    if "∑" in text or "∏" in text:
        _add("open scoped BigOperators")
    if re.search(r'\b\d+\s*!', text) or "Nat.factorial" in text:
        _add("open scoped Nat")
    if " ×ˢ" in text or " •ˢ" in text or "smul_set" in text:
        _add("open scoped Pointwise")
    if "‖" in text or "‖₊" in text:
        _add("open scoped NNNorm")


    return opens


def _normalize_type_univs(type_str: str) -> str:
    """Normalize universe level suffixes in a type string to Type*/Sort*."""
    s = re.sub(r"\bType\s+[\w.']+", "Type*", type_str)
    s = re.sub(r"\bSort\s+[\w.']+", "Sort*", s)
    s = re.sub(r"\bType\s*\([^)]{1,40}\)", "Type*", s)
    s = re.sub(r"\bSort\s*\([^)]{1,40}\)", "Sort*", s)
    return s


def _extract_variables(entry: dict) -> list[str]:
    """
    Parse state_before to reconstruct variable/typeclass declarations.

    state_before format (from LeanDojo):
        R : Type u_1
        inst✝² : CommRing R
        inst✝¹ : IsDomain R
        n m : ℕ
        ⊢ ...

    Rules:
      - inst✝* lines       → variable [TypeClass args]   (always — never in explicit sig)
      - Name : Type u_N    → variable {Name : Type*}     (implicit type var)
      - other Name : T     → skip if Name is an explicit param; else variable (Name : T)
      - Lines with →/↔/∧/∨ → skip (local hypotheses, not declarations)
    """
    tactics = entry.get("tactics") or []
    if not tactics:
        return []
    state_before = (tactics[0].get("state_before") or "").strip()
    if not state_before:
        return []

    statement = entry.get("statement", "")
    # Names that already appear as explicit params in the theorem signature.
    # For each binder group like `(U V : Opens X)`, we need to capture ALL names
    # (U, V, ...), not just the first. Strategy: find each binder group content
    # and extract all names before the final `:`.
    explicit_params: set[str] = set()
    for binder in re.findall(r'[({⦃\[](.*?)[)}\]⦄]', statement, re.DOTALL):
        # Find names before ':' in the binder
        colon_pos = binder.rfind(':')
        if colon_pos > 0:
            names_part = binder[:colon_pos].strip()
            for name in names_part.split():
                if re.match(r'^[^\W\d]\w*\'*$', name, re.UNICODE):
                    explicit_params.add(name)

    variables: list[str] = []
    # Track declared variable names to avoid emitting typeclasses for undeclared type vars.
    declared_vars: set[str] = set()

    for line in state_before.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("⊢") or line.startswith("case "):
            break

        # Match "name1 name2 : type"
        sep = line.find(" : ")
        if sep < 0:
            continue
        names_str = line[:sep].strip()
        type_str  = line[sep + 3:].strip()
        if not names_str or not type_str:
            continue

        names = names_str.split()

        # Typeclass instances (inst✝, inst✝¹, inst✝² …)
        # Only names that START with "inst" are typeclass instances.
        # Other ✝-suffixed names (p✝, n✝, f✝) are anonymous binders — skip them.
        if any(n.lower().startswith("inst") for n in names):
            # Skip instances that reference inaccessible variables (names with ✝).
            # e.g. inst✝ : Semiring R✝ — R✝ is not a valid name in our context.
            if re.search(r'\w✝', type_str):
                continue
            # Skip this typeclass if it references a type variable that's in explicit_params
            # but NOT yet declared as a file-level variable.
            # Handles both ASCII uppercase vars (M, R, X) and unicode vars (𝕜, α, β).
            has_undeclared = False
            for param in explicit_params:
                if param in declared_vars:
                    continue
                # Only check 'type-like' params: uppercase ASCII or unicode non-digit start
                if not (param and (param[0].isupper() or
                                   (not param[0].isascii() and not param[0].isdigit()))):
                    continue
                p_esc = re.escape(param)
                # ASCII-based word boundary handles unicode modifier chars (ˣ, ˢ, etc.)
                if re.search(r'(?<![A-Za-z0-9_])' + p_esc + r'(?![A-Za-z0-9_])', type_str):
                    has_undeclared = True
                    break
            if has_undeclared:
                continue
            # Strip explicit universe params from typeclass names: Category.{v, u} → Category
            # Lean can usually infer universe levels; explicit params cause 'is a local' errors.
            tc_type = re.sub(r'(\b[A-Z]\w*)\.\{[^}]{1,60}\}', r'\1', type_str)
            # Skip ∀-quantified typeclass instances: `variable [∀ i, HasPullback ...]`
            # is not valid Lean 4 syntax — the `∀` must be in an explicit binder, not `[...]`.
            if tc_type.lstrip().startswith("∀"):
                continue
            variables.append(f"variable [{tc_type}]")
            continue
        # Skip any line where all names are inaccessible (contain ✝) — anon binders
        if all("✝" in n for n in names):
            continue

        # Skip hypothesis lines (Prop-valued: contain definite logical connectives)
        # Keep "→" lines that look like function types (f : E → F) — only skip
        # implication lines where names look like hypothesis names (h, hn, hx, …)
        if any(c in type_str for c in ["↔", "∧", "∨", "¬"]):
            continue
        if "→" in type_str and all(
            re.match(r"^h[a-zA-Z0-9_]*$", n) or n in ("this",) for n in names
        ):
            continue

        # Skip ∀-quantified propositions — these are hypotheses, not data types.
        # e.g. 'Hg : ∀ (i j : ι) (hij : i ≤ j) (x : G i), expr' is a Prop.
        if type_str.startswith("∀"):
            continue

        # Skip any variable whose TYPE references inaccessible (✝-suffixed) names.
        # e.g. 'b c : ℍ[R,c₁✝,c₂✝]' — c₁✝/c₂✝ are not valid identifiers.
        if re.search(r'\w✝', type_str):
            continue

        # Type universe variables (R : Type u_1, α : Type*, etc.)
        if re.search(r"\bType\b|\bSort\b", type_str) and "→" not in type_str:
            normalized = _normalize_type_univs(type_str)
            for name in names:
                if re.match(r"^[^\W\d]\w*'*$", name, re.UNICODE) and name not in explicit_params:
                    variables.append(f"variable {{{name} : {normalized}}}")
                    declared_vars.add(name)
            continue

        # Regular variables — only add if not already an explicit param
        # Normalize universe levels in function-type return positions too.
        # e.g. 'A : ι → Type u_3' should become 'A : ι → Type*'
        type_str_norm = _normalize_type_univs(type_str)
        for name in names:
            if re.match(r"^[^\W\d]\w*'*$", name, re.UNICODE) and name not in explicit_params:
                variables.append(f"variable ({name} : {type_str_norm})")
                declared_vars.add(name)

    return variables


def build_check_command(entry: dict) -> str:
    """
    Build a Lean command wrapping the theorem + proof with full context:
    - noncomputable section (safe always)
    - open statements from open_namespaces or full_name
    - namespace wrapping for dot notation
    - private theorem rename (_vt suffix) to avoid collision
    """
    full_name = entry.get("full_name", "")
    statement = entry.get("statement", "").strip()
    proof_text = (entry.get("proof_text") or "").strip()

    if not statement or not proof_text:
        return None

    # Namespace wrapping (computed early — needed for theorem name prefix stripping below)
    ns = None
    if full_name and "." in full_name:
        ns = full_name.rsplit(".", 1)[0]
    elif entry.get("namespace"):
        ns = entry["namespace"]

    def _rename_thm(thm_name: str) -> str:
        """Strip redundant namespace prefix from theorem name and append _vt suffix.
        Inside namespace A.B, 'theorem A.B.foo' should become 'private theorem foo_vt'.
        Without stripping, Lean rejects dotted names inside a matching namespace."""
        if ns:
            parts = thm_name.split(".")
            for prefix_len in range(len(parts) - 1, 0, -1):
                prefix = ".".join(parts[:prefix_len])
                if ns.endswith("." + prefix) or ns == prefix:
                    thm_name = ".".join(parts[prefix_len:])
                    break
        return f"private theorem {thm_name}_vt"

    # Rename theorem/lemma to avoid "already been declared"
    # Drop 'protected' and 'noncomputable' modifiers — private theorem is always noncomputable
    # in a noncomputable section, and 'protected private' is invalid in Lean 4.
    _mod = r'(?:noncomputable\s+|protected\s+)*'
    stmt = re.sub(
        rf'^{_mod}(?:theorem|lemma)\s+(\S+)',
        lambda m: _rename_thm(m.group(1)),
        statement.rstrip(),
        count=1,
    )
    # Handle @[attr] on line before theorem
    stmt = re.sub(
        rf'^(@\[.*?\]\s*\n?){_mod}(?:theorem|lemma)\s+(\S+)',
        lambda m: f"{m.group(1)}{_rename_thm(m.group(2))}",
        stmt,
        count=1,
        flags=re.MULTILINE,
    )

    body = f"{stmt}\n{proof_text}" if stmt.endswith(":=") else f"{stmt} :=\n{proof_text}"

    opens = _open_stmts(entry)
    local_notations = _get_source_local_notations(entry)
    var_decls = _extract_variables(entry)

    # Detect named universe levels from non-inst state_before lines and statement.
    # Only scan non-inst hypothesis lines for "Type X" patterns — inst lines have
    # universe params like {v, u} that we've already stripped from typeclass names.
    tactics = entry.get("tactics") or []
    sb = (tactics[0].get("state_before") or "") if tactics else ""
    flat_univs: set[str] = set()
    _NOT_UNIVS = frozenset({'max', 'min', 'succ', 'imax'})
    # Scan statement
    for u in re.findall(r'(?:Type|Sort)\s+([a-z]\w*)', statement):
        if not re.match(r'^u_\d+$', u) and u not in _NOT_UNIVS:
            flat_univs.add(u)
    # Scan non-inst hypothesis lines in state_before
    for sb_line in sb.split("\n"):
        sb_line = sb_line.strip()
        if not sb_line or sb_line.startswith("⊢") or sb_line.startswith("case "):
            break
        names_part = sb_line.split(" : ", 1)[0].strip() if " : " in sb_line else ""
        if any(n.lower().startswith("inst") for n in names_part.split()):
            continue  # skip inst lines — universe params here are already stripped
        type_part = sb_line.split(" : ", 1)[1] if " : " in sb_line else ""
        for u in re.findall(r'(?:Type|Sort)\s+([a-z]\w*)', type_part):
            if not re.match(r'^u_\d+$', u) and u not in _NOT_UNIVS:
                flat_univs.add(u)

    lines = ["noncomputable section"]
    if flat_univs:
        lines.append(f"universe {' '.join(sorted(flat_univs))}")
    lines += opens
    lines += local_notations
    lines += var_decls
    if ns:
        lines.append(f"namespace {ns}")
        lines.append(body)
        lines.append(f"end {ns}")
    else:
        lines.append(body)
    lines.append("end")

    return "\n".join(lines)


def _classify(response) -> str:
    if response.error is None and not response.has_sorry:
        return "pass"
    if response.has_sorry:
        return "sorry"
    return f"fail:{(response.error or '').strip()[:120]}"


def run_corpus_test(count: int = 10, use_random: bool = False, workers: int = 1) -> None:
    print(f"\nData source: {DATA_FILE.name} ({DATA_SOURCE})")
    print(f"Loading {count} tactic proofs...")
    entries = load_tactic_proofs(count, use_random=use_random)
    if not entries:
        print(f"ERROR: No tactic proofs found in {DATA_FILE}")
        sys.exit(1)
    print(f"Loaded {len(entries)} entries.\n")

    jobs: list[tuple[dict, str]] = []
    skipped = 0
    for entry in entries:
        cmd = build_check_command(entry)
        if cmd:
            jobs.append((entry, cmd))
        else:
            skipped += 1

    passed = failed = 0
    fail_categories: dict[str, int] = {}

    def _record(verdict: str) -> None:
        nonlocal passed, failed
        if verdict in ("pass", "sorry"):
            passed += 1
        else:
            failed += 1
            msg = verdict[len("fail:"):].split("\n")[0][:60]
            # Bucket by error type
            for pattern, label in [
                ("failed to synthesize", "failed_to_synthesize"),
                ("unknown identifier", "unknown_identifier"),
                ("function expected", "function_expected"),
                ("expected token", "expected_token"),
                ("already been declared", "already_declared"),
                ("application type mismatch", "type_mismatch"),
            ]:
                if pattern in msg:
                    fail_categories[label] = fail_categories.get(label, 0) + 1
                    return
            fail_categories["other"] = fail_categories.get("other", 0) + 1

    if workers > 1:
        print(f"Starting {workers} Lean workers (parallel)...")
        t0 = time.time()
        pool = ReplPool(size=workers)
        pool.start()
        print(f"All workers ready in {time.time()-t0:.1f}s\n")

        cmds = [cmd for _, cmd in jobs]
        t_batch = time.time()
        responses = pool.map(cmds, timeout=90.0)
        elapsed_batch = time.time() - t_batch

        for i, ((entry, cmd), resp) in enumerate(zip(jobs, responses)):
            name = entry.get("full_name", f"entry_{i}")
            verdict = _classify(resp)
            tag = "PASS" if verdict == "pass" else "SORRY" if verdict == "sorry" else "FAIL"
            if tag != "PASS":
                msg = verdict[len("fail:"):] if verdict.startswith("fail:") else ""
                print(f"  {tag}  [{i+1}/{len(jobs)}] {name}")
                if msg:
                    print(f"         {msg[:100]}")
            _record(verdict)

        pool.stop()
        print(f"\n(Batch took {elapsed_batch:.1f}s wall time with {workers} workers)")

    else:
        print("Starting Lean (single worker)...")
        t0 = time.time()
        client = LeanReplClient()
        client.start()
        session = ReplSession(client)
        # Entry file already runs `import Mathlib` — sid=0 is post-Mathlib.
        # setup([]) just sets base_sid=0 without sending any commands.
        session.setup([])
        print(f"Lean ready in {time.time()-t0:.1f}s\n")

        for i, (entry, cmd) in enumerate(jobs):
            name = entry.get("full_name", f"entry_{i}")
            t0 = time.time()
            resp = session.check(cmd, timeout=90.0)
            elapsed_ms = (time.time() - t0) * 1000
            verdict = _classify(resp)
            tag = "PASS" if verdict == "pass" else "SORRY" if verdict == "sorry" else "FAIL"
            if tag == "PASS":
                print(f"  PASS  [{i+1}/{len(jobs)}] {name}  ({elapsed_ms:.0f}ms)")
            else:
                msg = verdict[len("fail:"):] if verdict.startswith("fail:") else ""
                print(f"  {tag}  [{i+1}/{len(jobs)}] {name}")
                if msg:
                    print(f"         {msg[:100]}")
            _record(verdict)

        client.stop()

    total = len(entries)
    print(f"\n{'='*60}")
    print(f"Data: {DATA_FILE.name}  |  {count} requested, {len(jobs)} checked, {skipped} skipped")
    print(f"Result: {passed} PASS  {failed} FAIL  ({passed/len(jobs)*100:.1f}%)")
    if fail_categories:
        print("Failure breakdown:")
        for cat, n in sorted(fail_categories.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {n}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()

    run_corpus_test(count=args.count, use_random=args.random, workers=args.workers)
