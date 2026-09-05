#!/usr/bin/env python3
"""Schematic OD stick diagrams for every gazetteer hole → sticks/.

Most holes lack measured unit thicknesses. Sticks are schematic: unit tokens from
top_units are stacked proportionally between GL and rockhead (measured, or
class-estimated cover). Report 7 BH1–BH6 use the printed OD intervals from
make_sections.py. SU14SW62 is copied from figures/ (flooding-audit log).

Not a substitute for the printed sheets — a quick visual linked from the map.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path("/workspace/a303-corridor")
OUT = ROOT / "sticks"
DATA = ROOT / "data" / "boreholes.json"
FIG = ROOT / "figures"

DEFAULT_COVER = {
    "chalk": 0.6,
    "made_ground": 1.5,
    "colluvium": 2.0,
    "periglacial_coombe": 2.5,
    "solution": 3.5,
    "ambiguous": 1.5,
}

# Map free-text unit tokens → colour key
TOKEN_COLOUR = [
    (r"buried\s*soil", "#3d2914", "Buried soil? (not till)"),
    (r"flint\s*lag|\blag\b", "#5a5a5a", "Flint lag"),
    (r"\bb\s*horizon\b|\bb\b$", "#a67c52", "B horizon"),
    (r"plough|topsoil|subsoil", "#6b4f2a", "Ploughsoil / topsoil"),
    (r"made\s*ground", "#888888", "Made ground"),
    (r"colluv", "#c4a574", "Colluvium"),
    (r"coombe|solifluct|head|periglacial", "#e8e0c8", "Coombe / head"),
    (r"gravel|sand", "#b0a090", "Gravel / sand"),
    (r"weathered\s*chalk", "#f5f0d8", "Weathered chalk"),
    (r"structureless|degraded\s*chalk|blocky\s*chalk", "#f0ead0", "Structureless chalk"),
    (r"structural\s*chalk|bedrock|seaford|chalk", "#faf6e8", "Chalk"),
    (r"solution|infiltration", "#a89070", "Solution / fill"),
]


def colour_for(token: str) -> tuple[str, str]:
    t = token.lower().strip()
    for pat, col, label in TOKEN_COLOUR:
        if re.search(pat, t):
            return col, label
    return "#d0c8b8", token[:40]


def safe_name(hid: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", hid)


# Detailed OD intervals for Report 7 (from printed sheets) — top, base, label
R7_DETAILED = {
    "R7-BH1": [
        (78.41, 78.15, "ploughsoil"),
        (78.15, 76.81, "colluvium"),
        (76.81, 75.91, "coombe chalk"),
        (75.91, 75.61, "structural chalk"),
    ],
    "R7-BH2": [
        (77.23, 76.88, "ploughsoil"),
        (76.88, 76.58, "B horizon"),
        (76.58, 76.23, "flint lag"),
        (76.01, 73.23, "colluvium"),
        (73.23, 72.53, "coombe chalk"),
        (72.53, 72.23, "structural chalk"),
    ],
    "R7-BH3": [
        (76.25, 75.90, "ploughsoil"),
        (75.90, 75.35, "B horizon"),
        (75.35, 73.55, "colluvium"),
        (73.55, 71.75, "coombe chalk"),
        (71.75, 71.25, "structural chalk"),
    ],
    "R7-BH4": [
        (75.93, 75.63, "ploughsoil"),
        (75.63, 74.93, "B horizon"),
        (74.68, 72.83, "colluvium"),
        (72.83, 71.33, "coombe chalk"),
        (71.33, 70.93, "structural chalk"),
    ],
    "R7-BH5": [
        (75.86, 75.46, "ploughsoil"),
        (75.46, 74.76, "B horizon"),
        (74.76, 74.16, "flint lag"),
        (74.16, 73.86, "colluvium"),
        (73.86, 73.26, "coombe chalk"),
        (73.26, 73.06, "colluvium"),
        (73.06, 72.69, "buried soil?"),
        (72.69, 71.11, "coombe chalk"),
        (71.11, 70.80, "weathered chalk"),
    ],
    "R7-BH6": [
        (75.88, 75.55, "ploughsoil"),
        (75.55, 74.44, "B horizon"),
        (74.44, 73.36, "colluvium"),
        (73.36, 72.88, "coombe chalk"),
        (72.88, 72.67, "buried soil?"),
        (72.67, 71.08, "coombe chalk"),
        (71.08, 70.88, "weathered chalk"),
    ],
}


def intervals_for(row: dict) -> tuple[list[tuple[float, float, str]], bool, float]:
    """Return (intervals top/base/label, measured_rockhead?, gl)."""
    hid = row["id"]
    gl = float(row["gl_m_od"])
    if hid in R7_DETAILED:
        return R7_DETAILED[hid], True, gl

    tokens = [u.strip() for u in (row.get("top_units") or "").split(";") if u.strip()]
    if not tokens:
        tokens = [row.get("class_label") or row.get("classification") or "unknown"]

    if row.get("rockhead_m_od") is not None:
        rh = float(row["rockhead_m_od"])
        measured = True
    else:
        cover = DEFAULT_COVER.get(row.get("classification"), 1.5)
        rh = gl - cover
        measured = False

    if rh >= gl:
        rh = gl - 0.3

    # Drop a trailing bedrock-ish token from the superficial stack if present —
    # chalk below rockhead is drawn as the continuation block.
    superficial = list(tokens)
    while superficial and re.search(
        r"structural|bedrock|seaford|^chalk$", superficial[-1].lower()
    ):
        superficial.pop()
    if not superficial:
        superficial = tokens[:1] if tokens else ["cover"]

    span = gl - rh
    n = len(superficial)
    # Weight: topsoil/plough thinner; coombe/colluvium thicker
    weights = []
    for tok in superficial:
        tl = tok.lower()
        if re.search(r"plough|topsoil|subsoil|\bb\b|b horizon", tl):
            weights.append(0.5)
        elif re.search(r"buried|lag", tl):
            weights.append(0.35)
        else:
            weights.append(1.0)
    wsum = sum(weights)
    intervals = []
    cursor = gl
    for tok, w in zip(superficial, weights):
        thick = span * (w / wsum)
        base = cursor - thick
        intervals.append((cursor, base, tok))
        cursor = base
    # snap last base to rh
    if intervals:
        top, _, lab = intervals[-1]
        intervals[-1] = (top, rh, lab)
    return intervals, measured, gl


def draw_stick(row: dict, path: Path) -> None:
    intervals, measured, gl = intervals_for(row)
    rh = intervals[-1][1] if intervals else gl - 1
    # Zoom to the stack (Mortimore-style). 0 m OD called out in caption when far below.
    cover = max(gl - rh, 0.5)
    chalk_base = rh - max(1.5, min(cover * 1.2, 6.0))
    y_min = chalk_base - 0.4
    y_max = gl + max(1.2, cover * 0.25)

    fig, ax = plt.subplots(figsize=(5.2, 7.2), dpi=120)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#fafafa")

    # chalk stub under rockhead
    ax.add_patch(
        mpatches.Rectangle(
            (-0.55, chalk_base),
            1.1,
            rh - chalk_base,
            facecolor="#faf6e8",
            edgecolor="#333",
            linewidth=0.5,
            zorder=1,
        )
    )
    used = {}
    for top, base, lab in intervals:
        col, legend = colour_for(lab)
        ax.add_patch(
            mpatches.Rectangle(
                (-0.55, base),
                1.1,
                top - base,
                facecolor=col,
                edgecolor="#333",
                linewidth=0.45,
                zorder=2,
            )
        )
        used[legend] = col
        mid = 0.5 * (top + base)
        # Full label to the RIGHT of the stick (never truncated inside the band)
        ax.plot([0.55, 0.85], [mid, mid], color="#666", lw=0.5, zorder=3)
        ax.text(
            0.95,
            mid,
            lab,
            ha="left",
            va="center",
            fontsize=7,
            color="#222",
            zorder=3,
            clip_on=False,
        )

    ax.plot([-0.9, 0.9], [gl, gl], color="#111", lw=1.3, zorder=4)
    ax.plot(
        [-0.9, 0.9],
        [rh, rh],
        color="#6b4e2e",
        lw=1.0,
        ls="--" if not measured else "-",
        zorder=4,
    )
    ax.set_xlim(-1.4, 4.8)
    ax.set_ylim(y_min, y_max)
    ax.set_xticks([])
    ax.set_ylabel("Elevation (m OD)", fontsize=9)
    ax.set_title(f"{row['id']}  ·  GL {gl:.2f} m OD", fontsize=10, pad=6)

    mode = "Measured rockhead" if measured else "Estimated rockhead"
    detail = (
        "Printed OD intervals (Report 7)"
        if row["id"] in R7_DETAILED
        else "Schematic stack (proportional unit labels)"
    )
    # Single caption BELOW the axes — not overlapping the title
    footnote = f"{mode}. {detail}."
    if gl > 15:
        footnote += f"  ≈ 0 m OD is {gl:.0f} m below GL (below this frame)."
    else:
        ax.axhline(0, color="#1f77b4", lw=0.9, ls=":", zorder=0)
    fig.text(0.5, 0.01, footnote, ha="center", va="bottom", fontsize=7, color="#444", wrap=True)

    handles = [mpatches.Patch(facecolor=c, edgecolor="#333", label=l) for l, c in used.items()]
    handles += [
        Line2D([0], [0], color="#111", lw=1.3, label="Ground level"),
        Line2D(
            [0],
            [0],
            color="#6b4e2e",
            lw=1.0,
            ls="-" if measured else "--",
            label="Rockhead",
        ),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=6.5, framealpha=0.95)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(path, dpi=120, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_index(rows: list[dict]) -> None:
    cards = []
    for r in sorted(rows, key=lambda x: x["id"]):
        fn = safe_name(r["id"]) + ".png"
        cards.append(
            f'<a class="card" href="{fn}"><img src="{fn}" alt="{r["id"]}" loading="lazy"/>'
            f'<span>{r["id"]}<br/><small>{r.get("class_label","")}</small></span></a>'
        )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>A303 corridor — borehole sticks</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; }}
  header {{ padding: 1.2rem 1.5rem; max-width: 1200px; margin: 0 auto; }}
  header a {{ color: #c9a227; }}
  h1 {{ margin: 0 0 .4rem; font-size: 1.35rem; }}
  .note {{ color: #bbb; font-size: .9rem; line-height: 1.4; max-width: 52rem; }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: .75rem; padding: 0 1.5rem 2rem; max-width: 1200px; margin: 0 auto;
  }}
  .card {{
    background: #1a1a1a; border: 1px solid #333; border-radius: 6px;
    text-decoration: none; color: #eee; overflow: hidden; display: flex; flex-direction: column;
  }}
  .card img {{ width: 100%; height: 220px; object-fit: contain; background: #fff; }}
  .card span {{ padding: .45rem .55rem; font-size: .78rem; line-height: 1.25; }}
  .card small {{ color: #999; }}
</style>
</head>
<body>
<header>
  <h1>Schematic borehole sticks ({len(rows)})</h1>
  <p class="note">
    Linked from the <a href="../">corridor gazetteer</a>.
    Stacks are schematic from gazetteer unit labels between ground level and rockhead
    (measured where logged; otherwise class-estimated cover).
    Report&nbsp;7 BH1–BH6 use printed OD intervals. SU14SW62 is the flooding-audit stick.
    Not a substitute for the NSIP PDFs.
  </p>
</header>
<div class="grid">
{''.join(cards)}
</div>
</body>
</html>
"""
    (OUT / "index.html").write_text(html, encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = json.loads(DATA.read_text())
    for r in rows:
        path = OUT / f"{safe_name(r['id'])}.png"
        draw_stick(r, path)
    # Also include SU14SW62 from figures if present
    src = FIG / "su14sw62-stick.png"
    if src.exists():
        shutil.copy2(src, OUT / "SU14SW62.png")
    write_index(rows)
    # Extra index entry note — SU14SW62 not in gazetteer; leave as sidecar file
    print(f"wrote {len(rows)} sticks + index → {OUT}")
    if src.exists():
        print("copied SU14SW62.png")


if __name__ == "__main__":
    main()
