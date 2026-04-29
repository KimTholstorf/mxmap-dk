#!/usr/bin/env python3
"""Split companies-ca-data.json into summary + detail files for the frontend.

Summary  → companies-ca-summary.json  (map/list rendering, stats)
Detail   → companies-ca-detail.json   (popup cert-chain details)

Usage:
    uv run python3 scripts/build_companies_ca_frontend.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SUMMARY_FIELDS = {
    "id", "index", "ticker", "name", "domain", "sector",
    "hq_country", "hq_municipality", "hq_municipality_id", "hq_lat", "hq_lng",
    "primary_ca", "ca_owner", "ca_country", "jurisdiction", "risk_level",
    "category", "confidence", "error", "error_category",
    "cert_mismatch", "shared_hosting",
}

DETAIL_FIELDS = {
    "cert_chain", "caa_records", "ct_issuers", "tls_version", "cert_expiry",
    "scanned_domain", "http_accessible", "shared_cert_fingerprint", "scan_timestamp",
}


def main() -> None:
    input_path = ROOT / "companies-ca-data.json"
    if not input_path.exists():
        print(f"ERROR: {input_path} not found. Run 'uv run python3 scripts/scan_companies_ca.py' first.")
        raise SystemExit(1)

    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    companies = data.get("companies", {})
    total = len(companies)

    summary_companies: dict = {}
    detail_companies: dict = {}

    for company_id, c in companies.items():
        summary_companies[company_id] = {k: v for k, v in c.items() if k in SUMMARY_FIELDS}
        detail_companies[company_id] = {k: v for k, v in c.items() if k in DETAIL_FIELDS}

    summary = {
        "generated": data.get("generated", ""),
        "total": total,
        "counts": data.get("counts", {}),
        "companies": summary_companies,
    }

    summary_path = ROOT / "companies-ca-summary.json"
    detail_path = ROOT / "companies-ca-detail.json"

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, separators=(",", ":"), ensure_ascii=False)

    with open(detail_path, "w", encoding="utf-8") as f:
        json.dump(detail_companies, f, separators=(",", ":"), ensure_ascii=False)

    summary_kb = summary_path.stat().st_size // 1024
    detail_kb = detail_path.stat().st_size // 1024
    original_kb = input_path.stat().st_size // 1024

    print(f"  companies-ca-summary.json: {summary_kb} KB")
    print(f"  companies-ca-detail.json:  {detail_kb} KB")
    print(f"  Original: {original_kb} KB → split: {summary_kb + detail_kb} KB")
    print(f"  {total} companies written")


if __name__ == "__main__":
    main()
