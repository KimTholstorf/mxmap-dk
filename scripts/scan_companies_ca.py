#!/usr/bin/env python3
"""Scan TLS certificates for Nordic stock-index companies.

Reads all *_classified.json files from data/, runs async TLS scan via the
cert_sovereignty pipeline, writes companies-ca-data.json at the repo root.

Usage:
    uv run python3 scripts/scan_companies_ca.py
    uv run python3 scripts/scan_companies_ca.py --skip-ct --timeout 20
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"

INDEX_FILES = {
    "OMXC20": DATA_DIR / "omxc20_classified.json",
    "OMXS30": DATA_DIR / "omxs30_classified.json",
    "OMXH25": DATA_DIR / "omxh25_classified.json",
    "OBX":    DATA_DIR / "obx_classified.json",
    "OMXI15": DATA_DIR / "omxi15_classified.json",
}

SUMMARY_FIELDS = {
    "id", "index", "ticker", "name", "domain", "sector",
    "hq_country", "hq_municipality", "hq_municipality_id", "hq_lat", "hq_lng",
    "primary_ca", "ca_owner", "ca_country", "jurisdiction", "risk_level",
    "category", "confidence", "error", "error_category", "cert_mismatch",
    "shared_hosting",
}

DETAIL_FIELDS = {
    "cert_chain", "caa_records", "ct_issuers", "tls_version", "cert_expiry",
    "scanned_domain", "http_accessible", "shared_cert_fingerprint", "scan_timestamp",
}


def load_all_companies() -> list[dict]:
    """Load and merge all index files into a flat list, deduplicating by domain."""
    seen_domains: set[str] = set()
    entries: list[dict] = []

    for index_name, path in INDEX_FILES.items():
        if not path.exists():
            logger.warning("Index file not found, skipping: {}", path)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for c in data.get("companies", []):
            domain = (c.get("domain") or "").strip()
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            # Derive HQ country from hq_municipality_id (e.g. "DK-159" → "DK")
            muni_id = c.get("hq_municipality_id", "")
            hq_country = muni_id.split("-")[0] if "-" in muni_id else ""
            entries.append({
                "id": f"{index_name}:{c.get('ticker', domain)}",
                "index": index_name,
                "ticker": c.get("ticker", ""),
                "name": c.get("name", domain),
                "domain": domain,
                "sector": c.get("sector", ""),
                "hq_country": hq_country,
                "hq_municipality": c.get("hq_municipality", ""),
                "hq_municipality_id": muni_id,
                "hq_lat": c.get("hq_lat"),
                "hq_lng": c.get("hq_lng"),
            })

    return entries


def build_companies_ca_data(
    entries: list[dict],
    results: dict,
) -> dict:
    """Build companies-ca-data.json from entries + scan results."""
    from cert_sovereignty.pipeline import (
        _detect_shared_hosting,
        _error_category,
        serialize_result,
    )
    from cert_sovereignty.pipeline import CATEGORY_MAP

    generated = datetime.now(UTC).isoformat()
    shared_info = _detect_shared_hosting(results)

    counts: dict[str, int] = {
        "us-controlled": 0, "eu-controlled": 0, "nordic": 0,
        "allied": 0, "http_only": 0, "unknown": 0,
    }

    companies_data: dict[str, dict] = {}

    for entry in entries:
        entry_id = entry["id"]
        domain = entry.get("domain", "")
        result = results.get(domain)

        if result:
            is_shared, fp = shared_info.get(domain, (False, ""))
            # serialize_result uses meta keys: id, name, country, region
            meta = {
                **entry,
                "country": entry.get("hq_country", ""),
                "region": entry.get("sector", ""),
            }
            serialized = serialize_result(result, meta, shared_hosting=is_shared, shared_cert_fp=fp)
            # Restore company-specific fields that serialize_result overwrites
            serialized["id"] = entry_id
            serialized["index"] = entry.get("index", "")
            serialized["ticker"] = entry.get("ticker", "")
            serialized["sector"] = entry.get("sector", "")
            serialized["hq_country"] = entry.get("hq_country", "")
            serialized["hq_municipality"] = entry.get("hq_municipality", "")
            serialized["hq_municipality_id"] = entry.get("hq_municipality_id", "")
            serialized["hq_lat"] = entry.get("hq_lat")
            serialized["hq_lng"] = entry.get("hq_lng")

            if result.error == "http_only":
                counts["http_only"] += 1
            else:
                cat = serialized.get("category", "unknown")
                counts[cat] = counts.get(cat, 0) + 1
        else:
            serialized = {
                **entry,
                "country": entry.get("hq_country", ""),
                "region": entry.get("sector", ""),
                "primary_ca": "Unknown",
                "jurisdiction": "other",
                "risk_level": "unknown",
                "category": "unknown",
                "confidence": 0,
                "error": "no_domain" if not domain else "not_scanned",
                "error_category": "no_domain" if not domain else "not_scanned",
            }
            counts["unknown"] += 1

        companies_data[entry_id] = serialized

    return {
        "generated": generated,
        "total": len(entries),
        "counts": counts,
        "companies": companies_data,
    }


async def run(args: argparse.Namespace) -> None:
    from cert_sovereignty.pipeline import scan_many
    from cert_sovereignty.log import setup_logging

    setup_logging(args.verbose)

    entries = load_all_companies()
    if not entries:
        logger.error("No company entries found — run classify scripts first")
        sys.exit(1)

    unique_domains = [e["domain"] for e in entries]
    logger.info(
        "Scanning {} company domains  concurrency={}  timeout={}s  ct={}",
        len(unique_domains), args.concurrency, args.timeout,
        "disabled" if args.skip_ct else "enabled",
    )

    results = await scan_many(
        unique_domains,
        concurrency=args.concurrency,
        skip_ct=args.skip_ct,
        tls_timeout=args.timeout,
    )

    data = build_companies_ca_data(entries, results)

    output_path = ROOT / "companies-ca-data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    size_kb = output_path.stat().st_size // 1024
    logger.info("Wrote {} ({} KB)", output_path, size_kb)

    counts = data.get("counts", {})
    total = data.get("total", 0)
    print(f"\n{'=' * 50}")
    print(f"CA SCAN — COMPANIES: {total} entries")
    for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
        pct = count / max(total, 1) * 100
        bar = "█" * int(pct / 2)
        print(f"  {cat:20s}: {count:4d}  ({pct:5.1f}%)  {bar}")
    print("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan TLS certificates for Nordic stock-index companies"
    )
    parser.add_argument("--concurrency", type=int, default=40)
    parser.add_argument("--skip-ct", action="store_true")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
