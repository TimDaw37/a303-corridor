#!/usr/bin/env python3
"""Build A303 corridor gazetteer: JSON, GeoJSON, and GitHub Pages HTML from data/boreholes.csv."""
from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
DATA = OUT / "data"
CSV_PATH = DATA / "boreholes.csv"

_OSGB_TF = None


def osgb_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """OSGB36 easting/northing -> WGS84 lat, lon.

    Prefer pyproj (EPSG:27700→4326). Fallback is Airy 1830 + OSGB36→WGS84 Helmert.
    """
    global _OSGB_TF
    try:
        from pyproj import Transformer

        if _OSGB_TF is None:
            _OSGB_TF = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
        lon, lat = _OSGB_TF.transform(easting, northing)
        return float(lat), float(lon)
    except Exception:
        pass
    return _osgb_to_wgs84_helmert(easting, northing)


def _osgb_to_wgs84_helmert(easting: float, northing: float) -> tuple[float, float]:
    a, b = 6377563.396, 6356256.909
    F0 = 0.9996012717
    lat0 = math.radians(49.0)
    lon0 = math.radians(-2.0)
    N0, E0 = -100000.0, 400000.0
    e2 = 1 - (b * b) / (a * a)
    n = (a - b) / (a + b)
    lat = lat0
    M = 0.0
    for _ in range(10):
        lat = ((northing - N0 - M) / (a * F0)) + lat
        Ma = (1 + n + 1.25 * n**2 + 1.25 * n**3) * (lat - lat0)
        Mb = (3 * n + 3 * n**2 + 2.625 * n**3) * math.sin(lat - lat0) * math.cos(lat + lat0)
        Mc = (1.875 * n**2 + 1.875 * n**3) * math.sin(2 * (lat - lat0)) * math.cos(2 * (lat + lat0))
        Md = (35.0 / 24.0) * n**3 * math.sin(3 * (lat - lat0)) * math.cos(3 * (lat + lat0))
        M = b * F0 * (Ma - Mb + Mc - Md)
        if abs(northing - N0 - M) < 1e-5:
            break
    sinlat, coslat = math.sin(lat), math.cos(lat)
    nu = a * F0 / math.sqrt(1 - e2 * sinlat**2)
    rho = a * F0 * (1 - e2) / (1 - e2 * sinlat**2) ** 1.5
    eta2 = nu / rho - 1
    tanlat = math.tan(lat)
    VII = tanlat / (2 * rho * nu)
    VIII = tanlat / (24 * rho * nu**3) * (5 + 3 * tanlat**2 + eta2 - 9 * tanlat**2 * eta2)
    IX = tanlat / (720 * rho * nu**5) * (61 + 90 * tanlat**2 + 45 * tanlat**4)
    X = 1 / (coslat * nu)
    XI = 1 / (coslat * 6 * nu**3) * (nu / rho + 2 * tanlat**2)
    XII = 1 / (coslat * 120 * nu**5) * (5 + 28 * tanlat**2 + 24 * tanlat**4)
    XIIA = 1 / (coslat * 5040 * nu**7) * (
        61 + 662 * tanlat**2 + 1320 * tanlat**4 + 720 * tanlat**6
    )
    dE = easting - E0
    lat_os = lat - VII * dE**2 + VIII * dE**4 - IX * dE**6
    lon_os = lon0 + X * dE - XI * dE**3 + XII * dE**5 - XIIA * dE**7
    tx, ty, tz = 446.448, -125.157, 542.060
    s = -20.4894e-6
    rx = math.radians(0.1502 / 3600)
    ry = math.radians(0.2470 / 3600)
    rz = math.radians(0.8421 / 3600)
    a_wgs = 6378137.0
    f_wgs = 1 / 298.257223563
    e2_wgs = 2 * f_wgs - f_wgs * f_wgs
    sin_lat, cos_lat = math.sin(lat_os), math.cos(lat_os)
    sin_lon, cos_lon = math.sin(lon_os), math.cos(lon_os)
    nu2 = a / math.sqrt(1 - e2 * sin_lat**2)
    x = nu2 * cos_lat * cos_lon
    y = nu2 * cos_lat * sin_lon
    z = (nu2 * (1 - e2)) * sin_lat
    x2 = tx + (1 + s) * x + (-rz) * y + ry * z
    y2 = ty + rz * x + (1 + s) * y + (-rx) * z
    z2 = tz + (-ry) * x + rx * y + (1 + s) * z
    p = math.hypot(x2, y2)
    lat_w = math.atan2(z2, p * (1 - e2_wgs))
    for _ in range(6):
        nu_w = a_wgs / math.sqrt(1 - e2_wgs * math.sin(lat_w) ** 2)
        lat_w = math.atan2(z2 + e2_wgs * nu_w * math.sin(lat_w), p)
    lon_w = math.atan2(y2, x2)
    return math.degrees(lat_w), math.degrees(lon_w)


CLASS_ORDER = [
    "periglacial_coombe",
    "colluvium",
    "chalk",
    "solution",
    "alluvium",
    "made_ground",
    "ambiguous",
]

CLASS_LABEL = {
    "periglacial_coombe": "periglacial coombe/head",
    "colluvium": "colluvium",
    "chalk": "chalk",
    "solution": "solution feature",
    "alluvium": "alluvium",
    "made_ground": "made ground",
    "ambiguous": "ambiguous",
}

# Planning Inspectorate / BGS / peer URLs for public index.html (no local paths)
SOURCE_DOC_URLS = {
    "TR010025-000429": "https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000429-6-3_ES-Appendix_10.4_PSSR.pdf",
    "TR010025-000582": "https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000582-Report%204%20-%20Western%20Portal%20and%20Approach%20%E2%80%93%20Part%201%20Text.pdf",
    "TR010025-000584": "https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000584-Report%205%20-%20Archaeological%20Evaluation%20Report%20Eastern%20Portal%20-%20Part%201%20Text.pdf",
    "TR010025-000588": "https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000588-Report%207%20-%20Electrical%20Resistance%20Tomography%20and%20Borehole%20Survey%20Report.pdf",
    "TR010025-002245": "https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-002245-A303-EIR_Reports-2-12B-G.pdf",
    "TR010025-002259": "https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-002259-A303-EIR_Reports-2-16-Gr.pdf",
    "TR010025-002269": "https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-002269-A303-EIR_Reports-2-13-Gr.pdf",
    "BGS": "https://mapapps2.bgs.ac.uk/geoindex/home.html?layer=BGSBoreholes",
}

def load_rows() -> list[dict]:
    rows: list[dict] = []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            e = float(raw["easting"])
            n = float(raw["northing"])
            lat, lon = osgb_to_wgs84(e, n)
            gl = raw.get("gl_m_od", "").strip()
            rh = raw.get("rockhead_m_od", "").strip()
            gw = (raw.get("glacial_wording") or "n").strip().lower()
            clas = (raw.get("classification") or "ambiguous").strip()
            if clas not in CLASS_LABEL:
                clas = "ambiguous"
            rec = {
                "id": raw["id"].strip(),
                "source_doc": raw.get("source_doc", "").strip(),
                "easting": round(e, 2),
                "northing": round(n, 2),
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "gl_m_od": float(gl) if gl else None,
                "rockhead_m_od": float(rh) if rh else None,
                "top_units": (raw.get("top_units") or "").strip(),
                "notes": (raw.get("notes") or "").strip(),
                "area": (raw.get("area") or "").strip(),
                "glacial_wording": "y" if gw.startswith("y") else "n",
                "classification": clas,
                "class_label": CLASS_LABEL[clas],
            }
            rows.append(rec)
    rows.sort(key=lambda r: (r["easting"], r["northing"], r["id"]))
    return rows


def to_geojson(rows: list[dict]) -> dict:
    features = []
    for r in rows:
        props = {k: v for k, v in r.items() if k not in ("lat", "lon")}
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                "properties": props,
            }
        )
    return {"type": "FeatureCollection", "features": features}


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>A boring story: A303 Stonehenge corridor boreholes</title>
<link rel="license" href="https://creativecommons.org/licenses/by-sa/4.0/"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  :root {
    --ink: #e8e0d0;
    --muted: #b7ad9a;
    --bg: #1a1814;
    --panel: #242017;
    --line: #3c362c;
    --gold: #c4a35a;
    --coombe: #6d8b74;
    --colluvium: #b08968;
    --chalk: #cfc6b0;
    --solution: #7b6b9a;
    --alluvium: #3d7ea6;
    --made: #8a6a4f;
    --ambiguous: #6c757d;
    --flag: #c23b22;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 "Palatino Linotype", Palatino, "Book Antiqua", serif; }
  header { padding: 1.4rem 1.5rem .6rem; max-width: 1400px; margin: 0 auto; }
  header h1 { font-size: 1.75rem; font-weight: 600; letter-spacing: .02em; margin: 0 0 .25rem; color: var(--gold); }
  header .sub { color: var(--muted); font-style: italic; margin: 0 0 .5rem; }
  header .lead { color: var(--ink); margin: 0; max-width: 54rem; }
  .stats { display: flex; flex-wrap: wrap; gap: .5rem; max-width: 1400px; margin: 0 auto .6rem; padding: 0 1.5rem; }
  .stat { background: var(--panel); border: 1px solid var(--line); padding: .4rem .7rem; border-radius: 4px; font-size: .85rem; }
  .stat b { color: var(--gold); }
  .sea-panel {
    max-width: 1400px; margin: 0 auto .8rem; padding: .75rem 1rem;
    background: #1f2a24; border: 1px solid #3a5344; border-radius: 4px;
    color: var(--ink); font-size: .95rem;
  }
  .sea-panel strong { color: var(--gold); }
  .legend { font: .75rem/1.4 system-ui, sans-serif; color: var(--muted); padding: 0 1.5rem .6rem; max-width: 1400px; margin: 0 auto; }
  label.chip { display: inline-flex; align-items: center; gap: .3rem; background: var(--bg); color: var(--muted); border: 1px solid var(--line); padding: .25rem .55rem; font: .78rem/1.2 system-ui, sans-serif; border-radius: 99px; cursor: pointer; }
  label.chip input { margin: 0; }
  label.chip.on { border-color: var(--gold); color: var(--ink); }
  .swatch { width: .7rem; height: .7rem; border-radius: 99px; display: inline-block; }
  .layout { display: grid; grid-template-columns: 1.2fr .8fr; gap: 0; max-width: 1400px; margin: 0 auto; border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
  #map { min-height: 72vh; background: #111; }
  .side { background: var(--panel); border-left: 1px solid var(--line); display: flex; flex-direction: column; max-height: 72vh; }
  .filters { padding: .8rem; border-bottom: 1px solid var(--line); display: flex; flex-wrap: wrap; gap: .35rem; }
  .filters input[type=search] { flex: 1 1 180px; background: var(--bg); color: var(--ink); border: 1px solid var(--line); padding: .4rem .55rem; font: inherit; }
  .chip-row { display: flex; flex-wrap: wrap; gap: .3rem; padding: 0 .8rem .55rem; }
  .chip-row .lab { font: .72rem/1.2 system-ui, sans-serif; color: var(--muted); width: 100%; margin: .15rem 0 0; letter-spacing: .04em; text-transform: uppercase; }
  .list { overflow: auto; flex: 1; }
  .card { padding: .7rem .9rem; border-bottom: 1px solid var(--line); cursor: pointer; }
  .card:hover, .card.sel { background: #2c271c; }
  .card h3 { margin: 0 0 .15rem; font-size: 1.02rem; }
  .meta { font: .78rem/1.35 system-ui, sans-serif; color: var(--muted); }
  .badge { display: inline-block; padding: 0 .4rem; border-radius: 99px; font-size: .7rem; letter-spacing: .04em; text-transform: uppercase; margin-right: .25rem; color: #111; }
  .b-periglacial_coombe { background: var(--coombe); color: #f4f1ea; }
  .b-colluvium { background: var(--colluvium); }
  .b-chalk { background: var(--chalk); }
  .b-solution { background: var(--solution); color: #eee; }
  .b-alluvium { background: var(--alluvium); color: #eee; }
  .b-made_ground { background: var(--made); color: #eee; }
  .b-ambiguous { background: var(--ambiguous); color: #eee; }
  .flag { color: var(--flag); font-weight: 600; }
  .detail { max-width: 1400px; margin: 0 auto; padding: 1.2rem 1.5rem 1.5rem; }
  .detail h2 { color: var(--gold); margin: 0 0 .3rem; }
  .detail-grid { display: grid; grid-template-columns: 1fr 140px; gap: 1rem; align-items: start; }
  @media (max-width: 700px) { .detail-grid { grid-template-columns: 1fr; } }
  .stick-panel { max-width: 160px; }
  .stick-thumb { display: block; border: 1px solid #ddd; border-radius: 4px; background: #fff; }
  .stick-thumb img { display: block; width: 100%; height: auto; }
  .stick-meta { font-size: .78rem; color: var(--muted); margin: .45rem 0 0; line-height: 1.35; }

  .kv { display: grid; grid-template-columns: 10rem 1fr; gap: .2rem .8rem; font: .9rem/1.4 system-ui, sans-serif; margin: 1rem 0; }
  .kv dt { color: var(--muted); }
  a { color: #d4c08a; }
  .notes { max-width: 720px; margin: 0 auto; padding: 1.5rem 1.5rem 2.5rem; color: var(--muted); font-size: .92rem; }
  .notes h2 { font-size: 1.05rem; color: var(--gold); margin: 1.4rem 0 .6rem; font-weight: 600; }
  .notes h2:first-child { margin-top: 0; }
  figure.xs { margin: 1.2rem 0 1.6rem; }
  figure.xs img {
    display: block; max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px;
    background: #fff; cursor: zoom-in;
  }
  figure.xs img:hover { border-color: #888; }
  figure.xs figcaption { font-size: 0.85rem; color: #555; margin-top: 0.45rem; line-height: 1.35; }
  figure.xs-narrow img { margin: 0 auto; }
  .lb-hint { font-size: 0.8rem; color: #777; margin: -.4rem 0 1rem; }
  #lightbox {
    display: none; position: fixed; inset: 0; z-index: 10000;
    background: rgba(10, 12, 16, 0.88); align-items: center; justify-content: center;
    padding: 1rem; cursor: zoom-out;
  }
  #lightbox.open { display: flex; }
  #lightbox img {
    max-width: min(96vw, 1800px); max-height: 92vh; width: auto; height: auto;
    object-fit: contain; border-radius: 4px; box-shadow: 0 8px 40px rgba(0,0,0,.45);
    background: #fff; cursor: default;
  }
  #lightbox .lb-close {
    position: absolute; top: 0.75rem; right: 1rem; border: 0; background: transparent;
    color: #fff; font-size: 1.75rem; line-height: 1; cursor: pointer; opacity: .85;
  }
  #lightbox .lb-close:hover { opacity: 1; }
  #lightbox .lb-cap {
    position: absolute; left: 0; right: 0; bottom: 0.6rem; text-align: center;
    color: #ddd; font-size: 0.85rem; padding: 0 1rem; pointer-events: none;
  }
  .notes p { margin: 0 0 .8rem; }
  .notes ul { margin: 0 0 .8rem; padding-left: 1.1rem; }
  .notes li { margin: 0 0 .25rem; }
  .unit-key { display: grid; grid-template-columns: 1.1rem 1fr; gap: .35rem .6rem; align-items: center; font: .85rem/1.35 system-ui, sans-serif; margin: .6rem 0 1rem; }
  footer { max-width: 720px; margin: 0 auto; padding: 0 1.5rem 2.5rem; color: var(--muted); font-size: .8rem; }
  footer ul { margin: .35rem 0 1rem; padding-left: 1.1rem; }
  footer li { margin: 0 0 .3rem; }
</style>
</head>
<body>
<header>
  <h1>A boring story: A303 Stonehenge corridor boreholes</h1>
  <p class="sub">Tim Daw / working 2026. CC BY-SA.</p>
  <p class="lead">Geolocated boreholes, trial pits and evaluation trenches along the A303 Amesbury–Berwick Down scheme — chalk rockhead, periglacial coombe/head, Holocene colluvium. Field “glacial” wording is flagged separately and reclassified where the reports themselves describe peri-glacial processes.</p>
</header>

<div class="stats" id="stats"></div>
<div class="sea-panel" id="seaPanel"></div>
<p class="legend">Coloured by sediment classification. Open rings mark holes whose own log uses “glacial” / till / glaciation field wording — almost always peri-glacial coombe, solifluction or solution in the same report’s interpretive text. Elevations are metres OD (Ordnance Datum), not depth below ground.</p>

<div class="layout">
  <div id="map"></div>
  <div class="side">
    <div class="filters">
      <input id="q" type="search" placeholder="Search id, units, notes, doc…"/>
    </div>
    <div class="chip-row" id="classChips"></div>
    <div class="chip-row" id="flagChips"></div>
    <div class="list" id="list"></div>
  </div>
</div>

<section class="detail" id="detail">
  <p class="meta">Select a hole or trench.</p>
</section>

<section class="notes">
  <h2>Unit key</h2>
  <div class="unit-key" id="unitKey"></div>
  <p><b>Periglacial coombe / head</b> — solifluction and gelifluction of frost-shattered chalk and flint under cold-stage climates (BGS Coombe deposits / Head). <b>Colluvium</b> — Holocene downslope wash over coombe or chalk. <b>Solution</b> — dissolution pipes / hollows, sometimes with thickened colluvium. <b>Chalk</b> — thin ploughsoil over chalk-dominated logs. <b>Made ground</b> — anthropogenic fill (often eastern portal / Countess). <b>Ambiguous</b> — reserved where the printed sheet still does not pin a clear stack.</p>

  <h2>Glacial ≠ ice on this corridor</h2>
  <p>Across Reports 4, 5 and 7 the dominant scientific language is <b>periglacial / solifluction / cryoturbation / coombe / colluvium</b>. True ice-contact till wording is rare, informal, and usually contradicted by the next sentence. <a href="https://webapps.bgs.ac.uk/memoirs/docs/B06131.html">BGS Salisbury Sheet 298</a> maps Head / Coombe on the Plain — not till. <a href="https://www.nature.com/articles/s43247-025-03105-3">Clarke &amp; Kirkland (2026)</a> conclude Salisbury Plain remained unglaciated in the Pleistocene. <a href="https://www.buystonehenge.com/the-glacial-a303/">BuyStonehenge’s desk search</a> is how this public NSIP corpus was noticed; this gazetteer is not a rebuttal essay, only a geolocated reading of the printed elevations and deposit labels.</p>

  <h2>Field “glacial” wording: why it does not mean ice</h2>
  <p>Five evaluation trenches in this gazetteer carry a <code>glacial_wording=y</code> flag. Four of them sit together on the western approach interfluve in <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000582-Report%204%20-%20Western%20Portal%20and%20Approach%20%E2%80%93%20Part%201%20Text.pdf">Report 4 (TR010025-000582)</a>; one is a separate eastern-portal phrase in <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000584-Report%205%20-%20Archaeological%20Evaluation%20Report%20Eastern%20Portal%20-%20Part%201%20Text.pdf">Report 5 (TR010025-000584)</a>. Reading the printed sheets against the same reports’ geoarchaeology shows cold-climate <b>Head / coombe</b>, not ice-sheet till.</p>

  <h3>What was written</h3>
  <ul>
    <li><b>R4-T241</b> (NGR 410399 141396, <b>99.48 m OD</b>) — natural 24102: “Compact, saluted chalk, glacial coombe deposit.” Neighbouring solution hollow 24105 is described in the interpretive text as a doline in soliflucted chalk. “Saluted” recurs elsewhere in Report 4 (“saluted chalk silt”) and is the sheet’s spelling of <b>soliflucted</b>.</li>
    <li><b>R4-T247</b> (410451 141409, <b>98.99 m OD</b>) — natural 24703: “Glacially affected coombe chalk. Very rare, subangular flint nodules, poorly sorted.” Overlain by possible colluvial subsoil 24702.</li>
    <li><b>R4-T248</b> (410488 141433, <b>98.72 m OD</b>) — natural 24803: “Glacially affected coombe chalk. Rare subangular flint nodules, poorly sorted.” Same stack pattern as T247.</li>
    <li><b>R4-T263</b> (410694 141501, <b>96.82 m OD</b>) — geological features 26307–26308: “Probably derived from a combination of glacial scouring and solution hollows”; “Probable scarring from glaciation.” The same trench also logs chalk-gravel striations (26303) and colluvium — a solution / peri-glacial hollow reading.</li>
    <li><b>R5-T511</b> (414910 142118, <b>73.2 m OD</b>) — natural 51132: deposit “laid down by fluvial action on glacial till within scraped out limestone, possibly by glacial activity or water movement.” Immediately above, 51131 is “Soliflucted chalk. Same as (51103)”; 51132–51136 are all equated to that same natural.</li>
  </ul>

  <h3>Spatial and authorship pattern</h3>
  <p>Report 4 is titled <i>Archaeological Evaluation Report: Western Portal and Approach — Part 1: Text</i> (April 2019; HE551506-AMW-HER-Z2_ML_M00_Z-RP-LH-0001). Corporate authorship is <b>Wessex Archaeology Ltd</b> for AECOM–Mace–WSP (AmW) on behalf of Highways England. Reports 4 and 5 share the same document author in the PDF metadata; no individual trench-sheet logger initials are printed in the Part 1 context tables. Report 4 §5.2 explicitly groups Trenches 241, 247, 248 and 263 (with others) as the central dry-valley / coombe crossing where “the natural geology comprised soliflucted or heavily cryoturbated Chalk” with “frequent periglacial stripes.” Those four flagged trenches span only ~300 m east–west at ~97–99.5 m OD on Normanton Down high ground near the proposed western portal (~100 m aOD) — one evaluation area, one report, one coombe-crossing cluster (<code>glacial_wording_cluster=western_r4</code>), not four independent ice claims. Winterbourne Stoke Crossroads barrow cemetery lies to the north-west at Longbarrow; the Report 7 Winterbourne Stoke <i>coombe floor</i> is a different, lower landform.</p>
  <p>Report 5 is the matching <i>Eastern Portal</i> evaluation (Countess West; HE551506-AMW-HER-Z4-GN_000_Z-RP-LH-0001; same corporate line and PDF author). T511 sits alone in that eastern package, ~4.4 km east of the western cluster, on the lower approach falling toward the Avon (~70 m aOD at the far east of that site).</p>

  <h3>What the same documents mean by coombe / solifluction</h3>
  <p>Report 5’s geoarchaeology chapter defines coombe deposits as “material soliflucted downslope under periglacial conditions (alternate freeze-thawing), likely during the last glacial period.” Report 4’s results section uses the same process language: soliflucted / cryoturbated chalk, periglacial stripes and striations (e.g. T214, T215, T246). <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000588-Report%207%20-%20Electrical%20Resistance%20Tomography%20and%20Borehole%20Survey%20Report.pdf">Report 7</a> likewise places Pleistocene periglacial coombe over chalk rockhead. <a href="https://webapps.bgs.ac.uk/lexicon/lexicon.cfm?pub=COD">BGS Coombe deposits (COD)</a> are solifluction/gelifluction Head in chalk valleys — parent unit Head, not till. On Sheet 298 the Quaternary inventory is clay-with-flints, head variants, terrace deposits and alluvium; no ice-sheet till is mapped on the chalk plain around Stonehenge.</p>

  <h3>Sedimentological tests a true till would need</h3>
  <p>Ice-contact till (lodgement or melt-out diamicton) is normally argued from a combination of: a poorly sorted diamict fabric with a measurable clast orientation (fabric analysis); a significant exotic far-travelled clast assemblage; glacitectonic structures or bullet-shaped / striated clasts with consistent orientations; and a stratigraphic context compatible with ice-marginal deposition. None of these five trench sheets supplies that package. They record chalky coombe / soliflucted chalk, local flint, solution hollows, or — in T511 — an informal “till” sentence that the same register immediately equates to soliflucted chalk natural. Sample <b>51138</b> is a 40 L bulk of context <b>51135</b> (light green sand and degraded chalk), later assessed for charred plant remains — it is not a till micromorphology or clast-provenance assay.</p>

  <h3>Why high-ground “glacial coombe chalk” is still Head</h3>
  <p>Ground levels at T241–T263 (~96.8–99.5 m OD) sit on the western approach interfluve / shallow coombe head near the western portal, tens of metres above Report 7’s Winterbourne Stoke coombe-floor rockhead (~71–76 m OD) and far above Holocene sea level (~0 m OD). Coombe and Head routinely mantle chalk slopes and interfluves under periglacial freeze–thaw; the adjective “glacial” on a coombe-chalk sheet is cold-stage climate shorthand, not evidence that an ice sheet overrode Normanton Down. Neighbouring blanks and naturals in the same appendix use the explicit labels “Soliflucted chalk”, “periglacial stripes”, and “Cryoturbated chalk.”</p>

  <h3>R5-T511 special case</h3>
  <p>The eastern “glacial till… glacial activity” phrase is the only till wording among the five, but it is field slang inside a machine-trench natural that the register itself identifies as soliflucted chalk (51131 = 51103). Report 5’s interpretive geoarchaeology never elevates T511 to ice-laid diamicton; coombe remains peri-glacial solifluction. Treat 51132 as a flagged wording outlier on the lower eastern portal (~73 m OD), not as a mapped till sheet.</p>

  <h2>Elevations versus sea level</h2>
  <h2 id="cross-sections">Cross-sections (m OD)</h2>
  <p>Elevation sections modelled on Mortimore et&nbsp;al. (2017) Fig.&nbsp;16 (<i>Proc. Geol. Assoc.</i> 128) — the chalk corridor plotted in metres OD, the same visual language as the <a href="https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html">January 2026 Stonehenge Bottom flooding audit</a>. Stacks are from printed Report&nbsp;7 sheets; corridor points are this gazetteer.</p>
  <p class="lb-hint">Click a figure to enlarge · Esc or click outside to close</p>
  <figure class="xs">
    <img class="expandable" src="figures/winterbourne-stoke-section.png" tabindex="0" role="button" alt="Winterbourne Stoke coombe N–S cross-section, Report 7 BH1–BH6, elevation in metres OD" width="100%" loading="lazy" />
    <figcaption>Winterbourne Stoke coombe (Report 7 BH1–BH6). Periglacial coombe chalk under Holocene colluvium; rockhead ≈ 71–76 m OD. Holocene sea level ≈ 0 m OD lies ~70 m below the frame. The thin dark band in BH5 and BH6 is <b>not till</b> — see note below.</figcaption>
  </figure>
  <p class="xs-note"><b>That dark band in BH5 and BH6 is not glacial till.</b> Report&nbsp;7 (TR010025-000588) logs a thin dark brown flinty silty clay <i>within</i> the periglacial coombe chalk in those two holes only. The report’s own alternatives are (1) a possible Windermere Interstadial buried soil, later overridden by renewed solifluction, or (2) a clay-with-flint lined dissolution pipe — the lower contacts are sharp, which is a poor fit for a normal in-situ soil profile. Either way it is a local coombe-hosted feature a few tens of centimetres thick, sandwiched in structureless chalk Head, not an ice-laid diamicton and not a sheet across the Plain. The corridor long-section’s brown veneer is the same family of deposits (ploughsoil, colluvium, coombe/head), drawn schematically between ground level and rockhead — again Head/coombe, not till.</p>
  <figure class="xs">
    <img class="expandable" src="figures/corridor-long-section.png" tabindex="0" role="button" alt="A303 corridor west–east long section of ground level and rockhead in metres OD" width="100%" loading="lazy" />
    <figcaption>Corridor long-section (W→E). Continuous ground level and rockhead over a solid chalk block (Mortimore-style long-section). Superficial veneer between the two lines; rockhead measured at squares, elsewhere class-estimated. SU14SW62 at 96 m OD.</figcaption>
  </figure>
  <figure class="xs xs-narrow">
    <img class="expandable" src="figures/su14sw62-stick.png" tabindex="0" role="button" alt="SU14SW62 Stonehenge Bottom borehole stick log in metres OD" width="320" loading="lazy" />
    <figcaption>SU14SW62 (Stonehenge Bottom) — thin periglacial head over Seaford Chalk; no Holocene aquatic facies. Same audit borehole as the January 2026 post.</figcaption>
  </figure>

  <p>Holocene eustatic sea level sits near <b>~0 m OD</b>. Ground levels in this gazetteer sit from <b>__GL_MIN__ to __GL_MAX__ m OD</b>. Winterbourne Stoke coombe rockhead (Report 7 BH1–BH6) is about <b>71–76 m OD</b>. BGS SU14SW62 at Stonehenge Bottom is <b>96.00 m OD</b> with no Holocene marine/aquatic facies. High Holocene water covering Stonehenge Bottom / the Plain is incompatible with these elevations — same argument as the January 2026 flooding audit.</p>
  <p class="cite">Mortimore, R.N., Gelder, A., Moore, J., Brooks, S., Gallagher, L. &amp; Farrant, A.R. (2017). Stonehenge — a unique Late Cretaceous phosphatic Chalk geology. <i>Proceedings of the Geologists’ Association</i> 128, 564–598. Fig.&nbsp;16 is the style model for the elevation sections above.</p>

  <h2 id="sticks-note">Schematic sticks for every hole</h2>
  <p>Every gazetteer pin has a schematic OD stick in the separate <a href="sticks/"><code>sticks/</code> directory</a> (also linked from the detail panel). Most are proportional stacks from the unit-label string between ground level and rockhead (measured where logged; otherwise a class-based cover estimate). Report&nbsp;7 BH1–BH6 use the printed OD intervals; <a href="sticks/SU14SW62.png">SU14SW62</a> is the flooding-audit stick. These are reading aids, not substitutes for the NSIP sheets.</p>

  <h2>How to read a pin</h2>
  <p>Each record carries OSGB36 easting/northing as printed, ground level (m OD) where printed, rockhead (m OD) only where the log states it (never invented), a short unit stack, and a <code>glacial_wording</code> flag independent of <code>classification</code>. Source document IDs link to the Planning Inspectorate published PDF where known.</p>

  <h2>Sources</h2>
  <ul>
    <li>NSIP / National Highways factual reports (Planning Inspectorate):
      <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000429-6-3_ES-Appendix_10.4_PSSR.pdf">TR010025-000429</a> (PSSR);
      <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000582-Report%204%20-%20Western%20Portal%20and%20Approach%20%E2%80%93%20Part%201%20Text.pdf">000582</a> Report 4 Western Portal;
      <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000584-Report%205%20-%20Archaeological%20Evaluation%20Report%20Eastern%20Portal%20-%20Part%201%20Text.pdf">000584</a> Report 5 Eastern Portal;
      <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-000588-Report%207%20-%20Electrical%20Resistance%20Tomography%20and%20Borehole%20Survey%20Report.pdf">000588</a> Report 7 ERT/boreholes;
      <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-002245-A303-EIR_Reports-2-12B-G.pdf">002245</a> Phase 6 GI;
      <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-002259-A303-EIR_Reports-2-16-Gr.pdf">002259</a> Phase 7B factual;
      <a href="https://nsip-documents.planninginspectorate.gov.uk/published-documents/TR010025-002269-A303-EIR_Reports-2-13-Gr.pdf">002269</a> Phase 7a(i) factual.</li>
    <li><a href="https://mapapps2.bgs.ac.uk/geoindex/home.html?layer=BGSBoreholes">BGS GeoIndex boreholes</a> (incl. SU14SW62).</li>
    <li><a href="https://webapps.bgs.ac.uk/lexicon/lexicon.cfm?pub=COD">BGS Coombe deposits lexicon (COD)</a>;
        <a href="https://webapps.bgs.ac.uk/memoirs/docs/B06131.html">Salisbury Sheet 298 memoir brief</a>.</li>
    <li>Daw, T. 2026. <a href="https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html">Auditing the claim of Holocene flooding of Stonehenge Bottom</a>.</li>
    <li>Clarke, A.P. &amp; Kirkland, C.L. 2026. <a href="https://www.nature.com/articles/s43247-025-03105-3"><i>Commun. Earth Environ.</i> s43247-025-03105-3</a>.</li>
    <li>Corpus noticed via <a href="https://www.buystonehenge.com/the-glacial-a303/">BuyStonehenge — The glacial A303</a> (desk search only; not a source of elevations).</li>
  </ul>
</section>

<footer>
  <h2 style="font-size:1.05rem;color:var(--gold);margin:0 0 .6rem;font-weight:600;">References</h2>
  <ul>
    <li>National Highways / NSIP A303 Amesbury to Berwick Down — see <b>Sources</b> above for live Planning Inspectorate PDFs (TR010025-000429, -000582, -000584, -000588, -002245, -002259, -002269).</li>
    <li>Daw, T. 2026. Auditing the claim of Holocene flooding of Stonehenge Bottom. <a href="https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html">sarsen.org</a> — BGS SU14SW62 @ 96.00 m OD.</li>
    <li><a href="https://webapps.bgs.ac.uk/memoirs/docs/B06131.html">BGS Salisbury Sheet 298</a>;
        <a href="https://webapps.bgs.ac.uk/lexicon/lexicon.cfm?pub=COD">Coombe deposits (COD)</a>;
        <a href="https://mapapps2.bgs.ac.uk/geoindex/home.html?layer=BGSBoreholes">GeoIndex</a>.</li>
    <li>Clarke, A.P. &amp; Kirkland, C.L. 2026. <a href="https://www.nature.com/articles/s43247-025-03105-3"><i>Commun. Earth Environ.</i></a> — Plain unglaciated; negligible Preseli zircon fingerprint.</li>
    <li>Quote concordance: see <code>NOTES.md</code> in this repo.</li>
  </ul>
  <p>Original compilation, classification flags and code<br/>
  © Tim Daw 2026, licensed <a rel="license" href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</p>
  <p>Underlying GI logs © National Highways / examination library. This is a research gazetteer, not a substitute for the published factual reports. Inclusion does not imply public access to land.</p>
</footer>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const HOLES = __HOLES_JSON__;
const SOURCE_DOC_URLS = __SOURCE_DOC_URLS__;
const COLOUR = {
  periglacial_coombe: '#6d8b74',
  colluvium: '#b08968',
  chalk: '#cfc6b0',
  solution: '#7b6b9a',
  alluvium: '#3d7ea6',
  made_ground: '#8a6a4f',
  ambiguous: '#6c757d'
};
const CLASS_ORDER = __CLASS_ORDER__;
const CLASS_LABEL = __CLASS_LABEL__;
const GL_MIN = __GL_MIN__;
const GL_MAX = __GL_MAX__;
const N_FLAG = __N_FLAG__;
const N_ROCK = __N_ROCK__;

const map = L.map('map').setView([51.178, -1.84], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18, attribution: '&copy; OpenStreetMap'
}).addTo(map);

if (!map.getPane('holes')) {
  map.createPane('holes');
  map.getPane('holes').style.zIndex = 650;
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

function fmtOd(v) {
  return (v === null || v === undefined || v === '') ? '—' : Number(v).toFixed(2) + ' m OD';
}

function sourceDocHtml(doc) {
  const url = SOURCE_DOC_URLS[doc];
  if (!url) return esc(doc || '—');
  return `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(doc)}</a>`;
}

const markers = {};
const layer = L.layerGroup().addTo(map);
HOLES.forEach(h => {
  const col = COLOUR[h.classification] || '#888';
  const flagged = h.glacial_wording === 'y';
  const m = L.circleMarker([h.lat, h.lon], {
    radius: flagged ? 8 : 6,
    color: flagged ? '#c23b22' : '#1a1814',
    weight: flagged ? 2.5 : 1,
    fillColor: col,
    fillOpacity: 0.9,
    pane: 'holes'
  }).bindTooltip(h.id + (h.gl_m_od != null ? ' · ' + h.gl_m_od + ' m OD' : ''));
  m.on('click', () => select(h.id, true));
  markers[h.id] = m;
  m.addTo(layer);
});

function makeChips(el, values, kind, labels) {
  el.innerHTML = `<div class="lab">${kind}</div>` + values.map(v => {
    const col = kind === 'classification' ? COLOUR[v] : '';
    const sw = kind === 'classification' ? `<span class="swatch" style="background:${col}"></span>` : '';
    const lab = labels ? (labels[v] || v) : v;
    return `<label class="chip on"><input type="checkbox" data-kind="${kind}" value="${esc(v)}" checked/> ${sw}${esc(lab)}</label>`;
  }).join(' ');
  el.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('change', () => {
      inp.parentElement.classList.toggle('on', inp.checked);
      renderList();
    });
  });
}

const present = CLASS_ORDER.filter(c => HOLES.some(h => h.classification === c));
makeChips(document.getElementById('classChips'), present, 'classification', CLASS_LABEL);
makeChips(document.getElementById('flagChips'), ['n', 'y'], 'glacial_wording', {
  n: 'no glacial wording',
  y: 'glacial wording flagged'
});

document.getElementById('unitKey').innerHTML = present.map(c =>
  `<span class="swatch" style="background:${COLOUR[c]}"></span><span>${esc(CLASS_LABEL[c] || c)}</span>`
).join('');

function selected(kind) {
  return [...document.querySelectorAll(`input[data-kind="${kind}"]:checked`)].map(i => i.value);
}

function filtered() {
  const q = document.getElementById('q').value.toLowerCase();
  const classes = new Set(selected('classification'));
  const flags = new Set(selected('glacial_wording'));
  return HOLES.filter(h => {
    if (classes.size && !classes.has(h.classification)) return false;
    if (flags.size && !flags.has(h.glacial_wording)) return false;
    if (!q) return true;
    const blob = [h.id, h.source_doc, h.top_units, h.notes, h.area, h.class_label, h.classification].join(' ').toLowerCase();
    return blob.includes(q);
  });
}

function renderList() {
  const rows = filtered();
  const el = document.getElementById('list');
  el.innerHTML = rows.map(h => `
    <div class="card" data-id="${esc(h.id)}">
      <div><span class="badge b-${esc(h.classification)}">${esc(h.class_label)}</span>
      ${h.glacial_wording === 'y' ? '<span class="flag meta">glacial wording</span>' : ''}
      </div>
      <h3>${esc(h.id)}</h3>
      <div class="meta">${fmtOd(h.gl_m_od)}${h.rockhead_m_od != null ? ' · rockhead ' + fmtOd(h.rockhead_m_od) : ''} · ${sourceDocHtml(h.source_doc)}</div>
    </div>`).join('') || '<div class="card">No holes match.</div>';
  el.querySelectorAll('.card[data-id]').forEach(card => {
    card.addEventListener('click', () => select(card.dataset.id, true));
  });
  Object.values(markers).forEach(m => layer.removeLayer(m));
  rows.forEach(h => markers[h.id].addTo(layer));
}

function select(id, pan) {
  const h = HOLES.find(x => x.id === id);
  if (!h) return;
  document.querySelectorAll('.card').forEach(c => c.classList.toggle('sel', c.dataset.id === id));
  if (pan) map.setView([h.lat, h.lon], Math.max(map.getZoom(), 14));
  if (markers[id].openTooltip) markers[id].openTooltip();
  const stickFile = 'sticks/' + String(h.id).replace(/[^\w.\-]+/g, '_') + '.png';
  document.getElementById('detail').innerHTML = `
    <span class="badge b-${esc(h.classification)}">${esc(h.class_label)}</span>
    ${h.glacial_wording === 'y' ? '<span class="flag">glacial wording on this log</span>' : ''}
    <h2>${esc(h.id)}</h2>
    <p class="meta">${sourceDocHtml(h.source_doc)}</p>
    <div class="detail-grid">
      <div>
        <dl class="kv">
          <dt>OSGB36</dt><dd>E ${h.easting} · N ${h.northing}</dd>
          <dt>Ground level</dt><dd>${fmtOd(h.gl_m_od)}</dd>
          <dt>Rockhead</dt><dd>${fmtOd(h.rockhead_m_od)}</dd>
          <dt>Unit stack</dt><dd>${esc(h.top_units || '—')}</dd>
          <dt>Area</dt><dd>${esc(h.area || '—')}</dd>
          <dt>Classification</dt><dd>${esc(h.class_label)}</dd>
          <dt>Glacial wording</dt><dd>${h.glacial_wording === 'y' ? 'yes (field slang flagged)' : 'no'}</dd>
          <dt>Source PDF</dt><dd>${sourceDocHtml(h.source_doc)}</dd>
          <dt>Map</dt><dd><a href="https://www.openstreetmap.org/?mlat=${h.lat}&mlon=${h.lon}#map=16/${h.lat}/${h.lon}" target="_blank" rel="noopener">OpenStreetMap</a></dd>
          <dt>Stick</dt><dd><a href="${stickFile}" target="_blank" rel="noopener">Full-size schematic</a>
            · <a href="sticks/">all sticks</a></dd>
        </dl>
        <p>${esc(h.notes || '')}</p>
      </div>
      <div class="stick-panel">
        <a class="stick-thumb" href="${stickFile}" title="Open schematic stick">
          <img class="expandable" src="${stickFile}" alt="Schematic stick for ${esc(h.id)}" loading="lazy"/>
        </a>
        <p class="stick-meta">Schematic OD stick — click to enlarge. Unit thicknesses are proportional unless Report&nbsp;7 printed intervals.</p>
      </div>
    </div>`;
  // re-bind lightbox for newly injected expandable img
  const fresh = document.querySelector('#detail img.expandable');
  if (fresh && window._bindStickLightbox) window._bindStickLightbox(fresh);
}

document.getElementById('q').addEventListener('input', renderList);

document.getElementById('stats').innerHTML = `
  <div class="stat"><b>${HOLES.length}</b> holes / trenches</div>
  <div class="stat"><b>${GL_MIN.toFixed(2)}–${GL_MAX.toFixed(2)}</b> m OD ground level</div>
  <div class="stat"><b>${N_ROCK}</b> with rockhead</div>
  <div class="stat"><b>${N_FLAG}</b> glacial_wording flagged</div>
`;

document.getElementById('seaPanel').innerHTML =
  `<strong>Holocene sea ~0 m OD</strong>; corridor ground levels in this gazetteer from <strong>${GL_MIN.toFixed(2)} to ${GL_MAX.toFixed(2)} m OD</strong>. ` +
  `That gap falsifies high Holocene marine water over Stonehenge Bottom / the Plain — see ` +
  `<a href="https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html">the January 2026 flooding audit</a>.`;

renderList();
const bounds = L.latLngBounds(HOLES.map(h => [h.lat, h.lon]));
if (bounds.isValid()) map.fitBounds(bounds.pad(0.08));
</script>

<div id="lightbox" hidden aria-modal="true" role="dialog" aria-label="Enlarged figure">
  <button type="button" class="lb-close" aria-label="Close">&times;</button>
  <img alt="" />
  <div class="lb-cap"></div>
</div>
<script>
(function () {
  const lb = document.getElementById('lightbox');
  const lbImg = lb.querySelector('img');
  const lbCap = lb.querySelector('.lb-cap');
  const closeBtn = lb.querySelector('.lb-close');

  function openLb(img) {
    lbImg.src = img.currentSrc || img.src;
    lbImg.alt = img.alt || '';
    const cap = img.closest('figure') && img.closest('figure').querySelector('figcaption');
    lbCap.textContent = cap ? cap.textContent : '';
    lb.hidden = false;
    lb.classList.add('open');
    document.documentElement.style.overflow = 'hidden';
    closeBtn.focus();
  }
  function closeLb() {
    lb.classList.remove('open');
    lb.hidden = true;
    lbImg.removeAttribute('src');
    document.documentElement.style.overflow = '';
  }

  function bindExpandable(img) {
    if (!img || img.dataset.lbBound) return;
    img.dataset.lbBound = '1';
    img.addEventListener('click', (e) => { e.preventDefault(); openLb(img); });
    img.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openLb(img); }
    });
  }
  document.querySelectorAll('img.expandable').forEach(bindExpandable);
  window._bindStickLightbox = bindExpandable;
  closeBtn.addEventListener('click', (e) => { e.stopPropagation(); closeLb(); });
  lb.addEventListener('click', (e) => { if (e.target === lb) closeLb(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && lb.classList.contains('open')) closeLb();
  });
})();
</script>
</body>
</html>
"""


def main() -> None:
    rows = load_rows()
    gls = [r["gl_m_od"] for r in rows if r["gl_m_od"] is not None]
    rhs = [r["rockhead_m_od"] for r in rows if r["rockhead_m_od"] is not None]
    n_flag = sum(1 for r in rows if r["glacial_wording"] == "y")
    gl_min, gl_max = (min(gls), max(gls)) if gls else (0.0, 0.0)

    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "boreholes.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (DATA / "boreholes.geojson").write_text(
        json.dumps(to_geojson(rows), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    html = (
        HTML.replace("__HOLES_JSON__", json.dumps(rows, ensure_ascii=False))
        .replace("__SOURCE_DOC_URLS__", json.dumps(SOURCE_DOC_URLS))
        .replace("__CLASS_ORDER__", json.dumps(CLASS_ORDER))
        .replace("__CLASS_LABEL__", json.dumps(CLASS_LABEL))
        .replace("__GL_MIN__", f"{gl_min:.2f}")
        .replace("__GL_MAX__", f"{gl_max:.2f}")
        .replace("__N_FLAG__", str(n_flag))
        .replace("__N_ROCK__", str(len(rhs)))
    )
    # also fill the notes section placeholders that use the same tokens
    (OUT / "index.html").write_text(html, encoding="utf-8")

    print(f"holes: {len(rows)}")
    print(f"GL OD: {gl_min:.2f} .. {gl_max:.2f}")
    print(f"rockhead: {len(rhs)}; glacial_wording y: {n_flag}")
    print(f"wrote {DATA / 'boreholes.json'}")
    print(f"wrote {DATA / 'boreholes.geojson'}")
    print(f"wrote {OUT / 'index.html'}")
    print("by classification:", dict(Counter(r["classification"] for r in rows)))


if __name__ == "__main__":
    main()
