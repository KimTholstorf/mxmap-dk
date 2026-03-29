# Add Andorra to MX Map

You are extending the MX Map to include Andorra (7 parishes/parròquies).
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Overview

Andorra is a microstate in the Pyrenees with **7 parishes** — the smallest country addition. OSM admin_level=7. Trivial to implement but interesting as a data sovereignty edge case (non-EU, non-EEA, but GDPR-adjacent).

## Phase 1: Seed data

Create `data/municipalities_ad.json` with all 7 parishes. This can be done manually:

| ISO 3166-2 | Name | Notes |
|---|---|---|
| AD-02 | Canillo | |
| AD-03 | Encamp | |
| AD-04 | La Massana | |
| AD-05 | Ordino | |
| AD-06 | Sant Julià de Lòria | |
| AD-07 | Andorra la Vella | Capital |
| AD-08 | Escaldes-Engordany | |

1. **Wikidata**: Query `Q24279` (parish of Andorra) for P856 (website), P402 (OSM relation).
2. **Domains**: `.ad` TLD. Registration requires an Andorran trademark. Look for `comu[name].ad` or `[name].ad` patterns. With only 7 entries, manually web-search each.
3. **IDs**: Use ISO 3166-2 codes: `AD-02` through `AD-08`.
4. Format: `{"id": "AD-07", "name": "Andorra la Vella", "country": "AD", "region": "Andorra", "domain": "andorralavella.ad", "osm_relation_id": XXXXX}`

## Phase 2: Pipeline changes

### preprocess.py
- Add `"AD": "municipalities_ad.json"` to `SEED_FILES`
- Add `"AD": [".ad"]` to `tld_map`
- Catalan diacritics: `à→a`, `è→e`, `í→i`, `ò→o`, `ú→u` — most already covered by existing transliteration

### constants.py
- Add `"example.ad"` to `SKIP_DOMAINS`
- No ISP ASNs needed initially — only 7 entries

### tests
- Update expected countries/TLDs sets

## Phase 3: ISP discovery

With only 7 entries, manually check each:
- **Andorra Telecom** is the sole telecom operator — likely hosts most email
- Some parishes may use Microsoft 365
- `dig +short domain MX` for each

## Phase 4-5: Postprocess + validate

Standard pipeline run.

## Phase 6: TopoJSON

- Overpass API with `admin_level=7` in Andorra, or manually draw 7 polygons
- Tiny addition (~10 KB to TopoJSON)

## Phase 7: Frontend

- Add AD filter button, flag `🇦🇩`, country name "Andorra"
- Map center may need adjustment to show Pyrenees (current center at [57,15] zoom 4 may not show Andorra — it's at ~42.5°N, 1.5°E)
- Consider zooming out to zoom 3 or shifting center south

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
