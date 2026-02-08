# Animation Plan: Agent Traversing Theorem Space

## Concept
Agent explores theorem-theorem network from roots, revealing downstream possibilities as it moves. Downstream nodes appear faintly when agent arrives, solidify when agent "proves" them via tactics on edges.

## Visual Aesthetics (Minimal & Beautiful)
- **Base:** vis-network, minimal UI
- **Background:** White
- **Color Palette:**
  - Agent location: Pulsing circle (black)
  - Visited nodes: Solid black
  - Faint ghosts (adjacent possible): Light gray (opacity 0.3)
  - Edges with tactics: Thin lines, appear on traversal
  - Text annotations: Small, elegant monospace

## Starting Point
- Begin at a **root node** (in-degree 0) in theorem-theorem network
- Select root with interesting downstream structure (20-50 reachable theorems)

## Animation Flow

**Step 1:** Agent at root node
- Root node solidifies (black)
- Immediate downstream nodes become faintly visible (gray ghosts)
- Annotation: "Starting from [theorem name]"

**Step 2-N:** Agent moves
1. Agent selects an adjacent possible ghost
2. Edge appears with tactic label (small text on edge)
3. Agent moves along edge (animated)
4. Target node solidifies (gray → black)
5. New downstream ghosts appear from this node
6. Annotation updates: "Discovered [theorem name] using [tactic]"

**Repeat** until exploration complete or depth limit

## Technical
- **Output:** Single HTML file, self-contained
- **Controls:** Play/pause, speed (1x, 2x, 4x), reset
- **Duration:** 1-2 seconds per discovery
- **Visual transitions:** Smooth fade-in/out (300-500ms)
- **Annotations:** Top-right corner, fade on update

## Data Sources

### Primary Data
**File:** `cache/bundle.pkl`
- **Load:** `bundle["G_original"]` - NetworkX DiGraph
- **Nodes:** All theorems (99,412 nodes)
- **Edges:** A→B means "B uses A in its proof"

### What to Extract
1. **Root nodes:** Theorems with `in_degree(node) == 0` (48,081 roots)
2. **Select example root:** Pick root with:
   - Out-degree (successors) between 20-50
   - Reachable descendants ~30-60 (via BFS)
   - Filter: `node_type == "theorem"` if attribute exists

3. **For each node:**
   - Node ID: Theorem full name (e.g., `"Nat.add_comm"`)
   - Label: Shortened name (last component after final `.`)

4. **For each edge:**
   - Source/target theorem names
   - "Tactic" label: Use source theorem name (simplified - actual tactics not in this data)

### Traversal Strategy
- **BFS from selected root:** Guarantees prerequisites met before discovery
- **Order:** Level-by-level (all depth-N before depth-N+1)
- **Limit:** Stop at depth 3-4 or 50 nodes total (whichever first)
