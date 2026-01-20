# Migration Instructions: Replace premise_registry with corpus.jsonl

## Changes Made

### 1. Added `load_corpus_premises()` function to `00_myutils2.py`

This function loads `corpus.jsonl` and flattens it into a format compatible with `build_premise_index()`.

**Location**: `00_myutils2.py` (added before `build_premise_index`)

**Function**:
```python
def load_corpus_premises(corpus_path="corpus.jsonl"):
    """
    Load corpus.jsonl and flatten it into a list of premises.
    Each premise dict will have:
      - full_name: from premise entry
      - defPath: from file's path field (for compatibility with premise_registry format)
      - path: from file's path field (original corpus field)
      - All other fields from the premise entry (code, start, end, kind, etc.)
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
```

### 2. Update Notebook Cell

In `reprover_demo.ipynb`, find the cell that loads the premise registry (around line 798-834) and replace:

**OLD CODE**:
```python
# Load premise registry (for premise/lemma resolution)
premise_registry = []
with open("premise_registry_unique.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            premise_registry.append(json.loads(line))

print(f"Loaded {len(premise_registry)} unique premises from registry")

# Reload modules
import importlib.util
import sys
...
```

**NEW CODE**:
```python
# Reload modules first (so we can import load_corpus_premises)
import importlib.util
import sys
...
# (keep all the module reloading code)

# Load corpus and extract premises (for premise/lemma resolution)
# Use corpus.jsonl instead of premise_registry_unique.jsonl
premise_registry = load_corpus_premises("corpus.jsonl")

print(f"Loaded {len(premise_registry)} premises from corpus")
```

**Key changes**:
1. Move module reloading BEFORE loading premises (so `load_corpus_premises` is available)
2. Replace the file reading loop with `load_corpus_premises("corpus.jsonl")`
3. Update the print message

### 3. How It Works

- `extract_all_premises()` extracts raw candidate names from tactics (unchanged)
- `run_proof_tactics()` calls `build_premise_index(premise_registry)` to build search indices
- `resolve_candidate()` searches these indices to match candidates to full premise names
- The corpus data is flattened so each premise has:
  - `full_name`: Used for matching
  - `defPath`: Used for file preference in resolution
  - All other fields preserved from corpus

### 4. Testing

After making changes:
1. Reload the notebook cell
2. Run `run_proof_tactics()` with a test proof
3. Verify that:
   - Premises are resolved correctly
   - File paths are preserved
   - Resolution statistics look reasonable

### 5. Benefits

- Uses comprehensive corpus.jsonl data (all lemmas/premises)
- Maintains compatibility with existing code (same variable name, same format)
- Preserves file path information for better resolution
- No changes needed to `build_premise_index()` or `resolve_candidate()`
