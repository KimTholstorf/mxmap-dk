import asyncio
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from mail_sovereignty.classify import classify, detect_gateway
from mail_sovereignty.constants import CONCURRENCY
from mail_sovereignty.dns import (
    lookup_autodiscover,
    lookup_dkim,
    lookup_mx,
    lookup_spf,
    resolve_mx_asns,
    resolve_mx_countries,
    resolve_mx_cnames,
    resolve_spf_includes,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

SEED_FILES = {
    "EE": "municipalities_ee.json",
    "LV": "municipalities_lv.json",
    "LT": "municipalities_lt.json",
    "FI": "municipalities_fi.json",
    "NO": "municipalities_no.json",
    "SE": "municipalities_se.json",
    "DE": "municipalities_de.json",
}


def url_to_domain(url: str | None) -> str | None:
    """Extract the base domain from a URL."""
    if not url:
        return None
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    return host if host else None


def guess_domains(name: str, country: str = "") -> list[str]:
    """Generate a small set of plausible domain guesses for a Baltic municipality."""
    raw = name.lower().strip()
    raw = re.sub(r"\s*\(.*?\)\s*", "", raw)

    # Remove common prefixes in municipality names
    for prefix in ["landkreis ", "kreis ", "stadt "]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]

    # Remove common suffixes in municipality names
    for suffix in [
        " vald", " linn",                             # Estonian
        " novads", " pilsēta", " valstspilsēta",      # Latvian
        " rajono savivaldybė", " miesto savivaldybė",  # Lithuanian
        " savivaldybė",
        " kaupunki", " kunta",                         # Finnish
        " kommune",                                     # Norwegian
        " kommun",                                      # Swedish
        " (kreisfreie stadt)",                              # German
    ]:
        if raw.endswith(suffix):
            raw = raw[: -len(suffix)]

    # Baltic diacritics transliteration
    translits = [
        ("ä", "a"), ("ö", "o"), ("ü", "u"), ("õ", "o"),  # Estonian
        ("š", "s"), ("ž", "z"), ("č", "c"),                # Shared
        ("ā", "a"), ("ē", "e"), ("ī", "i"), ("ū", "u"),  # Latvian
        ("ķ", "k"), ("ļ", "l"), ("ņ", "n"), ("ģ", "g"),
        ("ė", "e"), ("į", "i"), ("ų", "u"), ("ū", "u"),  # Lithuanian
        ("å", "a"),                                          # Finnish/Nordic
        ("ø", "o"), ("æ", "ae"),                                 # Norwegian
    ]
    clean = raw
    for a, b in translits:
        clean = clean.replace(a, b)

    def slugify(s):
        s = re.sub(r"['\u2019`]", "", s)
        s = re.sub(r"[^a-z0-9]+", "-", s)
        return s.strip("-")

    slugs = {slugify(clean), slugify(raw)} - {""}

    # German umlaut expansion (ä→ae, ö→oe, ü→ue, ß→ss)
    if country == "DE" or not country:
        german_translits = [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")]
        de_clean = raw
        for a, b in german_translits:
            de_clean = de_clean.replace(a, b)
        de_slug = slugify(de_clean)
        if de_slug:
            slugs.add(de_slug)

    # Determine TLDs based on country
    tld_map = {"EE": [".ee"], "LV": [".lv"], "LT": [".lt"], "FI": [".fi"], "NO": [".no", ".kommune.no"], "SE": [".se"], "DE": [".de"]}
    tlds = tld_map.get(country, [".ee", ".lv", ".lt", ".fi", ".no", ".se", ".de"])

    candidates = set()
    for slug in slugs:
        for tld in tlds:
            candidates.add(f"{slug}{tld}")
    return sorted(candidates)


def load_seed_data() -> dict[str, dict[str, str]]:
    """Load Baltic municipalities from curated seed JSON files."""
    print("Loading Baltic municipalities from seed data...")
    municipalities = {}

    for country_code, filename in SEED_FILES.items():
        path = DATA_DIR / filename
        if not path.exists():
            print(f"  WARNING: {path} not found, skipping {country_code}")
            continue
        with open(path, encoding="utf-8") as f:
            entries = json.load(f)

        for entry in entries:
            muni_id = entry["id"]
            municipalities[muni_id] = {
                "bfs": muni_id,  # reuse "bfs" field as generic municipality ID
                "name": entry["name"],
                "canton": entry.get("region", ""),  # reuse "canton" field for region
                "country": entry.get("country", country_code),
                "website": entry.get("domain", ""),
                "osm_relation_id": entry.get("osm_relation_id"),
            }
        print(f"  {country_code}: {len(entries)} municipalities")

    # Apply overrides
    overrides_path = DATA_DIR / "overrides.json"
    if overrides_path.exists():
        with open(overrides_path, encoding="utf-8") as f:
            overrides = json.load(f)
        for muni_id, override in overrides.items():
            if muni_id in municipalities:
                municipalities[muni_id].update(override)

    print(
        f"  Total: {len(municipalities)} municipalities, "
        f"{sum(1 for m in municipalities.values() if m['website'])} with domains"
    )
    return municipalities


async def scan_municipality(
    m: dict[str, str], semaphore: asyncio.Semaphore
) -> dict[str, Any]:
    """Scan a single municipality for email provider info."""
    async with semaphore:
        domain = url_to_domain(m.get("website", ""))
        mx, spf = [], ""

        if domain:
            mx = await lookup_mx(domain)
            if mx:
                spf = await lookup_spf(domain)

        if not mx:
            country = m.get("country", "")
            for guess in guess_domains(m["name"], country):
                if guess == domain:
                    continue
                mx = await lookup_mx(guess)
                if mx:
                    domain = guess
                    spf = await lookup_spf(guess)
                    break

        spf_resolved = await resolve_spf_includes(spf) if spf else ""
        mx_cnames = await resolve_mx_cnames(mx) if mx else {}
        mx_asns = await resolve_mx_asns(mx) if mx else set()
        mx_countries = await resolve_mx_countries(mx) if mx else set()
        autodiscover = await lookup_autodiscover(domain) if domain else {}
        dkim = await lookup_dkim(domain) if domain else {}
        provider, reason = classify(
            mx,
            spf,
            mx_cnames=mx_cnames,
            mx_asns=mx_asns or None,
            resolved_spf=spf_resolved or None,
            autodiscover=autodiscover or None,
            dkim=dkim or None,
        )
        gateway = detect_gateway(mx) if mx else None

        entry: dict[str, Any] = {
            "bfs": m["bfs"],
            "name": m["name"],
            "canton": m.get("canton", ""),
            "country": m.get("country", ""),
            "domain": domain or "",
            "mx": mx,
            "spf": spf,
            "provider": provider,
            "reason": reason,
        }
        if m.get("osm_relation_id"):
            entry["osm_relation_id"] = m["osm_relation_id"]
        if spf_resolved and spf_resolved != spf:
            entry["spf_resolved"] = spf_resolved
        if gateway:
            entry["gateway"] = gateway
        if mx_cnames:
            entry["mx_cnames"] = mx_cnames
        if mx_asns:
            entry["mx_asns"] = sorted(mx_asns)
        if mx_countries:
            entry["mx_countries"] = sorted(mx_countries)
        if autodiscover:
            entry["autodiscover"] = autodiscover
        if dkim:
            entry["dkim"] = dkim
        return entry


async def run(output_path: Path) -> None:
    municipalities = load_seed_data()
    total = len(municipalities)

    print(f"\nScanning {total} municipalities for MX/SPF records...")
    print("(This takes a few minutes with async lookups)\n")

    semaphore = asyncio.Semaphore(CONCURRENCY)
    tasks = [scan_municipality(m, semaphore) for m in municipalities.values()]

    results = {}
    done = 0
    for coro in asyncio.as_completed(tasks):
        result = await coro
        results[result["bfs"]] = result
        done += 1
        if done % 50 == 0 or done == total:
            counts = {}
            for r in results.values():
                counts[r["provider"]] = counts.get(r["provider"], 0) + 1
            print(
                f"  [{done:4d}/{total}]  "
                f"MS={counts.get('microsoft', 0)}  "
                f"Google={counts.get('google', 0)}  "
                f"Zone={counts.get('zone', 0)}  "
                f"Telia={counts.get('telia', 0)}  "
                f"TET={counts.get('tet', 0)}  "
                f"AWS={counts.get('aws', 0)}  "
                f"ISP={counts.get('local-isp', 0)}  "
                f"Indep={counts.get('independent', 0)}  "
                f"?={counts.get('unknown', 0)}"
            )

    counts = {}
    for r in results.values():
        counts[r["provider"]] = counts.get(r["provider"], 0) + 1

    print(f"\n{'=' * 50}")
    print(f"RESULTS: {len(results)} municipalities scanned")
    print(f"  Microsoft/Azure : {counts.get('microsoft', 0):>5}")
    print(f"  Google/GCP      : {counts.get('google', 0):>5}")
    print(f"  Zone.eu         : {counts.get('zone', 0):>5}")
    print(f"  Telia           : {counts.get('telia', 0):>5}")
    print(f"  TET             : {counts.get('tet', 0):>5}")
    print(f"  AWS             : {counts.get('aws', 0):>5}")
    print(f"  Local ISP       : {counts.get('local-isp', 0):>5}")
    print(f"  Independent     : {counts.get('independent', 0):>5}")
    print(f"  Unknown/No MX   : {counts.get('unknown', 0):>5}")
    print(f"{'=' * 50}")

    sorted_counts = dict(sorted(counts.items()))
    sorted_munis = dict(sorted(results.items()))

    output = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": len(results),
        "counts": sorted_counts,
        "municipalities": sorted_munis,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    size_kb = len(json.dumps(output)) / 1024
    print(f"\nWritten {output_path} ({size_kb:.0f} KB)")
