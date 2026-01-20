"""
Categorized extraction of premises from Lean proofs.

This script extracts and categorizes all identifiers from tactic blocks:
- global_lemmas: Qualified names, snake_case lemmas
- local_hypotheses: h, x, h1, this, ih, h_eq, etc.
- local_var_access: x.property, this.method, f.rootSet
- keywords_modifiers: tactic names, only, using, etc.
- type_class_annotations: MapsTo, Monoid, Injective, etc.
- type_variables: Single uppercase letters (A, B, R, etc.)
- namespaces: ENNReal, Function, Submodule, etc.
- corrupted_unicode: â, ð (encoding garbage)
- other: Anything not matching above categories

Output files:
- 00_full_tactic_to_premises_categorized.json: Per-tactic-block data
- 00_global_category_summary.json: Global statistics
"""

import json
import sys
import importlib.util
from collections import Counter, defaultdict
from tqdm import tqdm

# Load data
print("Loading data...")
with open('complete_proofs.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
print(f'Loaded {len(data)} proofs')

# Load myutils2 (force reload to get latest changes)
if 'myutils2' in sys.modules:
    del sys.modules['myutils2']
    
spec = importlib.util.spec_from_file_location('myutils2', '00_myutils2.py')
module = importlib.util.module_from_spec(spec)
sys.modules['myutils2'] = module
spec.loader.exec_module(module)

from myutils2 import extract_all_premises_categorized, extract_lemma_candidates_categorized

# Categories to track (must match function output)
CATEGORIES = [
    "global_lemmas",
    "local_hypotheses", 
    "local_var_access",
    "keywords_modifiers",
    "type_class_annotations",
    "type_variables",
    "namespaces",
    "corrupted_unicode",
    "other",
]

# Global accumulators
global_summary = {cat: Counter() for cat in CATEGORIES}
tactic_block_categorized = defaultdict(lambda: defaultdict(Counter))
tactic_blocks_in_proofs_cat = defaultdict(set)

# Process all proofs
print('Processing proofs...')
for i in tqdm(range(len(data)), desc='Categorized extraction'):
    result = extract_all_premises_categorized(i=i, data=data, printing=False, strip_whitespace=True)
    if result is None or result[0] is None:
        continue
    tactic_blocks_cat, proof_summary = result
    
    # Aggregate global summary
    for cat_name, counter in proof_summary.items():
        global_summary[cat_name].update(counter)
    
    # Aggregate per-tactic-block data
    for tactic, categories in tactic_blocks_cat.items():
        tactic_blocks_in_proofs_cat[tactic].add(i)
        for cat_name, items in categories.items():
            for item in items:
                tactic_block_categorized[tactic][cat_name][item] += 1

# Build output
print("Building output...")
total_proofs = len(data)
categorized_output = {}

for tactic in tactic_block_categorized:
    num_proofs = len(tactic_blocks_in_proofs_cat[tactic])
    pct = (num_proofs / total_proofs) * 100 if total_proofs > 0 else 0
    
    categories_dict = {}
    category_totals = {}
    
    for cat_name in CATEGORIES:
        cat_data = dict(tactic_block_categorized[tactic][cat_name])
        categories_dict[cat_name] = cat_data
        category_totals[cat_name] = sum(cat_data.values())
    
    categorized_output[tactic] = {
        'tactic_block_count': num_proofs,
        'tactic_block_percentage_occurrence': pct,
        'categories': categories_dict,
        'category_totals': category_totals,
    }

# Sort by count
sorted_output = dict(sorted(categorized_output.items(), key=lambda x: x[1]['tactic_block_count'], reverse=True))

# Save categorized output
print("Saving categorized output...")
with open('00_full_tactic_to_premises_categorized.json', 'w', encoding='utf-8') as f:
    json.dump(sorted_output, f, indent=2, ensure_ascii=False)
print(f'Saved {len(sorted_output)} unique tactic blocks to 00_full_tactic_to_premises_categorized.json')

# Save global summary
global_summary_output = {
    cat_name: {
        'unique_count': len(counter),
        'total_occurrences': sum(counter.values()),
        'top_50': dict(counter.most_common(50)),
        'all_items': dict(counter)
    }
    for cat_name, counter in global_summary.items()
}

with open('00_global_category_summary.json', 'w', encoding='utf-8') as f:
    json.dump(global_summary_output, f, indent=2, ensure_ascii=False)
print('Saved global summary to 00_global_category_summary.json')

# Print stats
print()
print('=' * 60)
print('GLOBAL SUMMARY')
print('=' * 60)
total_unique = 0
total_occurrences = 0
for cat_name, counter in global_summary.items():
    unique = len(counter)
    total = sum(counter.values())
    total_unique += unique
    total_occurrences += total
    print(f'{cat_name:25s}: {unique:6d} unique, {total:8d} total')

print()
print(f'{"TOTAL":25s}: {total_unique:6d} unique, {total_occurrences:8d} total')

# Signal vs noise analysis
print()
print('=' * 60)
print('SIGNAL VS NOISE')
print('=' * 60)
lemmas_unique = len(global_summary["global_lemmas"])
lemmas_total = sum(global_summary["global_lemmas"].values())

noise_cats = ["local_hypotheses", "local_var_access", "keywords_modifiers", "corrupted_unicode"]
noise_unique = sum(len(global_summary[c]) for c in noise_cats)
noise_total = sum(sum(global_summary[c].values()) for c in noise_cats)

context_cats = ["type_class_annotations", "type_variables", "namespaces"]
context_unique = sum(len(global_summary[c]) for c in context_cats)
context_total = sum(sum(global_summary[c].values()) for c in context_cats)

other_unique = len(global_summary["other"])
other_total = sum(global_summary["other"].values())

print(f'Global lemmas (signal):   {lemmas_unique:6d} unique, {lemmas_total:8d} total')
print(f'Filtered items (noise):   {noise_unique:6d} unique, {noise_total:8d} total')
print(f'Context items (types):    {context_unique:6d} unique, {context_total:8d} total')
print(f'Other (unclassified):     {other_unique:6d} unique, {other_total:8d} total')
print()
print(f'Signal/noise ratio: {lemmas_total/max(1,noise_total):.2f}x')

# Show top 10 tactic blocks
print()
print('=' * 60)
print('TOP 10 TACTIC BLOCKS (after whitespace normalization)')
print('=' * 60)
for i, (tactic, tdata) in enumerate(list(sorted_output.items())[:10]):
    print(f"\n{i+1}. Count: {tdata['tactic_block_count']} ({tdata['tactic_block_percentage_occurrence']:.3f}%)")
    # Escape tactic for display
    tactic_display = repr(tactic[:80]) if len(tactic) > 80 else repr(tactic)
    print(f"   Tactic: {tactic_display}")
    # Show non-zero category totals
    non_zero = {k: v for k, v in tdata['category_totals'].items() if v > 0}
    print(f"   Non-zero categories: {non_zero}")

# Show top 20 global lemmas
print()
print('=' * 60)
print('TOP 20 GLOBAL LEMMAS')
print('=' * 60)
for lemma, count in global_summary["global_lemmas"].most_common(20):
    print(f"  {lemma:40s}: {count:6d}")

# Show items still in "other" category
print()
print('=' * 60)
print('TOP 20 "OTHER" ITEMS (need further classification)')
print('=' * 60)
for item, count in global_summary["other"].most_common(20):
    print(f"  {item:40s}: {count:6d}")

print()
print("Done!")
