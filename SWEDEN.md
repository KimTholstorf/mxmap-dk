# Add Sweden to MX Map

You are extending the Nordic-Baltic MX Map to include Sweden (~290 municipalities/kommuner).
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Phase 1: Seed data

Create `data/municipalities_se.json` with ALL Swedish municipalities (kommuner).

1. Use web search to find the current official list from Statistics Sweden (SCB). Sweden has 290 municipalities as of 2024.
2. Use Wikidata SPARQL to get OSM relation IDs (`P402`) and official websites (`P856`) for each municipality. Query for `Q127448` (municipality of Sweden) with `P2504` (municipality code).
3. For domains: Swedish municipalities do NOT have a uniform domain pattern like Norway's `.kommune.no`. Domains vary widely — some use `name.se`, others use custom domains. Always extract from Wikidata `P856`. Common patterns:
   - `name.se` (e.g., `stockholm.se`, `goteborg.se`)
   - Abbreviated forms (e.g., `borlange.se` for Borlänge)
   - Completely different domains (watch for corporate namesakes)
4. Format each entry as: `{"id": "SE-0180", "name": "Stockholm", "country": "SE", "region": "Stockholms län", "domain": "stockholm.se", "osm_relation_id": 398021}`
5. Use Swedish municipality codes (kommunkod) for the id field, format `SE-XXXX`.
6. For regions, use the län (county) name.

**IMPORTANT domain pitfalls** (read CLAUDE.md "Common Domain Pitfalls"):
- Verify domains via web search — Swedish municipality domains are highly irregular and many will NOT match the municipality name
- Corporate namesakes are a real risk: e.g., `sandvik.se` (engineering company), `ericsson.se` (telecom company) — always verify the domain belongs to the municipality
- Some municipalities share domains with their region or use subdomains
- Check that the domain has MX records: `dig +short domain MX`
- Bilingual municipalities (Finnish-speaking in Norrbotten/Tornedalen) may use alternative name forms

## Phase 2: Pipeline changes

### preprocess.py
- Add `"SE": "municipalities_se.json"` to `SEED_FILES` dict
- Swedish diacritics are already covered by existing transliteration: `("ä", "a"), ("ö", "o"), ("å", "a")` — verify these are sufficient
- Add `"SE": [".se"]` to `tld_map` in `guess_domains()`
- Add `" kommun"` to the name suffixes to strip

### constants.py
- Add `"example.se"` to `SKIP_DOMAINS`
- Add `"/kontakt"` to `SUBPAGES` if not already present (Swedish municipalities use `/kontakt` or `/kontakta-oss`)
- Do NOT add ISP ASNs yet — that comes in Phase 3

### tests
- Update `test_loads_all_countries` expected countries set to include `"SE"`
- Update `test_no_country_generates_all_tlds` expected TLDs to include `"se"`
- Add a Swedish diacritics test case (e.g., "Malmö" → "malmo")

Run tests: `uv run pytest`

## Phase 3: ISP discovery (iterative)

This is the most important phase. Run it in a loop:

1. Run: `uv run preprocess`
2. Check results — count of "independent" will be high on first run
3. For each independent municipality, check the MX server's ASN:
   ```
   dig +short <mx_host> A | head -1 | xargs -I{} sh -c 'rev=$(echo {} | awk -F. "{print \$4\".\"\$3\".\"\$2\".\"\$1}"); dig +short ${rev}.origin.asn.cymru.com TXT'
   ```
4. Group independents by ASN — common Swedish ISPs and IT providers to look for:
   - Telia Sweden (AS3301, AS1299)
   - Bahnhof
   - Bredband2
   - IP-Only / GlobalConnect
   - Netnod
   - Kommunal IT companies (e.g., Inera, Advania, Tieto/TietoEVRY)
   - Municipal IT cooperatives (kommunalförbund) — similar to Norwegian IKT companies
5. Add discovered ISP ASNs to `LOCAL_ISP_ASNS` in `constants.py` with comments
6. Also check for gateway patterns — Swedish municipalities commonly use:
   - Cisco IronPort (`iphmx.com`) — already in GATEWAY_KEYWORDS
   - StaySecure (`staysecuregroup.com`) — already in GATEWAY_KEYWORDS
   - MailAnyone/VIPRE (`mailanyone.net`, `mx25.net`, `electric.net`) — `mailanyone.net` already in GATEWAY_KEYWORDS, consider adding `mx25.net` and `electric.net`
   - Proofpoint (`ppe-hosted.com`) — already in GATEWAY_KEYWORDS
   - Halon (Swedish email security company) — check if any MX patterns appear
   Add new patterns to `GATEWAY_KEYWORDS` if not already there
7. Re-run `uv run preprocess` and repeat until independent count is below ~10

Also check if any municipalities show as "unknown" (no MX). Web-search their actual domain and fix in seed data or add to `MANUAL_OVERRIDES` in `postprocess.py`.

## Phase 4: Domain verification

After ISP discovery stabilizes:

1. List all remaining independent and unknown municipalities
2. Web-search each to verify the domain is correct
3. Also spot-check ~20 random municipalities across different regions to catch corporate namesakes or wrong domains — this is especially important for Sweden where domain patterns are irregular
4. Fix seed data directly for wrong domains, or add `MANUAL_OVERRIDES` in `postprocess.py` for domains that differ from the guessed pattern
5. Run `uv run preprocess` again after fixes

## Phase 5: Postprocess + validate

```bash
uv run postprocess    # Applies overrides, SMTP banner checks, scraping
uv run validate       # Quality gate check
```

Review final counts. Expected rough distribution for Sweden:
- Microsoft: majority (60-80%)
- Google: moderate share (Sweden has higher Google Workspace adoption than Norway)
- Local ISP: some
- Independent: <10
- Unknown: <5

## Phase 6: TopoJSON boundaries

1. Find Sweden municipality boundaries — options:
   - Overpass API with `admin_level=7` for Swedish kommuner
   - Lantmäteriet (Swedish mapping authority) publishes official boundaries
   - SCB publishes statistical boundaries
   - Existing GeoJSON repos on GitHub (search for "sweden kommuner geojson")
2. Feature IDs MUST be `relation/XXXXX` format matching `osm_relation_id` in seed data
3. **OSM relation ID mismatches are likely** for municipalities that merged or changed boundaries. Match by municipality code (`ref` field) to resolve, then update seed data OSM IDs. This was a significant issue with Norway (20 out of 357 needed fixing).
4. Merge into `baltic-municipalities.topo.json`:
   - Decode existing TopoJSON arcs manually (delta encoding + transform)
   - Convert new boundaries to GeoJSON features with correct IDs
   - **Preserve `name` and `name_en` properties** on ALL features (existing EE/LV features rely on name matching)
   - **Filter degenerate rings** (< 4 coordinates) within MultiPolygons — do NOT drop entire features (island municipalities like Gotland will have complex MultiPolygon geometries)
   - Re-encode via Python `topojson` library with `toposimplify=False`
5. Verify: all seed data OSM IDs must have a matching feature in the TopoJSON, and all existing features must be preserved (check count before and after)

## Phase 7: Frontend

Edit `index.html`:

1. Add SE country filter button: `<button class="country-btn active" data-country="SE">SE</button>`
2. Add to `FLAGS` map: `'SE': '🇸🇪'`
3. Add `'SE'` to `activeCountries` default set
4. Add `'SE': 'Sweden'` to `countryNames`
5. Add `'SE'` color to `countryColors` for MX server location stats
6. Add `'SE'` to the `mxLocal` country check (the `cc.some(c => [...].includes(c))` line)
7. Add `'SE'` to the `activeList` in per-country stats
8. Adjust map center/zoom if needed — current `[63.0, 18.0]` zoom 5 should already cover Sweden
9. Update the "What is this?" card to list Sweden in the countries

## Phase 8: Final verification

1. Start local server: `python -m http.server 8000`
2. Open in browser and verify:
   - All Swedish municipalities appear on the map with correct colors
   - Click a few municipalities — popup shows correct data (including autodiscover/DKIM when present)
   - Country filter SE button works
   - Statistics panel shows Sweden breakdown
   - Legend counts sum correctly
   - Shield icons appear for gateway municipalities
   - Existing countries (EE/LV/LT/FI/NO) still display correctly
3. Run full test suite: `uv run pytest`

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
- Delete or overwrite existing country data
