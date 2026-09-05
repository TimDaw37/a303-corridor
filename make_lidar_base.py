#!/usr/bin/env python3
"""Build corridor hillshade PNG from OS Terrain 50 ASC + cover-thickness GeoJSON."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path('/workspace/a303-corridor')
LIDAR = ROOT / 'lidar'
OUT = LIDAR / 'web'
OUT.mkdir(parents=True, exist_ok=True)

# Corridor crop in OSGB: main borehole ribbon (exclude TP-A/B/C outliers), ~250 m pad
EXCLUDE_IDS = {'TP-A', 'TP-B', 'TP-C'}
PAD_M = 250.0


def corridor_crop_osgb():
    rows = json.loads((ROOT / 'data' / 'boreholes.json').read_text())
    main = [r for r in rows if r.get('id') not in EXCLUDE_IDS]
    if not main:
        raise SystemExit('no main-corridor boreholes for crop')
    es = [float(r['easting']) for r in main]
    ns = [float(r['northing']) for r in main]
    e0, e1 = min(es) - PAD_M, max(es) + PAD_M
    n0, n1 = min(ns) - PAD_M, max(ns) + PAD_M
    print(
        f'OSGB crop (excl {sorted(EXCLUDE_IDS)}, pad {PAD_M:g} m): '
        f'E {e0:.2f}–{e1:.2f}, N {n0:.2f}–{n1:.2f} '
        f'({len(main)} holes; raw E {min(es):.2f}–{max(es):.2f}, N {min(ns):.2f}–{max(ns):.2f})'
    )
    return e0, e1, n0, n1


E0, E1, N0, N1 = corridor_crop_osgb()

DEFAULT = {
    'chalk': 0.6, 'made_ground': 1.5, 'colluvium': 2.0,
    'periglacial_coombe': 2.5, 'solution': 3.5, 'ambiguous': 1.5,
}


def read_asc(path: Path):
    meta = {}
    with path.open() as f:
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                break
            parts = line.split()
            if not parts:
                continue
            # Header key/value until first numeric data line
            if len(parts) >= 2 and not parts[0].lstrip('-').replace('.', '', 1).isdigit():
                k, v = parts[0], parts[1]
                meta[k.lower()] = float(v) if '.' in v or 'e' in v.lower() else int(float(v))
                continue
            f.seek(pos)
            break
        data = np.loadtxt(f)
    return meta, data


def osgb_to_wgs84(e, n):
    """Approximate OSGB36→WGS84 (same Helmert as generate.py)."""
    # Use pyproj if available else helmert
    try:
        from pyproj import Transformer
        t = Transformer.from_crs(27700, 4326, always_xy=True)
        lon, lat = t.transform(e, n)
        return lat, lon
    except Exception:
        # Airy Helmert approx
        a, b = 6377563.396, 6356256.909
        F0 = 0.9996012717
        lat0, lon0 = np.radians(49), np.radians(-2)
        N0r, E0r = -100000.0, 400000.0
        e2 = 1 - (b * b) / (a * a)
        n_ = (a - b) / (a + b)
        lat, M = lat0, 0.0
        for _ in range(10):
            lat = ((n - N0r) / (a * F0) + lat0)
            # simplified iteration
            break
        # fallback: use approximate conversion good enough for overlay bounds
        # (Will install pyproj if needed)
        raise


def mosaic_and_hillshade():
    tiles = []
    for name in ('SU04.asc', 'SU14.asc'):
        meta, data = read_asc(LIDAR / 'terr50' / name)
        tiles.append((meta, data))
        print(name, meta, data.shape, 'z', np.nanmin(data), np.nanmax(data))

    # Both should be 50m cell, 10km tiles. SU04: E400000 N140000; SU14: E410000 N140000
    cell = tiles[0][0]['cellsize']
    # Build mosaic array covering E0-E1, N0-N1
    width = int(round((E1 - E0) / cell))
    height = int(round((N1 - N0) / cell))
    grid = np.full((height, width), np.nan, dtype=np.float64)

    for meta, data in tiles:
        nodata = meta.get('nodata_value', -9999)
        data = data.astype(np.float64)
        data[data == nodata] = np.nan
        xll, yll = meta['xllcorner'], meta['yllcorner']
        nrows, ncols = int(meta['nrows']), int(meta['ncols'])
        for r in range(nrows):
            n = yll + (nrows - r - 1) * cell + cell / 2
            if n < N0 or n > N1:
                continue
            gr = int((N1 - n) / cell)
            if gr < 0 or gr >= height:
                continue
            for c in range(ncols):
                e = xll + c * cell + cell / 2
                if e < E0 or e > E1:
                    continue
                gc = int((e - E0) / cell)
                if 0 <= gc < width:
                    grid[gr, gc] = data[r, c]

    # Fill tiny holes by nanmean neighbour
    mask = np.isnan(grid)
    print('nan fraction', mask.mean(), 'shape', grid.shape)

    # Hillshade
    dy, dx = np.gradient(grid, cell, cell)
    # illuminate from NW
    azimuth = np.radians(315)
    altitude = np.radians(45)
    slope = np.pi / 2 - np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)
    shaded = (
        np.sin(altitude) * np.sin(slope)
        + np.cos(altitude) * np.cos(slope) * np.cos(azimuth - aspect)
    )
    shaded = np.clip(shaded, 0, 1)
    shaded[np.isnan(grid)] = np.nan

    # Elevation colour wash + hillshade multiply
    z = grid.copy()
    zmin, zmax = np.nanpercentile(z, 2), np.nanpercentile(z, 98)
    zn = (z - zmin) / (zmax - zmin + 1e-9)
    zn = np.clip(zn, 0, 1)
    cmap = plt.get_cmap('terrain')
    rgba = cmap(zn)
    # multiply RGB by hillshade
    for i in range(3):
        rgba[:, :, i] *= np.where(np.isnan(shaded), 1, 0.35 + 0.65 * shaded)
    rgba[np.isnan(grid)] = (0, 0, 0, 0)

    # Upsample for smoother web display
    img = Image.fromarray((rgba * 255).astype(np.uint8), 'RGBA')
    img = img.resize((width * 8, height * 8), Image.Resampling.BILINEAR)
    png = OUT / 'terr50-hillshade.png'
    img.save(png)
    print('wrote', png, img.size)

    # Bounds in WGS84 for Leaflet imageOverlay [[south,west],[north,east]]
    try:
        from pyproj import Transformer
    except ImportError:
        import subprocess
        subprocess.check_call(['/workspace/.venv/bin/pip', 'install', 'pyproj', '-q'])
        from pyproj import Transformer
    t = Transformer.from_crs(27700, 4326, always_xy=True)
    lon0, lat0 = t.transform(E0, N0)
    lon1, lat1 = t.transform(E1, N1)
    bounds = {
        'osgb': {'e0': E0, 'e1': E1, 'n0': N0, 'n1': N1},
        'wgs84_leaflet': [[lat0, lon0], [lat1, lon1]],  # SW, NE
        'source': 'OS Terrain 50 (OpenData) SU04+SU14 — interim base until EA 1m DTM tiles land',
        'cellsize_m': cell,
        'z_range_m_od': [float(np.nanmin(grid)), float(np.nanmax(grid))],
    }
    (OUT / 'terr50-bounds.json').write_text(json.dumps(bounds, indent=2))
    print('bounds', bounds)
    return bounds


def cover_geojson():
    rows = json.loads((ROOT / 'data' / 'boreholes.json').read_text())
    feats = []
    for r in rows:
        if r.get('rockhead_m_od') is not None:
            cover = float(r['gl_m_od']) - float(r['rockhead_m_od'])
            measured = True
        else:
            cover = DEFAULT.get(r['classification'], 1.5)
            measured = False
        rh = float(r['gl_m_od']) - cover
        feats.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [r['lon'], r['lat']]},
            'properties': {
                'id': r['id'],
                'cover_m': round(cover, 2),
                'gl_m_od': r['gl_m_od'],
                'rockhead_m_od': round(rh, 2),
                'rockhead_measured': measured,
                'classification': r['classification'],
            },
        })
    gj = {'type': 'FeatureCollection', 'features': feats}
    path = ROOT / 'data' / 'cover-thickness.geojson'
    path.write_text(json.dumps(gj))
    print('wrote', path, 'n', len(feats))
    return path


if __name__ == '__main__':
    mosaic_and_hillshade()
    cover_geojson()
