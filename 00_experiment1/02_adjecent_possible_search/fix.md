# thinking.md — Open questions and unresolved assumptions

## Tactic application is not free

Our Level I model assumes that once all premises are in memory, discovery is instantaneous. But real proof construction has a per-attempt cost.

In Lean 4, applying a tactic to a goal state requires compilation — the kernel checks the term. This takes time t per attempt, and most attempts fail. A tactic like `simp` takes a list of lemmas and tries to close the goal using all of them. A tactic like `apply` takes exactly one lemma. `rw` takes one rewrite rule. So the arity varies: some tactics consume 1 premise, some consume many.

This means the agent faces a combinatorial testing problem even when all premises are in memory. If memory contains K theorems and the tactic expects n premises, there are C(K, n) combinations to try. Even for n=2 and K=5000, that's ~12.5 million pairs. Each test costs time t (compilation + kernel check). The agent cannot "test all at once."

Current model: discovery cost = 0 once prerequisites are in memory.
Reality: discovery cost = (number of tactic attempts) × t, where each attempt selects a subset of premises and a tactic, writes the Lean term, and compiles.

### Implications for our strategies

1. **Memory size K has a dual role.** Larger K means more premises available (good for retrieval) but exponentially more combinations to test (bad for search). There may be an optimal K that balances these — too small and you miss prerequisites, too large and you drown in combinatorial search. This would show up as a non-monotonic coverage curve: coverage increasing with K, then plateauing or decreasing once search cost dominates.

2. **Tactic arity matters.** Tactics that consume few premises (apply, rw, exact) have search cost linear in K. Tactics that consume many premises (simp with a long lemma list, omega with many hypotheses) have search cost polynomial or worse. The difficulty of a proof step depends not just on whether the right premises are available but on how many premises the tactic needs and how many wrong combinations exist.

3. **Tactic choice and premise selection are coupled.** You don't choose premises then choose a tactic — you choose a tactic, which determines how many and what kind of premises it needs, then search for matching premises. This is the Level II→III transition in our hierarchy. The search space is (number of tactics) × (premise combinations per tactic), not (number of tactics) + (number of premises).

4. **Time budget becomes a real constraint.** In our current model, budget = number of discovery steps. In a realistic model, budget = wall-clock time, and each step consumes variable time depending on tactic arity and compilation cost. A strategy that makes many cheap attempts (apply single lemmas) vs few expensive attempts (simp with large lemma sets) would have very different coverage profiles under the same time budget.

### How to incorporate this

Extend the simulation with a per-discovery cost function: cost(T) = sum over proof steps of C(K_available, arity_of_tactic) × t. We have the data to estimate this: each theorem's proof in our dataset lists the tactics used and the premises per tactic step. We can compute the empirical distribution of tactic arities and use it to calibrate a stochastic cost model.

The key experiment: re-run the memory-bounded exploration with a time budget (total compilation-equivalents) instead of a step budget, and see how the phase transition shifts. If the transition moves to smaller K (because large K makes each step too expensive), that's a strong result — it means the optimal context window for a prover is smaller than the retrieval-only analysis suggests.

### Connection to neural provers

Neural provers implicitly handle this by generating one tactic application at a time (next-step prediction). They don't enumerate combinations — they predict the most likely tactic + premise combination given the proof state. This is an amortized search: the neural network's forward pass replaces the combinatorial enumeration. The quality of this amortization is what separates good provers from bad ones. Our retrieval experiment (Experiment 4) measures the premise selection component; the tactic selection component is the gap between retrieval performance and proof completion performance.