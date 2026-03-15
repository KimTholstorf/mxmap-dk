#!/usr/bin/env python3
"""Fetch missing municipality boundaries and merge into existing TopoJSON files.

Finds data entries that have OSM relation IDs but no matching TopoJSON feature,
fetches their boundaries from Overpass API, and merges them into the existing
per-country TopoJSON files.

Usage: uv run python3 scripts/patch_missing_boundaries.py [CC ...]
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
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def find_missing(cc: str) -> list[dict]:
    """Find data entries with OSM IDs that don't match any TopoJSON feature."""
    with open(ROOT / "data-summary.json") as f:
        munis = json.load(f)["municipalities"]

    manifest = json.load(open(TOPO_DIR / "manifest.json"))
    if cc not in manifest:
        return []

    topo_file = manifest[cc]["files"]["municipality"]
    with open(TOPO_DIR / topo_file) as f:
        topo = json.load(f)
    geoms = list(topo["objects"].values())[0]["geometries"]
    topo_ids = set(g.get("id", "") for g in geoms)

    cc_munis = {k: v for k, v in munis.items() if v.get("country") == cc}
    missing = []
    for bfs, m in cc_munis.items():
        osm = m.get("osm_relation_id")
        if not osm:
            continue
        if f"relation/{osm}" not in topo_ids:
            missing.append({"osm_id": osm, "name": m["name"], "bfs": bfs})

    return missing


def fetch_relations(osm_ids: list[int]) -> dict:
    """Fetch specific relations from Overpass API."""
    # Overpass needs comma-separated IDs in id: filter
    id_list = ",".join(str(i) for i in osm_ids)
    query = f"""
[out:json][timeout:300];
(
  relation(id:{id_list});
);
out body;
>;
out skel qt;
"""
    data = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "MXMap/1.0"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def osm_to_geojson(osm_data: dict, tmpdir: str) -> str:
    """Convert OSM data to GeoJSON via osmtogeojson."""
    osm_path = f"{tmpdir}/osm.json"
    geo_path = f"{tmpdir}/patch.geojson"

    with open(osm_path, "w") as f:
        json.dump(osm_data, f)

    subprocess.run(
        ["osmtogeojson", osm_path],
        stdout=open(geo_path, "w"),
        check=True,
        timeout=120,
    )
    return geo_path


def merge_into_topo(cc: str, patch_geojson: str):
    """Merge new GeoJSON features into existing TopoJSON file via mapshaper."""
    manifest = json.load(open(TOPO_DIR / "manifest.json"))
    topo_file = TOPO_DIR / manifest[cc]["files"]["municipality"]

    with tempfile.TemporaryDirectory() as tmpdir:
        # Convert existing topo to geojson
        existing_geo = f"{tmpdir}/existing.geojson"
        subprocess.run(
            ["mapshaper", str(topo_file), "-o", existing_geo, "format=geojson"],
            check=True,
            capture_output=True,
        )

        # Merge the two geojson files
        merged_geo = f"{tmpdir}/merged.geojson"
        subprocess.run(
            [
                "mapshaper",
                existing_geo,
                "-merge-layers",
                "force",
                f"combine-files",
                patch_geojson,
                "-o",
                merged_geo,
                "format=geojson",
            ],
            check=True,
            capture_output=True,
        )

        # Convert back to topojson with same simplification
        subprocess.run(
            [
                "mapshaper",
                merged_geo,
                "-simplify",
                "15%",
                "keep-shapes",
                "-o",
                str(topo_file),
                "format=topojson",
            ],
            check=True,
            capture_output=True,
        )


def simple_merge(cc: str, patch_geojson: str):
    """Merge new GeoJSON features into existing TopoJSON via mapshaper.

    Converts existing TopoJSON back to GeoJSON, concatenates features,
    then re-creates TopoJSON. This avoids coordinate transform mismatches
    that occur when manually merging arcs from different TopoJSON files.
    """
    manifest = json.load(open(TOPO_DIR / "manifest.json"))
    topo_path = TOPO_DIR / manifest[cc]["files"]["municipality"]

    with tempfile.TemporaryDirectory() as tmpdir:
        # Convert existing topo to geojson
        # mapshaper may output multiple files for multi-layer topos
        subprocess.run(
            ["mapshaper", str(topo_path), "-o", f"{tmpdir}/layer.geojson", "format=geojson"],
            check=True,
            capture_output=True,
        )

        # Find the polygon layer (largest file, or check geometry type)
        import glob
        geo_files = sorted(glob.glob(f"{tmpdir}/layer*.geojson"),
                           key=lambda p: -Path(p).stat().st_size)

        # Merge all polygon features from all layers
        all_features = []
        for gf in geo_files:
            with open(gf) as f:
                layer = json.load(f)
            for feat in layer.get("features", []):
                geom = feat.get("geometry")
                if not geom:
                    continue
                gtype = geom.get("type", "")
                if "Polygon" in gtype:
                    all_features.append(feat)

        existing = {"type": "FeatureCollection", "features": all_features}

        with open(patch_geojson) as f:
            patch = json.load(f)

        existing["features"].extend(patch["features"])

        merged_geo = f"{tmpdir}/merged.geojson"
        with open(merged_geo, "w") as f:
            json.dump(existing, f)

        # Convert back to topojson with simplification
        subprocess.run(
            [
                "mapshaper",
                merged_geo,
                "-simplify",
                "15%",
                "keep-shapes",
                "-o",
                str(topo_path),
                "format=topojson",
            ],
            check=True,
            capture_output=True,
        )


def main():
    countries = sys.argv[1:] if len(sys.argv) > 1 else None

    # Find all countries with missing boundaries
    manifest = json.load(open(TOPO_DIR / "manifest.json"))
    if not countries:
        countries = sorted(manifest.keys())

    for cc in countries:
        cc = cc.upper()
        missing = find_missing(cc)
        if not missing:
            continue

        print(f"\n{cc}: {len(missing)} missing boundaries")
        for m in missing:
            print(f"  {m['name']} (relation/{m['osm_id']})")

        osm_ids = [m["osm_id"] for m in missing]

        print(f"  Fetching {len(osm_ids)} relations from Overpass...")
        try:
            osm_data = fetch_relations(osm_ids)
        except Exception as e:
            print(f"  ERROR fetching: {e}")
            time.sleep(10)
            continue

        relations = [e for e in osm_data.get("elements", []) if e["type"] == "relation"]
        print(f"  Got {len(relations)} relations")

        if not relations:
            time.sleep(5)
            continue

        with tempfile.TemporaryDirectory() as tmpdir:
            print(f"  Converting to GeoJSON...")
            geo_path = osm_to_geojson(osm_data, tmpdir)

            with open(geo_path) as f:
                geo = json.load(f)
            features = geo.get("features", [])
            print(f"  Got {len(features)} GeoJSON features")

            if not features:
                time.sleep(5)
                continue

            # Filter to only polygon/multipolygon features
            poly_features = [
                f
                for f in features
                if f.get("geometry", {}).get("type") in ("Polygon", "MultiPolygon")
            ]
            print(f"  {len(poly_features)} polygon features")

            if not poly_features:
                time.sleep(5)
                continue

            # Write filtered geojson
            filtered_path = f"{tmpdir}/filtered.geojson"
            with open(filtered_path, "w") as f:
                json.dump(
                    {"type": "FeatureCollection", "features": poly_features}, f
                )

            print(f"  Merging into {cc} TopoJSON...")
            try:
                simple_merge(cc, filtered_path)
                topo_file = manifest[cc]["files"]["municipality"]
                size = (TOPO_DIR / topo_file).stat().st_size
                print(f"  Done: {topo_file} ({size:,} bytes)")
            except Exception as e:
                print(f"  ERROR merging: {e}")

        # Rate limit
        time.sleep(5)

    print("\nDone!")


if __name__ == "__main__":
    main()
