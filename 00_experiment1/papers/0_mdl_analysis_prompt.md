# Computing MDL Gain for All Mathlib Theorems: Analysis Prompt

## Objective

For each theorem T in Mathlib, compute ΔL_MDL(T) = compression gain from T's existence. Plot the distribution and compare against theoretical baselines representing extreme boundary conditions. Interpret where the actual mathematical library sits relative to these extremes.

---

## Part 1: Compute MDL Gain for All Theorems

### Data Available
- 99,412 theorems with: statement, proof (tactics or term), premises, in-degree, out-degree
- Dependency graph (with cycles, 2,611 components)
- For tactic proofs: full tactic sequences
- For term proofs: statement_length as proxy

### Computation Pipeline

**Step 1: For each theorem T, compute L(T) - cost of defining T**

```python
def compute_theorem_cost(T):
    """Cost to add theorem T to library"""
    
    # Statement cost (tokenized, entropy-coded)
    statement_cost = len(tokenize(T.statement)) * avg_bits_per_token  # ~180 bits
    
    # Proof cost
    if T.proof_type == 'tactic':
        # Tactic sequence length × bits per tactic
        proof_cost = len(T.tactics) * log2(tactic_vocab_size)  # ~11 bits/tactic
    else:  # term proof
        # Estimate from statement length + premise count
        proof_cost = 0.3 * T.statement_length * 7 + len(T.premises) * 17
    
    return statement_cost + proof_cost
```

**Step 2: For each theorem T, estimate how many proofs use T's pattern**

```python
def estimate_pattern_usage(T, mathlib):
    """How many proofs would need to inline T's pattern if T didn't exist?"""
    
    # Explicit uses: count T's in-degree
    explicit_uses = T.in_degree
    
    # Implicit uses: proofs with similar tactic patterns (expensive - approximate)
    # For now: assume explicit captures most usage
    # TODO: implement tactic AST isomorphism for subset
    
    return explicit_uses

def estimate_pattern_length(T):
    """How long is T's characteristic proof pattern?"""
    
    if T.proof_type == 'tactic':
        return len(T.tactics)
    else:
        # Estimate from premises and statement complexity
        return max(3, len(T.premises) * 2)  # heuristic
```

**Step 3: Compute MDL gain**

```python
def compute_mdl_gain(T, mathlib):
    """
    ΔL_MDL(T) = savings from abstraction - cost of theorem
    """
    
    # Cost to define T
    cost_of_T = compute_theorem_cost(T)
    
    # How many proofs use T?
    num_uses = estimate_pattern_usage(T, mathlib)
    
    # Pattern length
    pattern_length = estimate_pattern_length(T)
    
    # Savings per use
    # Each use saves: (pattern_length tactics) - (1 reference)
    bits_per_tactic = log2(2000)  # ~11 bits
    bits_per_reference = log2(99412)  # ~17 bits
    
    savings_per_use = pattern_length * bits_per_tactic - bits_per_reference
    
    # Total savings
    total_savings = num_uses * savings_per_use
    
    # Net gain
    mdl_gain = total_savings - cost_of_T
    
    return {
        'mdl_gain': mdl_gain,
        'cost': cost_of_T,
        'savings': total_savings,
        'num_uses': num_uses,
        'pattern_length': pattern_length,
        'savings_per_use': savings_per_use
    }

# Compute for all theorems
results = []
for T in mathlib.theorems:
    result = compute_mdl_gain(T, mathlib)
    result['theorem'] = T.full_name
    result['in_degree'] = T.in_degree
    result['out_degree'] = T.out_degree
    results.append(result)

df = pd.DataFrame(results)
```

---

## Part 2: Define Baseline/Extreme Models

Think like a physicist: bound the system with extreme cases, locate reality within.

### Baseline 1: Random Library (No Compression)

**Hypothesis:** Theorems are independent, no pattern reuse. Each theorem used once by its definition alone.

**Model:**
```python
def random_library_mdl(T):
    """Extreme: no abstraction benefit, pure overhead"""
    cost = compute_theorem_cost(T)
    savings = 0  # no reuse
    return -cost  # always negative

baseline_1 = [random_library_mdl(T) for T in theorems]
```

**Physical interpretation:** Maximum entropy state. Like a gas where particles don't interact. Every theorem is isolated overhead.

**Expected position:** All real theorems should be ABOVE this (otherwise they're useless and shouldn't exist).

---

### Baseline 2: Trivial Abstraction (Single Use)

**Hypothesis:** Each theorem cited exactly once. Measures pure proof-length effect with minimal reuse.

**Model:**
```python
def single_use_mdl(T):
    """One citation per theorem - over-abstraction"""
    cost = compute_theorem_cost(T)
    pattern_length = estimate_pattern_length(T)
    
    # One use: saves (pattern_length - 1) tactics
    savings = (pattern_length - 1) * log2(2000) - log2(99412)
    
    return savings - cost  # usually negative for short proofs

baseline_2 = [single_use_mdl(T) for T in theorems]
```

**Physical interpretation:** Barely interactive system. Like molecules with weak van der Waals forces—some structure, minimal cooperation.

**Expected position:** Most real theorems should be ABOVE this (otherwise humans over-abstracted).

---

### Baseline 3: Frequency-Weighted (Citations Only)

**Hypothesis:** Value purely from citation count, ignoring proof structure. All patterns same complexity.

**Model:**
```python
def citation_only_mdl(T):
    """Assume all theorems have median pattern length"""
    median_pattern_length = 15  # from data
    median_cost = 500  # bits, from data
    
    num_uses = T.in_degree
    savings_per_use = median_pattern_length * log2(2000) - log2(99412)
    
    return num_uses * savings_per_use - median_cost

baseline_3 = [citation_only_mdl(T) for T in theorems]
```

**Physical interpretation:** Uniform interaction strength. Like an ideal crystal where all bonds equal. High-degree nodes win regardless of individual properties.

**Expected position:** Real system should SCATTER around this—some theorems punch above their citation weight (complex proofs), others below (trivial lemmas cited often).

---

### Extreme 4: Perfect Crystallization (Upper Bound)

**Hypothesis:** Every theorem captures the maximum compressible pattern extractable from its neighborhood.

**Model:**
```python
def perfect_crystallization_mdl(T):
    """Theoretical maximum: optimal pattern extraction"""
    
    # Assume theorem abstracts pattern appearing in ALL descendants
    num_uses = T.out_degree + T.in_degree  # reachable nodes
    
    # Assume pattern as long as median proof using it
    # (Can't be longer than shortest user)
    users = [p for p in mathlib if T in p.premises]
    if len(users) > 0:
        pattern_length = np.median([len(p.tactics) for p in users if p.proof_type == 'tactic'])
    else:
        pattern_length = estimate_pattern_length(T)
    
    cost = compute_theorem_cost(T)
    savings = num_uses * (pattern_length * log2(2000) - log2(99412))
    
    return savings - cost

baseline_4 = [perfect_crystallization_mdl(T) for T in theorems]
```

**Physical interpretation:** Ground state energy. Like superconductivity—zero-resistance information flow. Maximum compression achievable with current dependencies.

**Expected position:** Real system should be BELOW this (humans can't be perfectly optimal). Gap = room for algorithmic improvement.

---

## Part 3: Visualization Strategy

### Plot 1: Distribution Comparison (Log-Log Scatter)

```python
import matplotlib.pyplot as plt
import numpy as np

fig, ax = plt.subplots(figsize=(12, 8))

# Sort theorems by actual MDL gain
df_sorted = df.sort_values('mdl_gain')
x = np.arange(len(df_sorted))

# Plot actual data
ax.scatter(x, df_sorted['mdl_gain'], 
           c=df_sorted['in_degree'], cmap='viridis',
           alpha=0.6, s=20, label='Actual Mathlib')

# Plot baselines
ax.plot(x, sorted(baseline_1), 'r--', linewidth=2, 
        label='Baseline 1: Random (no compression)', alpha=0.8)
ax.plot(x, sorted(baseline_2), 'orange', linewidth=2,
        label='Baseline 2: Single-use', alpha=0.8)
ax.plot(x, sorted(baseline_3), 'b--', linewidth=2,
        label='Baseline 3: Citation-only', alpha=0.8)
ax.plot(x, sorted(baseline_4), 'g--', linewidth=2,
        label='Extreme: Perfect crystallization', alpha=0.8)

ax.axhline(y=0, color='black', linestyle=':', linewidth=1)
ax.set_xlabel('Theorem Rank (sorted by MDL gain)', fontsize=12)
ax.set_ylabel('ΔL_MDL (bits)', fontsize=12)
ax.set_yscale('symlog')  # symmetric log for negative values
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_title('MDL Gain Distribution: Actual vs Theoretical Bounds', fontsize=14)

plt.tight_layout()
plt.savefig('mdl_gain_distribution.png', dpi=300)
```

**What to look for:**
- How many theorems are NEGATIVE (overhead, shouldn't exist)?
- Where does bulk of distribution sit relative to citation-only baseline?
- How far is perfect crystallization extreme from reality? (Gap = optimization opportunity)

---

### Plot 2: Phase Diagram (2D Scatter)

```python
fig, ax = plt.subplots(figsize=(10, 8))

# Color by MDL gain
scatter = ax.scatter(df['in_degree'], df['pattern_length'],
                     c=df['mdl_gain'], cmap='RdYlGn',
                     s=50, alpha=0.7, norm=SymLogNorm(linthresh=100))

# Overlay baseline curves
# Citation-only baseline: fixed pattern_length
citation_only_pattern = 15
ax.axhline(y=citation_only_pattern, color='blue', linestyle='--', 
           linewidth=2, alpha=0.7, label='Citation-only assumption')

# Perfect crystallization: ΔL = 0 contour
# Solve: num_uses * savings_per_use - cost = 0
# For fixed cost, this gives hyperbolic curve
costs = [100, 500, 1000, 2000]
for cost in costs:
    # ΔL = 0 implies: num_uses * (pattern_length * 11 - 17) = cost
    in_degrees = np.logspace(0, 3, 100)
    pattern_lengths = cost / (in_degrees * 11 - 17 * in_degrees) + 17/11
    pattern_lengths = np.clip(pattern_lengths, 0, 100)
    ax.plot(in_degrees, pattern_lengths, 'gray', alpha=0.3, linestyle=':')

ax.set_xlabel('In-Degree (# times theorem cited)', fontsize=12)
ax.set_ylabel('Pattern Length (# tactics)', fontsize=12)
ax.set_xscale('log')
ax.set_yscale('log')
ax.set_xlim([1, 10000])
ax.set_ylim([1, 100])

cbar = plt.colorbar(scatter, ax=ax)
cbar.set_label('ΔL_MDL (bits)', fontsize=12)

ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)
ax.set_title('MDL Phase Space: Citations vs Pattern Complexity', fontsize=14)

plt.tight_layout()
plt.savefig('mdl_phase_diagram.png', dpi=300)
```

**What to look for:**
- High-value region: high in-degree + high pattern_length (upper right)
- Noise region: low in-degree + low pattern_length (lower left, near ΔL=0)
- Outliers: high pattern_length + low in-degree (missed opportunities?)

---

### Plot 3: Baseline Deviation Histogram

```python
fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# Compare actual vs each baseline
baselines = {
    'Random (no compression)': baseline_1,
    'Single-use': baseline_2,
    'Citation-only': baseline_3,
    'Perfect crystallization': baseline_4
}

for idx, (name, baseline) in enumerate(baselines.items()):
    ax = axes[idx // 2, idx % 2]
    
    # Deviation = actual - baseline
    deviation = df['mdl_gain'].values - np.array(baseline)
    
    ax.hist(deviation, bins=50, alpha=0.7, edgecolor='black')
    ax.axvline(x=0, color='red', linestyle='--', linewidth=2)
    ax.axvline(x=np.median(deviation), color='green', linestyle='--', 
               linewidth=2, label=f'Median: {np.median(deviation):.0f} bits')
    
    ax.set_xlabel(f'Actual - {name} (bits)', fontsize=11)
    ax.set_ylabel('Number of Theorems', fontsize=11)
    ax.set_title(f'Deviation from {name}', fontsize=12)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('mdl_baseline_deviations.png', dpi=300)
```

**What to look for:**
- Median deviation from citation-only: if large, proof structure matters
- Median deviation from perfect: optimization gap
- Shape of distributions: symmetric = unbiased, skewed = systematic over/under abstraction

---

## Part 4: Statistical Summary

```python
# Quantify system position relative to baselines

summary = {
    'Total theorems': len(df),
    'Negative MDL (overhead)': (df['mdl_gain'] < 0).sum(),
    'Positive MDL (compressive)': (df['mdl_gain'] > 0).sum(),
    'Zero-sum theorems': ((df['mdl_gain'] >= -50) & (df['mdl_gain'] <= 50)).sum(),
    
    'Median MDL gain': df['mdl_gain'].median(),
    'Mean MDL gain': df['mdl_gain'].mean(),
    'Total compression': df['mdl_gain'].sum(),
    
    'Above random baseline': (df['mdl_gain'] > np.array(baseline_1)).sum(),
    'Above single-use': (df['mdl_gain'] > np.array(baseline_2)).sum(),
    'Above citation-only': (df['mdl_gain'] > np.array(baseline_3)).sum(),
    'Below perfect': (df['mdl_gain'] < np.array(baseline_4)).sum(),
    
    'Optimization gap (vs perfect)': (np.array(baseline_4) - df['mdl_gain'].values).sum(),
    'Efficiency ratio': df['mdl_gain'].sum() / np.array(baseline_4).sum(),
}

print("=" * 50)
print("MDL GAIN ANALYSIS SUMMARY")
print("=" * 50)
for key, value in summary.items():
    if isinstance(value, float):
        print(f"{key:.<40} {value:>10.1f}")
    else:
        print(f"{key:.<40} {value:>10,}")
print("=" * 50)
```

---

## Part 5: Top/Bottom Theorems Analysis

```python
# Identify interesting outliers

# Top 20 most compressive
top_20 = df.nlargest(20, 'mdl_gain')[['theorem', 'mdl_gain', 'num_uses', 'pattern_length', 'in_degree']]
print("\nTOP 20 MOST COMPRESSIVE THEOREMS:")
print(top_20.to_string(index=False))

# Bottom 20 (most wasteful overhead)
bottom_20 = df.nsmallest(20, 'mdl_gain')[['theorem', 'mdl_gain', 'num_uses', 'pattern_length', 'in_degree']]
print("\nBOTTOM 20 (MOST WASTEFUL OVERHEAD):")
print(bottom_20.to_string(index=False))

# Largest deviation from citation-only baseline (under/over-performers)
df['deviation_from_citation'] = df['mdl_gain'] - np.array(baseline_3)
over_performers = df.nlargest(10, 'deviation_from_citation')[['theorem', 'mdl_gain', 'deviation_from_citation', 'pattern_length']]
under_performers = df.nsmallest(10, 'deviation_from_citation')[['theorem', 'mdl_gain', 'deviation_from_citation', 'in_degree']]

print("\nOVER-PERFORMERS (high MDL despite low citations):")
print("These have complex patterns that justify existence despite infrequent use")
print(over_performers.to_string(index=False))

print("\nUNDER-PERFORMERS (low MDL despite high citations):")
print("These are cited often but provide minimal compression (trivial lemmas)")
print(under_performers.to_string(index=False))
```

---

## Expected Insights

### Physics-Style Boundary Analysis

**If reality is close to Random baseline:**
- Mathematics has minimal compression structure
- Theorems are mostly independent facts
- **Conclusion:** Human abstraction provides little value
- **Unlikely** — would contradict entire foundation of mathematics

**If reality is close to Single-use baseline:**
- Over-abstraction problem
- Humans name things unnecessarily
- **Conclusion:** Mathlib should be refactored to inline many lemmas
- **Testable:** Do negative-MDL theorems correlate with low importance?

**If reality tracks Citation-only baseline:**
- Proof structure irrelevant, only frequency matters
- **Conclusion:** PageRank-style metrics sufficient, no need for MDL
- **Testable:** Residuals from citation-only should be random noise

**If reality significantly below Perfect crystallization:**
- Large optimization gap
- **Conclusion:** Algorithmic abstraction can improve on human organization
- **Testable:** Gap size predicts success rate of crystallized lemma mining

**Expected outcome:** Reality lies between Citation-only and Perfect, with systematic deviations revealing:
- High-pattern-length theorems over-perform (complex proofs worth abstracting even if rare)
- High-in-degree trivial lemmas under-perform (frequently used but minimal compression)
- Gap to Perfect ≈ 20-40% (room for crystallization to help)

---

## Deliverable

**Jupyter notebook:** `mdl_gain_analysis.ipynb`

Sections:
1. Data loading and MDL computation
2. Baseline model definitions
3. Visualization (3 plots)
4. Statistical summary table
5. Top/bottom theorems inspection
6. Physics-style interpretation: where does Mathlib sit in the phase space?

**Key figure for paper:** Combined plot showing actual distribution overlaid with all four baselines, annotated with interpretation arrows.

**Runtime estimate:** ~30 minutes on full Mathlib (pattern length estimation is expensive for term proofs, but can approximate).
