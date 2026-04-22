"""Classify email providers for Nordic administrative regions.
Reads data/regions_*.json and writes data/regions_classified.json."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from mail_sovereignty.classify import classify, classify_from_smtp_banner, detect_gateway
from mail_sovereignty.dns import (
    lookup_autodiscover,
    lookup_dkim,
    lookup_mx,
    lookup_tenant,
    lookup_txt,
    resolve_mx_asns,
    resolve_mx_cnames,
    resolve_mx_countries,
    resolve_spf_includes,
)
from mail_sovereignty.smtp import fetch_smtp_banner

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

SEED_FILES = {
    "DK": DATA_DIR / "regions_dk.json",
    "SE": DATA_DIR / "regions_se.json",
    "NO": DATA_DIR / "regions_no.json",
    "FI": DATA_DIR / "regions_fi.json",
    "GL": DATA_DIR / "regions_gl.json",
}


async def classify_domain(domain: str) -> dict:
    mx = await lookup_mx(domain)
    spf, txt_verifications = await lookup_txt(domain) if mx else (None, {})
    spf_resolved = await resolve_spf_includes(spf) if spf else ""
    mx_cnames = await resolve_mx_cnames(mx) if mx else {}
    mx_asns = await resolve_mx_asns(mx) if mx else set()
    mx_countries = await resolve_mx_countries(mx) if mx else set()
    autodiscover = await lookup_autodiscover(domain) if mx else {}
    dkim = await lookup_dkim(domain) if mx else {}
    gateway = detect_gateway(mx) if mx else None
    tenant = await lookup_tenant(domain) if mx and gateway else None

    provider, reason = classify(
        mx_records=mx or [],
        spf_record=spf,
        mx_cnames=mx_cnames,
        mx_asns=mx_asns,
        resolved_spf=spf_resolved,
        autodiscover=autodiscover,
        dkim=dkim,
        txt_verifications=txt_verifications,
        tenant=tenant,
    )

    # For self-hosted results, probe SMTP banner to detect Exchange on-prem
    smtp_banner = ""
    smtp_software = ""
    if provider == "independent" and mx:
        primary_mx = mx[0]
        result = await fetch_smtp_banner(primary_mx)
        smtp_banner = result.get("banner", "")
        ehlo = result.get("ehlo", "")
        if smtp_banner:
            banner_provider = classify_from_smtp_banner(smtp_banner, ehlo)
            if banner_provider:
                provider = banner_provider
                reason = f"SMTP banner on {primary_mx} reveals {banner_provider}"
            # Extract software hint from banner (e.g. "Microsoft ESMTP MAIL Service")
            smtp_software = smtp_banner.split("220 ")[-1].strip() if "220" in smtp_banner else smtp_banner

    return {
        "mx": mx or [],
        "spf": spf,
        "mx_countries": sorted(mx_countries),
        "gateway": gateway,
        "tenant": tenant,
        "provider": provider,
        "reason": reason,
        "smtp_banner": smtp_banner,
        "smtp_software": smtp_software,
    }


async def run() -> None:
    all_regions = []
    for cc, path in SEED_FILES.items():
        seed = json.loads(path.read_text())
        print(f"\n{cc} ({len(seed)} regions):")
        for region in seed:
            domain = region["domain"]
            print(f"  {region['full_name']} ({domain}) ...", end=" ", flush=True)
            dns = await classify_domain(domain)
            print(f"{dns['provider']}  [{dns['reason']}]")
            all_regions.append({**region, **dns, "verified": True})

    out = DATA_DIR / "regions_classified.json"
    out.write_text(
        json.dumps(
            {"generated": datetime.now(UTC).isoformat(), "regions": all_regions},
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nWrote {len(all_regions)} regions to {out}")


if __name__ == "__main__":
    asyncio.run(run())
