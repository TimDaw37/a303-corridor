# `boreholes.csv` schema

| Column | Meaning |
|---|---|
| `id` | Hole / trench label |
| `source_doc` | NSIP ID (`TR010025-…`) or `BGS` |
| `easting` / `northing` | OSGB36 metres (as printed) |
| `gl_m_od` | Ground level (m OD); blank if unknown |
| `rockhead_m_od` | Structural/weathered chalk top (m OD); blank if unknown — never invented |
| `top_units` | Short stack summary |
| `notes` | Caveats / wording |
| `glacial_wording` | `y` if this hole’s log uses ice-till / glacial-scour language |
| `classification` | `periglacial_coombe` \| `colluvium` \| `chalk` \| `alluvium` \| `made_ground` \| `solution` \| `ambiguous` |

Rebuild JSON / GeoJSON / HTML with `python3 ../generate.py`.
