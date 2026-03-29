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
    # Albania: Q1781058 (bashkia) = 61 post-2015 municipalities
    "AL": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q1781058 .
  ?item wdt:P17 wd:Q222 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sq" }
}
ORDER BY ?itemLabel
""",
    # Kosovo: Q2989682 (municipality of Kosovo) = 35-38
    "XK": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q2989682 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sq,sr" }
}
ORDER BY ?itemLabel
""",
    # Montenegro: Q838549 (municipality of Montenegro) = 25
    "ME": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q838549 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sr,cnr" }
}
ORDER BY ?itemLabel
""",
    # Bosnia: Q17268368 (FBiH municipality) + Q57315116 (RS municipality) + Q102104752 (city)
    "BA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  VALUES ?type { wd:Q17268368 wd:Q57315116 wd:Q102104752 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q225 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,bs,sr,hr" }
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
    with urllib.request.urlopen(req, timeout=300) as resp:
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


DE_STATES = {
    "01": ("Q1194", "Schleswig-Holstein"),
    "02": ("Q1055", "Hamburg"),
    "03": ("Q1197", "Niedersachsen"),
    "04": ("Q24879", "Bremen"),
    "05": ("Q1198", "Nordrhein-Westfalen"),
    "06": ("Q1199", "Hessen"),
    "07": ("Q1200", "Rheinland-Pfalz"),
    "08": ("Q985", "Baden-Württemberg"),
    "09": ("Q980", "Bayern"),
    "10": ("Q1201", "Saarland"),
    "11": ("Q64", "Berlin"),
    "12": ("Q1208", "Brandenburg"),
    "13": ("Q1196", "Mecklenburg-Vorpommern"),
    "14": ("Q1202", "Sachsen"),
    "15": ("Q1206", "Sachsen-Anhalt"),
    "16": ("Q1205", "Thüringen"),
}


def de_gemeinde_query(state_code: str) -> str:
    """SPARQL query for DE Gemeinden in a Bundesland.

    Uses Q262166 (Gemeinde in Germany) and P439 (AGS code).
    Filters by AGS prefix (2-digit state code) instead of P131+ traversal
    to avoid Wikidata timeouts.
    """
    return f"""
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?ags WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q262166 .
  ?item wdt:P439 ?ags .
  FILTER(STRSTARTS(?ags, "{state_code}"))
  FILTER NOT EXISTS {{ ?item wdt:P576 ?dissolved }}
  OPTIONAL {{ ?item wdt:P856 ?website }}
  OPTIONAL {{ ?item wdt:P402 ?osmId }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "de,en" }}
}}
ORDER BY ?ags
"""


def fetch_de_gemeinden():
    """Fetch all DE Gemeinden per Bundesland."""
    all_entries = []
    for state_code, (qid, state_name) in sorted(DE_STATES.items()):
        print(f"\n  Fetching {state_name} ({state_code})...")
        query = de_gemeinde_query(state_code)
        try:
            results = sparql_query(query)
            print(f"    Got {len(results)} raw results")
        except Exception as e:
            print(f"    ERROR: {e}")
            time.sleep(10)
            continue

        seen = set()
        for r in results:
            qid_item = r["item"]["value"].split("/")[-1]
            if qid_item in seen:
                continue
            seen.add(qid_item)

            name = r.get("itemLabel", {}).get("value", "")
            if not name or name.startswith("Q"):
                continue

            ags = r.get("ags", {}).get("value", "")
            website = r.get("website", {}).get("value", "")
            osm_id = r.get("osmId", {}).get("value", "")

            # AGS is 8-digit code; ID format: DE-XXXXXXXX
            muni_id = f"DE-{ags}" if ags else f"DE-{state_code}Q{qid_item}"

            entry = {
                "id": muni_id,
                "name": name,
                "country": "DE",
                "region": state_name,
                "domain": extract_domain(website),
            }
            if osm_id:
                try:
                    entry["osm_relation_id"] = int(osm_id)
                except ValueError:
                    pass

            all_entries.append(entry)

        print(f"    {len(seen)} unique Gemeinden")
        time.sleep(5)  # Rate limit

    # Sort by ID
    all_entries.sort(key=lambda e: e["id"])
    return all_entries


def main():
    countries = sys.argv[1:] if len(sys.argv) > 1 else list(QUERIES.keys())

    for cc in countries:
        cc = cc.upper()

        # Special handling for DE (per-state fetching)
        if cc == "DE":
            print(f"\n{'='*50}")
            print(f"Fetching DE Gemeinden (per Bundesland)...")
            entries = fetch_de_gemeinden()
            print(f"\n  Total: {len(entries)} DE Gemeinden")
            with_domain = sum(1 for e in entries if e["domain"])
            with_osm = sum(1 for e in entries if e.get("osm_relation_id"))
            print(f"  {with_domain} with domains, {with_osm} with OSM IDs")
            path = DATA / "municipalities_de.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(entries, f, ensure_ascii=False, indent=2)
            print(f"  Written to {path}")
            continue

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


# Additional countries
QUERIES.update({
    "RS": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q783930 .
  ?item wdt:P17 wd:Q403 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sr" }
}
ORDER BY ?itemLabel
""",
    "MK": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q646793 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mk" }
}
ORDER BY ?itemLabel
""",
    "UA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q1267632 .
  ?item wdt:P17 wd:Q212 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,uk" }
}
ORDER BY ?itemLabel
""",
    "MD": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q15068450 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ro,ru" }
}
ORDER BY ?itemLabel
""",
    "LI": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q203300 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de" }
}
ORDER BY ?itemLabel
""",
    "SM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P17 wd:Q238 .
  ?item wdt:P31/wdt:P279* wd:Q15284 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,it" }
}
ORDER BY ?itemLabel
""",
    "GE": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q2655841 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ka" }
}
ORDER BY ?itemLabel
""",
    "AM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q20724701 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,hy" }
}
ORDER BY ?itemLabel
""",
    "AZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q13417250 .
  ?item wdt:P17 wd:Q227 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,az" }
}
ORDER BY ?itemLabel
""",
    "BY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q2043199 .
  ?item wdt:P17 wd:Q184 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,be,ru" }
}
ORDER BY ?itemLabel
""",
    "TR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q48336 .
  ?item wdt:P17 wd:Q43 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,tr" }
}
ORDER BY ?itemLabel
""",
    # Australia: Q1867183 (local government area of Australia) — ~537 LGAs
    "AU": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1867183 .
  ?item wdt:P17 wd:Q408 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # New Zealand: Q941036 (territorial authority of NZ) — 67 councils
    "NZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q941036 .
  ?item wdt:P17 wd:Q664 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mi" }
}
ORDER BY ?itemLabel
""",
    # Indonesia: Q3191695 (regency) + Q3199141 (city) — ~521 kabupaten/kota
    "ID": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  VALUES ?type { wd:Q3191695 wd:Q3199141 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q252 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,id" }
}
ORDER BY ?itemLabel
""",
    # Papua New Guinea: Q1053630 (province) + Q14942893 (district) — ~112
    "PG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  VALUES ?type { wd:Q1053630 wd:Q14942893 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q691 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Malaysia: Q1994931 (district) — ~161 districts
    "MY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q1994931 .
  ?item wdt:P17 wd:Q833 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ms" }
}
ORDER BY ?itemLabel
""",
    # Thailand: Q50198 (province) — 76 provinces + Bangkok
    "TH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q50198 .
  ?item wdt:P17 wd:Q869 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,th" }
}
ORDER BY ?itemLabel
""",
    # Cambodia: Q7252589 (province) — 25 provinces
    "KH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q7252589 .
  ?item wdt:P17 wd:Q424 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,km" }
}
ORDER BY ?itemLabel
""",
    # Philippines: Q24764 (municipality) + Q29946056 (highly urbanized city)
    #   + Q106078286 (component city) — ~1637 total
    "PH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  VALUES ?type { wd:Q24764 wd:Q29946056 wd:Q106078286 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q928 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,tl" }
}
ORDER BY ?itemLabel
""",
    # Vietnam: Q2824648 (province) + Q1381899 (centrally-controlled city) — ~63
    "VN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  VALUES ?type { wd:Q2824648 wd:Q1381899 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q881 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,vi" }
}
ORDER BY ?itemLabel
""",
    # Myanmar: Q17315624 (state) + Q15072454 (region) — 14 states/regions + Naypyidaw
    "MM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  VALUES ?type { wd:Q17315624 wd:Q15072454 wd:Q15971681 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q836 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,my" }
}
ORDER BY ?itemLabel
""",
    # Oman: Q3250615 (wilayat) — ~63 wilayats
    "OM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q3250615 .
  ?item wdt:P17 wd:Q842 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # UAE: Q19833031 (emirate) — 7 emirates
    "AE": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q19833031 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Qatar: Q685320 (municipality) — 8 municipalities
    "QA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q685320 .
  ?item wdt:P17 wd:Q846 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Bahrain: Q867606 (governorate) — 4 governorates
    "BH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q867606 .
  ?item wdt:P17 wd:Q398 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Fiji: Q3064474 (province) — 14 provinces
    "FJ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q3064474 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Samoa: Q1070167 (district) — 11 districts
    "WS": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q1070167 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sm" }
}
ORDER BY ?itemLabel
""",
    # Vanuatu: Q847299 (province) — 6 provinces
    "VU": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q847299 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,bi" }
}
ORDER BY ?itemLabel
""",
    # Tonga: Q20740204 (division) — 5 divisions
    "TO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q20740204 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,to" }
}
ORDER BY ?itemLabel
""",
    # Nauru: Q319796 (district) — 14 districts
    "NR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q319796 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Palau: Q1044181 (state) — 16 states
    "PW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q1044181 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Japan: Q50337 (prefecture) — 47 prefectures
    "JP": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel WHERE {
  ?item wdt:P31 wd:Q50337 .
  ?item wdt:P17 wd:Q17 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ja" }
}
ORDER BY ?itemLabel
""",
})


if __name__ == "__main__":
    main()
