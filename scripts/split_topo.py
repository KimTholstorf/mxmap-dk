#!/usr/bin/env python3
"""Split monolithic TopoJSON into per-country per-level files.

Usage: python scripts/split_topo.py

Reads:
  baltic-municipalities.topo.json
  data/municipalities_*.json

Produces:
  topo/{cc}_municipality.topo.json
  topo/{cc}_region.topo.json       (dissolved by region)
  topo/{cc}_district.topo.json     (dissolved by district, AT/BE only)
  topo/manifest.json
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPO_DIR = ROOT / "topo"
MONOLITHIC = ROOT / "baltic-municipalities.topo.json"

COUNTRIES = [
    "EE",
    "LV",
    "LT",
    "FI",
    "NO",
    "IS",
    "SE",
    "DE",
    "DK",
    "AD",
    "LU",
    "BE",
    "AT",
    "CZ",
    "SK",
    "ES",
    "FR",
    "PL",
    "PT",
    "NL",
    "IT",
    "IE",
    "BG",
    "SI",
    "GB",
    "HR",
    "CY",
    "GR",
    "HU",
    "MT",
    "RO",
]

# Which conceptual level maps to which file level per country.
# None = level not available for this country.
LEVEL_MAP = {
    "AT": {"region": "region", "district": "district", "municipality": "municipality"},
    "BE": {"region": "region", "district": "district", "municipality": "municipality"},
    "DE": {
        "region": "region",
        "district": "municipality",
        "municipality": "municipality",
    },
    "FI": {"region": "region", "district": "region", "municipality": "municipality"},
    "NO": {"region": "region", "district": "region", "municipality": "municipality"},
    "IS": {"region": "region", "district": "region", "municipality": "municipality"},
    "SE": {"region": "region", "district": "region", "municipality": "municipality"},
    "DK": {"region": "region", "district": "region", "municipality": "municipality"},
    "CZ": {
        "region": "region",
        "district": "municipality",
        "municipality": "municipality",
    },
    "EE": {"region": "region", "district": "region", "municipality": "municipality"},
    "LT": {"region": "region", "district": "region", "municipality": "municipality"},
    "LV": {
        "region": "municipality",
        "district": "municipality",
        "municipality": "municipality",
    },
    "LU": {"region": "region", "district": "region", "municipality": "municipality"},
    "AD": {
        "region": "municipality",
        "district": "municipality",
        "municipality": "municipality",
    },
    "ES": {
        "region": "region",
        "district": "municipality",
        "municipality": "municipality",
    },
    "FR": {
        "region": "region",
        "district": "municipality",
        "municipality": "municipality",
    },
    "PL": {
        "region": "region",
        "district": "municipality",
        "municipality": "municipality",
    },
    "PT": {
        "region": "region",
        "district": "municipality",
        "municipality": "municipality",
    },
    "NL": {"region": "region", "district": "region", "municipality": "municipality"},
    "IT": {
        "region": "region",
        "district": "municipality",
        "municipality": "municipality",
    },
    "IE": {"region": "region", "district": "municipality", "municipality": "municipality"},
    "BG": {
        "region": "municipality",
        "district": "municipality",
        "municipality": "municipality",
    },
    "SK": {
        "region": "region",
        "district": "municipality",
        "municipality": "municipality",
    },
    "SI": {"region": "region", "district": "region", "municipality": "municipality"},
    "GB": {"region": "region", "district": "municipality", "municipality": "municipality"},
    "HR": {"region": "region", "district": "municipality", "municipality": "municipality"},
    "CY": {"region": "municipality", "district": "municipality", "municipality": "municipality"},
    "GR": {"region": "region", "district": "municipality", "municipality": "municipality"},
    "HU": {"region": "region", "district": "municipality", "municipality": "municipality"},
    "MT": {"region": "municipality", "district": "municipality", "municipality": "municipality"},
    "RO": {"region": "region", "district": "municipality", "municipality": "municipality"},
}


def get_district_key(cc, muni_id):
    """Derive district grouping key from municipality ID."""
    if cc == "AT":
        return muni_id[:6]  # "AT-101"
    if cc == "BE":
        return muni_id[:5]  # "BE-11"
    return None


def load_seed_data():
    """Load all municipality seed files."""
    munis = []
    for cc in COUNTRIES:
        path = ROOT / "data" / f"municipalities_{cc.lower()}.json"
        if path.exists():
            with open(path) as f:
                munis.extend(json.load(f))
    return munis


def run_mapshaper(args):
    """Run mapshaper with given arguments."""
    result = subprocess.run(
        ["mapshaper"] + args,
        check=True,
        capture_output=True,
        text=True,
    )
    return result


def write_topojson(geojson, output_path, simplify="15%", quantization=10000):
    """Write GeoJSON FeatureCollection to TopoJSON via mapshaper."""
    with tempfile.NamedTemporaryFile(suffix=".geojson", mode="w", delete=False) as tmp:
        json.dump(geojson, tmp)
        tmp_path = tmp.name

    try:
        layer_name = output_path.stem.replace(".topo", "")
        cmd = [
            tmp_path,
            "-filter-fields",
            "name,name_en,osm_id",
            "-rename-layers",
            layer_name,
        ]
        if simplify:
            cmd.extend(["-simplify", simplify, "keep-shapes"])
        cmd.extend(
            [
                "-o",
                str(output_path),
                "format=topojson",
                "id-field=osm_id",
                f"quantization={quantization}",
            ]
        )
        run_mapshaper(cmd)
    finally:
        os.unlink(tmp_path)


def dissolve_topojson(geojson, field, output_path, simplify="15%", quantization=10000):
    """Dissolve GeoJSON by field and write as TopoJSON."""
    with tempfile.NamedTemporaryFile(suffix=".geojson", mode="w", delete=False) as tmp:
        json.dump(geojson, tmp)
        tmp_path = tmp.name

    try:
        layer_name = output_path.stem.replace(".topo", "")
        cmd = [
            tmp_path,
            "-dissolve",
            field,
            "copy-fields=country",
            "-each",
            f"name = {field}",
            "-filter-fields",
            "name,country",
            "-rename-layers",
            layer_name,
        ]
        if simplify:
            cmd.extend(["-simplify", simplify, "keep-shapes"])
        cmd.extend(
            ["-o", str(output_path), "format=topojson", f"quantization={quantization}"]
        )
        run_mapshaper(cmd)
    finally:
        os.unlink(tmp_path)


def generate_manifest():
    """Generate manifest.json with file metadata."""
    manifest = {}
    for cc in COUNTRIES:
        level_map = LEVEL_MAP[cc]
        files = {}
        sizes = {}
        for level in ["region", "district", "municipality"]:
            actual = level_map.get(level)
            if actual is None:
                continue
            filename = f"{cc.lower()}_{actual}.topo.json"
            files[level] = filename
            filepath = TOPO_DIR / filename
            if filepath.exists() and filename not in sizes:
                sizes[filename] = filepath.stat().st_size

        available_levels = [
            lvl
            for lvl in ["region", "district", "municipality"]
            if level_map.get(lvl) is not None
        ]
        manifest[cc] = {
            "levels": available_levels,
            "files": files,
            "sizes": sizes,
        }

    with open(TOPO_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


def main():
    # Check prerequisites
    if not MONOLITHIC.exists():
        print(f"Error: {MONOLITHIC} not found")
        sys.exit(1)

    try:
        subprocess.run(["mapshaper", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("Error: mapshaper not found. Install with: npm install -g mapshaper")
        sys.exit(1)

    TOPO_DIR.mkdir(exist_ok=True)

    # Load seed data
    print("Loading seed data...")
    munis = load_seed_data()
    by_osm = {}
    by_name = {}
    for m in munis:
        if m.get("osm_relation_id"):
            by_osm[f"relation/{m['osm_relation_id']}"] = m
        by_name[m["name"].lower()] = m
    print(f"  {len(munis)} municipalities loaded")

    # Convert monolithic TopoJSON to GeoJSON
    print("Converting TopoJSON to GeoJSON...")
    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
        geojson_path = tmp.name

    try:
        run_mapshaper([str(MONOLITHIC), "-o", geojson_path, "format=geojson"])
        with open(geojson_path) as f:
            geojson = json.load(f)
    finally:
        os.unlink(geojson_path)

    print(f"  {len(geojson['features'])} features loaded")

    # Match features to municipalities and annotate
    print("Matching features to municipalities...")
    country_features = {cc: [] for cc in COUNTRIES}
    unmatched = 0
    for feature in geojson["features"]:
        props = feature.get("properties", {})
        osm_id = feature.get("id") or props.get("id", "")

        m = by_osm.get(osm_id)
        if not m:
            name = (props.get("name") or props.get("name_en") or "").lower()
            m = by_name.get(name) if name else None

        if m:
            cc = m["country"]
            # Use seed data's OSM relation ID (monolithic file has integer IDs)
            osm_rel_id = m.get("osm_relation_id")
            feature["properties"]["osm_id"] = (
                f"relation/{osm_rel_id}" if osm_rel_id else feature.get("id", "")
            )
            feature["properties"]["country"] = cc
            if "name_en" not in feature["properties"]:
                feature["properties"]["name_en"] = ""
            feature["properties"]["region"] = m.get("region", "")
            feature["properties"]["muni_id"] = m.get("id", "")
            dk = get_district_key(cc, m.get("id", ""))
            feature["properties"]["district_key"] = dk or m.get("region", "")
            country_features[cc].append(feature)
        else:
            unmatched += 1

    if unmatched:
        print(f"  Warning: {unmatched} unmatched features")

    # Generate per-country files
    for cc in COUNTRIES:
        features = country_features[cc]
        if not features:
            print(f"  {cc}: no features, skipping")
            continue

        level_map = LEVEL_MAP[cc]
        fc = {"type": "FeatureCollection", "features": features}

        # Municipality level (15% simplification, full quantization)
        muni_out = TOPO_DIR / f"{cc.lower()}_municipality.topo.json"
        print(f"  {cc}: {len(features)} municipalities -> {muni_out.name}")
        write_topojson(fc, muni_out, simplify="15%", quantization=10000)

        # Region level (dissolved, 8% simplification, lower quantization)
        if level_map["region"] == "region":
            region_out = TOPO_DIR / f"{cc.lower()}_region.topo.json"
            n_regions = len(set(f["properties"]["region"] for f in features))
            print(f"  {cc}: {n_regions} regions -> {region_out.name}")
            dissolve_topojson(
                fc, "region", region_out, simplify="8%", quantization=5000
            )

        # District level (dissolved, only AT/BE)
        if level_map["district"] == "district":
            district_out = TOPO_DIR / f"{cc.lower()}_district.topo.json"
            n_districts = len(set(f["properties"]["district_key"] for f in features))
            print(f"  {cc}: {n_districts} districts -> {district_out.name}")
            dissolve_topojson(fc, "district_key", district_out, simplify="15%")

    # Generate manifest
    print("Generating manifest...")
    generate_manifest()
    print("Done!")


if __name__ == "__main__":
    main()
