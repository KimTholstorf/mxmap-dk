#!/usr/bin/env python3
"""Fetch municipality boundaries from OSM Overpass API and create TopoJSON files.

Usage: python3 scripts/fetch_boundaries.py [CC ...]

For each country, fetches admin boundaries at the appropriate level,
converts to GeoJSON, annotates with region/country, and creates
TopoJSON files via mapshaper.
"""

import json
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPO_DIR = ROOT / "topo"
DATA_DIR = ROOT / "data"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
_overpass_idx = 0

# OSM admin_level per country + ISO 3166-1 alpha-2 codes for area filter
COUNTRY_CONFIG = {
    "HR": {"admin_level": 7, "iso": "HR", "name": "Croatia"},
    "CY": {"admin_level": 6, "iso": "CY", "name": "Cyprus"},
    "GR": {"admin_level": 7, "iso": "GR", "name": "Greece"},
    "HU": {"admin_level": 7, "iso": "HU", "name": "Hungary"},
    "MT": {"admin_level": 8, "iso": "MT", "name": "Malta"},
    "RO": {"admin_level": 4, "iso": "RO", "name": "Romania"},
    "GB": {"admin_level": 10, "iso": "GB", "name": "United Kingdom"},
    "IT": {"admin_level": 6, "iso": "IT", "name": "Italy"},
    "FR": {"admin_level": 6, "iso": "FR", "name": "France"},
    "ES": {"admin_level": 6, "iso": "ES", "name": "Spain"},
    "EE": {"admin_level": 7, "iso": "EE", "name": "Estonia"},
    "AL": {"admin_level": 7, "iso": "AL", "name": "Albania"},
    "XK": {"admin_level": 7, "iso": "XK", "name": "Kosovo"},
    "ME": {"admin_level": 6, "iso": "ME", "name": "Montenegro"},
    "BA": {"admin_level": 7, "iso": "BA", "name": "Bosnia and Herzegovina"},
    "RS": {"admin_level": 7, "iso": "RS", "name": "Serbia"},
    "MK": {"admin_level": 7, "iso": "MK", "name": "North Macedonia"},
    "UA": {"admin_level": 4, "iso": "UA", "name": "Ukraine"},
    "MD": {"admin_level": 4, "iso": "MD", "name": "Moldova"},
    "LI": {"admin_level": 8, "iso": "LI", "name": "Liechtenstein"},
    "SM": {"admin_level": 8, "iso": "SM", "name": "San Marino"},
    "GE": {"admin_level": 6, "iso": "GE", "name": "Georgia"},
    "AM": {"admin_level": 6, "iso": "AM", "name": "Armenia"},
    "AZ": {"admin_level": 6, "iso": "AZ", "name": "Azerbaijan"},
    "BY": {"admin_level": 6, "iso": "BY", "name": "Belarus"},
    "TR": {"admin_level": 4, "iso": "TR", "name": "Turkey"},
    "GL": {"admin_level": 4, "iso": "GL", "name": "Greenland"},
    # Oceania
    "AU": {"admin_level": 6, "iso": "AU", "name": "Australia"},
    "NZ": {"admin_level": 6, "iso": "NZ", "name": "New Zealand"},
    "FJ": {"admin_level": 6, "iso": "FJ", "name": "Fiji"},
    "WS": {"admin_level": 4, "iso": "WS", "name": "Samoa"},
    "VU": {"admin_level": 4, "iso": "VU", "name": "Vanuatu"},
    "TO": {"admin_level": 4, "iso": "TO", "name": "Tonga"},
    "NR": {"admin_level": 4, "iso": "NR", "name": "Nauru"},
    "PW": {"admin_level": 4, "iso": "PW", "name": "Palau"},
    # Southeast Asia
    "ID": {"admin_level": 5, "iso": "ID", "name": "Indonesia"},
    "PG": {"admin_level": 4, "iso": "PG", "name": "Papua New Guinea"},
    "MY": {"admin_level": 6, "iso": "MY", "name": "Malaysia"},
    "TH": {"admin_level": 4, "iso": "TH", "name": "Thailand"},
    "KH": {"admin_level": 4, "iso": "KH", "name": "Cambodia"},
    "PH": {"admin_level": 4, "iso": "PH", "name": "Philippines"},
    "VN": {"admin_level": 4, "iso": "VN", "name": "Vietnam"},
    "MM": {"admin_level": 4, "iso": "MM", "name": "Myanmar"},
    "LA": {"admin_level": 4, "iso": "LA", "name": "Laos"},
    "BN": {"admin_level": 6, "iso": "BN", "name": "Brunei"},
    "TL": {"admin_level": 5, "iso": "TL", "name": "Timor-Leste"},
    # East Asia
    "JP": {"admin_level": 4, "iso": "JP", "name": "Japan"},
    "TW": {"admin_level": 4, "iso": "TW", "name": "Taiwan"},
    "KR": {"admin_level": 6, "iso": "KR", "name": "South Korea"},
    "KP": {"admin_level": 4, "iso": "KP", "name": "North Korea"},
    "CN": {"admin_level": 4, "iso": "CN", "name": "China"},
    "MN": {"admin_level": 4, "iso": "MN", "name": "Mongolia"},
    # South Asia
    "IN": {"admin_level": 4, "iso": "IN", "name": "India"},
    "BD": {"admin_level": 4, "iso": "BD", "name": "Bangladesh"},
    "PK": {"admin_level": 4, "iso": "PK", "name": "Pakistan"},
    "LK": {"admin_level": 5, "iso": "LK", "name": "Sri Lanka"},
    "NP": {"admin_level": 6, "iso": "NP", "name": "Nepal"},
    # Central Asia
    "KZ": {"admin_level": 4, "iso": "KZ", "name": "Kazakhstan"},
    "UZ": {"admin_level": 4, "iso": "UZ", "name": "Uzbekistan"},
    "KG": {"admin_level": 4, "iso": "KG", "name": "Kyrgyzstan"},
    # Middle East
    "OM": {"admin_level": 4, "iso": "OM", "name": "Oman"},
    "AE": {"admin_level": 4, "iso": "AE", "name": "UAE"},
    "QA": {"admin_level": 4, "iso": "QA", "name": "Qatar"},
    "BH": {"admin_level": 4, "iso": "BH", "name": "Bahrain"},
    "SA": {"admin_level": 4, "iso": "SA", "name": "Saudi Arabia"},
    "IQ": {"admin_level": 4, "iso": "IQ", "name": "Iraq"},
    "JO": {"admin_level": 4, "iso": "JO", "name": "Jordan"},
    "LB": {"admin_level": 4, "iso": "LB", "name": "Lebanon"},
    "KW": {"admin_level": 4, "iso": "KW", "name": "Kuwait"},
    "IR": {"admin_level": 4, "iso": "IR", "name": "Iran"},
    "IL": {"admin_level": 4, "iso": "IL", "name": "Israel"},
    # South America
    "AR": {"admin_level": 6, "iso": "AR", "name": "Argentina"},
    "BO": {"admin_level": 6, "iso": "BO", "name": "Bolivia"},
    "BR": {"admin_level": 8, "iso": "BR", "name": "Brazil"},
    "CL": {"admin_level": 8, "iso": "CL", "name": "Chile"},
    "CO": {"admin_level": 6, "iso": "CO", "name": "Colombia"},
    "EC": {"admin_level": 6, "iso": "EC", "name": "Ecuador"},
    "GY": {"admin_level": 4, "iso": "GY", "name": "Guyana"},
    "PE": {"admin_level": 6, "iso": "PE", "name": "Peru"},
    "PY": {"admin_level": 6, "iso": "PY", "name": "Paraguay"},
    "SR": {"admin_level": 4, "iso": "SR", "name": "Suriname"},
    "UY": {"admin_level": 4, "iso": "UY", "name": "Uruguay"},
    "VE": {"admin_level": 6, "iso": "VE", "name": "Venezuela"},
}


def overpass_query(query: str) -> dict:
    """Execute Overpass API query and return JSON. Rotates between servers."""
    global _overpass_idx
    url = OVERPASS_URLS[_overpass_idx % len(OVERPASS_URLS)]
    _overpass_idx += 1
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": "MXMap/1.0"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def fetch_boundaries(cc: str) -> dict | None:
    """Fetch admin boundaries for a country from Overpass API."""
    config = COUNTRY_CONFIG[cc]
    admin_level = config["admin_level"]
    iso = config["iso"]

    # Use area filter for the country
    query = f"""
[out:json][timeout:300];
area["ISO3166-1"="{iso}"]->.country;
(
  relation["boundary"="administrative"]["admin_level"="{admin_level}"](area.country);
);
out body;
>;
out skel qt;
"""
    print(f"  Querying Overpass for admin_level={admin_level}...")
    try:
        return overpass_query(query)
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


def osm_to_geojson(osm_data: dict, tmpdir: str) -> str:
    """Convert OSM JSON to GeoJSON using osmtogeojson."""
    osm_path = f"{tmpdir}/osm.json"
    geo_path = f"{tmpdir}/boundaries.geojson"

    with open(osm_path, "w") as f:
        json.dump(osm_data, f)

    # Try osmtogeojson first, fall back to mapshaper
    try:
        subprocess.run(
            ["osmtogeojson", osm_path],
            stdout=open(geo_path, "w"),
            check=True,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  osmtogeojson not found, using Python conversion...")
        # Simple fallback: extract relations directly
        geo = convert_osm_to_geojson_simple(osm_data)
        with open(geo_path, "w") as f:
            json.dump(geo, f)

    return geo_path


def convert_osm_to_geojson_simple(osm_data: dict) -> dict:
    """Simple OSM to GeoJSON conversion for relations (fallback)."""
    # Build node index
    nodes = {}
    for el in osm_data.get("elements", []):
        if el["type"] == "node":
            nodes[el["id"]] = (el["lon"], el["lat"])

    # Build way index
    ways = {}
    for el in osm_data.get("elements", []):
        if el["type"] == "way":
            coords = [nodes[n] for n in el.get("nodes", []) if n in nodes]
            if coords:
                ways[el["id"]] = coords

    features = []
    for el in osm_data.get("elements", []):
        if el["type"] != "relation":
            continue
        tags = el.get("tags", {})
        name = tags.get("name", tags.get("name:en", ""))

        # Collect outer rings
        rings = []
        for member in el.get("members", []):
            if member["type"] == "way" and member.get("role") in ("outer", ""):
                ref = member["ref"]
                if ref in ways:
                    rings.append(ways[ref])

        if not rings:
            continue

        # Try to merge rings into polygons
        merged = merge_ways(rings)
        if not merged:
            continue

        if len(merged) == 1:
            geometry = {"type": "Polygon", "coordinates": [merged[0]]}
        else:
            geometry = {"type": "MultiPolygon", "coordinates": [[r] for r in merged]}

        feature = {
            "type": "Feature",
            "id": f"relation/{el['id']}",
            "properties": {
                "name": name,
                "name_en": tags.get("name:en", ""),
                "osm_id": f"relation/{el['id']}",
                "country": tags.get("ISO3166-1", tags.get("is_in:country_code", "")),
            },
            "geometry": geometry,
        }
        features.append(feature)

    return {"type": "FeatureCollection", "features": features}


def merge_ways(ways: list[list]) -> list[list]:
    """Try to merge way segments into closed rings."""
    if not ways:
        return []

    # If all ways are already closed rings, return them
    closed = []
    open_ways = []
    for w in ways:
        if len(w) >= 4 and w[0] == w[-1]:
            closed.append(w)
        else:
            open_ways.append(w)

    if not open_ways:
        return closed

    # Try to merge open ways
    merged = []
    remaining = list(open_ways)

    while remaining:
        current = list(remaining.pop(0))
        changed = True
        while changed:
            changed = False
            for i, way in enumerate(remaining):
                if not way:
                    continue
                # Try to connect
                if current[-1] == way[0]:
                    current.extend(way[1:])
                    remaining.pop(i)
                    changed = True
                    break
                elif current[-1] == way[-1]:
                    current.extend(reversed(way[:-1]))
                    remaining.pop(i)
                    changed = True
                    break
                elif current[0] == way[-1]:
                    current = way[:-1] + current
                    remaining.pop(i)
                    changed = True
                    break
                elif current[0] == way[0]:
                    current = list(reversed(way)) + current[1:]
                    remaining.pop(i)
                    changed = True
                    break

        if len(current) >= 4:
            # Close the ring if not already closed
            if current[0] != current[-1]:
                current.append(current[0])
            merged.append(current)

    return closed + merged


def annotate_geojson(geo_path: str, cc: str, seed_data: list) -> str:
    """Annotate GeoJSON features with country, region from seed data."""
    with open(geo_path) as f:
        geo = json.load(f)

    # Build OSM ID -> region mapping from seed data
    osm_to_region = {}
    for entry in seed_data:
        osm_id = entry.get("osm_relation_id")
        if osm_id:
            osm_to_region[osm_id] = entry.get("region", "")

    for feature in geo.get("features", []):
        props = feature.get("properties", {})
        # Set country
        props["country"] = cc

        # Try to match region from seed data
        fid = feature.get("id", "")
        if fid.startswith("relation/"):
            osm_id = int(fid.split("/")[1])
            if osm_id in osm_to_region:
                props["region"] = osm_to_region[osm_id]

    annotated_path = geo_path.replace(".geojson", "_annotated.geojson")
    with open(annotated_path, "w") as f:
        json.dump(geo, f)
    return annotated_path


def create_topojson(geo_path: str, cc: str, level: str = "municipality") -> str:
    """Convert GeoJSON to TopoJSON via mapshaper with simplification."""
    out_path = str(TOPO_DIR / f"{cc.lower()}_{level}.topo.json")

    simplify = "15%" if level == "municipality" else "8%"
    quantization = "" if level == "municipality" else "quantization=5000"

    cmd = [
        "mapshaper", geo_path,
        "-simplify", simplify, "keep-shapes",
        "-o", out_path, "format=topojson",
    ]
    if quantization:
        cmd[-1] += f" {quantization}"

    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def create_region_topojson(geo_path: str, cc: str) -> str | None:
    """Create dissolved region-level TopoJSON."""
    out_path = str(TOPO_DIR / f"{cc.lower()}_region.topo.json")

    try:
        subprocess.run(
            [
                "mapshaper", geo_path,
                "-dissolve", "region",
                "-simplify", "8%", "keep-shapes",
                "-o", out_path, "format=topojson",
            ],
            check=True,
            capture_output=True,
        )
        return out_path
    except subprocess.CalledProcessError as e:
        print(f"  Region dissolve failed: {e}")
        return None


def update_manifest(cc: str, has_region: bool):
    """Update topo/manifest.json with new country entry."""
    manifest_path = TOPO_DIR / "manifest.json"
    with open(manifest_path) as f:
        manifest = json.load(f)

    cc_lower = cc.lower()
    muni_file = f"{cc_lower}_municipality.topo.json"
    region_file = f"{cc_lower}_region.topo.json" if has_region else muni_file

    # Get file sizes
    muni_size = (TOPO_DIR / muni_file).stat().st_size
    sizes = {muni_file: muni_size}
    if has_region:
        sizes[region_file] = (TOPO_DIR / region_file).stat().st_size

    manifest[cc] = {
        "levels": ["region", "district", "municipality"],
        "files": {
            "region": region_file,
            "district": muni_file,
            "municipality": muni_file,
        },
        "sizes": sizes,
    }

    # Sort manifest by country code
    sorted_manifest = dict(sorted(manifest.items()))
    with open(manifest_path, "w") as f:
        json.dump(sorted_manifest, f, indent=2)


DE_STATES_OSM = {
    "01": 51529, "02": 62782, "03": 454192, "04": 62559,
    "05": 62761, "06": 62650, "07": 62341, "08": 62611,
    "09": 2145268, "10": 62372, "11": 62422, "12": 454311,
    "13": 28322, "14": 62467, "15": 62607, "16": 62366,
}

# Large countries that need per-state boundary fetching
# Maps state_code -> OSM relation ID
LARGE_COUNTRY_STATES = {
    "AU": {
        "ACT": 2354197, "NSW": 2316593, "NT": 2316594, "QLD": 2316595,
        "SA": 2316596, "TAS": 2369652, "VIC": 2316741, "WA": 2316598,
    },
    "MY": {
        "JHR": 2939653, "KDH": 4444908, "KTN": 4443571, "MLK": 2939673,
        "NSN": 2939674, "PHG": 4444595, "PNG": 4445131, "PRK": 4445076,
        "PLS": 4444918, "SGR": 2932285, "TRG": 4444411, "SBH": 3879783,
        "SWK": 3879784, "KUL": 2939672, "LBN": 4521286, "PJY": 4443881,
    },
    "PH": {
        "NCR": 147488, "01": 1552186, "02": 1552192, "03": 1552195,
        "05": 3561455, "06": 3589982, "07": 3625910, "08": 3759193,
        "09": 3777290, "10": 3873457, "11": 3936842, "12": 3851570,
        "13": 3870502, "15": 1552190, "40": 1552120, "41": 1552261,
        "BARMM": 3821409,
    },
    "AR": {
        "A": 2405230, "B": 1632167, "C": 1224652, "D": 153538,
        "E": 153551, "F": 153536, "G": 153544, "H": 153554,
        "J": 153539, "K": 153545, "L": 153541, "M": 153540,
        "N": 153553, "P": 2849847, "Q": 1606727, "R": 153547,
        "S": 153543, "T": 153558, "U": 153548, "V": 153550,
        "W": 153552, "X": 3592494, "Y": 153556, "Z": 153549,
    },
    "BR": {
        "AC": 326266, "AL": 303781, "AM": 332476, "AP": 331463,
        "BA": 362413, "CE": 302635, "DF": 421151, "ES": 54882,
        "GO": 334443, "MA": 332924, "MG": 315173, "MS": 334051,
        "MT": 333597, "PA": 185579, "PB": 301464, "PE": 303702,
        "PI": 302819, "PR": 297640, "RJ": 57963, "RN": 301079,
        "RO": 325866, "RR": 326287, "RS": 242620, "SC": 296584,
        "SE": 303940, "SP": 298204, "TO": 336819,
    },
    "PE": {
        "AMA": 1973462, "ANC": 1953170, "APU": 1929522, "ARE": 1879287,
        "AYA": 1930901, "CAJ": 1896111, "CAL": 1944657, "CUS": 1923695,
        "HUC": 1954493, "HUV": 1933551, "ICA": 1899013, "JUN": 1948258,
        "LAL": 1967959, "LAM": 1969722, "LIM": 1944659, "LMA": 1944670,
        "LOR": 1994077, "MDD": 1891287, "MOQ": 1875889, "PAS": 1948452,
        "PIU": 1986151, "PUN": 1907899, "SAM": 1971661, "TAC": 1874307,
        "TUM": 1986974, "UCA": 1921996,
    },
}


def fetch_boundaries_per_state(cc: str):
    """Fetch boundaries per state for large countries.

    Uses LARGE_COUNTRY_STATES config to fetch each state separately,
    then combines into a single TopoJSON file per country.
    """
    if cc not in LARGE_COUNTRY_STATES:
        print(f"  {cc} not configured for per-state fetching")
        return

    config = COUNTRY_CONFIG[cc]
    admin_level = config["admin_level"]
    states = LARGE_COUNTRY_STATES[cc]
    cc_lower = cc.lower()

    TOPO_DIR.mkdir(exist_ok=True)

    # Load seed data
    seed_path = DATA_DIR / f"municipalities_{cc_lower}.json"
    with open(seed_path) as f:
        seed_data = json.load(f)

    osm_to_entry = {}
    for e in seed_data:
        if e.get("osm_relation_id"):
            osm_to_entry[e["osm_relation_id"]] = e

    # Skip if output already exists
    out_path = TOPO_DIR / f"{cc_lower}_municipality.topo.json"
    if out_path.exists():
        print(f"  Skipping {cc} — {out_path.name} already exists ({out_path.stat().st_size:,} bytes)")
        return

    all_features = []
    for state_code, state_osm_id in sorted(states.items()):
        print(f"\n  State {state_code} (OSM {state_osm_id})...")
        area_id = 3600000000 + state_osm_id

        query = f"""
[out:json][timeout:300];
area({area_id})->.state;
(
  relation["boundary"="administrative"]["admin_level"="{admin_level}"](area.state);
);
out body;
>;
out skel qt;
"""
        osm_data = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    print(f"    Retry {attempt}...")
                osm_data = overpass_query(query)
                relations = [e for e in osm_data.get("elements", []) if e["type"] == "relation"]
                print(f"    Got {len(relations)} relations")
                break
            except Exception as e:
                print(f"    ERROR: {e}")
                if "429" in str(e):
                    print("    Rate limited, waiting 90s...")
                    time.sleep(90)
                elif "504" in str(e) or "timeout" in str(e).lower():
                    print("    Timeout, waiting 45s...")
                    time.sleep(45)
                else:
                    time.sleep(15)

        if not osm_data:
            time.sleep(10)
            continue

        geo = convert_osm_to_geojson_simple(osm_data)
        for feature in geo.get("features", []):
            props = feature.get("properties", {})
            props["country"] = cc
            props["state"] = state_code
            fid = feature.get("id", "")
            if fid.startswith("relation/"):
                osm_id_int = int(fid.split("/")[1])
                entry = osm_to_entry.get(osm_id_int)
                if entry:
                    props["region"] = entry.get("region", "")
            if not props.get("osm_id"):
                props["osm_id"] = fid

        all_features.extend(geo.get("features", []))
        print(f"    Total features so far: {len(all_features)}")
        time.sleep(10)  # 10s between successful fetches (was 15)

    if not all_features:
        print(f"  No features collected for {cc}")
        return

    # Write combined GeoJSON and create TopoJSON
    with tempfile.TemporaryDirectory() as tmpdir:
        combined_path = f"{tmpdir}/combined.geojson"
        with open(combined_path, "w") as f:
            json.dump({"type": "FeatureCollection", "features": all_features}, f)

        print(f"\n  Combined {len(all_features)} features for {cc}")

        # Create municipality TopoJSON
        muni_topo = create_topojson(combined_path, cc, "municipality")
        muni_size = Path(muni_topo).stat().st_size
        print(f"  Municipality TopoJSON: {muni_size:,} bytes")

        # Create region TopoJSON
        has_region = False
        regions = set(f.get("properties", {}).get("region", "") for f in all_features if f.get("properties", {}).get("region"))
        if len(regions) > 1:
            region_topo = create_region_topojson(combined_path, cc)
            if region_topo:
                region_size = Path(region_topo).stat().st_size
                print(f"  Region TopoJSON: {region_size:,} bytes")
                has_region = True

        update_manifest(cc, has_region)
        print(f"  Updated manifest.json")


def fetch_de_boundaries_per_state():
    """Fetch DE Gemeinde boundaries per Bundesland.

    Most states use admin_level=8 for Gemeinden, but city-states
    (Berlin=11, Hamburg=02, Bremen=04) use admin_level=6 or the
    state boundary itself. We try 8 first, then fall back to 6.
    """
    TOPO_DIR.mkdir(exist_ok=True)

    # Load seed data for annotation
    seed_path = DATA_DIR / "municipalities_de.json"
    with open(seed_path) as f:
        seed_data = json.load(f)

    osm_to_entry = {}
    state_counts = {}
    for e in seed_data:
        if e.get("osm_relation_id"):
            osm_to_entry[e["osm_relation_id"]] = e
        sc = e["id"][3:5]
        state_counts[sc] = state_counts.get(sc, 0) + 1

    for state_code, state_osm_id in sorted(DE_STATES_OSM.items()):
        out_path = TOPO_DIR / f"de_municipality_{state_code}.topo.json"
        expected = state_counts.get(state_code, 0)
        print(f"\n  Processing DE state {state_code} (OSM {state_osm_id}, "
              f"expect ~{expected} Gemeinden)...")

        area_id = 3600000000 + state_osm_id
        # Try admin_level 8 first, fall back to 6 for city-states
        admin_levels = ["8", "6"] if expected <= 5 else ["8"]
        osm_data = None
        relations = []
        for level in admin_levels:
            query = f"""
[out:json][timeout:300];
area({area_id})->.state;
(
  relation["boundary"="administrative"]["admin_level"="{level}"](area.state);
);
out body;
>;
out skel qt;
"""
            for attempt in range(3):
                try:
                    if attempt > 0:
                        print(f"    Retry {attempt}...")
                    else:
                        print(f"    Trying admin_level={level}...")
                    osm_data = overpass_query(query)
                    relations = [e for e in osm_data.get("elements", [])
                                 if e["type"] == "relation"]
                    print(f"    Got {len(relations)} relations")
                    break
                except Exception as e:
                    print(f"    ERROR: {e}")
                    if "429" in str(e):
                        print("    Rate limited, waiting 90s...")
                        time.sleep(90)
                    elif "504" in str(e) or "timeout" in str(e).lower():
                        print("    Timeout, waiting 30s...")
                        time.sleep(30)
                    else:
                        time.sleep(15)
            if relations:
                break
            time.sleep(10)

        if not osm_data or not relations:
            print("    Skipping (no relations at any admin level)")
            time.sleep(10)
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use Python converter (osmtogeojson strips properties)
            geo = convert_osm_to_geojson_simple(osm_data)
            print(f"    Converted to {len(geo.get('features', []))} GeoJSON features")

            if not geo.get("features"):
                print("    Skipping (no features after conversion)")
                time.sleep(5)
                continue

            # Annotate with country + region + osm_id
            for feature in geo.get("features", []):
                props = feature.get("properties", {})
                props["country"] = "DE"
                fid = feature.get("id", "")
                if fid.startswith("relation/"):
                    osm_id_int = int(fid.split("/")[1])
                    entry = osm_to_entry.get(osm_id_int)
                    if entry:
                        props["region"] = entry.get("region", "")
                # Ensure osm_id property exists for mapshaper id-field
                if not props.get("osm_id"):
                    props["osm_id"] = fid

            annotated_path = f"{tmpdir}/annotated.geojson"
            with open(annotated_path, "w") as fw:
                json.dump(geo, fw)

            # Create per-state TopoJSON
            layer_name = f"de_municipality_{state_code}"
            try:
                # Only keep fields that exist; name_en may not be present
                subprocess.run(
                    [
                        "mapshaper", annotated_path,
                        "-filter-fields", "name,osm_id",
                        "-rename-layers", layer_name,
                        "-simplify", "15%", "keep-shapes",
                        "-o", str(out_path), "format=topojson",
                        "id-field=osm_id", "quantization=10000",
                    ],
                    check=True, capture_output=True, text=True,
                )
                size = out_path.stat().st_size
                n_features = len(geo.get("features", []))
                print(f"    → {out_path.name} ({n_features} features, {size:,} bytes)")
            except subprocess.CalledProcessError as e:
                print(f"    mapshaper FAILED: {e.stderr[:200]}")

        time.sleep(10)  # Rate limit Overpass


def main():
    countries = sys.argv[1:] if len(sys.argv) > 1 else list(COUNTRY_CONFIG.keys())

    TOPO_DIR.mkdir(exist_ok=True)

    for cc in countries:
        cc = cc.upper()

        # Special handling for DE (per-state boundary fetching)
        if cc == "DE":
            print(f"\n{'='*50}")
            print("Processing Germany (DE) per-Bundesland...")
            fetch_de_boundaries_per_state()
            continue

        # Per-state fetching for other large countries
        if cc in LARGE_COUNTRY_STATES:
            print(f"\n{'='*50}")
            print(f"Processing {COUNTRY_CONFIG[cc]['name']} ({cc}) per-state...")
            fetch_boundaries_per_state(cc)
            continue

        if cc not in COUNTRY_CONFIG:
            print(f"Unknown country: {cc}")
            continue

        config = COUNTRY_CONFIG[cc]
        print(f"\n{'='*50}")
        print(f"Processing {config['name']} ({cc})...")

        # Skip if output already exists
        out_path = TOPO_DIR / f"{cc.lower()}_municipality.topo.json"
        if out_path.exists():
            print(f"  Skipping — {out_path.name} already exists ({out_path.stat().st_size:,} bytes)")
            continue

        # Load seed data for region annotation
        seed_path = DATA_DIR / f"municipalities_{cc.lower()}.json"
        with open(seed_path) as f:
            seed_data = json.load(f)
        print(f"  {len(seed_data)} municipalities in seed data")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Fetch from Overpass
            osm_data = fetch_boundaries(cc)
            if not osm_data:
                continue

            relations = [e for e in osm_data.get("elements", []) if e["type"] == "relation"]
            print(f"  Got {len(relations)} relations from Overpass")

            # Convert to GeoJSON
            geo_path = osm_to_geojson(osm_data, tmpdir)

            # Check feature count
            with open(geo_path) as f:
                geo = json.load(f)
            print(f"  GeoJSON features: {len(geo.get('features', []))}")

            if not geo.get("features"):
                print("  ERROR: No features extracted!")
                continue

            # Annotate
            annotated = annotate_geojson(geo_path, cc, seed_data)

            # Create municipality-level TopoJSON
            muni_topo = create_topojson(annotated, cc, "municipality")
            muni_size = Path(muni_topo).stat().st_size
            print(f"  Municipality TopoJSON: {muni_size:,} bytes")

            # Create region-level TopoJSON (dissolved)
            has_region = False
            # Check if regions exist in seed data
            regions = set(e.get("region", "") for e in seed_data if e.get("region"))
            if len(regions) > 1:
                region_topo = create_region_topojson(annotated, cc)
                if region_topo:
                    region_size = Path(region_topo).stat().st_size
                    print(f"  Region TopoJSON: {region_size:,} bytes")
                    has_region = True

            # Update manifest
            update_manifest(cc, has_region)
            print(f"  Updated manifest.json")

        # Rate limit for Overpass API
        time.sleep(5)

    print("\nDone!")


if __name__ == "__main__":
    main()
