# Add Luxembourg to MX Map

You are extending the MX Map to include Luxembourg (100 communes).
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Overview

Luxembourg has **100 communes** — very manageable, similar to Denmark (98). OSM admin_level=8. Trilingual country (Luxembourgish, French, German) but domains use a single form.

## Phase 1: Seed data

Create `data/municipalities_lu.json` with all 100 communes.

1. **Wikidata SPARQL**: Query `Q2919801` (municipality of Luxembourg) with P856 (website), P402 (OSM relation), P300 (ISO 3166-2 code).
2. **LAU codes**: Available from EU open data portal. Use `LU-` prefix + LAU code for IDs.
3. **Domains**: `.lu` TLD. No standardized pattern — domains vary:
   - `vdl.lu` (Ville de Luxembourg — capital)
   - `name.lu` (e.g., `differdange.lu`, `mamer.lu`)
   - Some may use `commune-name.lu` or abbreviations
4. Extract domains from Wikidata P856, verify MX records.
5. **Regions**: Use cantons (12) for the region field, or leave as "Luxembourg" since the country is small.

**Domain pitfalls:**
- Luxembourg City uses `vdl.lu` (Ville de Luxembourg), not `luxembourg.lu`
- Trilingual names — some communes have different names in Luxembourgish/French/German
- Small country so manual verification of all 100 is feasible

## Phase 2: Pipeline changes

### preprocess.py
- Add `"LU": "municipalities_lu.json"` to `SEED_FILES`
- Add `"LU": [".lu"]` to `tld_map`
- No special diacritics beyond existing French/German support

### constants.py
- Add `"example.lu"` to `SKIP_DOMAINS`

### tests
- Update expected countries/TLDs sets

## Phase 3: ISP discovery

1. Run `uv run preprocess`
2. Expect to find:
   - **POST Luxembourg** (formerly P&T) — dominant telecom, offers hosting/email
   - **Microsoft 365** — likely significant share
   - **SIX/LuxConnect** — Luxembourg data center operator
3. Add discovered ASNs to `LOCAL_ISP_ASNS`

## Phase 4-5: Domain verification, postprocess, validate

Standard flow. With 100 entries, full manual domain verification is feasible.

## Phase 6: TopoJSON

- GitHub: `dtonhofer/MunicipalitiesOfLuxembourg` — GeoJSON based on OSM
- Alternatively: Overpass API with `admin_level=8`
- Small addition (~50 KB to TopoJSON)

## Phase 7: Frontend

- Add LU filter button, flag `🇱🇺`, country name "Luxembourg"
- Map center: Luxembourg is at ~49.6°N, 6.1°E — visible with current zoom but near edge. May need slight center adjustment.

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
