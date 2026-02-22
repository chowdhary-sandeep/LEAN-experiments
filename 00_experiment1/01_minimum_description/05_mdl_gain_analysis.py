"""
MDL Gain Analysis for All Mathlib Theorems

Computes ΔL_MDL for each theorem and compares against theoretical baselines.
Following: papers/0_mdl_analysis_prompt.md
"""

import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import SymLogNorm
from pathlib import Path
from collections import Counter
import math

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "jsons" / "traced_theorems_unified_v2.jsonl"
FIGS_DIR = SCRIPT_DIR / "figs"

print("="*70)
print("MDL GAIN ANALYSIS: Computing Change in Description Length for All Theorems")
print("="*70)

# Constants (from earlier experiments)
TACTIC_VOCAB_SIZE = 278
THEOREM_COUNT = 99412
AVG_BITS_PER_TOKEN = 6  # From statement tokenization
BITS_PER_TACTIC = math.log2(TACTIC_VOCAB_SIZE)  # ~8.12
BITS_PER_REFERENCE = math.log2(THEOREM_COUNT)  # ~16.6

print(f"\nEncoding parameters:")
print(f"  Tactic vocabulary: {TACTIC_VOCAB_SIZE}")
print(f"  Bits per tactic: {BITS_PER_TACTIC:.2f}")
print(f"  Bits per theorem reference: {BITS_PER_REFERENCE:.2f}")


def compute_theorem_cost(thm):
    """Cost to add theorem T to library (bits)."""
    statement_cost = thm.get("metrics", {}).get("statement_length", 0) * AVG_BITS_PER_TOKEN

    if thm.get("proof_type") == "tactic":
        num_tactics = thm.get("metrics", {}).get("num_tactics", 0)
        proof_cost = num_tactics * BITS_PER_TACTIC
    else:  # term proof
        # Estimate from statement + premises
        stmt_len = thm.get("metrics", {}).get("statement_length", 0)
        num_premises = thm.get("metrics", {}).get("num_premises", 0)
        proof_cost = 0.3 * stmt_len * 7 + num_premises * BITS_PER_REFERENCE

    return statement_cost + proof_cost


def estimate_pattern_length(thm):
    """Estimate characteristic pattern length (in tactics)."""
    if thm.get("proof_type") == "tactic":
        return thm.get("metrics", {}).get("num_tactics", 0)
    else:
        # Heuristic for term proofs
        num_premises = thm.get("metrics", {}).get("num_premises", 0)
        return max(3, num_premises * 2)


# Load data
print("\n" + "="*70)
print("LOADING DATA")
print("="*70)

theorems = []
in_degrees = {}  # Will compute from premise references

with open(DATA_FILE, "r", encoding="utf-8") as f:
    for line_num, line in enumerate(f, 1):
        if not line.strip():
            continue

        try:
            thm = json.loads(line)
            theorems.append(thm)

            # Initialize in-degree
            name = thm.get("full_name")
            if name and name not in in_degrees:
                in_degrees[name] = 0

        except json.JSONDecodeError:
            continue

        if line_num % 50000 == 0:
            print(f"  Loaded {line_num:,} lines...")

print(f"\nLoaded {len(theorems):,} theorems")

# Compute in-degrees (how many theorems cite each theorem)
print("\nComputing in-degrees...")
for thm in theorems:
    all_premises = thm.get("all_premises", {})
    for premise_name in all_premises.keys():
        if premise_name in in_degrees:
            in_degrees[premise_name] += 1
        else:
            in_degrees[premise_name] = 1

print(f"  Computed in-degrees for {len(in_degrees):,} theorems/premises")

# Compute MDL gain for all theorems
print("\n" + "="*70)
print("COMPUTING MDL GAIN FOR ALL THEOREMS")
print("="*70)

results = []

for idx, thm in enumerate(theorems):
    name = thm.get("full_name", "")

    # Cost to define theorem
    cost = compute_theorem_cost(thm)

    # Pattern length
    pattern_length = estimate_pattern_length(thm)

    # Number of uses (in-degree)
    num_uses = in_degrees.get(name, 0)

    # Savings per use
    # Each use saves: (pattern_length tactics) - (1 reference)
    savings_per_use = pattern_length * BITS_PER_TACTIC - BITS_PER_REFERENCE

    # Total savings
    total_savings = num_uses * savings_per_use

    # Net MDL gain
    mdl_gain = total_savings - cost

    results.append({
        'theorem': name,
        'mdl_gain': mdl_gain,
        'cost': cost,
        'savings': total_savings,
        'num_uses': num_uses,
        'pattern_length': pattern_length,
        'savings_per_use': savings_per_use,
        'in_degree': num_uses,
        'out_degree': thm.get("metrics", {}).get("num_premises", 0),
        'proof_type': thm.get("proof_type", "term")
    })

    if (idx + 1) % 25000 == 0:
        print(f"  Processed {idx+1:,} theorems...")

df = pd.DataFrame(results)

print(f"\nCompleted MDL computation for {len(df):,} theorems")
print(f"  Mean MDL gain: {df['mdl_gain'].mean():.1f} bits")
print(f"  Median MDL gain: {df['mdl_gain'].median():.1f} bits")
print(f"  Total compression: {df['mdl_gain'].sum():,.0f} bits")

# Define baselines
print("\n" + "="*70)
print("DEFINING BASELINE MODELS")
print("="*70)

# Baseline 1: Random Library (no compression)
baseline_1 = [-row['cost'] for _, row in df.iterrows()]
print(f"  Baseline 1 (Random): All negative (pure overhead)")

# Baseline 2: Single-use
baseline_2 = []
for _, row in df.iterrows():
    cost = row['cost']
    pattern_length = row['pattern_length']
    savings = (pattern_length - 1) * BITS_PER_TACTIC - BITS_PER_REFERENCE
    baseline_2.append(max(savings - cost, -cost))  # Can't be worse than random

print(f"  Baseline 2 (Single-use): Mean = {np.mean(baseline_2):.1f} bits")

# Baseline 3: Citation-only (median pattern length)
median_pattern_length = df['pattern_length'].median()
median_cost = df['cost'].median()
print(f"  Using median pattern length: {median_pattern_length:.1f} tactics")
print(f"  Using median cost: {median_cost:.1f} bits")

baseline_3 = []
for _, row in df.iterrows():
    num_uses = row['num_uses']
    savings_per_use = median_pattern_length * BITS_PER_TACTIC - BITS_PER_REFERENCE
    baseline_3.append(num_uses * savings_per_use - median_cost)

print(f"  Baseline 3 (Citation-only): Mean = {np.mean(baseline_3):.1f} bits")

# Baseline 4: Perfect Crystallization
# Assume theorem abstracts pattern in ALL reachable nodes
baseline_4 = []
for _, row in df.iterrows():
    # Upper bound: num_uses + out_degree (all reachable)
    num_uses = row['in_degree'] + row['out_degree']
    pattern_length = row['pattern_length']
    cost = row['cost']

    savings_per_use = pattern_length * BITS_PER_TACTIC - BITS_PER_REFERENCE
    total_savings = num_uses * savings_per_use

    baseline_4.append(total_savings - cost)

print(f"  Baseline 4 (Perfect): Mean = {np.mean(baseline_4):.1f} bits")

# Create visualizations
print("\n" + "="*70)
print("GENERATING VISUALIZATIONS")
print("="*70)

# Plot 1: Distribution Comparison
fig, ax = plt.subplots(figsize=(14, 9))

df_sorted = df.sort_values('mdl_gain')
x = np.arange(len(df_sorted))

# Plot actual
scatter = ax.scatter(x, df_sorted['mdl_gain'],
                    c=df_sorted['in_degree'], cmap='viridis',
                    alpha=0.5, s=15, label='Actual Mathlib', norm=SymLogNorm(linthresh=1))

# Plot baselines
ax.plot(x, sorted(baseline_1), 'r--', linewidth=2.5,
        label='Baseline 1: Random (no compression)', alpha=0.8)
ax.plot(x, sorted(baseline_2), color='orange', linewidth=2.5,
        label='Baseline 2: Single-use', alpha=0.8)
ax.plot(x, sorted(baseline_3), 'b--', linewidth=2.5,
        label='Baseline 3: Citation-only', alpha=0.8)
ax.plot(x, sorted(baseline_4), 'g--', linewidth=2.5,
        label='Baseline 4: Perfect crystallization', alpha=0.8)

ax.axhline(y=0, color='black', linestyle=':', linewidth=2)
ax.set_xlabel('Theorem Rank (sorted by MDL gain)', fontsize=13, fontweight='bold', family='monospace')
ax.set_ylabel('ΔL_MDL (bits)', fontsize=13, fontweight='bold', family='monospace')
ax.set_yscale('symlog', linthresh=100)
ax.legend(fontsize=11, frameon=True, edgecolor='black', loc='upper left')
ax.grid(True, alpha=0.3)
ax.set_title('MDL Gain Distribution: Actual vs Theoretical Bounds',
             fontsize=15, fontweight='bold', family='monospace')

cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label('In-Degree (# citations)', fontsize=11, family='monospace')

plt.tight_layout()
save_path1 = FIGS_DIR / "mdl_gain_distribution.png"
fig.savefig(save_path1, dpi=300, bbox_inches='tight')
print(f"  Saved: {save_path1}")
plt.close()

# Plot 2: Phase Diagram
fig, ax = plt.subplots(figsize=(12, 9))

scatter = ax.scatter(df['in_degree'], df['pattern_length'],
                     c=df['mdl_gain'], cmap='RdYlGn',
                     s=40, alpha=0.6, norm=SymLogNorm(linthresh=100))

# Citation-only baseline line
ax.axhline(y=median_pattern_length, color='blue', linestyle='--',
          linewidth=2.5, alpha=0.8, label=f'Citation-only assumption\n(median={median_pattern_length:.1f})')

# ΔL = 0 contours
costs = [500, 1000, 2000, 5000]
for cost in costs:
    in_degrees_range = np.logspace(0, 4, 100)
    # ΔL = 0: num_uses * (pattern_length * 8.12 - 16.6) = cost
    # pattern_length = cost / (num_uses * 8.12) + 16.6 / 8.12
    pattern_lengths = cost / (in_degrees_range * BITS_PER_TACTIC) + BITS_PER_REFERENCE / BITS_PER_TACTIC
    pattern_lengths = np.clip(pattern_lengths, 1, 150)
    ax.plot(in_degrees_range, pattern_lengths, 'gray', alpha=0.4, linestyle=':',
           linewidth=1.5, label=f'ΔL=0 (cost={cost})' if cost == 500 else '')

ax.set_xlabel('In-Degree (# times theorem cited)', fontsize=13, fontweight='bold', family='monospace')
ax.set_ylabel('Pattern Length (# tactics)', fontsize=13, fontweight='bold', family='monospace')
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlim([0.9, 10000])
ax.set_ylim([1, 150])

cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label('ΔL_MDL (bits)', fontsize=12, family='monospace')

ax.legend(fontsize=10, frameon=True, edgecolor='black', loc='upper right')
ax.grid(True, alpha=0.3)
ax.set_title('MDL Phase Space: Citations vs Pattern Complexity',
            fontsize=15, fontweight='bold', family='monospace')

plt.tight_layout()
save_path2 = FIGS_DIR / "mdl_phase_diagram.png"
fig.savefig(save_path2, dpi=300, bbox_inches='tight')
print(f"  Saved: {save_path2}")
plt.close()

# Plot 3: Baseline Deviation Histograms
fig, axes = plt.subplots(2, 2, figsize=(16, 12))

baselines_dict = {
    'Random (no compression)': baseline_1,
    'Single-use': baseline_2,
    'Citation-only': baseline_3,
    'Perfect crystallization': baseline_4
}

for idx, (name, baseline) in enumerate(baselines_dict.items()):
    ax = axes[idx // 2, idx % 2]

    deviation = df['mdl_gain'].values - np.array(baseline)

    ax.hist(deviation, bins=60, alpha=0.7, edgecolor='black', linewidth=1.5, color='white')
    ax.axvline(x=0, color='red', linestyle='--', linewidth=2.5, label='Zero deviation')
    ax.axvline(x=np.median(deviation), color='green', linestyle='--',
              linewidth=2.5, label=f'Median: {np.median(deviation):.0f} bits')

    ax.set_xlabel(f'Actual - {name} (bits)', fontsize=12, fontweight='bold', family='monospace')
    ax.set_ylabel('Number of Theorems', fontsize=12, fontweight='bold', family='monospace')
    ax.set_title(f'Deviation from {name}', fontsize=13, fontweight='bold', family='monospace')
    ax.legend(fontsize=10, frameon=True, edgecolor='black')
    ax.grid(True, alpha=0.3)

plt.tight_layout()
save_path3 = FIGS_DIR / "mdl_baseline_deviations.png"
fig.savefig(save_path3, dpi=300, bbox_inches='tight')
print(f"  Saved: {save_path3}")
plt.close()

# Statistical Summary
print("\n" + "="*70)
print("STATISTICAL SUMMARY")
print("="*70)

summary = {
    'Total theorems': len(df),
    'Negative MDL (overhead)': (df['mdl_gain'] < 0).sum(),
    'Positive MDL (compressive)': (df['mdl_gain'] > 0).sum(),
    'Near-zero (-50 to +50 bits)': ((df['mdl_gain'] >= -50) & (df['mdl_gain'] <= 50)).sum(),

    'Median MDL gain': df['mdl_gain'].median(),
    'Mean MDL gain': df['mdl_gain'].mean(),
    'Total compression': df['mdl_gain'].sum(),

    'Above random baseline': (df['mdl_gain'] > np.array(baseline_1)).sum(),
    'Above single-use': (df['mdl_gain'] > np.array(baseline_2)).sum(),
    'Above citation-only': (df['mdl_gain'] > np.array(baseline_3)).sum(),
    'Below perfect': (df['mdl_gain'] < np.array(baseline_4)).sum(),

    'Optimization gap (vs perfect)': (np.array(baseline_4) - df['mdl_gain'].values).sum(),
    'Efficiency ratio': df['mdl_gain'].sum() / np.array(baseline_4).sum() if np.array(baseline_4).sum() > 0 else 0,
}

for key, value in summary.items():
    if isinstance(value, (int, np.integer)):
        print(f"{key:.<50} {value:>15,}")
    else:
        print(f"{key:.<50} {value:>15.1f}")

# Top/Bottom Analysis
print("\n" + "="*70)
print("TOP 20 MOST COMPRESSIVE THEOREMS")
print("="*70)

top_20 = df.nlargest(20, 'mdl_gain')[['theorem', 'mdl_gain', 'num_uses', 'pattern_length', 'in_degree']]
for idx, row in top_20.iterrows():
    short_name = row['theorem'].split('.')[-1][:50] if '.' in row['theorem'] else row['theorem'][:50]
    print(f"{short_name:50s} | MDL: {row['mdl_gain']:>10.0f} | Uses: {row['num_uses']:>5} | Len: {row['pattern_length']:>3}")

print("\n" + "="*70)
print("BOTTOM 20 (MOST WASTEFUL OVERHEAD)")
print("="*70)

bottom_20 = df.nsmallest(20, 'mdl_gain')[['theorem', 'mdl_gain', 'num_uses', 'pattern_length', 'cost']]
for idx, row in bottom_20.iterrows():
    short_name_raw = row['theorem'].split('.')[-1][:50] if '.' in row['theorem'] else row['theorem'][:50]
    short_name = short_name_raw.encode('ascii', 'replace').decode('ascii')  # Handle Unicode
    print(f"{short_name:50s} | MDL: {row['mdl_gain']:>10.0f} | Uses: {row['num_uses']:>5} | Cost: {row['cost']:>6.0f}")

# Save results
df.to_csv(SCRIPT_DIR / "mdl_gain_results.csv", index=False)
print(f"\nSaved full results to: mdl_gain_results.csv")

print("\n" + "="*70)
print("MDL GAIN ANALYSIS COMPLETE")
print("="*70)
print(f"Generated 3 figures:")
print(f"  1. {save_path1}")
print(f"  2. {save_path2}")
print(f"  3. {save_path3}")
