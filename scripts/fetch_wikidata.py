#!/usr/bin/env python3
"""Fetch municipality data from Wikidata for new EU countries.

Usage: python3 scripts/fetch_wikidata.py [CC ...]
"""

import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SPARQL_URL = "https://query.wikidata.org/sparql"

# Each country has a custom SPARQL query tailored to its admin structure.
# Classes found by querying items with P17=country AND P402 (OSM ID).
QUERIES = {
    # Malta: Q719592 (local council) + Q15631694 (admin entity) — 68 councils
    "MT": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  VALUES ?type { wd:Q719592 wd:Q15631694 }
  ?item wdt:P31/wdt:P279* ?type .
  ?item wdt:P17 wd:Q233 .
  FILTER NOT EXISTS { ?item wdt:P31 wd:Q6256 }
  FILTER NOT EXISTS { ?item wdt:P31 wd:Q7309296 }
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mt" }
}
ORDER BY ?itemLabel
""",
    # Cyprus: Q16739079 (municipalities of Cyprus Republic) = ~43
    "CY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q16739079 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,el" }
}
ORDER BY ?itemLabel
""",
    # Greece: Q1349648 (municipality of Greece) = 332 Kallikratis municipalities
    "GR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q1349648 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,el" }
}
ORDER BY ?itemLabel
""",
    # Croatia: Q57058 (municipality of Croatia, 429) + Q15105893 (town in Croatia, 122)
    "HR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  VALUES ?type { wd:Q57058 wd:Q15105893 }
  ?item wdt:P31 ?type .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,hr" }
}
ORDER BY ?itemLabel
""",
    # Hungary: Q1162835 (district of Hungary 2013-) = 175 districts
    # Using districts (járás) instead of 3000+ municipalities
    "HU": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q1162835 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,hu" }
}
ORDER BY ?itemLabel
""",
    # Romania: Q1776764 (county of Romania) = 41 counties + Bucharest
    "RO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q1776764 .
  ?item wdt:P17 wd:Q218 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ro" }
}
ORDER BY ?itemLabel
""",
}


def sparql_query(query: str) -> list[dict]:
    """Execute SPARQL query against Wikidata."""
    params = urllib.parse.urlencode({"query": query, "format": "json"})
    url = f"{SPARQL_URL}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "MXMap/1.0 (municipality email mapper)"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["results"]["bindings"]


def extract_domain(website: str) -> str:
    """Extract domain from website URL."""
    if not website:
        return ""
    from urllib.parse import urlparse
    parsed = urlparse(website if "://" in website else f"https://{website}")
    host = parsed.hostname or ""
    if host.startswith("www."):
        host = host[4:]
    return host


def process_results(results: list[dict], cc: str) -> list[dict]:
    """Convert SPARQL results to seed data format."""
    seen = set()
    entries = []
    idx = 1

    for r in results:
        qid = r["item"]["value"].split("/")[-1]
        if qid in seen:
            continue
        seen.add(qid)

        name = r.get("itemLabel", {}).get("value", "")
        if not name or name.startswith("Q"):
            continue

        website = r.get("website", {}).get("value", "")
        osm_id = r.get("osmId", {}).get("value", "")
        region = r.get("regionLabel", {}).get("value", "")

        entry = {
            "id": f"{cc}-{idx:03d}",
            "name": name,
            "country": cc,
            "region": region if region and not region.startswith("Q") else "",
            "domain": extract_domain(website),
        }
        if osm_id:
            try:
                entry["osm_relation_id"] = int(osm_id)
            except ValueError:
                pass

        entries.append(entry)
        idx += 1

    return entries


def main():
    countries = sys.argv[1:] if len(sys.argv) > 1 else list(QUERIES.keys())

    for cc in countries:
        cc = cc.upper()
        if cc not in QUERIES:
            print(f"Unknown country: {cc}")
            continue

        print(f"\n{'='*50}")
        print(f"Fetching {cc}...")

        try:
            results = sparql_query(QUERIES[cc])
            print(f"  Got {len(results)} raw results from Wikidata")
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        entries = process_results(results, cc)
        print(f"  Processed to {len(entries)} unique entries")

        with_domain = sum(1 for e in entries if e["domain"])
        with_osm = sum(1 for e in entries if e.get("osm_relation_id"))
        print(f"  {with_domain} with domains, {with_osm} with OSM IDs")

        for e in entries[:5]:
            print(f"    {e['id']}: {e['name']} ({e.get('domain') or '?'}) [osm:{e.get('osm_relation_id', '?')}]")
        if len(entries) > 5:
            print(f"    ... and {len(entries) - 5} more")

        path = DATA / f"municipalities_{cc.lower()}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        print(f"  Written to {path}")

        time.sleep(3)

    print("\nDone!")


if __name__ == "__main__":
    main()
