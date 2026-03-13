from __future__ import annotations

import importlib.util
import json
import pickle
import random
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
FIGS_DIR = ROOT / "figs"
DEPTHS = [5, 10, 20, 30]
REPEATS = 10


def load_pipeline_module():
    script = ROOT / "1_future_prediction_pipeline_v2.py"
    spec = importlib.util.spec_from_file_location("future_prediction_pipeline_v2", script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_cached_objects():
    with open(DATA_DIR / "1_fvs_pipeline_v2_dag.pkl", "rb") as f:
        dag = pickle.load(f)
    with open(DATA_DIR / "1_fvs_pipeline_v2_depths.pkl", "rb") as f:
        depths = pickle.load(f)
    with open(DATA_DIR / "1_fvs_pipeline_v2_targets.pkl", "rb") as f:
        targets = pickle.load(f)
    return dag, depths, targets


def frontier_nodes(depth_map, d: int):
    return [v for v, depth in depth_map.items() if depth == d]


def compute_target_structure(dag, depth_map, targets):
    rows = []
    bucket_rows = []
    for d in DEPTHS:
        nodes = frontier_nodes(depth_map, d)
        y1 = np.array([targets[v]["Y1"] for v in nodes], dtype=float)
        y2 = np.array([targets[v]["Y2"] for v in nodes], dtype=float)
        gc = []
        for v in nodes:
            grandchildren = set()
            for child in dag.successors(v):
                grandchildren.update(dag.successors(child))
            gc.append(len(grandchildren))
        gc = np.array(gc, dtype=float)

        positive = y1 > 0
        rows.append(
            {
                "depth": d,
                "n_frontier": len(nodes),
                "y1_zero_frac": float(np.mean(y1 == 0)),
                "y1_mean": float(np.mean(y1)),
                "y1_median": float(np.median(y1)),
                "y1_p90": float(np.percentile(y1, 90)),
                "y1_p99": float(np.percentile(y1, 99)),
                "y1_max": int(np.max(y1)),
                "y2_zero_frac": float(np.mean(y2 == 0)),
                "y2_mean": float(np.mean(y2)),
                "y2_median": float(np.median(y2)),
                "y2_p90": float(np.percentile(y2, 90)),
                "y2_p99": float(np.percentile(y2, 99)),
                "y2_max": int(np.max(y2)),
                "spearman_y1_y2_all": float(spearmanr(y1, y2).statistic),
                "spearman_y1_gc_all": float(spearmanr(y1, gc).statistic),
                "spearman_y1_y2_positive": float(spearmanr(y1[positive], y2[positive]).statistic)
                if positive.sum() > 1
                else np.nan,
                "spearman_y1_gc_positive": float(spearmanr(y1[positive], gc[positive]).statistic)
                if positive.sum() > 1
                else np.nan,
            }
        )

        buckets = defaultdict(list)
        for y2_value, y1_value in zip(y2.astype(int), y1):
            bucket = str(y2_value) if y2_value < 5 else "5+"
            buckets[bucket].append(float(y1_value))
        for bucket, values in sorted(buckets.items(), key=lambda item: (item[0] != "5+", item[0])):
            bucket_rows.append(
                {
                    "depth": d,
                    "y2_bucket": bucket,
                    "n_samples": len(values),
                    "y1_mean": float(np.mean(values)),
                    "y1_median": float(np.median(values)),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(bucket_rows)


def compute_feature_correlations(pipeline, dag, depth_map, targets, feature_cfg):
    rows = []
    for d in [5, 10, 20]:
        X, Y1, Y2, *_rest, feature_names = pipeline.create_dataset(dag, depth_map, targets, d, 0, feature_cfg)
        arr = pipeline.features_to_array(X, feature_names)
        y1 = np.array(Y1, dtype=float)
        y2 = np.array(Y2, dtype=float)
        for i, feature_name in enumerate(feature_names):
            x = arr[:, i]
            if np.all(x == x[0]):
                continue
            rows.append(
                {
                    "depth": d,
                    "feature": feature_name,
                    "spearman_y1": float(spearmanr(x, y1).statistic),
                    "spearman_y2": float(spearmanr(x, y2).statistic),
                    "abs_spearman_y1": float(abs(spearmanr(x, y1).statistic)),
                    "abs_spearman_y2": float(abs(spearmanr(x, y2).statistic)),
                }
            )
    df = pd.DataFrame(rows)
    summary = (
        df.groupby("feature")[["abs_spearman_y1", "abs_spearman_y2"]]
        .mean()
        .reset_index()
        .sort_values("abs_spearman_y2", ascending=False)
    )
    return df, summary


def compute_split_stability(pipeline, dag, depth_map, targets, feature_cfg):
    rows = []
    summary_rows = []
    for d in [5, 10, 20]:
        X, Y1, Y2, Z1, Z2, _nodes, feature_names = pipeline.create_dataset(dag, depth_map, targets, d, 0, feature_cfg)
        for seed in range(REPEATS):
            indices = list(range(len(X)))
            random.Random(seed).shuffle(indices)
            n_train = int(0.8 * len(indices))
            train_idx = indices[:n_train]
            test_idx = indices[n_train:]
            result = pipeline.train_and_evaluate_two_stage(
                [X[i] for i in train_idx],
                [Y1[i] for i in train_idx],
                [Y2[i] for i in train_idx],
                [Z1[i] for i in train_idx],
                [Z2[i] for i in train_idx],
                [X[i] for i in test_idx],
                [Y1[i] for i in test_idx],
                [Y2[i] for i in test_idx],
                [Z1[i] for i in test_idx],
                [Z2[i] for i in test_idx],
                feature_names,
                0,
            )
            rows.append(
                {
                    "depth": d,
                    "seed": seed,
                    "y2_pr_auc": result.get("Y2_GBoost_Class", {}).get("PR_AUC"),
                    "y1_spearman": result.get("Y1_GBoost_Reg", {}).get("Spearman_rho"),
                }
            )

        depth_df = pd.DataFrame([row for row in rows if row["depth"] == d])
        summary_rows.append(
            {
                "depth": d,
                "repeats": REPEATS,
                "y2_pr_auc_mean": float(depth_df["y2_pr_auc"].mean()),
                "y2_pr_auc_std": float(depth_df["y2_pr_auc"].std(ddof=0)),
                "y2_pr_auc_min": float(depth_df["y2_pr_auc"].min()),
                "y2_pr_auc_max": float(depth_df["y2_pr_auc"].max()),
                "y1_spearman_mean": float(depth_df["y1_spearman"].mean()),
                "y1_spearman_std": float(depth_df["y1_spearman"].std(ddof=0)),
                "y1_spearman_min": float(depth_df["y1_spearman"].min()),
                "y1_spearman_max": float(depth_df["y1_spearman"].max()),
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(summary_rows)


def compute_y2_importance(pipeline, dag, depth_map, targets, feature_cfg):
    rows = []
    for d in [5, 10, 20]:
        X, _Y1, Y2, _Z1, _Z2, _nodes, feature_names = pipeline.create_dataset(dag, depth_map, targets, d, 0, feature_cfg)
        indices = list(range(len(X)))
        random.Random(42).shuffle(indices)
        n_train = int(0.8 * len(indices))
        train_idx = indices[:n_train]

        x_train = pipeline.features_to_array([X[i] for i in train_idx], feature_names)
        x_train = np.nan_to_num(x_train, nan=0.0, posinf=1e6, neginf=-1e6)
        scaler = StandardScaler()
        x_train = scaler.fit_transform(x_train)
        y_train = (np.array([Y2[i] for i in train_idx]) > 0).astype(int)

        model = GradientBoostingClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(x_train, y_train)
        for feature_name, importance in zip(feature_names, model.feature_importances_):
            rows.append({"depth": d, "feature": feature_name, "importance": float(importance)})

    df = pd.DataFrame(rows)
    summary = (
        df.groupby("feature")["importance"]
        .mean()
        .reset_index()
        .sort_values("importance", ascending=False)
    )
    return df, summary


def save_figures(target_df, split_summary_df, importance_summary_df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot(target_df["depth"], target_df["spearman_y1_y2_positive"], marker="o", label="Y1 vs Y2")
    axes[0].plot(target_df["depth"], target_df["spearman_y1_gc_positive"], marker="s", label="Y1 vs grandchild_count")
    axes[0].set_title("Positive-case target coupling")
    axes[0].set_xlabel("Depth")
    axes[0].set_ylabel("Spearman rho")
    axes[0].legend()

    width = 0.35
    x = np.arange(len(split_summary_df))
    axes[1].bar(x - width / 2, split_summary_df["y2_pr_auc_mean"], width=width, label="Y2 PR-AUC")
    axes[1].bar(x + width / 2, split_summary_df["y1_spearman_mean"], width=width, label="Y1 Spearman")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(split_summary_df["depth"].astype(str).tolist())
    axes[1].set_title("r=0 repeated-split stability")
    axes[1].set_xlabel("Depth")
    axes[1].set_ylabel("Mean metric over 10 splits")
    axes[1].legend()

    fig.tight_layout()
    fig.savefig(FIGS_DIR / "1_intermediate_target_and_stability.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    top_features = importance_summary_df.head(10).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top_features["feature"], top_features["importance"], color="steelblue")
    ax.set_title("Average r=0 Y2 feature importance")
    ax.set_xlabel("Mean gradient-boosting importance")
    fig.tight_layout()
    fig.savefig(FIGS_DIR / "1_intermediate_y2_feature_importance_r0.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def save_summary_markdown(target_df, split_summary_df, importance_summary_df):
    lines = [
        "# Intermediate Analysis Notes",
        "",
        "Generated by `save_intermediate_analysis.py`.",
        "",
        "## Key numbers",
        "",
    ]
    for row in split_summary_df.itertuples(index=False):
        lines.append(
            f"- Depth {row.depth}: Y2 PR-AUC mean={row.y2_pr_auc_mean:.3f} (std={row.y2_pr_auc_std:.3f}), "
            f"Y1 Spearman mean={row.y1_spearman_mean:.3f} (std={row.y1_spearman_std:.3f})"
        )
    lines.extend(
        [
            "",
            "## Structural observations",
            "",
        ]
    )
    for row in target_df.itertuples(index=False):
        lines.append(
            f"- Depth {row.depth}: Y1 zero fraction={row.y1_zero_frac:.3f}, "
            f"positive-case Spearman(Y1,Y2)={row.spearman_y1_y2_positive:.3f}, "
            f"positive-case Spearman(Y1,grandchild_count)={row.spearman_y1_gc_positive:.3f}"
        )
    lines.extend(
        [
            "",
            "## Top r=0 features for Y2>0",
            "",
        ]
    )
    for row in importance_summary_df.head(10).itertuples(index=False):
        lines.append(f"- {row.feature}: mean importance={row.importance:.4f}")
    (DATA_DIR / "1_intermediate_analysis_summary.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    DATA_DIR.mkdir(exist_ok=True)
    FIGS_DIR.mkdir(exist_ok=True)

    pipeline = load_pipeline_module()
    dag, depth_map, targets = load_cached_objects()
    feature_cfg = pipeline.load_feature_config(ROOT / "1_future_prediction_pipeline_v2.json")

    target_df, bucket_df = compute_target_structure(dag, depth_map, targets)
    feature_corr_df, feature_corr_summary_df = compute_feature_correlations(
        pipeline, dag, depth_map, targets, feature_cfg
    )
    split_df, split_summary_df = compute_split_stability(pipeline, dag, depth_map, targets, feature_cfg)
    importance_df, importance_summary_df = compute_y2_importance(
        pipeline, dag, depth_map, targets, feature_cfg
    )

    target_df.to_csv(DATA_DIR / "1_intermediate_target_structure.csv", index=False)
    bucket_df.to_csv(DATA_DIR / "1_intermediate_y1_by_y2_bucket.csv", index=False)
    feature_corr_df.to_csv(DATA_DIR / "1_intermediate_feature_correlations_r0.csv", index=False)
    feature_corr_summary_df.to_csv(DATA_DIR / "1_intermediate_feature_correlations_r0_summary.csv", index=False)
    split_df.to_csv(DATA_DIR / "1_intermediate_repeated_split_metrics_r0.csv", index=False)
    split_summary_df.to_csv(DATA_DIR / "1_intermediate_repeated_split_summary_r0.csv", index=False)
    importance_df.to_csv(DATA_DIR / "1_intermediate_y2_feature_importance_r0.csv", index=False)
    importance_summary_df.to_csv(DATA_DIR / "1_intermediate_y2_feature_importance_r0_summary.csv", index=False)

    save_figures(target_df, split_summary_df, importance_summary_df)
    save_summary_markdown(target_df, split_summary_df, importance_summary_df)

    manifest = {
        "data_files": sorted(path.name for path in DATA_DIR.glob("1_intermediate_*")),
        "figure_files": sorted(path.name for path in FIGS_DIR.glob("1_intermediate_*")),
    }
    (DATA_DIR / "1_intermediate_analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
