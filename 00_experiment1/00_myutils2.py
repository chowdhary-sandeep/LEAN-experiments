"""Utility functions for running proofs and extracting lemma dependencies."""

import importlib
import sys
import re
import time
from collections import defaultdict, Counter

# Try to import myutils_reprover, handling both normal import and manual loading
try:
    if "myutils_reprover" in sys.modules:
        # Only reload if the module has a proper spec (was loaded normally)
        module = sys.modules["myutils_reprover"]
        if hasattr(module, "__spec__") and module.__spec__ is not None:
            importlib.reload(module)
    
    from myutils_reprover import (
        create_theorem_from_complete_proof,
        extract_theorem_name,
    )
except (ImportError, ModuleNotFoundError):
    # If myutils_reprover is not available, try to load it manually
    import importlib.util
    try:
        spec = importlib.util.spec_from_file_location("myutils_reprover", "00_myutils_reprover.py")
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules["myutils_reprover"] = module
            spec.loader.exec_module(module)
            from myutils_reprover import (
                create_theorem_from_complete_proof,
                extract_theorem_name,
            )
    except Exception:
        # If all else fails, raise a clear error
        raise ImportError("Could not import myutils_reprover. Make sure 00_myutils_reprover.py exists.")

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

# =============================================================================
# Categorized Extraction Constants
# =============================================================================

# Keywords and modifiers that should never be extracted as premises
_KEYWORDS_MODIFIERS = {
    # Tactic keywords
    "by", "fun", "match", "with", "let", "in", "have", "show", "from",
    "do", "return", "if", "then", "else", "where", "calc", "suffices",
    
    # Basic tactics (not premises)
    "intro", "intros", "rintro", "apply", "exact", "refine", "rw", "simp",
    "simp_all", "simp_rw", "aesop", "assumption", "constructor", "cases",
    "rcases", "obtain", "induction", "ring", "linarith", "omega", "trivial",
    "decide", "norm_num", "positivity", "polyrith", "nlinarith", "ext",
    "congr", "refl", "rfl", "symm", "trans", "conv", "change", "clear",
    "rename", "revert", "generalize", "specialize", "choose", "use",
    "push_neg", "contrapose", "by_contra", "by_cases", "split", "left",
    "right", "exists", "existsi", "trivial", "tauto", "tidy", "norm_cast",
    "ring_nf", "field_simp", "group", "abel", "continuity", "measurability",
    "positivity", "gcongr", "rel_simp", "set", "subst", "injection",
    "contradiction", "absurd", "exfalso", "sorry", "admit", "stop",
    "all_goals", "any_goals", "first", "try", "repeat", "iterate", "done",
    "native_decide", "ac_rfl", "convert", "convert_to", "swap", "rotate",
    "focus", "guard_hyp", "guard_target", "guard_expr", "trace", "fail",
    "skip", "simpa", "simp_intro", "dsimp", "unfold", "delta", "whnf",
    "reduce", "beta_reduce", "eta_reduce", "zeta_reduce",
    
    # Additional tactics missed in first pass (previously in global_lemmas or other)
    "filter_upwards", "split_ifs", "mod_cast", "push_cast", "lift",
    "tfae_have", "tfae_finish", "infer_instance", "inferInstance",
    "rwa", "era", "classical", "haveI", "letI", "exactI",
    "mono", "erw", "replace", "clear_value", "subsingleton",
    "nontriviality", "inhabit", "borelize", "measurability",
    "bound_tac", "interval_cases", "fin_cases", "dec_trivial",
    "norm_swap", "swap_var", "work_on_goal", "on_goal", "pick_goal",
    "clean", "success_if_fail", "fail_if_success",
    "refine'", "apply'", "exact'", "rw'", "simp'",
    
    # Tactics found in corpus no-match analysis
    "conv_rhs", "conv_lhs", "nth_rw", "apply_fun", "aesop_cat",
    "mfld_simps", "slice_lhs", "slice_rhs", "reassoc", "simp_nf",
    "continuity", "fun_prop", "data_refl", "norm_cast_assert",
    # More tactics from second no-match analysis
    "rename_i", "subst_vars", "linear_combination", "polyrith",
    "positivity", "ring_nf", "norm_num_ext", "module", "exact?",
    "apply?", "rfl?", "decide?", "simp?", "aesop?",
    
    # Modifiers (not premises)
    "only", "using", "at", "with", "generalizing", "motive", "termination_by",
    "decreasing_by",
    
    # Logic keywords
    "forall", "exists", "True", "False", "And", "Or", "Not", "Iff",
    
    # Placeholders
    "_", "?", "??", "*",
    
    # Lean internal markers
    "_root_",
}

# Single uppercase letters are type variables, not lemmas
_TYPE_VARIABLES = {
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
}

# Common Mathlib namespace prefixes (not lemmas by themselves)
_NAMESPACES = {
    "ENNReal", "NNReal", "EReal", "Real", "Complex", "Rat", "Int", "Nat",
    "Function", "Set", "Finset", "Multiset", "List", "Array", "Vector",
    "Submodule", "Subgroup", "Subring", "Subalgebra", "Submonoid",
    "LinearMap", "RingHom", "AlgHom", "MonoidHom", "AddMonoidHom",
    "Subtype", "Quotient", "Option", "Sum", "Prod", "Sigma",
    "Pi", "Category", "Functor", "Monad",
    "Ideal", "Polynomial", "MvPolynomial", "PowerSeries",
    "Finsupp", "DFinsupp", "WithTop", "WithBot", "WithZero",
    "Filter", "Topology", "Metric", "Norm", "Measure",
    "Matrix", "Module", "Algebra", "Ring", "Field", "Group",
}

# Standalone projection names that should be filtered when alone
_STANDALONE_PROJECTIONS = {
    "mp", "mpr", "symm", "trans", "refl", "comm", "assoc",
    "ne", "le", "lt", "ge", "gt", "eq",  # when standalone, not lemma names
    "fst", "snd", "val", "mk",  # constructors/projections
    "inl", "inr",  # Sum constructors (when standalone, ambiguous)
}

# Qualified constructors that should be filtered (not lemmas)
_CONSTRUCTORS = {
    "Or.inl", "Or.inr", "And.intro", "And.left", "And.right",
    "Sum.inl", "Sum.inr", "Prod.mk", "Prod.fst", "Prod.snd",
    "Option.some", "Option.none", "Except.ok", "Except.error",
    "Bool.true", "Bool.false", "Unit.unit", "PUnit.unit",
    "Nat.zero", "Nat.succ", "List.nil", "List.cons",
    "True.intro", "Eq.refl",
}

# Local hypothesis patterns (regex patterns)
_LOCAL_HYPOTHESIS_PATTERNS = [
    r"^[a-z]$",              # Single lowercase letter: h, x, f, g, etc.
    r"^[a-z]\d+$",           # Letter + number: h1, h2, x0, etc.
    r"^h[A-Z][a-z]*$",       # h + capitalized: hP, hQ, hG, hF, etc.
    r"^h[a-z]+$",            # h + lowercase: hf, hg, hp, etc.
    r"^this$",               # The special "this" keyword
    r"^ih$",                 # Induction hypothesis
    r"^IH$",                 # Induction hypothesis (caps)
    r"^H[A-Z]?$",            # H or HA, HB, etc.
    r"^hr[a-z]?$",           # hr, hra, hrb, etc.
    r"^hs[a-z]?$",           # hs, hsa, hsb, etc.
    r"^ht[a-z]?$",           # ht, hta, htb, etc.
    r"^hyp\d*$",             # hyp, hyp1, hyp2, etc.
    # Extended patterns for h_* style hypotheses
    r"^h_[a-z_]+$",          # h_eq, h_pos, h_zero, h_top, etc.
    r"^h[a-z]_[a-z_]+$",     # ha_top, hb_pos, etc.
    r"^h[a-z]+\d*$",         # hab, hab1, etc.
    # Numbered hypotheses: h_1, h_2, h_3, etc.
    r"^h_\d+$",              # h_1, h_2, etc.
    r"^h\d+$",               # h1, h2, etc. (already covered by ^[a-z]\d+$ but explicit)
    # h_[A-Z] patterns: h_C, h_Union, h_measM_f, etc.
    r"^h_[A-Z].*$",          # h_C, h_Union, h_D, etc.
    # Hypothesis names ending with common suffixes
    r"^h.*_pos$",            # hp_pos, h_pos, etc.
    r"^h.*_neg$",            # h_neg, hp_neg, etc.
    r"^h.*_eq$",             # h_eq, hp_eq, etc.
    r"^h.*_ne$",             # h_ne, hp_ne, etc.
    r"^h.*_lt$",             # h_lt, hp_lt, etc.
    r"^h.*_le$",             # h_le, hp_le, etc.
    r"^h.*_zero$",           # h_zero, hp_zero, etc.
    r"^h.*_one$",            # h_one, hp_one, etc.
    r"^h.*_top$",            # h_top, ha_top, etc.
    r"^h.*_bot$",            # h_bot, ha_bot, etc.
    r"^h.*_mem$",            # h_mem, hp_mem, etc.
    r"^h.*_sub$",            # h_sub, etc.
    r"^h.*_add$",            # h_add, etc.
    r"^h.*_mul$",            # h_mul, etc.
    r"^h.*_div$",            # h_div, etc.
    r"^h.*_pow$",            # h_pow, etc.
    r"^h.*_comm$",           # h_comm, etc.
    r"^h.*_assoc$",          # h_assoc, etc.
    r"^h.*_cover$",          # h_cover, etc.
    r"^h.*_rpow$",           # h_rpow, etc.
    r"^h.*_sum$",            # h_sum, h_sum_nnreal, etc.
    r"^h.*_frac$",           # h_frac, etc.
    r"^h.*_nonzero$",        # h_nonzero, etc.
    r"^h.*_nonneg$",         # h_nonneg, etc.
]

# Common type class / definition names (often appear as type annotations)
_TYPE_CLASS_NAMES = {
    # Algebraic structures
    "Monoid", "Group", "Ring", "Field", "Module", "Algebra", "Lattice",
    "Semiring", "CommRing", "CommGroup", "AddGroup", "AddMonoid",
    "LinearOrder", "PartialOrder", "Preorder", "OrderedRing", "OrderedSemiring",
    "TopologicalSpace", "MetricSpace", "NormedSpace", "NormedRing",
    "MeasurableSpace", "MeasureSpace", "BorelSpace",
    
    # Set/Function types
    "MapsTo", "Injective", "Surjective", "Bijective", "Continuous",
    "Measurable", "StronglyMeasurable", "Integrable",
    
    # Common mathlib types
    "Finset", "Fintype", "Finite", "Infinite", "Countable", "Uncountable",
    "Nonempty", "Subsingleton", "Unique", "Decidable", "DecidableEq",
    
    # Type constructors often used in annotations
    "Set", "Prop", "Type", "Sort", "Nat", "Int", "Real", "Complex",
    "Option", "List", "Array", "Vector", "Matrix", "Polynomial",
}

# Projections that indicate the base is a lemma (keep the full name)
_LEMMA_PROJECTIONS = {"1", "2", "mp", "mpr", "symm", "trans", "refl", "left", "right"}

# Corrupted Unicode patterns
_CORRUPTED_UNICODE_PATTERNS = {"â", "ã", "ä", "å", "ð", "ñ", "ò", "ó", "ô", "õ", "ö"}


def _is_local_hypothesis(name):
    """Check if name matches local hypothesis patterns."""
    import re
    for pattern in _LOCAL_HYPOTHESIS_PATTERNS:
        if re.match(pattern, name):
            return True
    return False


def _is_local_variable_access(name):
    """Detect patterns like x.coe_prop, f.rootSet, this.method, symm.trans."""
    if "." not in name:
        return False
    prefix = name.split(".")[0]
    # Single lowercase letter
    if len(prefix) == 1 and prefix.islower():
        return True
    # "this" keyword
    if prefix == "this":
        return True
    # Common local variable prefixes
    if prefix in {"hf", "hg", "hp", "hq", "hs", "ht", "hu", "hv", "hw", "hr"}:
        return True
    # Check if prefix is a local hypothesis
    if _is_local_hypothesis(prefix):
        return True
    # Projection chain patterns (symm.trans, refl.trans, etc.) - not qualified lemma names
    if prefix in {"symm", "trans", "refl", "comm", "assoc", "inl", "inr", "fst", "snd"}:
        return True
    # Single uppercase letters used as local functor/type variables (F.obj, G.map, etc.)
    if len(prefix) == 1 and prefix.isupper():
        return True
    return False


def _is_qualified_global_name(name):
    """Detect patterns like Subtype.ext, Real.Angle.induction_on."""
    if "." not in name:
        return False
    parts = name.split(".")
    # First part should be capitalized (namespace)
    if parts[0] and parts[0][0].isupper():
        return True
    return False


def _is_type_class_annotation(name):
    """Check if name is a known type class or type annotation."""
    # Check base name (without dots)
    base = name.split(".")[0] if "." in name else name
    return base in _TYPE_CLASS_NAMES


def _is_corrupted_unicode(name):
    """Check if name is corrupted Unicode garbage."""
    # Single corrupted character
    if name in _CORRUPTED_UNICODE_PATTERNS:
        return True
    # Starts with corrupted Unicode
    if name and name[0] in _CORRUPTED_UNICODE_PATTERNS:
        return True
    # Contains only corrupted chars
    if all(c in _CORRUPTED_UNICODE_PATTERNS or c.isspace() for c in name):
        return True
    return False


def _is_lemma_projection(name):
    """Check if name ends with a known lemma projection like .2, .mp, .mpr."""
    if "." not in name:
        return False
    suffix = name.rsplit(".", 1)[1]
    return suffix in _LEMMA_PROJECTIONS

def load_corpus_premises(corpus_path="corpus.jsonl"):
    """
    Load corpus.jsonl and flatten it into a list of premises.
    Each premise dict will have:
      - full_name: from premise entry (normalized Unicode symbols)
      - defPath: from file's path field (for compatibility with premise_registry format)
      - path: from file's path field (original corpus field)
      - All other fields from the premise entry (code, start, end, kind, etc.)
    
    Args:
        corpus_path: Path to corpus.jsonl file
        
    Returns:
        List of premise dictionaries compatible with build_premise_index
        (with normalized full_name fields)
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
                # Normalize Unicode symbols in full_name
                if "full_name" in prem_dict:
                    prem_dict["full_name"] = normalize_unicode_symbols(prem_dict["full_name"])
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


# Unicode symbol normalization mapping
# Maps Unicode escape sequences and various representations to normalized characters
_UNICODE_SYMBOL_MAP = {
    # Arrows - various representations
    "\\u22d9": "←",  # Left arrow (Unicode escape in JSON)
    "\\u2190": "←",  # Leftwards Arrow (alternative)
    "\\u2192": "→",  # Rightwards Arrow
    "\\u2194": "↔",  # Left Right Arrow
    "\\u27f5": "⟵",  # Long Leftwards Arrow
    "\\u27f6": "⟶",  # Long Rightwards Arrow
    "\\u27f7": "⟷",  # Long Left Right Arrow
    # Actual characters (for direct matching)
    "←": "←",
    "→": "→",
    "↔": "↔",
    "⟵": "⟵",
    "⟶": "⟶",
    "⟷": "⟷",
    # Category theory arrows
    "\\u27f6": "⟶",  # Category arrow
    "\\u27f9": "⟹",  # Long Rightwards Double Arrow
    "⟶": "⟶",
    "⟹": "⟹",
    # Other common Lean symbols
    "\\u2200": "∀",  # For All
    "\\u2203": "∃",  # There Exists
    "\\u2208": "∈",  # Element Of
    "\\u2264": "≤",  # Less-Than Or Equal To
    "\\u2265": "≥",  # Greater-Than Or Equal To
    "\\u2260": "≠",  # Not Equal To
    "\\u2293": "⊓",  # Square Cap
    "\\u2294": "⊔",  # Square Cup
    "\\u22a2": "⊢",  # Right Tack (turnstile)
    "\\u22a3": "⊣",  # Left Tack
    "\\u22c5": "⋅",  # Dot Operator
    "\\u2218": "∘",  # Function Composition
    "\\u03b1": "α",  # Greek alpha
    "\\u03b2": "β",  # Greek beta
    "\\u03b3": "γ",  # Greek gamma
    "\\u03c0": "π",  # Greek pi
    "\\u03c3": "σ",  # Greek sigma
    "\\u03c9": "ω",  # Greek omega
    "\\u03b9": "ι",  # Greek iota
    "\\u220f": "∏",  # N-Ary Product
    "\\u2211": "∑",  # N-Ary Summation
    "\\u22c5": "⋅",  # Dot Operator
    "\\u00d7": "×",  # Multiplication Sign
    "\\u2191": "↑",  # Upwards Arrow
    "\\u2193": "↓",  # Downwards Arrow
    "\\u226b": "≫",  # Much Greater-Than
    "\\u226a": "≪",  # Much Less-Than
}


def normalize_unicode_symbols(text):
    """
    Normalize Unicode symbols in text.
    Converts Unicode escape sequences (like \\u22d9) to actual characters,
    and ensures consistent representation.
    
    Args:
        text: String that may contain Unicode escape sequences or symbols
        
    Returns:
        Normalized string with consistent Unicode representation
    """
    if not text:
        return text
    
    # First, decode any JSON-style Unicode escape sequences
    # Handle both \\uXXXX and \uXXXX formats
    try:
        # Replace \\u with \u for proper decoding
        text = text.replace("\\\\u", "\\u")
        # Decode Unicode escape sequences
        text = text.encode().decode('unicode_escape')
    except (UnicodeDecodeError, UnicodeEncodeError):
        # If decoding fails, try direct replacement
        pass
    
    # Replace known Unicode escape sequences with actual characters
    for escape_seq, char in _UNICODE_SYMBOL_MAP.items():
        if escape_seq.startswith("\\u"):
            text = text.replace(escape_seq, char)
    
    return text


def extract_lemma_candidates(tac_block):
    """
    Extract "surface" lemma candidates from a tactic block:
    - identifiers in rewrite/simp lists: rw [a, b], simp [c], simp only [d]
    - head identifiers after apply/refine/exact/rw/suffices/have
    - dotted names like Subtype.coe_injective.injOn
    
    Note: Normalizes Unicode symbols before extraction.
    """
    # Normalize Unicode symbols first
    s = normalize_unicode_symbols(tac_block)

    cands = set()

    # (1) Things inside [...] lists
    for m in re.finditer(r"\[(.*?)\]", s, flags=re.DOTALL):
        inner = m.group(1)
        # split by commas at top level (best-effort)
        parts = [p.strip() for p in inner.split(",")]
        for p in parts:
            if not p or p in {"*", "_"}:
                continue
            # drop leading arrows etc. (normalized Unicode)
            p = p.lstrip("←→↔⟵⟶⟷⟹")
            # take first "name-like" chunk from this part
            nm = _NAME_RE.findall(p)
            if nm:
                cands.add(nm[0])

    # (2) Head identifier after common keywords
    for kw in ["apply", "refine", "exact", "rw", "simp", "suffices", "have"]:
        # capture the token right after keyword
        for m in re.finditer(rf"\b{kw}\b\s+([^\s\(\{{\[]+)", s):
            tok = m.group(1).strip()
            tok = tok.lstrip("←→↔⟵⟶⟷⟹")
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


def extract_lemma_candidates_categorized(tac_block):
    """
    Extract and categorize all identifiers from a tactic block.
    
    Returns a dict with categories:
        - global_lemmas: Qualified names with capital namespaces, known lemmas
        - local_hypotheses: Single letters, numbered (h1, h2), special (this, ih)
        - local_var_access: Patterns like x.property, this.method, f.rootSet
        - keywords_modifiers: Tactic names, only, using, etc.
        - type_class_annotations: Type names in type positions (MapsTo, Monoid, etc.)
        - type_variables: Single uppercase letters (A, B, R, etc.)
        - namespaces: Mathlib namespace names (ENNReal, Function, etc.)
        - corrupted_unicode: "â" and similar encoding garbage
        - other: Anything that doesn't fit elsewhere
        
    Each category maps to a list of extracted identifiers.
    """
    # Normalize Unicode symbols first
    s = normalize_unicode_symbols(tac_block)
    
    # Collect ALL raw candidates first (no filtering)
    all_raw = set()
    
    # (1) Things inside [...] lists
    for m in re.finditer(r"\[(.*?)\]", s, flags=re.DOTALL):
        inner = m.group(1)
        parts = [p.strip() for p in inner.split(",")]
        for p in parts:
            if not p:
                continue
            # Keep leading arrows for detection but also try stripped version
            p_stripped = p.lstrip("←→↔⟵⟶⟷⟹↦")
            # take first "name-like" chunk from this part
            nm = _NAME_RE.findall(p)
            if nm:
                all_raw.add(nm[0])
            nm_stripped = _NAME_RE.findall(p_stripped)
            if nm_stripped:
                all_raw.add(nm_stripped[0])
    
    # (2) Head identifier after common keywords
    for kw in ["apply", "refine", "exact", "rw", "simp", "simp_rw", "simpa", 
               "suffices", "have", "induction", "cases", "rcases", "obtain", "use"]:
        for m in re.finditer(rf"\b{kw}\b\s+([^\s\(\{{\[]+)", s):
            tok = m.group(1).strip()
            tok_stripped = tok.lstrip("←→↔⟵⟶⟷⟹↦")
            # strip trailing punctuation
            tok = re.sub(r"[,\)\]\}]+$", "", tok)
            tok_stripped = re.sub(r"[,\)\]\}]+$", "", tok_stripped)
            # accept only name-like tokens
            nm = _NAME_RE.findall(tok)
            if nm:
                all_raw.add(nm[0])
            nm_stripped = _NAME_RE.findall(tok_stripped)
            if nm_stripped:
                all_raw.add(nm_stripped[0])
    
    # (3) Any dotted chains in the block
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_']*(?:\.[A-Za-z0-9_']+)+)\b", s):
        all_raw.add(m.group(1))
    
    # (4) Any standalone identifiers (catch remaining)
    for m in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_']*)\b", s):
        all_raw.add(m.group(1))
    
    # Now categorize each raw candidate
    categories = {
        "global_lemmas": [],
        "local_hypotheses": [],
        "local_var_access": [],
        "keywords_modifiers": [],
        "type_class_annotations": [],
        "type_variables": [],
        "namespaces": [],
        "corrupted_unicode": [],
        "other": [],
    }
    
    for raw in sorted(all_raw):
        if not raw:
            continue
        
        # Skip purely numeric / punctuation
        if all(ch.isdigit() or ch in "._'" for ch in raw):
            continue
        
        # Corrupted Unicode first (highest priority to catch garbage)
        if _is_corrupted_unicode(raw):
            categories["corrupted_unicode"].append(raw)
            continue
        
        # Keywords and modifiers
        if raw in _KEYWORDS_MODIFIERS:
            categories["keywords_modifiers"].append(raw)
            continue
        
        # Standalone projection names (mp, mpr, etc. when alone) - filter as keywords
        if raw in _STANDALONE_PROJECTIONS:
            categories["keywords_modifiers"].append(raw)
            continue
        
        # Known constructors (Or.inl, Or.inr, etc.) - filter as keywords
        if raw in _CONSTRUCTORS:
            categories["keywords_modifiers"].append(raw)
            continue
        
        # Single uppercase letters = type variables
        if raw in _TYPE_VARIABLES:
            categories["type_variables"].append(raw)
            continue
        
        # Known namespace names (ENNReal, Function, etc.)
        if raw in _NAMESPACES:
            categories["namespaces"].append(raw)
            continue
        
        # Local variable access (x.property, this.method, etc.)
        if _is_local_variable_access(raw):
            categories["local_var_access"].append(raw)
            continue
        
        # Local hypotheses (single letters, h1, this, ih, h_*, etc.)
        if _is_local_hypothesis(raw):
            categories["local_hypotheses"].append(raw)
            continue
        
        # Type class annotations (MapsTo, Monoid, etc.)
        # Note: Only classify as type if it's NOT qualified (qualified are likely lemmas)
        if "." not in raw and _is_type_class_annotation(raw):
            categories["type_class_annotations"].append(raw)
            continue
        
        # Qualified global names (Namespace.Name where Namespace is capitalized)
        if _is_qualified_global_name(raw):
            categories["global_lemmas"].append(raw)
            continue
        
        # Unqualified names that look like lemmas (snake_case, end with known suffixes)
        # These are likely global lemmas without namespace prefix
        if "_" in raw and not raw.startswith("_"):
            # snake_case is typical for lemma names (le_antisymm, add_comm, etc.)
            categories["global_lemmas"].append(raw)
            continue
        
        # Lemma projections (name.2, name.mp, etc.) - keep as global lemma
        if _is_lemma_projection(raw):
            categories["global_lemmas"].append(raw)
            continue
        
        # Names starting with lowercase that aren't caught above
        if raw and raw[0].islower():
            # Could be a lemma or something else - put in other
            categories["other"].append(raw)
            continue
        
        # CamelCase names without dots - could be types or lemmas
        if raw and raw[0].isupper() and "." not in raw:
            # Already checked type_class, but some capitalized names are lemmas
            # Put in other for manual review
            categories["other"].append(raw)
            continue
        
        # Everything else
        categories["other"].append(raw)
    
    return categories


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


def extract_all_premises(i, data, theorem_registry=None, premise_registry=None, printing=False, version="v1", corpus_full_names_set=None):
    """
    Extract all raw lemma/def candidates from a theorem's proof as they appear in tactics.
    
    Args:
        i: Proof index in data
        data: List of proof data from complete_proofs.json
        theorem_registry: Optional (not used, kept for compatibility)
        premise_registry: Optional corpus/premise data (used in v2 to build corpus_full_names_set)
        printing: Whether to print progress
        version: "v1" (raw extraction) or "v2" (check full name in corpus first, then break down)
        corpus_full_names_set: Pre-built normalized set of corpus full names (for v2, pass this to avoid rebuilding)
        
    Returns:
        List of tuples (tactic_block, candidate) in order of appearance, or None if data invalid.
        - tactic_block: The tactic block where the candidate appears
        - candidate: Raw candidate name as extracted from the tactic (v1) or processed candidate (v2)
    """
    if printing:
        print(f"Extracting candidates for proof index: {i} (version: {version})")
    
    if i >= len(data) or len(data[i]) < 2:
        if printing:
            print("Invalid proof data.")
        return None
    
    # Get proof text and split into tactic blocks
    tactics_text = data[i][1]
    tactic_blocks = split_tactic_blocks(tactics_text)
    
    if printing:
        print(f"Found {len(tactic_blocks)} tactic blocks")
    
    # Use provided corpus set, or build it once if not provided (for v2)
    if version == "v2" and corpus_full_names_set is None and premise_registry:
        # Build normalized corpus lookup set (only if not provided)
        corpus_full_names_set = {normalize_unicode_symbols(p.get("full_name", "")) 
                                 for p in premise_registry if p.get("full_name")}
        if printing:
            print(f"Built corpus lookup with {len(corpus_full_names_set)} full names")
    
    # Extract all candidates in order
    all_candidates_list = []  # List of (tactic_block, candidate) tuples
    tactic_to_premises = {}  # Map full tactic block -> list of extracted premises
    
    for tac_block in tactic_blocks:
        # Extract candidates from this block
        cands = extract_lemma_candidates(tac_block)
        
        # Collect premises for this tactic block
        premises_from_tactic = []
        
        # Process candidates based on version
        for c in sorted(cands):  # Sort for consistent ordering
            if version == "v1":
                # v1: Raw extraction, no processing
                all_candidates_list.append((tac_block, c))
                premises_from_tactic.append(c)
            elif version == "v2":
                # v2: Check full name first, then break down if needed
                processed_candidate = _process_candidate_v2(c, corpus_full_names_set)
                if processed_candidate:
                    all_candidates_list.append((tac_block, processed_candidate))
                    premises_from_tactic.append(processed_candidate)
            else:
                # Default: treat as v1 for backward compatibility
                all_candidates_list.append((tac_block, c))
                premises_from_tactic.append(c)
        
        # Store mapping: full tactic -> list of premises (deduplicated)
        # Record all tactics that have premises extracted (after processing)
        if premises_from_tactic:  # If we have any premises after processing
            # Use tuple of sorted unique premises as key for consistent hashing
            unique_premises = sorted(set(premises_from_tactic))
            tactic_to_premises[tac_block] = unique_premises
    
    if printing:
        unique_candidates = len(set(c for _, c in all_candidates_list))
        print(f"Extracted {len(all_candidates_list)} total candidate usages")
        print(f"Found {unique_candidates} unique candidates")
        print(f"Found {len(tactic_to_premises)} tactic blocks with premises")
    
    # Return list of tuples in order of appearance, and tactic->premises mapping
    return all_candidates_list, tactic_to_premises


def _process_candidate_v2(candidate, corpus_full_names_set):
    """
    v2 processing: Check full candidate name in corpus first, then break down if not found.
    
    Args:
        candidate: Raw candidate name (e.g., "mem_sphere_zero_iff_norm.1")
        corpus_full_names_set: Pre-normalized set of all full names from corpus
        
    Returns:
        Processed candidate name (full name if found, or base name if broken down)
    """
    # Normalize Unicode symbols in candidate first
    candidate = normalize_unicode_symbols(candidate)
    
    # First, check if the full candidate name exists in corpus (already normalized)
    if candidate in corpus_full_names_set:
        return candidate
    
    # If not found, check if it has a projection/accessor pattern (ends with .1, .2, etc.)
    # Pattern: name.1, name.2, name.mp, name.mpr, etc.
    if "." in candidate:
        # Try to break it down: mem_sphere_zero_iff_norm.1 -> mem_sphere_zero_iff_norm
        parts = candidate.rsplit(".", 1)  # Split from right, get base and suffix
        if len(parts) == 2:
            base_name, suffix = parts
            
            # Check if base name exists in corpus (already normalized)
            if base_name in corpus_full_names_set:
                return base_name
            
            # Check if suffix is a projection pattern (.1, .2, .mp, .mpr, etc.)
            # These are typically tuple/record projections or modus ponens variants
            if suffix.isdigit() or suffix in ["mp", "mpr", "symm", "trans"]:
                # Return base name as the resolved candidate
                return base_name
            
            # If it's a multi-part name (e.g., Subtype.coe_injective.injOn)
            # Try checking if any prefix exists
            name_parts = candidate.split(".")
            for i in range(len(name_parts) - 1, 0, -1):
                partial_name = ".".join(name_parts[:i])
                if partial_name in corpus_full_names_set:
                    return partial_name
    
    # If no match found, return original candidate (will be marked as unresolved later)
    return candidate


def extract_all_premises_categorized(i, data, printing=False, strip_whitespace=True):
    """
    Extract and categorize all identifiers from a theorem's proof.
    
    Args:
        i: Proof index in data
        data: List of proof data from complete_proofs.json
        printing: Whether to print progress
        strip_whitespace: Whether to strip leading/trailing whitespace from tactic blocks
        
    Returns:
        Tuple of (tactic_blocks_categorized, summary) where:
        - tactic_blocks_categorized: dict mapping tactic_block -> categorized extraction dict
        - summary: aggregated counts across all tactics
        
        Each categorized extraction dict has keys:
            - global_lemmas: list of global lemma names
            - local_hypotheses: list of local hypothesis names  
            - local_var_access: list of local variable access patterns
            - keywords_modifiers: list of keywords/modifiers
            - type_class_annotations: list of type class names
            - type_variables: list of single uppercase letters
            - namespaces: list of namespace names
            - corrupted_unicode: list of corrupted unicode strings
            - other: list of uncategorized items
    """
    if printing:
        print(f"Extracting categorized candidates for proof index: {i}")
    
    if i >= len(data) or len(data[i]) < 2:
        if printing:
            print("Invalid proof data.")
        return None, None
    
    # Get proof text and split into tactic blocks
    tactics_text = data[i][1]
    tactic_blocks = split_tactic_blocks(tactics_text)
    
    if printing:
        print(f"Found {len(tactic_blocks)} tactic blocks")
    
    # Extract categorized candidates for each tactic block
    tactic_blocks_categorized = {}
    
    # Summary counters (all categories)
    summary = {
        "global_lemmas": Counter(),
        "local_hypotheses": Counter(),
        "local_var_access": Counter(),
        "keywords_modifiers": Counter(),
        "type_class_annotations": Counter(),
        "type_variables": Counter(),
        "namespaces": Counter(),
        "corrupted_unicode": Counter(),
        "other": Counter(),
    }
    
    for tac_block in tactic_blocks:
        # Strip whitespace from tactic block key if requested
        # This normalizes "  simp" and "    simp" to "simp"
        tac_key = tac_block.strip() if strip_whitespace else tac_block
        
        # Skip empty blocks after stripping
        if not tac_key:
            continue
        
        # Get categorized extraction for this block
        categories = extract_lemma_candidates_categorized(tac_block)
        
        # Store for this tactic block (using normalized key)
        # If key already exists, merge the categories
        if tac_key in tactic_blocks_categorized:
            existing = tactic_blocks_categorized[tac_key]
            for cat_name, items in categories.items():
                existing[cat_name].extend(items)
        else:
            tactic_blocks_categorized[tac_key] = categories
        
        # Aggregate into summary
        for cat_name, items in categories.items():
            for item in items:
                summary[cat_name][item] += 1
    
    if printing:
        print(f"Summary across {len(tactic_blocks)} tactic blocks ({len(tactic_blocks_categorized)} unique after normalization):")
        for cat_name, counter in summary.items():
            print(f"  {cat_name}: {len(counter)} unique, {sum(counter.values())} total")
    
    return tactic_blocks_categorized, summary
