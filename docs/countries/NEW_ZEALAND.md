# New Zealand (NZ)

## Overview
- 67 territorial authorities (district and city councils + unitary authorities)
- Wikidata class: Q941036 (territorial authority of New Zealand)
- OSM admin_level: 7
- Domains: `.govt.nz` (most common), `.co.nz`, `.nz`

## Seed Data
- Source: Wikidata SPARQL via `scripts/fetch_wikidata.py NZ`
- 66 entries from Wikidata
- All 66 have domains, 0 OSM relation IDs (need manual/Overpass lookup)

## Domain Patterns
- Most councils use `councilname.govt.nz` (e.g., `ashburtondc.govt.nz`)
- Auckland Council is the largest: `aucklandcouncil.govt.nz`
- Some use abbreviations: `cdc.govt.nz` (Carterton District Council)
- Maori names used for some councils

## Pipeline Config
- `SEED_FILES`: `"NZ": "municipalities_nz.json"`
- `tld_map`: `"NZ": [".govt.nz", ".co.nz", ".nz"]`
- Name suffixes stripped: `" district council"`, `" city council"`, `" regional council"`, `" council"`

## Expected Providers
Predominantly US cloud: Microsoft 365, Google Workspace.

## Notes
- 11 regional councils + 56 territorial authorities (cities and districts)
- Small country, all councils have websites and email
- No OSM IDs from Wikidata — boundaries need separate Overpass fetch
