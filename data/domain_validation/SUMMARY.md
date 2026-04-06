# Domain Validation Summary

**Date:** 2026-04-06
**Scope:** All 195 countries scanned. European core deep-analyzed with metadata fetch + MCP web search.

## Total Impact

**183 wrong seed domains corrected** across 17 countries.

## Corrections by Category

### Direct domain fixes (3)
| Country | Municipality | Wrong Domain | Correct Domain | Issue |
|---------|-------------|-------------|---------------|-------|
| EE | Nõo vald (EE-0528) | noo.ee | nvv.ee | Nõo Lihatööstus meat factory |
| BE | Zuienkerke (BE-31042) | mebosoft.be | zuienkerke.be | Web hosting company |
| KR | Pyeongchang County (KR-132) | en.yes-pc.net | (cleared) | Parked domain for sale |

### Shared non-municipal domains cleared (6)
| Country | Domain | Count | Issue |
|---------|--------|-------|-------|
| NA | arc.org.na | 5 | Association of Regional Councils (NGO) |
| GQ | guineaecuatorialpress.com | 1 | Press/media site |

### Platform/blog domains cleared (174)
| Country | Count | Main patterns |
|---------|-------|---------------|
| ES | 107 | altanet.org (61), blogspot (5), localtic.net (4), ya.com (4), ccbierzo.net (3), others |
| CA | 34 | municipalites-du-quebec (11), sasktel (3), weebly/wix/facebook (5), others |
| VE | 4 | wordpress, blogspot |
| PH | 5 | webs.com, wordpress |
| Others | 24 | AR, BR, CM, CU, DE, DO, DZ, GT, HN, MX, PE, PY |

## Heuristic Improvements Made

The `domain_heuristics.py` script was improved during this review:

1. **Government TLD recognition** — Added `.go.XX`, `.gub.uy`, `.lg.jp`, `.gob.XX` and 30+ country-specific government TLDs to slug extraction
2. **E-gov platform handling** — Added `atende.net`, `rks-gov.net`, `ds.gov.lk`, `gov.kz`, `ls.gov.rs` as known e-gov hosts
3. **Platform domain detection** — Added 30+ blog/free-hosting platform patterns for instant high-risk flagging
4. **Shared portal suppression** — Added `ds.gov.lk`, `gov.kz`, `kk.rks-gov.net` as shared portals to skip

**False positive rates improved:**

| Country | Before | After |
|---------|--------|-------|
| CR | 91% | 5% |
| UY | 95% | 5% |
| BR | 76% | 1% |
| ID | 66% | 1% |
| TH | 89% | 0% |
| JP | 49% | 0% |
| AT | 20% | 1% |
| LK | 88% | 0% |
| KZ | 40% | 0% |

## Remaining Known False Positives

These are legitimate government domains that the heuristic flags due to abbreviation patterns but are NOT wrong:

- **IR** (54%) — Iranian provincial abbreviations (ostan-ar, ostan-as, ostb, etc.)
- **XK** (24%) — Kosovo shared portal `kk.rks-gov.net` for 7 municipalities
- **KR** (13%) — Korean 2-letter county abbreviations on `.go.kr`
- **DE** (2%) — German VG/Amt shared domains
- **Various** small countries with abbreviation conventions

## Scripts

```
scripts/
  domain_heuristics.py     # Layer 1: risk scoring with gov TLD awareness + platform detection
  domain_llm_verify.py     # Layer 2: website metadata extraction for Claude Code review
  validate_domains.py      # Orchestrator with region groups + progress tracking
```

## Output Files

```
data/domain_validation/
  progress.json              # Per-country tracking
  summary.json               # Heuristic summary stats
  {cc}_flagged.json          # Per-country heuristic output
  {cc}_metadata.json         # Website metadata (priority countries)
  {cc}_report.json           # Combined analysis-ready report
  baltics_analysis.json      # Detailed verdicts
  nordics_analysis.json      # Detailed verdicts
  dach_analysis.json         # Detailed verdicts
  benelux_analysis.json      # Detailed verdicts
  british_iberia_analysis.json # Detailed verdicts
  es_platform_domains.json   # ES platform domain list
  SUMMARY.md                 # This file
```
