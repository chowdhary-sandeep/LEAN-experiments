# Animation Plan: Agent Traversing Theorem Space (High Aesthetics)

## Concept
Agent explores theorem-theorem network via **DFS**, revealing the "adjacent possible" as faint ghosts. When agent commits to a path, unchosen possibilities fade away, new ones emerge.

## Visual Aesthetics (Cinematic & Artistic)
- **Background:** Pure white or subtle gradient
- **Color Palette:**
  - Agent location: Glowing circle (deep black → red pulse)
  - Visited nodes: Solid black circles (elegant)
  - Proven edges: Curved Bézier curves, black, slowly draw from tail→tip
  - Adjacent possible nodes: Faint gray (opacity 0.2-0.3)
  - Adjacent possible edges: Faint gray curves (opacity 0.15), dashed
  - Labels: Clean sans-serif, small, fade in with nodes

## Edge Animation (Critical!)
- **Curved edges:** Bézier curves with gentle arcs
- **Draw-in effect:** Animate from source→target over 0.5-1.0 seconds
  - Use path clipping or progressive point drawing
  - Smooth, cinematic feel
- **No instant edges:** Everything appears gradually

## Starting Point
- Begin at a **root node** (in-degree 0)
- Select root with depth-rich structure (DFS depth 5-8, ~40-80 nodes reachable)

## Animation Flow (DFS-based)

**Step 1:** Agent at root
- Root node fades in (0.3s)
- Adjacent possible: immediate successors appear faintly
- Adjacent edges: faint curved lines to ghosts
- Pause (1s) for viewer to see possibilities

**Step 2-N:** Agent moves (DFS)
1. Agent selects ONE adjacent possible (DFS priority: deepest unexplored)
2. **Unchosen ghosts fade out** (0.5s) - the paths not taken vanish
3. **Chosen edge draws in** (tail→tip, curved, 0.8s)
4. Agent glides along edge to target (0.5s)
5. Target node solidifies (ghost → black, 0.3s)
6. **NEW adjacent possibles appear** from current node (0.5s fade-in)
7. Pause (0.5s)
8. If at leaf or depth limit, backtrack to last node with unexplored successors

**Backtracking (DFS):**
- When leaf reached, agent quickly fades back to parent (0.3s)
- Continue DFS from next unexplored branch

**Repeat** until depth limit or node count reached

## Technical Specs
- **Output:** MP4 video (1920×1080, 30fps)
- **Duration:** 30-60 seconds
- **Per-step timing:**
  - Edge draw: 0.8s
  - Agent move: 0.5s
  - Fade transitions: 0.3-0.5s
  - Pauses: 0.5-1.0s
- **Total nodes:** ~30-50 (quality over quantity)
- **DFS depth:** 5-8 levels

## Data Sources

### Primary Data
**File:** `cache/bundle.pkl`
- **Load:** `bundle["G_original"]` - NetworkX DiGraph
- **Nodes:** All theorems (99,412 nodes)
- **Edges:** A→B means "B uses A in its proof"

### What to Extract
1. **Root nodes:** `in_degree == 0` (48,081 roots)
2. **Select root:** Pick root with:
   - DFS reachable depth ≥ 6
   - Total reachable descendants: 50-150
   - Interesting branching structure (not too linear)

3. **Node rendering:**
   - Full name: `"PowerSeries.order"` (for internal use)
   - Display label: Last component (`"order"`)

### Traversal Strategy
- **DFS from root:** Depth-first with backtracking
- **Depth limit:** 6-8 levels
- **Node limit:** 40-60 total nodes visited
- **Branch selection:** Always pick first unvisited successor (deterministic)
