#!/usr/bin/env python3
"""
Extract code from corpus.jsonl for all entries.
Creates a mapping from full_name to code for use by the server.
"""

import json
from pathlib import Path
from collections import defaultdict

_SCRIPT_DIR = Path(__file__).resolve().parent
CORPUS_FILE = _SCRIPT_DIR / "jsons" / "corpus.jsonl"
OUTPUT_FILE = _SCRIPT_DIR / "jsons" / "corpus_code_index.json"

def extract_code_from_corpus(corpus_file, output_file):
    """
    Extract code field from all premises in corpus.jsonl.
    Creates a mapping: full_name -> code
    """
    print(f"Reading corpus from: {corpus_file}")
    
    code_index = {}  # full_name -> code
    total_entries = 0
    total_premises = 0
    
    with open(corpus_file, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                entry = json.loads(line)
                total_entries += 1
                
                premises = entry.get("premises", [])
                for prem in premises:
                    full_name = prem.get("full_name")
                    code = prem.get("code", "")
                    
                    if full_name:
                        total_premises += 1
                        # If multiple entries have same full_name, keep the last one
                        # (or you could merge/concatenate if needed)
                        code_index[full_name] = code
                
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse line {line_num}: {e}")
                continue
            except Exception as e:
                print(f"Warning: Error processing line {line_num}: {e}")
                continue
    
    print(f"Processed {total_entries} entries")
    print(f"Extracted code for {total_premises} premises")
    print(f"Unique full_names: {len(code_index)}")
    
    # Save to JSON file
    print(f"\nSaving code index to: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(code_index, f, ensure_ascii=False, indent=2)
    
    print(f"Done! Code index saved with {len(code_index)} entries.")
    return code_index


if __name__ == "__main__":
    extract_code_from_corpus(CORPUS_FILE, OUTPUT_FILE)
