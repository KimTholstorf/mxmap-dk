# Add Germany to MX Map

You are extending the Nordic-Baltic MX Map to include Germany.
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Scale decision: Landkreis level first

Germany has **~10,754 Gemeinden** (municipalities) — 9.5x the current total of 1,137 entries. Mapping at Gemeinde level has major implications for TopoJSON size (~15-25 MB), frontend rendering (10K+ polygons), and pipeline runtime (~5-6 min DNS lookups). Many small Gemeinden share IT infrastructure with their Amt/Verbandsgemeinde and may not have their own email domain.

**Start with Landkreis + kreisfreie Städte (~400 units)**. This is comparable in scale to Norway (357), validates the pipeline for Germany, and each unit has independent IT administration. A Gemeinde-level expansion can follow as Phase 2.

Germany's administrative hierarchy:
- **16 Bundesländer** (federal states, including 3 city-states: Berlin, Hamburg, Bremen)
- **294 Landkreise** (rural districts) + **106 kreisfreie Städte** (district-free cities) = **~400 units**
- **~10,754 Gemeinden** (municipalities) — future expansion

OSM admin_level: Bundesländer=4, Landkreise/kreisfreie Städte=6, Gemeinden=8. **Use admin_level=6.**

## Phase 1: Seed data

Create `data/municipalities_de.json` with ALL Landkreise and kreisfreie Städte.

1. **Official list**: Download from Destatis GV-ISys at `destatis.de/DE/Themen/Laender-Regionen/Regionales/Gemeindeverzeichnis`. The GV100 file contains the full hierarchy. A parsed version is available at GitHub `digineo/gemeindeverzeichnis`.
2. **Wikidata SPARQL**: Get OSM relation IDs (`P402`) and official websites (`P856`). Relevant classes:
   - `Q106658` — Landkreis (rural district)
   - `Q22865` — kreisfreie Stadt (district-free city)
   - `P439` — Amtlicher Gemeindeschlüssel (AGS, 8-digit code)
   - `P856` — official website
   - `P402` — OSM relation ID

   Example query:
   ```sparql
   SELECT ?item ?itemLabel ?ags ?website ?osmRelation WHERE {
     { ?item wdt:P31/wdt:P279* wd:Q106658 }  # Landkreis
     UNION
     { ?item wdt:P31/wdt:P279* wd:Q22865 }    # kreisfreie Stadt
     ?item wdt:P17 wd:Q183 ;                   # country = Germany
           wdt:P439 ?ags .
     OPTIONAL { ?item wdt:P856 ?website }
     OPTIONAL { ?item wdt:P402 ?osmRelation }
     SERVICE wikibase:label { bd:serviceParam wikibase:language "de,en". }
   }
   ```
3. **IDs**: Use AGS code with `DE-` prefix: `{"id": "DE-09162", "name": "München", "country": "DE", ...}`. For Landkreise the AGS is typically 5 digits (2-digit Bundesland + 1-digit Regierungsbezirk + 2-digit Kreis), padded to 8 digits for Gemeinden but 5 is sufficient at Kreis level.
4. **Regions**: Use Bundesland name as the region field.
5. Format: `{"id": "DE-09162", "name": "München", "country": "DE", "region": "Bayern", "domain": "muenchen.de", "osm_relation_id": 62428}`

**IMPORTANT domain pitfalls** (read CLAUDE.md "Common Domain Pitfalls"):

German Landkreis/Stadt domains are highly irregular:

| Pattern | Example | Notes |
|---------|---------|-------|
| `name.de` | `berlin.de`, `muenchen.de` | Large cities |
| `stadt-name.de` | `stadt-koeln.de` | Common for medium cities |
| `kreis-name.de` | `kreis-paderborn.de` | Some Landkreise |
| `landkreis-name.de` | `landkreis-muenchen.de` | Some Landkreise |
| `lk-name.de` | `lk-rostock.de` | Abbreviated Landkreis |
| `name-kreis.de` | Various | Less common |

**Corporate namesakes are a serious risk**: Germany is home to many global companies named after cities. Verify every domain. Examples of potential conflicts:
- Cities that share names with major companies (always verify the `.de` domain owner)
- Compound names where the domain differs from the official name
- Umlaut transliteration: `ü→ue`, `ö→oe`, `ä→ae`, `ß→ss` (not just dropping diacritics like Nordic countries — German convention is to expand umlauts)

**Bilingual areas** (Sorbian in Saxony/Brandenburg, Danish in Schleswig-Holstein, Frisian in North Frisia) use German-language domains.

**Wikidata P856 is essential** — do not rely on name-based domain guessing for Germany. Extract domains from official websites and verify MX records with `dig +short domain MX`.

## Phase 2: Pipeline changes

### preprocess.py
- Add `"DE": "municipalities_de.json"` to `SEED_FILES` dict
- German umlaut transliteration needs **expansion** not just stripping: `("ü", "ue"), ("ö", "oe"), ("ä", "ae"), ("ß", "ss")`. Check if the existing `("ä", "a"), ("ö", "o")` pairs conflict — you may need country-specific transliteration or add the `ue/oe/ae` variants as additional guesses
- Add `"DE": [".de"]` to `tld_map` in `guess_domains()`
- Add name suffixes to strip: `" (kreisfreie Stadt)"`, strip `"Landkreis "` prefix, `"Stadt "` prefix
- **Note**: Domain guessing will be unreliable for Germany. The seed data domains from Wikidata are critical.

### constants.py
- Add `"example.de"` to `SKIP_DOMAINS`
- Add German-specific contact page paths to `SUBPAGES`: `"/kontakt"`, `"/impressum"`, `"/service/kontakt"`
- Do NOT add ISP ASNs yet — that comes in Phase 3

### tests
- Update `test_loads_all_countries` expected countries set to include `"DE"`
- Update `test_no_country_generates_all_tlds` expected TLDs to include `"de"`
- Add a German umlaut test case (e.g., "München" → "muenchen" or "munchen")

Run tests: `uv run pytest`

## Phase 3: ISP and IT cooperative discovery (iterative)

This is the most important and complex phase. Germany's municipal IT landscape is fundamentally different from Nordic countries.

### Publicly-owned IT service providers (Kommunale IT-Dienstleister)

Germany has **~59 publicly-owned IT service providers** (organized under the umbrella association **Vitako**) serving ~10,000 municipalities. These are analogous to Norwegian IKT companies but much larger. Key ones to watch for:

| Provider | Region | Notes |
|----------|--------|-------|
| **Dataport** | Hamburg, Schleswig-Holstein, Bremen, Sachsen-Anhalt, MV | Major; shared MX infrastructure |
| **AKDB** | Bayern | Serves ~5,000 municipal customers |
| **ekom21** | Hessen | Merged from 5 regional data centers |
| **Komm.ONE** | Baden-Württemberg | Merged from 4 providers in 2018 |
| **ITEOS** | Baden-Württemberg | Also serves BaWü |
| **KDN / regio iT** | Nordrhein-Westfalen | NRW municipalities |
| **DIKOM** | Brandenburg | Brandenburg municipalities |
| **Kommunale Informationsverarbeitung Sachsen (KISA)** | Sachsen | Saxon municipalities |
| **ITK Rheinland** | NRW (Rheinland) | Regional IT cooperative |

These will appear as shared MX hostnames, shared ASNs, or DKIM tenants. They should be added to `LOCAL_ISP_ASNS` or `GATEWAY_KEYWORDS` as appropriate.

### Discovery loop

1. Run: `uv run preprocess`
2. Count "independent" — will be very high on first run
3. For each independent entry, check the MX server's ASN:
   ```
   dig +short <mx_host> A | head -1 | xargs -I{} sh -c 'rev=$(echo {} | awk -F. "{print \$4\".\"\$3\".\"\$2\".\"\$1}"); dig +short ${rev}.origin.asn.cymru.com TXT'
   ```
4. Group by ASN — expect to find:
   - **Deutsche Telekom / T-Systems** (AS3320, AS6878) — very common
   - **IONOS / 1&1** (AS8560) — popular hosting provider
   - **Hetzner** (AS24940) — popular German hosting
   - **Strato** (AS6724) — web/email hosting
   - **Dataport**, **AKDB**, etc. — public IT providers (will have their own ASNs)
   - **Open Telekom Cloud** — T-Systems' cloud, used by some government entities
5. Add discovered ASNs to `LOCAL_ISP_ASNS` in `constants.py`
6. Check for gateway patterns in MX hostnames — German-specific gateways:
   - **NoSpamProxy** (Net at Work) — BSI-certified, marketed to German public sector. Look for `nospamproxy` in MX hostnames
   - **Hornetsecurity** — Hannover-based cloud email security
   - **Retarus** — Munich-based email gateway
   - **SeppMail** (already in GATEWAY_KEYWORDS) — also used in Germany
   - **Cisco IronPort**, **Barracuda**, **FortiMail** (already in GATEWAY_KEYWORDS)
   - **Secumail** — check for `secumail` patterns
   Add new patterns to `GATEWAY_KEYWORDS`
7. Re-run `uv run preprocess` and repeat until independent count stabilizes

### Expected distribution (Germany is different from Nordic countries!)

Germany's data protection conference (DSK) has ruled that Microsoft 365 **cannot be used in GDPR-compliant manner** by public institutions. Several Bundesländer have banned or are migrating away from Microsoft 365. Expect:

- **Microsoft**: Lower share than Nordic countries (maybe 30-50%, not 80-90%)
- **Local ISP / IT cooperatives**: Much higher share (30-50%) — Dataport, AKDB, etc.
- **IONOS/T-Systems/Hetzner**: Significant share for self-hosted on German infrastructure
- **Google**: Very low (even more restricted than Microsoft in German public sector)
- **Independent/self-hosted**: Higher share than Nordic countries
- **Open-source solutions**: Some municipalities use Kopano, Open-Xchange, or other open-source email

This different distribution is analytically interesting — it shows Germany's more sovereignty-conscious approach.

## Phase 4: Domain verification

After ISP discovery stabilizes:

1. List all remaining independent and unknown entries
2. Web-search each to verify the domain is correct
3. Spot-check ~30 entries across different Bundesländer — corporate namesakes are a real risk
4. Pay special attention to:
   - Landkreise that may use a different domain than expected (e.g., `kreis-` prefix vs `landkreis-` prefix vs bare name)
   - Kreisfreie Städte that may use `stadt-` prefix
   - Entries with no MX records — check if the Landkreis/Stadt uses a different email domain than its website domain
5. Fix seed data or add `MANUAL_OVERRIDES` in `postprocess.py`
6. Re-run `uv run preprocess`

## Phase 5: Postprocess + validate

```bash
uv run postprocess    # Applies overrides, SMTP banner checks, scraping
uv run validate       # Quality gate check
```

Review final counts. Because Germany has ~400 entries (comparable to Norway's 357), the quality gate thresholds should be achievable.

## Phase 6: TopoJSON boundaries

1. **Find Germany Kreis-level boundaries** — options:
   - GitHub repos: `isellsoap/deutschlandGeoJSON` (has Landkreis-level GeoJSON)
   - Overpass API with `admin_level=6`
   - Destatis publishes official shapefiles
   - Bundesamt für Kartographie und Geodäsie (BKG) has authoritative data
2. Feature IDs MUST be `relation/XXXXX` format matching `osm_relation_id` in seed data
3. **OSM relation ID mismatches**: Germany has had recent Kreisreformen (district mergers), especially in Mecklenburg-Vorpommern (2011) and Sachsen (2008). Verify OSM IDs match current boundaries. Match by AGS code or `ref` field to resolve mismatches.
4. Merge into `baltic-municipalities.topo.json`:
   - Decode existing TopoJSON arcs manually (delta encoding + transform)
   - Convert new boundaries to GeoJSON features with correct IDs
   - **Preserve `name` and `name_en` properties** on ALL features (existing EE/LV features rely on name matching)
   - **Filter degenerate rings** (< 4 coordinates) within MultiPolygons
   - Re-encode via Python `topojson` library with `toposimplify=False`
   - **File size check**: adding ~400 German Kreise should add ~1-2 MB to the TopoJSON — manageable
5. Verify: all seed data OSM IDs must have a matching feature in the TopoJSON, and all existing features must be preserved (check count before and after — **the Sweden merge dropped 21 features**, don't repeat this)

## Phase 7: Frontend

Edit `index.html`:

1. Add DE country filter button: `<button class="country-btn active" data-country="DE">DE</button>`
2. Add to `FLAGS` map: `'DE': '🇩🇪'`
3. Add `'DE'` to `activeCountries` default set
4. Add `'DE': 'Germany'` to `countryNames`
5. Add `'DE'` color to `countryColors` for MX server location stats
6. Add `'DE'` to the `mxLocal` country check
7. Add `'DE'` to the `activeList` in per-country stats
8. Adjust map center/zoom — current `[63.0, 18.0]` zoom 5 is centered on Scandinavia. Germany extends south to ~47.3°N. Consider `[58.0, 18.0]` zoom 4 or `[55.0, 15.0]` zoom 5 to include both Scandinavia and Germany.
9. Update the "What is this?" card to mention Germany
10. **Stats layout**: The current 3×2 grid for 6 countries will need to become a 4×2 or similar layout for 7 countries. Consider adjusting `.stats-countries` grid.
11. **Consider renaming** "Nordic-Baltic" in the title/subtitle to something like "Nordic-Baltic & German" or "European" — discuss with project owner.

## Phase 8: Final verification

1. Start local server: `python -m http.server 8000`
2. Open in browser and verify:
   - All German Landkreise/Städte appear on the map with correct colors
   - Click a few entries — popup shows correct data
   - Country filter DE button works
   - Statistics panel shows Germany breakdown
   - Shield icons appear for gateway entries
   - Existing countries (EE/LV/LT/FI/NO/SE) still display correctly
   - **Check that the TopoJSON merge didn't drop any existing features**
3. Run full test suite: `uv run pytest`

## Future: Gemeinde-level expansion

After Landkreis-level is validated, a Gemeinde-level (~10,754) expansion would require:

1. **Frontend optimization**: Switch from Leaflet's default SVG/Canvas to vector tiles (e.g., `leaflet.vectorgrid` with TopoJSON tiles) or split into per-Bundesland views
2. **TopoJSON splitting**: Serve German Gemeinde boundaries as a separate file loaded on demand when DE filter is active
3. **Pipeline performance**: Increase `CONCURRENCY` for the German run, or parallelize by Bundesland
4. **Data quality**: Many small Gemeinden (~1,000 population) may not have their own email domain — they share IT with their Verwaltungsgemeinschaft/Amt. These would show as "unknown" and need manual domain research per Bundesland.

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
- Delete or overwrite existing country data
- Map at Gemeinde level in the first pass — start with Landkreis
