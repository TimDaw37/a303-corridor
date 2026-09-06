#!/usr/bin/env python3
"""Fetch BGS GeoIndex onshore boreholes for the EA LiDAR rectangle.

Reads lidar/web/ea1m-bounds.json (OSGB + WGS84) and writes
data/bgs_boreholes_index.json in the slim schema used by generate.load_bgs_fc().

Preferred source: ArcGIS MapServer query (OSGB envelope, EPSG:27700).
Fallback: BGS OGC API Features with WGS84 bbox.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BOUNDS_PATH = ROOT / "lidar" / "web" / "ea1m-bounds.json"
OUT_PATH = ROOT / "data" / "bgs_boreholes_index.json"

ARCGIS_URL = (
    "https://map.bgs.ac.uk/arcgis/rest/services/"
    "GeoIndex_Onshore/boreholes/MapServer/0/query"
)
OGC_URL = "https://ogcapi.bgs.ac.uk/collections/onshoreboreholeindex/items"

PAGE = 1000
TOL_M = 1.0  # small tolerance around LiDAR OSGB box


def _get_json(url: str, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "a303-corridor-bgs-fetch/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _nullish(v):
    if v is None:
        return None
    if isinstance(v, str) and v.strip().lower() in ("not available", "n/a", "none", ""):
        return None
    return v


def _scan_url(attrs: dict, bgs_id) -> str | None:
    scan = _nullish(attrs.get("SCAN_URL") or attrs.get("scan_url") or attrs.get("scan"))
    if scan:
        return scan
    # Preserve canonical scan URL pattern when a scan is indicated elsewhere
    # (ArcGIS usually supplies SCAN_URL; leave None when not available.)
    return None


def _ags_url(attrs: dict) -> str | None:
    return _nullish(attrs.get("AGS_LOG_URL") or attrs.get("ags_log_url") or attrs.get("ags"))


def _len_val(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _year_val(v):
    if v is None or v == "":
        return None
    return str(v)


def load_bounds() -> tuple[dict, list]:
    bounds = json.loads(BOUNDS_PATH.read_text(encoding="utf-8"))
    osgb = bounds["osgb"]
    wgs = bounds["wgs84_leaflet"]
    return osgb, wgs


def inside_box(e: float, n: float, osgb: dict, tol: float = TOL_M) -> bool:
    return (
        osgb["e0"] - tol <= e <= osgb["e1"] + tol
        and osgb["n0"] - tol <= n <= osgb["n1"] + tol
    )


def map_arcgis_feature(feat: dict) -> dict | None:
    a = feat.get("attributes") or {}
    geom = feat.get("geometry") or {}
    e = a.get("EASTING")
    n = a.get("NORTHING")
    if e is None or n is None:
        e = geom.get("x")
        n = geom.get("y")
    if e is None or n is None:
        return None
    e, n = float(e), float(n)
    bgs_id = a.get("BGS_ID") or a.get("ID")
    if bgs_id is not None:
        try:
            bgs_id = int(bgs_id)
        except (TypeError, ValueError):
            pass
    scan = _scan_url(a, bgs_id)
    # If ArcGIS gives a non-null SCAN_URL that is already a full URL, keep it;
    # if we only have an id and the field was "Not Available", leave null.
    if scan is None and bgs_id is not None:
        # Do not invent scan URLs — only keep when SCAN_URL present.
        pass
    return {
        "ref": a.get("REFERENCE") or a.get("ref"),
        "name": a.get("NAME") or a.get("name"),
        "e": e,
        "n": n,
        "len": _len_val(a.get("LENGTH")),
        "year": _year_val(a.get("YEAR_KNOWN")),
        "bgs_id": bgs_id,
        "scan": scan,
        "ags": _ags_url(a),
    }


def fetch_arcgis(osgb: dict) -> list[dict]:
    xmin, ymin = osgb["e0"], osgb["n0"]
    xmax, ymax = osgb["e1"], osgb["n1"]
    out: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "geometry": f"{xmin},{ymin},{xmax},{ymax}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": "27700",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "27700",
            "f": "json",
            "resultRecordCount": str(PAGE),
            "resultOffset": str(offset),
            "orderByFields": "BGS_ID ASC",
        }
        url = ARCGIS_URL + "?" + urllib.parse.urlencode(params)
        print(f"ArcGIS query offset={offset} …", flush=True)
        data = _get_json(url)
        if data.get("error"):
            raise RuntimeError(f"ArcGIS error: {data['error']}")
        feats = data.get("features") or []
        if not feats:
            break
        for feat in feats:
            rec = map_arcgis_feature(feat)
            if rec is not None:
                out.append(rec)
        if not data.get("exceededTransferLimit"):
            break
        offset += len(feats)
        if len(feats) == 0:
            break
    return out


def map_ogc_feature(feat: dict) -> dict | None:
    props = feat.get("properties") or {}
    geom = feat.get("geometry") or {}
    # Prefer OSGB easting/northing from properties when present
    e = props.get("easting") or props.get("EASTING") or props.get("e")
    n = props.get("northing") or props.get("NORTHING") or props.get("n")
    if e is None or n is None:
        # OGC geometry is usually WGS84 lon/lat — skip if no OSGB coords
        # (we filter in OSGB; without e/n we cannot reliably keep schema)
        return None
    e, n = float(e), float(n)
    bgs_id = props.get("bgs_id") or props.get("BGS_ID") or props.get("id")
    if bgs_id is not None:
        try:
            bgs_id = int(bgs_id)
        except (TypeError, ValueError):
            pass
    scan = _nullish(props.get("scan_url") or props.get("SCAN_URL"))
    return {
        "ref": props.get("reference") or props.get("REFERENCE") or props.get("ref"),
        "name": props.get("name") or props.get("NAME"),
        "e": e,
        "n": n,
        "len": _len_val(props.get("length") or props.get("LENGTH")),
        "year": _year_val(props.get("year_known") or props.get("YEAR_KNOWN") or props.get("year")),
        "bgs_id": bgs_id,
        "scan": scan,
        "ags": _nullish(props.get("ags_log_url") or props.get("AGS_LOG_URL")),
    }


def fetch_ogc(wgs_leaflet: list) -> list[dict]:
    # leaflet [[lat,lon],[lat,lon]] -> bbox minLon,minLat,maxLon,maxLat
    (lat0, lon0), (lat1, lon1) = wgs_leaflet
    min_lon, max_lon = min(lon0, lon1), max(lon0, lon1)
    min_lat, max_lat = min(lat0, lat1), max(lat0, lat1)
    bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"
    url = f"{OGC_URL}?{urllib.parse.urlencode({'f': 'json', 'limit': PAGE, 'bbox': bbox})}"
    out: list[dict] = []
    while url:
        print(f"OGC API {url[:100]}…", flush=True)
        data = _get_json(url)
        for feat in data.get("features") or []:
            rec = map_ogc_feature(feat)
            if rec is not None:
                out.append(rec)
        next_url = None
        for link in data.get("links") or []:
            if link.get("rel") == "next" and link.get("href"):
                next_url = link["href"]
                break
        url = next_url
    return out


def dedupe(records: list[dict]) -> list[dict]:
    by_key: dict = {}
    for r in records:
        key = r.get("bgs_id")
        if key is None:
            key = ("ref", r.get("ref"), r.get("e"), r.get("n"))
        by_key[key] = r
    out = list(by_key.values())
    out.sort(key=lambda r: (r.get("ref") or "", r.get("bgs_id") or 0))
    return out


def main() -> int:
    if not BOUNDS_PATH.is_file():
        print(f"Missing bounds: {BOUNDS_PATH}", file=sys.stderr)
        return 1
    osgb, wgs = load_bounds()
    print(
        f"LiDAR OSGB box: E {osgb['e0']}–{osgb['e1']}, N {osgb['n0']}–{osgb['n1']}",
        flush=True,
    )

    old_count = 0
    if OUT_PATH.is_file():
        try:
            old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
            if isinstance(old, list):
                old_count = len(old)
            elif isinstance(old, dict):
                old_count = len(old.get("features") or [])
        except Exception:
            pass

    records: list[dict] = []
    source = "arcgis"
    try:
        records = fetch_arcgis(osgb)
        print(f"ArcGIS returned {len(records)} raw records", flush=True)
    except Exception as exc:
        print(f"ArcGIS failed ({exc}); trying OGC API…", file=sys.stderr)
        source = "ogc"
        try:
            records = fetch_ogc(wgs)
            print(f"OGC API returned {len(records)} raw records", flush=True)
        except Exception as exc2:
            print(f"OGC API also failed: {exc2}", file=sys.stderr)
            return 1

    filtered = [
        r
        for r in records
        if r.get("e") is not None
        and r.get("n") is not None
        and inside_box(float(r["e"]), float(r["n"]), osgb)
    ]
    # Round e/n slightly for stable JSON
    for r in filtered:
        r["e"] = round(float(r["e"]), 1)
        r["n"] = round(float(r["n"]), 1)
        if r.get("len") is not None:
            r["len"] = round(float(r["len"]), 2)

    final = dedupe(filtered)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")

    ns = [r["n"] for r in final]
    es = [r["e"] for r in final]
    n_scan = sum(1 for r in final if r.get("scan"))
    n_ags = sum(1 for r in final if r.get("ags"))
    north = [r for r in final if r["n"] > 142500]
    south = [r for r in final if r["n"] < 140800]
    added = max(0, len(final) - old_count)

    print("---")
    print(f"source: {source}")
    print(f"old_count: {old_count}")
    print(f"new_count: {len(final)}")
    print(f"added: {added}")
    if ns and es:
        print(f"N_range: {min(ns)}–{max(ns)}")
        print(f"E_range: {min(es)}–{max(es)}")
    print(f"with_scan: {n_scan}")
    print(f"with_ags: {n_ags}")
    print(f"north_strip_N>142500: {len(north)} sample_refs: {[r.get('ref') for r in north[:8]]}")
    print(f"south_strip_N<140800: {len(south)} sample_refs: {[r.get('ref') for r in south[:8]]}")
    print(f"wrote: {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
