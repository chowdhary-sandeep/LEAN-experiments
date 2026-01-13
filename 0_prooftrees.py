"""
Load tripartite_edges.jsonl, compute proof trees, and generate HTML visualization.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

# Import visualization function
if 'visualize_proof_tree' in sys.modules:
    del sys.modules['visualize_proof_tree']

from visualize_proof_tree import visualize_proof_trees_grid

# Configuration
OUT_JSONL = "tripartite_edges.jsonl"
OUTPUT_JSON = "top_50_proof_trees.json"
OUTPUT_HTML = "proof_trees_grid.html"

def load_theorem_edges(jsonl_path):
    """Load edges from JSONL file and group by theorem."""
    print(f"Loading edges from {jsonl_path}...")
    edges = []
    
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            edges.append(json.loads(line))
    
    # Group edges by theorem
    theorem_edges = defaultdict(list)
    for e in edges:
        theorem_edges[e["theorem"]].append(e)
    
    # Sort edges for each theorem by state_before length (to maintain order)
    for thm in theorem_edges:
        theorem_edges[thm].sort(key=lambda x: len(x.get("state_before", "")))
    
    print(f"Found {len(theorem_edges)} unique theorems with recorded tactics")
    return theorem_edges

def build_proof_trees(theorem_edges, top_n=500):
    """Build proof tree structures from theorem edges."""
    # Find the top N longest theorems by number of edges
    theorem_lengths = []
    for thm, edge_info in theorem_edges.items():
        if isinstance(edge_info, list):
            theorem_lengths.append((thm, len(edge_info)))
        else:
            theorem_lengths.append((thm, 1))
    
    # Sort by length (descending) and take top N
    top_longest = sorted(theorem_lengths, key=lambda x: x[1], reverse=True)[:top_n]
    
    # Collect all theorem data in a single structure
    all_theorems_data = {
        "metadata": {
            "total_theorems": len(top_longest),
            "description": f"Top {top_n} longest theorems by proof tree size"
        },
        "theorems": []
    }
    
    for rank, (thm, length) in enumerate(top_longest, 1):
        if thm in theorem_edges:
            edge_info = theorem_edges[thm]
            
            # Prepare data for JSON file with tree structure
            theorem_data = {
                "rank": rank,
                "theorem_name": thm,
                "proof_length": length,
                "proof_tree": {
                    "nodes": {},  # state_id -> node_info
                    "edges": []   # list of {from: state_id, to: state_id, tactic: str, premises: []}
                }
            }
            
            # Check if it's a list of dicts
            if isinstance(edge_info, list):
                for i, edge in enumerate(edge_info):
                    if isinstance(edge, dict):
                        # Extract state information
                        state_before = edge.get('state_before')
                        state_after = edge.get('state_after')
                        tactic = edge.get('tactic')
                        premises = edge.get('premises', [])
                        
                        # Add nodes to the tree
                        if state_before and state_before not in theorem_data["proof_tree"]["nodes"]:
                            theorem_data["proof_tree"]["nodes"][state_before] = {
                                "state_id": state_before,
                                "is_initial": i == 0,
                                "is_terminal": False
                            }
                        
                        if state_after and state_after not in theorem_data["proof_tree"]["nodes"]:
                            theorem_data["proof_tree"]["nodes"][state_after] = {
                                "state_id": state_after,
                                "is_initial": False,
                                "is_terminal": False
                            }
                        
                        # Add edge to the tree
                        if state_before and state_after and tactic:
                            edge_data = {
                                "from": state_before,
                                "to": state_after,
                                "tactic": tactic
                            }
                            if premises:
                                edge_data["premises"] = premises
                            
                            theorem_data["proof_tree"]["edges"].append(edge_data)
                        
                        # Check for state mismatch with next edge
                        if i + 1 < len(edge_info) and isinstance(edge_info[i + 1], dict):
                            next_edge = edge_info[i + 1]
                            if ('state_after' in edge and 'state_before' in next_edge and 
                                edge['state_after'] != next_edge['state_before']):
                                edge_data["_state_mismatch_warning"] = "state_after != next_state_before"
                
                # Mark terminal nodes (nodes that don't have outgoing edges)
                outgoing_states = {edge["from"] for edge in theorem_data["proof_tree"]["edges"]}
                for state_id, node in theorem_data["proof_tree"]["nodes"].items():
                    if state_id not in outgoing_states:
                        node["is_terminal"] = True
                            
            elif isinstance(edge_info, dict):
                # Handle single edge case
                state_before = edge_info.get('state_before')
                state_after = edge_info.get('state_after')
                tactic = edge_info.get('tactic')
                premises = edge_info.get('premises', [])
                
                # Add nodes
                if state_before:
                    theorem_data["proof_tree"]["nodes"][state_before] = {
                        "state_id": state_before,
                        "is_initial": True,
                        "is_terminal": False
                    }
                
                if state_after:
                    theorem_data["proof_tree"]["nodes"][state_after] = {
                        "state_id": state_after,
                        "is_initial": False,
                        "is_terminal": True
                    }
                
                # Add edge
                if state_before and state_after and tactic:
                    edge_data = {
                        "from": state_before,
                        "to": state_after,
                        "tactic": tactic
                    }
                    if premises:
                        edge_data["premises"] = premises
                    
                    theorem_data["proof_tree"]["edges"].append(edge_data)
            
            # Add this theorem to the combined data
            all_theorems_data["theorems"].append(theorem_data)
    
    return all_theorems_data

def save_json(all_theorems_data, output_path):
    """Save theorem data to JSON file."""
    print(f"Saving {len(all_theorems_data['theorems'])} theorems to {output_path}...")
    with open(output_path, 'w') as f:
        json.dump(all_theorems_data, f, indent=2)
    print(f"Saved to {output_path}")

def create_visualization(json_path, html_path):
    """Load JSON and create HTML visualization."""
    print(f"Loading theorem data from {json_path}...")
    with open(json_path, 'r') as f:
        all_theorems_data = json.load(f)
    
    # Extract theorem_data objects (the visualization function expects the format with 'theorem_name' and 'proof_tree')
    theorem_list = []
    for thm_data in all_theorems_data["theorems"]:
        # Convert to the format expected by visualize_proof_trees_grid
        theorem_data = {
            "theorem_name": thm_data["theorem_name"],
            "proof_tree": thm_data["proof_tree"]
        }
        theorem_list.append(theorem_data)
    
    print(f"Visualizing {len(theorem_list)} theorems...")
    # Visualize all theorems in the grid
    html_path_result = visualize_proof_trees_grid(theorem_list, html_path)
    print(f"Grid visualization saved to: {html_path_result}")
    print(f"Total theorems loaded: {len(theorem_list)}")
    print(f"Theorems visualized: {len(theorem_list)}")

def main():
    """Main function to orchestrate the entire process."""
    # Step 1: Load edges from JSONL
    if not Path(OUT_JSONL).exists():
        print(f"Error: {OUT_JSONL} not found!")
        return
    
    theorem_edges = load_theorem_edges(OUT_JSONL)
    
    # Step 2: Build proof trees
    print("\nBuilding proof trees...")
    all_theorems_data = build_proof_trees(theorem_edges, top_n=500)
    
    # Step 3: Save to JSON
    save_json(all_theorems_data, OUTPUT_JSON)
    
    # Step 4: Create HTML visualization
    print("\nCreating HTML visualization...")
    create_visualization(OUTPUT_JSON, OUTPUT_HTML)
    
    print("\nDone!")

if __name__ == "__main__":
    main()
