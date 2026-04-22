"""Classify email providers for OMXC20 companies using the same DNS pipeline
as the municipality classifier. Reads data/omxc20.json and writes
data/omxc20_classified.json."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from mail_sovereignty.classify import classify, detect_gateway
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

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


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

    return {
        "mx": mx or [],
        "spf": spf,
        "mx_countries": sorted(mx_countries),
        "gateway": gateway,
        "tenant": tenant,
        "provider": provider,
        "reason": reason,
    }


async def run() -> None:
    seed = json.loads((DATA_DIR / "omxc20.json").read_text())
    results = []

    for company in seed:
        domain = company["domain"]
        print(f"  {company['name']} ({domain}) ...", end=" ", flush=True)
        dns = await classify_domain(domain)
        print(f"{dns['provider']}  [{dns['reason']}]")
        results.append({**company, **dns, "verified": True})

    out = DATA_DIR / "omxc20_classified.json"
    out.write_text(
        json.dumps(
            {"generated": datetime.now(UTC).isoformat(), "companies": results},
            indent=2,
            ensure_ascii=False,
        )
    )
    print(f"\nWrote {len(results)} companies to {out}")


if __name__ == "__main__":
    asyncio.run(run())
