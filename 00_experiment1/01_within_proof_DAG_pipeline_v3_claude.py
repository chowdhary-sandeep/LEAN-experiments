"""
Build proof DAGs from traced_theorems_unified_v2.jsonl.

Each proof is a sequence of tactic steps that transform proof states.
This visualizes the proof trajectory: state → tactic → new_state → ... → "no goals"

Inspired by 0_prooftrees.py but uses the unified v2 data format.
"""

import json
from pathlib import Path
from collections import defaultdict

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_FILE = SCRIPT_DIR / "jsons" / "traced_theorems_unified_v2.jsonl"
OUTPUT_HTML = SCRIPT_DIR / "01_within_proof_DAGs.html"


def load_theorems_with_proofs(jsonl_path, max_theorems=None):
    """
    Load theorems from JSONL, keeping only those with tactic proofs.

    Returns:
        list of theorem records with tactics
    """
    print(f"Loading theorems from {jsonl_path}...")
    theorems = []

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue

            try:
                thm = json.loads(line)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse line {line_num}")
                continue

            # Only keep theorems with tactic proofs
            if thm.get("proof_type") == "tactic" and thm.get("tactics"):
                theorems.append(thm)

            if max_theorems and len(theorems) >= max_theorems:
                break

    print(f"  Found {len(theorems):,} theorems with tactic proofs")
    return theorems


def build_proof_dag(theorem):
    """
    Build a DAG structure for a single proof.

    The proof is sequential: tactics[i].state_after ≈ tactics[i+1].state_before
    We reuse state nodes when they match to create a proper linear chain.

    Returns:
        dict with nodes and edges representing the proof trajectory
    """
    tactics = theorem.get("tactics", [])

    # Build nodes (proof states) - use hash of state string as ID to reuse matching states
    nodes = {}
    edges = []
    state_id_map = {}  # Map state string to node ID

    def get_or_create_state_node(state_str, context, tactic_idx, is_initial, is_terminal):
        """Get existing node ID for state, or create new one."""
        # Use hash of state string as stable ID (truncate for readability)
        state_hash = str(abs(hash(state_str)))[:8]

        if state_str in state_id_map:
            # State already exists - reuse it
            node_id = state_id_map[state_str]
            # Update terminal status if needed
            if is_terminal:
                nodes[node_id]["is_terminal"] = True
            return node_id

        # Create new node
        node_id = f"s{state_hash}"
        state_id_map[state_str] = node_id

        nodes[node_id] = {
            "id": node_id,
            "state": state_str[:500],  # Truncate for JSON size
            "goal": context.get("goal", "")[:300],  # Truncate goal too
            "num_hypotheses": len(context.get("hypotheses", {})),
            "num_variables": len(context.get("variables", {})),
            "is_initial": is_initial,
            "is_terminal": is_terminal,
            "tactic_index": tactic_idx
        }

        return node_id

    for i, tactic_record in enumerate(tactics):
        state_before = tactic_record.get("state_before", "")
        state_after = tactic_record.get("state_after", "")
        tactic_str = tactic_record.get("tactic", "")
        premises = tactic_record.get("premises", [])
        context = tactic_record.get("context", {})
        is_terminal = tactic_record.get("is_terminal", False)

        # Get or create state nodes
        state_before_id = get_or_create_state_node(
            state_before,
            context,
            i,
            is_initial=(i == 0),
            is_terminal=False
        )

        # Parse context for state_after (approximation - we don't have full context)
        after_context = {"goal": "", "hypotheses": {}, "variables": {}}
        state_after_id = get_or_create_state_node(
            state_after,
            after_context,
            i,
            is_initial=False,
            is_terminal=is_terminal
        )

        # Add edge (tactic step)
        edge = {
            "from": state_before_id,
            "to": state_after_id,
            "tactic": tactic_str[:200],  # Truncate tactic for JSON size
            "tactic_index": i,
            "premises": [p.get("full_name", "")[:100] for p in premises[:5]],  # Limit premises
            "num_goals_before": tactic_record.get("num_goals_before", 0),
            "num_goals_after": tactic_record.get("num_goals_after", 0)
        }
        edges.append(edge)

    return {
        "nodes": nodes,
        "edges": edges,
        "num_tactics": len(tactics)
    }


def select_interesting_theorems(theorems, count=20):
    """
    Select interesting theorems for visualization.

    Prioritize:
    - Medium length (5-30 tactics) for readability
    - Complete proofs (reaches "no goals")
    - Variety in complexity
    """
    # Filter complete proofs with reasonable length
    candidates = []
    for thm in theorems:
        num_tactics = thm.get("metrics", {}).get("num_tactics", 0)
        tactics = thm.get("tactics", [])

        # Check if proof is complete
        is_complete = False
        if tactics:
            last_tactic = tactics[-1]
            is_complete = last_tactic.get("is_terminal", False)

        if 5 <= num_tactics <= 30 and is_complete:
            candidates.append((thm, num_tactics))

    # Sort by length and take variety
    candidates.sort(key=lambda x: x[1])

    # Take samples across the range
    selected = []
    step = max(1, len(candidates) // count)
    for i in range(0, len(candidates), step):
        if len(selected) >= count:
            break
        selected.append(candidates[i][0])

    print(f"  Selected {len(selected)} theorems (from {len(candidates)} candidates)")
    return selected


def generate_html(theorems_with_dags, output_path):
    """
    Generate interactive HTML visualization of proof DAGs.

    Uses D3.js for force-directed graph layout.
    """
    html_template = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Proof DAGs - Within-Proof Trajectories</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            font-family: 'Courier New', monospace;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }}

        h1 {{
            text-align: center;
            margin-bottom: 10px;
        }}

        .subtitle {{
            text-align: center;
            color: #666;
            margin-bottom: 30px;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin: 0 auto;
            max-width: 2200px;
        }}

        .proof-card {{
            background: white;
            border: 2px solid #333;
            padding: 10px;
        }}

        .proof-header {{
            font-weight: bold;
            margin-bottom: 10px;
            padding: 5px;
            background: #eee;
            border-left: 4px solid #333;
            font-size: 12px;
            word-break: break-all;
        }}

        .proof-stats {{
            font-size: 11px;
            color: #666;
            margin-bottom: 10px;
        }}

        .proof-svg {{
            border: 1px solid #ddd;
        }}

        .node {{
            cursor: pointer;
        }}

        .node.initial {{
            stroke: #2ecc71;
            stroke-width: 3px;
        }}

        .node.terminal {{
            stroke: #e74c3c;
            stroke-width: 3px;
        }}

        .link {{
            stroke: #999;
            stroke-opacity: 0.6;
            stroke-width: 2px;
            fill: none;
        }}

        .link-label {{
            font-size: 9px;
            fill: #333;
            pointer-events: none;
        }}

        .node-label {{
            font-size: 10px;
            pointer-events: none;
            text-anchor: middle;
        }}

        .tooltip {{
            position: fixed;
            background: white;
            border: 2px solid #333;
            padding: 10px;
            font-size: 11px;
            max-width: 600px;
            max-height: 400px;
            overflow-y: auto;
            pointer-events: none;
            z-index: 1000;
            display: none;
        }}

        .tooltip-title {{
            font-weight: bold;
            margin-bottom: 5px;
            border-bottom: 1px solid #ddd;
            padding-bottom: 5px;
        }}

        .tooltip-section {{
            margin-top: 5px;
        }}

        .tooltip-label {{
            font-weight: bold;
            color: #666;
        }}

        .goal {{
            background: #fffacd;
            padding: 3px;
            margin-top: 3px;
            font-family: 'Courier New', monospace;
            font-size: 10px;
        }}

        .tactic {{
            background: #e8f4f8;
            padding: 3px;
            margin-top: 3px;
            font-family: 'Courier New', monospace;
            font-size: 10px;
        }}
    </style>
</head>
<body>
    <h1>Proof DAGs: Within-Proof State Trajectories</h1>
    <div class="subtitle">
        Each graph shows how tactics transform proof states until "no goals" is reached.
        <br>Green = initial state | Red = terminal state (proof complete)
    </div>

    <div class="grid" id="proof-grid"></div>
    <div class="tooltip" id="tooltip"></div>

    <script>
        const proofsData = {proofs_json};

        // Create visualization for each proof
        proofsData.forEach((proof, idx) => {{
            createProofGraph(proof, idx);
        }});

        function createProofGraph(proof, idx) {{
            const card = d3.select("#proof-grid")
                .append("div")
                .attr("class", "proof-card");

            // Header
            card.append("div")
                .attr("class", "proof-header")
                .text(proof.theorem_name);

            // Stats
            card.append("div")
                .attr("class", "proof-stats")
                .html(`
                    Tactics: ${{proof.num_tactics}} |
                    Premises: ${{proof.num_premises}} |
                    States: ${{Object.keys(proof.dag.nodes).length}}
                `);

            // SVG canvas
            const width = 480;
            const height = 400;

            const svg = card.append("svg")
                .attr("class", "proof-svg")
                .attr("width", width)
                .attr("height", height);

            // Prepare data for D3
            const nodes = Object.values(proof.dag.nodes).map(n => ({{
                ...n,
                x: Math.random() * width,
                y: Math.random() * height
            }}));

            const links = proof.dag.edges.map(e => ({{
                source: e.from,
                target: e.to,
                tactic: e.tactic,
                premises: e.premises,
                num_goals_before: e.num_goals_before,
                num_goals_after: e.num_goals_after
            }}));

            // Force simulation with left-to-right bias for sequential proofs
            const simulation = d3.forceSimulation(nodes)
                .force("link", d3.forceLink(links).id(d => d.id).distance(100))
                .force("charge", d3.forceManyBody().strength(-400))
                .force("center", d3.forceCenter(width / 2, height / 2))
                .force("collision", d3.forceCollide().radius(25))
                .force("x", d3.forceX().x(d => {{
                    // Position based on tactic index (left to right)
                    return 50 + (d.tactic_index / proof.num_tactics) * (width - 100);
                }}).strength(0.5));

            // Draw links
            const link = svg.append("g")
                .selectAll("line")
                .data(links)
                .join("line")
                .attr("class", "link")
                .attr("marker-end", "url(#arrowhead)");

            // Add arrowhead marker
            svg.append("defs").append("marker")
                .attr("id", "arrowhead")
                .attr("viewBox", "0 -5 10 10")
                .attr("refX", 20)
                .attr("refY", 0)
                .attr("markerWidth", 6)
                .attr("markerHeight", 6)
                .attr("orient", "auto")
                .append("path")
                .attr("d", "M0,-5L10,0L0,5")
                .attr("fill", "#999");

            // Draw nodes
            const node = svg.append("g")
                .selectAll("circle")
                .data(nodes)
                .join("circle")
                .attr("class", d => {{
                    let cls = "node";
                    if (d.is_initial) cls += " initial";
                    if (d.is_terminal) cls += " terminal";
                    return cls;
                }})
                .attr("r", 10)
                .attr("fill", d => d.is_terminal ? "#e74c3c" : (d.is_initial ? "#2ecc71" : "#3498db"))
                .call(drag(simulation))
                .on("mouseover", showTooltip)
                .on("mouseout", hideTooltip);

            // Node labels (state number based on position)
            const nodeLabel = svg.append("g")
                .selectAll("text")
                .data(nodes)
                .join("text")
                .attr("class", "node-label")
                .text((d, i) => i)  // Use sequential index instead of tactic index
                .attr("dy", 4);

            // Update positions on simulation tick
            simulation.on("tick", () => {{
                link
                    .attr("x1", d => d.source.x)
                    .attr("y1", d => d.source.y)
                    .attr("x2", d => d.target.x)
                    .attr("y2", d => d.target.y);

                node
                    .attr("cx", d => d.x)
                    .attr("cy", d => d.y);

                nodeLabel
                    .attr("x", d => d.x)
                    .attr("y", d => d.y);
            }});

            function showTooltip(event, d) {{
                const tooltip = d3.select("#tooltip");

                // Find the edge that starts from this node
                const outEdge = links.find(e => e.source.id === d.id || e.source === d.id);

                let html = `<div class="tooltip-title">State ${{d.tactic_index}}</div>`;

                if (d.goal) {{
                    html += `<div class="tooltip-section">
                        <span class="tooltip-label">Goal:</span>
                        <div class="goal">${{d.goal.substring(0, 200)}}${{d.goal.length > 200 ? '...' : ''}}</div>
                    </div>`;
                }}

                html += `<div class="tooltip-section">
                    <span class="tooltip-label">Context:</span>
                    ${{d.num_hypotheses}} hypotheses, ${{d.num_variables}} variables
                </div>`;

                if (outEdge) {{
                    html += `<div class="tooltip-section">
                        <span class="tooltip-label">Next Tactic:</span>
                        <div class="tactic">${{outEdge.tactic.substring(0, 200)}}${{outEdge.tactic.length > 200 ? '...' : ''}}</div>
                    </div>`;

                    if (outEdge.premises && outEdge.premises.length > 0) {{
                        html += `<div class="tooltip-section">
                            <span class="tooltip-label">Premises used:</span> ${{outEdge.premises.slice(0, 3).join(", ")}}
                            ${{outEdge.premises.length > 3 ? `... (+${{outEdge.premises.length - 3}} more)` : ''}}
                        </div>`;
                    }}
                }}

                if (d.is_terminal) {{
                    html += `<div class="tooltip-section" style="color: #e74c3c; font-weight: bold;">
                        ✓ Proof complete (no goals)
                    </div>`;
                }}

                tooltip
                    .html(html)
                    .style("display", "block")
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY + 10) + "px");
            }}

            function hideTooltip() {{
                d3.select("#tooltip").style("display", "none");
            }}
        }}

        function drag(simulation) {{
            function dragstarted(event) {{
                if (!event.active) simulation.alphaTarget(0.3).restart();
                event.subject.fx = event.subject.x;
                event.subject.fy = event.subject.y;
            }}

            function dragged(event) {{
                event.subject.fx = event.x;
                event.subject.fy = event.y;
            }}

            function dragended(event) {{
                if (!event.active) simulation.alphaTarget(0);
                event.subject.fx = null;
                event.subject.fy = null;
            }}

            return d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended);
        }}
    </script>
</body>
</html>"""

    # Prepare data for JSON embedding
    proofs_for_json = []
    for thm, dag in theorems_with_dags:
        proof_data = {
            "theorem_name": thm.get("full_name", "Unknown"),
            "num_tactics": dag["num_tactics"],
            "num_premises": thm.get("metrics", {}).get("num_premises", 0),
            "dag": dag
        }
        proofs_for_json.append(proof_data)

    # Generate HTML
    html_content = html_template.format(
        proofs_json=json.dumps(proofs_for_json, ensure_ascii=False)
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"HTML visualization saved to: {output_path}")


def main():
    """Main function to build proof DAGs and generate HTML."""
    print("="*70)
    print("BUILDING WITHIN-PROOF DAGs")
    print("="*70)

    # Load theorems
    theorems = load_theorems_with_proofs(DATA_FILE, max_theorems=1000)

    if not theorems:
        print("No theorems with tactic proofs found!")
        return

    # Select interesting subset
    selected = select_interesting_theorems(theorems, count=20)

    # Build DAGs
    print(f"\nBuilding proof DAGs...")
    theorems_with_dags = []
    for thm in selected:
        dag = build_proof_dag(thm)
        theorems_with_dags.append((thm, dag))

        # Diagnostic: show first few
        if len(theorems_with_dags) <= 3:
            print(f"  {thm['full_name'][:50]}: {dag['num_tactics']} tactics -> {len(dag['nodes'])} states")

    print(f"  Built {len(theorems_with_dags)} proof DAGs")

    # Generate HTML
    print(f"\nGenerating HTML visualization...")
    generate_html(theorems_with_dags, OUTPUT_HTML)

    print(f"\n{'='*70}")
    print("DONE!")
    print(f"Open {OUTPUT_HTML} in your browser to view the proof DAGs.")
    print("="*70)


if __name__ == "__main__":
    main()
