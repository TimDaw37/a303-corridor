# NOTES — glacial vs peri-glacial wording

Verbatim extracts live under the companion corpus
`glacial-a303/quotes/` (not copied into this public tree). This file is the
concordance for the map’s `glacial_wording` flags.

## Flagged holes in `boreholes.csv`

| id | Doc | Field wording | Classification used here | area / cluster |
|---|---|---|---|---|
| R4-T241 | TR010025-000582 | 24102 “Compact, saluted chalk, **glacial coombe** deposit” | `periglacial_coombe` — “saluted” = soliflucted typo elsewhere in Report 4 | `western_approach_interfluve`; `glacial_wording_cluster=western_r4` |
| R4-T247 | TR010025-000582 | “**Glacially affected** coombe chalk” | `periglacial_coombe` | same western_r4 cluster |
| R4-T248 | TR010025-000582 | “**Glacially affected** coombe chalk” | `periglacial_coombe` | same western_r4 cluster |
| R4-T263 | TR010025-000582 | 26307 “**glacial scouring** and solution hollows”; 26308 “scarring from **glaciation**” | `solution` — solution/peri-glacial hollows | same western_r4 cluster |
| R5-T511 | TR010025-000584 | 51132 “fluvial action on **glacial till**… possibly by **glacial activity** or water” | `periglacial_coombe` — same natural = soliflucted chalk (51131=51103); sample 51138 is 40 L of 51135, not a till assay | `eastern_portal_lower` (not in western cluster) |

## Report interpretive language (not ice)

- **Report 5** coombe definition: material “soliflucted downslope under
  **periglacial** conditions (alternate freeze-thawing), likely during the last
  glacial period.” → cold-stage climate, not an ice sheet on the Plain.
- **Report 4** also logs “soliflucted or heavily cryoturbated Chalk”, “frequent
  **periglacial** stripes”, “Periglacial striations orientated NW–SE”.
- **Report 7** (TR010025-000588): chalk rock overlain by Coombe from freeze/thaw,
  then Holocene colluvium. BH5/BH6 buried soil = Windermere **or** periglacial
  dissolution pipe.
- **Phase 7B** STP72602 rare quartzite: “POSSIBLE COLLUVIUM” — trace clast, not till.
- **BGS Sheet 298**: Quaternary = clay-with-flints, fluviatile sediments, and
  **periglacial head**; Head = solifluction; no till mapped on the chalk plain.

Quote files (paths relative to `glacial-a303/quotes/`):

- `01-TR010025-000584-Report5-Eastern-glacial-till-51132.txt`
- `01b-TR010025-000584-Report5-coombe-OSL-augers.txt`
- `02-TR010025-000582-Report4-Western-glacial-wording.txt`
- `03-TR010025-000588-Report7-BH5-BH6-Allerod-Windermere.txt`
- `04-TR010025-002259-Phase7B-rare-quartzite-OSL.txt`
- `05-BGS-Salisbury-298-head-coombe-no-till.txt`
- `06-Langdon-flooded-landscape-vs-A303-boreholes.txt`

## Holocene water / OD argument

- Holocene eustatic sea level ≈ **0 m OD**.
- Gazetteer GLs ≈ **71–118 m OD** (see `index.html` stats panel).
- Report 7 Winterbourne Stoke rockhead ≈ **71–76 m OD**.
- BGS **SU14SW62** (E 412924, N 141917): **GL 96.00 m OD**; no Holocene
  aquatic/marine deposits — Tim’s audit:
  https://www.sarsen.org/2026/01/auditing-claim-of-holocene-flooding-of.html

## Appendix — deep dive on the five `glacial_wording=y` holes (2026-09)

### Cluster conclusion

**Four of five** (R4-T241, T247, T248, T263) are a **single Report 4 / Western Portal
& Approach** cluster on Normanton Down high ground (~96.8–99.5 m OD), within
~300 m E–W. Report 4 §5.2 lists them together (with T214, T249, T250, T258…T274)
as the shallow coombe crossing where natural = soliflucted / cryoturbated chalk
with frequent periglacial stripes. Flag in notes:
`glacial_wording_cluster=western_r4`; CSV `area=western_approach_interfluve`.

**R5-T511** is a separate Eastern Portal (Countess West) trench at **73.2 m OD**
(~4.4 km east) — `area=eastern_portal_lower`. Not the same diggers’ day and not
the same landform.

The Western Portal site is **not** the Winterbourne Stoke coombe floor (that is
Report 7, rockhead ~71–76 m OD). Report 4 places Winterbourne Stoke Crossroads
barrow cemetery NW of the site at Longbarrow; the evaluation area itself is
Normanton Down / western tunnel portal and approach (~100 m aOD at the portal
head).

### Authorship

| Report | Title (April 2019) | Corporate | PDF Author metadata | Named field loggers in Part 1 tables |
|---|---|---|---|---|
| 4 / 000582 | Western Portal and Approach — Part 1: Text | Wessex Archaeology Ltd for AmW (AECOM–Mace–WSP) / Highways England | Same PDF-metadata author as Report 5 (name omitted) | None printed (no “recorded by” / initials in Appendix A) |
| 5 / 000584 | Eastern Portal — Part 1: Text | Same corporate line | Same PDF-metadata author as Report 4 (name omitted) | None printed |

HE refs: Report 4 `HE551506-AMW-HER-Z2_ML_M00_Z-RP-LH-0001`; Report 5
`HE551506-AMW-HER-Z4-GN_000_Z-RP-LH-0001`.

### Verbatim contexts (Appendix A)

**24102 Natural** — “Compact, saluted chalk, glacial coombe deposit. Surface
disturbed by plough and root activity.” (T241 GL 99.48 OD)

**24703 Natural** — “Glacially affected coombe chalk. Very rare, subangular flint
nodules, poorly sorted.” (over 24702 possible colluvium; GL 98.99 OD)

**24803 Natural** — “Glacially affected coombe chalk. Rare subangular flint
nodules, poorly sorted.” (GL 98.72 OD)

**Neighbouring solifluction labels (same appendix / coombe group):** 24602
“Soliflucted chalk with periglacial stripes”; 24903 “Soliflucted chalk…”

**26307 Geological feature** — “Irregular in plan… Probably derived from a
combination of glacial scouring and solution hollows. L 2.44m, W 1.57m, D 0.47m.”

**26308 Geological feature** — “Disruption in natural. Probable scarring from
glaciation. Irregular steep-moderate sides.” (T263 GL 96.82 OD; also 26303
chalk-gravel striations N–S)

**51131 Natural** — “Soliflucted chalk. Same as (51103)”

**51132 Natural** — “Same as (51103). This deposit is seen within machine trench
in various places, and has been laid down by fluvial action on glacial till within
scraped out limestone, possibly by glacial activity or water movement. Light brown
silt.” (T511 GL 73.2 m OD)

**51135 / 51138** — 51135 “Same as (51103). Light green sand and degraded chalk.”
51138 “40L sample of (51135)” → Appendix C charred-plant flot, not till assay.

### Elevations contrast

| Setting | Typical GL / rockhead |
|---|---|
| Western_r4 cluster (T241–T263) | GL **96.82–99.48 m OD** (interfluve / coombe head) |
| R5-T511 eastern portal | GL **73.2 m OD** |
| Report 7 Winterbourne Stoke coombe rockhead (BH1–BH6) | **~71–76 m OD** |
| Holocene eustatic sea | **~0 m OD** |

### Public HTML

`generate.py` writes the section **“Field ‘glacial’ wording: why it does not mean
ice”** into `index.html` (quotes, cluster, coombe definitions, till tests, high-ground
Head argument, T511 special case), with live PINS PDF links and BGS COD.

## Out of scope

- Lab / FOI chase on sample **51138** (field wording ≠ dated till).
- Bluestone-by-ice advocacy beyond what corridor logs support.
- Invented coordinates or elevations.

## Id note

- Gazetteer hole formerly labelled `R4-T597` is Report 4 **Trench 258** (NGR 410597 141482, 97.49 m OD); id corrected to `R4-T258`.
