# Research Plan: Quantifying Discovery Dynamics in Formal Mathematics

**Version:** 1.0  
**Date:** 2026-02-07  
**Focus:** Beyond citation prediction toward computational models of mathematical discovery, intuition, and interestingness

---

## I. Research Vision

### Core Question
What structural and computational principles govern which mathematical results get discovered, which prove useful, and which are deemed "interesting"?

### Philosophical Frame
Mathematics as **compression-driven search** through proof space. Theorems that:
1. **Compress** existing knowledge (reduce description length)
2. **Bridge** disconnected domains (low common ancestors)  
3. **Innovate** proof strategies (rare tactic combinations)
4. **Expand** the adjacent possible (enable previously impossible proofs)

These properties define both *utility* and *interestingness* from information-theoretic first principles.

### Dual Research Tracks

**Track 1: Evaluative (Predicting theorem impact)**
- Given existing Mathlib, predict which theorems will be most valuable
- Targets: MDL gain, betweenness growth, innovation score
- Focus: Understanding what makes theorems scientifically important

**Track 2: Generative (Discovering new theorems)**
- Mine Mathlib for repeated proof patterns
- Synthesize **Crystallized Lemmas** = algorithmically-discovered abstractions
- Compare: Human mathematical ontology vs. information-theoretically optimal factorization
- Focus: Can we improve on human organization post-hoc?

**Key insight:** Discovery is messy, requires suboptimal checkpoints. But retrospective analysis reveals better abstractions. This tests whether human mathematical intuition is optimal or if computational analysis discovers missed generalizations.

---

## I-B. Key Terminology

**Minimum Description Length (MDL):** Information-theoretic measure of how much a theorem compresses the proof corpus. Lower total description length = better compression.

**Structural Compression:** Reduction in proof length measured in tactic count (uniform encoding). Pure measure of proof shortening independent of frequency.

**Statistical Compression:** Reduction in description length using frequency-weighted encoding (Shannon codes). Accounts for how common symbols are.

**Crystallized Lemma:** Algorithmically-discovered theorem extracted by detecting repeated proof patterns whose abstraction reduces total MDL. The term "crystallized" reflects structure emerging from solution—patterns solidify into named abstractions when compression threshold is met.

**Pattern Crystallization:** The process of mining proof corpora for repeated tactic subtrees and synthesizing them into new theorems.

**Adjacent Possible:** The set of theorems that become provable after theorem T is added. Measured via growth kernel eigenanalysis.

**r-horizon:** Information visibility constraint. r=0 means only past graph visible (predict from structure alone). r=1 means immediate children visible. r≥2 means grandchildren+ visible.

**Tactic AST:** Abstract syntax tree representation of proof structure. Enables pattern detection via subgraph isomorphism.

**Betweenness Growth:** How much a theorem's centrality increases as the graph evolves. High growth = becomes bridge between research areas.

**Innovation Score:** Measure of proof strategy novelty via n-gram perplexity or AST edit distance from historical proofs.

---

### What We Have
- Theorem dependency DAG from Mathlib
- Complete formal proofs (tactic sequences + premise usage)
- Feature pipeline predicting descendant count at various horizons (r=0, r=1, r=2)

### Current Results (r=0, depth=5)
- R² ≈ 0 for regression on raw descendant count
- PR-AUC ≈ 0.64 for binary classification (has_descendants)
- MAE_log ≈ 1.26

### Why These Results Make Sense
**Descendant count is the wrong target.** It conflates:
- Mathematical necessity (theorem fills structural gap)
- Social factors (research program popularity)
- Temporal dynamics (when was it added relative to active development)

At r=0 we cannot predict human research priorities. But we **can** predict:
- Structural importance (graph-theoretic centrality changes)
- Compression value (description length reduction)
- Innovation potential (proof strategy novelty)

---

## III. Reframed Prediction Targets

### A. Minimum Description Length (MDL) Gain

**Definition:** How much does theorem T compress the proof corpus?

**Computation Pipeline:**

#### Step 1: Extract Proof Corpus
```
For each theorem T_i in Mathlib:
    proofs[T_i] = {
        'tactics': [tac_1, tac_2, ..., tac_n],
        'premises': [lemma_1, lemma_2, ..., lemma_k],
        'tactic_tree': AST of proof structure
    }
```

#### Step 2: Define Encoding Scheme — CRITICAL ANALYSIS

**Three Distinct Notions of Compression (and what they mean for science):**

**A. Uniform Encoding (Naive Baseline)**
```
DL_raw(proof) = Σᵢ [log₂(|V_tactic|) + nᵢ · log₂(|L_available|)]
```
- Each tactic costs log₂(vocab_size) bits
- Each lemma reference costs log₂(library_size) bits
- **Problem**: Doesn't capture that common lemmas are "cheaper" in practice
- **Scientific value**: Minimal. Just counting symbols.

**B. Shannon Encoding (Frequency-Based Compression)**
```
DL_Shannon(proof) = Σ_tactics [-log₂(p_tactic)] + Σ_lemmas [-log₂(p_lemma)]
```
where p = empirical frequency in the corpus.

- Common lemmas get shorter codes (e.g., 3 bits instead of 15)
- Achieves optimal compression given frequency statistics
- **Question**: Does this capture scientific understanding?

**Thought experiment:**
- Suppose lemma L is used 10,000 times (very high frequency)
- Shannon encoding gives it a short code (say, 4 bits)
- But what if L is just a trivial lookup (e.g., "0 < 1")?
  - High frequency ≠ deep insight
  - We've achieved data compression but not conceptual compression

**Occam's Razor Consideration:**  
Solomonoff induction says: shortest *program* is best predictor. But there's ambiguity:
- **Program 1**: Hardcode 10,000 uses of trivial lemma → short via frequency encoding
- **Program 2**: Derive everything from first principles → conceptually minimal but longer encoding

**Which is "simpler"?** Depends on notion of simplicity.

**C. Pattern Abstraction (Structural Compression)**
```
DL_pattern(corpus_with_T) = DL(corpus_without_T) - savings_from_abstraction(T)

where savings = Σ_{proofs} [
    if proof_contains_pattern_isomorphic_to(T):
        original_proof_length - (reference_to_T + len(proof_of_T))
]
```

- Detects when theorem T encapsulates a **repeated proof strategy**
- Not just frequency, but *structural reuse*
- Multiple proofs share isomorphic tactic subtrees → replaced by single reference to T

**Example:**
- 50 theorems each prove "X is continuous" using same 20-tactic sequence
- New theorem T: "composition preserves continuity"
- After T: those 50 proofs now use T as one-line premise
- Compression = 50 × 20 - 50 × 1 - len(proof_T) ≈ 950 tactics saved

**THIS is conceptual compression** — recognizing abstract pattern.

**Scientific value**: HIGH. This captures:
- Generalization (T abstracts specific instances)
- Explanatory power (one proof of T explains 50 cases)
- Mathematical elegance (replace repetition with principle)

**D. Conceptual Unification (Axiomatic Compression)**

Even deeper: theorem T might unify *superficially different* proofs under one framework.

**Example:**
- Before: Prove associativity separately for (ℕ,+), (ℤ,+), (ℚ,+), (ℝ,+)
- After: Prove once for abstract groups
- Compression isn't just tactic reuse — it's *recognizing shared structure*

**Metrics:**
- Reduction in axioms/assumptions needed
- Number of special cases subsumed
- Decrease in conceptual vocabulary

**This is the deepest form** — aligned with how mathematicians think about "understanding."

---

**What Should We Measure?**

**For scientific discovery research, prioritize Pattern Abstraction (C):**

1. **Kolmogorov insight**: If T's proof is short but appears in many downstream proofs as substructure, T has high compression value
   
2. **Not captured by frequency alone**: A lemma used 1000 times trivially vs. a theorem whose *proof strategy* gets reused 50 times non-trivially → latter is more scientifically interesting

3. **Testable**: Subgraph isomorphism on tactic ASTs is computable (unlike true Kolmogorov complexity)

**Revised Encoding Scheme (Pattern-Aware MDL):**

```python
def MDL_pattern_aware(corpus, T):
    """
    Measure compression via structural pattern reuse, not just frequency.
    """
    # Part 1: Identify tactic subtree pattern from proof(T)
    pattern_T = extract_tactic_subtree(proof(T), max_depth=k)
    
    # Part 2: Find isomorphic occurrences in corpus
    matches = {}
    for theorem_X in corpus:
        isomorphic_subproofs = find_subgraph_isomorphisms(
            proof(theorem_X).tactic_ast, 
            pattern_T
        )
        if isomorphic_subproofs:
            matches[theorem_X] = isomorphic_subproofs
    
    # Part 3: Compute savings
    # Before T exists: each match requires full pattern encoding
    DL_before = sum(
        len(pattern_T) * len(match_list)  # pattern_length × occurrences
        for match_list in matches.values()
    )
    
    # After T exists: replace with reference + T's proof once
    DL_after = (
        len(matches) * log2(library_size)  # references to T
        + len(proof(T))  # cost of T itself
    )
    
    compression_gain = DL_before - DL_after
    return compression_gain
```

**Key difference from Shannon:**
- Shannon: "lemma_1" used 1000 times → assign short code
- Pattern: "proof strategy P" appears 50 times → abstract to theorem

**Hybrid Approach (Recommended):**

```
DL_total = DL_shannon_base + penalty_for_pattern_redundancy

penalty = Σ_{patterns} [
    if pattern appears k times without abstraction:
        (k - 1) · pattern_length  # cost of not abstracting
]
```

This penalizes *repeated structure*, incentivizing creation of theorems that factor common proof strategies.

---

**Philosophical Resolution:**

**Q: Does compression = understanding?**

**A: Depends on what you compress:**

| Compression Type | Mechanism | Scientific Understanding |
|------------------|-----------|-------------------------|
| Frequency coding | Common → short code | No (just storage optimization) |
| Pattern abstraction | Repeated structure → theorem | Yes (generalization) |
| Conceptual unification | Special cases → abstract principle | YES (mathematical insight) |

**For this research:**
- **Primary metric**: Pattern abstraction (tactic AST isomorphism)
- **Secondary**: Conceptual unification (module bridging, parent LCA depth)
- **Baseline only**: Shannon frequency (for comparison)

**Occam's Razor properly interpreted:**  
"Entities should not be multiplied without necessity" → prefer theorems that *eliminate redundancy*, not just encode frequently. Theorem T with high MDL_pattern has *necessity* — it removes repetition.

---

**Concrete Implementation Decision:**

Use **two-part MDL** but with pattern-aware encoding:

```
L(M,D) = L(model) + L(data|model)

L(model) = cost_of_theorem_vocabulary + cost_of_tactic_vocabulary

L(data|model) = Σ_{proofs} encode_via_pattern_factorization(proof)
```

where `encode_via_pattern_factorization` detects repeated subtrees and represents them as references to abstracting theorems.

**This aligns compression with mathematical practice**: mathematicians prove lemmas precisely to avoid repeating proof strategies.

#### Step 2.5: Philosophical Interlude — What Are We Actually Measuring?

**The encoding choice matters deeply.** Two fundamentally different approaches:

**Approach A: Uniform Encoding (Fixed-Length Codes)**
```
DL_uniform(proof) = Σᵢ [log₂(|V_tactic|) + nᵢ · log₂(|L_available|)]
```
- Every tactic: log₂(|V_tactic|) bits
- Every lemma reference: log₂(|L_available|) bits  
- All symbols treated equally
- Adding theorem T increases |L_available| → all future lemma refs cost +ε bits
- BUT: if T is used k times, you save k·len(proof_T) - k·log₂(|L_available|+1)

**Approach B: Frequency-Based Encoding (Variable-Length Codes)**
```
DL_freq(proof) = Σᵢ [-log₂(p_tactic) + Σⱼ -log₂(p_lemma)]
```
- Frequent tactics/lemmas: short codes (~1-2 bits)
- Rare tactics/lemmas: long codes (~15-20 bits)
- Optimal prefix coding (Huffman/arithmetic)
- Adding T initially: long code (rare)
- If T becomes frequent: code shrinks automatically

**Case Study: Two Theorems, Same Reuse Pattern**

Theorem T₁: Used 5 times in group theory (niche area)
Theorem T₂: Used 5 times in linear algebra (popular area)

*Under uniform encoding:* Both save identical bits = 5·len(proof) - 5·log₂(n)

*Under frequency encoding:* 
- T₂ gets shorter code (linear algebra symbols already have high frequency)
- T₂'s references also cost less (it appears in "common" proof contexts)
- T₂ shows higher compression even with same reuse count

**Which captures scientific understanding?**

**Argument FOR uniform encoding (Structural Compression):**
- **Occam's razor cares about logical structure, not popularity**
- A theorem simplifying one proof by 100 steps is valuable even if used once
- Measures: actual proof shortening, subproof factorization
- Independent of social dynamics (which areas are trendy)
- Example: Fundamental lemma in obscure area vs. minor result in popular area
- **This is "compression of proof structure"** — what mathematicians mean by "elegance"

**Argument FOR frequency encoding (Statistical Compression):**
- **Science seeks regularities, and regularity = repetition**
- Frequent use indicates T captures a fundamental pattern
- Zipf's law: power-law distributions are natural in generative processes
- MDL principle (Rissanen): model should compress regularities, not just list cases
- If T is used 1000x, it's discovering something deep about mathematical structure
- **This is "compression via discovered patterns"** — what we mean by "fundamental"

**The Confound: Social vs. Mathematical Fundamentality**

Frequency mixes:
- Mathematical necessity (T solves a recurring problem)
- Research fashion (T's area is popular this decade)
- Historical accident (T was proven early, became standard)

**Example tensions:**

*Case 1: High reuse, low frequency*
- Theorem proves general result about obscure algebraic structure
- Used 20 times in proofs about that structure
- But structure itself rarely studied → low global frequency
- **Uniform encoding:** High value (lots of reuse)
- **Frequency encoding:** Low value (rare context)
- **Interpretation:** Locally fundamental, globally niche

*Case 2: Low reuse, high frequency*
- Theorem is trivial corollary of famous result
- Proven explicitly because it's "standard to state"
- Referenced often in intros but never does heavy lifting
- **Uniform encoding:** Low value (minimal proof shortening)
- **Frequency encoding:** High value (common symbol)
- **Interpretation:** Socially salient, mathematically shallow

*Case 3: High reuse, high frequency*
- Theorem like "fundamental theorem of calculus"
- Used constantly, compresses many proofs
- Both measures agree: high value
- **Interpretation:** Genuinely fundamental

**Resolution: Measure Both, Distinguish Them**

Define two separate targets:

**1. Structural Compression (uniform codes):**
```python
Δ_structural(T) = Σ_{proofs using T} [
    tactic_count_without_T - tactic_count_with_T
] - len(proof_T)
```
- Pure measure of proof simplification
- How many proof steps eliminated?
- Counts AST nodes, not bits weighted by frequency
- **This is closest to "mathematical insight"** — theorem T reveals a shortcut

**2. Statistical Compression (frequency codes):**
```python
Δ_statistical(T) = Σ_{proofs using T} [
    -log₂(p_symbols_without_T) - (-log₂(p_symbols_with_T))
] - (-log₂(p_T))
```
- Includes frequency weighting
- Captures both reuse AND fundamentality
- Frequent theorems in frequent contexts compress more
- **This measures "pattern discovery"** — theorem T identifies regularity

**3. Hybrid: Separate Concerns**
```python
compression_value(T) = α · Δ_structural(T) + β · Δ_statistical(T)
```

Where we empirically determine which predicts:
- **α dominant:** Predicting "landmark theorems" (expert labels)
- **β dominant:** Predicting citation count (social impact)
- **Both:** Predicting which theorems appear in textbooks

**For our research:**

We start with **structural compression** because:
1. It's what Occam's razor actually prescribes
2. Less confounded by social factors
3. Directly interpretable: "T shortens k proofs by avg n steps"
4. Matches intuition of "mathematical elegance"

But we ALSO compute **statistical compression** to:
1. Compare with citation-based metrics
2. Understand divergence between logical and social value
3. Test if "fundamentality" emerges from frequency patterns

**Key experiments:**
- Do high-structural, low-frequency theorems exist? (hidden gems)
- Do low-structural, high-frequency theorems exist? (overrated)
- Is there correlation? (validates frequency as proxy for quality)
- Can we predict which will become high-frequency from r=0 features?

**Practical Implementation:**

Compute both for each theorem:
```python
metrics[T] = {
    'structural_compression': count_tactic_savings(T),
    'statistical_compression': compute_shannon_savings(T),
    'reuse_count': len(descendants_using_T),
    'avg_proof_shortening': mean_tactic_reduction(T),
    'frequency_percentile': rank_by_usage_frequency(T),
}
```

Then predict both as separate targets, analyze:
- Which features predict each?
- Do they share latent factors?
- Where do they diverge most?

**Hypothesis:**
- Structural compression learnable from proof AST similarity (r=0)
- Statistical compression requires "what will become popular" (harder at r=0)
- Their ratio reveals "hidden fundamental" vs "overhyped" theorems

---

#### Step 2.6: Concrete Mathlib Case Studies

**To ground the abstract discussion, consider these actual theorem patterns:**

**Example 1: High Structural Compression (Pattern Abstraction)**
```lean
-- Theorem that factors repeated epsilon-delta arguments
theorem continuous.comp {f : α → β} {g : β → γ} 
  (hf : Continuous f) (hg : Continuous g) : 
  Continuous (g ∘ f)
```

**Analysis:**
- Proof length: ~30 tactics (epsilon-delta manipulation)
- Direct uses: ~50 explicit references
- Pattern reuse: ~200 theorems prove continuity of composed functions
  - Before: Each used full epsilon-delta argument (30 tactics)
  - After: Reference `continuous.comp` (1 tactic)
  
**Compression calculation:**
```
Structural: 200 × 30 - 200 × 1 - 30 = 5770 tactics saved
Statistical: Depends on whether continuity is "hot topic"
  - If continuity proofs are 10% of corpus → high frequency weight
  - If continuity proofs are 0.1% of corpus → low frequency weight
```

**Scientific value:** HIGH (independent of frequency)
- Abstracts fundamental proof pattern
- Generalizes from specific compositions
- Reduces cognitive load (don't re-derive epsilon-delta each time)

---

**Example 2: High Frequency, Low Structural Compression (Lookup Lemma)**
```lean
theorem zero_lt_one : (0 : ℕ) < 1 := by trivial
```

**Analysis:**
- Proof length: 1 tactic
- Direct uses: ~10,000 references (extremely common precondition)
- Pattern reuse: 0 (proof is atomic, no structure to abstract)

**Compression calculation:**
```
Structural: 10000 × 1 - 10000 × 1 - 1 = -1 (NEGATIVE!)
  - Replacing inline "trivial" with lemma reference costs more
  
Statistical: 10000 × [-log₂(p_trivial) - (-log₂(p_zero_lt_one))]
  - If "trivial" is common but "zero_lt_one" becomes even more common
  - Frequency encoding assigns short code → positive compression
```

**Scientific value:** LOW
- No proof strategy to abstract
- Just a named constant fact
- Exists for convenience, not insight

**Insight:** Statistical compression can be positive even when structural is negative, purely from frequency effects.

---

**Example 3: Conceptual Unification (Cross-Domain Bridge)**
```lean
-- Abstract group associativity
theorem Group.assoc {G : Type*} [Group G] (a b c : G) :
  (a * b) * c = a * (b * c)
```

**Analysis:**
- Unifies separate proofs for:
  - Natural number addition (25 tactics)
  - Integer addition (30 tactics)
  - Matrix multiplication (40 tactics)
  - Function composition (35 tactics)
  
**Before theorem exists:**
- Each domain: separate proof
- Total: 130 tactics across 4 domains
- NO connection recognized

**After theorem exists:**
- All reference abstract `Group.assoc`
- Total: 4 references + 1 abstract proof
- Connection EXPLICIT: "these are the same"

**Compression calculation:**
```
Structural: 130 - 5 - len(abstract_proof) ≈ 100 tactics
Statistical: High if group theory is central, low if peripheral

PLUS conceptual gain:
- Reduced axioms: only prove once for abstract structure
- Increased understanding: recognized isomorphism
- Enabled transfer: properties proven for groups auto-apply
```

**Scientific value:** HIGHEST
- This is what mathematicians call "real mathematics"
- Not just saving steps, but revealing hidden unity
- Enables analogical reasoning across domains

---

**Example 4: Overfitting (Noise Theorem)**
```lean
-- Suspiciously specific lemma
theorem nat_42_squared : (42 : ℕ)^2 = 1764 := by norm_num
```

**Analysis:**
- Proof length: 1 tactic (computation)
- Uses: 1 (the proof that needed this specific fact)
- Pattern reuse: 0
- Generality: 0

**Compression calculation:**
```
Structural: 1 × 1 - 1 × 1 - 1 = -1 (costs more than it saves)
Statistical: Near zero (unique number, never reused)
```

**Scientific value:** ZERO (arguably negative)
- Should be inline computation, not named theorem
- Clutters namespace
- No abstraction or insight

**Detection at r=0:**
- `proof_length` = 1 (trivial)
- `parent_count` = 0 (uses only primitives)
- `proof_tactic_novelty` = 0 (norm_num is common)
- Predict: `descendant_count` = 0

---

**Summary Table: Four Archetypes**

| Theorem Type | Structural Δ | Statistical Δ | Scientific Value | r=0 Signals |
|--------------|-------------|--------------|-----------------|-------------|
| **Pattern Abstraction** (Ex 1) | High (+5770) | Variable | High | Parent proof similarity, tactic tree depth |
| **Lookup Lemma** (Ex 2) | Low/Negative (-1) | High (freq) | Low | Proof length=1, no AST structure |
| **Conceptual Unifier** (Ex 3) | High (+100) | Variable | Highest | Parent module diversity, LCA depth low |
| **Noise** (Ex 4) | Negative (-1) | Near zero | Zero | Trivial proof, zero descendants |

---

**Implications for Feature Engineering:**

From these cases, **r=0 features that matter**:

**Positive signals for high structural compression:**
1. `parent_proof_ast_similarity` > 0.7 (parents use similar strategies)
2. `proof_tactic_tree_depth` > 3 (rich proof structure)
3. `avg_parent_proof_length` > 20 (substantial proofs to potentially replace)

**Positive signals for conceptual unification:**
1. `parent_module_entropy` > 1.5 (parents from diverse domains)
2. `parent_lca_depth_ratio` < 0.5 (merging distant lineages)
3. `proof_uses_type_variables` = True (abstracts over structures)

**Negative signals (filter out noise):**
1. `proof_length` < 3 AND `uses_only_primitives` = True
2. `parent_count` = 0 (axiomatic triviality)
3. `tactic_novelty` = 0 AND `proof_length` = 1

**Features that DON'T predict structural compression:**
- Raw `indegree` (confounds Examples 1 and 2)
- `depth` alone (not about when proven, but what it abstracts)
- Current popularity of parent modules (that's statistical, not structural)

---

#### Step 3: Compute ΔL When Adding Theorem T

**Before T exists:**
```python
def encode_proof_without_T(proof_of_theorem_X, available_lemmas):
    """
    Encode proof using only available_lemmas (excluding T).
    Return bit-length under optimal encoding.
    """
    tactic_sequence = proof_of_theorem_X.tactics
    premise_sequence = proof_of_theorem_X.premises
    
    # Shannon encoding: -log₂(p) bits per symbol
    bits_tactics = sum(-log2(freq[tac]/total_tac) for tac in tactic_sequence)
    bits_premises = sum(-log2(freq[lem]/total_lem) for lem in premise_sequence)
    
    return bits_tactics + bits_premises
```

**After T exists:**
```python
def encode_proof_with_T(proof_of_theorem_X, available_lemmas_plus_T):
    """
    Re-prove theorem X, now allowed to use T as a lemma.
    This requires either:
    (a) Human-expert refactored proofs, OR
    (b) ATP re-synthesis using T in premise pool, OR  
    (c) Proof compression algorithm (find T-substitutable subproofs)
    """
    # Option C (algorithmic, no human labels):
    compressed_proof = substitute_subproofs_with_T(
        original_proof=proof_of_theorem_X,
        new_lemma=T,
        proof_of_T=proofs[T]
    )
    return encode_proof(compressed_proof)
```

**MDL gain:**
```
Δ_MDL(T) = Σ_{X in corpus} [
    L_before(proof_X) - L_after(proof_X, using_T)
] - L(proof_T)  # cost of adding T itself
```

Positive Δ_MDL means T compresses the library.

#### Step 4: Practical Approximation (No Re-Proving)

**Two distinct computations based on encoding choice:**

**4A. Structural Compression Approximation**

Graph-based proxy measuring pure proof shortening:

```python
def approximate_structural_compression(T, dag, proofs):
    """
    Compute proof simplification via tactic subtree isomorphism.
    Uses UNIFORM encoding - counts steps saved, not frequency-weighted bits.
    """
    proof_T_pattern = extract_tactic_subtree(proofs[T])
    
    total_tactic_savings = 0
    proofs_compressed = 0
    
    for X in descendants_reachable_from_parents_of_T:
        proof_X = proofs[X]
        
        # Find isomorphic subgraphs in proof_X matching proof_T structure
        matches = subgraph_isomorphism(proof_X.tactic_tree, proof_T_pattern)
        
        if matches:
            # Each match = potential to replace subtree with lemma reference
            for match in matches:
                steps_in_subtree = len(match.nodes)  # AST nodes in matched pattern
                steps_if_using_T = 1  # Just reference T as lemma
                total_tactic_savings += (steps_in_subtree - steps_if_using_T)
            
            proofs_compressed += 1
    
    # Cost: T's own proof length
    cost_of_T = len(proofs[T].tactics)
    
    structural_gain = total_tactic_savings - cost_of_T
    
    return {
        'structural_compression': structural_gain,
        'proofs_compressed': proofs_compressed,
        'avg_shortening': total_tactic_savings / max(proofs_compressed, 1),
        'reuse_count': len(matches),
    }
```

**4B. Statistical Compression Approximation**

Frequency-weighted encoding:

```python
def approximate_statistical_compression(T, dag, proofs):
    """
    Compute frequency-weighted compression.
    Uses Shannon encoding - frequent symbols cost fewer bits.
    """
    # Build frequency models before/after T
    tactic_freq_before, lemma_freq_before = build_freq_model(proofs, exclude=T)
    tactic_freq_after, lemma_freq_after = build_freq_model(proofs, include=T)
    
    total_bit_savings = 0
    
    for X in descendants_using_T:
        proof_X_original = proofs[X]  # without using T
        proof_X_compressed = compress_with_T(proof_X_original, T)
        
        # Encoding cost before T available
        bits_before = sum(-log2(tactic_freq_before[tac]) for tac in proof_X_original.tactics)
        bits_before += sum(-log2(lemma_freq_before[lem]) for lem in proof_X_original.premises)
        
        # Encoding cost after T available  
        bits_after = sum(-log2(tactic_freq_after[tac]) for tac in proof_X_compressed.tactics)
        bits_after += sum(-log2(lemma_freq_after[lem]) for lem in proof_X_compressed.premises)
        bits_after += -log2(lemma_freq_after[T])  # cost to reference T
        
        total_bit_savings += (bits_before - bits_after)
    
    # Cost: encoding T's proof under new frequency model
    cost_bits = sum(-log2(tactic_freq_after[tac]) for tac in proofs[T].tactics)
    cost_bits += sum(-log2(lemma_freq_after[lem]) for lem in proofs[T].premises)
    
    statistical_gain = total_bit_savings - cost_bits
    
    return {
        'statistical_compression': statistical_gain,
        'bit_savings': total_bit_savings,
        'frequency_percentile': rank_by_frequency(T, lemma_freq_after),
    }
```

**Comparison on Example:**

Consider theorem T used 5 times, each saves 20 tactic steps:

*Structural:*
- Savings: 5 proofs × 20 steps = 100 steps
- Cost: 15 steps (T's own proof)
- **Net: 85 steps saved**

*Statistical (assume T becomes moderately common):*
- Before: 5 proofs × 20 tactics × log₂(500) ≈ 900 bits (avg tactic has ~500 options)
- After: 5 proofs × 1 reference × log₂(5000) ≈ 65 bits (vocab now 5000 lemmas)
- Also: T shortens each proof, so remaining tactics use updated frequencies
- **Net: ~600 bits saved** (more than structural because frequency weighting)

**When they diverge:**

*Example 1: Niche but powerful*
- T used in specialized module (low global frequency)
- But drastically shortens those proofs (high structural value)
- Structural >> Statistical

*Example 2: Trivial but common*  
- T is obvious corollary of famous theorem
- Referenced often as "standard step" (high frequency)
- But minimal proof shortening (trivial result)
- Statistical >> Structural

**Implementation Decision:**

Start with **structural compression** as primary target because:
1. More robust (frequency-agnostic)
2. Easier to validate (count AST nodes)
3. Matches mathematical intuition ("theorem simplifies proofs")

Compute **statistical compression** as secondary target to:
1. Compare with citation patterns
2. Test if fundamentality = frequency
3. Identify divergent cases for case studies

#### Step 5: Features Predicting Compression (for r=0)

**Two sets of features, targeting different compression types:**

**5A. Features Predicting Structural Compression**

These predict *proof simplification* (step reduction):

```python
structural_features = {
    # Pattern reuse potential
    'parent_proof_pattern_diversity': entropy(tactic_ngrams_in_parents),
    'upstream_pattern_reuse': count_isomorphic_subtrees_in_ancestors,
    'proof_abstraction_level': ratio_lemmas_to_primitives_in_parents,
    
    # Proof structure similarity  
    'parent_ast_homogeneity': 1 - variance(tree_edit_distances(parent_proofs)),
    'common_subproof_size': max_shared_subtree_size(parent_proofs),
    
    # Generalization potential
    'parent_lca_depth': depth(lowest_common_ancestor(parents)),
    'parent_lca_ratio': lca_depth / mean(parent_depths),  # low = merging distant branches
    
    # Local reuse indicators
    'sibling_reuse_rate': fraction_siblings_reusing_similar_patterns,
    'parent_outdegree_product': product(outdegree(p) for p in parents),  # fertile lineage
}
```

**Intuition:** Structural compression high when:
- Parents have similar proof patterns (homogeneous ASTs)
- Low LCA = merging distant techniques (new combination likely reused)
- High pattern diversity upstream = T unifies disparate approaches

**5B. Features Predicting Statistical Compression**

These predict *frequency-weighted value* (fundamentality):

```python
statistical_features = {
    # Vocabulary frequency context
    'parent_avg_frequency': mean(global_lemma_frequency[p] for p in parents),
    'parent_frequency_variance': variance(global_lemma_frequency[p] for p in parents),
    'tactic_rarity_in_proof': mean(-log(tactic_frequencies[t]) for t in tactics),
    
    # Module popularity
    'module_growth_rate': recent_theorem_addition_rate_in_module,
    'module_citation_density': mean_citations_per_theorem_in_module,
    
    # "Standard" combinations
    'parent_cooccurrence_frequency': how_often_parents_appear_together_historically,
    'canonical_position': centrality_in_module_subgraph,
    
    # PageRank-style importance propagation
    'parent_pagerank_product': product(pagerank(p) for p in parents),
    'weighted_ancestor_importance': sum(pagerank(a) / distance(a) for a in ancestors),
}
```

**Intuition:** Statistical compression high when:
- Parents are already high-frequency (T joins "core" vocabulary)
- Module is active/growing (more proofs will use T)
- Parents often co-occur (T formalizes common pattern)

**5C. Shared Features (Predict Both)**

Some features correlate with both types:

```python
shared_features = {
    'indegree': len(parents),  # more parents = more to unify
    'depth': distance_from_axioms,
    'parent_outdegree_max': max(outdegree(p) for p in parents),  # leveraging productive theorems
    'upstream_diversity': entropy(modules_in_ancestors),
}
```

**Experimental Design:**

Train three models:
1. **Model_structural**: Predict structural_compression using 5A + 5C features
2. **Model_statistical**: Predict statistical_compression using 5B + 5C features  
3. **Model_joint**: Multi-task, predict both with shared encoder

**Analysis:**
- Which features matter for each target?
- Is there latent "impact" factor, or orthogonal dimensions?
- Can we predict statistical from structural + social features?

**Key insight:** Structural ≈ mathematical necessity. Statistical ≈ mathematical + social.

If high correlation: frequency is good proxy for quality.
If low correlation: identify "hidden gems" (high structural, low statistical).

---

**Section III.A Summary: Which Encoding for Scientific Discovery?**

**The Question:** Does Occam's razor care about frequency, or just logical structure?

**The Answer:** Both matter, but for different reasons.

**Structural compression** (uniform encoding):
- Measures: proof simplification, logical elegance
- Independent of: social trends, research fashion
- Corresponds to: what mathematicians mean by "insight"
- Use for: identifying fundamental abstractions

**Statistical compression** (frequency encoding):  
- Measures: pattern regularities, usage fundamentality
- Influenced by: social dynamics, field popularity
- Corresponds to: what becomes "standard knowledge"
- Use for: predicting impact, citation

**Key Distinction:**
- Theorem proving 1000 trivial results: high frequency, low structural value
- Theorem unifying two approaches once: low frequency, high structural value

**Our Approach:**
1. **Primary target:** Structural compression (pure Occam)
2. **Secondary target:** Statistical compression (impact proxy)
3. **Analyze divergence:** Where do they disagree? Why?

**Expected Insight:**
If correlation is high (ρ > 0.7): frequency tracks quality → frequency is valid heuristic.
If correlation is low (ρ < 0.4): frequency is social artifact → need structural measures.

This distinction clarifies what we mean by "understanding" vs "popularity" in science.

---

### B. Tactic Innovation Score

**Definition:** Does theorem T introduce novel proof strategies?

**Computation:**

#### Method 1: N-Gram Surprise
```python
def tactic_innovation_score(T, historical_proofs):
    """
    Measure proof strategy novelty via n-gram surprise.
    """
    proof_T_tactics = proofs[T].tactics
    
    # Build n-gram language model from all proofs before T
    ngram_model = build_ngram_model(
        [p.tactics for p in historical_proofs],
        n=4  # 4-grams capture local proof patterns
    )
    
    # Compute perplexity of proof_T under historical model
    perplexity = ngram_model.perplexity(proof_T_tactics)
    
    # High perplexity = surprising tactic sequences
    return log(perplexity)
```

#### Method 2: Tactic AST Edit Distance
```python
def proof_strategy_distance(proof_A, proof_B):
    """
    Tree edit distance between tactic dependency trees.
    Measures structural dissimilarity of proof strategies.
    """
    ast_A = proof_A.tactic_tree
    ast_B = proof_B.tactic_tree
    
    return tree_edit_distance(ast_A, ast_B, 
                              cost_insert=1, 
                              cost_delete=1, 
                              cost_relabel=0.5)
```

Aggregate over k-nearest parents:
```python
innovation = mean([
    proof_strategy_distance(proofs[T], proofs[parent])
    for parent in parents_of_T
])
```

High distance = T uses different proof approach than typical for its parent theorems.

#### Method 3: Rare Tactic Combination Mining
```python
def rare_combination_score(T, dag):
    """
    Identify if T combines tactics rarely seen together.
    """
    tactic_pairs = set(zip(proofs[T].tactics[:-1], 
                          proofs[T].tactics[1:]))
    
    # Global co-occurrence statistics
    global_pair_freq = compute_pair_frequencies(all_historical_proofs)
    
    rarity_score = sum(
        -log(global_pair_freq.get(pair, 1e-6))  # surprise per pair
        for pair in tactic_pairs
    )
    
    return rarity_score / len(tactic_pairs)  # normalize by proof length
```

**Features for r=0:**
- `parent_tactic_ngram_entropy`: diversity of tactic sequences in parents
- `parent_proof_ast_diameter`: max tree-edit-distance among parent proofs
- `tactic_pair_rarity_max`: maximum rarity of tactic bigrams in vicinity

---

### C. Graph-Theoretic Impact Measures

Move beyond raw citation count to **structural importance**.

#### Betweenness Centrality Growth
```python
def betweenness_growth_potential(T, dag, horizon=10):
    """
    Predict how much T will increase its betweenness centrality
    as the graph grows in next 'horizon' additions.
    """
    # Compute betweenness on subgraph at depth d (T's introduction)
    G_current = subgraph_at_depth(dag, d)
    betweenness_t0 = nx.betweenness_centrality(G_current)[T]
    
    # True value: betweenness at depth d+horizon (this is Y target)
    G_future = subgraph_at_depth(dag, d + horizon)
    betweenness_t1 = nx.betweenness_centrality(G_future)[T]
    
    return betweenness_t1 - betweenness_t0
```

**r=0 Proxy Features:**
- `parent_betweenness_variance`: if parents span different graph regions, T bridges them
- `upstream_wcc_count`: number of weakly connected components in T's ancestor graph
- `lca_depth_ratio`: depth(LCA) / mean(depth(parents)) — low = merging distant lineages

#### PageRank Momentum
```python
def pagerank_acceleration(T, dag):
    """
    Rate of PageRank growth as graph evolves.
    """
    pagerank_scores = []
    for depth in range(T.depth, T.depth + 10):
        G_t = subgraph_at_depth(dag, depth)
        pagerank_scores.append(nx.pagerank(G_t)[T])
    
    # Fit linear trend
    slope, intercept = np.polyfit(range(10), pagerank_scores, 1)
    return slope  # positive slope = accelerating importance
```

#### Module Bridging Index
```python
def module_bridging_score(T, dag, module_labels):
    """
    Quantify if T connects previously disconnected research modules.
    """
    parent_modules = set(module_labels[p] for p in parents(T))
    
    # Compute modularity before/after T is added
    Q_before = modularity(dag_without_T, module_labels)
    Q_after = modularity(dag_with_T, module_labels)
    
    # Decreased modularity = T breaks module boundaries (bridge)
    bridging = Q_before - Q_after
    
    # Normalize by parent module diversity
    return bridging / len(parent_modules)
```

**r=0 Features:**
- `parent_module_count`: |{modules of parents}|
- `parent_pagerank_product`: Π(PageRank(p)) — high = leveraging important theorems
- `upstream_clustering_coefficient`: local graph structure richness

---

### D. Interestingness Operationalization

**Unified Formula (Updated for Compression Distinction):**
```
Interestingness(T) = (Novelty × Utility) / Complexity
```

**Components:**

1. **Novelty (N):**
   ```
   N(T) = KL_divergence(tactic_dist_T || tactic_dist_parents)
          + proof_strategy_distance(T, nearest_k_similar)
   ```
   Captures: surprisal of proof method

2. **Utility (U) — Now with compression disambiguation:**
   ```
   U(T) = α · structural_compression(T)     # logical elegance
          + β · statistical_compression(T)   # pattern fundamentality  
          + γ · betweenness_growth(T)        # graph bridging
   ```
   
   Where:
   - `structural_compression`: pure proof shortening (steps saved)
   - `statistical_compression`: frequency-weighted compression (bits saved)
   - `betweenness_growth`: increase in graph-theoretic centrality
   
   **Interpretation of weights (α, β, γ):**
   - **α-dominated (α >> β)**: "Mathematician's interestingness" — elegant proofs
   - **β-dominated (β >> α)**: "Sociologist's interestingness" — influential results
   - **Balanced**: "Pragmatic interestingness" — both elegant AND impactful

3. **Complexity (K):**
   ```
   K(T) = len(proof_T) + log(indegree_T)
   ```
   Captures: effort required (prefer elegant short proofs)

**Final score (three variants):**

```python
# Variant A: Pure structural (Occam's razor)
interestingness_structural = (novelty * structural_compression) / (complexity + 1)

# Variant B: Pure statistical (impact-focused)  
interestingness_statistical = (novelty * statistical_compression) / (complexity + 1)

# Variant C: Hybrid (tunable)
interestingness_hybrid = (novelty * (α·struct + β·stat + γ·bridge)) / (complexity + 1)
```

**What each variant captures:**

| Variant | High Scorers | Low Scorers | Use Case |
|---------|-------------|-------------|----------|
| Structural | Elegant generalizations, powerful abstractions | Trivial corollaries, social citations | Textbook theorems |
| Statistical | Field-defining results, frequently-used tools | Niche but deep results | Citation prediction |
| Hybrid | Balanced impact | Specialized edge cases | Suggesting "next theorem" |

**Validation Strategy:**

1. **Structural variant:**
   - Correlate with expert labels: "elegant proofs"
   - Compare with textbook inclusion
   - Test: Do Fields medalists' theorems score high?

2. **Statistical variant:**
   - Correlate with raw citation count
   - Compare with Mathlib "core" library theorems
   - Test: Does frequency = fundamentality?

3. **Divergence analysis:**
   - High structural, low statistical: "Hidden gems" (underappreciated)
   - Low structural, high statistical: "Overhyped" (socially important, mathematically trivial)
   - Both high: "Landmarks" (truly fundamental)
   - Both low: "Specialized" (niche but valid)

**Expected Results:**

- **Structural-statistical correlation:** ρ ≈ 0.4–0.6 (positive but incomplete)
- **Divergent cases:** ~20% high on one, low on other
- **Optimal α:β ratio:** Empirically determined via:
  - Maximize correlation with "landmark theorem" labels
  - Cross-validate on textbook appearances
  - Human preference studies (present pairs, ask "which more interesting?")

**Philosophical Resolution:**

Both types of compression are valid:
- **Structural** = what mathematics *is* (logical structure)
- **Statistical** = how mathematics *propagates* (through community)

"Interestingness" for mathematicians = structural + novelty
"Impact" for field = statistical + structural

We measure both, understand their relationship.

---

## III-B. Algorithmic Discovery: Mining Crystallized Lemmas

**Extended Goal:** Beyond evaluating existing theorems, can we **discover new theorems** algorithmically by detecting compressive patterns?

### Motivation

Human mathematical ontology reflects:
- Historical accidents (which problems were studied first)
- Pedagogical constraints (what's teachable)
- Aesthetic preferences (what "feels natural")
- Social dynamics (research community boundaries)

**Question:** Is the current decomposition of Mathlib into theorems **information-theoretically optimal**? Or can we find better factorizations post-hoc using compression principles?

**Key insight:** Discovery is messy and may require suboptimal intermediate representations to make progress. Mathematicians prove lemmas that help locally but don't globally optimize. Retrospective analysis with full corpus might reveal superior abstractions.

---

### Crystallized Lemmas: Definition

**Term:** **Crystallized Lemma** = theorem algorithmically extracted by detecting repeated proof patterns whose abstraction reduces total description length.

**Metaphor:** Like crystallization in chemistry—structure emerges from solution when conditions are right. Repeated patterns "crystallize" into named abstractions when compression threshold is met.

**Formal criterion:**
```
A proof pattern P should be crystallized into theorem T_P if:

ΔL_crystallize(P) = L(Mathlib_without_T_P) - L(Mathlib_with_T_P) > τ

where τ is compression threshold (e.g., save >50 tactics)
```

**Types of Crystallized Lemmas:**

1. **Tactical Patterns** (tactic sequence abstraction)
   - Frequently repeated tactic subgraphs
   - Example: "ε-δ argument template" appearing 100 times
   
2. **Premise Patterns** (lemma co-occurrence)
   - Sets of lemmas used together repeatedly
   - Example: Theorems A, B, C always appear together → abstract their combination

3. **Proof Strategy Patterns** (higher-order abstraction)
   - Isomorphic proof structures across different domains
   - Example: Same induction pattern used in 50 different contexts

4. **Cross-Domain Bridges** (conceptual unification)
   - Pattern appears in theorems from disconnected modules
   - Example: Same reasoning in topology and algebra → reveals hidden connection

---

### Mining Algorithm: Pattern Crystallization

**Phase 1: Pattern Detection**

```python
def mine_crystallizable_patterns(mathlib_proofs, min_frequency=5, min_complexity=10):
    """
    Identify repeated tactic subtrees worthy of abstraction.
    """
    patterns = {}
    
    # Extract all tactic subtrees of depth 3-7
    for proof in mathlib_proofs:
        ast = proof.tactic_tree
        for subtree in extract_subtrees(ast, min_depth=3, max_depth=7):
            # Canonicalize (ignore variable names, keep structure)
            canonical = canonicalize_ast(subtree)
            
            if len(canonical) < min_complexity:
                continue  # too trivial
                
            if canonical not in patterns:
                patterns[canonical] = []
            patterns[canonical].append({
                'theorem': proof.theorem_id,
                'location': subtree.position,
                'context': subtree.parent_tactics
            })
    
    # Filter by frequency
    frequent_patterns = {
        p: occurrences 
        for p, occurrences in patterns.items() 
        if len(occurrences) >= min_frequency
    }
    
    return frequent_patterns
```

**Phase 2: Compression Estimation**

```python
def estimate_compression_gain(pattern, occurrences, mathlib):
    """
    Compute ΔL if this pattern were abstracted to new theorem.
    """
    # Cost of proving the pattern once as new theorem
    cost_new_theorem = len(pattern)  # tactics in pattern itself
    cost_new_theorem += 5  # overhead: theorem statement, naming, etc.
    
    # Savings from replacing all occurrences
    savings = 0
    for occ in occurrences:
        # Original: full pattern length
        original_cost = len(pattern)
        
        # After: single reference to new theorem
        replacement_cost = 1  # one tactic: "apply new_theorem"
        
        savings += (original_cost - replacement_cost)
    
    # Net compression
    net_gain = savings - cost_new_theorem
    
    # Metadata for analysis
    metadata = {
        'occurrences': len(occurrences),
        'avg_savings_per_use': savings / len(occurrences),
        'pattern_complexity': len(pattern),
        'net_compression': net_gain,
        'modules_spanned': len(set(occ['theorem'].module for occ in occurrences))
    }
    
    return net_gain, metadata
```

**Phase 3: Candidate Ranking**

```python
def rank_crystallization_candidates(patterns):
    """
    Score patterns by multiple criteria beyond raw compression.
    """
    candidates = []
    
    for pattern, occurrences in patterns.items():
        net_gain, metadata = estimate_compression_gain(pattern, occurrences, mathlib)
        
        if net_gain <= 0:
            continue  # not compressive
        
        # Additional quality signals
        quality_score = (
            metadata['net_compression']  # raw compression
            * log(metadata['modules_spanned'] + 1)  # cross-domain bonus
            * (1 + metadata['pattern_complexity'] / 50)  # favor non-trivial patterns
            / (1 + variance_of_occurrence_contexts)  # penalize context-specific patterns
        )
        
        candidates.append({
            'pattern': pattern,
            'occurrences': occurrences,
            'compression': net_gain,
            'quality': quality_score,
            'metadata': metadata
        })
    
    return sorted(candidates, key=lambda x: x['quality'], reverse=True)
```

**Phase 4: Synthesis & Validation**

```python
def synthesize_crystallized_lemma(pattern, occurrences):
    """
    Generate theorem statement and proof for discovered pattern.
    """
    # Extract common premises from all occurrences
    common_premises = extract_common_context(occurrences)
    
    # Generalize pattern (abstract over variable names)
    generalized_pattern = abstract_variables(pattern)
    
    # Synthesize theorem statement
    theorem_statement = f"""
    theorem crystallized_lemma_{hash(pattern)} 
      {format_premises(common_premises)} : 
      {infer_conclusion_type(pattern)} :=
    by
      {format_tactics(generalized_pattern)}
    """
    
    # Validate: does this actually compile in Lean?
    validation_result = lean_typecheck(theorem_statement)
    
    if not validation_result.success:
        return None  # pattern not generalizable
    
    return {
        'statement': theorem_statement,
        'proof': generalized_pattern,
        'replaces': occurrences,
        'saves': estimate_total_savings(occurrences, pattern)
    }
```

---

### Evaluation: Human vs. Algorithmic Ontology

**Comparison Dimensions:**

**1. Compression Efficiency**
```python
def compare_factorizations(human_mathlib, crystallized_mathlib):
    """
    Which achieves lower total description length?
    """
    DL_human = compute_total_mdl(human_mathlib)
    DL_crystallized = compute_total_mdl(crystallized_mathlib)
    
    improvement = (DL_human - DL_crystallized) / DL_human
    
    return {
        'compression_improvement': improvement,
        'human_DL': DL_human,
        'crystallized_DL': DL_crystallized,
        'theorems_added': len(crystallized_mathlib) - len(human_mathlib),
        'avg_compression_per_new_theorem': improvement / num_new_theorems
    }
```

**2. Conceptual Alignment**
```python
def evaluate_conceptual_coherence(crystallized_lemmas, human_modules):
    """
    Do algorithmic abstractions align with human-defined modules?
    """
    # For each crystallized lemma, check module diversity of uses
    coherence_scores = []
    
    for lemma in crystallized_lemmas:
        modules_using = set(occ.module for occ in lemma.occurrences)
        
        if len(modules_using) == 1:
            # Module-specific pattern → aligns with human organization
            coherence_scores.append(1.0)
        else:
            # Cross-module pattern → novel abstraction
            # Check: is there an existing cross-module concept here?
            related_human_abstractions = find_abstractions_spanning_modules(modules_using)
            
            if related_human_abstractions:
                coherence_scores.append(0.5)  # humans noticed connection differently
            else:
                coherence_scores.append(0.0)  # genuinely novel
    
    return {
        'avg_coherence': np.mean(coherence_scores),
        'novel_abstractions': sum(1 for s in coherence_scores if s == 0.0),
        'module_specific': sum(1 for s in coherence_scores if s == 1.0)
    }
```

**3. Discovery Order Optimality**
```python
def analyze_discovery_order(mathlib_history, crystallized_lemmas):
    """
    When should each crystallized lemma have been proven?
    Vs. when could it have been discovered (pattern appeared)?
    """
    results = []
    
    for lemma in crystallized_lemmas:
        # Earliest depth where pattern appears ≥ threshold times
        first_detectable_depth = find_first_occurrence_threshold(
            lemma.pattern, 
            mathlib_history, 
            min_occurrences=5
        )
        
        # Check if human-proven equivalent exists
        human_equivalent = find_human_theorem_with_similar_pattern(lemma)
        
        if human_equivalent:
            actual_proof_depth = human_equivalent.depth
            delay = actual_proof_depth - first_detectable_depth
            results.append({
                'lemma': lemma,
                'optimal_depth': first_detectable_depth,
                'actual_depth': actual_proof_depth,
                'delay': delay,
                'compression_lost': estimate_compression_loss_from_delay(delay, lemma)
            })
        else:
            # Novel pattern never abstracted by humans
            results.append({
                'lemma': lemma,
                'optimal_depth': first_detectable_depth,
                'actual_depth': None,  # never proven
                'missed_opportunity': True,
                'total_compression_lost': estimate_total_possible_compression(lemma)
            })
    
    return results
```

---

### Expected Discoveries

**Category 1: Missed Generalizations**
- Patterns humans noticed in one domain but not others
- Example: Tactic sequence for proving "preserves structure" appears in:
  - Group homomorphisms (human theorem exists)
  - Ring homomorphisms (human theorem exists)  
  - Topological continuity (human theorem exists)
  - **BUT:** Abstract "structure-preserving map" pattern not unified at deepest level
  - **Crystallized lemma:** Meta-theorem about preservation in general categories

**Category 2: Over-Specialized Decompositions**
- Humans proved 10 similar theorems that could be one with parameter
- Example: Separate theorems for n=2,3,4,5 cases
- **Crystallized lemma:** Single parameterized version

**Category 3: Implicit Proof Patterns**
- Recurring tactic sequences never named
- Example: "Case split + symmetry + induction" appears 50 times
- Humans re-derive each time (muscle memory)
- **Crystallized lemma:** Named tactic macro that's formally a theorem

**Category 4: Cross-Domain Bridges**
- Same proof structure in disconnected modules
- Reveals deep connection humans didn't notice
- Example: Proof pattern in number theory identical to one in graph theory
- **Crystallized lemma:** Unifying abstraction showing isomorphism

**Example: Crystallized Lemma Discovery in Action**

**Scenario:** Algorithm detects this tactic pattern appearing 47 times across Mathlib:

```lean
-- Pattern detected (canonicalized):
intro h_pos
cases h_pos with a b
  · left; exact proof_for_case_a
  · right; exact proof_for_case_b
```

**Occurrences:** 
- 15 times in `Data.Nat` (natural number properties)
- 12 times in `Topology.Basic` (topological space proofs)
- 10 times in `Algebra.Group` (group theory)
- 10 times in `Order.Lattice` (lattice theory)

**Human status:** No existing lemma abstracts this pattern. Each proof repeats it inline.

**Compression calculation:**
```
Pattern length: 4 tactics
Occurrences: 47
Cost without abstraction: 47 × 4 = 188 tactics

Cost with crystallized lemma:
  - New theorem: 4 tactics (prove pattern once)
  - Statement overhead: ~5 tactics
  - References: 47 × 1 = 47 tactics
  - Total: 56 tactics

Net compression: 188 - 56 = 132 tactics saved
Compression ratio: 132/188 = 70% reduction
```

**Synthesized crystallized lemma:**
```lean
theorem crystallized_disjunctive_case_split 
  {α : Type*} {P Q : α → Prop} {x : α}
  (h : P x ∨ Q x) 
  (hp : P x → Goal₁) 
  (hq : Q x → Goal₂) :
  Goal₁ ∨ Goal₂ :=
by
  cases h with a b
    · left; exact hp a
    · right; exact hq b
```

**Why humans didn't abstract this:**
1. **Too domain-specific at local level:** In each module, looks like natural proof flow
2. **Crosses module boundaries:** Abstraction would need to live in `Logic.Basic` but isn't obviously "logical principle"
3. **Medium complexity:** Not trivial (worth abstracting) but not complex (demands attention)
4. **No standard name:** Humans haven't conceptualized this as named pattern

**Why algorithm discovers it:**
1. **Frequency-based:** Appears often enough to exceed threshold
2. **Structural matching:** Exact tactic tree isomorphism despite different domains
3. **Compression-driven:** Clear MDL gain from abstraction
4. **Domain-agnostic:** Algorithm doesn't respect module boundaries

**Validation questions:**
1. Would using this make proofs more readable? (Human survey)
2. Does it reveal conceptual connection between nat/topology/algebra/lattice? 
3. Could it have been discovered earlier in development? (Timeline analysis)
4. Are there even more instances with slight variations we could also capture?

**This exemplifies:**
- **Missed generalization:** Humans see pattern locally but don't globalize
- **Cross-domain transfer:** Same reasoning structure in different contexts
- **Compression opportunity:** Significant savings from simple abstraction
- **Algorithmic advantage:** Doesn't have cognitive boundaries of human modules

---

### Philosophical Implications

**On Discovery vs. Optimization:**

**Thesis:** Mathematical discovery necessarily involves suboptimal checkpoints.

**Argument:**
1. **Bounded rationality:** Mathematicians can't see entire corpus at once
2. **Local vs. global optima:** Lemma useful for current proof may not be globally optimal
3. **Path dependence:** Once abstraction A is adopted, theorem B built on A is natural, even if better factorization exists
4. **Social constraints:** Must prove in order others can verify; can't skip to endpoint

**Evidence to seek:**
- Do crystallized lemmas discovered at depth d become less compressive than those discoverable earlier?
  - If yes → penalty for delayed abstraction
- Are frequently-updated modules closer to info-theoretic optimum?
  - If yes → refactoring pressure works
- Do "stable" modules have more missed patterns?
  - If yes → ossification prevents optimization

**Analogy:** Code refactoring in software
- Initial implementation works but isn't optimal
- Post-hoc analysis reveals better abstractions
- Refactoring improves maintainability
- **BUT:** Can't always refactor due to dependencies

**Key question:** If we could restart Mathlib with crystallized lemmas as "hints," would development be faster?

**Counterfactual experiment:**
1. Mine crystallized lemmas from full Mathlib
2. Inject them at optimal discovery depth in historical timeline
3. Measure: how many subsequent theorems become easier to prove?
4. Compare: actual development vs. oracle-guided development

---

### Implementation Roadmap

**Week 1: Pattern Mining**
- Extract all tactic subtrees depth 3-7
- Compute isomorphism classes (canonical forms)
- Build frequency distribution

**Week 2: Compression Estimation**
- For top-1000 frequent patterns, compute ΔL
- Rank by compression gain
- Cluster by module distribution

**Week 3: Synthesis**
- Attempt to synthesize top-100 candidates as actual Lean theorems
- Validate type-checking
- Measure compilation success rate

**Week 4: Comparative Analysis**
- Compare crystallized vs. human factorization
- Identify missed generalizations
- Measure optimality gap

**Week 5: Counterfactual Simulation**
- Inject crystallized lemmas at optimal depths
- Re-simulate development (how many proofs shortened?)
- Quantify compression lost from suboptimal ordering

---

### Deliverables

**1. Crystallized Lemma Library**
- Ranked list of top-N compressive patterns
- Synthesized theorem statements
- Occurrence maps (where they'd help)

**2. Compression Analysis**
```
Current Mathlib DL: X tactics
Optimized (with crystallization): Y tactics
Improvement: (X-Y)/X = Z%

New theorems needed: N
Avg compression per new theorem: (X-Y)/N tactics
```

**3. Discovery Order Analysis**
- Timeline showing when patterns became detectable
- Comparison with when humans actually proved equivalents
- Quantified "missed opportunity" cost

**4. Ontology Comparison**
- Mathlib's module structure (human)
- Crystallized lemma cluster structure (algorithmic)
- Overlap and divergence analysis
- Novel cross-domain connections discovered

**5. Design Principles**
- Extracted rules: "Good theorems have properties X, Y, Z"
- Predictive model: Given proof corpus, suggest what to abstract next
- Integrated into ATP: system proposes new lemmas during development

---

### Connection to Broader Research Goals

**This addresses:**

1. **"What makes a theorem interesting?"**
   - Interesting = high compression gain when added
   - Quantifiable via crystallization criterion

2. **"What is mathematical intuition?"**
   - Humans intuit patterns worth abstracting
   - Can we learn their heuristics from what they *do* crystallize vs. what they *could*?

3. **"What is the adjacent possible?"**
   - Crystallized lemmas that become detectable at depth d expand the adjacent possible
   - Measuring this reveals structure of discovery space

4. **"Can we optimize the path through theorem space?"**
   - Counterfactual analysis shows better orderings exist
   - Identifies principles for efficient exploration

**Novel contribution:** Moving from *evaluating* to *generating* mathematical ontologies via compression principles.

---

## IV. Adjacent Possible Dynamics

### Growth Kernel Matrix

**Definition:** K[i,j] = P(proving theorem j becomes possible after theorem i is added)

**Empirical Estimation:**
```python
def build_growth_kernel(dag, time_window=50):
    """
    Estimate enabling probability from historical DAG growth.
    """
    K = np.zeros((n_theorems, n_theorems))
    
    for t in range(time_window, max_depth):
        # Theorems added in window [t-window, t]
        recent = theorems_at_depth_range(t - time_window, t)
        
        # Theorems added at depth t+1 (newly enabled)
        new = theorems_at_depth(t + 1)
        
        for i in recent:
            for j in new:
                if i in ancestors(j):
                    # i contributed to enabling j
                    K[i, j] += 1.0 / len(ancestors(j))  # credit shared among ancestors
    
    # Normalize to probabilities
    K /= K.sum(axis=1, keepdims=True)
    return K
```

**Spectral Analysis:**
```python
eigenvalues, eigenvectors = np.linalg.eig(K)

# Fast eigenvectors = high-growth research directions
fast_directions = eigenvectors[:, np.argsort(eigenvalues)[-10:]]

# Project each theorem onto growth directions
growth_potential = dag.nodes @ fast_directions
```

**r=0 Prediction Target:**  
`eigenvalue_acceleration(T)` = weighted contribution to top-k fast eigenmodes

**Features:**
- `parent_eigenspace_alignment`: cosine similarity of parents to fast eigenvectors
- `module_growth_rate`: historical growth rate of T's module
- `ancestor_fertility`: mean outdegree of ancestors (productive lineages)

---

## V. Concrete Experimental Roadmap

### Phase 1: MDL Infrastructure (Weeks 1-2)
**Goal:** Compute actual compression values

1. **Extract all proofs** from Mathlib to structured format:
   ```
   theorem_id → {tactics[], premises[], tactic_ast}
   ```

2. **Build n-gram language models**:
   - Tactic 3-grams, 4-grams
   - Premise sequence models
   - Joint tactic-premise models

3. **Implement subgraph isomorphism detector**:
   - Use VF2 algorithm on tactic ASTs
   - Cache frequent subtree patterns

4. **Compute Δ_MDL for all theorems**:
   - Approximate via pattern reuse counting
   - Validate on subset with manual proof refactoring

**Deliverable:** `theorem_id → {mdl_gain, pattern_reuse_count, compression_ratio}`

### Phase 2: Novelty Metrics (Weeks 3-4)
**Goal:** Quantify proof strategy innovation

1. **Tactic n-gram surprise**:
   - Train temporal models (only proofs before depth d)
   - Compute perplexity at each theorem's introduction

2. **Proof AST edit distance**:
   - Pairwise distances for all parent-child pairs
   - Cluster proofs by strategy similarity

3. **Rare combination mining**:
   - Extract tactic bigrams, trigrams
   - Identify statistically surprising combinations

**Deliverable:** `theorem_id → {innovation_score, strategy_novelty, rare_tactic_fraction}`

### Phase 3: Graph Features (Weeks 5-6)
**Goal:** Structural importance predictors

1. **Temporal betweenness tracking**:
   - Compute at depths d, d+5, d+10, d+20
   - Measure growth rates

2. **PageRank evolution**:
   - Track rank over depth increments
   - Identify accelerating/decelerating theorems

3. **Module bridging**:
   - Run Louvain clustering at each depth
   - Measure modularity changes

4. **Growth kernel estimation**:
   - Build K matrix from historical data
   - Spectral decomposition

**Deliverable:** `theorem_id → {betweenness_growth, pagerank_accel, bridging_score, eigen_potential}`

### Phase 4: Multi-Target Prediction (Weeks 7-8)
**Goal:** Joint model of impact dimensions

**Model Architecture:**
```
Input: r=0 features (parent stats, upstream structure, local topology)
       ↓
Shared encoder (GNN or transformer over local subgraph)
       ↓
Multi-head prediction:
├─ Head 1: MDL gain (regression)
├─ Head 2: Innovation score (regression)  
├─ Head 3: Betweenness growth (regression)
└─ Head 4: Interestingness (regression)

Loss = Σ_i λ_i * MSE(pred_i, target_i)
```

**Key experiment:** Which heads benefit from shared representations?  
→ Reveals whether "impact" is unified or multidimensional.

### Phase 5: Validation & Interpretation (Weeks 9-10)
**Goal:** Test against human notions of importance

1. **Benchmark datasets**:
   - Expert-labeled "landmark theorems" in Mathlib
   - Textbook-featured results
   - Highly-discussed theorems on Lean Zulip

2. **Ablation studies**:
   - Remove feature clusters, measure Δ performance
   - Identify which structural properties matter most

3. **Failure analysis**:
   - Find high-MDL theorems with low citation
   - Find high-citation theorems with low MDL
   - Understand social vs. mathematical importance divergence

4. **Case studies**:
   - Manually inspect top-k novel theorems by model
   - Verify proof strategy uniqueness
   - Check if compression actually occurs downstream

**Deliverable:** Paper draft + interactive visualization

---

## VI. Technical Implementation Details

### Data Structures

```python
class TheoremNode:
    id: str
    depth: int
    module: str
    proof: ProofStructure
    features: Dict[str, float]
    
class ProofStructure:
    tactics: List[str]
    premises: List[str]  # theorem IDs used
    tactic_ast: nx.DiGraph  # AST of proof structure
    
class DAG:
    nodes: Dict[str, TheoremNode]
    edges: List[Tuple[str, str]]  # (premise, conclusion) pairs
    
    def subgraph_at_depth(self, d) -> nx.DiGraph:
        """Return induced subgraph of nodes at depth ≤ d"""
        
    def ancestors(self, node_id) -> Set[str]:
        """All upstream dependencies"""
        
    def descendants_within_horizon(self, node_id, r) -> Set[str]:
        """Descendants within radius r"""
```

### Feature Computation Pipeline

```python
def compute_all_features(dag: DAG, proofs: Dict, r: int) -> pd.DataFrame:
    """
    Master pipeline.
    """
    features = []
    
    for node in dag.frontier_at_depth(d):
        f = {}
        
        # Basic (always available)
        f.update(node_basic_features(node, dag))
        
        # Parent stats (r=0)
        f.update(parent_features(node, dag, proofs))
        
        # Upstream structure (r=0)
        f.update(upstream_features(node, dag))
        
        # MDL proxy (r=0)
        f.update(compression_features(node, dag, proofs))
        
        # Innovation (r=0)
        f.update(novelty_features(node, dag, proofs))
        
        # Graph centrality (r=0, but computed on seen graph)
        f.update(centrality_features(node, dag))
        
        # Peek features (r ≥ 1)
        if r >= 1:
            f.update(peek_r1_features(node, dag))
        if r >= 2:
            f.update(peek_r2_features(node, dag))
        
        features.append(f)
    
    return pd.DataFrame(features)
```

### Compression Features (r=0 Proxies)

```python
def compression_features(node, dag, proofs):
    """
    Approximate MDL gain without re-proving.
    """
    proof = proofs[node.id]
    parent_proofs = [proofs[p] for p in node.parents]
    
    # Pattern reuse potential
    proof_pattern = extract_tactic_subtree(proof.tactic_ast, max_depth=3)
    
    # Count isomorphic patterns in downstream vicinity
    downstream_similar = 0
    for desc in dag.descendants_within_horizon(node.id, r=5):  # lookahead ok, not using as feature directly
        if subgraph_isomorphic(proofs[desc].tactic_ast, proof_pattern):
            downstream_similar += 1
    
    # Proxy: assume similar patterns in parents predict future reuse
    parent_pattern_overlap = count_shared_subtrees(parent_proofs)
    
    return {
        'proof_abstraction_ratio': len(proof.premises) / len(proof.tactics),
        'parent_pattern_diversity': len(unique_subtrees(parent_proofs)) / len(parent_proofs),
        'upstream_pattern_frequency': parent_pattern_overlap,
        'proof_lemma_density': len(proof.premises) / (len(proof.tactics) + 1),
    }
```

### Novelty Features (r=0)

```python
def novelty_features(node, dag, proofs):
    """
    Proof strategy innovation proxies.
    """
    proof = proofs[node.id]
    historical_proofs = [proofs[n] for n in dag.ancestors(node.id)]
    
    # Build n-gram model from history
    ngram_model = TacticNGramModel(historical_proofs, n=4)
    perplexity = ngram_model.perplexity(proof.tactics)
    
    # Tactic rarity
    tactic_freqs = Counter(t for p in historical_proofs for t in p.tactics)
    avg_rarity = np.mean([-np.log(tactic_freqs[t]/sum(tactic_freqs.values())) 
                          for t in proof.tactics])
    
    # Proof strategy distance from parents
    parent_proofs = [proofs[p] for p in node.parents]
    avg_edit_distance = np.mean([
        tree_edit_distance(proof.tactic_ast, pp.tactic_ast)
        for pp in parent_proofs
    ])
    
    return {
        'tactic_perplexity': np.log(perplexity),
        'avg_tactic_rarity': avg_rarity,
        'proof_strategy_distance': avg_edit_distance,
        'rare_tactic_fraction': sum(1 for t in proof.tactics 
                                     if tactic_freqs[t] < np.percentile(list(tactic_freqs.values()), 10)) / len(proof.tactics),
    }
```

---

## VII. Expected Outcomes & Insights

### Predictive Performance
- **MDL gain:** R² ≈ 0.3–0.5 at r=0 (structural compression is learnable)
- **Innovation score:** R² ≈ 0.4–0.6 (proof strategies cluster by domain)
- **Betweenness growth:** R² ≈ 0.2–0.4 (graph position predicts bridging)
- **Interestingness (composite):** R² ≈ 0.5–0.7 (validates information-theoretic definition)

### Scientific Insights
1. **MDL vs. citation divergence:** Identify useful-but-ignored theorems
2. **Innovation without impact:** Novel proof strategies that don't generalize
3. **Module bridging as growth catalyst:** Theorems connecting domains accelerate research
4. **Tactic evolution:** Which proof strategies emerge, which go extinct
5. **Optimal discovery paths:** Can we infer counterfactual "better" theorem orderings?

### Philosophical Implications
- **Interestingness = compression + novelty / complexity** (operationalized)
- **Intuition = pattern recognition + edit distance minimization** (learnable from structure)
- **Adjacent possible = eigenspace of growth kernel** (quantifiable expansion)

---

## VIII. Future Directions

### Beyond Static DAG Analysis
1. **Temporal dynamics:** Model theorem discovery as point process, predict *when* theorems emerge
2. **Counterfactual DAGs:** What if theorem T were proven earlier/later? Resample discovery order
3. **Human vs. ATP differences:** Do humans prefer high-MDL theorems? Do ATPs find novel strategies?

### Scaling to Tactic Discovery
- Extend from theorems to **tactics themselves** (meta-level compression)
- Measure: does new tactic reduce average proof length? (echoing [17])
- Predict: which tactic refactorings have high adoption rate?

### Crystallized Lemmas as Discovery Tool
- **Real-time suggestion:** During proof development, detect emerging patterns and suggest "this should be a lemma"
- **Automated refactoring:** Propose crystallized lemmas to library maintainers with compression estimates
- **Cross-library transfer:** Find patterns in Library A that compress Library B (porting abstractions)
- **Minimal basis discovery:** What is the smallest set of crystallized lemmas needed to achieve 90% compression?

### Optimal Discovery Paths
- **Counterfactual timeline:** If Mathlib started with crystallized lemmas as "oracle hints," measure speedup
- **Reinforcement learning:** Train agent to suggest lemmas that maximize future compression
- **Curriculum learning:** Order theorem proving to minimize cumulative description length
- **Detect ossification:** When does a module stop benefiting from refactoring?

### Human-Algorithm Collaboration
- **Identify blind spots:** Crystallized patterns humans systematically miss
- **Learn abstraction heuristics:** What features make humans abstract a pattern?
- **Reverse engineer intuition:** Can we predict what humans will find "elegant" from compression metrics?
- **Closing the loop:** Use crystallized lemmas to train mathematicians' pattern recognition

### Cross-Library Generalization
- Train on Mathlib, test on other proof assistants (Coq, Isabelle)
- Universal features of mathematical discovery?
- Do different communities crystallize different patterns? (Cultural analysis)

### Interactive Theorem Suggesting
- **Proof assistant integration:** Suggest "interesting" next theorems to prove
- Optimize for: MDL gain × novelty × missing bridging connections
- Human-in-the-loop: learn from mathematician's actual choices (RL from preference feedback)

### Philosophical Questions Enabled by Crystallization

**1. Is human mathematics optimal?**
- Compression gap between human and algorithmic factorizations
- If significant gap exists → human ontology is suboptimal
- If minimal gap → human intuition is near-optimal

**2. What is mathematical understanding?**
- If crystallized lemmas with high compression are "unnatural" to humans → understanding ≠ compression
- If crystallized lemmas align with human-judged "elegance" → validates compression theory of understanding

**3. Can we formalize aesthetics?**
- Do "beautiful" theorems have high compression + low complexity?
- Or is beauty orthogonal to information theory?
- Test: expert-rated aesthetic scores vs. crystallization metrics

**4. What is the structure of mathematical knowledge?**
- Crystallized lemma dependency graph reveals "true" conceptual hierarchy
- Compare with human-imposed module structure
- Network analysis: centrality of algorithmic vs. human abstractions

---

## IX. References & Connection to Literature

**Information Theory:**
- Shannon [18]: Entropy of symbolic sequences → tactic n-grams
- Rissanen [22]: MDL principle → theorem compression value

**Network Science:**
- Simon [23]: Preferential attachment → why some theorems dominate
- Tria et al. [24]: Adjacent possible dynamics → growth kernel eigenanalysis

**Automated Theorem Proving:**
- LEGO-Prover [11]: Lemma value → MDL gain operationalizes this
- Automated tactic discovery [17]: Compression via refactoring → direct inspiration
- LeanDojo [7], DeepSeek-Prover [8]: Premise selection → parent features inform prediction

**Philosophy of Math:**
- Puzis et al. [27]: Generating interesting theorems → our interestingness formula
- Rzhetsky et al. [26]: Choosing experiments → adjacent possible optimization

---

## X. Immediate Next Steps (This Week)

### Core Pipeline (Days 1-3)

1. **Parse all Mathlib proofs to structured format**
   - Extract tactic sequences
   - Build premise dependency lists
   - Construct tactic AST graphs

2. **Implement tactic n-gram model**
   - 3-grams and 4-grams
   - Compute perplexity for each theorem

3. **Subgraph isomorphism baseline**
   - VF2 implementation on tactic ASTs
   - Count pattern reuse in local neighborhoods

4. **Compute MDL approximation for 100 example theorems**
   - Manual validation: does high MDL correlate with "feels important"?

5. **Update feature pipeline**
   - Add: `tactic_perplexity`, `proof_abstraction_ratio`, `pattern_reuse_proxy`
   - Re-run experiments with new targets: {MDL, innovation, betweenness_growth}

### Crystallization Extension (Days 4-5)

6. **Pattern mining prototype**
   - Extract tactic subtrees depth 3-5 from 1000 random theorems
   - Build frequency histogram
   - Identify top-20 most repeated patterns

7. **Compression calculation for top patterns**
   - For each frequent pattern, estimate ΔL_crystallize
   - Rank by compression gain
   - Manually inspect top-5: are they "sensible" abstractions?

8. **Comparison with existing theorems**
   - For discovered patterns, search for similar human-proven lemmas
   - Measure overlap: how many crystallized patterns already exist as theorems?
   - Identify missed abstractions: high-compression patterns with no human equivalent

### Validation (Day 6-7)

9. **Case study: One crystallized lemma**
   - Pick highest-compression pattern without human equivalent
   - Synthesize full theorem statement
   - Attempt to compile in Lean
   - Manually verify: would using this shorten downstream proofs?

10. **Document initial findings**
   - Write memo comparing MDL predictions vs. actual citation counts
   - Identify divergence cases (high MDL + low citations = hidden gems)
   - Update research plan based on what we learn

---

**End of Plan Document**

*This document will evolve as experiments progress. Version control in Git. Update weekly.*
