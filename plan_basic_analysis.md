# Plan: Basic Analysis - 4x4 Grid HTML Visualization

## Data Structure: tripartite_edges.jsonl

Each line in `tripartite_edges.jsonl` is a JSON object with the following structure:

```json
{
  "theorem": "FreeMagma.hom_ext",
  "file": "Mathlib\\Algebra\\Free.lean",
  "tactic": "intros",
  "annotated_tactic": "intros",
  "premises": [],
  "state_before": "α : Type u\nβ : Type v\n...",
  "state_after": "α : Type u\nβ : Type v\n..."
}
```

**Fields:**
- `theorem`: Full name of the theorem (string)
- `file`: Path to the Lean file containing the theorem (string)
- `tactic`: The tactic applied (string)
- `annotated_tactic`: Annotated version of the tactic (string)
- `premises`: List of premises/lemmas used (list, can be empty)
- `state_before`: Proof state before applying the tactic (string, can contain Unicode math symbols)
- `state_after`: Proof state after applying the tactic (string, or "no goals" if proof complete)

**Data Characteristics:**
- Multiple edges per theorem (one per tactic application)
- Edges are grouped by theorem name
- States represent intermediate proof states in Lean
- Premises can be empty or contain lemma references

## 4x4 Grid Layout

### Row 1: Exploring tripartite_edges.jsonl Data

**Panel 1.1: Data Overview**
- Total number of edges
- Number of unique theorems
- Number of unique tactics
- Number of unique files
- Distribution summary statistics

**Panel 1.2: Theorem Distribution**
- Histogram of proof lengths (number of tactics per theorem)
- Statistics: mean, median, max, min proof lengths
- Cumulative distribution

**Panel 1.3: File Distribution**
- Bar chart or treemap showing theorems per file
- Top N files by theorem count
- File path hierarchy visualization

**Panel 1.4: Edge Flow Overview**
- Network diagram showing theorem → tactic → premise relationships
- Node sizes proportional to frequency
- Edge weights showing connection strength

### Row 2: Proof Tree Measurements

**Panel 2.1: Tree Depth Distribution**
- Histogram of proof tree depths
- Correlation between proof length and tree depth
- Statistics: mean, median, max depth

**Panel 2.2: Tree Width Analysis**
- Max width distribution
- Width at half-depth analysis
- Tree shape classification (wide vs. deep)

**Panel 2.3: Node Degree Analysis**
- Average out-degree distribution
- Percentage of leaves (terminal nodes)
- Branching factor statistics

**Panel 2.4: Tree Structure Metrics**
- Spine score distribution (longest path / total nodes)
- Imbalance score (variance in out-degrees)
- Scatter plot: depth vs. width
- Tree shape categories visualization

### Row 3: Tactics Analysis

**Panel 3.1: Most Common Tactics**
- Bar chart of top N most frequently used tactics
- Frequency distribution
- Cumulative percentage

**Panel 3.2: Tactic Sequences**
- Most common tactic pairs (bigrams)
- Transition matrix visualization
- Common proof patterns

**Panel 3.3: Tactic Effectiveness**
- Average proof length by starting tactic
- Success rate analysis (tactics that lead to "no goals")
- Tactic usage by proof complexity

**Panel 3.4: Tactic Diversity**
- Number of unique tactics per theorem
- Tactic reuse patterns
- Tactic specialization (tactics used in few vs. many theorems)

### Row 4: Complexity Patterns

**Panel 4.1: Complexity Correlations**
- Scatter plot matrix of tree metrics
- Correlation heatmap between: depth, width, nodes, edges, spine_score, imbalance
- Principal component analysis visualization

**Panel 4.2: Complexity Clusters**
- K-means clustering of theorems by complexity metrics
- Cluster visualization (2D projection)
- Cluster characteristics summary

**Panel 4.3: Complexity Over Time/File**
- Average complexity by file
- Complexity trends (if file ordering available)
- File complexity distribution

**Panel 4.4: Complexity Outliers**
- Identification of unusually complex/simple proofs
- Outlier analysis (Z-scores)
- Examples of extreme cases with theorem names

## Implementation Details

### Data Processing
1. Load `tripartite_edges.jsonl` using `load_theorem_edges()` from `0_prooftrees.py`
2. Build proof trees using `build_proof_trees()` from `0_prooftrees.py` (no tree visualization, just structure)
3. Compute tree metrics using logic similar to `compute_tree_metrics()` from `visualize_proof_tree.py`
4. Aggregate statistics for all panels

### Visualization Requirements
- **Aesthetics**: Black and white only (grayscale acceptable)
- **Interactivity**: 
  - Hover tooltips with detailed information
  - Click to filter/explore
  - Zoom/pan for large visualizations
- **Layout**: 4x4 grid, responsive design
- **Technology**: HTML/CSS/JavaScript with D3.js or Plotly.js for charts

### Output
- Single HTML file: `basic_analysis.html`
- Self-contained (all data embedded or loaded from JSON)
- No external dependencies (CDN for libraries is acceptable)

## Files to Create/Modify

1. **New file**: `basic_analysis.py` - Main script to generate the HTML
   - Load and process data
   - Compute all statistics
   - Generate HTML with embedded visualizations

2. **New file**: `basic_analysis.html` - Output visualization (generated by script)

3. **Reuse**: 
   - `0_prooftrees.py` - Functions: `load_theorem_edges()`, `build_proof_trees()`
   - `visualize_proof_tree.py` - Function: `compute_tree_metrics()` (may need to adapt)

## Metrics to Compute

### From Proof Trees:
- Depth (max depth)
- Median depth
- Max width
- Width at half-depth
- Average out-degree
- Percentage of leaves
- Spine score (longest path / total nodes)
- Imbalance (variance in out-degrees)

### From Raw Edges:
- Proof length (edges per theorem)
- Tactic frequencies
- Premise frequencies
- File distributions
- State transition patterns
