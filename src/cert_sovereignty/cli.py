"""CLI entry point: scan-certs

Reads municipalities + stock index companies from our data.json,
scans TLS certificates for each domain, writes ca-data.json.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from loguru import logger

from .log import setup_logging

ROOT = Path(__file__).parent.parent.parent  # project root


def scan_certs() -> None:
    """Scan TLS certificates for all Nordic municipalities + stock index companies.

    Reads:  data.json  (our MX pipeline output — provides id, name, country, domain)
    Writes: ca-data.json  (CA classification results keyed by municipality ID)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan TLS certificates for Nordic municipalities and companies"
    )
    parser.add_argument(
        "--input",
        default=str(ROOT / "data.json"),
        help="Input data.json from MX pipeline",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "ca-data.json"),
        help="Output ca-data.json",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=40,
        help="Concurrent TLS scans (default: 40)",
    )
    parser.add_argument(
        "--skip-ct",
        action="store_true",
        help="Skip Certificate Transparency log queries (faster, slightly less accurate)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="TLS connection timeout in seconds (default: 15)",
    )
    parser.add_argument(
        "--country",
        help="Scan only this country code (e.g. DK)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    async def _run() -> None:
        from .pipeline import build_ca_data, scan_many, write_ca_data

        input_path = Path(args.input)
        if not input_path.exists():
            logger.error("Input file not found: {}", input_path)
            sys.exit(1)

        with open(input_path, encoding="utf-8") as f:
            raw = json.load(f)

        municipalities_dict: dict = raw.get("municipalities", {})

        # Flatten to a list of entry dicts, preserving the BFS id
        entries: list[dict] = []
        for bfs_id, m in municipalities_dict.items():
            entry = {
                "id": bfs_id,
                "name": m.get("name", ""),
                "country": m.get("country", ""),
                "region": m.get("canton", m.get("region", "")),
                "domain": m.get("domain", ""),
            }
            entries.append(entry)

        # Filter by country if requested
        if args.country:
            entries = [e for e in entries if e.get("country") == args.country]
            logger.info("Filtered to {} {} entries", len(entries), args.country)

        # Deduplicate domains (multiple municipalities may share a domain)
        domain_to_entries: dict[str, list[dict]] = {}
        no_domain: list[dict] = []
        for entry in entries:
            domain = entry.get("domain", "").strip()
            if domain:
                domain_to_entries.setdefault(domain, []).append(entry)
            else:
                no_domain.append(entry)

        unique_domains = list(domain_to_entries.keys())
        logger.info(
            "Scanning {} unique domains from {} entries ({} have no domain)",
            len(unique_domains),
            len(entries),
            len(no_domain),
        )
        logger.info(
            "Settings: concurrency={} timeout={}s ct={}",
            args.concurrency,
            args.timeout,
            "disabled" if args.skip_ct else "enabled",
        )

        results = await scan_many(
            unique_domains,
            concurrency=args.concurrency,
            skip_ct=args.skip_ct,
            tls_timeout=args.timeout,
        )

        data = build_ca_data(entries, results)
        write_ca_data(data, Path(args.output))

        # Print summary
        counts = data.get("counts", {})
        total = data.get("total", 0)
        print(f"\n{'=' * 50}")
        print(f"CA SCAN RESULTS: {total} entries")
        for cat, count in sorted(counts.items(), key=lambda x: -x[1]):
            pct = count / max(total, 1) * 100
            bar = "█" * int(pct / 2)
            print(f"  {cat:20s}: {count:4d}  ({pct:5.1f}%)  {bar}")
        print("=" * 50)

    asyncio.run(_run())
