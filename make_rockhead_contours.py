#!/usr/bin/env python3
"""Interpolate rockhead m OD (measured + estimated) and emit contour GeoJSON for the map."""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import RBFInterpolator

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
COVER = DATA / "cover-thickness.geojson"
HOLES = DATA / "boreholes.json"
OUT = DATA / "rockhead-contours.geojson"

# Contour every 5 m OD across the Plain range (~70–117)
LEVELS = list(range(70, 120, 5))


def load_points() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[dict]]:
    cover = json.loads(COVER.read_text(encoding="utf-8"))
    bh = {r["id"]: r for r in json.loads(HOLES.read_text(encoding="utf-8"))}
    xs, ys, zs, meta = [], [], [], []
    for f in cover["features"]:
        p = f["properties"]
        rid = p["id"]
        r = bh.get(rid)
        if not r or p.get("rockhead_m_od") is None:
            continue
        # Prefer OSGB for isotropic RBF; fall back to lon/lat metres approx
        e, n = float(r["easting"]), float(r["northing"])
        xs.append(e)
        ys.append(n)
        zs.append(float(p["rockhead_m_od"]))
        meta.append(
            {
                "id": rid,
                "measured": bool(p.get("rockhead_measured")),
                "lon": float(r["lon"]),
                "lat": float(r["lat"]),
                "rockhead_m_od": float(p["rockhead_m_od"]),
            }
        )
    return np.asarray(xs), np.asarray(ys), np.asarray(zs), meta


def osgb_to_wgs84_batch(e: np.ndarray, n: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    try:
        from pyproj import Transformer

        tf = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
        lon, lat = tf.transform(e, n)
        return np.asarray(lat), np.asarray(lon)
    except Exception:
        # coarse fallback — should not hit if pyproj present
        lon = (e - 400000) / 65000.0 - 2.0
        lat = (n + 100000) / 111000.0 + 49.0
        return lat, lon


def paths_to_features(cs, levels: list[float]) -> list[dict]:
    """Convert matplotlib ContourSet to GeoJSON LineString features (WGS84)."""
    features: list[dict] = []
    # matplotlib ContourSet: allsegs[i] = list of paths for levels[i]
    for i, level in enumerate(levels):
        segs = cs.allsegs[i] if i < len(cs.allsegs) else []
        for seg in segs:
            if seg is None or len(seg) < 2:
                continue
            e = seg[:, 0]
            n = seg[:, 1]
            lat, lon = osgb_to_wgs84_batch(e, n)
            coords = [[round(float(lo), 6), round(float(la), 6)] for lo, la in zip(lon, lat)]
            # drop near-duplicates
            cleaned = [coords[0]]
            for c in coords[1:]:
                if abs(c[0] - cleaned[-1][0]) > 1e-7 or abs(c[1] - cleaned[-1][1]) > 1e-7:
                    cleaned.append(c)
            if len(cleaned) < 2:
                continue
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "rockhead_m_od": float(level),
                        "label": f"{int(level)} m OD",
                    },
                    "geometry": {"type": "LineString", "coordinates": cleaned},
                }
            )
    return features


def main() -> None:
    xs, ys, zs, meta = load_points()
    print(f"points: {len(zs)} (measured {sum(1 for m in meta if m['measured'])})")
    print(f"rockhead OD range: {zs.min():.2f} .. {zs.max():.2f}")

    pad = 80.0
    e0, e1 = float(xs.min() - pad), float(xs.max() + pad)
    n0, n1 = float(ys.min() - pad), float(ys.max() + pad)
    # ~25 m grid — readable corridor contours without huge GeoJSON
    step = 25.0
    ge = np.arange(e0, e1 + step, step)
    gn = np.arange(n0, n1 + step, step)
    EE, NN = np.meshgrid(ge, gn)
    grid_pts = np.column_stack([EE.ravel(), NN.ravel()])

    # Thin-plate / linear RBF with mild smoothing for sparse + class-estimated mix
    rbf = RBFInterpolator(
        np.column_stack([xs, ys]),
        zs,
        kernel="thin_plate_spline",
        smoothing=25.0,
    )
    ZZ = rbf(grid_pts).reshape(EE.shape)

    # Mask cells far from any borehole (avoid wild extrapolation)
    # distance to nearest sample
    from scipy.spatial import cKDTree

    tree = cKDTree(np.column_stack([xs, ys]))
    dist, _ = tree.query(grid_pts, k=1)
    mask = dist.reshape(EE.shape) > 450.0  # m
    ZZ = np.ma.array(ZZ, mask=mask)

    fig, ax = plt.subplots(figsize=(1, 1))
    cs = ax.contour(EE, NN, ZZ, levels=LEVELS)
    features = paths_to_features(cs, LEVELS)
    plt.close(fig)

    # Also emit measured-point markers as Point features (for optional styling)
    for m in meta:
        if not m["measured"]:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "kind": "measured_point",
                    "id": m["id"],
                    "rockhead_m_od": m["rockhead_m_od"],
                    "label": f"{m['id']} {m['rockhead_m_od']:.1f} m OD",
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [round(m["lon"], 6), round(m["lat"], 6)],
                },
            }
        )

    fc = {
        "type": "FeatureCollection",
        "properties": {
            "description": "Rockhead m OD contours (RBF over measured+estimated cover rockhead)",
            "levels_m_od": LEVELS,
            "method": "scipy RBFInterpolator thin_plate_spline smoothing=25; contour every 5 m; mask >450 m from samples",
        },
        "features": features,
    }
    OUT.write_text(json.dumps(fc, ensure_ascii=False) + "\n", encoding="utf-8")
    size = OUT.stat().st_size
    n_lines = sum(1 for f in features if f["geometry"]["type"] == "LineString")
    n_pts = sum(1 for f in features if f["geometry"]["type"] == "Point")
    print(f"wrote {OUT} ({size} bytes; {n_lines} line features, {n_pts} measured points)")


if __name__ == "__main__":
    main()
