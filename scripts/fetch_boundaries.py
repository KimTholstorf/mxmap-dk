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

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# OSM admin_level per country + ISO 3166-1 alpha-2 codes for area filter
COUNTRY_CONFIG = {
    "HR": {"admin_level": 7, "iso": "HR", "name": "Croatia"},
    "CY": {"admin_level": 6, "iso": "CY", "name": "Cyprus"},
    "GR": {"admin_level": 7, "iso": "GR", "name": "Greece"},
    "HU": {"admin_level": 7, "iso": "HU", "name": "Hungary"},
    "MT": {"admin_level": 8, "iso": "MT", "name": "Malta"},
    "RO": {"admin_level": 4, "iso": "RO", "name": "Romania"},
}


def overpass_query(query: str) -> dict:
    """Execute Overpass API query and return JSON."""
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
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
                "osm_id": el["id"],
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


def main():
    countries = sys.argv[1:] if len(sys.argv) > 1 else list(COUNTRY_CONFIG.keys())

    TOPO_DIR.mkdir(exist_ok=True)

    for cc in countries:
        cc = cc.upper()
        if cc not in COUNTRY_CONFIG:
            print(f"Unknown country: {cc}")
            continue

        config = COUNTRY_CONFIG[cc]
        print(f"\n{'='*50}")
        print(f"Processing {config['name']} ({cc})...")

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
