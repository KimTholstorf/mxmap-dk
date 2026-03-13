# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MX Map is a DNS-based email provider classifier for ~182 Baltic municipalities (Estonia, Latvia, Lithuania). It runs a 3-stage async pipeline that produces `data.json`, which powers an interactive Leaflet.js map showing where municipalities host their official email. Forked from [mxmap.ch](https://mxmap.ch) (Swiss municipalities).

## Commands

```bash
uv sync                # Install dependencies
uv sync --group dev    # Install with dev dependencies

# Pipeline (run in order, each reads/writes data.json)
uv run preprocess      # DNS lookups + classification (~30s)
uv run postprocess     # Overrides, SMTP banners, scraping (~5 min)
uv run validate        # Confidence scoring + quality gate

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

1. **Preprocess** (`preprocess.py`) — Loads municipalities from `data/municipalities_{ee,lv,lt}.json` seed files + `data/overrides.json`. For each municipality: extracts domain (or guesses from name with Baltic diacritics transliteration), performs async MX/SPF/CNAME/ASN/autodiscover DNS lookups via 3 resolvers (system, Google, Cloudflare), classifies provider, detects gateways. Concurrency: 20.

2. **Postprocess** (`postprocess.py`) — Four sub-steps: (a) apply `MANUAL_OVERRIDES` dict with DNS re-lookup for domain-only overrides, (b) retry DNS for unknowns that have a domain, (c) SMTP banner check on primary MX of independent/unknown entries (deduplicated, concurrency 5), (d) scrape municipality websites for email addresses on remaining unknowns (concurrency 10). Includes TYPO3 Caesar cipher decryption for obfuscated mailto: links.

3. **Validate** (`validate.py`) — Scores each entry 0–100 based on DNS data quality (has domain, MX, SPF, provider match, etc.). Quality gate: average score ≥ 70 and ≥ 80% of entries above 80 confidence. Writes `validation_report.json` and `validation_report.csv`. Exits 1 on failure.

### Classification Hierarchy (`classify.py`)

`classify()` returns `tuple[str, str]` — `(provider, reason)`.

Priority order:
1. **Direct MX match** — MX hostname contains provider keyword
2. **CNAME resolution** — MX host's CNAME target matches a provider
3. **Gateway look-through** — MX is a known gateway/spam filter (SeppMail, Barracuda, etc.) → check SPF/autodiscover for the actual backend provider
4. **Baltic ISP** — MX ASN matches known Baltic ISP ASNs
5. **Independent** — MX exists but doesn't match any known provider
6. **Unknown** — No MX records found

**Important:** SPF is only used to identify the backend provider when MX points to a known gateway. SPF alone does not determine the provider — it only indicates who is authorized to send, not where mailboxes are hosted.

Provider values: `microsoft`, `google`, `aws`, `zone`, `telia`, `tet`, `elkdata`, `baltic-isp`, `independent`, `unknown`.

### Provider Keywords (`constants.py`)

All provider detection is keyword-based. To add a new provider:
1. Add `*_KEYWORDS` list to `constants.py`
2. Add to `PROVIDER_KEYWORDS` dict
3. Add to `SMTP_BANNER_KEYWORDS` if applicable
4. Add to the two provider-matching loops in `classify()` (steps 1 and 2)
5. Add display name mapping + color in `index.html`

### Frontend (`index.html`)

Single-page app that fetches `data.json` + `baltic-municipalities.topo.json`. Normalizes pipeline output (dict keyed by BFS ID) into the shape the map expects. Features: country filters (EE/LV/LT) that update both map styling and legend counts, provider-colored choropleth, click popups with classification reason.

### DNS Module (`dns.py`)

All lookups use 3 independent resolvers with retry logic. Key functions: `lookup_mx()`, `lookup_spf()`, `resolve_spf_includes()` (recursive BFS with loop detection), `resolve_mx_cnames()`, `resolve_mx_asns()` (via Team Cymru DNS), `lookup_autodiscover()`.

## Testing

Tests use `pytest-asyncio` (auto mode) and `respx` for HTTP mocking. DNS is mocked via `AsyncMock` on resolver objects. Fixtures in `conftest.py` provide `sample_municipality`, `sovereign_municipality`, `sample_data_json`. Coverage threshold is 90%.

## Deployment

GitHub Actions nightly workflow (`.github/workflows/nightly.yml`) runs preprocess → postprocess → validate → commit data.json → deploy to GitHub Pages. Quality gate failure creates a GitHub issue. Default branch is `baltic`.
