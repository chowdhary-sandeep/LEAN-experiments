"""
Generate visualization plots from saved FVS prediction pipeline results.

This script loads the results JSON file produced by 01_fvs_prediction_pipeline_v2.py
and generates all visualization plots without rerunning the entire pipeline.
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict
import warnings

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
    raise ImportError("matplotlib is required for generating plots. Install with: pip install matplotlib")

# Configuration
_SCRIPT_DIR = Path(__file__).resolve().parent
FIGS_DIR = _SCRIPT_DIR / "figs"
FIGS_DIR.mkdir(exist_ok=True)

# Results are produced by 03_future_prediction pipeline
FVS_CACHE_PREFIX = "fvs_pipeline_v2_"
RESULTS_JSON = _SCRIPT_DIR.parent / "03_future_prediction" / "data" / f"{FVS_CACHE_PREFIX}results.json"


def load_results() -> List[Dict]:
    """Load results from JSON file."""
    if not RESULTS_JSON.exists():
        raise FileNotFoundError(
            f"Results file not found: {RESULTS_JSON}\n"
            f"Please run 01_fvs_prediction_pipeline_v2.py first to generate results."
        )

    with open(RESULTS_JSON, "r", encoding="utf-8") as f:
        all_results = json.load(f)

    print(f"Loaded {len(all_results)} result entries from {RESULTS_JSON}")
    return all_results


def generate_visualization_plots(all_results: List[Dict]):
    """Generate visualization plots for prediction accuracy, Spearman correlation, and observed vs predicted."""
    if not HAS_MATPLOTLIB:
        return

    # Filter to r=0 results for main analysis
    r0_results = [r for r in all_results if r.get("r") == 0]
    if not r0_results:
        print("Warning: No r=0 results found in data")
        return

    print(f"Generating plots for {len(r0_results)} r=0 results...")

    # 1. Spearman correlation vs depth
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Prediction Performance Analysis (r=0)', fontsize=16, fontweight='bold')

    depths = [r["d"] for r in r0_results]

    # Plot 1: Spearman correlation for Y1
    ax1 = axes[0, 0]
    y1_spearman = []
    for r in r0_results:
        spearman = r.get("Y1_GBoost_Reg", {}).get("Spearman_rho", None)
        y1_spearman.append(spearman if spearman is not None else np.nan)

    ax1.plot(depths, y1_spearman, 'o-', linewidth=2, markersize=8, label='Y1 (Descendant Count)')
    ax1.set_xlabel('Depth d', fontsize=12)
    ax1.set_ylabel('Spearman Correlation', fontsize=12)
    ax1.set_title('Y1 Prediction: Spearman Correlation vs Depth', fontsize=13)
    ax1.grid(True, alpha=0.3)
    ax1.legend()
    ax1.set_ylim([-1, 1])

    # Plot 2: PR-AUC for Y2 classification
    ax2 = axes[0, 1]
    y2_pr_auc = []
    for r in r0_results:
        pr_auc = r.get("Y2_GBoost_Class", {}).get("PR_AUC", None)
        y2_pr_auc.append(pr_auc if pr_auc is not None else np.nan)

    ax2.plot(depths, y2_pr_auc, 's-', linewidth=2, markersize=8, color='orange', label='Y2 (Outdegree)')
    ax2.set_xlabel('Depth d', fontsize=12)
    ax2.set_ylabel('PR-AUC', fontsize=12)
    ax2.set_title('Y2 Classification: PR-AUC vs Depth', fontsize=13)
    ax2.grid(True, alpha=0.3)
    ax2.legend()
    ax2.set_ylim([0, 1])

    # Plot 3: MAE comparison (log scale for Y1)
    ax3 = axes[1, 0]
    y1_mae_log = []
    zero_y1_mae_log = []
    for r in r0_results:
        mae = r.get("Y1_GBoost_Reg", {}).get("MAE", None)
        zero_mae = r.get("baselines", {}).get("Zero", {}).get("Y1_MAE_log", None)
        y1_mae_log.append(mae if mae is not None else np.nan)
        zero_y1_mae_log.append(zero_mae if zero_mae is not None else np.nan)

    ax3.plot(depths, zero_y1_mae_log, '--', linewidth=2, label='Zero Baseline (log)', alpha=0.7)
    ax3.plot(depths, y1_mae_log, 'o-', linewidth=2, markersize=8, label='GBoost Model (log)', color='green')
    ax3.set_xlabel('Depth d', fontsize=12)
    ax3.set_ylabel('MAE (log scale)', fontsize=12)
    ax3.set_title('Y1 Prediction: MAE Comparison (log scale)', fontsize=13)
    ax3.grid(True, alpha=0.3)
    ax3.legend()

    # Plot 4: Y2 MAE comparison
    ax4 = axes[1, 1]
    y2_mae = []
    zero_y2_mae = []
    for r in r0_results:
        mae = r.get("Y2_GBoost_Reg", {}).get("MAE", None)
        zero_mae = r.get("baselines", {}).get("Zero", {}).get("Y2_MAE", None)
        y2_mae.append(mae if mae is not None else np.nan)
        zero_y2_mae.append(zero_mae if zero_mae is not None else np.nan)

    ax4.plot(depths, zero_y2_mae, '--', linewidth=2, label='Zero Baseline', alpha=0.7)
    ax4.plot(depths, y2_mae, 's-', linewidth=2, markersize=8, label='GBoost Model', color='red')
    ax4.set_xlabel('Depth d', fontsize=12)
    ax4.set_ylabel('MAE (raw scale)', fontsize=12)
    ax4.set_title('Y2 Prediction: MAE Comparison', fontsize=13)
    ax4.grid(True, alpha=0.3)
    ax4.legend()

    plt.tight_layout()
    plt.savefig(FIGS_DIR / "prediction_performance_summary.png", dpi=300, bbox_inches='tight')
    plt.savefig(FIGS_DIR / "prediction_performance_summary.pdf", bbox_inches='tight')
    plt.close()
    print(f"  Generated prediction_performance_summary.png/pdf")

    # 2. Observed vs Predicted scatter plots (for best depth)
    if r0_results:
        # Find depth with best Y1 Spearman correlation
        best_depth_idx = np.nanargmax(y1_spearman)
        best_result = r0_results[best_depth_idx]
        best_d = best_result["d"]

        # Create observed vs predicted plots
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'Observed vs Predicted (r=0, d={best_d})', fontsize=16, fontweight='bold')

        # Y1: Log scale
        if "Y1_predictions" in best_result:
            ax1 = axes[0, 0]
            pred_data = best_result["Y1_predictions"]
            y1_true_log = np.array(pred_data["true_log"])
            y1_pred_log = np.array(pred_data["pred_log"])
            # Filter out zeros for log plot
            mask = (y1_true_log > 0) & (y1_pred_log > 0)
            if np.sum(mask) > 0:
                ax1.scatter(y1_true_log[mask], y1_pred_log[mask], alpha=0.5, s=20)
                # Diagonal line
                min_val = min(np.min(y1_true_log[mask]), np.min(y1_pred_log[mask]))
                max_val = max(np.max(y1_true_log[mask]), np.max(y1_pred_log[mask]))
                ax1.plot([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect prediction')
                ax1.set_xlabel('Observed log(Y1+1)', fontsize=12)
                ax1.set_ylabel('Predicted log(Y1+1)', fontsize=12)
                ax1.set_title('Y1: Observed vs Predicted (log scale)', fontsize=13)
                ax1.legend()
                ax1.grid(True, alpha=0.3)

        # Y1: Raw scale (log-log for better visualization)
        if "Y1_predictions" in best_result:
            ax2 = axes[0, 1]
            pred_data = best_result["Y1_predictions"]
            y1_true = np.array(pred_data["true"])
            y1_pred = np.array(pred_data["pred"])
            # Log-log plot
            mask = (y1_true > 0) & (y1_pred > 0)
            if np.sum(mask) > 0:
                ax2.loglog(y1_true[mask], y1_pred[mask], 'o', alpha=0.5, markersize=4)
                # Diagonal line
                min_val = min(np.min(y1_true[mask]), np.min(y1_pred[mask]))
                max_val = max(np.max(y1_true[mask]), np.max(y1_pred[mask]))
                ax2.loglog([min_val, max_val], [min_val, max_val], 'r--', linewidth=2, label='Perfect prediction')
                ax2.set_xlabel('Observed Y1', fontsize=12)
                ax2.set_ylabel('Predicted Y1', fontsize=12)
                ax2.set_title('Y1: Observed vs Predicted (log-log scale)', fontsize=13)
                ax2.legend()
                ax2.grid(True, alpha=0.3)

        # Y2: Raw scale
        if "Y2_predictions" in best_result:
            ax3 = axes[1, 0]
            pred_data = best_result["Y2_predictions"]
            y2_true = np.array(pred_data["true"])
            y2_pred = np.array(pred_data["pred"])
            ax3.scatter(y2_true, y2_pred, alpha=0.5, s=20, color='orange')
            # Diagonal line
            max_val = max(np.max(y2_true), np.max(y2_pred))
            ax3.plot([0, max_val], [0, max_val], 'r--', linewidth=2, label='Perfect prediction')
            ax3.set_xlabel('Observed Y2', fontsize=12)
            ax3.set_ylabel('Predicted Y2', fontsize=12)
            ax3.set_title('Y2: Observed vs Predicted', fontsize=13)
            ax3.legend()
            ax3.grid(True, alpha=0.3)

        # Y2: Confusion matrix style (for classification)
        if "Y2_GBoost_Class" in best_result:
            ax4 = axes[1, 1]
            # Get classification probabilities if available
            # For now, show distribution of Y2 predictions vs true
            if "Y2_predictions" in best_result:
                pred_data = best_result["Y2_predictions"]
                y2_true = np.array(pred_data["true"])
                y2_pred = np.array(pred_data["pred"])
                bins = np.arange(-0.5, max(np.max(y2_true), np.max(y2_pred)) + 1.5, 1)
                ax4.hist(y2_true, bins=bins, alpha=0.5, label='Observed', color='blue')
                ax4.hist(y2_pred, bins=bins, alpha=0.5, label='Predicted', color='orange')
                ax4.set_xlabel('Y2 (Outdegree)', fontsize=12)
                ax4.set_ylabel('Frequency', fontsize=12)
                ax4.set_title('Y2: Distribution Comparison', fontsize=13)
                ax4.legend()
                ax4.grid(True, alpha=0.3, axis='y')

        plt.tight_layout()
        plt.savefig(FIGS_DIR / f"observed_vs_predicted_d{best_d}.png", dpi=300, bbox_inches='tight')
        plt.savefig(FIGS_DIR / f"observed_vs_predicted_d{best_d}.pdf", bbox_inches='tight')
        plt.close()
        print(f"  Generated observed_vs_predicted_d{best_d}.png/pdf")

    # 3. Feature importance plot (if available)
    feature_importance_data = []
    for r in r0_results:
        if "feature_importance" in r:
            fi = r["feature_importance"]
            d = r["d"]
            for feat_name, importance in fi.items():
                feature_importance_data.append({
                    "feature": feat_name,
                    "importance": importance,
                    "depth": d
                })

    if feature_importance_data:
        # Aggregate feature importance across depths
        feat_agg = {}
        for item in feature_importance_data:
            feat = item["feature"]
            if feat not in feat_agg:
                feat_agg[feat] = []
            feat_agg[feat].append(item["importance"])

        # Average importance per feature
        feat_avg_imp = {feat: np.mean(imps) for feat, imps in feat_agg.items()}
        sorted_feats = sorted(feat_avg_imp.items(), key=lambda x: x[1], reverse=True)[:15]  # Top 15

        fig, ax = plt.subplots(figsize=(10, 8))
        features = [f[0] for f in sorted_feats]
        importances = [f[1] for f in sorted_feats]

        ax.barh(range(len(features)), importances, color='steelblue')
        ax.set_yticks(range(len(features)))
        ax.set_yticklabels(features)
        ax.set_xlabel('Average Feature Importance', fontsize=12)
        ax.set_title('Top 15 Feature Importances (r=0, averaged across depths)', fontsize=13)
        ax.grid(True, alpha=0.3, axis='x')
        plt.tight_layout()
        plt.savefig(FIGS_DIR / "feature_importance.png", dpi=300, bbox_inches='tight')
        plt.savefig(FIGS_DIR / "feature_importance.pdf", bbox_inches='tight')
        plt.close()
        print(f"  Generated feature_importance.png/pdf")

    print(f"\nAll plots saved to {FIGS_DIR}")


def main():
    """Main execution."""
    print("=" * 80)
    print("FVS Prediction Pipeline - Visualization Generator")
    print("=" * 80)

    # Load results
    try:
        all_results = load_results()
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        return

    # Generate plots
    print("\nGenerating visualization plots...")
    try:
        generate_visualization_plots(all_results)
        print("\n" + "=" * 80)
        print("Plotting complete!")
        print("=" * 80)
    except Exception as e:
        print(f"\nError generating plots: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
