#!/usr/bin/env python3
"""Jarvis-style OD cross-sections for a303-corridor public page.

Style model: Mortimore/Jarvis et al. 2017 Fig 16 (elevation m AoD vs distance,
labelled borehole sticks) — same figure Tim copied into the Jan 2026 flooding audit.
Data: Report 7 BH1–BH6 (TR010025-000588) + corridor gazetteer GLs.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np

OUT = Path("/workspace/a303-corridor/figures")
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path("/workspace/a303-corridor/data/boreholes.json")

# Colours tuned for chalk-valley stack (readable on white)
COLOURS = {
    "ploughsoil": "#6b4f2a",
    "b_horizon": "#a67c52",
    "lag": "#5a5a5a",
    "colluvium": "#c4a574",
    "buried_soil": "#3d2914",
    "coombe": "#e8e0c8",
    "weathered_chalk": "#f5f0d8",
    "bedrock": "#faf6e8",
    "void": "#ffffff",
    "head": "#9a7b4f",
    "topsoil": "#6b4f2a",
}

LABELS = {
    "ploughsoil": "Ploughsoil",
    "b_horizon": "B horizon",
    "lag": "Flint lag",
    "colluvium": "Holocene colluvium",
    "buried_soil": "Buried soil? (Windermere or pipe)",
    "coombe": "Coombe chalk (periglacial)",
    "weathered_chalk": "Weathered chalk",
    "bedrock": "Structural / bedrock chalk",
    "head": "Head (periglacial)",
    "topsoil": "Topsoil",
}

# Report 7 BH1–BH6 — intervals as (top_m_od, base_m_od, unit_key)
# Parsed from TR010025-000588 borehole sheets; voids skipped / merged into adjacent.
# Northing decreases BH1 → BH6 (N → S down coombe).
BH = [
    {
        "id": "BH1",
        "easting": 407207.06,
        "northing": 141421.1,
        "gl": 78.61,
        "units": [
            (78.61, 78.41, "void"),  # compression — omit from fill
            (78.41, 78.15, "ploughsoil"),
            (78.15, 76.81, "colluvium"),  # includes gravelly base 77.13–76.81
            (76.81, 75.91, "coombe"),
            (75.91, 75.61, "bedrock"),
        ],
    },
    {
        "id": "BH2",
        "easting": 407207.83,
        "northing": 141401.33,
        "gl": 77.23,
        "units": [
            (77.23, 76.88, "ploughsoil"),
            (76.88, 76.58, "b_horizon"),
            (76.58, 76.23, "lag"),
            # void 76.23–76.01 skipped
            (76.01, 73.23, "colluvium"),  # thickened solution / colluvium stack
            (73.23, 72.53, "coombe"),
            (72.53, 72.23, "bedrock"),
        ],
    },
    {
        "id": "BH3",
        "easting": 407207.74,
        "northing": 141381.51,
        "gl": 76.25,
        "units": [
            (76.25, 75.90, "ploughsoil"),
            (75.90, 75.35, "b_horizon"),
            (75.35, 73.55, "colluvium"),
            (73.55, 71.75, "coombe"),
            (71.75, 71.25, "bedrock"),
        ],
    },
    {
        "id": "BH4",
        "easting": 407207.48,
        "northing": 141371.52,
        "gl": 75.93,
        "units": [
            (75.93, 75.63, "ploughsoil"),
            (75.63, 74.93, "b_horizon"),
            # void 74.93–74.68
            (74.68, 72.83, "colluvium"),
            (72.83, 71.33, "coombe"),
            (71.33, 70.93, "bedrock"),
        ],
    },
    {
        "id": "BH5",
        "easting": 407207.65,
        "northing": 141362.06,
        "gl": 75.86,
        "units": [
            (75.86, 75.46, "ploughsoil"),
            (75.46, 74.76, "b_horizon"),
            (74.76, 74.16, "lag"),
            (74.16, 73.86, "colluvium"),
            (73.86, 73.26, "coombe"),
            (73.26, 73.06, "colluvium"),  # transition zone
            # log OCR has 73.06–72.69 approx for buried soil (0.37 m); base OD = 73.06-0.37
            (73.06, 72.69, "buried_soil"),
            (72.69, 71.11, "coombe"),
            (71.11, 70.80, "weathered_chalk"),
        ],
    },
    {
        "id": "BH6",
        "easting": 407207.25,
        "northing": 141352.72,
        "gl": 75.88,
        "units": [
            (75.88, 75.55, "ploughsoil"),
            (75.55, 74.44, "b_horizon"),
            (74.44, 73.36, "colluvium"),
            (73.36, 72.88, "coombe"),
            (72.88, 72.67, "buried_soil"),
            (72.67, 71.08, "coombe"),
            (71.08, 70.88, "weathered_chalk"),
        ],
    },
]

# Fix BH5 buried soil OD: log says 2.8–3.17 mbg at GL 75.86 → 73.06 to 72.69
# (3.17 mbg = 75.86-3.17 = 72.69). Good.
# Note: OCR wrongly printed 73.69 for base of buried soil — use depth arithmetic.


def _draw_stick(ax, x, units, width=4.5):
    for top, base, key in units:
        if key == "void":
            continue
        if top <= base:
            continue
        ax.add_patch(
            mpatches.Rectangle(
                (x - width / 2, base),
                width,
                top - base,
                facecolor=COLOURS[key],
                edgecolor="#333333",
                linewidth=0.4,
                zorder=3,
            )
        )


def make_winterbourne():
    # X = distance south of BH1 along nearly N–S transect (northings)
    n0 = BH[0]["northing"]
    xs = [n0 - b["northing"] for b in BH]  # metres south of BH1

    fig, ax = plt.subplots(figsize=(11.5, 6.2), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")

    # Ground surface polyline
    gls = [b["gl"] for b in BH]
    ax.plot(xs, gls, color="#222", linewidth=1.4, zorder=4, label="Ground level")
    ax.fill_between(xs, gls, [max(gls) + 1.2] * len(xs), color="#eef2e8", alpha=0.9, zorder=0)

    for x, b in zip(xs, BH):
        _draw_stick(ax, x, b["units"], width=5.2)
        ax.plot([x, x], [b["units"][-1][1], b["gl"]], color="#444", linewidth=0.5, zorder=2)
        ax.text(x, b["gl"] + 0.35, b["id"], ha="center", va="bottom", fontsize=9, fontweight="bold")

    # Rockhead dashed
    rh = [next(u[1] for u in b["units"] if u[2] in ("bedrock", "weathered_chalk")) for b in BH]
    # For BH1-4 rockhead is top of bedrock; BH5-6 top of weathered
    rh = []
    for b in BH:
        for top, base, key in b["units"]:
            if key in ("bedrock", "weathered_chalk"):
                rh.append(top)
                break
    ax.plot(xs, rh, color="#8a6d3b", linewidth=1.2, linestyle="--", zorder=5, label="Rockhead (chalk)")

    # Zoom to stack (Jarvis Fig 16 fills the frame with geology).
    # 0 m OD sits ~70 m below this window — stated in caption, not crushed into the plot.
    ax.set_xlim(xs[0] - 8, xs[-1] + 8)
    ax.set_ylim(68.5, max(gls) + 2.2)
    ax.set_xlabel("Distance south of BH1 along Report 7 transect (m)", fontsize=10)
    ax.set_ylabel("Elevation (m OD)", fontsize=10)
    ax.set_title(
        "Winterbourne Stoke coombe — Report 7 BH1–BH6\n"
        "N→S transect · TR010025-000588 · periglacial coombe + Holocene colluvium over chalk",
        fontsize=11,
        pad=10,
    )
    ax.grid(True, axis="y", alpha=0.35, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Legend — unique units present
    present = []
    for b in BH:
        for _, _, k in b["units"]:
            if k != "void" and k not in present:
                present.append(k)
    handles = [
        mpatches.Patch(facecolor=COLOURS[k], edgecolor="#333", label=LABELS[k]) for k in present
    ]
    handles += [
        Line2D([0], [0], color="#222", lw=1.4, label="Ground level"),
        Line2D([0], [0], color="#8a6d3b", lw=1.2, ls="--", label="Rockhead"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=7.5, framealpha=0.95, ncol=1)

    ax.text(
        0.98,
        0.04,
        "Rockhead ≈ 71–76 m OD  ·  Holocene sea level ≈ 0 m OD lies ~70 m below this frame",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color="#1f77b4",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#bcd", alpha=0.95),
    )

    fig.tight_layout()
    path = OUT / "winterbourne-stoke-section.png"
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / "winterbourne-stoke-section.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", path)
    return path


def make_corridor_long():
    rows = json.loads(DATA.read_text())
    # Sort by easting (W→E along A303 corridor)
    rows = sorted(rows, key=lambda r: r["easting"])
    e0 = rows[0]["easting"]
    xs = [r["easting"] - e0 for r in rows]
    gls = [r["gl_m_od"] for r in rows]

    fig, ax = plt.subplots(figsize=(12.5, 5.8), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")

    # Scatter GLs by classification colour
    class_col = {
        "periglacial_coombe": "#c4a574",
        "colluvium": "#d4b896",
        "chalk": "#f0ead8",
        "solution": "#a89070",
        "made_ground": "#888888",
        "ambiguous": "#cccccc",
    }
    for x, r in zip(xs, rows):
        c = class_col.get(r.get("classification"), "#999")
        ax.scatter(x, r["gl_m_od"], s=18, c=c, edgecolors="#333", linewidths=0.3, zorder=3)
        if r.get("rockhead_m_od") is not None:
            ax.plot(
                [x, x],
                [r["rockhead_m_od"], r["gl_m_od"]],
                color="#555",
                linewidth=0.9,
                zorder=2,
            )
            ax.scatter(x, r["rockhead_m_od"], s=12, c="#8a6d3b", marker="s", zorder=4)

    # Smooth envelope of GL (optional light line)
    ax.plot(xs, gls, color="#222", linewidth=0.6, alpha=0.35, zorder=1)

    ax.axhline(0, color="#1f77b4", linewidth=1.2, linestyle=":", zorder=1)
    ax.fill_between([xs[0], xs[-1]], -5, 0, color="#1f77b4", alpha=0.08, zorder=0)
    ax.text(xs[-1] * 0.02, 3, "Holocene eustatic sea level ≈ 0 m OD", color="#1f77b4", fontsize=9)

    # Landmark annotations by easting
    landmarks = [
        (407207, "Winterbourne Stoke\ncoombe (R7)", 82),
        (412924, "Stonehenge Bottom\nSU14SW62 @ 96 m OD", 102),
        (410000, "Western portal /\nNormanton Down ≈ 100 m", 112),
        (415000, "Eastern portal /\nCountess ≈ 70–75 m", 85),
    ]
    for e, label, y in landmarks:
        x = e - e0
        if xs[0] <= x <= xs[-1]:
            ax.axvline(x, color="#aaa", linewidth=0.6, linestyle="--", zorder=0)
            ax.text(x + 40, y, label, fontsize=7.5, color="#444", va="bottom")

    # SU14SW62 marker (audit borehole) — not in our gazetteer; add as reference
    sx = 412924 - e0
    ax.scatter([sx], [96.0], s=60, c="#c0392b", marker="*", zorder=6, label="SU14SW62 (flooding audit)")
    ax.annotate(
        "SU14SW62\n96 m OD",
        xy=(sx, 96),
        xytext=(sx + 200, 88),
        fontsize=8,
        color="#c0392b",
        arrowprops=dict(arrowstyle="->", color="#c0392b", lw=0.8),
    )

    ax.set_xlim(xs[0] - 100, xs[-1] + 100)
    ax.set_ylim(-8, max(gls) + 8)
    ax.set_xlabel(f"Distance east of westernmost hole (m) · OSGB easting {e0:.0f} →", fontsize=10)
    ax.set_ylabel("Elevation (m OD)", fontsize=10)
    ax.set_title(
        "A303 Amesbury–Berwick Down corridor — ground level & rockhead (m OD)\n"
        "Jarvis-style elevation section · falsifies Holocene inundation of the Plain",
        fontsize=11,
        pad=10,
    )
    ax.grid(True, axis="y", alpha=0.35, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    handles = [
        mpatches.Patch(facecolor=class_col["periglacial_coombe"], edgecolor="#333", label="Periglacial coombe"),
        mpatches.Patch(facecolor=class_col["colluvium"], edgecolor="#333", label="Colluvium"),
        mpatches.Patch(facecolor=class_col["chalk"], edgecolor="#333", label="Chalk-dominated"),
        mpatches.Patch(facecolor=class_col["solution"], edgecolor="#333", label="Solution"),
        mpatches.Patch(facecolor=class_col["made_ground"], edgecolor="#333", label="Made ground"),
        Line2D([0], [0], color="#8a6d3b", marker="s", lw=0, markersize=6, label="Rockhead (where logged)"),
        Line2D([0], [0], color="#1f77b4", lw=1.2, ls=":", label="≈ 0 m OD"),
        Line2D([0], [0], color="#c0392b", marker="*", lw=0, markersize=10, label="SU14SW62 audit BH"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=7.5, framealpha=0.95, ncol=2)

    fig.tight_layout()
    path = OUT / "corridor-long-section.png"
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / "corridor-long-section.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", path)
    return path


def make_stonehenge_bottom_stick():
    """Single-hole stick for SU14SW62 matching flooding-audit strata table."""
    gl = 96.0
    units = [
        (96.00, 95.90, "topsoil"),
        (95.90, 95.00, "head"),
        (95.00, 46.00, "bedrock"),  # chalk grades collapsed for visual
    ]
    fig, ax = plt.subplots(figsize=(4.2, 7.5), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")
    _draw_stick(ax, 0, units, width=1.4)
    ax.plot([-1, 1], [gl, gl], color="#222", lw=1.2)
    ax.axhline(0, color="#1f77b4", lw=1.0, ls=":")
    ax.text(1.2, 0.5, "≈ 0 m OD", color="#1f77b4", fontsize=8)
    ax.set_xlim(-2.5, 3.5)
    ax.set_ylim(-5, 102)
    ax.set_xticks([])
    ax.set_ylabel("Elevation (m OD)")
    ax.set_title("SU14SW62\nStonehenge Bottom\nGL 96.00 m OD", fontsize=10)
    ax.text(
        0,
        70,
        "Chalk\n(Seaford Fm)\n\nNo Holocene\naquatic facies",
        ha="center",
        va="center",
        fontsize=8,
        color="#555",
    )
    ax.text(0, 95.4, "Head", ha="center", fontsize=7, color="#fff")
    handles = [
        mpatches.Patch(facecolor=COLOURS["topsoil"], label="Topsoil"),
        mpatches.Patch(facecolor=COLOURS["head"], label="Head (periglacial)"),
        mpatches.Patch(facecolor=COLOURS["bedrock"], edgecolor="#333", label="Chalk bedrock"),
        Line2D([0], [0], color="#1f77b4", ls=":", label="≈ 0 m OD"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    fig.tight_layout()
    path = OUT / "su14sw62-stick.png"
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", path)
    return path


if __name__ == "__main__":
    make_winterbourne()
    make_corridor_long()
    make_stonehenge_bottom_stick()
