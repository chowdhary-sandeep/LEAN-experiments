"""
Phase Transition Analysis with Recall Mechanisms

Strategies: BFS (FIFO), DFS (LIFO), Random, Greedy
Recall modes:
  - none:    Agent stops when A_t empties
  - matched: Strategy-specific recall (BFS=oldest, DFS=newest, Random=random, Greedy=max-unblock)
  - hub:     Universal structural recall (highest out-degree not in memory)

OPTIMIZED v2: Freed graph after caching, IndexedSet for O(1) recall sampling,
              flipped init loop (iterate mem_set successors not all theorems).
"""

import json
import pickle
import random as rng
import heapq
import time
import gc
from pathlib import Path
from collections import deque

SCRIPT_DIR = Path(__file__).resolve().parent
CACHE_BUNDLE = SCRIPT_DIR / "cache" / "bundle.pkl"
OUTPUT_JSON = SCRIPT_DIR / "experiment2_phase_transition_results.json"

print("=" * 80)
print("PHASE TRANSITION: Coverage vs Memory x Strategy x Recall Mode")
print("=" * 80)


# -- IndexedSet: O(1) add/discard/contains, O(k) random sampling ---------------

class IndexedSet:
    """Set with O(1) add/discard/contains and O(k) random sampling."""
    __slots__ = ('_items', '_pos')

    def __init__(self, iterable=()):
        self._items = list(iterable)
        self._pos = {item: i for i, item in enumerate(self._items)}

    def add(self, item):
        if item not in self._pos:
            self._pos[item] = len(self._items)
            self._items.append(item)

    def discard(self, item):
        if item in self._pos:
            idx = self._pos.pop(item)
            last = self._items[-1]
            if idx < len(self._items) - 1:
                self._items[idx] = last
                self._pos[last] = idx
            self._items.pop()

    def sample(self, k):
        k = min(k, len(self._items))
        if k <= 0:
            return []
        return rng.sample(self._items, k)

    def __contains__(self, item):
        return item in self._pos

    def __len__(self):
        return len(self._items)

    def __bool__(self):
        return bool(self._items)

    def __iter__(self):
        return iter(self._items)


# -- Load & pre-cache (then free the heavy graph) ------------------------------

print("\nLoading...")
with open(CACHE_BUNDLE, "rb") as f:
    bundle = pickle.load(f)

G = bundle["G_original"]
del bundle  # free immediately

all_theorems = set(G.nodes())
root_nodes = sorted([n for n in all_theorems if G.in_degree(n) == 0])
N = len(all_theorems)
print(f"  {N:,} theorems, {len(root_nodes):,} roots, baseline={len(root_nodes)/N:.3f}")

print("Pre-caching into compact structures...")
succ_cache   = {n: tuple(G.successors(n)) for n in all_theorems}  # tuples < lists
total_prereqs = {n: G.in_degree(n) for n in all_theorems}
out_degree    = {n: G.out_degree(n) for n in all_theorems}

# Free the NetworkX graph (~1-2 GB)
del G
gc.collect()
print("  Done (graph freed from RAM).")


# -- Memory-Constrained Discovery Engine (optimized) ---------------------------

class MemoryDiscovery:
    def __init__(self, mem_size):
        self.mem_size = mem_size

    def initialize(self):
        self.discovered = set(root_nodes)
        mem_list = root_nodes[:] if self.mem_size >= len(root_nodes) else root_nodes[-self.mem_size:]
        self.memory = deque(mem_list)
        self.mem_set = set(mem_list)
        self.recallable = IndexedSet(self.discovered - self.mem_set)
        self.prereqs_in_mem = {}
        self.adjacent = set()

        # FLIPPED: iterate mem_set successors, not all 99k theorems
        for node in self.mem_set:
            for s in succ_cache[node]:
                if s not in self.discovered:
                    self.prereqs_in_mem[s] = self.prereqs_in_mem.get(s, 0) + 1

        for thm, met in self.prereqs_in_mem.items():
            if met == total_prereqs[thm] and total_prereqs[thm] > 0:
                self.adjacent.add(thm)

    def _update_memory(self, theorem):
        """Add theorem to memory, handle eviction."""
        newly = set()
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


# -- Heap-based recall selection ------------------------------------------------

MAX_CONSECUTIVE_RECALLS = 200


def make_recall_priority(strategy, recall_mode, discovery_order):
    if recall_mode == 'hub':
        return lambda thm: -out_degree.get(thm, 0)
    if strategy == 'bfs':
        return lambda thm: discovery_order.get(thm, float('inf'))
    elif strategy == 'dfs':
        return lambda thm: -discovery_order.get(thm, 0)
    return lambda thm: rng.random()


def run(strategy, recall_mode, mem_size, max_budget, checkpoints, seed=42):
    rng.seed(seed)
    md = MemoryDiscovery(mem_size)
    md.initialize()

    discovery_order = {ax: i for i, ax in enumerate(root_nodes)}
    disc_seq = len(root_nodes)

    disc_heap = []
    disc_counter = 0
    disc_sign = 1 if strategy == 'bfs' else -1

    if strategy in ('bfs', 'dfs'):
        for thm in sorted(md.adjacent):
            heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
            disc_counter += 1

    recall_heap = []
    recall_counter = 0
    use_recall_heap = recall_mode != 'none' and strategy != 'greedy'
    pri_fn = make_recall_priority(strategy, recall_mode, discovery_order) if recall_mode != 'none' else None

    if use_recall_heap and md.recallable:
        for thm in md.recallable:
            heapq.heappush(recall_heap, (pri_fn(thm), recall_counter, thm))
            recall_counter += 1

    results = {}
    discovery_count = 0
    recall_count = 0
    consecutive_recalls = 0

    def push_recall(thm):
        nonlocal recall_counter
        if use_recall_heap:
            heapq.heappush(recall_heap, (pri_fn(thm), recall_counter, thm))
            recall_counter += 1

    def pop_recall():
        while recall_heap:
            _, _, thm = heapq.heappop(recall_heap)
            if thm in md.recallable:
                return thm
        return None

    def select_recall_greedy():
        if not md.recallable:
            return None
        sample = md.recallable.sample(30)  # O(k) via IndexedSet
        if recall_mode == 'hub':
            return max(sample, key=lambda c: out_degree.get(c, 0))
        best, best_g = None, -1
        for c in sample:
            g = sum(1 for s in succ_cache[c]
                    if s not in md.discovered
                    and md.prereqs_in_mem.get(s, 0) + 1 == total_prereqs[s])
            if g > best_g:
                best_g, best = g, c
        return best

    for step in range(max_budget):
        if step in checkpoints:
            results[step] = {
                'coverage': len(md.discovered) / N,
                'discoveries': discovery_count,
                'recalls': recall_count,
            }

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
                chosen = md.adjacent.pop()   # O(1) from set
                md.adjacent.add(chosen)      # put it back; discover() will remove
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

            if chosen is None:
                break

            newly, evicted = md.discover(chosen)
            discovery_order[chosen] = disc_seq
            disc_seq += 1
            discovery_count += 1
            consecutive_recalls = 0

            if strategy in ('bfs', 'dfs'):
                for thm in sorted(newly):
                    heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
                    disc_counter += 1

            if evicted and evicted in md.recallable:
                push_recall(evicted)

        elif recall_mode != 'none':
            if consecutive_recalls >= MAX_CONSECUTIVE_RECALLS:
                break

            if strategy == 'greedy' or not use_recall_heap:
                recall_thm = select_recall_greedy()
            else:
                recall_thm = pop_recall()

            if recall_thm is None:
                break

            newly, evicted = md.recall(recall_thm)
            recall_count += 1
            consecutive_recalls += 1

            if strategy in ('bfs', 'dfs'):
                for thm in sorted(newly):
                    heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
                    disc_counter += 1

            if evicted and evicted in md.recallable:
                push_recall(evicted)
        else:
            break

    final = {
        'coverage': len(md.discovered) / N,
        'discoveries': discovery_count,
        'recalls': recall_count,
    }
    for cp in checkpoints:
        if cp not in results:
            results[cp] = final

    return results


# -- Configuration --------------------------------------------------------------

MEMORY_SIZES = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 30000,
                40000, 50000, 75000, 100000, 200000, 500000, 999999]
STRATEGIES = ['bfs', 'dfs', 'random', 'greedy']
RECALL_MODES = ['none', 'matched', 'hub']
BUDGETS = [1000, 5000, 20000, 60000]
CHECKPOINTS = set(BUDGETS)
MAX_BUDGET = max(BUDGETS)


# -- Run ------------------------------------------------------------------------

all_results = {}
t_total = time.time()

for strat in STRATEGIES:
    for rm in RECALL_MODES:
        key = f"{strat}__{rm}"
        print(f"\n--- {strat.upper()} / {rm} ---")
        data = []

        for K in MEMORY_SIZES:
            K_label = 'inf' if K == 999999 else str(K)
            t0 = time.time()
            res = run(strat, rm, K, MAX_BUDGET, CHECKPOINTS)
            dt = time.time() - t0
            final = res.get(MAX_BUDGET, {})
            cov  = final.get('coverage', 0)
            disc = final.get('discoveries', 0)
            rec  = final.get('recalls', 0)
            print(f"  K={K_label:>6s}: cov={cov:.3f}  disc={disc:>5,}  rec={rec:>5,}  [{dt:.1f}s]")

            data.append({
                'memory_size': K,
                'label': K_label,
                'by_budget': {str(b): res.get(b, {}) for b in BUDGETS},
            })

        all_results[key] = data

elapsed = time.time() - t_total
print(f"\nTotal time: {elapsed:.1f}s")

# -- Save ----------------------------------------------------------------------

output = {
    'strategies': STRATEGIES,
    'recall_modes': RECALL_MODES,
    'memory_sizes': MEMORY_SIZES,
    'budgets': BUDGETS,
    'total_theorems': N,
    'root_count': len(root_nodes),
    'baseline_coverage': len(root_nodes) / N,
    'results': all_results,
}

with open(OUTPUT_JSON, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nSaved to {OUTPUT_JSON}")
print("Done!")
