"""
Discovery Dynamics — Distilled 5-Panel Figure (v4)

Layout: 2 rows x 3 columns
  [0, 0:2]  EFG merged — Memory phase transition, all recall modes overlaid
  [0, 2]    C          — Dilution histogram
  [1, 0]    J          — Coverage gain from recall
  [1, 1]    K          — Recall fraction
  [1, 2]    L          — Strategy ranking at 3 memory sizes

Encoding: color = strategy, marker shape = recall mode.
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.lines as mlines
import matplotlib.ticker as mticker
from pathlib import Path

# -- Config ---------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR      = SCRIPT_DIR / "data"
RESULTS_FILE  = DATA_DIR / "experiment2_search_proof_results.json"
PHASE_FILE    = DATA_DIR / "experiment2_phase_transition_results.json"
CROSS_FILE    = DATA_DIR / "experiment3_cross_recall_results.json"
FIGURE_DATA   = DATA_DIR / "figure_data.json"
FIGS_DIR      = SCRIPT_DIR / "figs"
OUTPUT_PNG    = FIGS_DIR / "experiment2_search_proof_comprehensive.png"
OUTPUT_PDF    = FIGS_DIR / "experiment2_search_proof_comprehensive.pdf"

print("Loading results...")
with open(RESULTS_FILE, 'r') as f:
    results = json.load(f)

phase_data = None
if PHASE_FILE.exists():
    print("Loading phase transition results...")
    with open(PHASE_FILE, 'r') as f:
        phase_data = json.load(f)

cross_data = None
if CROSS_FILE.exists():
    print("Loading cross-recall results...")
    with open(CROSS_FILE, 'r') as f:
        cross_data = json.load(f)

cost_data = None
COST_FILE = DATA_DIR / "experiment2_cost_budget_results.json"
if COST_FILE.exists():
    print("Loading cost-budget results...")
    with open(COST_FILE, 'r') as f:
        cost_data = json.load(f)

print("Creating distilled visualization...")

# -- Font scale ----------------------------------------------------------------
S = 1.82

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.linewidth': 0.8,
    'axes.edgecolor': '#444444',
    'grid.alpha': 0.08,
    'grid.linewidth': 0.3,
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'xtick.major.size': 4,
    'ytick.major.size': 4,
})

# Strategy colors
SC = {'bfs': '#1a1a1a', 'dfs': '#2D8A6E', 'random': '#4A90D9', 'greedy': '#D94A4A'}
SL = {'bfs': 'BFS', 'dfs': 'DFS', 'random': 'Random', 'greedy': 'Greedy'}

# Recall-mode marker shapes
RM_MARKER = {'none': 'o', 'matched': 's', 'hub': '^', 'hub_local': 'v'}
RM_SIZE   = {'none': 40,  'matched': 50,  'hub': 55,  'hub_local': 55}
RM_LABEL  = {'none': 'No recall', 'matched': 'Matched recall',
             'hub': 'Hub global (oracle)', 'hub_local': 'Hub local (realistic)'}

ACCENT = '#C04040'
BG_NOTE = dict(boxstyle='round,pad=0.4', facecolor='#F7F7F7', edgecolor='#CCC', alpha=0.93)


def style_ax(ax, title, xlabel='', ylabel=''):
    ax.set_title(title, fontsize=14*S, fontweight='bold', pad=8, loc='left')
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10*S, labelpad=4)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10*S, labelpad=4)
    ax.tick_params(labelsize=9*S)
    ax.grid(True, alpha=0.08, linewidth=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


def note(ax, x, y, text, fontsize=None, ha='left', va='top'):
    if fontsize is None:
        fontsize = 9 * S
    ax.text(x, y, text, transform=ax.transAxes, fontsize=fontsize,
            family='monospace', color='#333', ha=ha, va=va, bbox=BG_NOTE,
            linespacing=1.5)


def k_formatter(x, p):
    # K > corpus size (99,412) is meaningless — cap display at 100k
    if x >= 100000: return '100k'
    if x >= 1000:   return f'{int(x/1000)}k'
    return f'{int(x)}'


# -- Figure layout: 2 rows x 3 columns -----------------------------------------
fig = plt.figure(figsize=(42, 24), facecolor='white')
gs = GridSpec(2, 3, figure=fig, hspace=0.32, wspace=0.26,
              left=0.05, right=0.97, top=0.93, bottom=0.05)

fig.text(0.50, 0.975, 'Discovery Dynamics in the Adjacent Possible',
         fontsize=26*S, fontweight='bold', ha='center')
fig.text(0.50, 0.955,
         'Mathlib  |  99,412 theorems  |  48,081 roots  |  '
         'Theorem-Theorem DAG  |  4 strategies  ×  3 recall modes  ×  14 memory sizes (K=50..100k)',
         fontsize=10*S, ha='center', color='#666')

root_count = phase_data['root_count'] if phase_data else 48081
N          = phase_data['total_theorems'] if phase_data else 99412
baseline   = root_count / N


# ==============================================================================
# PANEL C: Dilution  [row 0, col 2]
# ==============================================================================

ax_c = fig.add_subplot(gs[0, 2])

dilution_dist = results['experiment2_accessibility']['dilution_distribution']
mean_dil      = results['experiment2_accessibility']['dilution_stats']['mean']
access_dist   = results['experiment2_accessibility']['accessibility_distribution']
mean_acc      = results['experiment2_accessibility']['accessibility_stats']['mean']

ax_c.hist(dilution_dist, bins=50, edgecolor='#555', linewidth=0.5,
          color='#E0E0E0', alpha=0.9, zorder=2)
ax_c.axvline(mean_dil, color=ACCENT, linestyle='--', linewidth=2.0, zorder=3,
             label=f'Mean: {mean_dil:,.0f}')
ax_c.set_xscale('log')
style_ax(ax_c, 'C.  Dilution: "Hiding in Plain Sight"',
         '|A(t)| at Entry', 'Theorems')
ax_c.legend(fontsize=9*S, frameon=True, edgecolor='#CCC', fancybox=False)

# Accessibility inset
ax_ins = ax_c.inset_axes([0.52, 0.45, 0.45, 0.48])
ax_ins.hist(access_dist, bins=30, edgecolor='#555', linewidth=0.4,
            color='#D8D8D8', alpha=0.9)
ax_ins.axvline(mean_acc, color=ACCENT, linestyle='--', linewidth=1.2)
ax_ins.set_title(f'Accessibility Time (mean={mean_acc:.1f} steps)', fontsize=7*S, pad=3)
ax_ins.set_xlabel('BFS steps to become provable', fontsize=6*S)
ax_ins.tick_params(labelsize=6*S)
ax_ins.spines['top'].set_visible(False)
ax_ins.spines['right'].set_visible(False)

note(ax_c, 0.03, 0.38,
     'DILUTION EFFECT\n'
     f'Mean dilution: {mean_dil:,.0f}\n'
     f'Max dilution: {max(dilution_dist):,.0f}\n\n'
     f'Most theorems provable in\n'
     f'{mean_acc:.1f} BFS steps (shallow)\n'
     f'but hidden among ~10k\n'
     f'competing alternatives.')


# ==============================================================================
# PANEL EFG: Merged phase transition  [row 0, cols 0–1]
# ==============================================================================

ax_efg = fig.add_subplot(gs[0, 0:2])

if phase_data is not None:
    max_b = str(max(phase_data['budgets']))
    bl    = phase_data['baseline_coverage']

    ax_efg.axhline(bl, color='#CCC', linewidth=1.0, linestyle='-', alpha=0.5, zorder=1)
    ax_efg.text(55, bl - 0.015, f'baseline {bl:.1%}', fontsize=8*S, color='#AAA', va='top')

    # Convergence marker at K≈30k
    ax_efg.axvline(30000, color='#AAAAAA', linewidth=1.2, linestyle=':', alpha=0.7, zorder=2)
    ax_efg.text(30000 * 1.08, 0.455, 'K≈30k', fontsize=8*S, color='#999', va='bottom')

    for strat in phase_data['strategies']:
        for rm in ['none', 'matched', 'hub', 'hub_local']:
            key = f"{strat}__{rm}"
            entries = phase_data['results'].get(key, [])
            if not entries:
                continue
            ks   = [e['memory_size'] for e in entries]
            covs = [e['by_budget'].get(max_b, {}).get('coverage', 0) for e in entries]
            ax_efg.scatter(ks, covs,
                           color=SC[strat],
                           marker=RM_MARKER[rm],
                           s=RM_SIZE[rm] * S,
                           alpha=0.82, zorder=4,
                           edgecolors='none')

    # --- Cost-constrained overlay (experiment2_cost_budget.py) ---------------
    if cost_data is not None:
        _COST_SC = {'min_cost': '#9B59B6', 'efficient': '#E67E22'}
        for strat in cost_data['strategies']:
            for rm in cost_data['recall_modes']:
                key = f"{strat}__{rm}"
                entries = cost_data['results'].get(key, [])
                if not entries:
                    continue
                ks   = [e['memory_size'] for e in entries]
                covs = [e['coverage']    for e in entries]
                if strat in SC:
                    # existing strategy under cost budget: hollow diamond
                    ax_efg.scatter(ks, covs,
                                   marker='D', s=52 * S,
                                   facecolors='none',
                                   edgecolors=SC[strat],
                                   linewidths=1.2,
                                   alpha=0.72, zorder=5)
                elif strat == 'min_cost':
                    ax_efg.scatter(ks, covs,
                                   marker='P', s=60 * S,
                                   color=_COST_SC['min_cost'],
                                   alpha=0.82, zorder=5)
                elif strat == 'efficient':
                    ax_efg.scatter(ks, covs,
                                   marker='h', s=60 * S,
                                   color=_COST_SC['efficient'],
                                   alpha=0.82, zorder=5)

    style_ax(ax_efg, 'E–G.  Memory Phase Transition — All Recall Modes (@60k budget)',
             'Memory Size K', 'Coverage')
    ax_efg.set_xscale('log')
    ax_efg.set_ylim(0.44, 1.03)
    ax_efg.set_xlim(40, 130000)
    ax_efg.xaxis.set_major_formatter(mticker.FuncFormatter(k_formatter))
    ax_efg.axhspan(bl, 1.0, alpha=0.008, color='green', zorder=0)

    # Two legends: strategy (color) and recall mode (marker shape)
    strat_handles = [mlines.Line2D([], [], color=SC[s], marker='o', linestyle='none',
                                   markersize=9*S, label=SL[s])
                     for s in phase_data['strategies']]
    if cost_data is not None:
        strat_handles += [
            mlines.Line2D([], [], color='#9B59B6', marker='P', linestyle='none',
                          markersize=9*S, label='min_cost (cost-budget)'),
            mlines.Line2D([], [], color='#E67E22', marker='h', linestyle='none',
                          markersize=9*S, label='efficient (cost-budget)'),
        ]
    rm_handles = [mlines.Line2D([], [], color='#555', marker=RM_MARKER[rm], linestyle='none',
                                markersize=9*S, label=RM_LABEL[rm])
                  for rm in ['none', 'matched', 'hub', 'hub_local']]

    leg1 = ax_efg.legend(handles=strat_handles, loc='upper left', fontsize=9*S,
                         frameon=True, edgecolor='#CCC', fancybox=False,
                         title='Strategy', title_fontsize=9*S)
    ax_efg.add_artist(leg1)
    if cost_data is not None:
        cost_hdl = [
            mlines.Line2D([], [], color='#555', marker='D', linestyle='none',
                          markersize=9*S, markerfacecolor='none', markeredgewidth=1.2,
                          label='Cost-budget run\n(hollow = existing strat)'),
        ]
        leg3 = ax_efg.legend(handles=cost_hdl, loc='lower left', fontsize=8*S,
                             frameon=True, edgecolor='#CCC', fancybox=False,
                             title='Cost Model', title_fontsize=8*S)
        ax_efg.add_artist(leg3)
    ax_efg.legend(handles=rm_handles, loc='lower right', fontsize=9*S,
                  frameon=True, edgecolor='#CCC', fancybox=False,
                  title='Recall Mode', title_fontsize=9*S)

    note(ax_efg, 0.38, 0.97,
         'ORACLE vs REALISTIC HUB RECALL\n'
         '▲ hub_global (oracle out-degree)\n'
         '▽ hub_local  (visible subgraph only)\n'
         '■ matched  ● none\n\n'
         'NOTE: ■ matched hides 4 strategies:\n'
         '  BFS=FIFO  DFS=LIFO\n'
         '  Random=random  Greedy=unblock\n'
         'Only Greedy matched is real planning.\n\n'
         'All strategies converge below K≈30k.')

    if cost_data is not None:
        note(ax_efg, 0.03, 0.60,
             'COST MODEL (fix.md)\n'
             'cost_per_step = max(1, K)\n'
             'budget = 60M comp-equiv.\n'
             'K=1k -> 60k steps (same)\n'
             'K=10k -> 6k steps\n'
             'K=30k -> 2k steps\n\n'
             'hollow diamonds: existing\n'
             'strats, cost-scaled budget\n'
             '+ min_cost: fewest prereqs\n'
             'hex efficient: gain/cost')

else:
    ax_efg.axis('off')
    ax_efg.text(0.5, 0.5, "Run experiment2_phase_transition.py first",
                transform=ax_efg.transAxes, fontsize=14*S, ha='center')


# ==============================================================================
# ROW 2: J, K, L
# ==============================================================================

if phase_data is not None:
    max_b   = str(max(phase_data['budgets']))
    recalls = phase_data['recall_modes']

    # -- J: Coverage Gain from Recall  [row 1, col 0] --------------------------
    ax_j = fig.add_subplot(gs[1, 0])

    for strat in phase_data['strategies']:
        none_entries = phase_data['results'].get(f"{strat}__none", [])
        if not none_entries:
            continue
        ks = [e['memory_size'] for e in none_entries]
        for rm, mk, sz, al in [('matched', 's', 55, 0.85),
                                ('hub',       '^', 60, 0.75),
                                ('hub_local', 'v', 60, 0.70)]:
            rm_entries = phase_data['results'].get(f"{strat}__{rm}", [])
            if not rm_entries:
                continue
            gains = []
            for i in range(len(ks)):
                cn = none_entries[i]['by_budget'].get(max_b, {}).get('coverage', 0)
                cr = rm_entries[i]['by_budget'].get(max_b, {}).get('coverage', 0)
                gains.append(cr - cn)
            ax_j.scatter(ks, gains, color=SC[strat], marker=mk, s=sz*S,
                         alpha=al, zorder=4, edgecolors='none')

    style_ax(ax_j, 'J.  Coverage Gain from Recall (@60k)',
             'Memory Size K', 'Coverage Gain (vs no-recall)')
    ax_j.set_xscale('log')
    ax_j.set_xlim(40, 130000)
    ax_j.xaxis.set_major_formatter(mticker.FuncFormatter(k_formatter))
    ax_j.axhline(0, color='#CCC', linewidth=1.0, alpha=0.5)

    j_handles  = [mlines.Line2D([], [], color=SC[s], marker='o', linestyle='none',
                                markersize=8*S, label=SL[s])
                  for s in phase_data['strategies']]
    j_handles += [mlines.Line2D([], [], color='#555', marker='s', linestyle='none', markersize=8*S, label='Matched'),
                  mlines.Line2D([], [], color='#555', marker='^', linestyle='none', markersize=8*S, label='Hub global'),
                  mlines.Line2D([], [], color='#555', marker='v', linestyle='none', markersize=8*S, label='Hub local')]
    ax_j.legend(handles=j_handles, fontsize=7.5*S, loc='upper right',
                frameon=True, edgecolor='#CCC', fancybox=False, ncol=2)

    note(ax_j, 0.03, 0.98,
         'ORACLE vs REALISTIC GAIN\n'
         '■ matched  ▲ hub_global  ▽ hub_local\n\n'
         'Gap ▲ vs ▽ = oracle information\n'
         'premium. If small: hub strategy\n'
         'is robust. If large: original\n'
         'finding was an artifact.\n\n'
         'Peak gain at mid-K (5k–50k).')

    # -- K: Recall Fraction  [row 1, col 1] ------------------------------------
    ax_k = fig.add_subplot(gs[1, 1])

    for strat in phase_data['strategies']:
        for rm, mk, sz, al in [('matched',   's', 55, 0.85),
                                ('hub',       '^', 60, 0.70),
                                ('hub_local', 'v', 60, 0.65)]:
            entries = phase_data['results'].get(f"{strat}__{rm}", [])
            if not entries:
                continue
            ks    = [e['memory_size'] for e in entries]
            fracs = []
            for e in entries:
                d     = e['by_budget'].get(max_b, {})
                disc  = d.get('discoveries', 0)
                rec   = d.get('recalls', 0)
                total = disc + rec
                fracs.append(rec / total if total > 0 else 0)
            ax_k.scatter(ks, fracs, color=SC[strat], marker=mk, s=sz*S,
                         alpha=al, edgecolors='none')

    style_ax(ax_k, 'K.  Recall Fraction (@60k budget)',
             'Memory Size K', 'Recalls / Total Steps')
    ax_k.set_xscale('log')
    ax_k.set_xlim(40, 130000)
    ax_k.set_ylim(-0.02, 1.02)
    ax_k.xaxis.set_major_formatter(mticker.FuncFormatter(k_formatter))

    k_handles  = [mlines.Line2D([], [], color=SC[s], marker='o', linestyle='none',
                                markersize=8*S, label=SL[s])
                  for s in phase_data['strategies']]
    k_handles += [mlines.Line2D([], [], color='#555', marker='s', linestyle='none', markersize=8*S, label='Matched'),
                  mlines.Line2D([], [], color='#555', marker='^', linestyle='none', markersize=8*S, label='Hub global'),
                  mlines.Line2D([], [], color='#555', marker='v', linestyle='none', markersize=8*S, label='Hub local')]
    ax_k.legend(handles=k_handles, fontsize=7.5*S, loc='center right',
                frameon=True, edgecolor='#CCC', fancybox=False, ncol=1)

    note(ax_k, 0.03, 0.98,
         'RECALL OVERHEAD\n'
         '■ matched  ▲ hub_global  ▽ hub_local\n\n'
         'Small K: 80–95% of steps are\n'
         'recalls (memory overflows fast,\n'
         'agent constantly re-fetching).\n\n'
         'Large K: 0% recalls (memory\n'
         'holds everything needed).\n\n'
         'Crossover at K~30k–50k: where\n'
         'recall transitions from burden\n'
         'to unnecessary.')

    # -- L: Cross-recall heatmap (exp3) or strategy ranking bar (fallback) ----
    ax_l = fig.add_subplot(gs[1, 2])

    if cross_data is not None:
        # Heatmap: 4 strategies × 6 recall modes, coverage at K=10k
        target_K   = 10000
        strats_c   = cross_data['strategies']
        rms_c      = cross_data['recall_modes']
        RM_LABELS_C = {
            'none':         'none',
            'fifo':         'FIFO\n(BFS-style)',
            'lifo':         'LIFO\n(DFS-style)',
            'random_recall':'random',
            'unblock':      'unblock\n(greedy-style)',
            'hub_local':    'hub_local',
        }

        matrix = []
        for strat in strats_c:
            row = []
            for rm in rms_c:
                key     = f"{strat}__{rm}"
                entries = cross_data['results'].get(key, [])
                entry   = next((e for e in entries if e['K'] == target_K), None)
                row.append(entry['coverage'] if entry else 0)
            matrix.append(row)
        matrix = np.array(matrix)

        im = ax_l.imshow(matrix, cmap='YlOrRd', aspect='auto', vmin=0.48, vmax=1.0)
        ax_l.set_xticks(range(len(rms_c)))
        ax_l.set_xticklabels([RM_LABELS_C[r] for r in rms_c], fontsize=6.5*S)
        ax_l.set_yticks(range(len(strats_c)))
        ax_l.set_yticklabels([SL[s] for s in strats_c], fontsize=8*S)

        for i in range(len(strats_c)):
            for j in range(len(rms_c)):
                val   = matrix[i, j]
                color = 'white' if val > 0.72 else '#333'
                ax_l.text(j, i, f'{val:.2f}', ha='center', va='center',
                          fontsize=6.5*S, color=color, fontweight='bold')

        cbar = fig.colorbar(im, ax=ax_l, fraction=0.046, pad=0.04, shrink=0.8)
        cbar.ax.tick_params(labelsize=7*S)
        cbar.set_label('Coverage', fontsize=8*S)

        ax_l.set_title(f'L.  Cross-Recall Heatmap (K={target_K:,}, @60k)',
                       fontsize=14*S, fontweight='bold', pad=8, loc='left')
        ax_l.spines['top'].set_visible(False)
        ax_l.spines['right'].set_visible(False)

        note(ax_l, 0.01, 0.28,
             'KEY: unblock recall\n'
             'helps ALL strategies,\n'
             'not just greedy.\n'
             'Recall strategy matters\n'
             'more than exploration.')

    else:
        # Fallback: strategy ranking bar chart
        key_ks  = [500, 5000, 50000]
        k_names = ['K=500\n(tiny)', 'K=5k\n(medium)', 'K=50k\n(large)']
        bar_width   = 0.18
        x_positions = np.arange(len(key_ks))

        for si, strat in enumerate(phase_data['strategies']):
            best_covs = []
            for tk in key_ks:
                best_cov = 0
                for rm in recalls:
                    entries = phase_data['results'].get(f"{strat}__{rm}", [])
                    if entries:
                        entry = min(entries, key=lambda e: abs(e['memory_size'] - tk))
                        c = entry['by_budget'].get(max_b, {}).get('coverage', 0)
                        best_cov = max(best_cov, c)
                best_covs.append(best_cov)

            offset = (si - 1.5) * bar_width
            bars = ax_l.bar(x_positions + offset, best_covs, bar_width * 0.9,
                            color=SC[strat], alpha=0.8, edgecolor='#333', linewidth=0.5,
                            label=SL[strat])
            for bar, cov in zip(bars, best_covs):
                ax_l.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.008,
                          f'{cov:.0%}', ha='center', va='bottom', fontsize=7*S,
                          color=SC[strat], fontweight='bold')

        ax_l.axhline(baseline, color='#CCC', linewidth=1.0, linestyle='--', alpha=0.6)
        ax_l.text(2.5, baseline + 0.008, f'baseline {baseline:.1%}',
                  fontsize=7.5*S, color='#AAA', ha='right')
        ax_l.set_xticks(x_positions)
        ax_l.set_xticklabels(k_names, fontsize=9*S)
        ax_l.set_ylim(0.44, 1.05)
        style_ax(ax_l, 'L.  Best Coverage by Strategy × Memory',
                 '', 'Coverage (best recall mode)')
        ax_l.legend(fontsize=9*S, loc='upper left', frameon=True, edgecolor='#CCC',
                    fancybox=False, ncol=2)
        note(ax_l, 0.03, 0.55,
             'Run experiment3_cross_recall.py\n'
             'to unlock the cross-recall\n'
             'heatmap panel.')

else:
    for col in range(3):
        ax = fig.add_subplot(gs[1, col])
        ax.axis('off')
        ax.text(0.5, 0.5, "Run experiment2_phase_transition.py first",
                transform=ax.transAxes, fontsize=14*S, ha='center')


# ==============================================================================
# EXPORT FIGURE DATA (all plotted values → data/figure_data.json)
# ==============================================================================

figure_data = {
    "meta": {
        "description": "All data plotted in experiment2_search_proof_comprehensive figures",
        "panels": ["C", "EFG", "J", "K", "L"],
        "encoding": "color=strategy, marker=recall_mode (o=none, s=matched, ^=hub_global, v=hub_local)",
        "budget_shown": max_b if phase_data else None,
    },

    # Panel C — histogram probabilities (not raw data) -----------------------
    "panel_C_dilution": (lambda: {
        "dilution_histogram": dict(zip(
            ["bin_edges", "probabilities"],
            [arr.tolist() for arr in (lambda c, e: (e, c / c.sum()))(
                *np.histogram(dilution_dist, bins=50))]
        )),
        "dilution_mean": mean_dil,
        "dilution_max": float(max(dilution_dist)),
        "dilution_xscale": "log",
        "accessibility_histogram": dict(zip(
            ["bin_edges", "probabilities"],
            [arr.tolist() for arr in (lambda c, e: (e, c / c.sum()))(
                *np.histogram(access_dist, bins=30))]
        )),
        "accessibility_mean": mean_acc,
    })(),
}

if phase_data is not None:
    max_b_int = max(phase_data['budgets'])
    max_b_str = str(max_b_int)

    # Panel EFG --------------------------------------------------------------
    efg = {}
    for strat in phase_data['strategies']:
        for rm in ['none', 'matched', 'hub', 'hub_local']:
            key = f"{strat}__{rm}"
            entries = phase_data['results'].get(key, [])
            if entries:
                efg[key] = {
                    "K": [e['memory_size'] for e in entries],
                    "coverage": [e['by_budget'].get(max_b_str, {}).get('coverage', 0)
                                 for e in entries],
                }
    figure_data["panel_EFG_phase_transition"] = {
        "budget": max_b_int,
        "baseline_coverage": phase_data['baseline_coverage'],
        "series": efg,
    }

    # Panel EFG cost-budget overlay ------------------------------------------
    if cost_data is not None:
        cost_efg = {}
        for strat in cost_data['strategies']:
            for rm in cost_data['recall_modes']:
                key = f"{strat}__{rm}"
                entries = cost_data['results'].get(key, [])
                if entries:
                    cost_efg[key] = {
                        "K":            [e['memory_size']  for e in entries],
                        "coverage":     [e['coverage']     for e in entries],
                        "steps_budget": [e['steps_budget'] for e in entries],
                        "discoveries":  [e['discoveries']  for e in entries],
                    }
        figure_data["panel_EFG_cost_budget"] = {
            "cost_model":       cost_data.get('cost_model', 'cost_per_step = max(1, K)'),
            "time_budget":      cost_data.get('time_budget'),
            "norm_k":           cost_data.get('norm_k'),
            "baseline_coverage": cost_data.get('baseline_coverage'),
            "series": cost_efg,
        }

    # Panel J ----------------------------------------------------------------
    j_data = {}
    for strat in phase_data['strategies']:
        none_entries = phase_data['results'].get(f"{strat}__none", [])
        if not none_entries:
            continue
        ks = [e['memory_size'] for e in none_entries]
        j_data[strat] = {"K": ks}
        for rm in ['matched', 'hub', 'hub_local']:
            rm_entries = phase_data['results'].get(f"{strat}__{rm}", [])
            if rm_entries:
                j_data[strat][f"gain_{rm}"] = [
                    rm_entries[i]['by_budget'].get(max_b_str, {}).get('coverage', 0)
                    - none_entries[i]['by_budget'].get(max_b_str, {}).get('coverage', 0)
                    for i in range(len(ks))
                ]
    figure_data["panel_J_recall_gain"] = {"budget": max_b_int, "series": j_data}

    # Panel K ----------------------------------------------------------------
    k_data = {}
    for strat in phase_data['strategies']:
        k_data[strat] = {}
        for rm in ['matched', 'hub', 'hub_local']:
            entries = phase_data['results'].get(f"{strat}__{rm}", [])
            if not entries:
                continue
            ks, fracs = [], []
            for e in entries:
                d = e['by_budget'].get(max_b_str, {})
                disc = d.get('discoveries', 0)
                rec  = d.get('recalls', 0)
                total = disc + rec
                ks.append(e['memory_size'])
                fracs.append(rec / total if total > 0 else 0)
            k_data[strat][rm] = {"K": ks, "recall_fraction": fracs}
    figure_data["panel_K_recall_fraction"] = {"budget": max_b_int, "series": k_data}

    # Panel L ----------------------------------------------------------------
    key_ks  = [500, 5000, 50000]
    l_data  = {}
    for strat in phase_data['strategies']:
        l_data[strat] = {}
        for tk in key_ks:
            best_cov = 0
            best_rm  = None
            for rm in phase_data['recall_modes']:
                entries = phase_data['results'].get(f"{strat}__{rm}", [])
                if entries:
                    entry = min(entries, key=lambda e: abs(e['memory_size'] - tk))
                    c = entry['by_budget'].get(max_b_str, {}).get('coverage', 0)
                    if c > best_cov:
                        best_cov, best_rm = c, rm
            l_data[strat][str(tk)] = {"best_coverage": best_cov, "best_recall_mode": best_rm}
    figure_data["panel_L_strategy_ranking"] = {
        "budget": max_b_int,
        "K_values": key_ks,
        "baseline": phase_data['baseline_coverage'],
        "series": l_data,
    }

    # Panel L (cross-recall heatmap) -----------------------------------------
    if cross_data is not None:
        target_K = 10000
        l_cross  = {}
        for strat in cross_data['strategies']:
            l_cross[strat] = {}
            for rm in cross_data['recall_modes']:
                key     = f"{strat}__{rm}"
                entries = cross_data['results'].get(key, [])
                entry   = next((e for e in entries if e['K'] == target_K), None)
                l_cross[strat][rm] = entry['coverage'] if entry else None
        figure_data["panel_L_cross_recall_heatmap"] = {
            "K": target_K,
            "budget": cross_data['budget'],
            "baseline": cross_data['baseline_coverage'],
            "recall_mode_descriptions": cross_data['recall_mode_descriptions'],
            "coverage_by_strategy_and_mode": l_cross,
        }

DATA_DIR.mkdir(exist_ok=True)
with open(FIGURE_DATA, 'w') as f:
    json.dump(figure_data, f, indent=2)
print(f"Saved figure data: {FIGURE_DATA}")


# ==============================================================================
# SAVE
# ==============================================================================

FIGS_DIR.mkdir(exist_ok=True)
plt.savefig(OUTPUT_PNG, dpi=150, bbox_inches='tight', facecolor='white')
print(f"Saved: {OUTPUT_PNG}")

plt.savefig(OUTPUT_PDF, bbox_inches='tight', facecolor='white')
print(f"Saved: {OUTPUT_PDF}")

plt.close()
print("Done!")
