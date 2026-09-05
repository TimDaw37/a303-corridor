#!/usr/bin/env python3
"""Prototype: superficial cover thickness map (measured vs estimated)."""
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

ROOT = Path('/workspace/a303-corridor')
rows = json.load(open(ROOT / 'data' / 'boreholes.json'))
bgs = json.load(open(ROOT / 'data' / 'bgs_boreholes_index.json'))

DEFAULT = {
    'chalk': 0.6, 'made_ground': 1.5, 'colluvium': 2.0,
    'periglacial_coombe': 2.5, 'solution': 3.5, 'ambiguous': 1.5,
}

pts = []
for r in rows:
    if r.get('rockhead_m_od') is not None:
        cover = float(r['gl_m_od']) - float(r['rockhead_m_od'])
        measured = True
    else:
        cover = DEFAULT.get(r['classification'], 1.5)
        measured = False
    pts.append(dict(
        e=r['easting'], n=r['northing'], gl=r['gl_m_od'],
        cover=cover, measured=measured, cls=r['classification'], id=r['id']
    ))

fig, axes = plt.subplots(
    1, 2, figsize=(13.5, 5.8), dpi=140,
    gridspec_kw=dict(width_ratios=[1.15, 1], wspace=0.18),
)
fig.patch.set_facecolor('white')

ax = axes[0]
ax.set_facecolor('#f4f1ea')
be = np.array([b['e'] for b in bgs if b['e'] and b['n']])
bn = np.array([b['n'] for b in bgs if b['e'] and b['n']])
ax.scatter(be, bn, s=6, c='#c8c2b4', alpha=0.45, zorder=1, label='BGS index (n=309)')

for p in pts:
    size = 25 + p['cover'] * 55
    edge = '#222' if p['measured'] else '#666'
    lw = 0.7 if p['measured'] else 0.4
    ax.scatter(
        p['e'], p['n'], s=size, c=p['cover'], cmap='YlOrBr',
        vmin=0, vmax=5, edgecolors=edge, linewidths=lw,
        alpha=0.9 if p['measured'] else 0.8, zorder=3 if p['measured'] else 2,
    )

sc = ax.scatter([np.nan], [np.nan], c=[0], cmap='YlOrBr', vmin=0, vmax=5)
cb = fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.02)
cb.set_label('Superficial cover thickness (m)', fontsize=9)

ax.scatter([412924], [141917], marker='*', s=120, c='#c0392b', zorder=5)
ax.annotate(
    'SU14SW62', xy=(412924, 141917), xytext=(413400, 142200),
    fontsize=8, color='#c0392b',
    arrowprops=dict(arrowstyle='->', color='#c0392b', lw=0.8),
)
ax.annotate(
    'Winterbourne\nStoke coombe', xy=(407207, 141380), xytext=(406700, 140950),
    fontsize=8, color='#444',
    arrowprops=dict(arrowstyle='->', color='#888', lw=0.7),
)

ax.set_aspect('equal')
ax.set_xlabel('Easting (OSGB)')
ax.set_ylabel('Northing (OSGB)')
ax.set_title(
    'Plan view — cover thickness\n(circle size ∝ thickness; bold edge = measured rockhead)',
    fontsize=10,
)
ax.legend(loc='upper left', fontsize=7.5, framealpha=0.95)
ax.grid(True, alpha=0.25)

ax2 = axes[1]
ax2.set_facecolor('#fafafa')
e0 = min(p['e'] for p in pts)
xs = np.array([p['e'] - e0 for p in pts])
order = np.argsort(xs)
xs = xs[order]
gls = np.array([p['gl'] for p in pts])[order]
rhs = np.array([p['gl'] - p['cover'] for p in pts])[order]

bins = np.arange(xs.min(), xs.max() + 80, 80)
bx, bgl, brh = [], [], []
for i in range(len(bins) - 1):
    m = (xs >= bins[i]) & (xs < bins[i + 1])
    if not np.any(m):
        continue
    bx.append(0.5 * (bins[i] + bins[i + 1]))
    bgl.append(np.median(gls[m]))
    brh.append(np.median(rhs[m]))
bx = np.array(bx)
bgl = np.array(bgl)
brh = np.minimum(np.array(brh), bgl - 0.15)

ax2.fill_between(bx, 40, brh, color='#f3ecd4', label='Chalk (below rockhead)')
ax2.fill_between(bx, brh, bgl, color='#c4a574', label='Superficial cover')
ax2.plot(bx, bgl, color='#111', lw=1.6, label='Ground level')
ax2.plot(bx, brh, color='#6b4e2e', lw=1.3, ls='--', label='Rockhead')
for p in pts:
    if p['measured']:
        ax2.scatter(
            p['e'] - e0, p['gl'] - p['cover'], s=28, c='#6b4e2e',
            marker='s', zorder=5, edgecolors='#222', linewidths=0.4,
        )

ax2.axhline(0, color='#1f77b4', ls=':', lw=1)
ax2.set_ylim(-5, 125)
ax2.set_xlabel(f'Distance east (m) from E {e0:.0f}')
ax2.set_ylabel('Elevation (m OD)')
ax2.set_title(
    'Same idea in section — coombe “tongue”\n= thick brown where rockhead drops under GL',
    fontsize=10,
)
ax2.legend(loc='lower right', fontsize=7.5, framealpha=0.95, ncol=2)
ax2.grid(True, axis='y', alpha=0.3)
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

fig.suptitle(
    'Visualising periglacial cover vs chalk rockhead along the A303 corridor (prototype)',
    fontsize=12, y=1.02,
)
fig.text(
    0.5, -0.02,
    'Left: our 143 gazetteer holes (+ grey BGS index pins). Only 8 rockheads are measured (bold rings/squares); '
    'other thicknesses are class estimates. Right: long-section fill — the brown band is the “tongue”.',
    ha='center', fontsize=8, color='#555',
)
out = ROOT / 'figures' / 'cover-thickness-prototype.png'
fig.savefig(out, dpi=140, bbox_inches='tight', facecolor='white')
print('wrote', out)
