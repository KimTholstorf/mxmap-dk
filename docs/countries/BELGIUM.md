# Add Belgium to MX Map

You are extending the MX Map to include Belgium (565 municipalities).
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Overview

Belgium has **565 municipalities** (as of Jan 2025, after recent mergers). OSM admin_level=8. Complex trilingual structure: Dutch (Flanders), French (Wallonia), German (eastern cantons), bilingual Brussels. Comparable in scale to the Nordic-Baltic combined (~847).

Administrative hierarchy:
- 3 Regions: Flanders, Wallonia, Brussels-Capital
- 10 Provinces (+ Brussels)
- 43 Arrondissements
- **565 Municipalities** (gemeenten/communes)

## Phase 1: Seed data

Create `data/municipalities_be.json` with all 565 municipalities.

1. **Wikidata SPARQL**: Query `Q493522` (municipality of Belgium) with:
   - `P1567` — NIS/INS code (5-digit: province + district + municipality)
   - `P856` — official website
   - `P402` — OSM relation ID
2. **IDs**: Use `BE-` prefix + NIS code: `{"id": "BE-11001", "name": "Antwerpen", "country": "BE", ...}`
3. **Regions**: Use province name, or region (Flanders/Wallonia/Brussels).

**Domain pitfalls — BILINGUAL COMPLEXITY:**
- 12 municipalities have "linguistic facilities" (bilingual services)
- Brussels: 19 communes, all officially bilingual Dutch/French
- Some municipalities have different names: Mons (FR) = Bergen (NL), Liège (FR) = Luik (NL), Antwerpen (NL) = Anvers (FR)
- Domain typically uses the official language of the municipality:
  - Flemish: `antwerpen.be`, `gent.be`, `brugge.be`
  - Walloon: `namur.be`, `liege.be`, `charleroi.be`
  - Brussels: varies (`jette.irisnet.be`, `uccle.be`)
- Some use `stad[name].be` (Flemish) or `ville[name].be` (Walloon)
- `.brussels` and `.vlaanderen` TLDs exist but likely not used for email

**Extract domains from Wikidata P856 — do NOT guess.**

## Phase 2: Pipeline changes

### preprocess.py
- Add `"BE": "municipalities_be.json"` to `SEED_FILES`
- Add `"BE": [".be"]` to `tld_map`
- Belgian diacritics: mostly French (`é`, `è`, `ê`, `ë`) and Dutch — existing transliteration should cover most

### constants.py
- Add `"example.be"` to `SKIP_DOMAINS`

### tests
- Update expected countries/TLDs sets

## Phase 3: ISP discovery

1. Run `uv run preprocess`
2. Expect to find:
   - **V-ICT-OR** — Flemish municipal IT consortium (uses Microsoft Azure)
   - **Smals** — federal government IT provider
   - **Proximus** (AS5432) — dominant Belgian telecom
   - **Telenet** (AS6848) — major cable operator (Flanders)
   - **BICS/Belgacom** — related to Proximus
   - **Microsoft 365** — likely high share especially in Flanders via V-ICT-OR
3. Group independents by ASN, add to `LOCAL_ISP_ASNS`
4. Check for Belgian-specific gateway patterns

Expected distribution:
- **Microsoft**: High (60-80%) — especially Flanders via V-ICT-OR
- **Local Provider**: Moderate — Proximus, Telenet
- **Self-hosted**: Some, especially smaller Walloon communes

## Phase 4-5: Domain verification, postprocess, validate

With 565 entries, manual verification of all domains is not feasible. Focus on:
- All unknowns and independents
- Spot-check ~30 across all 3 regions
- Bilingual Brussels communes need special attention

## Phase 6: TopoJSON

- GitHub: `weRbelgium/BelgiumMaps.Admin` — municipality boundaries
- EU open data: official administrative limits
- Overpass API with `admin_level=8`
- Feature IDs must match seed data OSM relation IDs

## Phase 7: Frontend

- Add BE filter button, flag `🇧🇪`, country name "Belgium"
- Map center: Belgium is at ~50.8°N, 4.3°E — visible with current zoom
- Stats grid: will need layout adjustment for 9+ countries

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
