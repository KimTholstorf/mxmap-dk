# Australia (AU)

## Overview
- ~537 Local Government Areas (LGAs) including shires, cities, towns, and regional councils
- Wikidata class: Q1867183 (local government area of Australia), with state-specific subclasses
- OSM admin_level: 6
- Domains: `.gov.au` (most common), `.com.au`, state-level `.nsw.gov.au`, `.qld.gov.au`, etc.

## Seed Data
- Source: Wikidata SPARQL via `scripts/fetch_wikidata.py AU`
- ~699 entries from Wikidata (includes unincorporated areas)
- ~523 with domains, ~544 with OSM relation IDs

## Domain Patterns
- Most councils use `councilname.nsw.gov.au`, `councilname.qld.gov.au` etc. (state-level gov.au subdomains)
- Some use `councilname.com.au` or bare `.au`
- Capital cities often use `cityofX.com.au` (e.g., `cityofadelaide.com.au`)
- Aboriginal shires may lack websites entirely

## Pipeline Config
- `SEED_FILES`: `"AU": "municipalities_au.json"`
- `tld_map`: `"AU": [".gov.au", ".com.au", ".au"]`
- Name suffixes stripped: `" shire council"`, `" shire"`, `" regional council"`, `" city council"`, `" council"`, `" district council"`

## Expected Providers
Predominantly US cloud: Microsoft 365, Google Workspace, with some local hosting.

## Notes
- 6 states + 2 territories, each with their own LGA structure
- Some very remote Aboriginal communities may have no web/email presence
- Wikidata P856 websites often point to council portals, email domains usually match
