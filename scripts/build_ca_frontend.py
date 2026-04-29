#!/usr/bin/env python3
"""Split ca-data.json into ca-data-summary.json and ca-data-detail.json.

Summary fields (needed for map coloring, legend, stats):
  id, name, country, region, domain, primary_ca, ca_owner, ca_country,
  jurisdiction, risk_level, category, confidence, error, error_category,
  cert_mismatch, shared_hosting

Detail fields (popup only):
  cert_chain, caa_records, ct_issuers, tls_version, cert_expiry,
  scanned_domain, http_accessible, shared_cert_fingerprint, scan_timestamp
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent.parent

SUMMARY_FIELDS = {
    "id",
    "name",
    "country",
    "region",
    "domain",
    "primary_ca",
    "ca_owner",
    "ca_country",
    "jurisdiction",
    "risk_level",
    "category",
    "confidence",
    "error",
    "error_category",
    "cert_mismatch",
    "shared_hosting",
}

DETAIL_FIELDS = {
    "cert_chain",
    "caa_records",
    "ct_issuers",
    "tls_version",
    "cert_expiry",
    "scanned_domain",
    "http_accessible",
    "shared_cert_fingerprint",
    "scan_timestamp",
}


def main() -> None:
    ca_data_path = ROOT / "ca-data.json"
    if not ca_data_path.exists():
        print(f"ERROR: {ca_data_path} not found. Run 'uv run scan-certs' first.")
        raise SystemExit(1)

    with open(ca_data_path, encoding="utf-8") as f:
        ca_data = json.load(f)

    municipalities = ca_data.get("municipalities", {})
    total = len(municipalities)

    summary_munis: dict = {}
    detail_munis: dict = {}

    for bfs_id, m in municipalities.items():
        summary_munis[bfs_id] = {k: v for k, v in m.items() if k in SUMMARY_FIELDS}
        detail_munis[bfs_id] = {k: v for k, v in m.items() if k in DETAIL_FIELDS}

    summary = {
        "generated": ca_data.get("generated", ""),
        "total": total,
        "counts": ca_data.get("counts", {}),
        "municipalities": summary_munis,
    }

    detail = detail_munis

    summary_path = ROOT / "ca-data-summary.json"
    detail_path = ROOT / "ca-data-detail.json"

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, separators=(",", ":"), ensure_ascii=False)

    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(detail, f, separators=(",", ":"), ensure_ascii=False)

    summary_kb = summary_path.stat().st_size // 1024
    detail_kb = detail_path.stat().st_size // 1024
    original_kb = ca_data_path.stat().st_size // 1024

    print(f"  ca-data-summary.json: {summary_kb:,} KB")
    print(f"  ca-data-detail.json:  {detail_kb:,} KB")
    print(f"  Original ca-data.json: {original_kb:,} KB -> {summary_kb + detail_kb:,} KB")


if __name__ == "__main__":
    main()
