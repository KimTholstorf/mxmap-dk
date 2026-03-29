# Add Austria to MX Map

You are extending the MX Map to include Austria (~2,095 Gemeinden).
Work locally only — do NOT push to github, do NOT create PRs or branches.
Read CLAUDE.md first for project architecture and the "Adding a New Country" guide.

## Overview

Austria has **~2,095 Gemeinden** (municipalities). OSM admin_level=8. Despite the large count, Austria is uniquely tractable because municipalities use the standardized **`.gv.at`** domain suffix for government services — a GitHub repo (`Yepoleb/gv.at`) has a sanitized list of all `.gv.at` domains.

Administrative hierarchy:
- 9 Bundesländer (federal states)
- 94 Bezirke (79 political districts + 15 Statutarstädte)
- **~2,095 Gemeinden** (municipalities)

**Map at Gemeinde level** (not Bezirk) — the `.gv.at` domain convention and existing domain lists make this feasible despite the count.

## Phase 1: Seed data

Create `data/municipalities_at.json` with all ~2,095 Gemeinden.

1. **Wikidata SPARQL**: Query `Q667509` (municipality of Austria) with:
   - Gemeindekennzahl (GKZ, 5-digit: State + District + Municipality)
   - `P856` — official website
   - `P402` — OSM relation ID
2. **Domain bootstrap**: Use `Yepoleb/gv.at` GitHub repo to get `.gv.at` domains for most municipalities. Pattern: `gemeindename.gv.at` (e.g., `wien.gv.at`, `salzburg.gv.at`, `kirchberg-wagram.gv.at`).
3. **IDs**: Use `AT-` prefix + GKZ: `{"id": "AT-90001", "name": "Wien", "country": "AT", "region": "Wien", "domain": "wien.gv.at", "osm_relation_id": 109166}`
4. **Regions**: Use Bundesland name.

**Domain pitfalls:**
- `.gv.at` is the standard government domain suffix — most municipalities use `name.gv.at`
- Some may also have `.at` domains for websites but `.gv.at` for email
- German umlauts: same as Germany (`ä→ae`, `ö→oe`, `ü→ue` in domains)
- Compound names with hyphens (e.g., `sankt-poelten.gv.at`, not `st-poelten.gv.at`)
- Vienna is `wien.gv.at` (not `vienna.gv.at`)

## Phase 2: Pipeline changes

### preprocess.py
- Add `"AT": "municipalities_at.json"` to `SEED_FILES`
- Add `"AT": [".gv.at", ".at"]` to `tld_map` — note `.gv.at` is a second-level domain
- German umlaut expansion already exists (from DE implementation)
- Add Austrian name suffixes: `" (statutarstadt)"`, `" (marktgemeinde)"`

### constants.py
- Add `"example.at"` to `SKIP_DOMAINS`

### tests
- Update expected countries/TLDs sets
- Add test for `.gv.at` domain generation

## Phase 3: ISP discovery

1. Run `uv run preprocess`
2. Expect to find:
   - **BRZ** (Bundesrechenzentrum) — central federal IT provider
   - **A1 Telekom Austria** (AS8447) — dominant telecom
   - **Magenta Telekom** (AS8412) — T-Mobile Austria
   - **Drei/Hutchison** (AS25255) — third operator
   - **State-level IT providers** — similar to German model
   - **Microsoft 365** — likely significant share (autodiscover under `.gv.at` suggests Exchange/M365)
3. Austrian email landscape likely falls between Nordic (high Microsoft) and German (high local) — data sovereignty awareness is strong but no DSK-equivalent ruling exists

## Phase 4-5: Domain verification, postprocess, validate

With ~2,095 entries, manual verification is not feasible for all. Strategy:
1. Verify all unknowns and independents
2. Cross-check domains against `Yepoleb/gv.at` list
3. Spot-check ~50 across all 9 Bundesländer

## Phase 6: TopoJSON

- GitHub: `ginseng666/GeoJSON-TopoJSON-Austria` — municipalities as of Jan 2021
- Overpass API with `admin_level=8`
- **File size**: ~2,095 Gemeinden will add ~3-5 MB to TopoJSON — manageable
- Verify municipality mergers haven't changed boundaries since the GeoJSON source date

## Phase 7: Frontend

- Add AT filter button, flag `🇦🇹`, country name "Austria"
- Map center: Austria is at ~47.5°N, 13.5°E — at the edge of current view
- **May need to adjust map center** south to accommodate both Scandinavia and Austria/Andorra
- Stats grid: layout adjustment for additional country

## Do NOT
- Push to github
- Create branches or PRs
- Modify .github/workflows
- Skip `.gv.at` domain discovery — it's the key advantage for Austria
