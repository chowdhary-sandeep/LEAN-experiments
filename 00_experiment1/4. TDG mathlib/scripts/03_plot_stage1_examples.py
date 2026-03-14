from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

from tdg_utils import ROOT, theorem_slug


DATA_DIR = ROOT / "data"
FIGS_DIR = ROOT / "figs"


def load_graphs(limit: int | None = None) -> list[dict]:
    graphs = []
    with (DATA_DIR / "stage1_tdg_by_theorem.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            graphs.append(json.loads(line))
            if limit is not None and len(graphs) >= limit:
                break
    return graphs


def draw_tdg(graph: dict, output_path: Path, title: str) -> None:
    dg = nx.DiGraph()
    labels = {}
    colors = []
    for node in graph["nodes"]:
        dg.add_node(node["node_id"], node_type=node["node_type"], label=node["tactic_head"])
        if node["node_type"] == "special":
            labels[node["node_id"]] = node["tactic_head"]
            colors.append("#d9eef7")
        else:
            labels[node["node_id"]] = node["tactic_head"]
            colors.append("#9ed3e6")
    for edge in graph["edges"]:
        if edge["src_node_id"] in dg and edge["dst_node_id"] in dg:
            dg.add_edge(edge["src_node_id"], edge["dst_node_id"], label=edge["label"], edge_type=edge["edge_type"])

    topo = list(nx.topological_generations(dg))
    pos = {}
    for x, layer in enumerate(topo):
        y_positions = list(range(len(layer)))[::-1]
        for y, node_id in zip(y_positions, layer):
            pos[node_id] = (x, y)

    fig, ax = plt.subplots(figsize=(max(6, len(topo) * 1.4), 3.6))
    nx.draw_networkx_nodes(
        dg,
        pos,
        node_color=["#d9eef7" if dg.nodes[n]["node_type"] == "special" else "#9ed3e6" for n in dg.nodes],
        node_shape="o",
        node_size=[2200 if dg.nodes[n]["node_type"] == "special" else 1800 for n in dg.nodes],
        edgecolors="#35566b",
        linewidths=1.2,
        ax=ax,
    )
    nx.draw_networkx_labels(dg, pos, labels=labels, font_size=8, ax=ax)
    nx.draw_networkx_edges(dg, pos, arrows=True, arrowstyle="-|>", arrowsize=12, width=1.4, ax=ax, edge_color="#2f4754")
    edge_labels = {(u, v): data["label"] for u, v, data in dg.edges(data=True) if data["edge_type"] != "goal_to_goal" or data["label"] != "active_goal"}
    if edge_labels:
        nx.draw_networkx_edge_labels(dg, pos, edge_labels=edge_labels, font_size=6, ax=ax)
    ax.set_title(title, fontsize=11)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(output_path, format="svg")
    plt.close(fig)


def make_corpus_summary(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> None:
    summary_dir = FIGS_DIR / "stage1_corpus_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    tactic_nodes = nodes_df[nodes_df["node_type"] == "tactic"]
    tactic_counts = tactic_nodes.groupby("theorem").size()
    edge_counts = edges_df.groupby("theorem").size()
    head_counts = Counter(tactic_nodes["tactic_head"])

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    axes[0, 0].hist(tactic_counts, bins=40, color="#9ed3e6", edgecolor="#35566b")
    axes[0, 0].set_title("TDG tactic nodes per theorem")
    axes[0, 1].hist(edge_counts, bins=40, color="#9ed3e6", edgecolor="#35566b")
    axes[0, 1].set_title("TDG edges per theorem")

    top_heads = head_counts.most_common(15)
    axes[1, 0].barh([name for name, _ in top_heads][::-1], [count for _, count in top_heads][::-1], color="#9ed3e6", edgecolor="#35566b")
    axes[1, 0].set_title("Top tactic heads")

    edge_type_counts = edges_df["edge_type"].value_counts()
    axes[1, 1].bar(edge_type_counts.index, edge_type_counts.values, color="#9ed3e6", edgecolor="#35566b")
    axes[1, 1].set_title("Edge type counts")

    for ax in axes.ravel():
        ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(summary_dir / "stage1_corpus_summary.svg", format="svg")
    plt.close(fig)


def main() -> None:
    single_dir = FIGS_DIR / "stage1_single_proof_examples"
    pair_dir = FIGS_DIR / "stage1_pair_examples"
    triptych_dir = FIGS_DIR / "stage1_refactoring_triptychs"
    for directory in (single_dir, pair_dir, triptych_dir):
        directory.mkdir(parents=True, exist_ok=True)

    graphs = load_graphs()
    nodes_df = pd.read_parquet(DATA_DIR / "stage1_tdg_nodes.parquet")
    edges_df = pd.read_parquet(DATA_DIR / "stage1_tdg_edges.parquet")

    interesting = sorted(
        graphs,
        key=lambda g: len(g["nodes"]),
    )
    selected = []
    selected.extend(interesting[:2])
    selected.extend(interesting[len(interesting) // 2: len(interesting) // 2 + 2])
    selected.extend(interesting[-2:])

    for graph in selected:
        slug = theorem_slug(graph["theorem"])
        draw_tdg(graph, single_dir / f"{slug}.svg", graph["theorem"])

    signature_map: dict[tuple[str, ...], list[dict]] = {}
    for graph in graphs:
        heads = tuple(node["tactic_head"] for node in graph["nodes"] if node["node_type"] == "tactic")
        signature_map.setdefault(heads[:6], []).append(graph)
    pair_candidates = [group[:2] for group in signature_map.values() if len(group) >= 2 and len(group[0]["nodes"]) >= 4]
    for idx, pair in enumerate(pair_candidates[:3], start=1):
        fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
        for axis, graph in zip(axes, pair):
            temp_path = pair_dir / f"_tmp_{idx}.svg"
            plt.sca(axis)
            dg = nx.DiGraph()
            for node in graph["nodes"]:
                dg.add_node(node["node_id"], node_type=node["node_type"], label=node["tactic_head"])
            for edge in graph["edges"]:
                if edge["src_node_id"] in dg and edge["dst_node_id"] in dg:
                    dg.add_edge(edge["src_node_id"], edge["dst_node_id"])
            topo = list(nx.topological_generations(dg))
            pos = {}
            for x, layer in enumerate(topo):
                for y, node_id in enumerate(layer[::-1]):
                    pos[node_id] = (x, y)
            nx.draw_networkx_nodes(
                dg,
                pos,
                node_color=["#d9eef7" if dg.nodes[n]["node_type"] == "special" else "#9ed3e6" for n in dg.nodes],
                node_size=1200,
                edgecolors="#35566b",
                ax=axis,
            )
            nx.draw_networkx_labels(dg, pos, labels={n: dg.nodes[n]["label"] for n in dg.nodes}, font_size=7, ax=axis)
            nx.draw_networkx_edges(dg, pos, arrows=True, arrowstyle="-|>", arrowsize=10, width=1.2, edge_color="#2f4754", ax=axis)
            axis.set_title(graph["theorem"].split(".")[-1], fontsize=9)
            axis.axis("off")
        fig.tight_layout()
        fig.savefig(pair_dir / f"pair_{idx}.svg", format="svg")
        plt.close(fig)

    if selected:
        triptych_graphs = selected[:3]
        fig, axes = plt.subplots(1, 3, figsize=(15, 4))
        titles = ["(a) Original proof TDG", "(b) Extracted subgraph view", "(c) Alternate proof TDG"]
        for axis, graph, title in zip(axes, triptych_graphs, titles):
            dg = nx.DiGraph()
            for node in graph["nodes"]:
                dg.add_node(node["node_id"], node_type=node["node_type"], label=node["tactic_head"])
            for edge in graph["edges"]:
                if edge["src_node_id"] in dg and edge["dst_node_id"] in dg:
                    dg.add_edge(edge["src_node_id"], edge["dst_node_id"])
            topo = list(nx.topological_generations(dg))
            pos = {}
            for x, layer in enumerate(topo):
                for y, node_id in enumerate(layer[::-1]):
                    pos[node_id] = (x, y)
            nx.draw_networkx_nodes(
                dg,
                pos,
                node_color=["#d9eef7" if dg.nodes[n]["node_type"] == "special" else "#9ed3e6" for n in dg.nodes],
                node_size=1200,
                edgecolors="#35566b",
                ax=axis,
            )
            nx.draw_networkx_labels(dg, pos, labels={n: dg.nodes[n]["label"] for n in dg.nodes}, font_size=7, ax=axis)
            nx.draw_networkx_edges(dg, pos, arrows=True, arrowstyle="-|>", arrowsize=10, width=1.2, edge_color="#2f4754", ax=axis)
            axis.set_title(title, fontsize=9)
            axis.axis("off")
        fig.tight_layout()
        fig.savefig(triptych_dir / "stage1_triptych.svg", format="svg")
        plt.close(fig)

    make_corpus_summary(nodes_df, edges_df)
    print("Wrote stage-1 figures.")


if __name__ == "__main__":
    main()
