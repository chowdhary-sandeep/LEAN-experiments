"""
Cost-Constrained Discovery Dynamics  (fix.md implementation)

Tactic application is NOT free.  At memory K every discovery attempt
costs  cost_per_step(K) = max(1, K)  compilation-equivalents
(unary / linear tactic model: most tactics consume exactly one lemma).

With a fixed TIME_BUDGET the number of steps shrinks as K grows:
    K=100   → 600,000 steps   (10× more than today's 60k)
    K=1,000 → 60,000 steps    (same as experiment2_phase_transition.py)
    K=5,000 → 12,000 steps
    K=10,000→  6,000 steps
    K=30,000→  2,000 steps

Key prediction (fix.md §1): the coverage-vs-K curve becomes non-monotonic,
peaking at the K where retrieval benefit and combinatorial search cost balance.

Strategies
----------
bfs / dfs / random / greedy   — same algorithms as experiment2_phase_transition.py
min_cost                       — NEW: pick the theorem in A_t with minimum
                                 total_prereqs (fewest tactic steps → cheapest
                                 to verify, proxy for proof complexity)
efficient                      — NEW: maximise expansion_factor / max(1, total_prereqs)
                                 (coverage gain per unit of proof complexity)

Recall modes tested: none, hub_local   (oracle hub not included — this is a
realistic cost model so we skip the oracle variant)

Output: data/experiment2_cost_budget_results.json
"""

import json
import pickle
import random as rng
import heapq
import time
import gc
from pathlib import Path
from collections import deque

SCRIPT_DIR   = Path(__file__).resolve().parent
CACHE_BUNDLE = SCRIPT_DIR.parent / "cache" / "bundle.pkl"
OUTPUT_JSON  = SCRIPT_DIR / "data" / "experiment2_cost_budget_results.json"

# ---------------------------------------------------------------------------
# Cost model
# ---------------------------------------------------------------------------

STEP_BUDGET  = 60_000           # step budget used in experiment2_phase_transition.py
NORM_K       = 1_000            # calibration: K=NORM_K → exactly STEP_BUDGET steps
TIME_BUDGET  = STEP_BUDGET * NORM_K   # 60,000,000 compilation-equivalents


def cost_per_step(K: int) -> int:
    """Compilation-equivalents consumed per discovery attempt at memory size K."""
    return max(1, K)


def steps_available(K: int) -> int:
    """How many discovery steps fit in TIME_BUDGET at memory K."""
    return TIME_BUDGET // cost_per_step(K)


print("=" * 80)
print("COST-CONSTRAINED DISCOVERY  (fix.md)")
print("=" * 80)
print(f"\nCost model : cost_per_step = max(1, K)   [linear / unary tactic]")
print(f"Time budget: {TIME_BUDGET:,} compilation-equivalents")
print(f"Calibration: K={NORM_K:,} -> exactly {STEP_BUDGET:,} steps\n")
print("Steps available at key memory sizes:")
for K in [100, 500, 1_000, 2_000, 5_000, 10_000, 30_000, 100_000]:
    print(f"  K={K:>7,}  ->  {steps_available(K):>9,} steps")


# ---------------------------------------------------------------------------
# IndexedSet  (copied verbatim from experiment2_phase_transition.py)
# ---------------------------------------------------------------------------

class IndexedSet:
    """Set with O(1) add/discard/contains and O(k) random sampling."""
    __slots__ = ('_items', '_pos')

    def __init__(self, iterable=()):
        self._items = list(iterable)
        self._pos   = {item: i for i, item in enumerate(self._items)}

    def add(self, item):
        if item not in self._pos:
            self._pos[item] = len(self._items)
            self._items.append(item)

    def discard(self, item):
        if item in self._pos:
            idx  = self._pos.pop(item)
            last = self._items[-1]
            if idx < len(self._items) - 1:
                self._items[idx] = last
                self._pos[last]  = idx
            self._items.pop()

    def sample(self, k):
        k = min(k, len(self._items))
        return rng.sample(self._items, k) if k > 0 else []

    def __contains__(self, item): return item in self._pos
    def __len__(self):            return len(self._items)
    def __bool__(self):           return bool(self._items)
    def __iter__(self):           return iter(self._items)


# ---------------------------------------------------------------------------
# Load & pre-cache  (then free the heavy NetworkX graph)
# ---------------------------------------------------------------------------

print("\nLoading cache...")
with open(CACHE_BUNDLE, "rb") as f:
    bundle = pickle.load(f)

G           = bundle["G_original"]
del bundle

all_theorems = set(G.nodes())
root_nodes   = sorted([n for n in all_theorems if G.in_degree(n) == 0])
N            = len(all_theorems)
baseline     = len(root_nodes) / N

print(f"  {N:,} theorems,  {len(root_nodes):,} roots,  baseline={baseline:.3f}")

print("Pre-caching compact structures...")
succ_cache    = {n: tuple(G.successors(n)) for n in all_theorems}
total_prereqs = {n: G.in_degree(n)         for n in all_theorems}

del G
gc.collect()
print("  Done (graph freed from RAM).")


# ---------------------------------------------------------------------------
# MemoryDiscovery engine  (copied verbatim from experiment2_phase_transition.py)
# ---------------------------------------------------------------------------

class MemoryDiscovery:
    def __init__(self, mem_size):
        self.mem_size = mem_size

    def initialize(self):
        self.discovered = set(root_nodes)
        mem_list = (root_nodes[:] if self.mem_size >= len(root_nodes)
                    else root_nodes[-self.mem_size:])
        self.memory          = deque(mem_list)
        self.mem_set         = set(mem_list)
        self.recallable      = IndexedSet(self.discovered - self.mem_set)
        self.prereqs_in_mem  = {}
        self.adjacent        = set()

        for node in self.mem_set:
            for s in succ_cache[node]:
                if s not in self.discovered:
                    self.prereqs_in_mem[s] = self.prereqs_in_mem.get(s, 0) + 1

        for thm, met in self.prereqs_in_mem.items():
            if met == total_prereqs[thm] and total_prereqs[thm] > 0:
                self.adjacent.add(thm)

    def _update_memory(self, theorem):
        newly   = set()
        evicted = None

        if len(self.memory) >= self.mem_size:
            evicted = self.memory.popleft()
            self.mem_set.discard(evicted)
            if evicted in self.discovered:
                self.recallable.add(evicted)
            for s in succ_cache[evicted]:
                if s not in self.discovered:
                    old = self.prereqs_in_mem.get(s, 0)
                    if old == total_prereqs[s]:
                        self.adjacent.discard(s)
                    self.prereqs_in_mem[s] = old - 1

        self.memory.append(theorem)
        self.mem_set.add(theorem)
        self.recallable.discard(theorem)

        for s in succ_cache[theorem]:
            if s not in self.discovered:
                nv = self.prereqs_in_mem.get(s, 0) + 1
                self.prereqs_in_mem[s] = nv
                if nv == total_prereqs[s]:
                    self.adjacent.add(s)
                    newly.add(s)

        return newly, evicted

    def discover(self, theorem):
        self.adjacent.discard(theorem)
        self.discovered.add(theorem)
        return self._update_memory(theorem)

    def recall(self, theorem):
        if theorem in self.mem_set:
            return set(), None
        return self._update_memory(theorem)


# ---------------------------------------------------------------------------
# Core run function  (cost-constrained)
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_RECALLS = 200


def run_cost(strategy: str, recall_mode: str, mem_size: int, seed: int = 42) -> dict:
    """
    Mirror of experiment2_phase_transition.run() but with a TIME budget:
      max_steps = steps_available(mem_size)

    recall_mode in {'none', 'hub_local'}.
    strategy    in {'bfs', 'dfs', 'random', 'greedy', 'min_cost', 'efficient'}.
    """
    rng.seed(seed)
    max_steps = steps_available(mem_size)

    md = MemoryDiscovery(mem_size)
    md.initialize()

    discovery_order = {ax: i for i, ax in enumerate(root_nodes)}
    disc_seq        = len(root_nodes)

    disc_heap    = []
    disc_counter = 0
    disc_sign    = 1 if strategy == 'bfs' else -1

    if strategy in ('bfs', 'dfs'):
        for thm in sorted(md.adjacent):
            heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
            disc_counter += 1

    # --- hub_local recall setup ---
    # heap-based for bfs / dfs;  sampled (greedy-style) for random / greedy / new strats
    recall_heap    = []
    recall_counter = 0
    use_recall_heap = recall_mode == 'hub_local' and strategy in ('bfs', 'dfs')

    def local_priority(thm):
        return -sum(1 for s in succ_cache[thm]
                    if s in md.discovered or s in md.adjacent)

    if use_recall_heap and md.recallable:
        for thm in md.recallable:
            heapq.heappush(recall_heap, (local_priority(thm), recall_counter, thm))
            recall_counter += 1

    def push_recall(thm):
        nonlocal recall_counter
        if use_recall_heap:
            heapq.heappush(recall_heap, (local_priority(thm), recall_counter, thm))
            recall_counter += 1

    def pop_recall_heap():
        while recall_heap:
            _, _, thm = heapq.heappop(recall_heap)
            if thm in md.recallable:
                return thm
        return None

    def sample_recall_hub_local():
        """Sampled hub_local recall for strategies without a heap."""
        if not md.recallable:
            return None
        sample = md.recallable.sample(30)
        return max(sample, key=lambda c: sum(
            1 for s in succ_cache[c] if s in md.discovered or s in md.adjacent
        ))

    discovery_count    = 0
    recall_count       = 0
    consecutive_recalls = 0

    for _step in range(max_steps):

        # ---- DISCOVER ---------------------------------------------------
        if md.adjacent:
            chosen = None

            if strategy in ('bfs', 'dfs'):
                while disc_heap:
                    _, thm = heapq.heappop(disc_heap)
                    if thm in md.adjacent:
                        chosen = thm
                        break
                if chosen is None:
                    for thm in sorted(md.adjacent):
                        heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
                        disc_counter += 1
                    while disc_heap:
                        _, thm = heapq.heappop(disc_heap)
                        if thm in md.adjacent:
                            chosen = thm
                            break

            elif strategy == 'random':
                chosen = md.adjacent.pop()
                md.adjacent.add(chosen)

            elif strategy == 'greedy':
                cands = rng.sample(list(md.adjacent), min(50, len(md.adjacent)))
                best, best_e = None, -1
                for c in cands:
                    e = sum(1 for s in succ_cache[c]
                            if s not in md.discovered
                            and md.prereqs_in_mem.get(s, 0) + 1 == total_prereqs[s])
                    if e > best_e:
                        best_e, best = e, c
                chosen = best

            elif strategy == 'min_cost':
                # Pick the theorem with fewest total prerequisites.
                # Proxy for cheapest proof: fewer required lemmas ≈ fewer tactic steps.
                cands  = rng.sample(list(md.adjacent), min(50, len(md.adjacent)))
                chosen = min(cands, key=lambda c: total_prereqs[c])

            elif strategy == 'efficient':
                # Maximise expansion_factor / max(1, total_prereqs).
                # Selects theorems giving the most coverage gain per unit of proof cost.
                cands = rng.sample(list(md.adjacent), min(50, len(md.adjacent)))
                best, best_r = None, -1.0
                for c in cands:
                    expansion = sum(
                        1 for s in succ_cache[c]
                        if s not in md.discovered
                        and md.prereqs_in_mem.get(s, 0) + 1 == total_prereqs[s]
                    )
                    ratio = expansion / max(1, total_prereqs[c])
                    if ratio > best_r:
                        best_r, best = ratio, c
                chosen = best

            if chosen is None:
                break

            newly, evicted = md.discover(chosen)
            discovery_order[chosen] = disc_seq
            disc_seq        += 1
            discovery_count += 1
            consecutive_recalls = 0

            if strategy in ('bfs', 'dfs'):
                for thm in sorted(newly):
                    heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
                    disc_counter += 1

            if evicted and evicted in md.recallable:
                push_recall(evicted)

        # ---- RECALL (when A_t is empty) ----------------------------------
        elif recall_mode != 'none':
            if consecutive_recalls >= MAX_CONSECUTIVE_RECALLS:
                break

            if use_recall_heap:
                recall_thm = pop_recall_heap()
            else:
                recall_thm = sample_recall_hub_local() if recall_mode == 'hub_local' else None

            if recall_thm is None:
                break

            newly, evicted = md.recall(recall_thm)
            recall_count       += 1
            consecutive_recalls += 1

            if strategy in ('bfs', 'dfs'):
                for thm in sorted(newly):
                    heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
                    disc_counter += 1

            if evicted and evicted in md.recallable:
                push_recall(evicted)

        else:
            break

    return {
        'coverage':     len(md.discovered) / N,
        'discoveries':  discovery_count,
        'recalls':      recall_count,
        'steps_budget': max_steps,
    }


# ---------------------------------------------------------------------------
# Configuration & sweep
# ---------------------------------------------------------------------------

# Capped at 100,000 — corpus has 99,412 theorems, so K ≥ 100k = full memory (no constraint).
MEMORY_SIZES = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000,
                40000, 50000, 75000, 100000]
STRATEGIES   = ['bfs', 'dfs', 'random', 'greedy', 'min_cost', 'efficient']
RECALL_MODES = ['none', 'hub_local']

all_results = {}
t_total     = time.time()

for strat in STRATEGIES:
    for rm in RECALL_MODES:
        key = f"{strat}__{rm}"
        print(f"\n--- {strat.upper()} / {rm} ---")
        data = []

        for K in MEMORY_SIZES:
            K_label = str(K)
            t0  = time.time()
            res = run_cost(strat, rm, K)
            dt  = time.time() - t0
            print(f"  K={K_label:>6s}: cov={res['coverage']:.3f}  "
                  f"disc={res['discoveries']:>6,}  budget={res['steps_budget']:>8,}  [{dt:.1f}s]")
            data.append({
                'memory_size':  K,
                'label':        K_label,
                'steps_budget': res['steps_budget'],
                'coverage':     res['coverage'],
                'discoveries':  res['discoveries'],
                'recalls':      res['recalls'],
            })

        all_results[key] = data

elapsed = time.time() - t_total
print(f"\nTotal time: {elapsed:.1f}s")

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

OUTPUT_JSON.parent.mkdir(exist_ok=True)
output = {
    'cost_model':        'cost_per_step = max(1, K)',
    'time_budget':       TIME_BUDGET,
    'step_budget_ref':   STEP_BUDGET,
    'norm_k':            NORM_K,
    'strategies':        STRATEGIES,
    'recall_modes':      RECALL_MODES,
    'memory_sizes':      MEMORY_SIZES,
    'total_theorems':    N,
    'root_count':        len(root_nodes),
    'baseline_coverage': baseline,
    'results':           all_results,
}

with open(OUTPUT_JSON, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nSaved -> {OUTPUT_JSON}")
print("Done!")
