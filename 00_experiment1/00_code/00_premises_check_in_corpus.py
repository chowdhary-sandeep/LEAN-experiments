"""
Check if global_lemmas from 00_full_tactic_to_premises_categorized.json
exist in corpus.jsonl, with both EXACT and SUFFIX matching.

The issue: Corpus has QUALIFIED names (e.g., "Nat.add_comm", "Int.add_comm")
but extracted lemmas are often UNQUALIFIED (just "add_comm").

This script does:
1. Exact matching (lemma == corpus_name)
2. Suffix matching (corpus_name ends with ".lemma")
3. Reports which namespaced versions exist for unmatched lemmas
"""

import json
from collections import Counter, defaultdict
from pathlib import Path
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent

# =============================================================================
# LOAD CORPUS
# =============================================================================
print("Loading corpus.jsonl...")
corpus_full_names = set()
corpus_by_suffix = defaultdict(list)  # {suffix: [full_names]}

with open(_PROJECT_DIR.parent / "corpus.jsonl", "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if not line.strip():
            continue
        try:
            file_entry = json.loads(line)
            for prem in file_entry.get("premises", []):
                full_name = prem.get("full_name", "")
                if full_name:
                    corpus_full_names.add(full_name)
                    # Index by suffix (last component after dot)
                    if "." in full_name:
                        suffix = full_name.rsplit(".", 1)[1]
                        corpus_by_suffix[suffix].append(full_name)
                    else:
                        corpus_by_suffix[full_name].append(full_name)
        except Exception as e:
            print(f"Warning: Error parsing line {line_num}: {e}")

print(f"Loaded {len(corpus_full_names):,} unique full names from corpus")
print(f"Indexed {len(corpus_by_suffix):,} unique suffixes for fuzzy matching")

# =============================================================================
# LOAD EXTRACTED LEMMAS
# =============================================================================
print("\nLoading 00_full_tactic_to_premises_categorized.json...")
with open(_PROJECT_DIR / "00_full_tactic_to_premises_categorized.json", "r", encoding="utf-8") as f:
    categorized_data = json.load(f)

print(f"Loaded {len(categorized_data):,} unique tactic blocks")

# Extract all global_lemmas
print("\nExtracting global_lemmas...")
all_global_lemmas = []

for tactic_block, entry_data in categorized_data.items():
    categories = entry_data.get("categories", {})
    global_lemmas = categories.get("global_lemmas", {})
    for lemma_name, count in global_lemmas.items():
        all_global_lemmas.extend([lemma_name] * count)

occurrence_counter = Counter(all_global_lemmas)
print(f"Found {len(all_global_lemmas):,} total occurrences")
print(f"Found {len(occurrence_counter):,} unique lemmas")

# =============================================================================
# MATCHING
# =============================================================================
print("\nMatching lemmas against corpus...")

# Categories for matching results
exact_matches = {}          # lemma -> count (exact match in corpus)
suffix_matches = {}         # lemma -> count (suffix match found)
suffix_match_details = {}   # lemma -> [list of matching full names]
no_matches = {}             # lemma -> count (no match at all)

for lemma, count in occurrence_counter.items():
    # 1. Check exact match
    if lemma in corpus_full_names:
        exact_matches[lemma] = count
        continue
    
    # 2. Check suffix match (unqualified name matches end of qualified name)
    # Check if lemma is a suffix in our index
    if lemma in corpus_by_suffix:
        suffix_matches[lemma] = count
        suffix_match_details[lemma] = corpus_by_suffix[lemma]
        continue
    
    # 3. For qualified names like "Function.comp_apply", check if full name exists
    if "." in lemma:
        # Also check suffix of the extracted name
        extracted_suffix = lemma.rsplit(".", 1)[1]
        if extracted_suffix in corpus_by_suffix:
            # Find matches that end with our lemma
            matching_full_names = [n for n in corpus_by_suffix[extracted_suffix] if n.endswith(lemma)]
            if matching_full_names:
                suffix_matches[lemma] = count
                suffix_match_details[lemma] = matching_full_names
                continue
    
    # 4. No match found
    no_matches[lemma] = count

# =============================================================================
# CALCULATE STATISTICS
# =============================================================================
total_occ = len(all_global_lemmas)
total_unique = len(occurrence_counter)

exact_occ = sum(exact_matches.values())
exact_unique = len(exact_matches)

suffix_occ = sum(suffix_matches.values())
suffix_unique = len(suffix_matches)

total_matched_occ = exact_occ + suffix_occ
total_matched_unique = exact_unique + suffix_unique

no_match_occ = sum(no_matches.values())
no_match_unique = len(no_matches)

# =============================================================================
# PRINT RESULTS
# =============================================================================
print("\n" + "="*70)
print("MATCHING RESULTS")
print("="*70)

print(f"\nTotal extracted global_lemmas:")
print(f"  Occurrences: {total_occ:,}")
print(f"  Unique: {total_unique:,}")

print(f"\n--- EXACT MATCHES (lemma == corpus_name) ---")
print(f"  Occurrences: {exact_occ:,} ({exact_occ/max(1,total_occ)*100:.1f}%)")
print(f"  Unique: {exact_unique:,} ({exact_unique/max(1,total_unique)*100:.1f}%)")

print(f"\n--- SUFFIX MATCHES (corpus_name ends with .lemma) ---")
print(f"  Occurrences: {suffix_occ:,} ({suffix_occ/max(1,total_occ)*100:.1f}%)")
print(f"  Unique: {suffix_unique:,} ({suffix_unique/max(1,total_unique)*100:.1f}%)")

print(f"\n--- TOTAL MATCHED (exact + suffix) ---")
print(f"  Occurrences: {total_matched_occ:,} ({total_matched_occ/max(1,total_occ)*100:.1f}%)")
print(f"  Unique: {total_matched_unique:,} ({total_matched_unique/max(1,total_unique)*100:.1f}%)")

print(f"\n--- NO MATCH ---")
print(f"  Occurrences: {no_match_occ:,} ({no_match_occ/max(1,total_occ)*100:.1f}%)")
print(f"  Unique: {no_match_unique:,} ({no_match_unique/max(1,total_unique)*100:.1f}%)")

# =============================================================================
# TOP MATCHES
# =============================================================================
print("\n" + "="*70)
print("TOP 15 EXACT MATCHES")
print("="*70)
for lemma, count in sorted(exact_matches.items(), key=lambda x: -x[1])[:15]:
    print(f"  {lemma:40s}: {count:,}")

print("\n" + "="*70)
print("TOP 15 SUFFIX MATCHES (with corpus names)")
print("="*70)
for lemma, count in sorted(suffix_matches.items(), key=lambda x: -x[1])[:15]:
    corpus_names = suffix_match_details.get(lemma, [])
    num_variants = len(corpus_names)
    examples = corpus_names[:3]
    print(f"  {lemma:30s}: {count:,} ({num_variants} variants)")
    for ex in examples:
        print(f"    -> {ex}")

print("\n" + "="*70)
print("TOP 20 NO MATCH (not in corpus at all)")
print("="*70)
for lemma, count in sorted(no_matches.items(), key=lambda x: -x[1])[:20]:
    print(f"  {lemma:40s}: {count:,}")

# =============================================================================
# SAVE RESULTS
# =============================================================================
print("\n" + "="*70)
print("SAVING RESULTS")
print("="*70)

# Combine exact and suffix matches for the "matched" output
all_matched = {**exact_matches, **suffix_matches}

with open(_PROJECT_DIR / "lemma_candidate_counter.json", "w", encoding="utf-8") as f:
    json.dump(all_matched, f, indent=2, ensure_ascii=False)
print(f"Saved {len(all_matched):,} matched lemmas to lemma_candidate_counter.json")

with open(_PROJECT_DIR / "lemma_candidate_counter_filtered_out.json", "w", encoding="utf-8") as f:
    json.dump(no_matches, f, indent=2, ensure_ascii=False)
print(f"Saved {len(no_matches):,} unmatched lemmas to lemma_candidate_counter_filtered_out.json")

# Save detailed suffix match info
suffix_details_output = {
    lemma: {
        "count": suffix_matches[lemma],
        "corpus_names": suffix_match_details[lemma]
    }
    for lemma in suffix_matches
}
with open(_PROJECT_DIR / "lemma_suffix_matches.json", "w", encoding="utf-8") as f:
    json.dump(suffix_details_output, f, indent=2, ensure_ascii=False)
print(f"Saved suffix match details to lemma_suffix_matches.json")

# =============================================================================
# ANALYSIS OF NO-MATCHES
# =============================================================================
print("\n" + "="*70)
print("ANALYSIS: WHY ARE THESE NOT MATCHING?")
print("="*70)

# Categorize no-matches
no_match_analysis = {
    "looks_like_tactic": [],      # Might be tactics misclassified
    "looks_like_local": [],        # Might be local hypotheses
    "looks_like_type": [],         # Might be type names
    "qualified_but_wrong_ns": [],  # Has dots but namespace doesn't match
    "other": []
}

TACTIC_NAMES = {"filter_upwards", "split_ifs", "mod_cast", "push_cast", "rwa", 
                "classical", "mono", "tfae_have", "tfae_finish", "infer_instance"}
LOCAL_PATTERNS = ["h_", "hp_", "hf_", "this.", "h."]

for lemma in no_matches:
    if lemma in TACTIC_NAMES or lemma.startswith("by_"):
        no_match_analysis["looks_like_tactic"].append(lemma)
    elif any(lemma.startswith(p) or lemma == "this" for p in LOCAL_PATTERNS):
        no_match_analysis["looks_like_local"].append(lemma)
    elif lemma[0].isupper() and "_" not in lemma and "." not in lemma:
        no_match_analysis["looks_like_type"].append(lemma)
    elif "." in lemma:
        no_match_analysis["qualified_but_wrong_ns"].append(lemma)
    else:
        no_match_analysis["other"].append(lemma)

print("\nNo-match breakdown:")
for category, items in no_match_analysis.items():
    total_count = sum(no_matches.get(item, 0) for item in items)
    print(f"  {category}: {len(items)} unique, {total_count:,} occurrences")
    if items:
        top_items = sorted(items, key=lambda x: -no_matches.get(x, 0))[:5]
        for item in top_items:
            print(f"    - {item}: {no_matches[item]:,}")

print("\nDone!")
