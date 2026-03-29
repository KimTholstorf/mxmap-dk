# Add Denmark to MX Map

You are extending the MX Map to include Denmark (98 municipalities/kommuner).
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Overview

Denmark has **98 kommuner** since the 2007 Strukturreform. This is the smallest country addition yet — comparable to Estonia (79) and Latvia (43). OSM admin_level=7 for kommuner.

Key context: Denmark mandated email encryption for sensitive data since Jan 2019. All 98 municipalities reportedly have Microsoft Entra ID tenants. Expect high Microsoft share but with many municipalities routing through local email security gateways (Comendo, Paratu/Permido).

## Phase 1: Seed data

Create `data/municipalities_dk.json` with all 98 kommuner.

1. **Wikidata SPARQL**: Query for `Q2177636` (municipality of Denmark) with:
   - `P1168` — kommunekode (3-digit code)
   - `P856` — official website
   - `P402` — OSM relation ID
   - Danish label for name

   ```sparql
   SELECT ?item ?name ?code ?website ?osmRelation WHERE {
     ?item wdt:P31 wd:Q2177636 .
     ?item rdfs:label ?name . FILTER(LANG(?name) = "da")
     OPTIONAL { ?item wdt:P1168 ?code }
     OPTIONAL { ?item wdt:P856 ?website }
     OPTIONAL { ?item wdt:P402 ?osmRelation }
   }
   ```

2. **IDs**: Use `DK-` prefix + kommunekode: `{"id": "DK-101", "name": "København", "country": "DK", "region": "Hovedstaden", "domain": "kk.dk", "osm_relation_id": 2192363}`
3. **Regions**: Use the 5 Danish regions (Hovedstaden, Midtjylland, Nordjylland, Syddanmark, Sjælland).

**Domain pitfalls:**
- Copenhagen uses **`kk.dk`** (Københavns Kommune), NOT `copenhagen.dk` or `koebenhavn.dk`
- Høje-Taastrup uses **`htk.dk`** (abbreviation)
- Some municipalities use abbreviations rather than full names
- Danish characters: `æ→ae`, `ø→oe`, `å→aa` in domains (e.g., Aabenraa not Åbenrå)
- No `.kommune.dk` pattern — all use plain `.dk` domains
- Wikidata P856 is essential — extract domains from websites, verify MX records

## Phase 2: Pipeline changes

### preprocess.py
- Add `"DK": "municipalities_dk.json"` to `SEED_FILES`
- Danish diacritics: `æ→ae`, `ø→oe`, `å→aa` are already covered by existing transliteration (`("æ", "ae")` exists, `("ø", "o")` exists but should also add `("å", "aa")` for Danish convention alongside `("å", "a")`)
- Add `"DK": [".dk"]` to `tld_map` in `guess_domains()`
- Add `" kommune"` to name suffixes to strip (if not already — check if " kommun" covers it or if " kommune" is needed separately)

### constants.py
- Add `"example.dk"` to `SKIP_DOMAINS`
- Do NOT add ISP ASNs yet — Phase 3

### tests
- Update `test_loads_all_countries` expected countries set to include `"DK"`
- Update `test_no_country_generates_all_tlds` expected TLDs to include `"dk"`
- Add Danish diacritics test (e.g., "Aabenraa" → "aabenraa", "Århus" → "aarhus")

Run tests: `uv run pytest`

## Phase 3: ISP discovery (iterative)

1. Run: `uv run preprocess`
2. Check "independent" count for DK entries
3. Group by ASN — expect to find:
   - **TDC/Nuuday** (AS3292, AS34482) — Denmark's largest telecom
   - **GlobalConnect** (AS42525)
   - **Telia Denmark** — part of Telia Group
   - **KMD** — municipal IT company (now NEC subsidiary)
   - **NNIT** — IT services
   - **Gigabit/Stofa** — regional ISPs
4. Add discovered ASNs to `LOCAL_ISP_ASNS`
5. Check gateway patterns — expect:
   - **Comendo** (`comendosystems.com`) — already in GATEWAY_KEYWORDS
   - **Paratu/Permido** (`paratu.dk`, `permido.dk`) — Danish email encryption vendor, add if found
   - Standard gateways (Barracuda, Cisco IronPort, etc.)
6. Re-run until independent count stabilizes

Expected distribution:
- **Microsoft**: Majority (70-85%) — all 98 have Entra ID tenants
- **Local Provider**: Some (10-20%) — TDC, KMD
- **Self-hosted**: Few (<10)
- **Google**: Very few
- Many municipalities likely route through gateways (Comendo, Paratu) to Microsoft backend — expect DKIM to reveal Microsoft behind local MX

## Phase 4: Domain verification

1. List remaining independent/unknown entries
2. Web-search each to verify domain
3. Spot-check ~15 municipalities — Copenhagen (kk.dk) is the key one
4. Fix seed data or add MANUAL_OVERRIDES

## Phase 5: Postprocess + validate

```bash
uv run postprocess
uv run validate
```

## Phase 6: TopoJSON boundaries

1. **Sources**:
   - GitHub: `magnuslarsen/geoJSON-Danish-municipalities` — GeoJSON with municipality names and LAU-1 codes
   - GitHub: `ok-dk/geodata` — TopoJSON of Danish municipalities
   - Overpass API with `admin_level=7` for Danish kommuner
2. Feature IDs must be `relation/XXXXX` matching seed data `osm_relation_id`
3. Merge into `baltic-municipalities.topo.json`:
   - Decode existing, combine with new, re-encode
   - **Preserve all existing features** (verify count before/after)
   - Preserve `name` and `name_en` properties

## Phase 7: Frontend

Edit `index.html`:
1. Add DK filter button: `<button class="country-btn active" data-country="DK">DK</button>`
2. Add to `FLAGS`: `'DK': '🇩🇰'`
3. Add `'DK'` to `activeCountries`
4. Add `'DK': 'Denmark'` to `countryNames`
5. Add `'DK'` to `countryColors` (for MX server location)
6. Add `'DK'` to the `mxLocal` country check
7. Add `'DK'` to `activeList`
8. Stats grid: 8 countries → keep 4-column grid (4×2 layout)
9. Update "What is this?" text to include Denmark

## Phase 8: Final verification

1. `python -m http.server 8000`, open browser
2. Verify DK municipalities colored, clickable, stats showing
3. Existing countries still correct
4. `uv run pytest`

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
- Delete or overwrite existing country data
