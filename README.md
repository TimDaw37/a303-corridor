# A boring story: A303 Stonehenge corridor boreholes

Geolocated gazetteer of boreholes, trial pits and evaluation trenches along the
**A303 Amesbury–Berwick Down** scheme (National Highways / NSIP). Built for
GitHub Pages as a static Leaflet map.

**Author:** Tim Daw / working 2026. **Licence:** [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).

## What this is

1. A **superficial stack** gazetteer: OSGB36 E/N, ground level (m OD), rockhead
   (m OD) where the log states it, and a short unit summary
   (chalk / coombe-head / colluvium / alluvium / made ground / solution).
2. An elevation argument against **high Holocene water** covering Stonehenge
   Bottom / the Plain: Holocene sea ≈ **0 m OD**; corridor GLs in this set run
   from about **71–118 m OD**. Same logic as
   [the January 2026 flooding audit](https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html).
3. A reclassification of field **“glacial”** wording as **peri-glacial** where
   the reports themselves do.
   BuyStonehenge is mentioned only as how the public NSIP corpus was noticed.

Heavy PDFs and verbatim quote extracts stay in the companion research folder
`/workspace/glacial-a303/` (or your local copy of that corpus). This public tree
cites **TR010025** document IDs only.

## Open locally

```bash
cd a303-corridor
python3 -m http.server 8000
# then open http://localhost:8000/
```

Or open `index.html` directly in a browser (Leaflet loads from unpkg CDN).

## Rebuild from CSV

```bash
python3 generate.py
```

Reads `data/boreholes.csv` and writes:

- `data/boreholes.json`
- `data/boreholes.geojson`
- `index.html` (Palatino dark theme, map + list first)

Coordinate transform reuses the `osgb_to_wgs84` helper from the Devon sarsens
map (pyproj if installed; otherwise Airy 1830 + Helmert fallback).

## GitHub Pages

No secrets are in this tree. From a clean clone:

```bash
cd a303-corridor
git init
git add .
git commit -m "A303 corridor geoarchaeology gazetteer"
# push to timdaw37.github.io (root or /a303-corridor/) or a new repo with Pages enabled
```

Do **not** commit the `glacial-a303` PDF corpus into this repo.

## Data sources (NSIP IDs)

| ID | Role |
|---|---|
| TR010025-000588 | Report 7 ERT + BH1–BH6 (Winterbourne Stoke; rockhead) |
| TR010025-002259 | Phase 7B factual (STP / TP with E/N/GL) |
| TR010025-002269 | Phase 7a(i) factual (CP/R holes with E/N/GL) |
| TR010025-000582 | Report 4 Western Portal trenches |
| TR010025-000584 | Report 5 Eastern Portal trenches (incl. 511 “glacial till” wording) |
| BGS SU14SW62 | Stonehenge Bottom @ 96.00 m OD (Tim’s audit) |

Elevations are **never invented** — blank means not yet verified from a printed log.

## Files

| Path | Purpose |
|---|---|
| `index.html` | Map + clickable list + explanation |
| `data/boreholes.csv` | Source table |
| `data/boreholes.json` | Enriched records (WGS84) |
| `data/boreholes.geojson` | QGIS / GIS export |
| `generate.py` | Rebuild script |
| `NOTES.md` | Glacial vs peri-glacial quote concordance |

## Related research corpus

Local: `../glacial-a303/` (PDFs, `quotes/`, `PROJECT.md`, `RESEARCH-NOTE.md`).
