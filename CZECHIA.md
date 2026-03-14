# Add Czechia to MX Map

You are extending the MX Map to include Czechia at ORP level (205 municipalities with extended powers).
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Scale decision: ORP level

Czechia has **6,258 obce** (municipalities) — too many for initial mapping. Many are tiny villages (~200 people) that share IT infrastructure. Instead, map at **ORP level (205 municipalities with extended powers)** — these are the municipalities that provide state administration services to surrounding villages and have their own IT infrastructure.

Administrative hierarchy:
- 14 Kraje (regions)
- 77 Okresy (districts)
- **205 ORP** (obce s rozšířenou působností / municipalities with extended powers)
- ~6,258 Obce (municipalities) — future expansion

OSM admin_level: Kraje=6, Okresy=7, ORP=not directly mapped (use boundaries from CSÚ), Obce=8.

## Phase 1: Seed data

Create `data/municipalities_cz.json` with all 205 ORP municipalities.

1. **Data source**: Czech Statistical Office (CSÚ) publishes the ORP list with codes.
2. **Wikidata**: Query for `Q7819319` (municipality with extended powers in Czechia) or filter from `Q5153359` (municipality of Czech Republic).
   - Properties: P856 (website), P402 (OSM relation)
   - LAU-2 codes for identification
3. **Centralized portal**: `mesta.obce.cz` — lists all Czech municipalities with their websites.
4. **IDs**: Use `CZ-` prefix + LAU code or CSÚ ORP code.
5. **Regions**: Use Kraj name.

**Domain pitfalls:**
- `.cz` TLD — no standardized government domain suffix (unlike Austria's `.gv.at`)
- Patterns vary: `name.cz`, `mesto-name.cz`, `meu-name.cz` (městský úřad = city office)
- Czech diacritics in names: háčky (č, š, ž, ř, ď, ť, ň) and čárky (á, é, í, ó, ú, ý) — domains drop all diacritics
- **Praha (Prague)** uses `praha.eu` for some services
- Compound names may use hyphens or be concatenated
- `mesta.obce.cz` portal is the best source for domain discovery

## Phase 2: Pipeline changes

### preprocess.py
- Add `"CZ": "municipalities_cz.json"` to `SEED_FILES`
- Add `"CZ": [".cz"]` to `tld_map`
- Czech diacritics: `("č", "c"), ("š", "s"), ("ž", "z"), ("ř", "r"), ("ď", "d"), ("ť", "t"), ("ň", "n")` — háčky are mostly covered by existing shared translits, add `("ř", "r")` if missing
- Long vowels: `("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"), ("ý", "y")` — mostly covered
- Add name suffixes to strip: none specific (ORP names are city names)

### constants.py
- Add `"example.cz"` to `SKIP_DOMAINS`

### tests
- Update expected countries/TLDs sets
- Add Czech diacritics test (e.g., "Ústí nad Labem" → "usti-nad-labem")

## Phase 3: ISP discovery

1. Run `uv run preprocess`
2. Expect to find:
   - **O2 Czech Republic** (AS5610) — major telecom (formerly Telefónica CZ)
   - **T-Mobile CZ** (AS13036)
   - **CETIN** (AS28725) — Czech telecom infrastructure
   - **CESNET** (AS2852) — Czech research/education network
   - **Seznam.cz** — popular Czech web/email provider, may host some municipal email
   - **Microsoft 365** — likely moderate share
3. Czech municipalities may have more diverse hosting than Nordic countries — local ISPs and Czech hosting providers are competitive

Expected distribution:
- **Microsoft**: Moderate (40-60%)
- **Local Provider**: Significant — O2 CZ, T-Mobile CZ, local hosting
- **Self-hosted**: Higher share than Nordic countries
- **Google**: Low

## Phase 4-5: Domain verification, postprocess, validate

With 205 entries, manual verification is feasible for unknowns/independents.

## Phase 6: TopoJSON

- ORP boundaries: CSÚ publishes official ORP boundary shapefiles
- GitHub: `jlacko/RCzechia` — Czech shapefiles at multiple admin levels
- Overpass API: ORP level is not a standard admin_level — may need to use okres boundaries or CSÚ data
- **Alternative**: Use okres (77 districts) if ORP boundaries are hard to obtain, then expand later

## Phase 7: Frontend

- Add CZ filter button, flag `🇨🇿`, country name "Czechia"
- Map center: Czechia is at ~49.8°N, 15.5°E — visible with current zoom
- Stats grid layout adjustment

## Future: Obce-level expansion

After ORP validation, expanding to all ~6,258 obce would require:
- Frontend optimization (vector tiles or per-region views)
- Separate TopoJSON file for CZ obce
- Extensive domain discovery using `mesta.obce.cz`

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
- Map at obce level (6,258) in the first pass — start with ORP (205)
