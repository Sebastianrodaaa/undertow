"""Real OpenStreetMap extracts and rasterization.

Downloads are cached with a byte cap, timeout, and SHA-256 checksum. OSM data is
licensed ODbL 1.0; derived grids carry the same attribution (see NOTICE.md).
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
MAX_DOWNLOAD_BYTES = 28 * 1024 * 1024
TIMEOUT_SECONDS = 18
_OVERPASS_AVAILABLE: bool | None = None


@dataclass(frozen=True)
class CitySpec:
    key: str
    label: str
    bbox: tuple[float, float, float, float]  # south, west, north, east


CITIES: dict[str, CitySpec] = {
    "paris": CitySpec("paris", "Paris · Ile de la Cite", (48.8505, 2.3370, 48.8615, 2.3575)),
    "lyon": CitySpec("lyon", "Lyon · Presqu'ile", (45.7560, 4.8235, 45.7675, 4.8425)),
    "amsterdam": CitySpec("amsterdam", "Amsterdam · canal ring", (52.3600, 4.8790, 52.3780, 4.9050)),
    "venice": CitySpec("venice", "Venice · San Marco", (45.4315, 12.3260, 45.4390, 12.3425)),
}


@dataclass
class Way:
    osm_id: int
    name: str
    bridge: bool
    highway: str
    cells: np.ndarray  # (n, 2), y/x integer cells


@dataclass
class CityGrid:
    spec: CitySpec
    size: int
    walkable: np.ndarray
    exits: np.ndarray
    exit_points: np.ndarray
    buildings: np.ndarray
    ways: list[Way]
    checksum: str
    cell_to_ways: dict[tuple[int, int], list[int]]

    @property
    def named_ways(self) -> list[Way]:
        return [w for w in self.ways if w.name]

    def way_by_name(self, fragment: str) -> Way | None:
        needle = fragment.casefold()
        exact = [w for w in self.named_ways if w.name.casefold() == needle]
        if exact:
            return exact[0]
        partial = [w for w in self.named_ways if needle in w.name.casefold()]
        return partial[0] if partial else None

    def way_at_cell(self, y: int, x: int) -> Way | None:
        ids = self.cell_to_ways.get((int(y), int(x)), [])
        if not ids:
            return None
        by_id = {w.osm_id: w for w in self.ways}
        named = [by_id[i] for i in ids if by_id[i].name]
        return named[0] if named else by_id[ids[0]]


def _bbox_q(bbox: tuple[float, float, float, float]) -> str:
    return "%.7f,%.7f,%.7f,%.7f" % bbox


def _queries(bbox: tuple[float, float, float, float]) -> dict[str, str]:
    b = _bbox_q(bbox)
    return {
        "streets": f'[out:json][timeout:{TIMEOUT_SECONDS}];way["highway"]({b});out geom;',
        "stops": (
            f'[out:json][timeout:{TIMEOUT_SECONDS}];('
            f'node["railway"~"^(station|tram_stop|halt)$"]({b});'
            f'node["public_transport"~"^(platform|stop_position)$"]({b});'
            f'node["amenity"="ferry_terminal"]({b});'
            f'node["station"="subway"]({b});'
            f');out body;'
        ),
        "buildings": (
            f'[out:json][timeout:{TIMEOUT_SECONDS}];('
            f'way["building"]({b});node["building"]({b});'
            f');out center;'
        ),
    }


def _post_overpass(query: str) -> dict:
    body = urllib.parse.urlencode({"data": query}).encode()
    last_error: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={"User-Agent": "undertow-research/0.1 (OSM ODbL attribution in NOTICE.md)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS + 5) as response:
                payload = response.read(MAX_DOWNLOAD_BYTES + 1)
            if len(payload) > MAX_DOWNLOAD_BYTES:
                raise ValueError(f"Overpass response exceeds {MAX_DOWNLOAD_BYTES} byte cap")
            return json.loads(payload.decode("utf-8"))
        except Exception as exc:  # network endpoints genuinely fail over
            last_error = exc
            time.sleep(1.0)
    raise RuntimeError(f"Overpass download failed: {last_error}")


def _canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _tile_bboxes(bbox: tuple[float, float, float, float], max_width: float = 0.0065, max_height: float = 0.0038) -> list[tuple[float, float, float, float]]:
    south, west, north, east = bbox
    nx = max(1, math.ceil((east - west) / max_width))
    ny = max(1, math.ceil((north - south) / max_height))
    tiles = []
    for iy in range(ny):
        for ix in range(nx):
            s = south + (north - south) * iy / ny
            n = south + (north - south) * (iy + 1) / ny
            w = west + (east - west) * ix / nx
            e = west + (east - west) * (ix + 1) / nx
            tiles.append((s, w, n, e))
    return tiles


def _download_osm_api_tile(tile: tuple[float, float, float, float]) -> bytes:
    south, west, north, east = tile
    url = "https://api.openstreetmap.org/api/0.6/map?" + urllib.parse.urlencode(
        {"bbox": f"{west:.7f},{south:.7f},{east:.7f},{north:.7f}"}
    )
    req = urllib.request.Request(url, headers={"User-Agent": "undertow-research/0.1 (OSM ODbL attribution in NOTICE.md)"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS + 8) as response:
        payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise ValueError("OSM API tile exceeds byte cap")
    return payload


def _tags(el: ET.Element) -> dict[str, str]:
    return {tag.attrib.get("k", ""): tag.attrib.get("v", "") for tag in el.findall("tag")}


def _osm_api_extract(spec: CitySpec) -> dict:
    """Fallback real OSM extract through the versioned OSM map API.

    ponytail: this exists because public Overpass endpoints are intermittently
    unreachable from CI/dev boxes. It preserves the same cache/checksum/cap
    boundary and records the actual source in the extract.
    """
    tiles = _tile_bboxes(spec.bbox)
    with ThreadPoolExecutor(max_workers=min(6, len(tiles))) as pool:
        xml_tiles = list(pool.map(_download_osm_api_tile, tiles))
    nodes: dict[int, dict] = {}
    ways: dict[int, dict] = {}
    for raw in xml_tiles:
        root = ET.fromstring(raw)
        for el in root.findall("node"):
            node_id = int(el.attrib["id"])
            nodes[node_id] = {
                "type": "node",
                "id": node_id,
                "lat": float(el.attrib["lat"]),
                "lon": float(el.attrib["lon"]),
                "tags": _tags(el),
            }
        for el in root.findall("way"):
            way_id = int(el.attrib["id"])
            ways[way_id] = {
                "type": "way",
                "id": way_id,
                "nodes": [int(nd.attrib["ref"]) for nd in el.findall("nd")],
                "tags": _tags(el),
            }

    streets = []
    buildings = []
    stops = []
    for way_id in sorted(ways):
        way = ways[way_id]
        tags = way["tags"]
        geometry = []
        missing = False
        for node_id in way["nodes"]:
            node = nodes.get(node_id)
            if node is None:
                missing = True
                break
            geometry.append({"lat": node["lat"], "lon": node["lon"]})
        if missing or not geometry:
            continue
        if "highway" in tags:
            streets.append({"type": "way", "id": way_id, "tags": tags, "geometry": geometry})
        if "building" in tags:
            lat = sum(p["lat"] for p in geometry) / len(geometry)
            lon = sum(p["lon"] for p in geometry) / len(geometry)
            buildings.append({"type": "way", "id": way_id, "center": {"lat": lat, "lon": lon}, "tags": tags})
    for node_id in sorted(nodes):
        node = nodes[node_id]
        tags = node["tags"]
        if (
            tags.get("railway") in {"station", "tram_stop", "halt"}
            or tags.get("public_transport") in {"platform", "stop_position"}
            or tags.get("amenity") == "ferry_terminal"
            or tags.get("station") == "subway"
        ):
            stops.append({"type": "node", "id": node_id, "lat": node["lat"], "lon": node["lon"], "tags": tags})
        if "building" in tags:
            buildings.append({"type": "node", "id": node_id, "lat": node["lat"], "lon": node["lon"], "center": {"lat": node["lat"], "lon": node["lon"]}, "tags": tags})
    return {
        "bbox": spec.bbox,
        "source_api": "https://api.openstreetmap.org/api/0.6/map",
        "downloaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "responses": {
            "streets": {"elements": streets},
            "stops": {"elements": stops},
            "buildings": {"elements": buildings},
        },
    }


def _fresh_extract(spec: CitySpec) -> dict:
    global _OVERPASS_AVAILABLE
    if _OVERPASS_AVAILABLE is not False:
        try:
            payload = {
                "bbox": spec.bbox,
                "source_api": "overpass",
                "downloaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "responses": {name: _post_overpass(query) for name, query in _queries(spec.bbox).items()},
            }
            _OVERPASS_AVAILABLE = True
            return payload
        except Exception:
            _OVERPASS_AVAILABLE = False
    return _osm_api_extract(spec)


def load_extract(spec: CitySpec, cache_dir: str | Path = "data/osm", refresh: bool = False) -> tuple[dict, str]:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / f"{spec.key}.osm.json.gz"
    sha_path = cache / f"{spec.key}.osm.sha256"
    if path.exists() and sha_path.exists() and not refresh:
        raw = gzip.decompress(path.read_bytes())
        payload = json.loads(raw.decode("utf-8"))
        checksum = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
        recorded = sha_path.read_text().strip().split()[0]
        if checksum != recorded:
            raise ValueError(f"OSM cache checksum mismatch for {spec.key}")
        return payload, checksum

    payload = _fresh_extract(spec)
    checksum = hashlib.sha256(_canonical_bytes(payload)).hexdigest()
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    if len(raw) > MAX_DOWNLOAD_BYTES * 2:
        raise ValueError(f"combined OSM extract for {spec.key} exceeds cache size cap")
    path.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    sha_path.write_text(f"{checksum}  {path.name}\n")
    return payload, checksum


def _project(lat: float, lon: float, spec: CitySpec, size: int) -> tuple[float, float]:
    south, west, north, east = spec.bbox
    x = (lon - west) / (east - west) * (size - 1)
    y = (north - lat) / (north - south) * (size - 1)
    return y, x


def _cardinal_segment(a: tuple[int, int], b: tuple[int, int]) -> Iterable[tuple[int, int]]:
    y, x = a
    ty, tx = b
    yield y, x
    # Move the longer axis first in alternating passes. This deliberately uses
    # cardinal steps so the four-neighbour model never sees diagonal-only roads.
    while (y, x) != (ty, tx):
        if x != tx and (y == ty or abs(tx - x) >= abs(ty - y)):
            x += 1 if tx > x else -1
        elif y != ty:
            y += 1 if ty > y else -1
        elif x != tx:
            x += 1 if tx > x else -1
        yield y, x


def _rasterize_line(points: list[tuple[float, float]], size: int) -> set[tuple[int, int]]:
    if len(points) < 2:
        return set()
    cells: set[tuple[int, int]] = set()
    for (ay, ax), (by, bx) in zip(points, points[1:]):
        steps = max(2, int(math.ceil(max(abs(by - ay), abs(bx - ax)) * 2)))
        previous: tuple[int, int] | None = None
        for i in range(steps + 1):
            t = i / steps
            yy = round(ay + (by - ay) * t)
            xx = round(ax + (bx - ax) * t)
            cur = (int(yy), int(xx))
            if previous is None:
                seq = [cur]
            else:
                seq = list(_cardinal_segment(previous, cur))[1:]
            for y, x in seq:
                if 0 <= y < size and 0 <= x < size:
                    cells.add((y, x))
                    # Real streets are wider than one five-metre raster line. One
                    # orthogonal dilation preserves connectivity without diagonal leakage.
                    if y + 1 < size:
                        cells.add((y + 1, x))
                    if x + 1 < size:
                        cells.add((y, x + 1))
            previous = cur
    return cells


def _nearest_walkable(y: float, x: float, walkable_xy: np.ndarray) -> tuple[int, int]:
    d2 = (walkable_xy[:, 0] - y) ** 2 + (walkable_xy[:, 1] - x) ** 2
    row = walkable_xy[int(np.argmin(d2))]
    return int(row[0]), int(row[1])


def rasterize(payload: dict, spec: CitySpec, checksum: str, size: int = 256, max_dots: int = 2000) -> CityGrid:
    walkable = np.zeros((size, size), dtype=bool)
    ways: list[Way] = []
    cell_to_ways: dict[tuple[int, int], list[int]] = {}

    for el in payload["responses"]["streets"].get("elements", []):
        if el.get("type") != "way" or "geometry" not in el:
            continue
        points = [_project(p["lat"], p["lon"], spec, size) for p in el["geometry"]]
        cells = sorted(_rasterize_line(points, size))
        if len(cells) < 2:
            continue
        tags = el.get("tags", {})
        name = tags.get("name", "")
        highway = tags.get("highway", "")
        bridge = tags.get("bridge") in {"yes", "true", "viaduct"} or any(
            token in name.casefold() for token in ("pont", "bridge", "brug", "ponte")
        )
        way = Way(int(el["id"]), name, bridge, highway, np.asarray(cells, dtype=np.int32))
        ways.append(way)
        for y, x in cells:
            walkable[y, x] = True
            cell_to_ways.setdefault((int(y), int(x)), []).append(way.osm_id)

    walkable_xy = np.argwhere(walkable)
    if len(walkable_xy) == 0:
        raise ValueError(f"no walkable OSM streets rasterized for {spec.key}")

    stop_cells: list[tuple[int, int, int]] = []
    south, west, north, east = spec.bbox
    for el in payload["responses"]["stops"].get("elements", []):
        if "lat" not in el or "lon" not in el:
            continue
        lat, lon = float(el["lat"]), float(el["lon"])
        if not (south <= lat <= north and west <= lon <= east):
            continue
        fy, fx = _project(lat, lon, spec, size)
        y, x = _nearest_walkable(fy, fx, walkable_xy)
        score = 2 if el.get("tags", {}).get("railway") == "station" or el.get("tags", {}).get("station") == "subway" else 1
        stop_cells.append((score, int(el.get("id", 0)), y * size + x))

    # Deterministic, spread-out transit exits. Prefer stations, then take a
    # spatially separated greedy subset of at most six real stop nodes.
    stop_cells.sort(key=lambda row: (-row[0], row[1]))
    unique_cells = sorted({flat for _, _, flat in stop_cells})
    chosen: list[int] = []
    if unique_cells:
        chosen.append(unique_cells[0])
        while len(chosen) < min(6, len(unique_cells)):
            best = max(
                (c for c in unique_cells if c not in chosen),
                key=lambda c: min((c // size - s // size) ** 2 + (c % size - s % size) ** 2 for s in chosen),
            )
            chosen.append(best)
    exits = np.zeros((size, size), dtype=bool)
    exit_points = []
    for flat in chosen:
        y, x = divmod(flat, size)
        exits[y, x] = True
        exit_points.append((y, x))

    dots: list[tuple[float, float]] = []
    for el in payload["responses"]["buildings"].get("elements", []):
        center = el.get("center") or {}
        if "lat" not in center or "lon" not in center:
            if el.get("type") == "node" and "lat" in el:
                center = el
            else:
                continue
        y, x = _project(float(center["lat"]), float(center["lon"]), spec, size)
        if 0 <= y < size and 0 <= x < size:
            dots.append((y, x))
    if len(dots) > max_dots:
        idx = np.linspace(0, len(dots) - 1, max_dots).round().astype(int)
        dots = [dots[int(i)] for i in idx]

    return CityGrid(
        spec=spec,
        size=size,
        walkable=walkable,
        exits=exits,
        exit_points=np.asarray(exit_points, dtype=np.int32),
        buildings=np.asarray(dots, dtype=np.float32),
        ways=ways,
        checksum=checksum,
        cell_to_ways=cell_to_ways,
    )


def load_city(key: str, size: int = 256, cache_dir: str | Path = "data/osm", refresh: bool = False) -> CityGrid:
    spec = CITIES[key]
    payload, checksum = load_extract(spec, cache_dir=cache_dir, refresh=refresh)
    return rasterize(payload, spec, checksum, size=size)


def expand_edit_ids(city: CityGrid, closed_ids: Iterable[int]) -> set[int]:
    """Expand a clicked way to all real OSM ways carrying the same street name.

    OSM commonly splits one bridge or street into carriageway, cycleway, and
    sidewalk ways. Closing only one segment would leave a parallel line open;
    the edit object is therefore the named street/bridge, while every expanded
    id is still a real OSM way.
    """
    seed = set(int(i) for i in closed_ids)
    names = {w.name for w in city.ways if w.osm_id in seed and w.name}
    expanded = set(seed)
    if names:
        expanded.update(w.osm_id for w in city.ways if w.name in names)
    return expanded


def closed_walkable(city: CityGrid, closed_ids: Iterable[int]) -> np.ndarray:
    walk = city.walkable.copy()
    closed = expand_edit_ids(city, closed_ids)
    for way in city.ways:
        if way.osm_id in closed:
            for y, x in way.cells:
                # A closure is a physical barricade: if a raster cell is part
                # of the closed street, parallel overlapping OSM lines do not
                # keep that five-metre cell open.
                walk[int(y), int(x)] = False
    return walk


def way_table(city: CityGrid) -> list[dict]:
    return [
        {
            "id": w.osm_id,
            "name": w.name or f"way {w.osm_id}",
            "bridge": w.bridge,
            "highway": w.highway,
            "cells": int(len(w.cells)),
        }
        for w in sorted(city.ways, key=lambda item: (not item.bridge, item.name, item.osm_id))
    ]


if __name__ == "__main__":
    for key in CITIES:
        city = load_city(key)
        print(key, city.label, "walkable", int(city.walkable.sum()), "exits", len(city.exit_points), "ways", len(city.ways), "checksum", city.checksum[:12])
