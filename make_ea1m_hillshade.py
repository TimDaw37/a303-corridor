#!/usr/bin/env python3
"""Build corridor hillshade PNG from EA LIDAR Composite DTM 2022 1m GeoTIFFs.

Crop is computed from data/boreholes.json every run (not from terr50-bounds.json):
  main = holes excluding TP-A/B/C
  lark_n = max northing of TP-A/B/C
  mid_n = 0.5 * (min(main N) + max(main N))
  north_reach = lark_n - mid_n
  n1 = lark_n + 250
  n0 = mid_n - north_reach - 250
  e0/e1 = main easting span ± 1000 m
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rasterio.merge import merge

ROOT = Path("/workspace/a303-corridor")
EA1M = ROOT / "lidar" / "ea1m"
OUT = ROOT / "lidar" / "web"
OUT.mkdir(parents=True, exist_ok=True)

EXCLUDE_TP = {"TP-A", "TP-B", "TP-C"}

# Target web resolution (metres). Wider Larkhill crop → ~3 m keeps PNG manageable.
TARGET_CELL_M = 3.0


def compute_osgb_crop() -> tuple[float, float, float, float, dict]:
    rows = json.loads((ROOT / "data" / "boreholes.json").read_text())
    main = [r for r in rows if r.get("id") not in EXCLUDE_TP]
    tps = [r for r in rows if r.get("id") in EXCLUDE_TP]
    if not main:
        raise SystemExit("no main-corridor holes in boreholes.json")
    if not tps:
        raise SystemExit("TP-A/B/C missing from boreholes.json (needed for Larkhill north)")

    main_e = [float(r["easting"]) for r in main]
    main_n = [float(r["northing"]) for r in main]
    lark_n = max(float(r["northing"]) for r in tps)
    mid_n = 0.5 * (min(main_n) + max(main_n))
    north_reach = lark_n - mid_n
    n1 = lark_n + 250.0
    n0 = mid_n - north_reach - 250.0
    e0 = min(main_e) - 1000.0
    e1 = max(main_e) + 1000.0
    meta = {
        "lark_n": lark_n,
        "mid_n": mid_n,
        "north_reach": north_reach,
        "main_e_span": [min(main_e), max(main_e)],
        "main_n_span": [min(main_n), max(main_n)],
        "tp_ids": sorted({r["id"] for r in tps}),
    }
    print(
        f"OSGB crop from boreholes (Larkhill+symmetric south, ±1000 m E): "
        f"E {e0:.2f}–{e1:.2f}, N {n0:.2f}–{n1:.2f}"
    )
    print(
        f"  lark_n={lark_n:.2f} mid_n={mid_n:.2f} north_reach={north_reach:.2f} "
        f"width={e1 - e0:.0f} m height={n1 - n0:.0f} m"
    )
    return e0, e1, n0, n1, meta


def list_tiles() -> list[Path]:
    tiles = sorted(EA1M.glob("*_DTM_1m.tif"))
    if not tiles:
        raise SystemExit(f"no *_DTM_1m.tif under {EA1M}")
    return tiles


def mosaic_union_bounds(tiles: list[Path]) -> tuple[float, float, float, float]:
    lefts, bottoms, rights, tops = [], [], [], []
    for p in tiles:
        with rasterio.open(p) as ds:
            b = ds.bounds
            lefts.append(b.left)
            bottoms.append(b.bottom)
            rights.append(b.right)
            tops.append(b.top)
            print(f"  tile {p.name}: E {b.left:.0f}–{b.right:.0f} N {b.bottom:.0f}–{b.top:.0f}")
    return min(lefts), min(bottoms), max(rights), max(tops)


def apply_coverage_clamp(
    e0: float, e1: float, n0: float, n1: float, tiles: list[Path]
) -> tuple[float, float, float, float, dict]:
    ul, ub, ur, ut = mosaic_union_bounds(tiles)
    print(f"mosaic union: E {ul:.0f}–{ur:.0f} N {ub:.0f}–{ut:.0f}")
    short = {
        "west_m": max(0.0, ul - e0),
        "east_m": max(0.0, e1 - ur),
        "south_m": max(0.0, ub - n0),
        "north_m": max(0.0, n1 - ut),
    }
    clamped = False
    ce0, ce1, cn0, cn1 = e0, e1, n0, n1
    if short["west_m"] or short["east_m"] or short["south_m"] or short["north_m"]:
        print(
            "SHORTFALL vs mosaic union: "
            f"W {short['west_m']:.1f} m, E {short['east_m']:.1f} m, "
            f"S {short['south_m']:.1f} m, N {short['north_m']:.1f} m"
        )
        ce0, ce1 = max(e0, ul), min(e1, ur)
        cn0, cn1 = max(n0, ub), min(n1, ut)
        clamped = True
        print(
            f"CLAMPED crop to available coverage: E {ce0:.2f}–{ce1:.2f}, N {cn0:.2f}–{cn1:.2f}"
        )
    else:
        print("crop fully covered by mosaic union (no clamp)")
    info = {
        "mosaic_union": {"e0": ul, "e1": ur, "n0": ub, "n1": ut},
        "requested": {"e0": e0, "e1": e1, "n0": n0, "n1": n1},
        "shortfall_m": short,
        "clamped": clamped,
        "used": {"e0": ce0, "e1": ce1, "n0": cn0, "n1": cn1},
        "tiles": [p.name for p in tiles],
    }
    return ce0, ce1, cn0, cn1, info


def mosaic_crop(tiles: list[Path], e0, e1, n0, n1):
    srcs = [rasterio.open(p) for p in tiles]
    try:
        mosaic, transform = merge(
            srcs,
            bounds=(e0, n0, e1, n1),
            res=(TARGET_CELL_M, TARGET_CELL_M),
            nodata=np.nan,
            dtype="float32",
        )
    finally:
        for s in srcs:
            s.close()
    grid = mosaic[0].astype(np.float64)
    grid[~np.isfinite(grid)] = np.nan
    grid[grid < -1e20] = np.nan
    grid[grid > 1e4] = np.nan
    return grid, transform


def hillshade_rgba(grid: np.ndarray, cell: float):
    dy, dx = np.gradient(grid, cell, cell)
    azimuth = np.radians(315.0)
    altitude = np.radians(45.0)
    slope = np.pi / 2 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    shaded = (
        np.sin(altitude) * np.sin(slope)
        + np.cos(altitude) * np.cos(slope) * np.cos(azimuth - aspect)
    )
    shaded = np.clip(shaded, 0, 1)
    shaded[np.isnan(grid)] = np.nan

    z = grid.copy()
    zmin, zmax = np.nanpercentile(z, 2), np.nanpercentile(z, 98)
    zn = np.clip((z - zmin) / (zmax - zmin + 1e-9), 0, 1)
    cmap = plt.get_cmap("terrain")
    rgba = cmap(zn)
    for i in range(3):
        rgba[:, :, i] *= np.where(np.isnan(shaded), 1, 0.35 + 0.65 * shaded)
    rgba[np.isnan(grid)] = (0, 0, 0, 0)
    return rgba, float(np.nanmin(grid)), float(np.nanmax(grid))


def main() -> None:
    e0, e1, n0, n1, crop_meta = compute_osgb_crop()
    tiles = list_tiles()
    e0, e1, n0, n1, cov = apply_coverage_clamp(e0, e1, n0, n1, tiles)

    print("mosaicking / cropping / resampling to", TARGET_CELL_M, "m …")
    grid, transform = mosaic_crop(tiles, e0, e1, n0, n1)
    h, w = grid.shape
    print(f"grid shape {h}×{w}, nan fraction {np.isnan(grid).mean():.4f}")
    print(f"z range {np.nanmin(grid):.2f}–{np.nanmax(grid):.2f} m OD")

    rgba, zmin, zmax = hillshade_rgba(grid, TARGET_CELL_M)
    img = Image.fromarray((rgba * 255).astype(np.uint8), "RGBA")
    png = OUT / "ea1m-hillshade.png"
    img.save(png, optimize=True)
    size_mb = png.stat().st_size / (1024 * 1024)
    print(f"wrote {png} {img.size[0]}×{img.size[1]} ({size_mb:.2f} MB)")

    # Leaflet bounds use the (possibly clamped) OSGB crop box
    west, east, south, north = e0, e1, n0, n1
    t = Transformer.from_crs(27700, 4326, always_xy=True)
    lon0, lat0 = t.transform(west, south)
    lon1, lat1 = t.transform(east, north)
    tile_names = "+".join(p.stem.replace("_DTM_1m", "") for p in tiles)
    bounds = {
        "osgb": {"e0": west, "e1": east, "n0": south, "n1": north},
        "wgs84_leaflet": [[lat0, lon0], [lat1, lon1]],
        "source": (
            f"EA LIDAR Composite DTM 2022 1m ({tile_names}), Open Government Licence"
        ),
        "cellsize_m": TARGET_CELL_M,
        "z_range_m_od": [zmin, zmax],
        "png_pixels": [img.size[0], img.size[1]],
        "png_mb": round(size_mb, 3),
        "crop_meta": crop_meta,
        "coverage": cov,
        "affine_pixel_ul": {
            "a": transform.a,
            "e": transform.e,
            "c": transform.c,
            "f": transform.f,
        },
    }
    (OUT / "ea1m-bounds.json").write_text(json.dumps(bounds, indent=2) + "\n")
    print("FINAL OSGB crop:", bounds["osgb"])
    print("FINAL PNG:", f"{img.size[0]}x{img.size[1]}", f"{size_mb:.3f} MB")
    print("CLAMPED:", cov["clamped"], "shortfall_m:", cov["shortfall_m"])
    print("bounds written", OUT / "ea1m-bounds.json")


if __name__ == "__main__":
    main()
