"""
Cross-Recall Experiment (experiment3)

Recall strategy decoupled from exploration strategy.
Answers: does unblock recall help BFS/DFS/random as much as greedy?

Exploration strategies : bfs, dfs, random, greedy  (4)
Recall modes           : none, fifo, lifo, random_recall, unblock, hub_local  (6)
K values               : 1k, 5k, 10k, 30k, 50k  (5)
Budget                 : 60k (single, to keep runtime manageable)

Total runs: 4 × 6 × 5 = 120
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
OUTPUT_JSON  = SCRIPT_DIR / "data" / "experiment3_cross_recall_results.json"

print("=" * 80)
print("CROSS-RECALL: 4 strategies × 6 recall modes × 5 K values")
print("=" * 80)


# -- IndexedSet ----------------------------------------------------------------

class IndexedSet:
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


# -- Load & cache --------------------------------------------------------------

print("\nLoading cache...")
with open(CACHE_BUNDLE, "rb") as f:
    bundle = pickle.load(f)

G = bundle["G_original"]
del bundle

all_theorems  = set(G.nodes())
root_nodes    = sorted([n for n in all_theorems if G.in_degree(n) == 0])
N             = len(all_theorems)
print(f"  {N:,} theorems, {len(root_nodes):,} roots")

print("Pre-caching...")
succ_cache    = {n: tuple(G.successors(n)) for n in all_theorems}
total_prereqs = {n: G.in_degree(n) for n in all_theorems}
# NOTE: succ_cache is global knowledge (known limitation — see fix.md)

del G
gc.collect()
print("  Done.")


# -- MemoryDiscovery -----------------------------------------------------------

class MemoryDiscovery:
    def __init__(self, mem_size):
        self.mem_size = mem_size

    def initialize(self):
        self.discovered = set(root_nodes)
        mem_list        = root_nodes[:] if self.mem_size >= len(root_nodes) \
                          else root_nodes[-self.mem_size:]
        self.memory     = deque(mem_list)
        self.mem_set    = set(mem_list)
        self.recallable = IndexedSet(self.discovered - self.mem_set)
        self.prereqs_in_mem = {}
        self.adjacent   = set()

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


# -- Unified recall selector (Change 3: standalone modes) ----------------------

MAX_CONSECUTIVE_RECALLS = 200
SAMPLE_N = 30   # candidates for unblock / hub_local
FIFO_SAMPLE = 150  # larger sample for fifo/lifo to get better ordering


def select_recall(recall_mode, md, discovery_order):
    """
    Recall modes (all decoupled from exploration strategy):
      fifo          – recall oldest discovered theorem (approx via sampling)
      lifo          – recall newest discovered theorem (approx via sampling)
      random_recall – recall uniformly random evicted theorem
      unblock       – recall theorem that unblocks most frontier entries
      hub_local     – recall theorem with highest local out-degree (discovered+adjacent)
    """
    if not md.recallable:
        return None

    if recall_mode == 'fifo':
        cands = md.recallable.sample(min(FIFO_SAMPLE, len(md.recallable)))
        return min(cands, key=lambda t: discovery_order.get(t, float('inf')))

    if recall_mode == 'lifo':
        cands = md.recallable.sample(min(FIFO_SAMPLE, len(md.recallable)))
        return max(cands, key=lambda t: discovery_order.get(t, 0))

    if recall_mode == 'random_recall':
        s = md.recallable.sample(1)
        return s[0] if s else None

    if recall_mode == 'unblock':
        # locally optimal: unblock as many frontier entries as possible
        sample   = md.recallable.sample(SAMPLE_N)
        best, bg = None, -1
        for c in sample:
            g = sum(1 for s in succ_cache[c]
                    if s not in md.discovered
                    and md.prereqs_in_mem.get(s, 0) + 1 == total_prereqs[s])
            if g > bg:
                bg, best = g, c
        return best

    if recall_mode == 'hub_local':
        sample = md.recallable.sample(SAMPLE_N)
        return max(sample, key=lambda c: sum(
            1 for s in succ_cache[c]
            if s in md.discovered or s in md.adjacent))

    return None  # 'none'


# -- Main run function ---------------------------------------------------------

def run(strategy, recall_mode, mem_size, budget, seed=42):
    rng.seed(seed)
    md = MemoryDiscovery(mem_size)
    md.initialize()

    discovery_order = {ax: i for i, ax in enumerate(root_nodes)}
    disc_seq        = len(root_nodes)

    # Exploration heap (BFS/DFS only)
    disc_heap    = []
    disc_counter = 0
    disc_sign    = 1 if strategy == 'bfs' else -1

    if strategy in ('bfs', 'dfs'):
        for thm in sorted(md.adjacent):
            heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
            disc_counter += 1

    discovery_count    = 0
    recall_count       = 0
    consecutive_recalls = 0

    coverage_at_budget = {}

    for step in range(budget + 1):
        if step == budget:
            coverage_at_budget[budget] = {
                'coverage': len(md.discovered) / N,
                'discoveries': discovery_count,
                'recalls': recall_count,
            }
            break

        # -- Explore -----------------------------------------------------------
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
                chosen = next(iter(md.adjacent))

            elif strategy == 'greedy':
                cands       = rng.sample(list(md.adjacent), min(50, len(md.adjacent)))
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

            newly, _ = md.discover(chosen)
            discovery_order[chosen] = disc_seq
            disc_seq        += 1
            discovery_count += 1
            consecutive_recalls = 0

            if strategy in ('bfs', 'dfs'):
                for thm in sorted(newly):
                    heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
                    disc_counter += 1

        # -- Recall (when frontier empty) --------------------------------------
        elif recall_mode != 'none':
            if consecutive_recalls >= MAX_CONSECUTIVE_RECALLS:
                break

            recall_thm = select_recall(recall_mode, md, discovery_order)
            if recall_thm is None:
                break

            newly, _ = md.recall(recall_thm)
            recall_count        += 1
            consecutive_recalls += 1

            if strategy in ('bfs', 'dfs'):
                for thm in sorted(newly):
                    heapq.heappush(disc_heap, (disc_sign * disc_counter, thm))
                    disc_counter += 1
        else:
            break

    final = {'coverage': len(md.discovered) / N,
             'discoveries': discovery_count, 'recalls': recall_count}
    coverage_at_budget.setdefault(budget, final)
    return coverage_at_budget[budget]


# -- Configuration -------------------------------------------------------------

STRATEGIES   = ['bfs', 'dfs', 'random', 'greedy']
RECALL_MODES = ['none', 'fifo', 'lifo', 'random_recall', 'unblock', 'hub_local']
K_VALUES     = [1000, 5000, 10000, 30000, 50000]
BUDGET       = 60000

# -- Run -----------------------------------------------------------------------

all_results = {}
t_total     = time.time()

for strat in STRATEGIES:
    for rm in RECALL_MODES:
        key = f"{strat}__{rm}"
        print(f"\n--- {strat.upper()} / {rm} ---")
        row = []
        for K in K_VALUES:
            t0  = time.time()
            res = run(strat, rm, K, BUDGET)
            dt  = time.time() - t0
            print(f"  K={K:>6,}: cov={res['coverage']:.3f}  "
                  f"disc={res['discoveries']:>5,}  rec={res['recalls']:>5,}  [{dt:.1f}s]")
            row.append({'K': K, **res})
        all_results[key] = row

elapsed = time.time() - t_total
print(f"\nTotal time: {elapsed:.1f}s")

# -- Save ----------------------------------------------------------------------

(SCRIPT_DIR / "data").mkdir(exist_ok=True)

output = {
    'strategies':   STRATEGIES,
    'recall_modes': RECALL_MODES,
    'K_values':     K_VALUES,
    'budget':       BUDGET,
    'total_theorems': N,
    'root_count':   len(root_nodes),
    'baseline_coverage': len(root_nodes) / N,
    'recall_mode_descriptions': {
        'none':         'No recall — agent stops when frontier empties',
        'fifo':         'Recall oldest discovered theorem (approx FIFO over evicted set)',
        'lifo':         'Recall newest discovered theorem (approx LIFO over evicted set)',
        'random_recall':'Recall uniformly random evicted theorem',
        'unblock':      'Recall theorem that unblocks most adjacent-possible entries (locally optimal)',
        'hub_local':    'Recall highest local out-degree theorem (visible subgraph only)',
    },
    'results': all_results,
}

with open(OUTPUT_JSON, 'w') as f:
    json.dump(output, f, indent=2)

print(f"\nSaved: {OUTPUT_JSON}")
print("Done!")
