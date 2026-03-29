# Add Norway to MX Map

You are extending the Nordic-Baltic MX Map to include Norway (~356 municipalities/kommuner).
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Phase 1: Seed data

Create `data/municipalities_no.json` with ALL Norwegian municipalities (kommuner).

1. Use web search to find the current official list from Statistics Norway (SSB) or Kartverket. Norway has ~356 municipalities as of 2024.
2. Use Wikidata SPARQL to get OSM relation IDs (`P402`) and official websites (`P856`) for each municipality.
3. For domains: Norwegian municipalities typically use `name.kommune.no` or just `name.no`. Check Wikidata `P856` (official website) to extract the actual domain. Some use abbreviated forms.
4. Format each entry as: `{"id": "NO-0301", "name": "Oslo", "country": "NO", "region": "Oslo", "domain": "oslo.kommune.no", "osm_relation_id": 406091}`
5. Use Norwegian municipality numbers (kommunenummer) for the id field, format `NO-XXXX`.
6. For regions, use the fylke (county) name.

**IMPORTANT domain pitfalls** (read CLAUDE.md "Common Domain Pitfalls"):
- Verify domains via web search, especially for municipalities sharing names with companies
- Some municipalities may use Sami-language domains
- Check that the domain has MX records: `dig +short domain MX`

## Phase 2: Pipeline changes

### preprocess.py
- Add `"NO": "municipalities_no.json"` to `SEED_FILES` dict
- Add Norwegian diacritics to transliteration in `guess_domains()`: `("ø", "o"), ("å", "a"), ("æ", "ae")`
- Add `"NO": [".no", ".kommune.no"]` to `tld_map` in `guess_domains()`
- Add `" kommune"` to the name suffixes to strip

### constants.py
- Add `"kommune.no"` to `SKIP_DOMAINS` if it exists as a generic domain
- Do NOT add ISP ASNs yet — that comes in Phase 3

### tests
- Update `test_loads_all_countries` expected countries set to include `"NO"`
- Update `test_no_country_generates_all_tlds` expected TLDs to include `"no"`
- Add a Norwegian diacritics test case (e.g., "Trømsø" → "tromso")

Run tests: `uv run pytest`

## Phase 3: ISP discovery (iterative)

This is the most important phase. Run it in a loop:

1. Run: `uv run preprocess`
2. Check results — count of "independent" will be high on first run
3. For each independent municipality, check the MX server's ASN:
   ```
   dig +short <mx_host> A | head -1 | xargs -I{} sh -c 'rev=$(echo {} | awk -F. "{print \$4\".\"\$3\".\"\$2\".\"\$1}"); dig +short ${rev}.origin.asn.cymru.com TXT'
   ```
4. Group independents by ASN — common Norwegian ISPs to look for:
   - Telenor (various ASNs)
   - Telia Norge
   - Broadnet / Lyse
   - Loqal
   - Altibox
   - NextGenTel
   - PowerTech / IKT Nordvest
   - Kommunal IT companies (IKT Agder, IKT Orkidé, etc.)
5. Add discovered ISP ASNs to `BALTIC_ISP_ASNS` in `constants.py` with comments
6. Also check for gateway patterns — if MX hostnames contain fortimail, barracuda, etc. add to `GATEWAY_KEYWORDS` if not already there
7. Re-run `uv run preprocess` and repeat until independent count is below ~10

Also check if any municipalities show as "unknown" (no MX). Web-search their actual domain and fix in seed data or add to `MANUAL_OVERRIDES` in `postprocess.py`.

## Phase 4: Domain verification

After ISP discovery stabilizes:

1. List all remaining independent and unknown municipalities
2. Web-search each to verify the domain is correct
3. Also spot-check ~20 random municipalities across different regions to catch corporate namesakes or wrong domains
4. Fix seed data directly for wrong domains, or add `MANUAL_OVERRIDES` in `postprocess.py` for domains that differ from the guessed pattern
5. Run `uv run preprocess` again after fixes

## Phase 5: Postprocess + validate

```bash
uv run postprocess    # Applies overrides, SMTP banner checks, scraping
uv run validate       # Quality gate check
```

Review final counts. Expected rough distribution for Norway:
- Microsoft: majority (60-80%)
- Local ISP: significant minority
- Google: a few
- Independent: <10
- Unknown: <5

## Phase 6: TopoJSON boundaries

1. Find Norway municipality boundaries — options:
   - Overpass API with `admin_level=7` for Norwegian kommuner
   - Kartverket publishes official GeoJSON boundaries
   - Existing TopoJSON repos on GitHub
2. Feature IDs MUST be `relation/XXXXX` format matching `osm_relation_id` in seed data
3. Merge into `baltic-municipalities.topo.json` using the same approach as Finland:
   - Decode existing TopoJSON arcs manually (delta encoding + transform)
   - Convert new boundaries to GeoJSON features with correct IDs
   - Re-encode via Python `topojson` library with `toposimplify=False`
4. Verify feature count matches seed data count

## Phase 7: Frontend

Edit `index.html`:

1. Add NO country filter button: `<button class="country-btn active" data-country="NO">NO</button>`
2. Add to `countryFlags` map: `'NO': '🇳🇴'`
3. Add `'NO'` to `activeCountries` default set
4. Add Norwegian flag emoji in the stats country section
5. Add per-country stats block for Norway in `computeStats()` and rendering
6. Adjust map center/zoom to include Norway — probably `[63.0, 18.0]` zoom 5
7. May need to adjust the "About" panel text to say "Nordic-Baltic" countries list

## Phase 8: Final verification

1. Start local server: `python -m http.server 8000`
2. Open in browser and verify:
   - All Norwegian municipalities appear on the map with correct colors
   - Click a few municipalities — popup shows correct data
   - Country filter NO button works
   - Statistics panel shows Norway breakdown
   - Legend counts sum correctly
   - Shield icons appear for gateway municipalities
3. Run full test suite: `uv run pytest`

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
- Delete or overwrite existing country data
