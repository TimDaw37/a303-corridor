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
    """Jarvis Fig 16 style: continuous GL + rockhead, solid filled blocks.

    Holes sit on a 2D corridor; projecting onto easting alone makes a noisy
    scatter. Bin by easting, take median GL, and build a rockhead surface from
    measured values plus class-based thin-cover estimates (captioned as such).
    """
    rows = json.loads(DATA.read_text())
    rows = sorted(rows, key=lambda r: r["easting"])
    e0 = rows[0]["easting"]

    # --- class-based default superficial thickness (m) when rockhead unknown ---
    # chalk: thin ploughsoil; coombe/colluvium: Report 7 typical 2–4 m; measured wins.
    DEFAULT_COVER = {
        "chalk": 0.6,
        "made_ground": 1.5,
        "colluvium": 2.0,
        "periglacial_coombe": 2.5,
        "solution": 3.5,
        "ambiguous": 1.5,
    }

    def rockhead_est(r):
        if r.get("rockhead_m_od") is not None:
            return float(r["rockhead_m_od"]), True
        cover = DEFAULT_COVER.get(r.get("classification"), 1.5)
        return float(r["gl_m_od"]) - cover, False

    # Per-hole samples in distance-east space
    pts = []
    for r in rows:
        rh, measured = rockhead_est(r)
        pts.append(
            {
                "x": r["easting"] - e0,
                "gl": float(r["gl_m_od"]),
                "rh": rh,
                "measured": measured,
                "cls": r.get("classification"),
                "id": r["id"],
            }
        )

    # Bin every 80 m — median GL / RH for a clean section envelope
    xs = np.array([p["x"] for p in pts])
    xmin, xmax = float(xs.min()), float(xs.max())
    bin_w = 80.0
    edges = np.arange(xmin, xmax + bin_w, bin_w)
    bx, bgl, brh, bn = [], [], [], []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        in_bin = [p for p in pts if lo <= p["x"] < hi]
        if not in_bin:
            continue
        bx.append(0.5 * (lo + hi))
        bgl.append(float(np.median([p["gl"] for p in in_bin])))
        brh.append(float(np.median([p["rh"] for p in in_bin])))
        bn.append(len(in_bin))
    bx = np.array(bx)
    bgl = np.array(bgl)
    brh = np.array(brh)
    # Ensure rockhead never above ground
    brh = np.minimum(brh, bgl - 0.15)

    chalk_floor = 40.0  # Jarvis-like deep frame (m OD)

    fig, ax = plt.subplots(figsize=(12.8, 6.4), dpi=160)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f7f5ef")

    # Solid chalk block (bedrock) from floor up to rockhead
    ax.fill_between(
        bx, chalk_floor, brh, color="#f3ecd4", edgecolor="none", zorder=1, label="Chalk bedrock"
    )
    # Solid superficial veneer GL → rockhead
    ax.fill_between(
        bx,
        brh,
        bgl,
        color="#c4a574",
        edgecolor="none",
        zorder=2,
        label="Superficial (head / coombe / colluvium / thin ploughsoil)",
    )
    # Ground level — strong continuous line
    ax.plot(bx, bgl, color="#1a1a1a", linewidth=2.0, zorder=5, label="Ground level")
    # Rockhead — continuous line
    ax.plot(bx, brh, color="#6b4e2e", linewidth=1.6, linestyle="--", zorder=5, label="Rockhead (see note)")

    # Tick marks at measured rockheads only
    for p in pts:
        if p["measured"]:
            ax.plot(
                [p["x"], p["x"]],
                [p["rh"], p["gl"]],
                color="#333",
                linewidth=1.1,
                zorder=6,
            )
            ax.scatter(p["x"], p["rh"], s=22, c="#6b4e2e", marker="s", zorder=7, edgecolors="#222", linewidths=0.4)

    # Holocene sea level
    ax.axhline(0, color="#1f77b4", linewidth=1.2, linestyle=":", zorder=3)
    ax.fill_between([bx[0], bx[-1]], -5, 0, color="#1f77b4", alpha=0.10, zorder=0)
    ax.text(
        bx[0] + 80,
        3.5,
        "Holocene eustatic sea level ≈ 0 m OD",
        color="#1f77b4",
        fontsize=9,
    )

    # Landmarks
    landmarks = [
        (407207 - e0, "Winterbourne\nStoke coombe", None),
        (410000 - e0, "Western portal\n≈ 100 m OD", None),
        (412924 - e0, None, "SU14SW62"),  # special
        (415000 - e0, "Eastern portal\n≈ 70–75 m OD", None),
    ]
    for x, label, special in landmarks:
        if bx[0] <= x <= bx[-1]:
            ax.axvline(x, color="#999", linewidth=0.7, linestyle=":", zorder=0)
            if label:
                # place label above ground
                yi = float(np.interp(x, bx, bgl))
                ax.text(x + 40, yi + 4, label, fontsize=7.5, color="#444", va="bottom")

    # SU14SW62 star on ground
    sx = 412924 - e0
    ax.scatter([sx], [96.0], s=70, c="#c0392b", marker="*", zorder=8)
    ax.annotate(
        "SU14SW62 · 96 m OD\n(flooding-audit BH)",
        xy=(sx, 96),
        xytext=(sx + 280, 108),
        fontsize=8,
        color="#c0392b",
        arrowprops=dict(arrowstyle="->", color="#c0392b", lw=0.9),
    )

    ax.set_xlim(bx[0] - 50, bx[-1] + 50)
    ax.set_ylim(-5, float(np.max(bgl)) + 12)
    ax.set_xlabel(f"Distance east along corridor (m) · from OSGB E {e0:.0f}", fontsize=10)
    ax.set_ylabel("Elevation (m OD)", fontsize=10)
    ax.set_title(
        "A303 Amesbury–Berwick Down — geological long-section (m OD)\n"
        "Ground level and rockhead as continuous surfaces · chalk as a solid block",
        fontsize=11,
        pad=10,
    )
    ax.grid(True, axis="y", alpha=0.3, linewidth=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    handles = [
        Line2D([0], [0], color="#1a1a1a", lw=2.0, label="Ground level (binned median)"),
        Line2D([0], [0], color="#6b4e2e", lw=1.6, ls="--", label="Rockhead surface"),
        mpatches.Patch(facecolor="#c4a574", label="Superficial deposits"),
        mpatches.Patch(facecolor="#f3ecd4", label="Chalk bedrock"),
        Line2D([0], [0], color="#6b4e2e", marker="s", lw=0, markersize=6, label="Measured rockhead"),
        Line2D([0], [0], color="#1f77b4", lw=1.2, ls=":", label="≈ 0 m OD"),
        Line2D([0], [0], color="#c0392b", marker="*", lw=0, markersize=10, label="SU14SW62"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=7.5, framealpha=0.95, ncol=2)

    ax.text(
        0.01,
        0.02,
        "Rockhead: measured where logged (squares); elsewhere estimated from class "
        "(chalk ≈ 0.6 m cover; coombe/colluvium ≈ 2–3.5 m). "
        "Binned every 80 m to suppress N–S scatter off the A303 line.",
        transform=ax.transAxes,
        fontsize=7,
        color="#555",
        va="bottom",
        ha="left",
        wrap=True,
    )

    fig.tight_layout()
    path = OUT / "corridor-long-section.png"
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    fig.savefig(OUT / "corridor-long-section.svg", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", path, f"bins={len(bx)}")
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
