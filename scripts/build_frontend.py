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

    # Write summary
    summary_out = ROOT / "data-summary.json"
    summary_data = {
        "generated": raw.get("generated", raw.get("generated_at", "")),
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
