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


def load_bgs_fc() -> dict:
    """Slim FeatureCollection from data/bgs_boreholes_index.json (already corridor-cropped)."""
    src = DATA / "bgs_boreholes_index.json"
    if not src.is_file():
        return {"type": "FeatureCollection", "features": []}
    raw = json.loads(src.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "features" in raw:
        return raw
    features = []
    for r in raw:
        e, n = float(r["e"]), float(r["n"])
        lat, lon = osgb_to_wgs84(e, n)
        scan = r.get("scan")
        if isinstance(scan, str) and scan.strip().lower() in ("not available", "n/a", "none", ""):
            scan = None
        ags = r.get("ags") or None
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
                "properties": {
                    "ref": r.get("ref"),
                    "name": r.get("name"),
                    "e": round(e, 1),
                    "n": round(n, 1),
                    "len": r.get("len"),
                    "year": r.get("year"),
                    "bgs_id": r.get("bgs_id"),
                    "SCAN_URL": scan,
                    "AGS_LOG_URL": ags,
                },
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
  html, body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 16px/1.5 "Palatino Linotype", Palatino, "Book Antiqua", serif;
    overflow-x: hidden; max-width: 100%;
  }
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
  #map { min-height: 72vh; height: 72vh; background: #111; position: relative; }
  .side { background: var(--panel); border-left: 1px solid var(--line); display: flex; flex-direction: column; max-height: 72vh; min-height: 0; }
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
  .leaflet-control-layers {
    background: var(--panel); color: var(--ink); border: 1px solid var(--line);
    font: .78rem/1.35 system-ui, sans-serif;
  }
  .leaflet-control-layers-toggle { background-color: var(--panel); }
  .leaflet-control-layers label { color: var(--ink); }
  .leaflet-control-layers-separator { border-top-color: var(--line); }

  .cover-legend {
    background: rgba(36, 32, 23, 0.92);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 3px;
    padding: .28rem .4rem .3rem;
    font: .62rem/1.2 system-ui, sans-serif;
    box-shadow: 0 1px 3px rgba(0,0,0,.4);
    line-height: 1.15;
  }
  .cover-legend .bar {
    display: flex;
    align-items: flex-end;
    gap: .2rem;
  }
  .cover-legend .sw {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: .1rem;
  }
  .cover-legend .sw i {
    display: block;
    width: .55rem;
    height: .55rem;
    border-radius: 99px;
    border: 1px solid #2a1808;
  }
  .cover-legend .sw b {
    font-weight: 500;
    color: var(--muted);
    font-size: .55rem;
  }
  .cover-legend .sep {
    width: 1px;
    height: 1.1rem;
    background: var(--line);
    margin: 0 .15rem .15rem;
  }
  .cover-legend .ring {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: .1rem;
  }
  .cover-legend .ring i {
    display: block;
    width: .55rem;
    height: .55rem;
    border-radius: 99px;
    background: #fec44f;
  }
  .cover-legend .ring.measured i { border: 2px solid #2a1808; }
  .cover-legend .ring.estimated i { border: 1px solid #a67c52; }
  .cover-legend .ring b {
    font-weight: 500;
    color: var(--muted);
    font-size: .5rem;
  }

  /* —— Mobile / standing-back —— */
  @media (max-width: 900px) {
    .layout { grid-template-columns: 1fr; }
    header { padding: .9rem 1rem .4rem; }
    header h1 { font-size: 1.35rem; }
    header .lead { font-size: .92rem; line-height: 1.4; }
    .stats, .legend, .sea-panel { padding-left: 1rem; padding-right: 1rem; }
    .sea-panel { font-size: .88rem; padding: .55rem .75rem; }
    #map { min-height: 52vh; height: 52vh; }
    .side {
      border-left: none;
      border-top: 1px solid var(--line);
      max-height: 40vh;
      height: 40vh;
    }
    label.chip { padding: .4rem .7rem; font-size: .82rem; min-height: 2rem; }
    .filters input[type=search] { font-size: 1rem; padding: .5rem .6rem; }
    .leaflet-control-attribution {
      font-size: 9px !important; max-width: 55vw; line-height: 1.15;
    }
    .cover-legend { transform: scale(0.92); transform-origin: bottom left; max-width: 46vw; }
    .map-read-note { max-width: min(92vw, 280px); font-size: .68rem; }
    .landmark-label { font-size: 10px !important; }
  }
  @media (max-width: 600px) {
    header { padding: .7rem .75rem .3rem; }
    header h1 { font-size: 1.2rem; }
    header .sub { font-size: .85rem; margin-bottom: .35rem; }
    header .lead { font-size: .86rem; }
    #map { min-height: 50vh; height: 50vh; }
    .side { max-height: 38vh; height: 38vh; }
    .detail { padding: 1rem .85rem 1.2rem; }
    .kv { grid-template-columns: 7.5rem 1fr; font-size: .85rem; }
    .leaflet-bottom.leaflet-right .leaflet-control-attribution { max-width: 48vw; }
    .cover-legend { max-width: 42vw; padding: .2rem .3rem; }
  }

  .detail-actions { display: flex; flex-wrap: wrap; gap: .45rem; margin: .6rem 0 0; }
  .detail-actions a, .detail-actions button {
    display: inline-block; background: var(--bg); color: var(--gold);
    border: 1px solid var(--line); border-radius: 4px;
    padding: .4rem .7rem; font: .8rem/1.2 system-ui, sans-serif;
    text-decoration: none; cursor: pointer;
  }
  .detail-actions a:hover, .detail-actions button:hover { border-color: var(--gold); }
  figure.xs.flash-hi {
    outline: 2px solid var(--gold); outline-offset: 3px;
    transition: outline-color .3s;
  }

  .map-read-note {
    background: rgba(36, 32, 23, 0.94);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: .45rem .55rem .5rem;
    font: .72rem/1.35 system-ui, sans-serif;
    max-width: 260px;
    box-shadow: 0 2px 8px rgba(0,0,0,.35);
  }
  .map-read-note h4 {
    margin: 0 1.4rem .3rem 0; color: var(--gold);
    font-size: .78rem; font-weight: 600; letter-spacing: .02em;
  }
  .map-read-note p { margin: 0 0 .28rem; color: var(--muted); }
  .map-read-note p:last-child { margin-bottom: 0; }
  .map-read-note .dismiss {
    position: absolute; top: .2rem; right: .35rem;
    border: 0; background: transparent; color: var(--muted);
    font-size: 1.1rem; line-height: 1; cursor: pointer; padding: .15rem .25rem;
  }
  .map-read-note .dismiss:hover { color: var(--ink); }
  .map-read-note-wrap { position: relative; }

  .landmark-label {
    background: rgba(26, 24, 20, 0.78);
    color: #e8e0d0;
    border: 1px solid #3c362c;
    border-radius: 3px;
    padding: 1px 5px;
    font: 11px/1.25 system-ui, sans-serif;
    white-space: nowrap;
    box-shadow: 0 1px 3px rgba(0,0,0,.35);
    pointer-events: none;
  }
  .rh-label {
    background: transparent; border: 0; box-shadow: none;
    color: #d4c08a; font: 10px/1 system-ui, sans-serif;
    text-shadow: 0 0 3px #1a1814, 0 1px 2px #000;
    white-space: nowrap; pointer-events: none;
  }
</style>
</head>
<body>
<header>
  <h1>A boring story: A303 Stonehenge corridor boreholes</h1>
  <p class="sub">Tim Daw / working 2026. CC BY-SA.</p>
  <p class="lead">Geolocated A303 Highways / NSIP boreholes, trial pits and trenches (classified gazetteer), plus BGS GeoIndex pins across the same LiDAR rectangle — chalk rockhead, periglacial coombe/head, Holocene colluvium. Field “glacial” wording is flagged separately and reclassified where the reports themselves describe peri-glacial processes. Counts are two piles (not additive): many Highways logs also sit in BGS.</p>
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

  <h3>Chalk control landscape</h3>
  <p>Where Anglian ice overrode chalk and left a preserved record — for example Royston to Saffron Walden — maps and boreholes show chalky till / Drift on chalk.
  This corridor does not: Sheet&nbsp;298 is Head / coombe, and the flagged “glacial” trenches read as peri-glacial Head, not till-on-chalk.
  That is a like-for-like chalk comparison, not a claim that ice can never exist without till everywhere
  (<a href="https://doi.org/10.1016/j.pgeola.2024.12.002">Lee &amp; Roberson 2025</a>).</p>

  <h3>Why high-ground “glacial coombe chalk” is still Head</h3>
  <p>Ground levels at T241–T263 (~96.8–99.5 m OD) sit on the western approach interfluve / shallow coombe head near the western portal, tens of metres above Report 7’s Winterbourne Stoke coombe-floor rockhead (~71–76 m OD) and far above Holocene sea level (~0 m OD). Coombe and Head routinely mantle chalk slopes and interfluves under periglacial freeze–thaw; the adjective “glacial” on a coombe-chalk sheet is cold-stage climate shorthand, not evidence that an ice sheet overrode Normanton Down. Neighbouring blanks and naturals in the same appendix use the explicit labels “Soliflucted chalk”, “periglacial stripes”, and “Cryoturbated chalk.”</p>

  <h3>R5-T511 special case</h3>
  <p>The eastern “glacial till… glacial activity” phrase is the only till wording among the five, but it is field slang inside a machine-trench natural that the register itself identifies as soliflucted chalk (51131 = 51103). Report 5’s interpretive geoarchaeology never elevates T511 to ice-laid diamicton; coombe remains peri-glacial solifluction. Treat 51132 as a flagged wording outlier on the lower eastern portal (~73 m OD), not as a mapped till sheet.</p>

  <h2>Elevations versus sea level</h2>
  <h2 id="cross-sections">Cross-sections (m OD)</h2>
  <p>Elevation sections modelled on Mortimore et&nbsp;al. (2017) Fig.&nbsp;16 (<i>Proc. Geol. Assoc.</i> 128) — the chalk corridor plotted in metres OD, the same visual language as the <a href="https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html">January 2026 Stonehenge Bottom flooding audit</a>. Stacks are from printed Report&nbsp;7 sheets; corridor points are this gazetteer.</p>
  <p class="lb-hint">Click a figure to enlarge · Esc or click outside to close</p>
  <figure class="xs" id="winterbourne-stoke-section">
    <img class="expandable" src="figures/winterbourne-stoke-section.png" tabindex="0" role="button" alt="Winterbourne Stoke coombe N–S cross-section, Report 7 BH1–BH6, elevation in metres OD" width="100%" loading="lazy" />
    <figcaption>Winterbourne Stoke coombe (Report 7 BH1–BH6). Periglacial coombe chalk under Holocene colluvium; rockhead ≈ 71–76 m OD. Holocene sea level ≈ 0 m OD lies ~70 m below the frame. The thin dark band in BH5 and BH6 is <b>not till</b> — see note below.</figcaption>
  </figure>
  <p class="xs-note"><b>That dark band in BH5 and BH6 is not glacial till.</b> Report&nbsp;7 (TR010025-000588) logs a thin dark brown flinty silty clay <i>within</i> the periglacial coombe chalk in those two holes only. The report’s own alternatives are (1) a possible Windermere Interstadial buried soil, later overridden by renewed solifluction, or (2) a clay-with-flint lined dissolution pipe — the lower contacts are sharp, which is a poor fit for a normal in-situ soil profile. Either way it is a local coombe-hosted feature a few tens of centimetres thick, sandwiched in structureless chalk Head, not an ice-laid diamicton and not a sheet across the Plain. The corridor long-section’s brown veneer is the same family of deposits (ploughsoil, colluvium, coombe/head), drawn schematically between ground level and rockhead — again Head/coombe, not till.</p>
  <figure class="xs" id="corridor-long-section">
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

  <h2>Terrain &amp; cover thickness</h2>
  <p>Ground-surface base is the <b>Environment Agency LiDAR Composite DTM 2022 1&nbsp;m</b> hillshade (downsampled for the web map; not rockhead). Cover-thickness circles use the small bottom-left key (metres; bold ring = measured rockhead). <b>Rockhead OD contours</b> are a light RBF surface over measured rockhead where logged and class-estimated rockhead elsewhere — schematic, not a surveyed isopach. Toggle layers top-right. Optional <b>BGS GeoIndex</b> overlay (grey pins, default off) links to public scans; rockhead is not yet transcribed from AGS/scans.</p>

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
    <li><a href="https://mapapps2.bgs.ac.uk/geoindex/home.html?layer=BGSBoreholes">BGS GeoIndex boreholes</a> (incl. SU14SW62) — map overlay “BGS GeoIndex” (grey pins → scan / AGS links where available; rockhead not yet transcribed from AGS/scans).</li>
    <li><a href="https://webapps.bgs.ac.uk/lexicon/lexicon.cfm?pub=COD">BGS Coombe deposits lexicon (COD)</a>;
        <a href="https://webapps.bgs.ac.uk/memoirs/docs/B06131.html">Salisbury Sheet 298 memoir brief</a>.</li>
    <li>Daw, T. 2026. <a href="https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html">Auditing the claim of Holocene flooding of Stonehenge Bottom</a>.</li>
    <li>Lee, J.R. &amp; Roberson, S. 2025. <a href="https://doi.org/10.1016/j.pgeola.2024.12.002"><i>Proc. Geol. Assoc.</i> 136, 101087</a> — limit of preserved glacial evidence; till vs head in boreholes.</li>
    <li>Clarke, A.P. &amp; Kirkland, C.L. 2026. <a href="https://www.nature.com/articles/s43247-025-03105-3"><i>Commun. Earth Environ.</i> s43247-025-03105-3</a>.</li>
    <li>Corpus noticed via <a href="https://www.buystonehenge.com/the-glacial-a303/">BuyStonehenge — The glacial A303</a> (desk search only; not a source of elevations).</li>
    <li>Environment Agency LiDAR Composite DTM 2022 1&nbsp;m hillshade; Open Government Licence. (OS Terrain&nbsp;50 was used briefly as an interim base before the EA 1&nbsp;m tiles.)</li>
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
    <li>EA LiDAR Composite DTM 2022 1&nbsp;m © Environment Agency / Open Government Licence.</li>
  </ul>
  <p>Original compilation, classification flags and code<br/>
  © Tim Daw 2026, licensed <a rel="license" href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a>.</p>
  <p>Underlying GI logs © National Highways / examination library. This is a research gazetteer, not a substitute for the published factual reports. Inclusion does not imply public access to land.</p>
</footer>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const HOLES = __HOLES_JSON__;
const COVER = __COVER_JSON__;
const BGS = __BGS_JSON__;
const ROCKHEAD = __ROCKHEAD_JSON__;
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
const N_BGS = __N_BGS__;
const EA1M_BOUNDS = __EA1M_BOUNDS__;

const map = L.map('map').setView([51.178, -1.84], 12);
const osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 18, attribution: '&copy; OpenStreetMap'
}).addTo(map);

const ea1m = L.imageOverlay('lidar/web/ea1m-hillshade.png', EA1M_BOUNDS, {
  opacity: 0.78,
  interactive: false,
  attribution: 'EA LiDAR Composite DTM 2022 1m © Environment Agency / OGL'
}).addTo(map);

if (!map.getPane('bgs')) {
  map.createPane('bgs');
  map.getPane('bgs').style.zIndex = 640;
}
if (!map.getPane('holes')) {
  map.createPane('holes');
  map.getPane('holes').style.zIndex = 650;
}
if (!map.getPane('cover')) {
  map.createPane('cover');
  map.getPane('cover').style.zIndex = 660;
}
if (!map.getPane('rockhead')) {
  map.createPane('rockhead');
  map.getPane('rockhead').style.zIndex = 655;
}
if (!map.getPane('landmarks')) {
  map.createPane('landmarks');
  map.getPane('landmarks').style.zIndex = 670;
}

function coverColour(m) {
  const v = Number(m);
  if (!(v >= 0)) return '#fee391';
  if (v < 1) return '#fff7bc';
  if (v < 2) return '#fec44f';
  if (v < 3) return '#fe9929';
  if (v < 4) return '#ec7014';
  return '#8c2d04';
}
function coverRadius(m) {
  const v = Math.max(0, Number(m) || 0);
  return 3.5 + Math.sqrt(v) * 3.2;
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

const coverLayer = L.layerGroup();
(COVER.features || COVER).forEach(f => {
  const p = f.properties || f;
  const coords = f.geometry ? f.geometry.coordinates : [f.lon, f.lat];
  const lon = coords[0], lat = coords[1];
  const measured = !!p.rockhead_measured;
  const cm = p.cover_m;
  const tip = `${p.id} · cover ${cm != null ? Number(cm).toFixed(2) + ' m' : '—'} · ${measured ? 'rockhead measured' : 'cover estimated'}`;
  L.circleMarker([lat, lon], {
    radius: coverRadius(cm),
    color: measured ? '#2a1808' : '#a67c52',
    weight: measured ? 2.8 : 1.2,
    fillColor: coverColour(cm),
    fillOpacity: 0.88,
    pane: 'cover'
  }).bindTooltip(tip).addTo(coverLayer);
});

coverLayer.addTo(map);

/* —— Rockhead OD contours (measured + estimated RBF) —— */
const rockheadLayer = L.layerGroup();
const rockheadLines = L.layerGroup().addTo(rockheadLayer);
const rockheadMeasured = L.layerGroup().addTo(rockheadLayer);
(ROCKHEAD.features || []).forEach(f => {
  const p = f.properties || {};
  const g = f.geometry;
  if (!g) return;
  if (g.type === 'LineString' || g.type === 'MultiLineString') {
    const latlngs = g.type === 'LineString'
      ? g.coordinates.map(c => [c[1], c[0]])
      : g.coordinates.map(ring => ring.map(c => [c[1], c[0]]));
    const od = Number(p.rockhead_m_od);
    const line = L.polyline(latlngs, {
      color: '#c4a35a',
      weight: 1.15,
      opacity: 0.72,
      pane: 'rockhead',
      interactive: false
    });
    line.addTo(rockheadLines);
    // label every 10 m OD on midpoint of longest segment
    if (Number.isFinite(od) && od % 10 === 0 && g.type === 'LineString' && g.coordinates.length > 2) {
      const mid = g.coordinates[Math.floor(g.coordinates.length / 2)];
      L.marker([mid[1], mid[0]], {
        pane: 'rockhead',
        interactive: false,
        icon: L.divIcon({
          className: '',
          html: `<span class="rh-label">${od}</span>`,
          iconSize: [28, 12],
          iconAnchor: [14, 6]
        })
      }).addTo(rockheadLines);
    }
  } else if (g.type === 'Point' && p.kind === 'measured_point') {
    L.circleMarker([g.coordinates[1], g.coordinates[0]], {
      radius: 5.5,
      color: '#2a1808',
      weight: 2.4,
      fillColor: '#f0e6c8',
      fillOpacity: 0.95,
      pane: 'rockhead'
    }).bindTooltip(p.label || (p.id + ' measured rockhead')).addTo(rockheadMeasured);
  }
});
rockheadLayer.addTo(map);

/* —— Context landmarks —— */
const LANDMARKS = [
  { name: 'Stonehenge', lat: 51.1789, lon: -1.8262 },
  { name: 'Winterbourne Stoke', lat: 51.1698, lon: -1.8885 },
  { name: 'Countess / E portal', lat: 51.1796, lon: -1.7795 },
  { name: 'Larkhill', lat: 51.1975, lon: -1.8055 }
];
const landmarksLayer = L.layerGroup();
LANDMARKS.forEach(lm => {
  const icon = L.divIcon({
    className: '',
    html: `<div class="landmark-label">${lm.name}</div>`,
    iconSize: [1, 1],
    iconAnchor: [0, 0]
  });
  L.marker([lm.lat, lm.lon], {
    icon,
    pane: 'landmarks',
    interactive: true,
    keyboard: false
  }).bindTooltip(lm.name, { permanent: false }).addTo(landmarksLayer);
});
landmarksLayer.addTo(map);

function bgsLinkHtml(label, url) {
  if (!url) return '';
  const parts = String(url).split(',').map(s => s.trim()).filter(Boolean);
  if (!parts.length) return '';
  return parts.map((u, i) => {
    const lab = parts.length > 1 ? `${label} ${i + 1}` : label;
    return `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(lab)}</a>`;
  }).join(' · ');
}

const bgsLayer = L.layerGroup();
(BGS.features || []).forEach(f => {
  const p = f.properties || {};
  const coords = f.geometry ? f.geometry.coordinates : null;
  if (!coords) return;
  const lon = coords[0], lat = coords[1];
  const title = (p.ref || 'BGS') + (p.name ? ' — ' + p.name : '');
  const lenStr = (p.len != null && p.len !== '') ? Number(p.len).toFixed(2) + ' m' : '—';
  const yearStr = p.year != null && p.year !== '' ? String(p.year) : '—';
  const tip = `${p.ref || 'BGS'}${p.year ? ' · ' + p.year : ''}${p.len != null ? ' · ' + Number(p.len).toFixed(1) + ' m' : ''}`;
  const links = [bgsLinkHtml('Scan', p.SCAN_URL), bgsLinkHtml('AGS log', p.AGS_LOG_URL)].filter(Boolean).join('<br/>');
  const html = `<strong>${esc(title)}</strong><br/>`
    + `OSGB ${esc(p.e)}E ${esc(p.n)}N<br/>`
    + `${Number(lat).toFixed(5)}, ${Number(lon).toFixed(5)}<br/>`
    + `Length ${esc(lenStr)} · Year ${esc(yearStr)}`
    + (links ? `<br/>${links}` : '');
  L.circleMarker([lat, lon], {
    radius: 3.5,
    color: '#555555',
    weight: 1,
    fillColor: '#888888',
    fillOpacity: 0.45,
    opacity: 0.7,
    pane: 'bgs'
  }).bindTooltip(tip).bindPopup(html).addTo(bgsLayer);
});

function isNarrow() {
  return (window.matchMedia && window.matchMedia('(max-width: 900px)').matches)
    || window.innerWidth <= 900;
}

const layersControl = L.control.layers(
  { 'OSM': osm },
  {
    'EA LiDAR 1m hillshade (2022)': ea1m,
    'Cover thickness': coverLayer,
    'Rockhead OD contours': rockheadLayer,
    'Landmarks': landmarksLayer,
    'BGS GeoIndex': bgsLayer
  },
  { collapsed: isNarrow(), position: 'topright' }
).addTo(map);

function syncLayersCollapsed() {
  layersControl.options.collapsed = isNarrow();
  if (isNarrow()) {
    if (typeof layersControl.collapse === 'function') layersControl.collapse();
  } else {
    if (typeof layersControl.expand === 'function') layersControl.expand();
  }
}
syncLayersCollapsed();

/* —— On-map orientation note (dismissible, sessionStorage) —— */
const READ_NOTE_KEY = 'a303_map_read_note_dismissed';
const ReadNote = L.Control.extend({
  options: { position: 'topright' },
  onAdd: function () {
    const wrap = L.DomUtil.create('div', 'map-read-note-wrap map-read-note');
    wrap.innerHTML = `
      <button type="button" class="dismiss" aria-label="Dismiss">&times;</button>
      <h4>Reading this map</h4>
      <p>Colours = sediment class; open rings = log uses “glacial”/till wording (almost always peri-glacial in the same report).</p>
      <p>Elevations are m OD. Plain holes ~70–117 m OD vs Holocene sea ~0 m OD — high Holocene water covering the Plain doesn’t fit.</p>
      <p>Cover-thickness = depth to rockhead (measured or estimated). Bold cover rings / pale contour ticks = measured rockhead.</p>`;
    L.DomEvent.disableClickPropagation(wrap);
    L.DomEvent.disableScrollPropagation(wrap);
    wrap.querySelector('.dismiss').addEventListener('click', () => {
      try { sessionStorage.setItem(READ_NOTE_KEY, '1'); } catch (e) {}
      map.removeControl(this);
    });
    return wrap;
  }
});
let readNoteControl = null;
if (!sessionStorage.getItem(READ_NOTE_KEY)) {
  readNoteControl = new ReadNote();
  readNoteControl.addTo(map);
}

function invalidateSoon() {
  requestAnimationFrame(() => {
    map.invalidateSize({ animate: false });
  });
  setTimeout(() => map.invalidateSize({ animate: false }), 200);
}
window.addEventListener('resize', () => {
  syncLayersCollapsed();
  invalidateSoon();
});
window.addEventListener('orientationchange', invalidateSoon);


const coverLegend = L.control({ position: 'bottomleft' });
coverLegend.onAdd = function () {
  const div = L.DomUtil.create('div', 'cover-legend');
  div.title = 'Cover thickness (m). Bold ring = measured rockhead; light = estimated.';
  div.innerHTML = `
    <div class="bar">
      <span class="sw"><i style="background:#fff7bc"></i><b>0</b></span>
      <span class="sw"><i style="background:#fec44f"></i><b>1</b></span>
      <span class="sw"><i style="background:#fe9929"></i><b>2</b></span>
      <span class="sw"><i style="background:#ec7014"></i><b>3</b></span>
      <span class="sw"><i style="background:#8c2d04"></i><b>4+</b></span>
      <span class="sep"></span>
      <span class="ring measured"><i></i><b>meas.</b></span>
      <span class="ring estimated"><i></i><b>est.</b></span>
    </div>
  `;
  L.DomEvent.disableClickPropagation(div);
  return div;
};
coverLegend.addTo(map);

map.on('overlayadd', (e) => {
  if (e.name === 'Cover thickness') coverLegend.addTo(map);
});
map.on('overlayremove', (e) => {
  if (e.name === 'Cover thickness') map.removeControl(coverLegend);
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
  const isR7 = /^R7-BH[1-6]$/i.test(h.id);
  const sectionLinks = `
    <div class="detail-actions">
      <a href="${stickFile}" target="_blank" rel="noopener">Open schematic stick</a>
      <a href="#corridor-long-section" data-scroll-fig="corridor-long-section">Corridor long-section</a>
      ${isR7 ? '<a href="#winterbourne-stoke-section" data-scroll-fig="winterbourne-stoke-section">Winterbourne Stoke section</a>' : ''}
    </div>`;
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
        ${sectionLinks}
        <p>${esc(h.notes || '')}</p>
      </div>
      <div class="stick-panel">
        <a class="stick-thumb" href="${stickFile}" title="Open schematic stick">
          <img class="expandable" src="${stickFile}" alt="Schematic stick for ${esc(h.id)}" loading="lazy"/>
        </a>
        <p class="stick-meta">Schematic OD stick — click to enlarge. Unit thicknesses are proportional unless Report&nbsp;7 printed intervals.</p>
      </div>
    </div>`;
  const fresh = document.querySelector('#detail img.expandable');
  if (fresh && window._bindStickLightbox) window._bindStickLightbox(fresh);
  document.querySelectorAll('#detail [data-scroll-fig]').forEach(a => {
    a.addEventListener('click', (ev) => {
      const fid = a.getAttribute('data-scroll-fig');
      const fig = document.getElementById(fid);
      if (!fig) return;
      ev.preventDefault();
      fig.scrollIntoView({ behavior: 'smooth', block: 'start' });
      fig.classList.add('flash-hi');
      setTimeout(() => fig.classList.remove('flash-hi'), 2200);
    });
  });
  if (isNarrow()) {
    const det = document.getElementById('detail');
    if (det) det.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

document.getElementById('q').addEventListener('input', renderList);

document.getElementById('stats').innerHTML = `
  <div class="stat"><b>${HOLES.length}</b> Highways / NSIP gazetteer</div>
  <div class="stat"><b>${N_BGS}</b> BGS GeoIndex (LiDAR box)</div>
  <div class="stat"><b>${GL_MIN.toFixed(2)}–${GL_MAX.toFixed(2)}</b> m OD ground level</div>
  <div class="stat"><b>${N_ROCK}</b> with rockhead</div>
  <div class="stat"><b>${N_FLAG}</b> glacial_wording flagged</div>
`;

document.getElementById('seaPanel').innerHTML =
  `<strong>Holocene sea ~0 m OD</strong>; corridor ground levels in this gazetteer from <strong>${GL_MIN.toFixed(2)} to ${GL_MAX.toFixed(2)} m OD</strong>. ` +
  `That gap falsifies high Holocene marine water over Stonehenge Bottom / the Plain — see ` +
  `<a href="https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html">the January 2026 flooding audit</a>.`;

renderList();
const MAIN_HOLES = HOLES.filter(h => !['TP-A','TP-B','TP-C'].includes(h.id));
// Fit to the EA LiDAR ribbon so the hillshade fills the default map (same OSGB crop as the holes).
map.fitBounds(EA1M_BOUNDS, { padding: [6, 6], maxZoom: 14 });
map.once('moveend', invalidateSoon);
invalidateSoon();
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

    cover_path = DATA / "cover-thickness.geojson"
    if cover_path.is_file():
        cover_fc = json.loads(cover_path.read_text(encoding="utf-8"))
    else:
        cover_fc = {"type": "FeatureCollection", "features": []}

    rockhead_path = DATA / "rockhead-contours.geojson"
    if rockhead_path.is_file():
        rockhead_fc = json.loads(rockhead_path.read_text(encoding="utf-8"))
    else:
        rockhead_fc = {"type": "FeatureCollection", "features": []}

    bgs_fc = load_bgs_fc()

    ea1m_bounds_path = OUT / "lidar" / "web" / "ea1m-bounds.json"
    if ea1m_bounds_path.is_file():
        ea1m_bounds = json.loads(ea1m_bounds_path.read_text(encoding="utf-8"))["wgs84_leaflet"]
    else:
        ea1m_bounds = [[51.16707, -1.90997], [51.18092, -1.73920]]

    html = (
        HTML.replace("__HOLES_JSON__", json.dumps(rows, ensure_ascii=False))
        .replace("__COVER_JSON__", json.dumps(cover_fc, ensure_ascii=False))
        .replace("__ROCKHEAD_JSON__", json.dumps(rockhead_fc, ensure_ascii=False))
        .replace("__BGS_JSON__", json.dumps(bgs_fc, ensure_ascii=False))
        .replace("__SOURCE_DOC_URLS__", json.dumps(SOURCE_DOC_URLS))
        .replace("__CLASS_ORDER__", json.dumps(CLASS_ORDER))
        .replace("__CLASS_LABEL__", json.dumps(CLASS_LABEL))
        .replace("__GL_MIN__", f"{gl_min:.2f}")
        .replace("__GL_MAX__", f"{gl_max:.2f}")
        .replace("__N_FLAG__", str(n_flag))
        .replace("__N_ROCK__", str(len(rhs)))
        .replace("__N_BGS__", str(len(bgs_fc.get("features", []))))
        .replace("__EA1M_BOUNDS__", json.dumps(ea1m_bounds))
    )
    # also fill the notes section placeholders that use the same tokens
    (OUT / "index.html").write_text(html, encoding="utf-8")

    print(f"holes: {len(rows)}")
    print(f"BGS GeoIndex: {len(bgs_fc.get('features', []))}")
    print(f"GL OD: {gl_min:.2f} .. {gl_max:.2f}")
    print(f"rockhead: {len(rhs)}; glacial_wording y: {n_flag}")
    print(f"wrote {DATA / 'boreholes.json'}")
    print(f"wrote {DATA / 'boreholes.geojson'}")
    print(f"wrote {OUT / 'index.html'}")
    print(f"rockhead contours features: {len(rockhead_fc.get('features', []))} ({rockhead_path.stat().st_size if rockhead_path.is_file() else 0} bytes)")
    print("by classification:", dict(Counter(r["classification"] for r in rows)))


if __name__ == "__main__":
    main()
