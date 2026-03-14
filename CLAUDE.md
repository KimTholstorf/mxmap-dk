# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MX Map is a DNS-based email provider classifier for Nordic-Baltic municipalities (Estonia, Latvia, Lithuania, Finland, Norway — ~847 total). It runs a 3-stage async pipeline that produces `data.json`, which powers an interactive Leaflet.js map showing where municipalities host their official email. Forked from [mxmap.ch](https://mxmap.ch) (Swiss municipalities).

## Commands

```bash
uv sync                # Install dependencies
uv sync --group dev    # Install with dev dependencies

# Pipeline (run in order, each reads/writes data.json)
uv run preprocess      # DNS lookups + classification (~30s)
uv run postprocess     # Overrides, SMTP banners, scraping (~5 min)
uv run validate        # Confidence scoring + quality gate

# TopoJSON split (requires mapshaper: npm install -g mapshaper)
python3 scripts/split_topo.py                    # Splits monolithic TopoJSON -> topo/

# Tests
uv run pytest                                    # All tests
uv run pytest tests/test_classify.py             # Single file
uv run pytest tests/test_classify.py::test_name  # Single test
uv run pytest --cov --cov-report=term-missing    # With coverage (90% threshold)

# Lint
uv run ruff check src tests
uv run ruff format src tests

# Local frontend
python -m http.server
```

## Architecture

### Pipeline Stages

All three stages operate on `data.json` at the repo root:

1. **Preprocess** (`preprocess.py`) — Loads municipalities from `data/municipalities_{ee,lv,lt,fi,no}.json` seed files + `data/overrides.json`. For each municipality: extracts domain (or guesses from name with diacritics transliteration), performs async MX/SPF/CNAME/ASN/autodiscover/DKIM DNS lookups via 3 resolvers (system, Google, Cloudflare), classifies provider, detects gateways. Concurrency: 20.

2. **Postprocess** (`postprocess.py`) — Four sub-steps: (a) apply `MANUAL_OVERRIDES` dict with DNS re-lookup for domain-only overrides, (b) retry DNS for unknowns that have a domain, (c) SMTP banner check on primary MX of independent/unknown entries (deduplicated, concurrency 5), (d) scrape municipality websites for email addresses on remaining unknowns (concurrency 10). Includes TYPO3 Caesar cipher decryption for obfuscated mailto: links.

3. **Validate** (`validate.py`) — Scores each entry 0–100 based on DNS data quality (has domain, MX, SPF, provider match, etc.). Quality gate: average score ≥ 70 and ≥ 80% of entries above 80 confidence. Writes `validation_report.json` and `validation_report.csv`. Exits 1 on failure.

### Classification Hierarchy (`classify.py`)

`classify()` returns `tuple[str, str]` — `(provider, reason)`.

Priority order:
1. **Direct MX match** — MX hostname contains provider keyword
2. **CNAME resolution** — MX host's CNAME target matches a provider
3. **Known gateway look-through** — MX matches a `GATEWAY_KEYWORDS` entry (SeppMail, Barracuda, FortiMail, SecMail, D-Fence, Cisco IronPort, MailAnyone, Comendo, Heimdal, StaySecure, edelkey, ippnet, garmtech, etc.) → check SPF (only if exactly one main provider found) → autodiscover → DKIM for the actual backend provider. If no backend identified, returns "independent" with reason mentioning the gateway.
4. **Self-hosted gateway detection** — MX exists but doesn't match any provider or gateway → check DKIM for a hidden backend provider (e.g., `mail.muhu.ee` on Radicenter but DKIM → `*.onmicrosoft.com` = Microsoft)
5. **Local ISP** — MX ASN matches known Nordic-Baltic ISP ASNs (`LOCAL_ISP_ASNS` in constants.py)
6. **Independent** — MX exists but doesn't match any known provider and no DKIM backend found
7. **Unknown** — No MX records found

**SPF vs DKIM for backend detection:**
- **SPF** is only used in step 3 (known gateways), and **only when exactly one main provider is found** in SPF. If multiple providers appear (e.g., Microsoft + Google), SPF is ambiguous — municipalities often include `spf.protection.outlook.com` for shared calendars or hybrid sending without hosting mailboxes on Microsoft. In ambiguous cases, fall through to autodiscover/DKIM.
- **DKIM** is used in both steps 3 and 4. DKIM CNAMEs (`selector1._domainkey.domain → *.onmicrosoft.com`) prove a Microsoft 365 tenant is configured to sign mail for that domain — this is definitive proof of mail hosting. DKIM is the most reliable signal for identifying the actual backend provider.

Provider values: `microsoft`, `google`, `aws`, `zone`, `telia`, `tet`, `elkdata`, `local-isp`, `independent`, `unknown`.

### Provider Keywords (`constants.py`)

All provider detection is keyword-based. To add a new provider:
1. Add `*_KEYWORDS` list to `constants.py`
2. Add to `PROVIDER_KEYWORDS` dict
3. Add to `SMTP_BANNER_KEYWORDS` if applicable
4. Add to the two provider-matching loops in `classify()` (steps 1 and 2)
5. Add display name mapping + color in `index.html`

### Frontend (`index.html`)

Single-page app with three admin-level views (Region/District/Municipality) and per-country lazy-loaded TopoJSON.

**Data loading:** Fetches `data.json` + `topo/manifest.json` on startup. The manifest maps each country × level to a TopoJSON file. Files are fetched on demand and cached in memory (`topoCache`). Default view is "Districts" (~760 features total).

**Multi-level toggle:** Three-button segmented control (top-left) switches between Region, District, and Municipality views. Each level loads different TopoJSON files per country. For countries where two levels are identical (e.g., DE district=municipality), the manifest points both levels at the same file.

**Per-country layers:** Each country has its own `L.geoJSON` layer stored in `countryLayers` Map. Country filter buttons add/remove layers and restyle them (active = provider-colored, inactive = gray).

**Aggregation:** At Region/District levels, multiple municipalities map to one polygon. `computeAggregation()` groups municipalities by region name or district key (AT: first 3 digits of ID, BE: first 2 digits). Each group tracks dominant provider, provider breakdown, and municipality count. `matchGroupFeature()` matches dissolved TopoJSON features to groups by `name` property.

**Popups:** Municipality level shows individual DNS data (MX, SPF, DKIM, autodiscover). Region/District level shows aggregated view: dominant provider badge, stacked provider bar chart, scrollable municipality list with provider dots.

**Statistics panel:** Always shows municipality-level data — unaffected by the level toggle.

**Gateway markers:** Shield icons (🛡️) only shown at municipality level.

### TopoJSON Split (`scripts/split_topo.py`)

Splits `baltic-municipalities.topo.json` (18 MB monolithic source) into per-country per-level files in `topo/`:

```
topo/
  manifest.json                  # { CC: { levels, files, sizes } }
  {cc}_municipality.topo.json    # Per-country municipality boundaries (simplified 15%)
  {cc}_region.topo.json          # Dissolved by region field (11 countries)
  {cc}_district.topo.json        # Dissolved by district key (AT, BE only)
```

**Process:** Converts monolithic TopoJSON → GeoJSON via mapshaper, matches features to seed data municipalities, annotates with country/region/district_key, then for each country: writes municipality TopoJSON, dissolves by region (using mapshaper `-dissolve`), dissolves by district_key for AT/BE. All files simplified 15% with `keep-shapes`.

**Level aliasing:** When district=region or district=municipality for a country, `manifest.json` points both levels at the same file. Frontend detects this via `manifest[cc].files[level] === manifest[cc].files.municipality` to decide whether to aggregate.

Run: `python3 scripts/split_topo.py` (requires mapshaper CLI).

### DNS Module (`dns.py`)

All lookups use 3 independent resolvers with retry logic. Key functions: `lookup_mx()`, `lookup_spf()`, `resolve_spf_includes()` (recursive BFS with loop detection), `resolve_mx_cnames()`, `resolve_mx_asns()`, `resolve_mx_countries()` (both via Team Cymru DNS — ASN + country code from same query), `lookup_autodiscover()`, `lookup_dkim()` (checks `selector1/selector2/google._domainkey` CNAMEs — definitive proof of mail hosting, e.g. CNAME to `*.onmicrosoft.com` = Microsoft 365).

## Testing

Tests use `pytest-asyncio` (auto mode) and `respx` for HTTP mocking. DNS is mocked via `AsyncMock` on resolver objects. Fixtures in `conftest.py` provide `sample_municipality`, `sovereign_municipality`, `sample_data_json`. Coverage threshold is 90%.

## Deployment

GitHub Actions nightly workflow (`.github/workflows/nightly.yml`) runs preprocess → postprocess → validate → commit data.json → deploy to GitHub Pages. Quality gate failure creates a GitHub issue. Default branch is `baltic`.

## Adding a New Country

### 1. Seed data (`data/municipalities_XX.json`)

Create a JSON array of municipalities:
```json
[{"id": "XX-001", "name": "City Name", "country": "XX", "region": "Region", "domain": "city.xx", "osm_relation_id": 12345}]
```
Sources: national statistics office API for official list, Wikidata SPARQL for OSM relation IDs + domains (`P856` website, `P402` OSM relation), Nominatim as fallback for OSM IDs.

### 2. Pipeline changes

- **`preprocess.py`**: Add `"XX": "municipalities_xx.json"` to `SEED_FILES`. Add diacritics transliteration pairs. Add `"XX": [".xx"]` to `tld_map` in `guess_domains()`. Add name suffixes to strip (e.g., " kommun", " kunta").
- **`constants.py`**: Add country-specific ISP ASNs to `LOCAL_ISP_ASNS`. Use Team Cymru DNS (`origin.asn.cymru.com`) to identify ASNs of municipalities classified as "independent" — many will be local ISPs. Add gateway keywords if the country uses local email security appliances (FortiMail, SecMail, etc.). Municipal IT cooperatives (e.g., Norwegian IKT companies like Hedmark IKT, Lofoten IKT) often act as gateways — add them to `GATEWAY_KEYWORDS` or `LOCAL_ISP_ASNS` as appropriate.
- **`constants.py`**: Add `"example.xx"` to `SKIP_DOMAINS`. Add country-specific contact page paths to `SUBPAGES` if different from existing ones.

### 3. TopoJSON boundaries

- Find the OSM `admin_level` for municipalities in that country (varies: EE=7, LV=6, LT=5, FI=8, NO=7)
- Download boundaries via Overpass API or find an existing TopoJSON/GeoJSON source (GitHub repos like GeoHarrier/norway-kommuner-geojson are good sources)
- Feature IDs must be `relation/XXXXX` matching `osm_relation_id` in seed data
- **OSM relation IDs may differ** between Wikidata and current GeoJSON sources for municipalities that underwent mergers. Match by municipality number (`ref` field) to resolve mismatches, then update seed data with the current OSM IDs.
- Merge into `baltic-municipalities.topo.json` using the Python `topojson` library: decode existing TopoJSON arcs manually (delta encoding + transform), combine with new GeoJSON features, re-encode with `toposimplify=False`
- **Preserve `name` and `name_en` properties** on all features — EE/LV features rely on name-based matching (their OSM IDs differ from seed data). Dropping properties breaks the map.
- **Handle degenerate rings**: island municipalities (Saaremaa, Hiiumaa, Kihnu, etc.) have MultiPolygon features where some tiny island rings collapse to < 4 coordinates during quantization. Filter out degenerate rings (< 4 coords) within polygons rather than dropping the entire feature.

### 4. Frontend (`index.html`)

- Add country filter button with flag emoji in the filter bar
- Add country code to `activeCountries` default set
- Add country flag to `countryFlags` map
- Add country section in `computeStats()` and per-country stats rendering
- Adjust map center/zoom if needed

### 5. Tests

- Update `test_loads_all_countries` expected countries set
- Update `test_no_country_generates_all_tlds` expected TLDs
- Add diacritics test case in `TestGuessDomains`

### 6. Verify

Run preprocess → check "independent" municipalities → look up their MX ASNs → add missing local ISPs to `LOCAL_ISP_ASNS` → re-run. Typical pattern: first run has too many "independent", iteratively adding ISP ASNs and gateway keywords brings it down to a handful of genuinely self-hosted servers. Also check for gateway patterns in MX hostnames (e.g., `iphmx.com` = Cisco IronPort, `comendosystems.com` = Comendo) and add to `GATEWAY_KEYWORDS`.

## Common Domain Pitfalls

Municipality domains are the most error-prone part of the data. Always verify domains via web search — do not trust automated guessing alone.

### Domain ≠ municipality name
Many municipality domains do NOT match the municipality name:
- **Corporate namesakes**: `nokia.fi` (phone company), `outokumpu.fi` (mining company), `noo.ee` (meat factory). Cities use `nokiankaupunki.fi`, `outokummunkaupunki.fi`, `nvv.ee`.
- **Tourism/portal sites**: `hiiumaa.ee` (tourism portal, municipality is at `vald.hiiumaa.ee`), `peipsi.ee` (tourism NGO, municipality is `peipsivald.ee`), `rouge.ee` (community portal, municipality is `rougevald.ee`).
- **Gaming/unrelated sites**: `siauliu.lt` was a Counter-Strike gaming site; the actual municipality domain is `siauliuraj.lt`.

### Bilingual municipalities use the minority-language domain
Swedish-speaking Finnish municipalities consistently use their **Swedish name** for domains: Kruunupyy→`kronoby.fi`, Luoto→`larsmo.fi`, Maalahti→`malax.fi`, Vöyri→`vora.fi`, Kristiinankaupunki→`krs.fi`.

### Latvian novads vs city domains
After Latvia's 2021 municipal reform, many novads (counties) have their own domains distinct from the main city: `bauskasnovads.lv` (not `bauska.lv`), `valmierasnovads.lv` (not `valmiera.lv`), `ventspilsnd.lv` (not `ventspils.lv` which is the city). The seed data domain with no MX causes the pipeline to guess the city domain instead — always set the correct novads domain in seed data.

### Norwegian municipality domains
Norwegian municipalities mostly use `name.kommune.no`, but exceptions exist: `ha.no` (Hå), `sarpsborg.com` (Sarpsborg), `voss.herad.no` (Voss herad), `mgk.no` (Midtre Gauldal), `ahk.no` (Aurskog-Høland). Sami-language municipalities may use `.suohkan.no` for their website but `.kommune.no` for email (e.g., Kautokeino). Post-merger municipalities sometimes retain stale "nye" (new) domains — always verify the current domain has MX records.

### Website domain ≠ email domain
Some municipalities use different domains for their website and email. When the seed data domain has no MX records, the pipeline falls back to guessing from the municipality name, which may find a wrong domain. Always check MX records for the seed data domain; if empty, search for the actual email domain.

### Verification approach
For each country, web-search every municipality to verify domains. Use `dig +short domain MX` to confirm MX records exist. The `MANUAL_OVERRIDES` dict in `postprocess.py` handles cases where the guessed domain is wrong but the seed data domain is correct for the website (overrides trigger DNS re-lookup on the corrected domain).

## Gateway Detection Patterns

Municipalities often use local email security gateways (FortiMail, SecMail, D-Fence, Barracuda, etc.) that relay to cloud providers. The pipeline detects these via `GATEWAY_KEYWORDS` in `constants.py`. When a gateway is detected, the pipeline checks SPF → autodiscover → DKIM to identify the backend provider.

Small local IT companies can also act as gateways (e.g., `edelkey.net` for Helsinki, `ippnet.fi` for Parkano, `garmtech.com` for Saulkrasti). Add these to `GATEWAY_KEYWORDS` when discovered — otherwise they get classified as "independent" instead of the actual backend provider.

**Gateway SPF ambiguity:** When looking through a gateway, SPF is only trusted if exactly one main provider keyword is found. Many municipalities have multiple providers in SPF (e.g., Microsoft for mailboxes + Google for transactional email), making SPF ambiguous. In those cases, the pipeline falls through to autodiscover and DKIM for a definitive answer. If none of SPF/autodiscover/DKIM identifies a backend, the municipality is classified as "independent" with a reason mentioning the gateway name.

**DKIM is the most reliable signal** for identifying the backend provider. A CNAME at `selector1._domainkey.domain` pointing to `*.onmicrosoft.com` is definitive proof of Microsoft 365, even when MX and SPF point elsewhere.

**Norwegian IKT cooperatives:** Many Norwegian municipalities share IT infrastructure via regional IKT companies (Hedmark IKT, Lofoten IKT, IKT Sunnmøre, etc.). These appear as shared MX hosts or DKIM tenants (e.g., `lofotenikt.onmicrosoft.com`). They typically relay to Microsoft 365.
