#!/usr/bin/env python3
"""Build slim frontend data files from pipeline output.

Usage: python3 scripts/build_frontend.py

Reads:
  data.json  (full pipeline output, 6 MB)

Produces:
  data-summary.json  (map/stats fields only, ~60 KB gzipped)
  data-detail.json   (popup fields, keyed by bfs, ~130 KB gzipped)
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Fields needed for map rendering, legend, stats, and aggregation
SUMMARY_FIELDS = {
    "bfs",
    "name",
    "name_en",
    "canton",
    "district",
    "country",
    "domain",
    "provider",
    "jurisdiction",
    "confidence",
    "osm_relation_id",
    "mx_countries",
    "gateway",
    "isp_name",
    "population",
}

# Fields needed only for popups (loaded in background)
DETAIL_FIELDS = {
    "mx",
    "spf",
    "reason",
    "autodiscover",
    "dkim",
    "txt_verifications",
    "tenant",
    "smtp_software",
}

# Fields intentionally dropped (not used by frontend)
# spf_resolved, mx_asns, smtp_banner, mx_cnames

# Jurisdiction grouping: each raw provider maps to a sovereignty category.
# US Cloud = subject to US CLOUD Act / FISA 702.
# EU Provider = hosted within EU/EEA legal jurisdiction.
# Self-hosted = municipality runs its own mail server.
PROVIDER_JURISDICTION = {
    "microsoft": "us-cloud",
    "google": "us-cloud",
    "aws": "us-cloud",
    "zoho": "us-cloud",
    "yandex": "foreign-cloud",   # Russian jurisdiction
    "zone": "eu-provider",
    "telia": "eu-provider",
    "tet": "eu-provider",
    "elkdata": "eu-provider",
    "local-isp": "eu-provider",
    "independent": "self-hosted",
    "unknown": "unknown",
}

# Display names for jurisdiction categories (used in region data + legend)
PROVIDER_DISPLAY = {
    "microsoft": "US Cloud",
    "google": "US Cloud",
    "aws": "US Cloud",
    "zoho": "US Cloud",
    "yandex": "Foreign Cloud",
    "zone": "EU Provider",
    "telia": "EU Provider",
    "tet": "EU Provider",
    "elkdata": "EU Provider",
    "local-isp": "EU Provider",
    "independent": "Self-hosted",
    "unknown": "Unknown",
}

COLORS = {
    "US Cloud":      "#E83838",
    "Foreign Cloud": "#FF7A5C",
    "EU Provider":   "#10B898",
    "Self-hosted":   "#5B8DEF",
    "Unknown":       "#BFBFBF",
}

US_PROVIDERS = {"US Cloud", "Foreign Cloud"}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def blend_provider_colors(providers: dict[str, int], total: int) -> str:
    r = g = b = 0.0
    for p, count in providers.items():
        color = COLORS.get(p, COLORS["Unknown"])
        cr, cg, cb = hex_to_rgb(color)
        w = count / total
        r += cr * w
        g += cg * w
        b += cb * w
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def build_region_data(munis: dict, generated: str) -> dict:
    """Build pre-computed region-level aggregations with population weighting."""
    countries: dict[str, dict] = {}

    # First pass: collect per-country population stats for fallback estimation
    country_pops: dict[str, list[int]] = {}
    for bfs, m in munis.items():
        cc = m.get("country", "")
        pop = m.get("population", 0) or 0
        if pop > 0:
            country_pops.setdefault(cc, []).append(pop)

    # Compute median population per country for fallback
    country_median: dict[str, int] = {}
    for cc, pops in country_pops.items():
        sorted_pops = sorted(pops)
        mid = len(sorted_pops) // 2
        country_median[cc] = sorted_pops[mid] if sorted_pops else 0

    for bfs, m in munis.items():
        cc = m.get("country", "")
        region = m.get("canton", "") or ""
        raw_provider = m.get("provider", "unknown")
        provider = PROVIDER_DISPLAY.get(raw_provider, raw_provider)
        pop = m.get("population", 0) or 0
        # Fallback: use country median if no population, or 1 if no data at all
        if pop <= 0:
            pop = country_median.get(cc, 0) or 1
        has_gateway = bool(
            m.get("gateway")
            and cc in (m.get("mx_countries") or [])
            and provider in US_PROVIDERS
        )

        if cc not in countries:
            countries[cc] = {
                "total": 0,
                "providers": {},
                "popProviders": {},
                "popTotal": 0,
                "gateway_count": 0,
                "regions": {},
            }
        cd = countries[cc]
        cd["total"] += 1
        cd["providers"][provider] = cd["providers"].get(provider, 0) + 1
        cd["popProviders"][provider] = cd["popProviders"].get(provider, 0) + pop
        cd["popTotal"] += pop
        if has_gateway:
            cd["gateway_count"] += 1

        if region not in cd["regions"]:
            cd["regions"][region] = {
                "count": 0,
                "providers": {},
                "popProviders": {},
                "popTotal": 0,
                "gateway_count": 0,
            }
        rd = cd["regions"][region]
        rd["count"] += 1
        rd["providers"][provider] = rd["providers"].get(provider, 0) + 1
        rd["popProviders"][provider] = rd["popProviders"].get(provider, 0) + pop
        rd["popTotal"] += pop
        if has_gateway:
            rd["gateway_count"] += 1

    # Compute blended colors: population-weighted if available, count-based as fallback
    for cc, cd in countries.items():
        if cd["popTotal"] > cd["total"]:
            cd["blendedColor"] = blend_provider_colors(cd["popProviders"], cd["popTotal"])
        else:
            cd["blendedColor"] = blend_provider_colors(cd["providers"], cd["total"])
        sorted_providers = sorted(cd["providers"].items(), key=lambda x: -x[1])
        cd["dominant"] = sorted_providers[0][0] if sorted_providers else "Unknown"

        for rname, rd in cd["regions"].items():
            sorted_providers = sorted(
                rd["providers"].items(), key=lambda x: -x[1]
            )
            rd["dominant"] = sorted_providers[0][0] if sorted_providers else "Unknown"
            rd["dominance"] = round(
                sorted_providers[0][1] / rd["count"], 3
            ) if sorted_providers else 0
            # Use population-weighted color if we have real population data
            if rd["popTotal"] > rd["count"]:
                rd["blendedColor"] = blend_provider_colors(rd["popProviders"], rd["popTotal"])
            else:
                rd["blendedColor"] = blend_provider_colors(rd["providers"], rd["count"])

    return {"generated": generated, "total": len(munis), "countries": countries}


def _compute_confidence(entry: dict) -> int:
    """Compute a 0-100 confidence score for an entry.

    Derived from validate.score_entry() logic — duplicated here to avoid a
    full pipeline dependency and the MANUAL_OVERRIDE_BFS side-effect.
    """
    from mail_sovereignty.classify import classify_from_mx, classify_from_spf, spf_mentions_providers
    from mail_sovereignty.constants import PROVIDER_KEYWORDS

    provider = entry.get("provider", "unknown")
    domain = entry.get("domain", "")
    mx = entry.get("mx", [])
    spf = entry.get("spf", "")

    if provider == "merged":
        return 100

    score = 0

    if domain:
        score += 15
    if mx:
        score += 25
        if len(mx) >= 2:
            score += 5
    if spf:
        score += 15
        if spf.rstrip().endswith("-all"):
            score += 5
        elif "~all" in spf:
            score += 3

    mx_provider = classify_from_mx(mx)
    spf_provider = classify_from_spf(spf)
    spf_providers = spf_mentions_providers(spf)

    if mx_provider and spf_provider:
        if mx_provider == spf_provider or mx_provider in spf_providers:
            score += 20
        elif mx_provider == "independent" and spf_provider:
            score += 10
        else:
            score -= 20
    elif mx_provider == "independent" and spf and not spf_provider:
        score += 20

    main_spf_providers = spf_providers & set(PROVIDER_KEYWORDS.keys())
    if len(main_spf_providers) >= 2:
        score -= 10

    if not mx and provider not in ("unknown", "merged") and spf_provider:
        score -= 15

    if provider not in ("unknown",):
        score += 10

    if entry.get("gateway"):
        pass  # gateway adds uncertainty, neutral

    if provider == "unknown":
        score = min(score, 25)

    return max(0, min(100, score))


def main():
    data_path = ROOT / "data.json"
    if not data_path.exists():
        print("Error: data.json not found")
        sys.exit(1)

    with open(data_path) as f:
        raw = json.load(f)

    munis = raw.get("municipalities", {})
    if isinstance(munis, list):
        munis = {m["bfs"]: m for m in munis}

    generated = raw.get("generated", raw.get("generated_at", ""))

    summary_munis = {}
    detail_munis = {}

    for bfs, m in munis.items():
        raw_provider = m.get("provider", "unknown")
        jurisdiction = PROVIDER_JURISDICTION.get(raw_provider, "unknown")
        confidence = _compute_confidence(m)

        # Summary: core fields + computed fields + has_mx flag
        summary = {k: m[k] for k in SUMMARY_FIELDS if k in m}
        summary["has_mx"] = len(m.get("mx", [])) > 0
        summary["jurisdiction"] = jurisdiction
        summary["confidence"] = confidence
        summary_munis[bfs] = summary

        # Detail: popup-only fields
        detail = {k: m[k] for k in DETAIL_FIELDS if k in m}
        if detail:
            detail_munis[bfs] = detail

    # Write region-level aggregations (lightweight, loaded first)
    regions_out = ROOT / "data-regions.json"
    regions_data = build_region_data(munis, generated)
    with open(regions_out, "w") as f:
        json.dump(regions_data, f, separators=(",", ":"), ensure_ascii=False)
    print(f"  data-regions.json: {regions_out.stat().st_size:,} bytes")

    # Write per-country drill-down files (summary + key detail fields)
    summary_dir = ROOT / "data" / "summary"
    summary_dir.mkdir(exist_ok=True)
    by_country: dict[str, list] = {}
    for bfs, m in munis.items():
        cc = m.get("country", "")
        if not cc:
            continue
        raw_provider = m.get("provider", "unknown")
        # Merge summary + selected detail fields
        entry = {k: m[k] for k in SUMMARY_FIELDS if k in m}
        entry["has_mx"] = len(m.get("mx", [])) > 0
        entry["jurisdiction"] = PROVIDER_JURISDICTION.get(raw_provider, "unknown")
        entry["confidence"] = _compute_confidence(m)
        # Add detail fields needed for drill-down
        for field in ("mx", "reason", "gateway", "spf", "autodiscover",
                      "dkim", "txt_verifications", "tenant", "smtp_software"):
            if m.get(field):
                entry[field] = m[field]
        by_country.setdefault(cc, []).append(entry)
    total_country_size = 0
    for cc, entries in by_country.items():
        cc_path = summary_dir / f"{cc.lower()}.json"
        with open(cc_path, "w") as f:
            json.dump(entries, f, separators=(",", ":"), ensure_ascii=False)
        total_country_size += cc_path.stat().st_size
    print(f"  data/summary/*.json: {len(by_country)} files, {total_country_size:,} bytes total")

    # Write summary
    summary_out = ROOT / "data-summary.json"
    summary_data = {
        "generated": generated,
        "municipalities": summary_munis,
    }
    with open(summary_out, "w") as f:
        json.dump(summary_data, f, separators=(",", ":"), ensure_ascii=False)
    print(f"  data-summary.json: {summary_out.stat().st_size:,} bytes")

    # Write detail
    detail_out = ROOT / "data-detail.json"
    with open(detail_out, "w") as f:
        json.dump(detail_munis, f, separators=(",", ":"), ensure_ascii=False)
    print(f"  data-detail.json:  {detail_out.stat().st_size:,} bytes")

    # Compare with original
    orig_size = data_path.stat().st_size
    new_size = summary_out.stat().st_size + detail_out.stat().st_size
    print(
        f"  Original data.json: {orig_size:,} bytes"
        f" -> {new_size:,} bytes ({new_size * 100 // orig_size}%)"
    )


if __name__ == "__main__":
    main()
