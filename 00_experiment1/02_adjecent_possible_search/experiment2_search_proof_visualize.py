"""
Discovery Dynamics — Distilled 5-Panel Figure (v4)

Layout: 2 rows x 3 columns
  [0, 0:2]  EFG merged — Memory phase transition, all recall modes overlaid
  [0, 2]    C          — Dilution histogram
  [1, 0]    J          — Coverage gain from recall
  [1, 1]    K          — Recall fraction
  [1, 2]    L          — Strategy ranking at 3 memory sizes

Encoding: color = strategy, linestyle = recall mode (merged EFG panel only).
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
RESULTS_FILE = SCRIPT_DIR / "experiment2_search_proof_results.json"
PHASE_FILE = SCRIPT_DIR / "experiment2_phase_transition_results.json"
FIGS_DIR = SCRIPT_DIR / "figs"
OUTPUT_PNG = FIGS_DIR / "experiment2_search_proof_comprehensive.png"
OUTPUT_PDF = FIGS_DIR / "experiment2_search_proof_comprehensive.pdf"

print("Loading results...")
with open(RESULTS_FILE, 'r') as f:
    results = json.load(f)

phase_data = None
if PHASE_FILE.exists():
    print("Loading phase transition results...")
    with open(PHASE_FILE, 'r') as f:
        phase_data = json.load(f)

print("Creating distilled visualization...")

# -- Font scale ----------------------------------------------------------------
S = 1.4

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

# Recall-mode linestyles
RM_LS    = {'none': '-',  'matched': '--', 'hub': ':'}
RM_LW    = {'none': 1.6,  'matched': 2.0,  'hub': 2.5}
RM_LABEL = {'none': 'No recall', 'matched': 'Matched recall', 'hub': 'Hub recall'}

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
    return '$\\infty$' if x >= 500000 else f'{int(x):,}'


# -- Figure layout: 2 rows x 3 columns -----------------------------------------
fig = plt.figure(figsize=(42, 24), facecolor='white')
gs = GridSpec(2, 3, figure=fig, hspace=0.32, wspace=0.26,
              left=0.05, right=0.97, top=0.93, bottom=0.05)

fig.text(0.50, 0.975, 'Discovery Dynamics in the Adjacent Possible',
         fontsize=26*S, fontweight='bold', ha='center')
fig.text(0.50, 0.955,
         'Mathlib  |  99,412 theorems  |  48,081 roots  |  '
         'Theorem-Theorem DAG  |  4 strategies  ×  3 recall modes  ×  17 memory sizes',
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
        for rm in ['none', 'matched', 'hub']:
            key = f"{strat}__{rm}"
            entries = phase_data['results'].get(key, [])
            if not entries:
                continue
            ks   = [e['memory_size'] for e in entries]
            covs = [e['by_budget'].get(max_b, {}).get('coverage', 0) for e in entries]
            ax_efg.plot(ks, covs,
                        color=SC[strat],
                        linestyle=RM_LS[rm],
                        linewidth=RM_LW[rm] * S,
                        alpha=0.82, zorder=4)

    style_ax(ax_efg, 'E–G.  Memory Phase Transition — All Recall Modes (@60k budget)',
             'Memory Size K', 'Coverage')
    ax_efg.set_xscale('log')
    ax_efg.set_ylim(0.44, 1.03)
    ax_efg.set_xlim(40, 1500000)
    ax_efg.xaxis.set_major_formatter(mticker.FuncFormatter(k_formatter))
    ax_efg.axhspan(bl, 1.0, alpha=0.008, color='green', zorder=0)

    # Two legends: strategy (color) and recall mode (linestyle)
    strat_handles = [mlines.Line2D([], [], color=SC[s], linewidth=2.5*S, label=SL[s])
                     for s in phase_data['strategies']]
    rm_handles = [mlines.Line2D([], [], color='#555',
                                linewidth=RM_LW[rm]*S, linestyle=RM_LS[rm],
                                label=RM_LABEL[rm])
                  for rm in ['none', 'matched', 'hub']]

    leg1 = ax_efg.legend(handles=strat_handles, loc='upper left', fontsize=9*S,
                         frameon=True, edgecolor='#CCC', fancybox=False,
                         title='Strategy', title_fontsize=9*S, handlelength=1.5)
    ax_efg.add_artist(leg1)
    ax_efg.legend(handles=rm_handles, loc='lower right', fontsize=9*S,
                  frameon=True, edgecolor='#CCC', fancybox=False,
                  title='Recall Mode', title_fontsize=9*S, handlelength=2.8)

    note(ax_efg, 0.38, 0.97,
         'HUB RECALL SHIFTS S-CURVE LEFT\n'
         'Dotted > dashed > solid: adding hub recall\n'
         'closes half the gap to ceiling at mid-K.\n\n'
         'All strategies converge below K≈30k\n'
         '— memory is the binding constraint,\n'
         'not exploration strategy.')

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
        none_entries    = phase_data['results'].get(f"{strat}__none", [])
        matched_entries = phase_data['results'].get(f"{strat}__matched", [])
        hub_entries     = phase_data['results'].get(f"{strat}__hub", [])
        if not (none_entries and matched_entries and hub_entries):
            continue

        ks = [e['memory_size'] for e in none_entries]
        gain_matched, gain_hub = [], []
        for i in range(len(ks)):
            cn = none_entries[i]['by_budget'].get(max_b, {}).get('coverage', 0)
            cm = matched_entries[i]['by_budget'].get(max_b, {}).get('coverage', 0)
            ch = hub_entries[i]['by_budget'].get(max_b, {}).get('coverage', 0)
            gain_matched.append(cm - cn)
            gain_hub.append(ch - cn)

        ax_j.plot(ks, gain_matched, color=SC[strat], linewidth=2.5, linestyle='-',  zorder=4)
        ax_j.plot(ks, gain_hub,     color=SC[strat], linewidth=1.6, linestyle='--', alpha=0.7, zorder=3)

    style_ax(ax_j, 'J.  Coverage Gain from Recall (@60k)',
             'Memory Size K', 'Coverage Gain (vs no-recall)')
    ax_j.set_xscale('log')
    ax_j.set_xlim(40, 1500000)
    ax_j.xaxis.set_major_formatter(mticker.FuncFormatter(k_formatter))
    ax_j.axhline(0, color='#CCC', linewidth=1.0, alpha=0.5)

    j_handles  = [mlines.Line2D([], [], color=SC[s], linewidth=2, label=SL[s])
                  for s in phase_data['strategies']]
    j_handles += [mlines.Line2D([], [], color='#555', linewidth=2,               label='Matched'),
                  mlines.Line2D([], [], color='#555', linewidth=1.3, linestyle='--', alpha=0.7, label='Hub')]
    ax_j.legend(handles=j_handles, fontsize=7.5*S, loc='upper right',
                frameon=True, edgecolor='#CCC', fancybox=False, ncol=2)

    note(ax_j, 0.03, 0.98,
         'RECALL BENEFIT\n'
         'Solid = strategy-matched recall\n'
         'Dashed = hub (out-degree) recall\n\n'
         'Peak gain at mid-K (5k–50k)\n'
         'where memory is tight but\n'
         'recall can still help.\n\n'
         'Hub recall gives larger gains\n'
         'than matched for most strategies.')

    # -- K: Recall Fraction  [row 1, col 1] ------------------------------------
    ax_k = fig.add_subplot(gs[1, 1])

    for strat in phase_data['strategies']:
        for rm, ls_style in [('matched', '-'), ('hub', '--')]:
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
            lw = 2.5 if rm == 'matched' else 1.4
            ax_k.plot(ks, fracs, color=SC[strat], linewidth=lw, linestyle=ls_style,
                      alpha=0.85 if rm == 'matched' else 0.6)

    style_ax(ax_k, 'K.  Recall Fraction (@60k budget)',
             'Memory Size K', 'Recalls / Total Steps')
    ax_k.set_xscale('log')
    ax_k.set_xlim(40, 1500000)
    ax_k.set_ylim(-0.02, 1.02)
    ax_k.xaxis.set_major_formatter(mticker.FuncFormatter(k_formatter))

    k_handles  = [mlines.Line2D([], [], color=SC[s], linewidth=2, label=SL[s])
                  for s in phase_data['strategies']]
    k_handles += [mlines.Line2D([], [], color='#555', linewidth=2,               label='Matched'),
                  mlines.Line2D([], [], color='#555', linewidth=1.3, linestyle='--', label='Hub')]
    ax_k.legend(handles=k_handles, fontsize=7.5*S, loc='center right',
                frameon=True, edgecolor='#CCC', fancybox=False, ncol=1)

    note(ax_k, 0.03, 0.98,
         'RECALL OVERHEAD\n'
         'Small K: 80–95% of steps are\n'
         'recalls (memory overflows fast,\n'
         'agent constantly re-fetching).\n\n'
         'Large K: 0% recalls (memory\n'
         'holds everything needed).\n\n'
         'Crossover at K~30k–50k: where\n'
         'recall transitions from burden\n'
         'to unnecessary.')

    # -- L: Strategy Ranking by K Region  [row 1, col 2] -----------------------
    ax_l = fig.add_subplot(gs[1, 2])

    key_ks   = [500, 5000, 50000]
    k_names  = ['K=500\n(tiny)', 'K=5k\n(medium)', 'K=50k\n(large)']
    bar_width = 0.18
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
    ax_l.text(2.5, baseline + 0.008, f'baseline {baseline:.1%}', fontsize=7.5*S,
              color='#AAA', ha='right')

    ax_l.set_xticks(x_positions)
    ax_l.set_xticklabels(k_names, fontsize=9*S)
    ax_l.set_ylim(0.44, 1.05)
    style_ax(ax_l, 'L.  Best Coverage by Strategy × Memory',
             '', 'Coverage (best recall mode)')
    ax_l.legend(fontsize=9*S, loc='upper left', frameon=True, edgecolor='#CCC',
                fancybox=False, ncol=2)

    note(ax_l, 0.38, 0.55,
         'KEY FINDING\n'
         'At small K: Greedy+recall\n'
         'wins (~55% vs 48% baseline).\n'
         'At large K: all strategies\n'
         'converge to ceiling.\n\n'
         'Strategy choice matters\n'
         'most when memory is scarce\n'
         '— the realistic regime\n'
         'for bounded agents.')

else:
    for col in range(3):
        ax = fig.add_subplot(gs[1, col])
        ax.axis('off')
        ax.text(0.5, 0.5, "Run experiment2_phase_transition.py first",
                transform=ax.transAxes, fontsize=14*S, ha='center')


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
