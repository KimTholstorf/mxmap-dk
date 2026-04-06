#!/usr/bin/env python3
"""Domain ownership validation orchestrator.

Runs Layer 1 (heuristics) + Layer 2 (metadata fetch) and produces a
combined analysis-ready report for Claude Code to review in-conversation.

Usage:
    python3 scripts/validate_domains.py EE LV LT     # Specific countries
    python3 scripts/validate_domains.py --region baltics
    python3 scripts/validate_domains.py --region dach
    python3 scripts/validate_domains.py --region nordics
    python3 scripts/validate_domains.py --list-regions
    python3 scripts/validate_domains.py --status       # Show progress

Writes: data/domain_validation/{cc}_report.json  (analysis-ready)
        data/domain_validation/progress.json      (tracking)
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VALIDATION_DIR = ROOT / "data" / "domain_validation"
PROGRESS_FILE = VALIDATION_DIR / "progress.json"

# Region groups for systematic progress tracking
REGIONS = {
    "baltics": ["EE", "LV", "LT"],
    "nordics": ["NO", "SE", "FI", "DK", "IS"],
    "dach": ["DE", "AT", "LI", "LU"],
    "benelux": ["BE", "NL"],
    "british": ["GB", "IE"],
    "iberia": ["ES", "PT"],
    "france_med": ["FR", "IT", "GR", "CY", "MT"],
    "central_europe": ["CZ", "SK", "PL", "HU", "SI", "HR", "BA", "RS", "MK", "AL", "XK", "ME", "BG", "RO"],
    "eastern": ["UA", "BY", "GE", "AM", "AZ", "MD", "RU"],
    "latam": ["BR", "MX", "AR", "CO", "PE", "CL", "VE", "EC", "BO", "PY", "UY", "CR", "PA", "HN", "SV", "NI", "GT", "CU", "DO", "HT"],
    "africa": ["NG", "ZA", "GH", "RW", "DZ", "MA", "TN", "CM", "BF", "SN", "TZ", "KE", "ET", "UG"],
    "asia_pacific": ["AU", "NZ", "PH", "ID", "SG", "MY", "KR", "JP", "TH", "IN"],
}


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"countries": {}, "started": datetime.now(timezone.utc).isoformat()}


def save_progress(progress: dict):
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def show_status():
    progress = load_progress()
    countries = progress.get("countries", {})

    print("Domain Validation Progress")
    print("=" * 60)

    for region_name, region_ccs in REGIONS.items():
        done = sum(1 for cc in region_ccs if countries.get(cc, {}).get("status") == "done")
        reviewed = sum(1 for cc in region_ccs if countries.get(cc, {}).get("reviewed"))
        total = len(region_ccs)

        status_parts = []
        for cc in region_ccs:
            cs = countries.get(cc, {})
            if cs.get("reviewed"):
                status_parts.append(f"{cc}✓")
            elif cs.get("status") == "done":
                status_parts.append(f"{cc}◐")
            else:
                status_parts.append(f"{cc}○")

        bar = f"[{done}/{total}]"
        print(f"  {region_name:18s} {bar:8s} {' '.join(status_parts)}")

    # Summary
    total_done = sum(1 for c in countries.values() if c.get("status") == "done")
    total_reviewed = sum(1 for c in countries.values() if c.get("reviewed"))
    total_countries = sum(len(v) for v in REGIONS.values())
    print(f"\n  Scanned: {total_done}/{total_countries}  Reviewed: {total_reviewed}/{total_countries}")


def list_regions():
    print("Available regions:")
    for name, ccs in REGIONS.items():
        print(f"  --region {name:18s} → {', '.join(ccs)}")


async def run_validation(countries: list[str], threshold: int = 20):
    """Run heuristics + metadata fetch for given countries."""
    # Import the other scripts
    sys.path.insert(0, str(ROOT / "scripts"))
    from domain_heuristics import run_heuristics
    from domain_llm_verify import process_country

    print(f"\n--- Layer 1: Heuristic scoring ---")
    run_heuristics(countries, threshold)

    print(f"\n--- Layer 2: Website metadata fetch ---")
    for cc in countries:
        await process_country(cc, threshold=0)

    # Build combined report per country
    print(f"\n--- Building analysis reports ---")
    progress = load_progress()

    for cc in countries:
        flagged_file = VALIDATION_DIR / f"{cc.lower()}_flagged.json"
        meta_file = VALIDATION_DIR / f"{cc.lower()}_metadata.json"

        if not flagged_file.exists():
            continue

        with open(flagged_file) as f:
            flagged_data = json.load(f)

        meta_entries = {}
        if meta_file.exists():
            with open(meta_file) as f:
                meta_data = json.load(f)
            for e in meta_data.get("entries", []):
                meta_entries[e["id"]] = e.get("website", {})

        # Build analysis-ready report
        report_entries = []
        for entry in flagged_data.get("flagged", []):
            mid = entry["id"]
            meta = meta_entries.get(mid, {})
            report_entries.append({
                "id": mid,
                "name": entry["name"],
                "domain": entry["domain"],
                "provider": entry.get("provider", ""),
                "risk_score": entry["risk_score"],
                "flags": entry["flags"],
                "similarity": entry.get("similarity", 0),
                "website_title": meta.get("title", ""),
                "website_description": meta.get("description", ""),
                "website_text": meta.get("text_snippet", "")[:300],
                "website_status": meta.get("status", "not_fetched"),
                "final_url": meta.get("final_url", ""),
            })

        report = {
            "country": cc,
            "generated": datetime.now(timezone.utc).isoformat(),
            "total_municipalities": flagged_data["total_municipalities"],
            "with_domain": flagged_data["with_domain"],
            "flagged_count": len(report_entries),
            "clean_count": len(flagged_data.get("clean", [])),
            "entries": report_entries,
        }

        report_file = VALIDATION_DIR / f"{cc.lower()}_report.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        progress["countries"][cc] = {
            "status": "done",
            "flagged": len(report_entries),
            "total": flagged_data["total_municipalities"],
            "date": datetime.now(timezone.utc).isoformat(),
            "reviewed": False,
        }
        print(f"  {cc}: {len(report_entries)} flagged → {report_file.name}")

    save_progress(progress)
    print(f"\nProgress saved. Run with --status to see overall progress.")
    print(f"Read *_report.json files in Claude Code for analysis.")


def main():
    args = sys.argv[1:]
    countries = []
    threshold = 20

    if not args:
        print(__doc__)
        sys.exit(0)

    i = 0
    while i < len(args):
        if args[i] == "--status":
            show_status()
            return
        elif args[i] == "--list-regions":
            list_regions()
            return
        elif args[i] == "--region" and i + 1 < len(args):
            region = args[i + 1].lower()
            if region not in REGIONS:
                print(f"Unknown region: {region}. Use --list-regions.")
                sys.exit(1)
            countries.extend(REGIONS[region])
            i += 2
        elif args[i] == "--threshold" and i + 1 < len(args):
            threshold = int(args[i + 1])
            i += 2
        else:
            countries.append(args[i].upper())
            i += 1

    if not countries:
        print("No countries specified.")
        sys.exit(1)

    asyncio.run(run_validation(countries, threshold))


if __name__ == "__main__":
    main()
