"""
Discovery Dynamics — Dense Multi-Panel Figure (v2)

Layout: 2 rows x 6 columns (12 panels, annotations inside plots)
Row 1: Exploration dynamics + gateway analysis
Row 2: Phase transitions + recall analysis

Figure: ~72" wide x 12" tall, super dense
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.lines as mlines
import matplotlib.ticker as mticker
import matplotlib.colors as mcolors
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

print("Creating comprehensive visualization...")

# -- Style ----------------------------------------------------------------------
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.linewidth': 0.7,
    'axes.edgecolor': '#444444',
    'grid.alpha': 0.08,
    'grid.linewidth': 0.3,
    'xtick.major.width': 0.5,
    'ytick.major.width': 0.5,
    'xtick.major.size': 3,
    'ytick.major.size': 3,
})

# Strategy colors
SC = {'bfs': '#1a1a1a', 'dfs': '#2D8A6E', 'random': '#4A90D9', 'greedy': '#D94A4A'}
SL = {'bfs': 'BFS', 'dfs': 'DFS', 'random': 'Random', 'greedy': 'Greedy'}

# Budget linestyles
BLS = {
    '1000':  {'lw': 0.8, 'ls': (0, (1, 2)),      'label': '1k'},
    '5000':  {'lw': 1.1, 'ls': (0, (4, 2)),       'label': '5k'},
    '20000': {'lw': 1.5, 'ls': (0, (4, 1, 1, 1)), 'label': '20k'},
    '60000': {'lw': 2.2, 'ls': '-',                'label': '60k'},
}

ACCENT = '#C04040'
BG_NOTE = dict(boxstyle='round,pad=0.25', facecolor='#FAFAFA', edgecolor='#DDD', alpha=0.92)


def style_ax(ax, title, xlabel='', ylabel='', title_size=9.5):
    ax.set_title(title, fontsize=title_size, fontweight='bold', pad=5, loc='left')
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=7.5, labelpad=3)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=7.5, labelpad=3)
    ax.tick_params(labelsize=6.5)
    ax.grid(True, alpha=0.08, linewidth=0.3)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


def note(ax, x, y, text, fontsize=6.5, ha='left', va='top'):
    """Place annotation text inside a plot."""
    ax.text(x, y, text, transform=ax.transAxes, fontsize=fontsize,
            family='monospace', color='#444', ha=ha, va=va, bbox=BG_NOTE,
            linespacing=1.4)


# -- Figure layout: 2 rows x 6 columns ----------------------------------------
fig = plt.figure(figsize=(72, 12), facecolor='white')
gs = GridSpec(2, 6, figure=fig, hspace=0.35, wspace=0.25,
              left=0.025, right=0.985, top=0.90, bottom=0.07)

fig.text(0.50, 0.965, 'Discovery Dynamics in the Adjacent Possible',
         fontsize=20, fontweight='bold', ha='center')
fig.text(0.50, 0.94, 'Mathlib  |  99,412 theorems  |  48,081 roots  |  Theorem-Theorem DAG  |  4 strategies x 3 recall modes x 17 memory sizes x 4 budgets',
         fontsize=8, ha='center', color='#777')

root_count = phase_data['root_count'] if phase_data else 48081
N = phase_data['total_theorems'] if phase_data else 99412


# ==============================================================================
# ROW 1: EXPLORATION DYNAMICS
# ==============================================================================

# -- A: |A_t| Possibility Space ------------------------------------------------
ax_a = fig.add_subplot(gs[0, 0])

bfs_data = results['experiment1_adjacent_possible']['bfs']
random_data = results['experiment1_adjacent_possible']['random']
greedy_data = results['experiment1_adjacent_possible']['greedy']
summary = results['experiment1_adjacent_possible']['summary']

for data, name in [(random_data, 'random'), (greedy_data, 'greedy'), (bfs_data, 'bfs')]:
    steps = [d['step'] for d in data]
    adj = [max(d['adjacent'], 1) for d in data]
    lw = 2.2 if name == 'bfs' else 1.4
    ax_a.plot(steps, adj, color=SC[name], linewidth=lw, alpha=0.85, label=SL[name])

ax_a.set_yscale('log')
style_ax(ax_a, 'A.  |A(t)| Possibility Space', 'Discovery Steps', '|A(t)|  (log)')
ax_a.legend(fontsize=6, loc='center right', frameon=True, edgecolor='#CCC',
            fancybox=False, handlelength=1.5)

note(ax_a, 0.03, 0.25,
     '|A(t)| explodes early then\n'
     'contracts as easy results\n'
     'exhaust. Peak ~15k options.\n'
     'BFS = Greedy trajectory.')


# -- B: Knowledge Accumulation -------------------------------------------------
ax_b = fig.add_subplot(gs[0, 1])

for data, name in [(random_data, 'random'), (greedy_data, 'greedy'), (bfs_data, 'bfs')]:
    steps = [d['step'] for d in data]
    known = [d['known'] for d in data]
    lw = 2.2 if name == 'bfs' else 1.4
    ax_b.plot(steps, known, color=SC[name], linewidth=lw, alpha=0.85, label=SL[name])

ax_b.axhline(N * 0.979, color='#AAA', linewidth=0.8, linestyle='--', alpha=0.5)
style_ax(ax_b, 'B.  Knowledge Accumulation', 'Discovery Steps', 'Known Theorems')
ax_b.legend(fontsize=6, loc='center right', frameon=True, edgecolor='#CCC', fancybox=False)

note(ax_b, 0.03, 0.98,
     f'BFS:    97.9% in 32 steps\n'
     f'Random: 97.9% in 49k steps\n'
     f'Greedy: 58.4% in 10k steps\n'
     f'Ceiling: 97.9% (2.1% orphans)')


# -- C: Dilution ---------------------------------------------------------------
ax_c = fig.add_subplot(gs[0, 2])

dilution_dist = results['experiment2_accessibility']['dilution_distribution']
mean_dil = results['experiment2_accessibility']['dilution_stats']['mean']

ax_c.hist(dilution_dist, bins=50, edgecolor='#555', linewidth=0.4,
          color='#E0E0E0', alpha=0.9, zorder=2)
ax_c.axvline(mean_dil, color=ACCENT, linestyle='--', linewidth=1.5, zorder=3)
ax_c.set_xscale('log')
style_ax(ax_c, 'C.  Dilution: "Hiding in Plain Sight"',
         '|A(t)| at Entry', 'Theorems')

# Accessibility inset
ax_ins = ax_c.inset_axes([0.50, 0.40, 0.47, 0.52])
access_dist = results['experiment2_accessibility']['accessibility_distribution']
mean_acc = results['experiment2_accessibility']['accessibility_stats']['mean']
ax_ins.hist(access_dist, bins=30, edgecolor='#555', linewidth=0.4, color='#D8D8D8', alpha=0.9)
ax_ins.axvline(mean_acc, color=ACCENT, linestyle='--', linewidth=1)
ax_ins.set_title(f'Accessibility (mean={mean_acc:.1f})', fontsize=6, pad=2)
ax_ins.set_xlabel('BFS steps', fontsize=5)
ax_ins.tick_params(labelsize=5)
ax_ins.spines['top'].set_visible(False)
ax_ins.spines['right'].set_visible(False)

note(ax_c, 0.03, 0.35,
     f'Mean dilution: {mean_dil:,.0f}\n'
     f'Theorems provable in\n'
     f'{mean_acc:.1f} BFS steps but\n'
     f'hidden among ~10k options')


# -- D: Gateway Removal Impact -------------------------------------------------
ax_d = fig.add_subplot(gs[0, 3])

removal_dist = results['experiment3_bottlenecks']['removal_impact_distribution']
mean_rem = results['experiment3_bottlenecks']['removal_impact_stats']['mean']

ax_d.hist(removal_dist, bins=50, edgecolor='#555', linewidth=0.4,
          color='#E0E0E0', alpha=0.9, zorder=2)
ax_d.axvline(mean_rem, color=ACCENT, linestyle='--', linewidth=1.5, zorder=3)
ax_d.set_yscale('log')
style_ax(ax_d, 'D.  Gateway Removal Impact', 'Fraction Unreachable', 'Count (log)')

note(ax_d, 0.40, 0.98,
     f'Mean impact: {mean_rem:.3f}\n'
     f'Most theorems: near-zero\n'
     f'Few critical gateways\n'
     f'Robust interconnection')


# -- E: Top 10 Gateways -------------------------------------------------------
ax_e = fig.add_subplot(gs[0, 4])

top_b = results['experiment3_bottlenecks']['top_bottlenecks'][:10]
names = [b['theorem'].split('.')[-1][:20] for b in top_b]
impacts = [b['impact'] for b in top_b]
y_pos = np.arange(len(names))

bars = ax_e.barh(y_pos, impacts, height=0.6, edgecolor='#555', linewidth=0.5, color='#E8E8E8')
for bar, imp in zip(bars, impacts):
    if imp >= 0.9:
        bar.set_facecolor('#FFD8D8')
        bar.set_edgecolor(ACCENT)
    ax_e.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
              f'{imp:.3f}', fontsize=5.5, va='center', color='#555')

ax_e.set_yticks(y_pos)
ax_e.set_yticklabels(names, fontsize=6, family='monospace')
ax_e.invert_yaxis()
ax_e.set_xlim(0, 1.15)
style_ax(ax_e, 'E.  Top 10 Gateway Theorems', 'Downstream Impact', '')

note(ax_e, 0.35, 0.75,
     'add_eq_zero: impact=1.0\n'
     'Removing it severs ALL\n'
     'descendants. Most have\n'
     'near-zero impact.')


# -- F: Memory-Constrained (old exp6) -----------------------------------------
ax_f = fig.add_subplot(gs[0, 5])

memory_data = results['experiment6_memory_constrained']['memory_coverage']
mem_sizes = [d['memory_size'] for d in memory_data]
coverages = [d['coverage'] for d in memory_data]

ax_f.plot(mem_sizes, coverages, 'o-', linewidth=2, markersize=8,
          color='black', markerfacecolor='white', markeredgewidth=1.5, zorder=3)
ax_f.fill_between(mem_sizes, 0, coverages, alpha=0.03, color='black')
ax_f.axhline(root_count / N, color='#CCC', linewidth=0.8, linestyle='-', alpha=0.5)

for ms, cov in zip(mem_sizes, coverages):
    label = 'inf' if ms > 100000 else f'{ms:,}'
    ax_f.annotate(f'K={label}\n{cov:.1%}', (ms, cov),
                  textcoords='offset points', xytext=(0, 12),
                  fontsize=6, ha='center', color='#555')

ax_f.set_xscale('log')
ax_f.set_ylim(0, max(coverages) * 1.2)
style_ax(ax_f, 'F.  Memory-Constrained (Random, no recall)',
         'Memory Size K', 'Coverage')

note(ax_f, 0.03, 0.55,
     'Smooth degradation\n'
     'No sharp phase transition\n'
     'K=10k: 49.5% (barely above\n'
     f'baseline {root_count/N:.1%})')


# ==============================================================================
# ROW 2: PHASE TRANSITIONS
# ==============================================================================

def plot_phase_panel(ax, phase_data, recall_mode, title):
    """Plot survival curves for one recall mode."""
    baseline = phase_data['baseline_coverage']
    budgets_sorted = sorted(phase_data['budgets'])

    ax.axhline(baseline, color='#CCC', linewidth=0.8, linestyle='-', alpha=0.5, zorder=1)
    ax.text(55, baseline - 0.012, f'baseline {baseline:.1%}',
            fontsize=5.5, color='#AAA', va='top')

    # BFS ceiling
    bfs_key = f'bfs__{recall_mode}'
    if bfs_key in phase_data['results']:
        for e in phase_data['results'][bfs_key]:
            if e['label'] == 'inf':
                bfs_inf = e['by_budget'].get(str(max(budgets_sorted)), {}).get('coverage', 0)
                if bfs_inf > 0.9:
                    ax.axhline(bfs_inf, color='#AADDAA', linewidth=0.8, linestyle='-', alpha=0.4, zorder=1)
                    ax.text(55, bfs_inf + 0.005, f'ceiling {bfs_inf:.1%}',
                            fontsize=5.5, color='#5A9A5A', va='bottom')

    for strat in phase_data['strategies']:
        key = f"{strat}__{recall_mode}"
        if key not in phase_data['results']:
            continue
        entries = phase_data['results'][key]

        for budget in budgets_sorted:
            bs = BLS[str(budget)]
            ks = [e['memory_size'] for e in entries]
            covs = []
            for entry in entries:
                cov_data = entry['by_budget'].get(str(budget), {})
                covs.append(cov_data.get('coverage', 0) if isinstance(cov_data, dict) else 0)
            ax.plot(ks, covs, color=SC[strat], linewidth=bs['lw'], linestyle=bs['ls'], zorder=4)

            if budget == max(budgets_sorted):
                ax.plot(ks[-1], covs[-1], 'D', color=SC[strat], markersize=5,
                        markeredgecolor='white', markeredgewidth=0.8, zorder=6)

    style_ax(ax, title, 'Memory Size K', 'Coverage')
    ax.set_xscale('log')
    ax.set_ylim(0.44, 1.03)
    ax.set_xlim(40, 1500000)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, p: '$\\infty$' if x >= 500000 else f'{int(x):,}'))
    ax.axhspan(baseline, 1.0, alpha=0.008, color='green', zorder=0)


if phase_data is not None:
    # -- G: No Recall --------------------------------------------------------------
    ax_g = fig.add_subplot(gs[1, 0])
    plot_phase_panel(ax_g, phase_data, 'none', 'G.  Phase: No Recall')

    # Strategy + budget legends
    strat_handles = [mlines.Line2D([], [], color=SC[s], linewidth=1.8, label=SL[s])
                     for s in phase_data['strategies']]
    leg1 = ax_g.legend(handles=strat_handles, loc='upper left', fontsize=6,
                       frameon=True, edgecolor='#CCC', fancybox=False,
                       title='Strategy', title_fontsize=6, handlelength=1.5)
    ax_g.add_artist(leg1)

    budget_handles = [mlines.Line2D([], [], color='#555',
                      linewidth=BLS[str(b)]['lw'], linestyle=BLS[str(b)]['ls'],
                      label=BLS[str(b)]['label'])
                      for b in sorted(phase_data['budgets'])]
    ax_g.legend(handles=budget_handles, loc='lower right', fontsize=5.5,
                frameon=True, edgecolor='#CCC', fancybox=False,
                title='Budget', title_fontsize=5.5)

    note(ax_g, 0.35, 0.28,
         'Without recall, agent\n'
         'stalls when frontier\n'
         'empties. K < 1k:\n'
         'all strategies = baseline')

    # -- H: Matched Recall ---------------------------------------------------------
    ax_h = fig.add_subplot(gs[1, 1])
    plot_phase_panel(ax_h, phase_data, 'matched', 'H.  Phase: Matched Recall')

    note(ax_h, 0.03, 0.50,
         'Strategy-matched recall\n'
         'helps most at mid-K.\n'
         'Greedy + recall lifts\n'
         'small-K coverage ~5%')

    # -- I: Hub Recall -------------------------------------------------------------
    ax_i = fig.add_subplot(gs[1, 2])
    plot_phase_panel(ax_i, phase_data, 'hub', 'I.  Phase: Hub Recall')

    note(ax_i, 0.03, 0.50,
         'Hub recall (out-degree)\n'
         'universally effective.\n'
         'All strategies converge\n'
         'to similar trajectories.')

    # -- J: Coverage Gain from Recall ----------------------------------------------
    ax_j = fig.add_subplot(gs[1, 3])
    max_b = str(max(phase_data['budgets']))

    for strat in phase_data['strategies']:
        none_entries = phase_data['results'].get(f"{strat}__none", [])
        matched_entries = phase_data['results'].get(f"{strat}__matched", [])
        hub_entries = phase_data['results'].get(f"{strat}__hub", [])
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

        ax_j.plot(ks, gain_matched, color=SC[strat], linewidth=1.8, linestyle='-', zorder=4)
        ax_j.plot(ks, gain_hub, color=SC[strat], linewidth=1.2, linestyle='--', alpha=0.7, zorder=3)

    style_ax(ax_j, 'J.  Coverage Gain from Recall (@60k)',
             'Memory Size K', 'Coverage Gain')
    ax_j.set_xscale('log')
    ax_j.set_xlim(40, 1500000)
    ax_j.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, p: '$\\infty$' if x >= 500000 else f'{int(x):,}'))
    ax_j.axhline(0, color='#CCC', linewidth=0.8, alpha=0.5)

    h_handles = [mlines.Line2D([], [], color=SC[s], linewidth=1.5, label=SL[s])
                 for s in phase_data['strategies']]
    h_handles += [mlines.Line2D([], [], color='#555', linewidth=1.5, label='Matched'),
                  mlines.Line2D([], [], color='#555', linewidth=1, linestyle='--', alpha=0.7, label='Hub')]
    ax_j.legend(handles=h_handles, fontsize=5.5, loc='upper right',
                frameon=True, edgecolor='#CCC', fancybox=False, ncol=2)

    note(ax_j, 0.03, 0.98,
         'Solid = matched recall\n'
         'Dashed = hub recall\n'
         'Peak gain at mid-K\n'
         'where recall matters most')

    # -- K: Recall Fraction --------------------------------------------------------
    ax_k = fig.add_subplot(gs[1, 4])

    for strat in phase_data['strategies']:
        for rm, ls_style in [('matched', '-'), ('hub', '--')]:
            entries = phase_data['results'].get(f"{strat}__{rm}", [])
            if not entries:
                continue
            ks = [e['memory_size'] for e in entries]
            fracs = []
            for e in entries:
                d = e['by_budget'].get(max_b, {})
                disc = d.get('discoveries', 0)
                rec = d.get('recalls', 0)
                total = disc + rec
                fracs.append(rec / total if total > 0 else 0)
            lw = 1.8 if rm == 'matched' else 1.0
            ax_k.plot(ks, fracs, color=SC[strat], linewidth=lw, linestyle=ls_style,
                      alpha=0.85 if rm == 'matched' else 0.6)

    style_ax(ax_k, 'K.  Recall Fraction (@60k budget)',
             'Memory Size K', 'Recalls / Total Steps')
    ax_k.set_xscale('log')
    ax_k.set_xlim(40, 1500000)
    ax_k.set_ylim(-0.02, 1.02)
    ax_k.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda x, p: '$\\infty$' if x >= 500000 else f'{int(x):,}'))

    k_handles = [mlines.Line2D([], [], color=SC[s], linewidth=1.5, label=SL[s])
                 for s in phase_data['strategies']]
    k_handles += [mlines.Line2D([], [], color='#555', linewidth=1.5, label='Matched'),
                  mlines.Line2D([], [], color='#555', linewidth=1, linestyle='--', label='Hub')]
    ax_k.legend(handles=k_handles, fontsize=5.5, loc='upper left',
                frameon=True, edgecolor='#CCC', fancybox=False, ncol=2)

    note(ax_k, 0.55, 0.98,
         'Small K: mostly recalls\n'
         '(memory overflows fast)\n'
         'Large K: zero recalls\n'
         '(memory holds everything)')

    # -- L: Heatmap: Strategy x Memory (max budget coverage) -----------------------
    ax_l = fig.add_subplot(gs[1, 5])

    strats = phase_data['strategies']
    recalls = phase_data['recall_modes']
    # Select representative memory sizes
    target_ks = [100, 1000, 5000, 20000, 50000, 100000]
    k_labels = ['100', '1k', '5k', '20k', '50k', '100k']

    rows = []
    row_labels = []
    for strat in strats:
        for rm in recalls:
            key = f"{strat}__{rm}"
            entries = phase_data['results'].get(key, [])
            if not entries:
                continue
            row = []
            for tk in target_ks:
                # Find closest memory size
                best_entry = min(entries, key=lambda e: abs(e['memory_size'] - tk))
                cov = best_entry['by_budget'].get(max_b, {}).get('coverage', 0)
                row.append(cov)
            rows.append(row)
            row_labels.append(f'{SL[strat]}_{rm[:3]}')

    matrix = np.array(rows)
    im = ax_l.imshow(matrix, cmap='YlOrRd', aspect='auto', vmin=0.48, vmax=1.0)
    ax_l.set_xticks(range(len(k_labels)))
    ax_l.set_xticklabels(k_labels, fontsize=6)
    ax_l.set_yticks(range(len(row_labels)))
    ax_l.set_yticklabels(row_labels, fontsize=5.5, family='monospace')
    ax_l.set_xlabel('Memory K', fontsize=7.5, labelpad=3)

    # Annotate cells
    for i in range(len(row_labels)):
        for j in range(len(k_labels)):
            val = matrix[i, j]
            color = 'white' if val > 0.75 else '#333'
            ax_l.text(j, i, f'{val:.2f}', ha='center', va='center',
                      fontsize=5, color=color, fontweight='bold')

    ax_l.set_title('L.  Coverage Heatmap (@60k budget)', fontsize=9.5,
                    fontweight='bold', pad=5, loc='left')
    ax_l.spines['top'].set_visible(False)
    ax_l.spines['right'].set_visible(False)

    # Colorbar
    cbar = fig.colorbar(im, ax=ax_l, fraction=0.046, pad=0.04, shrink=0.8)
    cbar.ax.tick_params(labelsize=5.5)
    cbar.set_label('Coverage', fontsize=6.5)

else:
    for col in range(6):
        ax = fig.add_subplot(gs[1, col])
        ax.axis('off')
        ax.text(0.5, 0.5, "Run experiment2_phase_transition.py first",
                transform=ax.transAxes, fontsize=10, ha='center')


# ==============================================================================
# SAVE
# ==============================================================================

FIGS_DIR.mkdir(exist_ok=True)
plt.savefig(OUTPUT_PNG, dpi=180, bbox_inches='tight', facecolor='white')
print(f"Saved: {OUTPUT_PNG}")

plt.savefig(OUTPUT_PDF, bbox_inches='tight', facecolor='white')
print(f"Saved: {OUTPUT_PDF}")

plt.close()
print("Done!")
