"""Show sample records from the unified traced file."""
import json
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

print("="*80)
print("SAMPLE RECORDS FROM traced_theorems_unified.jsonl")
print("="*80)

with open("traced_theorems_unified.jsonl", "r", encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= 3:
            break
        
        thm = json.loads(line)
        
        print(f"\n{'='*80}")
        print(f"THEOREM {i+1}: {thm['full_name']}")
        print("="*80)
        
        print(f"\n📁 File: {thm['file']}")
        print(f"📊 Tactics: {thm['num_tactics']}, Premises: {thm['num_premises']}")
        print(f"⚠️  Unicode issues: {thm['has_unicode_issues']}")
        
        print(f"\n--- TACTICS ({len(thm['tactics'])}) ---")
        for tac in thm['tactics'][:3]:  # Show first 3
            print(f"\n  [{tac['index']}] {tac['tactic'][:60]}...")
            print(f"      Context:")
            ctx = tac['context']
            if ctx['variables']:
                vars_str = ', '.join(f"{k}: {v}" for k, v in list(ctx['variables'].items())[:3])
                print(f"        Variables: {vars_str}...")
            if ctx['typeclasses']:
                print(f"        Typeclasses: {ctx['typeclasses'][:2]}...")
            if ctx['goal']:
                print(f"        Goal: {ctx['goal'][:50]}...")
            print(f"      Premises: {[p['full_name'] for p in tac['premises'][:3]]}")
        
        if len(thm['tactics']) > 3:
            print(f"\n  ... and {len(thm['tactics']) - 3} more tactics")
        
        print(f"\n--- ALL PREMISES USED ---")
        for prem_name, prem_info in list(thm['all_premises'].items())[:5]:
            print(f"  {prem_name}: used {prem_info['count']}x in tactics {prem_info['tactics']}")
        if len(thm['all_premises']) > 5:
            print(f"  ... and {len(thm['all_premises']) - 5} more premises")

# Stats
print("\n\n" + "="*80)
print("FILE STATISTICS")
print("="*80)

total_thms = 0
total_tactics = 0
total_premises = 0
resolved_counts = {"leandojo_annotation": 0, "unique": 0, "exact": 0, "not_found": 0, "other": 0}

with open("traced_theorems_unified.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        thm = json.loads(line)
        total_thms += 1
        total_tactics += thm['num_tactics']
        
        for tac in thm['tactics']:
            for prem in tac['premises']:
                total_premises += 1
                resolved_by = prem.get('resolved_by', 'other')
                if resolved_by.startswith('type_hint'):
                    resolved_counts['other'] += 1
                elif resolved_by.startswith('ambiguous'):
                    resolved_counts['other'] += 1
                elif resolved_by in resolved_counts:
                    resolved_counts[resolved_by] += 1
                else:
                    resolved_counts['other'] += 1

print(f"\nTotal theorems: {total_thms:,}")
print(f"Total tactics: {total_tactics:,}")
print(f"Total premise references: {total_premises:,}")

print("\nPremise resolution breakdown:")
for method, count in sorted(resolved_counts.items(), key=lambda x: -x[1]):
    pct = count / max(1, total_premises) * 100
    print(f"  {method}: {count:,} ({pct:.1f}%)")
