"""Check why common lemmas aren't found in corpus.jsonl"""
import json

# Load corpus and check for these lemmas
lemmas_to_check = [
    'add_comm', 'comp_apply', 'congr_arg', 'zero_add', 
    'mul_zero', 'add_zero', 'map_zero', 'sub_eq_add_neg', 
    'ext_iff', 'mem_univ'
]

corpus_names = set()

print('Loading corpus.jsonl...')
with open('corpus.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if not line.strip():
            continue
        entry = json.loads(line)
        for prem in entry.get('premises', []):
            full_name = prem.get('full_name', '')
            if full_name:
                corpus_names.add(full_name)

print(f'Loaded {len(corpus_names)} unique names from corpus')

# Check for exact matches
print()
print('=== EXACT MATCH CHECK ===')
for lemma in lemmas_to_check:
    if lemma in corpus_names:
        print(f'{lemma}: FOUND')
    else:
        print(f'{lemma}: NOT FOUND')

# Check for partial matches (names ending with the lemma)
print()
print('=== NAMES ENDING WITH LEMMA (e.g., Namespace.lemma) ===')
for lemma in lemmas_to_check:
    matches = sorted([n for n in corpus_names if n.endswith('.' + lemma) or n == lemma])[:10]
    if matches:
        print(f'{lemma}:')
        for m in matches:
            print(f'  - {m}')
    else:
        print(f'{lemma}: No matches ending with .{lemma}')

# Check for partial matches (names containing the lemma)
print()
print('=== NAMES CONTAINING LEMMA ===')
for lemma in lemmas_to_check[:5]:  # Just first 5 to avoid too much output
    matches = sorted([n for n in corpus_names if lemma in n])[:10]
    if matches:
        print(f'{lemma}: {len([n for n in corpus_names if lemma in n])} total matches')
        for m in matches[:5]:
            print(f'  - {m}')
    else:
        print(f'{lemma}: No partial matches')

# Check a sample of corpus entries to understand structure
print()
print('=== SAMPLE CORPUS STRUCTURE ===')
with open('corpus.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        if not line.strip():
            continue
        entry = json.loads(line)
        print(f"\nFile: {entry.get('path', 'N/A')}")
        premises = entry.get('premises', [])
        print(f"  Number of premises: {len(premises)}")
        if premises:
            print(f"  First 3 premise names: {[p.get('full_name') for p in premises[:3]]}")

# Check what kinds of names ARE in the corpus
print()
print('=== CORPUS NAME PATTERNS ===')
# Count by first component (namespace)
namespaces = {}
for name in corpus_names:
    if '.' in name:
        ns = name.split('.')[0]
    else:
        ns = '(no namespace)'
    namespaces[ns] = namespaces.get(ns, 0) + 1

print('Top 20 namespaces in corpus:')
for ns, count in sorted(namespaces.items(), key=lambda x: -x[1])[:20]:
    print(f'  {ns}: {count}')

# Check if these are Lean 4 standard library names that might not be traced
print()
print('=== CHECKING FOR LEAN 4 CORE LIBRARY PATTERNS ===')
core_prefixes = ['Init.', 'Std.', 'Lean.']
core_count = sum(1 for n in corpus_names if any(n.startswith(p) for p in core_prefixes))
print(f'Names starting with Init./Std./Lean.: {core_count}')

mathlib_count = sum(1 for n in corpus_names if n.startswith('Mathlib.') or '.' not in n or n.split('.')[0][0].isupper())
print(f'Names looking like Mathlib (Capitalized namespace or no namespace): {mathlib_count}')
