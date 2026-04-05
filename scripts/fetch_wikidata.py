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
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
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
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q16739079 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,el" }
}
ORDER BY ?itemLabel
""",
    # Greece: Q1349648 (municipality of Greece) = 332 Kallikratis municipalities
    "GR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1349648 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,el" }
}
ORDER BY ?itemLabel
""",
    # Croatia: Q57058 (municipality of Croatia, 429) + Q15105893 (town in Croatia, 122)
    "HR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q57058 wd:Q15105893 }
  ?item wdt:P31 ?type .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,hr" }
}
ORDER BY ?itemLabel
""",
    # Hungary: Q1162835 (district of Hungary 2013-) = 175 districts
    # Using districts (járás) instead of 3000+ municipalities
    "HU": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1162835 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,hu" }
}
ORDER BY ?itemLabel
""",
    # Albania: Q1781058 (bashkia) = 61 post-2015 municipalities
    "AL": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1781058 .
  ?item wdt:P17 wd:Q222 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sq" }
}
ORDER BY ?itemLabel
""",
    # Kosovo: Q2989682 (municipality of Kosovo) = 35-38
    "XK": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q2989682 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sq,sr" }
}
ORDER BY ?itemLabel
""",
    # Montenegro: Q838549 (municipality of Montenegro) = 25
    "ME": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q838549 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sr,cnr" }
}
ORDER BY ?itemLabel
""",
    # Bosnia: Q17268368 (FBiH municipality) + Q57315116 (RS municipality) + Q102104752 (city)
    "BA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q17268368 wd:Q57315116 wd:Q102104752 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q225 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,bs,sr,hr" }
}
ORDER BY ?itemLabel
""",
    # Romania: Q1776764 (county of Romania) = 41 counties + Bucharest
    "RO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1776764 .
  ?item wdt:P17 wd:Q218 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ro" }
}
ORDER BY ?itemLabel
""",
    # Spain: Q2074737 (municipality of Spain / municipio de España) — ~8,131
    "ES": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2074737 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Argentina: Q15284 (municipality) filtered to AR — ~1,554
    "AR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q15284 .
  ?item wdt:P17 wd:Q414 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Bolivia: Q1062710 (municipality of Bolivia) — ~340
    "BO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1062710 .
  ?item wdt:P17 wd:Q750 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Brazil: Q3184121 (municipality of Brazil) — ~5,570
    "BR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q3184121 .
  ?item wdt:P17 wd:Q155 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,pt" }
}
ORDER BY ?itemLabel
""",
    # Chile: Q1840161 (commune of Chile) — ~346
    "CL": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1840161 .
  ?item wdt:P17 wd:Q298 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Colombia: Q2555896 (municipality of Colombia) — ~1,100
    "CO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2555896 .
  ?item wdt:P17 wd:Q739 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Ecuador: Q1724017 (canton of Ecuador) — ~222
    "EC": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1724017 .
  ?item wdt:P17 wd:Q736 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Guyana: Q2087773 (region of Guyana) — ~10
    "GY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q2087773 .
  ?item wdt:P17 wd:Q734 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Peru: Q2179958 (district of Peru) — ~1,892
    "PE": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2179958 .
  ?item wdt:P17 wd:Q419 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Paraguay: Q917092 (municipality of Paraguay) — ~267
    "PY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q917092 .
  ?item wdt:P17 wd:Q733 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Suriname: Q1539014 (ressort of Suriname) — ~64
    "SR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1539014 .
  ?item wdt:P17 wd:Q730 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,nl" }
}
ORDER BY ?itemLabel
""",
    # Uruguay: Q56059 (department of Uruguay) — ~19
    "UY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q56059 .
  ?item wdt:P17 wd:Q77 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Venezuela: Q3327920 (municipality of Venezuela) — ~352
    "VE": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q3327920 .
  ?item wdt:P17 wd:Q717 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # ── Canada ───────────────────────────────────────────────────────
    # Canada: multiple municipal types — ~3500+
    "CA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type {
    wd:Q27676428 wd:Q3957 wd:Q27676416 wd:Q15210668 wd:Q55774719
    wd:Q532 wd:Q27676524 wd:Q3327874 wd:Q14762300 wd:Q55430416
    wd:Q515 wd:Q6644778 wd:Q6644696 wd:Q44529188 wd:Q14762205
    wd:Q60458065 wd:Q6641762 wd:Q6644759 wd:Q3327871 wd:Q27676420
    wd:Q27676422 wd:Q59341087 wd:Q204613
  }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q16 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # ── Central America ─────────────────────────────────────────────
    # Belize: Q765865 (district of Belize) — ~6
    "BZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q765865 .
  ?item wdt:P17 wd:Q242 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Guatemala: Q1872284 (municipality of Guatemala) — ~299
    "GT": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1872284 .
  ?item wdt:P17 wd:Q774 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Honduras: Q2602693 (municipality of Honduras) — ~298
    "HN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2602693 .
  ?item wdt:P17 wd:Q783 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # El Salvador: Q127499753 (district of El Salvador) — ~262
    "SV": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q127499753 .
  ?item wdt:P17 wd:Q792 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Nicaragua: Q318727 (municipality of Nicaragua) — ~153
    "NI": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q318727 .
  ?item wdt:P17 wd:Q811 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Costa Rica: Q953822 (canton of Costa Rica) — ~84
    "CR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q953822 .
  ?item wdt:P17 wd:Q800 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # Panama: Q3710488 (district of Panama) — ~75
    "PA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q3710488 .
  ?item wdt:P17 wd:Q804 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es" }
}
ORDER BY ?itemLabel
""",
    # ── Africa — North ──────────────────────────────────────────────
    # Algeria: Q2989398 (commune of Algeria) — ~569
    "DZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2989398 .
  ?item wdt:P17 wd:Q262 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar" }
}
ORDER BY ?itemLabel
""",
    # Egypt: Q204910 (governorate of Egypt) — ~27
    "EG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q204910 .
  ?item wdt:P17 wd:Q79 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Libya: Q16124843 (municipality of Libya) — ~70
    "LY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q16124843 .
  ?item wdt:P17 wd:Q1016 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Morocco: Q17318027 (rural commune) + Q5765944 (urban commune) — ~539+
    "MA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q17318027 wd:Q5765944 }
  ?item wdt:P31/wdt:P279* ?type .
  ?item wdt:P17 wd:Q1028 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar" }
}
ORDER BY ?itemLabel
""",
    # Tunisia: Q1184072 (delegation of Tunisia) — ~258
    "TN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1184072 .
  ?item wdt:P17 wd:Q948 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar" }
}
ORDER BY ?itemLabel
""",
    # Sudan: Q505830 (district of Sudan) — ~57
    "SD": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q505830 .
  ?item wdt:P17 wd:Q1049 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # ── Africa — West ───────────────────────────────────────────────
    # Benin: Q1780506 (commune of Benin) — ~67
    "BJ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1780506 .
  ?item wdt:P17 wd:Q962 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Burkina Faso: Q2566190 (department of Burkina Faso) — ~202
    "BF": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2566190 .
  ?item wdt:P17 wd:Q965 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Cape Verde: Q12712989 (concelho of Cape Verde) — ~22
    "CV": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q12712989 .
  ?item wdt:P17 wd:Q1011 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,pt" }
}
ORDER BY ?itemLabel
""",
    # Côte d'Ivoire: Q851830 (region of Côte d'Ivoire) — ~26
    "CI": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q851830 .
  ?item wdt:P17 wd:Q1008 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Gambia: Q1504917 (district of Gambia) — ~19
    "GM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1504917 .
  ?item wdt:P17 wd:Q1005 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Ghana: Q545769 (district of Ghana) — ~259
    "GH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q545769 .
  ?item wdt:P17 wd:Q117 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Guinea: Q1394653 (prefecture of Guinea) — ~17
    "GN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1394653 .
  ?item wdt:P17 wd:Q1006 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Guinea-Bissau: Q7444736 (sector of Guinea-Bissau) — ~20
    "GW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q7444736 .
  ?item wdt:P17 wd:Q1007 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,pt" }
}
ORDER BY ?itemLabel
""",
    # Liberia: Q2421044 (district of Liberia) — ~85
    "LR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2421044 .
  ?item wdt:P17 wd:Q1014 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Mali: Q2115792 (cercle of Mali) — ~46
    "ML": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2115792 .
  ?item wdt:P17 wd:Q912 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Mauritania: Q846327 (region of Mauritania) — ~13
    "MR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q846327 .
  ?item wdt:P17 wd:Q1025 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar" }
}
ORDER BY ?itemLabel
""",
    # Niger: Q2914501 (department of Niger) — ~36
    "NE": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2914501 .
  ?item wdt:P17 wd:Q1032 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Nigeria: Q1639634 (local government area of Nigeria) — ~787
    "NG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1639634 .
  ?item wdt:P17 wd:Q1033 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Senegal: Q2989649 (commune of Senegal) — ~164
    "SN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2989649 .
  ?item wdt:P17 wd:Q1041 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Sierra Leone: Q1298632 (district of Sierra Leone) — ~13
    "SL": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1298632 .
  ?item wdt:P17 wd:Q1044 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Togo: Q828485 (prefecture of Togo) — ~15
    "TG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q828485 .
  ?item wdt:P17 wd:Q945 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # ── Africa — Central ────────────────────────────────────────────
    # Cameroon: Q3076994 (commune of Cameroon) — ~147
    "CM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q3076994 .
  ?item wdt:P17 wd:Q1009 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Central African Republic: Q17176508 (commune of CAR) — ~109
    "CF": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q17176508 .
  ?item wdt:P17 wd:Q929 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Chad: Q640262 (province of Chad) — ~21
    "TD": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q640262 .
  ?item wdt:P17 wd:Q657 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar" }
}
ORDER BY ?itemLabel
""",
    # Congo (Brazzaville): Q1958165 (district of Congo) — ~93
    "CG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1958165 .
  ?item wdt:P17 wd:Q971 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # DR Congo: Q7703797 (territory of DR Congo) — ~146
    "CD": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q7703797 .
  ?item wdt:P17 wd:Q974 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Equatorial Guinea: Q867597 (province of Equatorial Guinea) — ~7
    "GQ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q867597 .
  ?item wdt:P17 wd:Q983 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,es,fr" }
}
ORDER BY ?itemLabel
""",
    # Gabon: Q653596 (province of Gabon) — ~9
    "GA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q653596 .
  ?item wdt:P17 wd:Q1000 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # São Tomé and Príncipe: Q911736 (district of STP) — ~7
    "ST": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q911736 .
  ?item wdt:P17 wd:Q1039 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,pt" }
}
ORDER BY ?itemLabel
""",
    # ── Africa — East ───────────────────────────────────────────────
    # Burundi: Q1577513 (commune of Burundi) — ~24
    "BI": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1577513 .
  ?item wdt:P17 wd:Q967 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Comoros: Q20732232 (autonomous island of the Comoros) — ~4
    "KM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q20732232 .
  ?item wdt:P17 wd:Q970 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar" }
}
ORDER BY ?itemLabel
""",
    # Djibouti: Q1202812 (region of Djibouti) — ~4
    "DJ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1202812 .
  ?item wdt:P17 wd:Q977 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,ar" }
}
ORDER BY ?itemLabel
""",
    # Eritrea: Q874223 (region of Eritrea) — ~6
    "ER": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q874223 .
  ?item wdt:P17 wd:Q986 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ti" }
}
ORDER BY ?itemLabel
""",
    # Ethiopia: Q219875 (zone of Ethiopia) — ~68
    "ET": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q219875 .
  ?item wdt:P17 wd:Q115 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,am" }
}
ORDER BY ?itemLabel
""",
    # Kenya: Q269218 (county of Kenya) — ~46
    "KE": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q269218 .
  ?item wdt:P17 wd:Q114 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sw" }
}
ORDER BY ?itemLabel
""",
    # Madagascar: Q971831 (region of Madagascar) — ~21
    "MG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q971831 .
  ?item wdt:P17 wd:Q1019 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,mg" }
}
ORDER BY ?itemLabel
""",
    # Malawi: Q1058387 (district of Malawi) — ~27
    "MW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1058387 .
  ?item wdt:P17 wd:Q1020 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Mauritius: Q2387050 (district of Mauritius) — ~9
    "MU": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2387050 .
  ?item wdt:P17 wd:Q1027 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Mozambique: Q2068214 (district of Mozambique) — ~151
    "MZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2068214 .
  ?item wdt:P17 wd:Q1029 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,pt" }
}
ORDER BY ?itemLabel
""",
    # Rwanda: Q3058029 (sector of Rwanda) — ~285
    "RW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q3058029 .
  ?item wdt:P17 wd:Q1037 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,rw" }
}
ORDER BY ?itemLabel
""",
    # Seychelles: Q1149621 (district of Seychelles) — ~24
    "SC": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1149621 .
  ?item wdt:P17 wd:Q1042 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr" }
}
ORDER BY ?itemLabel
""",
    # Somalia: Q18555638 (district of Somalia) — ~116
    "SO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q18555638 .
  ?item wdt:P17 wd:Q1045 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,so,ar" }
}
ORDER BY ?itemLabel
""",
    # South Sudan: Q279479 (county of South Sudan) — ~46
    "SS": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q279479 .
  ?item wdt:P17 wd:Q958 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Tanzania: Q2409750 (district of Tanzania) — ~186
    "TZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2409750 .
  ?item wdt:P17 wd:Q924 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sw" }
}
ORDER BY ?itemLabel
""",
    # Uganda: Q3539870 (district of Uganda) — ~133
    "UG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q3539870 .
  ?item wdt:P17 wd:Q1036 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sw" }
}
ORDER BY ?itemLabel
""",
    # ── Africa — Southern ───────────────────────────────────────────
    # Angola: Q378508 (municipality of Angola) — ~22
    "AO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q378508 .
  ?item wdt:P17 wd:Q916 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,pt" }
}
ORDER BY ?itemLabel
""",
    # Botswana: Q57368 (district of Botswana) — ~10
    "BW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q57368 .
  ?item wdt:P17 wd:Q963 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Eswatini: Q2280192 (inkhundla) — ~37
    "SZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2280192 .
  ?item wdt:P17 wd:Q1050 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Lesotho: Q844531 (district of Lesotho) — ~10
    "LS": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q844531 .
  ?item wdt:P17 wd:Q1013 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Namibia: Q608843 (region of Namibia) — ~14
    "NA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q608843 .
  ?item wdt:P17 wd:Q1030 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # South Africa: Q1500352 (local municipality of South Africa) — ~215
    "ZA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1500352 .
  ?item wdt:P17 wd:Q258 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Zambia: Q2744064 (district of Zambia) — ~96
    "ZM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q2744064 .
  ?item wdt:P17 wd:Q953 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Zimbabwe: Q5283558 (district of Zimbabwe) — ~42
    "ZW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q5283558 .
  ?item wdt:P17 wd:Q954 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
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

        pop_val = r.get("population", {}).get("value", "")
        if pop_val:
            try:
                entry["population"] = int(float(pop_val))
            except (ValueError, TypeError):
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
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?ags ?population WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q262166 .
  ?item wdt:P439 ?ags .
  FILTER(STRSTARTS(?ags, "{state_code}"))
  FILTER NOT EXISTS {{ ?item wdt:P576 ?dissolved }}
  OPTIONAL {{ ?item wdt:P856 ?website }}
  OPTIONAL {{ ?item wdt:P402 ?osmId }}
  OPTIONAL {{ ?item wdt:P1082 ?population }}
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

            pop_val = r.get("population", {}).get("value", "")
            if pop_val:
                try:
                    entry["population"] = int(float(pop_val))
                except (ValueError, TypeError):
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
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q783930 .
  ?item wdt:P17 wd:Q403 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sr" }
}
ORDER BY ?itemLabel
""",
    "MK": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q646793 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mk" }
}
ORDER BY ?itemLabel
""",
    "UA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1267632 .
  ?item wdt:P17 wd:Q212 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,uk" }
}
ORDER BY ?itemLabel
""",
    "MD": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q15068450 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ro,ru" }
}
ORDER BY ?itemLabel
""",
    "LI": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q203300 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,de" }
}
ORDER BY ?itemLabel
""",
    "SM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
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
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q2655841 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ka" }
}
ORDER BY ?itemLabel
""",
    "AM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q20724701 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,hy" }
}
ORDER BY ?itemLabel
""",
    "AZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q13417250 .
  ?item wdt:P17 wd:Q227 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,az" }
}
ORDER BY ?itemLabel
""",
    "BY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q2043199 .
  ?item wdt:P17 wd:Q184 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,be,ru" }
}
ORDER BY ?itemLabel
""",
    "TR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q48336 .
  ?item wdt:P17 wd:Q43 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,tr" }
}
ORDER BY ?itemLabel
""",
    # Australia: Q1867183 (local government area of Australia) — ~537 LGAs
    "AU": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1867183 .
  ?item wdt:P17 wd:Q408 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # New Zealand: Q941036 (territorial authority of NZ) — 67 councils
    "NZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q941036 .
  ?item wdt:P17 wd:Q664 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mi" }
}
ORDER BY ?itemLabel
""",
    # Indonesia: Q3191695 (regency) + Q3199141 (city) — ~521 kabupaten/kota
    "ID": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q3191695 wd:Q3199141 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q252 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,id" }
}
ORDER BY ?itemLabel
""",
    # Papua New Guinea: Q1053630 (province) + Q14942893 (district) — ~112
    "PG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q1053630 wd:Q14942893 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q691 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Malaysia: Q1994931 (district) — ~161 districts
    "MY": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1994931 .
  ?item wdt:P17 wd:Q833 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ms" }
}
ORDER BY ?itemLabel
""",
    # Thailand: Q50198 (province) — 76 provinces + Bangkok
    "TH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q50198 .
  ?item wdt:P17 wd:Q869 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,th" }
}
ORDER BY ?itemLabel
""",
    # Cambodia: Q7252589 (province) — 25 provinces
    "KH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q7252589 .
  ?item wdt:P17 wd:Q424 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,km" }
}
ORDER BY ?itemLabel
""",
    # Philippines: Q24764 (municipality) + Q29946056 (highly urbanized city)
    #   + Q106078286 (component city) — ~1637 total
    "PH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q24764 wd:Q29946056 wd:Q106078286 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q928 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,tl" }
}
ORDER BY ?itemLabel
""",
    # Vietnam: Q2824648 (province) + Q1381899 (centrally-controlled city) — ~63
    "VN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q2824648 wd:Q1381899 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q881 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,vi" }
}
ORDER BY ?itemLabel
""",
    # Myanmar: Q17315624 (state) + Q15072454 (region) — 14 states/regions + Naypyidaw
    "MM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q17315624 wd:Q15072454 wd:Q15971681 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q836 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,my" }
}
ORDER BY ?itemLabel
""",
    # Oman: Q3250615 (wilayat) — ~63 wilayats
    "OM": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q3250615 .
  ?item wdt:P17 wd:Q842 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # UAE: Q19833031 (emirate) — 7 emirates
    "AE": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q19833031 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Qatar: Q685320 (municipality) — 8 municipalities
    "QA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q685320 .
  ?item wdt:P17 wd:Q846 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Bahrain: Q867606 (governorate) — 4 governorates
    "BH": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q867606 .
  ?item wdt:P17 wd:Q398 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Fiji: Q3064474 (province) — 14 provinces
    "FJ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q3064474 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Samoa: Q1070167 (district) — 11 districts
    "WS": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1070167 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,sm" }
}
ORDER BY ?itemLabel
""",
    # Vanuatu: Q847299 (province) — 6 provinces
    "VU": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q847299 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fr,bi" }
}
ORDER BY ?itemLabel
""",
    # Tonga: Q20740204 (division) — 5 divisions
    "TO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q20740204 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,to" }
}
ORDER BY ?itemLabel
""",
    # Nauru: Q319796 (district) — 14 districts
    "NR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q319796 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Palau: Q1044181 (state) — 16 states
    "PW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1044181 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
ORDER BY ?itemLabel
""",
    # Japan: Q50337 (prefecture) — 47 prefectures
    "JP": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q50337 .
  ?item wdt:P17 wd:Q17 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ja" }
}
ORDER BY ?itemLabel
""",
    # Taiwan: Q706447 (county/city) — ~21
    "TW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q706447 wd:Q1867507 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q865 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,zh" }
}
ORDER BY ?itemLabel
""",
    # South Korea: Q29045252 (city) + Q17143371 (county) + Q15901936 (district) — ~160
    "KR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q29045252 wd:Q17143371 wd:Q15901936 wd:Q4925355 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q884 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ko" }
}
ORDER BY ?itemLabel
""",
    # North Korea: Q15620174 (province) — 9 provinces
    "KP": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q15620174 .
  ?item wdt:P17 wd:Q423 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ko" }
}
ORDER BY ?itemLabel
""",
    # China: Q1615742 (province-level division) — ~34
    "CN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31/wdt:P279* wd:Q1615742 .
  ?item wdt:P17 wd:Q148 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,zh" }
}
ORDER BY ?itemLabel
""",
    # Mongolia: Q50399 (province) — 21 aimags
    "MN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q50399 .
  ?item wdt:P17 wd:Q711 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mn" }
}
ORDER BY ?itemLabel
""",
    # India: Q12443800 (state/UT) — ~36
    "IN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q12443800 wd:Q467745 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q668 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,hi" }
}
ORDER BY ?itemLabel
""",
    # Bangladesh: Q878040 (division) — 8 divisions
    "BD": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q878040 .
  ?item wdt:P17 wd:Q902 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,bn" }
}
ORDER BY ?itemLabel
""",
    # Pakistan: Q15058985 (province) — ~8
    "PK": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q15058985 wd:Q1440957 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q843 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ur" }
}
ORDER BY ?itemLabel
""",
    # Sri Lanka: Q1230110 (district) — 25 districts
    "LK": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1230110 .
  ?item wdt:P17 wd:Q854 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,si,ta" }
}
ORDER BY ?itemLabel
""",
    # Nepal: Q2537537 (district) — 77 districts
    "NP": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q2537537 .
  ?item wdt:P17 wd:Q837 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ne" }
}
ORDER BY ?itemLabel
""",
    # Laos: Q15673297 (province) — 17 provinces
    "LA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q15673297 .
  ?item wdt:P17 wd:Q819 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,lo" }
}
ORDER BY ?itemLabel
""",
    # Brunei: Q60047 (mukim) — ~40
    "BN": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q60047 .
  ?item wdt:P17 wd:Q921 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ms" }
}
ORDER BY ?itemLabel
""",
    # East Timor: Q741821 (municipality) — 14
    "TL": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q741821 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,pt,tet" }
}
ORDER BY ?itemLabel
""",
    # Kazakhstan: Q836672 (region) — 17 regions
    "KZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q836672 .
  ?item wdt:P17 wd:Q232 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,kk,ru" }
}
ORDER BY ?itemLabel
""",
    # Uzbekistan: Q842420 (region) — 12 regions
    "UZ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q842420 .
  ?item wdt:P17 wd:Q265 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,uz,ru" }
}
ORDER BY ?itemLabel
""",
    # Kyrgyzstan: Q693039 (region) — 7 regions
    "KG": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q693039 .
  ?item wdt:P17 wd:Q813 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ky,ru" }
}
ORDER BY ?itemLabel
""",
    # Saudi Arabia: Q15728204 (province) — 13 provinces
    "SA": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q15728204 .
  ?item wdt:P17 wd:Q851 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Iraq: Q841753 (governorate) — 19
    "IQ": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q841753 .
  ?item wdt:P17 wd:Q796 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar,ku" }
}
ORDER BY ?itemLabel
""",
    # Jordan: Q867567 (governorate) — 12
    "JO": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q867567 .
  ?item wdt:P17 wd:Q810 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Lebanon: Q844713 (governorate) — 9
    "LB": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q844713 .
  ?item wdt:P17 wd:Q822 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Kuwait: Q842876 (governorate) — 6
    "KW": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q842876 .
  ?item wdt:P17 wd:Q817 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,ar" }
}
ORDER BY ?itemLabel
""",
    # Iran: Q1344695 (province) — 31
    "IR": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  ?item wdt:P31 wd:Q1344695 .
  ?item wdt:P17 wd:Q794 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,fa" }
}
ORDER BY ?itemLabel
""",
    # Israel: Q193560 (district) + Q1022469 (regional council) — ~60
    "IL": """
SELECT DISTINCT ?item ?itemLabel ?website ?osmId ?regionLabel ?population WHERE {
  VALUES ?type { wd:Q193560 wd:Q1022469 }
  ?item wdt:P31 ?type .
  ?item wdt:P17 wd:Q801 .
  OPTIONAL { ?item wdt:P856 ?website }
  OPTIONAL { ?item wdt:P402 ?osmId }
  OPTIONAL { ?item wdt:P131 ?region }
  OPTIONAL { ?item wdt:P1082 ?population }
  FILTER NOT EXISTS { ?item wdt:P576 ?dissolved }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,he,ar" }
}
ORDER BY ?itemLabel
""",
})


if __name__ == "__main__":
    main()
