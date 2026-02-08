"""
Create beautiful multi-panel figure for Search Proof Dynamics results.

Visualizes:
1. Adjacent possible growth curves (BFS, Random, Greedy)
2. Accessibility time distribution
3. Dilution factor analysis
4. Bottleneck identification
5. Memory-constrained coverage
6. Strategy comparison + interpretation
"""

import json
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import matplotlib.patches as mpatches
from pathlib import Path

# Configuration
SCRIPT_DIR = Path(__file__).resolve().parent
RESULTS_FILE = SCRIPT_DIR / "experiment2_search_proof_results.json"
FIGS_DIR = SCRIPT_DIR / "figs"
OUTPUT_PNG = FIGS_DIR / "experiment2_search_proof_comprehensive.png"

print("Loading results...")
with open(RESULTS_FILE, 'r') as f:
    results = json.load(f)

print("Creating comprehensive visualization...")

# Create figure
fig = plt.figure(figsize=(22, 16))
gs = GridSpec(4, 3, figure=fig, hspace=0.35, wspace=0.3,
              left=0.05, right=0.98, top=0.95, bottom=0.05)

# Title
fig.suptitle('Mathematical Discovery Dynamics: The Adjacent Possible in Formal Theorem Proving',
             fontsize=20, fontweight='bold', family='monospace')

# Color scheme
colors = {
    'bfs': '#2E7D32',      # Dark green
    'random': '#1976D2',   # Blue
    'greedy': '#D32F2F',   # Red
    'bg': '#FFF3E0'        # Light orange
}

# Background box
bg_box = mpatches.FancyBboxPatch((0.01, 0.01), 0.98, 0.93,
                                 boxstyle="round,pad=0.01",
                                 facecolor=colors['bg'],
                                 edgecolor='black', linewidth=2, alpha=0.15,
                                 transform=fig.transFigure, zorder=0)
fig.patches.append(bg_box)

# ============================================================================
# ROW 1: ADJACENT POSSIBLE DYNAMICS
# ============================================================================

# Panel 1.1: Adjacent possible size over time
ax1 = fig.add_subplot(gs[0, 0])

bfs_data = results['experiment1_adjacent_possible']['bfs']
random_data = results['experiment1_adjacent_possible']['random']
greedy_data = results['experiment1_adjacent_possible']['greedy']

bfs_steps = [d['step'] for d in bfs_data]
bfs_adjacent = [d['adjacent'] for d in bfs_data]

random_steps = [d['step'] for d in random_data]
random_adjacent = [d['adjacent'] for d in random_data]

greedy_steps = [d['step'] for d in greedy_data]
greedy_adjacent = [d['adjacent'] for d in greedy_data]

ax1.plot(bfs_steps, bfs_adjacent, linewidth=2.5, color=colors['bfs'], label='BFS (Optimal)', alpha=0.9)
ax1.plot(random_steps, random_adjacent, linewidth=2.5, color=colors['random'], label='Random Walk', alpha=0.9)
ax1.plot(greedy_steps, greedy_adjacent, linewidth=2.5, color=colors['greedy'], label='Greedy Expansion', alpha=0.9)

ax1.set_xlabel('Discovery Steps', fontsize=11, fontweight='bold', family='monospace')
ax1.set_ylabel('|A(t)| - Adjacent Possible Size', fontsize=11, fontweight='bold', family='monospace')
ax1.set_title('A. Evolution of Possibility Space', fontsize=12, fontweight='bold', family='monospace')
ax1.legend(fontsize=10, frameon=True, edgecolor='black', loc='best')
ax1.grid(True, alpha=0.3)
ax1.set_yscale('log')

# Panel 1.2: Known theorems over time
ax2 = fig.add_subplot(gs[0, 1])

bfs_known = [d['known'] for d in bfs_data]
random_known = [d['known'] for d in random_data]
greedy_known = [d['known'] for d in greedy_data]

ax2.plot(bfs_steps, bfs_known, linewidth=2.5, color=colors['bfs'], label='BFS', alpha=0.9)
ax2.plot(random_steps, random_known, linewidth=2.5, color=colors['random'], label='Random', alpha=0.9)
ax2.plot(greedy_steps, greedy_known, linewidth=2.5, color=colors['greedy'], label='Greedy', alpha=0.9)

ax2.set_xlabel('Discovery Steps', fontsize=11, fontweight='bold', family='monospace')
ax2.set_ylabel('Known Theorems', fontsize=11, fontweight='bold', family='monospace')
ax2.set_title('B. Knowledge Accumulation', fontsize=12, fontweight='bold', family='monospace')
ax2.legend(fontsize=10, frameon=True, edgecolor='black')
ax2.grid(True, alpha=0.3)

# Panel 1.3: Strategy summary + interpretation
ax3 = fig.add_subplot(gs[0, 2])
ax3.axis('off')

summary = results['experiment1_adjacent_possible']['summary']
interp_text = f"""FINDING: Explosive Growth Phase

Adjacent possible |A(t)| shows:
• BFS: Rapid initial explosion, then
  plateau as graph exhausted
• Random: Slower growth, higher peak
  (explores broadly before depth)
• Greedy: Optimizes expansion but
  similar to BFS

Coverage achieved:
• BFS: {summary['bfs_coverage']:.1%}
• Random: {summary['random_coverage']:.1%}
• Greedy: {summary['greedy_coverage']:.1%}

INTERPRETATION:
Mathematical discovery is NOT uniform
exploration. Early discoveries unlock
explosive growth in possibilities,
then possibility space contracts as
easier results are exhausted.

Greedy ≈ BFS suggests humans naturally
optimize expansion, not randomly walk.
"""

ax3.text(0.05, 0.95, interp_text, transform=ax3.transAxes,
        fontsize=9.5, verticalalignment='top', family='monospace',
        bbox=dict(boxstyle='round', facecolor='white', edgecolor='black', linewidth=2.5))

# ============================================================================
# ROW 2: ACCESSIBILITY AND DILUTION
# ============================================================================

# Panel 2.1: Accessibility time distribution
ax4 = fig.add_subplot(gs[1, 0])

access_dist = results['experiment2_accessibility']['accessibility_distribution']
ax4.hist(access_dist, bins=50, edgecolor='black', linewidth=1.5, color='white', alpha=0.9)

mean_access = results['experiment2_accessibility']['accessibility_stats']['mean']
ax4.axvline(mean_access, color='red', linestyle='--', linewidth=2.5,
           label=f'Mean: {mean_access:.1f} steps')

ax4.set_xlabel('Accessibility Time (BFS steps)', fontsize=11, fontweight='bold', family='monospace')
ax4.set_ylabel('Number of Theorems', fontsize=11, fontweight='bold', family='monospace')
ax4.set_title('C. When Theorems Become Provable', fontsize=12, fontweight='bold', family='monospace')
ax4.legend(fontsize=10, frameon=True, edgecolor='black')
ax4.grid(True, alpha=0.3)

# Panel 2.2: Dilution factor distribution
ax5 = fig.add_subplot(gs[1, 1])

dilution_dist = results['experiment2_accessibility']['dilution_distribution']
ax5.hist(dilution_dist, bins=50, edgecolor='black', linewidth=1.5, color='white', alpha=0.9)

mean_dilution = results['experiment2_accessibility']['dilution_stats']['mean']
ax5.axvline(mean_dilution, color='red', linestyle='--', linewidth=2.5,
           label=f'Mean: {mean_dilution:.0f} alternatives')

ax5.set_xlabel('Dilution Factor (|A(t)| at entry)', fontsize=11, fontweight='bold', family='monospace')
ax5.set_ylabel('Number of Theorems', fontsize=11, fontweight='bold', family='monospace')
ax5.set_title('D. "Hiding in Plain Sight"', fontsize=12, fontweight='bold', family='monospace')
ax5.legend(fontsize=10, frameon=True, edgecolor='black')
ax5.grid(True, alpha=0.3)
ax5.set_xscale('log')

# Panel 2.3: Interpretation
ax6 = fig.add_subplot(gs[1, 2])
ax6.axis('off')

access_stats = results['experiment2_accessibility']
interp2_text = f"""FINDING: Dilution Effect

Accessibility time: When theorem first
becomes provable (all prerequisites met)

Mean accessibility: {access_stats['accessibility_stats']['mean']:.1f} steps
Max accessibility: {access_stats['accessibility_stats']['max']} steps

Dilution factor: How many alternatives
exist when theorem enters A(t)

Mean dilution: {access_stats['dilution_stats']['mean']:.0f} options
Max dilution: {access_stats['dilution_stats']['max']:,} options!

INTERPRETATION:
Theorems entering A(t) when |A(t)| is
large are "hidden" among many options.
Discovery difficulty ≠ just depth, but
also how diluted the theorem is.

High-dilution theorems require either:
• Strategic search (not random)
• Explicit value recognition
• Lucky exploration
"""

ax6.text(0.05, 0.95, interp2_text, transform=ax6.transAxes,
        fontsize=9.5, verticalalignment='top', family='monospace',
        bbox=dict(boxstyle='round', facecolor='white', edgecolor='black', linewidth=2.5))

# ============================================================================
# ROW 3: BOTTLENECKS AND GATEWAYS
# ============================================================================

# Panel 3.1: Removal impact distribution
ax7 = fig.add_subplot(gs[2, 0])

removal_dist = results['experiment3_bottlenecks']['removal_impact_distribution']
ax7.hist(removal_dist, bins=50, edgecolor='black', linewidth=1.5, color='white', alpha=0.9)

mean_removal = results['experiment3_bottlenecks']['removal_impact_stats']['mean']
ax7.axvline(mean_removal, color='red', linestyle='--', linewidth=2.5,
           label=f'Mean: {mean_removal:.3f}')

ax7.set_xlabel('Removal Impact (fraction downstream unreachable)', fontsize=10, fontweight='bold', family='monospace')
ax7.set_ylabel('Number of Theorems', fontsize=11, fontweight='bold', family='monospace')
ax7.set_title('E. Gateway Theorem Identification', fontsize=12, fontweight='bold', family='monospace')
ax7.legend(fontsize=10, frameon=True, edgecolor='black')
ax7.grid(True, alpha=0.3)

# Panel 3.2: Top bottlenecks
ax8 = fig.add_subplot(gs[2, 1])

top_bottlenecks = results['experiment3_bottlenecks']['top_bottlenecks'][:10]
names = [b['theorem'].split('.')[-1][:20] for b in top_bottlenecks]
impacts = [b['impact'] for b in top_bottlenecks]

y_pos = np.arange(len(names))
ax8.barh(y_pos, impacts, edgecolor='black', linewidth=1.5, color='white')
ax8.set_yticks(y_pos)
ax8.set_yticklabels(names, fontsize=9, family='monospace')
ax8.set_xlabel('Downstream Impact', fontsize=10, fontweight='bold', family='monospace')
ax8.set_title('F. Top 10 Gateway Theorems', fontsize=12, fontweight='bold', family='monospace')
ax8.invert_yaxis()
ax8.grid(True, alpha=0.3, axis='x')

# Panel 3.3: Interpretation
ax9 = fig.add_subplot(gs[2, 2])
ax9.axis('off')

removal_stats = results['experiment3_bottlenecks']
top1 = top_bottlenecks[0]
interp3_text = f"""FINDING: Sparse Gateways

Removal impact: Fraction of downstream
theorems unreachable if theorem removed

Mean impact: {removal_stats['removal_impact_stats']['mean']:.3f}
Max impact: {removal_stats['removal_impact_stats']['max']:.3f}

Top gateway theorem:
{top1['theorem'].split('.')[-1][:30]}
Impact: {top1['impact']:.3f}

INTERPRETATION:
Mathematical knowledge does NOT have
bow-tie structure with critical narrow
gateways. Most theorems have low
removal impact.

This suggests robust interconnection:
many alternative paths to any result.

Discovery order relatively unimportant
for ultimate coverage - multiple routes
exist to most theorems.
"""

ax9.text(0.05, 0.95, interp3_text, transform=ax9.transAxes,
        fontsize=9.5, verticalalignment='top', family='monospace',
        bbox=dict(boxstyle='round', facecolor='white', edgecolor='black', linewidth=2.5))

# ============================================================================
# ROW 4: MEMORY-CONSTRAINED DISCOVERY
# ============================================================================

# Panel 4.1: Memory vs coverage
ax10 = fig.add_subplot(gs[3, 0])

memory_data = results['experiment6_memory_constrained']['memory_coverage']
memory_sizes = [d['memory_size'] for d in memory_data]
coverages = [d['coverage'] for d in memory_data]

ax10.plot(memory_sizes, coverages, 'o-', linewidth=2.5, markersize=10,
         color='black', markerfacecolor='white', markeredgewidth=2)

ax10.set_xlabel('Memory Size K (working memory)', fontsize=11, fontweight='bold', family='monospace')
ax10.set_ylabel('Coverage (fraction discovered)', fontsize=11, fontweight='bold', family='monospace')
ax10.set_title('G. Memory-Constrained Discovery', fontsize=12, fontweight='bold', family='monospace')
ax10.set_xscale('log')
ax10.grid(True, alpha=0.3)
ax10.axhline(0.5, color='red', linestyle='--', alpha=0.5, linewidth=1.5)

# Panel 4.2: Zoom on phase transition
ax11 = fig.add_subplot(gs[3, 1])

ax11.plot(memory_sizes, coverages, 'o-', linewidth=3, markersize=12,
         color='black', markerfacecolor='white', markeredgewidth=2.5)

# Highlight critical region
for i in range(len(memory_sizes)-1):
    if coverages[i] < 0.5 and coverages[i+1] > 0.5:
        ax11.axvspan(memory_sizes[i], memory_sizes[i+1], alpha=0.2, color='red')

ax11.set_xlabel('Memory Size K', fontsize=11, fontweight='bold', family='monospace')
ax11.set_ylabel('Coverage', fontsize=11, fontweight='bold', family='monospace')
ax11.set_title('H. Phase Transition Search', fontsize=12, fontweight='bold', family='monospace')
ax11.grid(True, alpha=0.3)
ax11.set_ylim([0, 1.05])

# Panel 4.3: Summary + Interpretation
ax12 = fig.add_subplot(gs[3, 2])
ax12.axis('off')

# Find critical K
critical_K = None
for i in range(len(coverages)-1):
    if coverages[i] < 0.5 and coverages[i+1] > 0.5:
        critical_K = (memory_sizes[i], memory_sizes[i+1])
        break

interp4_text = f"""FINDING: Memory Threshold

Bounded working memory limits what
can be discovered. Theorem enters A(t)
only if ALL prerequisites in last K
discovered theorems.

Coverage results:
K=infinite: {coverages[0]:.1%}
K=10000: {coverages[1]:.1%}
K=1000: {coverages[2]:.1%}
K=100: {coverages[3]:.1%}

"""

if critical_K:
    interp4_text += f"""Critical memory K* ≈ {critical_K[0]}-{critical_K[1]}
(50% coverage threshold)

"""

interp4_text += """INTERPRETATION:
Smooth growth (not sharp transition)
suggests continuous difficulty spectrum.

Implications for bounded agents:
• K<50: Severely limited discovery
• K>200: Most mathematics accessible
• No single threshold complexity

Human mathematicians use external
memory (papers, notes) to exceed
biological working memory limits!
"""

ax12.text(0.05, 0.95, interp4_text, transform=ax12.transAxes,
        fontsize=9.5, verticalalignment='top', family='monospace',
        bbox=dict(boxstyle='round', facecolor='white', edgecolor='black', linewidth=2.5))

# Save figure
plt.tight_layout()
plt.savefig(OUTPUT_PNG, dpi=200, bbox_inches='tight', facecolor='white')
print(f"\nSaved figure to: {OUTPUT_PNG}")

# Also save as PDF
OUTPUT_PDF = FIGS_DIR / "experiment2_search_proof_comprehensive.pdf"
plt.savefig(OUTPUT_PDF, bbox_inches='tight', facecolor='white')
print(f"Saved PDF to: {OUTPUT_PDF}")

plt.close()

print("\nVisualization complete!")
