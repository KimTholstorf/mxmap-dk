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
    "osm_relation_id",
    "mx_countries",
    "gateway",
    "isp_name",
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


PROVIDER_DISPLAY = {
    "microsoft": "Microsoft",
    "google": "Google",
    "aws": "AWS",
    "telia": "Local Provider",
    "tet": "Local Provider",
    "zone": "Local Provider",
    "elkdata": "Local Provider",
    "local-isp": "Local Provider",
    "zoho": "Local Provider",
    "independent": "Self-hosted",
    "unknown": "Unknown",
}

COLORS = {
    "Microsoft": "#E83838",
    "Google": "#FFAB96",
    "AWS": "#FF7A5C",
    "Local Provider": "#10B898",
    "Self-hosted": "#0E9680",
    "Unknown": "#BFBFBF",
}

US_PROVIDERS = {"Microsoft", "Google", "AWS"}


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
    """Build pre-computed region-level aggregations."""
    countries: dict[str, dict] = {}

    for bfs, m in munis.items():
        cc = m.get("country", "")
        region = m.get("canton", "") or ""
        raw_provider = m.get("provider", "unknown")
        provider = PROVIDER_DISPLAY.get(raw_provider, raw_provider)
        has_gateway = bool(
            m.get("gateway")
            and cc in (m.get("mx_countries") or [])
            and provider in US_PROVIDERS
        )

        if cc not in countries:
            countries[cc] = {
                "total": 0,
                "providers": {},
                "gateway_count": 0,
                "regions": {},
            }
        cd = countries[cc]
        cd["total"] += 1
        cd["providers"][provider] = cd["providers"].get(provider, 0) + 1
        if has_gateway:
            cd["gateway_count"] += 1

        if region not in cd["regions"]:
            cd["regions"][region] = {
                "count": 0,
                "providers": {},
                "gateway_count": 0,
            }
        rd = cd["regions"][region]
        rd["count"] += 1
        rd["providers"][provider] = rd["providers"].get(provider, 0) + 1
        if has_gateway:
            rd["gateway_count"] += 1

    # Compute dominant provider and blended color per country and region
    for cc, cd in countries.items():
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
            rd["blendedColor"] = blend_provider_colors(rd["providers"], rd["count"])

    return {"generated": generated, "total": len(munis), "countries": countries}


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
        # Summary: core fields + has_mx flag
        summary = {k: m[k] for k in SUMMARY_FIELDS if k in m}
        summary["has_mx"] = len(m.get("mx", [])) > 0
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
