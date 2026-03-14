from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from tdg_utils import ROOT


DATA_DIR = ROOT / "data"
FIG_DIR = ROOT / "figs"
REPORT_DIR = ROOT / "reports"


def motif_text(labels: object) -> str:
    if isinstance(labels, np.ndarray):
        seq = labels.tolist()
    elif isinstance(labels, list):
        seq = labels
    else:
        seq = [str(labels)]
    return " -> ".join(str(x) for x in seq)


def main() -> None:
    FIG_DIR.mkdir(exist_ok=True)
    REPORT_DIR.mkdir(exist_ok=True)

    rank = pd.read_parquet(DATA_DIR / "stage4b_connected_compression_ranking.parquet")
    collapsible = pd.read_parquet(DATA_DIR / "stage3b_connected_collapsible_candidates.parquet")

    merged = rank.merge(
        collapsible[
            [
                "candidate_id",
                "support_theorems",
                "witness_count",
                "collapsible_witness_count",
                "collapsible_theorem_support",
            ]
        ],
        on="candidate_id",
        how="left",
    )
    merged["motif"] = merged["node_labels"].map(motif_text)
    merged["overlap_loss"] = 1.0 - (
        merged["disjoint_witness_count"] / merged["raw_collapsible_witness_count"].clip(lower=1)
    )

    top_overall = merged.head(12).iloc[::-1]
    top_large = merged[merged["candidate_num_nodes"] >= 3].head(12).iloc[::-1]

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    plt.subplots_adjust(hspace=0.28, wspace=0.22)

    ax = axes[0, 0]
    colors = ["#c6d8e3" if n == 2 else "#7aa6c2" if n == 3 else "#355c7d" for n in top_overall["candidate_num_nodes"]]
    ax.barh(top_overall["motif"], top_overall["estimated_corpus_savings"], color=colors, edgecolor="#23313a")
    ax.set_title("Top Connected Candidates by Estimated Corpus Savings")
    ax.set_xlabel("Estimated corpus savings")
    ax.set_ylabel("")
    for i, value in enumerate(top_overall["estimated_corpus_savings"]):
        ax.text(value + max(top_overall["estimated_corpus_savings"]) * 0.01, i, f"{int(value):,}", va="center", fontsize=9)

    ax = axes[0, 1]
    colors = ["#7aa6c2" if n == 3 else "#355c7d" for n in top_large["candidate_num_nodes"]]
    ax.barh(top_large["motif"], top_large["estimated_corpus_savings"], color=colors, edgecolor="#23313a")
    ax.set_title("Largest Compressive Candidates (Size >= 3)")
    ax.set_xlabel("Estimated corpus savings")
    ax.set_ylabel("")
    for i, value in enumerate(top_large["estimated_corpus_savings"]):
        ax.text(value + max(top_large["estimated_corpus_savings"]) * 0.01, i, f"{int(value):,}", va="center", fontsize=9)

    ax = axes[1, 0]
    size_summary = (
        merged.groupby("candidate_num_nodes")
        .agg(
            candidate_count=("candidate_id", "size"),
            median_savings=("estimated_corpus_savings", "median"),
            p90_savings=("estimated_corpus_savings", lambda s: float(s.quantile(0.9))),
            max_savings=("estimated_corpus_savings", "max"),
        )
        .reset_index()
    )
    x = np.arange(len(size_summary))
    ax.bar(x - 0.18, size_summary["candidate_count"], width=0.36, color="#d9e2e8", edgecolor="#23313a", label="candidate count")
    ax2 = ax.twinx()
    ax2.plot(x, size_summary["median_savings"], color="#7aa6c2", marker="o", linewidth=2, label="median savings")
    ax2.plot(x, size_summary["p90_savings"], color="#355c7d", marker="o", linewidth=2, label="90th pct savings")
    ax.set_xticks(x)
    ax.set_xticklabels([str(int(v)) for v in size_summary["candidate_num_nodes"]])
    ax.set_title("Candidate Size vs Compression Profile")
    ax.set_xlabel("Candidate size (nodes)")
    ax.set_ylabel("Number of candidates")
    ax2.set_ylabel("Estimated corpus savings")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="upper right", frameon=False)

    ax = axes[1, 1]
    scatter = merged.sample(min(4000, len(merged)), random_state=0).copy()
    color_map = {2: "#c6d8e3", 3: "#7aa6c2", 4: "#355c7d"}
    ax.scatter(
        scatter["raw_collapsible_witness_count"].clip(lower=1),
        scatter["disjoint_witness_count"].clip(lower=1),
        c=scatter["candidate_num_nodes"].map(color_map),
        s=16,
        alpha=0.35,
        edgecolors="none",
    )
    lim = max(scatter["raw_collapsible_witness_count"].max(), scatter["disjoint_witness_count"].max())
    ax.plot([1, lim], [1, lim], linestyle="--", color="#555555", linewidth=1)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Raw collapsible witness count")
    ax.set_ylabel("Disjoint witness count")
    ax.set_title("Overlap Loss After Disjoint Witness Selection")
    for _, row in merged.head(8).iterrows():
        ax.annotate(
            row["motif"],
            (max(row["raw_collapsible_witness_count"], 1), max(row["disjoint_witness_count"], 1)),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    legend_handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=color_map[size], markersize=8, label=f"size {size}")
        for size in sorted(color_map)
    ]
    ax.legend(handles=legend_handles, loc="lower right", frameon=False)

    fig.suptitle("Connected Compression Summary for Mathlib TDG Candidates", fontsize=16, y=0.98)
    out_path = FIG_DIR / "stage4b_connected_compression_multipanel.png"
    fig.savefig(out_path, dpi=220, bbox_inches="tight")
    plt.close(fig)

    report_lines = [
        "# Stage 4B Connected Compression Multipanel",
        "",
        f"- figure: `{out_path.name}`",
        f"- ranked candidates: {len(merged):,}",
        f"- top candidate: `{merged.iloc[0]['candidate_id']}` = `{merged.iloc[0]['motif']}` with estimated corpus savings {int(merged.iloc[0]['estimated_corpus_savings']):,}",
        f"- best size>=3 candidate: `{top_large.iloc[-1]['candidate_id']}` = `{top_large.iloc[-1]['motif']}` with estimated corpus savings {int(top_large.iloc[-1]['estimated_corpus_savings']):,}",
        "",
        "## Size summary",
        "",
    ]
    for _, row in size_summary.iterrows():
        report_lines.append(
            f"- size {int(row['candidate_num_nodes'])}: {int(row['candidate_count']):,} candidates | median savings {int(row['median_savings']):,} | 90th percentile {int(row['p90_savings']):,} | max {int(row['max_savings']):,}"
        )

    (REPORT_DIR / "stage4b_connected_compression_multipanel.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
