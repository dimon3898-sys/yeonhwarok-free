"""Offline, bounded acquisition planning and service-response CPU decoding.

No function performs transport. A ``planned`` result is a list of requests for
the bounded downloader, never evidence that a service accepted those requests.
Caller-supplied source versions, index records, COG layouts and actual coordinate
vectors are used directly; dataset names, country bounds and tile existence are
not invented. Each response is limited to 64 MiB, with additional cell/tile caps.
"""
from copy import deepcopy
from dataclasses import dataclass
from io import StringIO
import json
import math
import re
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import numpy as np
from osgeo import osr

from .download_contract import AcquisitionPlan, DownloadRequest
from .model import DataError, RasterData, sha256, split_dateline, validate_bbox
from .providers import DataRequest


_MAX_BYTES = 64 * 1024 * 1024
_NS = {"wmts": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}
_IDENTIFIER = r"[A-Za-z_][A-Za-z_0-9]*"
_FLOAT = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"


def _integer(value, label, *, maximum=None):
    if (isinstance(value, bool) or not isinstance(value, int) or value <= 0
            or maximum is not None and value > maximum):
        raise DataError(f"{label} must be a positive bounded integer")
    return value


def _budget(value):
    return _integer(value, "max_bytes", maximum=_MAX_BYTES)


def _raw(data, expected_sha256=None, *, maximum=_MAX_BYTES):
    if not isinstance(data, bytes) or not data or len(data) > maximum:
        raise DataError("nonempty bounded response bytes are required")
    digest = sha256(data)
    if expected_sha256 is not None:
        if (not isinstance(expected_sha256, str)
                or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256)):
            raise DataError("expected SHA-256 must contain 64 hexadecimal characters")
        if digest != expected_sha256.lower():
            raise DataError("response SHA-256 mismatch")
    return digest


def _text(data, *, maximum=8*1024*1024):
    _raw(data, maximum=maximum)
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataError("response must be UTF-8 text") from exc
    if "\x00" in text:
        raise DataError("response contains NUL characters")
    return text


def _identity(url, source_id, source_version):
    if (not isinstance(source_id, str) or not source_id.strip()
            or not isinstance(source_version, str) or not source_version.strip()):
        raise DataError("explicit pinned source identity and version are required")
    DownloadRequest(url, source_id, source_version, 1).validate()


def _intersection(a, b):
    west, south = max(a[0], b[0]), max(a[1], b[1])
    east, north = min(a[2], b[2]), min(a[3], b[3])
    return (west, south, east, north) if west < east and south < north else None


def _spacing(axis, label, *, ascending=False):
    if axis.ndim != 1 or len(axis) < 2 or not np.isfinite(axis).all():
        raise DataError(f"{label} needs at least two finite actual coordinate values")
    delta = float((axis[-1] - axis[0]) / (len(axis) - 1))
    if (delta == 0 or ascending and delta < 0
            or not np.all(np.diff(axis) * np.sign(delta) > 0)
            or not np.allclose(axis, axis[0] + np.arange(len(axis)) * delta, rtol=0, atol=1e-9)):
        raise DataError(f"unsupported nonrectilinear or reversed {label} axis")
    return delta


def _index_span(origin, step, count, low, high, *, centers=True, first_index=0, last_index=None):
    """Conservative index candidates, then exact checks against actual geometry.

    No fixed epsilon snaps requested boundaries: even a very narrow positive
    interval can contain a center or straddle a tile edge.
    """
    shift = .5 if centers else 0
    endpoints = [(value-origin)/step-shift for value in (low, high)]
    if not all(math.isfinite(value) for value in endpoints):
        raise DataError("grid index arithmetic exceeds finite supported precision")
    first = max(first_index, 0, math.floor(min(endpoints))-2)
    last = min(count-1 if last_index is None else last_index, count-1, math.ceil(max(endpoints))+2)

    def intersects(index):
        if centers:
            value = origin + (index+.5)*step
            return low <= value < high
        edge = origin + index*step
        other_edge = edge + step
        return min(edge, other_edge) < high and max(edge, other_edge) > low

    checks = 0
    while first <= last and not intersects(first):
        first += 1
        checks += 1
        if checks > 16:
            raise DataError("grid spacing collapses at coordinate precision")
    while first <= last and not intersects(last):
        last -= 1
        checks += 1
        if checks > 32:
            raise DataError("grid spacing collapses at coordinate precision")
    return first, last


@dataclass(frozen=True)
class IndexedTerrainTile:
    """An existing index entry, with its declared footprint and object identity.

    ``sha256`` is the full object's hash, so it is used only for a full-object
    fallback. Range/probe requests cannot use it as a delivered-response hash.
    Index footprints select candidates; the actual TIFF transform governs crop.
    """
    source_id: str
    source_version: str
    url: str
    bbox: tuple
    object_bytes: int | None = None
    etag: str | None = None
    sha256: str | None = None


def build_copernicus_index_request(*, index_url, base_url, source_id,
                                  source_version, max_bytes=8*1024*1024,
                                  expected_sha256=None, expected_etag=None,
                                  observed_source_version=None,
                                  tile_prefix="Copernicus_DSM_COG_10") -> AcquisitionPlan:
    """Plan a bounded GET of a caller-declared public tile-key text index.

    Neither index URL nor live response format is discovered or verified here.
    The supported key grammar is the naming scheme in supplied source metadata:
    ``PREFIX_N37_00_E128_00_DEM`` or that stem followed by ``/STEM.tif``.
    ``base_url`` is the caller's pinned object-root URL, not a guessed mirror.
    Version is supplied explicitly; filenames do not establish a release year.
    """
    cap = _budget(max_bytes)
    _identity(index_url, source_id, source_version)
    _identity(base_url, source_id, source_version)
    if urlsplit(base_url).query:
        raise DataError("tile object base URL must not contain a query")
    if not isinstance(tile_prefix, str) or not re.fullmatch(r"Copernicus_DSM_COG_\d{2}", tile_prefix):
        raise DataError("tile_prefix must declare the supported Copernicus naming prefix")
    if observed_source_version is not None:
        if not isinstance(observed_source_version, str) or not observed_source_version.strip():
            raise DataError("observed index source version must be nonempty text")
        if observed_source_version != source_version:
            return AcquisitionPlan("version_changed", "COPERNICUS_PUBLIC_INDEX_TEXT",
                                   metadata={"reason": "PINNED_INDEX_VERSION_MISMATCH",
                                             "sourceVersion": source_version,
                                             "observedSourceVersion": observed_source_version})
    declarations = {"indexURL": index_url, "baseURL": base_url.rstrip("/"),
                    "sourceId": source_id, "sourceVersion": source_version,
                    "tilePrefix": tile_prefix, "format": "COPERNICUS_TILE_KEYS_TEXT"}
    declaration_hash = sha256(json.dumps(declarations, sort_keys=True, separators=(",", ":")).encode())
    outgoing = DownloadRequest(index_url, source_id, source_version, cap,
                               expected_sha256=expected_sha256, expected_etag=expected_etag,
                               source_metadata_sha256=declaration_hash)
    return AcquisitionPlan("planned", "COPERNICUS_PUBLIC_INDEX_TEXT", (outgoing,),
                           metadata={**declarations, "sourceMetadataSha256": declaration_hash,
                                     "liveIndexFormat": "UNVERIFIED_NOT_ARCHIVED",
                                     "footprintMeaning": "NOMINAL_ONE_DEGREE_INDEX_CANDIDATE",
                                     "actualTransformRequired": True, "downloadExecuted": False},
                           warnings=("LIVE_INDEX_FORMAT_AND_ACCESS_UNVERIFIED",))


def parse_copernicus_index(data: bytes, plan: AcquisitionPlan, *,
                           observed_source_version=None, max_tiles=100_000):
    """Return ``(tuple[IndexedTerrainTile], raw_index_sha256)`` for listed keys.

    Usage: build the index request, cache its response, parse it, then pass the
    records and raw SHA to ``plan_copernicus_tiles(...,
    index_metadata_sha256=raw_sha)``. Each UTF-8 nonblank line must be a listed
    directory stem or its exactly matching relative TIFF key. URLs are expanded
    only for those entries. No tile names are enumerated from geographic bounds.

    Nominal one-degree footprints identify candidates; TIFF PixelIsPoint edges,
    spacing, missing values and source object hashes still require real metadata.
    This supported text grammar remains LIVE FORMAT UNVERIFIED until an actual
    index response is supplied and checked. No version is inferred from keys.
    """
    _integer(max_tiles, "max_tiles", maximum=200_000)
    if (not isinstance(plan, AcquisitionPlan) or plan.status != "planned"
            or plan.stage != "COPERNICUS_PUBLIC_INDEX_TEXT" or len(plan.requests) != 1):
        raise DataError("a planned Copernicus public text-index request is required")
    request, metadata = plan.requests[0], plan.metadata
    if (request.url != metadata["indexURL"] or request.source_id != metadata["sourceId"]
            or request.source_version != metadata["sourceVersion"]
            or request.source_metadata_sha256 != metadata["sourceMetadataSha256"]):
        raise DataError("index plan source identity/version differs from download request")
    if observed_source_version is not None:
        if not isinstance(observed_source_version, str) or not observed_source_version.strip():
            raise DataError("observed index source version must be nonempty text")
        if observed_source_version != request.source_version:
            raise DataError("PINNED_INDEX_VERSION_MISMATCH: observed index version differs")
    digest = _raw(data, request.expected_sha256, maximum=request.max_bytes)
    text = _text(data, maximum=request.max_bytes)
    prefix = metadata["tilePrefix"]
    stem_pattern = (re.escape(prefix) + r"_(?P<lathem>[NS])(?P<lat>\d{2})_00_"
                    r"(?P<lonhem>[EW])(?P<lon>\d{3})_00_DEM")
    records, seen_urls, seen_origins = [], set(), set()
    for line_number, raw_line in enumerate(StringIO(text), 1):
        if line_number > 2*max_tiles+32:
            raise DataError("tile-index line budget exceeded")
        key = raw_line.strip()
        if not key:
            continue
        pieces = key.split("/")
        if len(pieces) == 1:
            stem = pieces[0]
        elif len(pieces) == 2 and pieces[1] == pieces[0] + ".tif":
            stem = pieces[0]
        else:
            raise DataError("unsupported tile index key; relative matching TIFF keys are required")
        match = re.fullmatch(stem_pattern, stem, flags=re.ASCII)
        if match is None:
            raise DataError("unsupported Copernicus tile key or product prefix")
        south = int(match["lat"]) * (-1 if match["lathem"] == "S" else 1)
        west = int(match["lon"]) * (-1 if match["lonhem"] == "W" else 1)
        if not -90 <= south < 90 or not -180 <= west < 180:
            raise DataError("tile key nominal footprint exceeds geographic bounds")
        url = metadata["baseURL"] + "/" + stem + "/" + stem + ".tif"
        origin = (west, south)
        if url in seen_urls or origin in seen_origins:
            raise DataError("duplicate tile index entry or ambiguous geographic origin")
        if len(records) >= max_tiles:
            raise DataError("tile-index record budget exceeded")
        _identity(url, request.source_id, request.source_version)
        records.append(IndexedTerrainTile(request.source_id, request.source_version, url,
                                          (west, south, west+1, south+1)))
        seen_urls.add(url)
        seen_origins.add(origin)
    if not records:
        raise DataError("tile index contains no supported listed keys")
    return tuple(records), digest


def plan_copernicus_tiles(request: DataRequest, indexed_tiles, *, source_id,
                         source_version, metadata_probe_bytes=16384,
                         max_bytes=_MAX_BYTES, index_metadata_sha256=None,
                         allow_full_tile=False, max_tiles=256,
                         max_total_bytes=512*1024*1024) -> AcquisitionPlan:
    """Intersect supplied index entries; probe metadata or explicitly GET tiles.

    Full-tile fallback requires ``allow_full_tile=True`` and a known object size
    within the response cap. No absent tile names/URLs are synthesized, and a
    partial index is not evidence of complete coverage or valid terrain cells.
    The caller can tighten the hard batch limits of 256 tiles and 512 MiB total
    delivered bytes; the aggregate limit also applies to metadata probes.
    """
    request.validate()
    cap = _budget(max_bytes)
    _integer(max_tiles, "max_tiles", maximum=256)
    _integer(max_total_bytes, "max_total_bytes", maximum=512*1024*1024)
    _integer(metadata_probe_bytes, "metadata_probe_bytes", maximum=cap)
    parts = split_dateline(request.bbox)
    selected, no_entries = [], []
    seen = set()
    for tile in indexed_tiles:
        if not isinstance(tile, IndexedTerrainTile):
            raise DataError("terrain index must contain IndexedTerrainTile entries")
        _identity(tile.url, tile.source_id, tile.source_version)
        bounds = validate_bbox(tile.bbox)
        if bounds[0] >= bounds[2]:
            raise DataError("index tile footprints must not cross the dateline")
        if tile.object_bytes is not None:
            _integer(tile.object_bytes, "object_bytes")
        if any(_intersection(part, bounds) for part in parts):
            if tile.source_id != source_id or tile.source_version != source_version:
                return AcquisitionPlan("version_changed", "COPERNICUS_INDEX",
                                       metadata={"reason": "INDEX_SOURCE_OR_VERSION_MISMATCH"})
            key = (tile.url, tile.source_id, tile.source_version)
            if key in seen:
                raise DataError("duplicate intersecting terrain index entry")
            if len(selected) >= max_tiles:
                raise DataError("selected terrain tiles exceed max_tiles")
            seen.add(key)
            selected.append(tile)
    for part in parts:
        if not any(_intersection(part, tile.bbox) for tile in selected):
            no_entries.append(list(part))
    coverage = {"requestedBBox": list(request.bbox), "requestedParts": list(parts),
                "indexedFootprints": [list(tile.bbox) for tile in selected],
                "partsWithNoIndexEntry": no_entries,
                "catalogCompleteness": "UNVERIFIED", "paddingApplied": False}
    if not selected:
        return AcquisitionPlan("unavailable", "COPERNICUS_INDEX", coverage=coverage,
                               metadata={"reason": "NO_SUPPLIED_INDEX_INTERSECTION"})
    outgoing, records, total_bytes = [], [], 0
    for tile in selected:
        if allow_full_tile:
            if tile.object_bytes is None or tile.object_bytes > cap:
                return AcquisitionPlan("unavailable", "COPERNICUS_BOUNDED_FULL_TILE",
                                       coverage=coverage,
                                       metadata={"reason": "FULL_TILE_SIZE_UNKNOWN_OR_OVER_CAP"})
            total_bytes += tile.object_bytes
            if total_bytes > max_total_bytes:
                raise DataError("terrain full-tile batch exceeds max_total_bytes")
            outgoing.append(DownloadRequest(tile.url, source_id, source_version, tile.object_bytes,
                            expected_sha256=tile.sha256, expected_etag=tile.etag,
                            bbox=tuple(tile.bbox), total_object_bytes=tile.object_bytes,
                            source_metadata_sha256=index_metadata_sha256))
        else:
            count = min(metadata_probe_bytes, tile.object_bytes or metadata_probe_bytes)
            total_bytes += count
            if total_bytes > max_total_bytes:
                raise DataError("terrain metadata-probe batch exceeds max_total_bytes")
            outgoing.append(DownloadRequest(tile.url, source_id, source_version, count,
                            byte_range=(0, count - 1), expected_etag=tile.etag,
                            bbox=tuple(tile.bbox), total_object_bytes=tile.object_bytes,
                            source_metadata_sha256=index_metadata_sha256))
        records.append({"url": tile.url, "objectBytes": tile.object_bytes,
                        "wholeObjectSha256": tile.sha256, "etag": tile.etag})
    return AcquisitionPlan("planned", "COPERNICUS_BOUNDED_FULL_TILE" if allow_full_tile
                           else "COPERNICUS_COG_METADATA_REQUIRED", tuple(outgoing),
                           metadata={"sourceId": source_id, "sourceVersion": source_version,
                                     "indexMetadataSha256": index_metadata_sha256, "objects": records,
                                     "plannedResponseBytes": total_bytes, "maxTotalBytes": max_total_bytes,
                                     "selectedTileCount": len(selected), "maxTiles": max_tiles,
                                     "actualTransformRequired": True, "downloadExecuted": False},
                           coverage=coverage,
                           warnings=("INDEX_FOOTPRINTS_DO_NOT_PROVE_COMPLETE_VALID_GRID",))


@dataclass(frozen=True)
class CogBlock:
    row: int
    column: int
    offset: int
    byte_count: int


@dataclass(frozen=True)
class CogLevel:
    """Actual IFD level, transform and compressed block locations from metadata."""
    level_id: str
    width: int
    height: int
    transform: tuple
    block_width: int
    block_height: int
    blocks: tuple


@dataclass(frozen=True)
class CogLayout:
    tile: IndexedTerrainTile
    levels: tuple
    metadata_sha256: str
    crs: str = "EPSG:4326"
    dtype: str = "Float32"
    pixel_registration: str = "Point"


def plan_cog_ranges(layout: CogLayout, request: DataRequest, *, level_id="native",
                    max_bytes=_MAX_BYTES, max_blocks=4096) -> AcquisitionPlan:
    """Plan exact compressed blocks from supplied, object-bound IFD metadata.

    This function does not discover offsets, decode partial TIFFs or assert COG
    conformance. ``level_id`` explicitly selects an advertised overview; no
    overview or resolution is invented. Individual ranges need their own hash
    when known, not the whole object's SHA. The downloader verifies 206,
    Content-Range, total size and ETag before any decoder can consume a block.
    """
    request.validate()
    cap = _budget(max_bytes)
    _integer(max_blocks, "max_blocks")
    if not isinstance(layout, CogLayout) or not isinstance(layout.tile, IndexedTerrainTile):
        raise DataError("a supplied CogLayout and indexed tile are required")
    tile = layout.tile
    _identity(tile.url, tile.source_id, tile.source_version)
    _integer(tile.object_bytes, "known COG object_bytes")
    if layout.crs != request.crs or layout.dtype != "Float32" or layout.pixel_registration not in ("Point", "Area"):
        raise DataError("COG plan requires geographic Float32 terrain with explicit registration")
    levels = [level for level in layout.levels if level.level_id == level_id]
    if len(levels) != 1:
        raise DataError("exactly one advertised COG level must match level_id")
    level = levels[0]
    for value, label in ((level.width, "width"), (level.height, "height"),
                         (level.block_width, "block_width"), (level.block_height, "block_height")):
        _integer(value, label)
    t = level.transform
    if (not isinstance(t, (list, tuple)) or len(t) != 6
            or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in t)
            or t[1] <= 0 or t[2] != 0 or t[4] != 0 or t[5] == 0):
        raise DataError("COG metadata requires a finite rectilinear corner transform")
    block_columns = math.ceil(level.width / level.block_width)
    block_rows = math.ceil(level.height / level.block_height)
    by_position = {}
    for block in level.blocks:
        if (not isinstance(block, CogBlock) or any(isinstance(v, bool) or not isinstance(v, int)
                for v in (block.row, block.column, block.offset, block.byte_count))
                or not 0 <= block.row < block_rows or not 0 <= block.column < block_columns
                or block.offset < 0 or block.byte_count <= 0
                or block.offset + block.byte_count > tile.object_bytes):
            raise DataError("invalid COG compressed block offset/count")
        key = (block.row, block.column)
        if key in by_position:
            raise DataError("duplicate COG block position")
        by_position[key] = block
    if len(by_position) != block_rows * block_columns:
        raise DataError("COG level metadata does not cover every source block")
    if not all(math.isfinite(v) for v in (t[0] + level.width*t[1], t[3] + level.height*t[5])):
        raise DataError("COG transform produces nonfinite source edges")
    wanted = set()
    windows = []
    for west, south, east, north in split_dateline(request.bbox):
        # Derive inclusive source index bounds without allocating global axes.
        col_first, col_last = _index_span(t[0], t[1], level.width, west, east)
        row_first, row_last = _index_span(t[3], t[5], level.height, south, north)
        if col_first > col_last or row_first > row_last:
            continue
        windows.append([col_first, row_first, col_last-col_first+1, row_last-row_first+1])
        row_start, row_stop = row_first // level.block_height, row_last // level.block_height
        col_start, col_stop = col_first // level.block_width, col_last // level.block_width
        count = (row_stop - row_start + 1) * (col_stop - col_start + 1)
        if count > max_blocks:
            raise DataError("COG block request exceeds max_blocks")
        wanted.update((row, col) for row in range(row_start, row_stop + 1)
                      for col in range(col_start, col_stop + 1))
    if len(wanted) > max_blocks:
        raise DataError("COG block request exceeds max_blocks")
    if not wanted:
        return AcquisitionPlan("unavailable", "COPERNICUS_COG_BLOCKS",
                               metadata={"reason": "NO_SOURCE_SAMPLE_CENTERS"})
    outgoing = []
    for key in sorted(wanted):
        block = by_position[key]
        if block.byte_count > cap:
            raise DataError("compressed COG block exceeds response cap")
        outgoing.append(DownloadRequest(tile.url, tile.source_id, tile.source_version,
                        block.byte_count, byte_range=(block.offset, block.offset + block.byte_count - 1),
                        expected_etag=tile.etag, total_object_bytes=tile.object_bytes,
                        bbox=tuple(request.bbox), resolution={"spacingDegrees": [abs(t[1]), abs(t[5])]},
                        source_metadata_sha256=layout.metadata_sha256))
    return AcquisitionPlan("planned", "COPERNICUS_COG_BLOCKS", tuple(outgoing),
                           metadata={"levelId": level_id, "transform": list(t),
                                     "pixelRegistration": layout.pixel_registration,
                                     "dimensions": [level.width, level.height],
                                     "wholeObjectSha256": tile.sha256,
                                     "sourceMetadataSha256": layout.metadata_sha256,
                                     "offsetAuthority": "SUPPLIED_OBJECT_BOUND_IFD_METADATA",
                                     "rangeDecodeExecuted": False},
                           coverage={"requestedBBox": list(request.bbox), "sourcePixelWindows": windows},
                           warnings=("EXPLICIT_SOURCE_OVERVIEW_SELECTED",) if level_id != "native" else ())


def _dds(text):
    """Strict supported DAP2 Grid grammar, not an executable/schema interpreter."""
    pattern = (r"\s*Dataset\s*\{(?P<globals>.*?)Grid\s*\{\s*ARRAY:\s*"
               r"(?P<dtype>\w+)\s+(?P<array>" + _IDENTIFIER + r")\s*"
               r"(?P<dims>(?:\[\s*" + _IDENTIFIER + r"\s*=\s*\d+\s*\])+);\s*"
               r"MAPS:(?P<maps>.*?)\}\s*(?P<grid>" + _IDENTIFIER + r");\s*"
               r"\}\s*(?P<dataset>[^;{}]+);\s*")
    match = re.fullmatch(pattern, text, re.S)
    if match is None or match["dtype"] != "Int16" or match["array"] != match["grid"]:
        raise DataError("DDS must declare one signed Int16 DAP Grid")
    dimension = r"\[\s*(" + _IDENTIFIER + r")\s*=\s*(\d+)\s*\]"
    dims = [(name, int(size)) for name, size in re.findall(dimension, match["dims"])]
    if len(dims) != 2 or dims[0][0] == dims[1][0] or any(size <= 0 for _, size in dims):
        raise DataError("DDS elevation must have two nonempty distinct dimensions")
    maps = []
    for declaration in match["maps"].split(";"):
        if not declaration.strip():
            continue
        item = re.fullmatch(r"\s*Float64\s+(" + _IDENTIFIER + r")\s*" + dimension + r"\s*", declaration)
        if not item or item[1] != item[2]:
            raise DataError("DDS maps must be named Float64 coordinate axes")
        maps.append((item[1], int(item[3])))
    if maps != dims:
        raise DataError("DDS map dimensions/order must match grid [latitude][longitude]")
    global_names, standalone_axes = set(), set()
    for declaration in match["globals"].split(";"):
        if not declaration.strip():
            continue
        scalar = re.fullmatch(r"\s*String\s+" + _IDENTIFIER + r"\s*", declaration)
        axis = re.fullmatch(r"\s*Float64\s+(" + _IDENTIFIER + r")\s*" + dimension + r"\s*", declaration)
        if not scalar and (not axis or axis[1] != axis[2] or (axis[1], int(axis[3])) not in maps):
            raise DataError("unsupported or conflicting DDS global variable")
        name = axis[1] if axis else declaration.split()[1]
        if name in global_names:
            raise DataError("duplicate DDS global variable")
        global_names.add(name)
        if axis:
            standalone_axes.add(name)
    return {"variable": match["array"], "dimensions": dims,
            "standaloneAxes": standalone_axes, "datasetPath": match["dataset"].strip()}


def _das(text):
    token_pattern = re.compile(r'\s+|//[^\n]*|"(?:\\.|[^"\\])*"|[{};,]|' + _FLOAT + r'|' + _IDENTIFIER)
    tokens, position = [], 0
    for match in token_pattern.finditer(text):
        if match.start() != position:
            raise DataError("unsupported DAS token")
        position = match.end()
        token = match[0]
        if not token.isspace() and not token.startswith("//"):
            tokens.append(token)
            if len(tokens) > 200_000:
                raise DataError("DAS token budget exceeded")
    if position != len(text):
        raise DataError("unsupported DAS trailing content")
    index = 0

    def take(expected=None):
        nonlocal index
        if index >= len(tokens):
            raise DataError("truncated DAS")
        value = tokens[index]
        index += 1
        if expected is not None and value != expected:
            raise DataError("invalid DAS container")
        return value

    def container(depth=0):
        if depth > 32:
            raise DataError("DAS nesting depth exceeds supported metadata")
        result = {}
        take("{")
        while index < len(tokens) and tokens[index] != "}":
            first = take()
            if index < len(tokens) and tokens[index] == "{":
                name, value = first, container(depth+1)
            else:
                kind, name, values = first, take(), []
                if kind not in {"String", "Byte", "Int16", "UInt16", "Int32", "UInt32", "Float32", "Float64"}:
                    raise DataError("unsupported DAS attribute type")
                while True:
                    token = take()
                    try:
                        if kind == "String":
                            value = json.loads(token)
                            if not isinstance(value, str):
                                raise ValueError()
                        elif kind.startswith("Float"):
                            value = float(token)
                        else:
                            if not re.fullmatch(r"[+-]?\d+", token):
                                raise ValueError()
                            value = int(token)
                    except (ValueError, json.JSONDecodeError) as exc:
                        raise DataError("invalid DAS attribute value") from exc
                    values.append(value)
                    separator = take()
                    if separator == ";":
                        break
                    if separator != ",":
                        raise DataError("invalid DAS attribute separator")
                value = values[0] if len(values) == 1 else values
            if name in result:
                raise DataError("duplicate DAS attribute/container")
            result[name] = value
        take("}")
        return result

    take("Attributes")
    result = container()
    if index != len(tokens):
        raise DataError("unexpected DAS trailing content")
    return result


def parse_gebco_metadata(dds: bytes, das: bytes, *, source_id, source_version,
                         source_url) -> dict:
    """Validate supplied DDS/DAS; retain declarations without inventing axes.

    Nominal bounds/spacing and node_offset do not establish actual global axis
    direction/endpoints. ``plan_gebco_subset`` therefore requires actual full
    vectors or first returns a bounded coordinate-only request.
    """
    _identity(source_url, source_id, source_version)
    if urlsplit(source_url).query:
        raise DataError("version-pinned DAP dataset URL must not contain a query")
    schema, attrs = _dds(_text(dds)), _das(_text(das))
    latitude, longitude = schema["dimensions"]
    if schema["standaloneAxes"] != {latitude[0], longitude[0]}:
        raise DataError("source DDS requires actual standalone Float64 coordinate variables")
    for (name, _), standard, units, axis in ((latitude, "latitude", "degrees_north", "Y"),
                                           (longitude, "longitude", "degrees_east", "X")):
        declaration = attrs.get(name, {})
        if (not isinstance(declaration, dict) or declaration.get("standard_name") != standard or declaration.get("units") != units
                or declaration.get("axis", axis) != axis):
            raise DataError("DDS/DAS latitude/longitude axis semantics disagree")
    elevation = attrs.get(schema["variable"], {})
    global_attrs = attrs.get("NC_GLOBAL", {})
    if not isinstance(elevation, dict) or not isinstance(global_attrs, dict):
        raise DataError("DAS elevation/global attributes must be containers")
    mapping_name = elevation.get("grid_mapping")
    if not isinstance(mapping_name, str):
        raise DataError("DAS requires an explicit named grid mapping")
    mapping = attrs.get(mapping_name, {})
    if not isinstance(mapping, dict):
        raise DataError("DAS CRS attributes must be a container")
    if (mapping.get("grid_mapping_name") != "latitude_longitude"
            or mapping.get("epsg_code") != "EPSG:4326"):
        raise DataError("GEBCO metadata requires declared EPSG:4326 geographic CRS")
    with osr.ExceptionMgr():
        reference = osr.SpatialReference()
        reference.ImportFromEPSG(4326)
        expected_geodesy = {"semi_major_axis": reference.GetSemiMajor(),
                           "semi_minor_axis": reference.GetSemiMinor(),
                           "inverse_flattening": reference.GetInvFlattening(),
                           "longitude_of_prime_meridian": 0.0}
    for field, expected in expected_geodesy.items():
        if field in mapping and (isinstance(mapping[field], bool)
                or not isinstance(mapping[field], (int, float)) or not math.isfinite(mapping[field])
                or not math.isclose(mapping[field], expected, rel_tol=1e-12, abs_tol=1e-8)):
            raise DataError("declared CRS geodesy conflicts with WGS84")
    if "earth_radius" in mapping:
        raise DataError("declared spherical CRS conflicts with WGS84 ellipsoid")
    if (not isinstance(elevation.get("units"), str)
            or elevation.get("units") not in {"m", "meter", "meters", "metre", "metres"}
            or elevation.get("positive", global_attrs.get("geospatial_vertical_positive")) != "up"):
        raise DataError("GEBCO metadata requires meters, positive up")
    if (elevation.get("scale_factor", 1) != 1 or elevation.get("add_offset", 0) != 0
            or str(elevation.get("_Unsigned", "false")).lower() in {"true", "yes", "1"}):
        raise DataError("packed/unsigned elevation is unsupported")
    digest = sha256(b"DDS\x00" + dds + b"\x00DAS\x00" + das)
    return {"sourceId": source_id, "sourceVersion": source_version, "sourceURL": source_url,
            "variable": schema["variable"], "latitudeName": latitude[0], "longitudeName": longitude[0],
            "globalShape": [latitude[1], longitude[1]], "dtype": "Int16", "crs": "EPSG:4326",
            "units": "m", "positive": "up", "datasetPath": schema["datasetPath"],
            "sourceMetadataSha256": digest, "ddsSha256": sha256(dds), "dasSha256": sha256(das),
            "verticalDatum": elevation.get("vertical_datum", global_attrs.get("geospatial_bounds_vertical_crs")),
            "sourceAttributes": attrs, "globalAxisVerification": "ACTUAL_VECTORS_REQUIRED",
            "globalElevationAcquisitionAllowed": False}


def _dap_url(metadata, expression):
    return metadata["sourceURL"] + ".ascii?" + quote(expression, safe=",:")


def plan_gebco_subset(request: DataRequest, metadata, longitude=None, latitude=None, *,
                      max_cells=1_000_000, max_bytes=_MAX_BYTES) -> AcquisitionPlan:
    """Use actual complete 1D vectors to select half-open bbox centers.

    The DAP stop index is inclusive. Source latitude order is retained. Without
    vectors, request coordinates only; the global elevation grid is prohibited.
    Arrays must match DDS lengths, use conventional longitude, and be regular.
    """
    request.validate()
    cap = _budget(max_bytes)
    _integer(max_cells, "max_cells", maximum=16_000_000)
    _identity(metadata["sourceURL"], metadata["sourceId"], metadata["sourceVersion"])
    rows, columns = metadata["globalShape"]
    lat_name, lon_name = metadata["latitudeName"], metadata["longitudeName"]
    if longitude is None and latitude is None:
        estimated = 32 * (rows + columns) + 8192
        if estimated > cap:
            raise DataError("coordinate-only response exceeds byte budget")
        expression = f"{lon_name}[0:1:{columns-1}],{lat_name}[0:1:{rows-1}]"
        outgoing = DownloadRequest(_dap_url(metadata, expression), metadata["sourceId"],
                                  metadata["sourceVersion"], cap,
                                  source_metadata_sha256=metadata["sourceMetadataSha256"])
        return AcquisitionPlan("planned", "GEBCO_COORDINATE_METADATA_REQUIRED", (outgoing,),
                               metadata={"coordinateOnly": True, "globalElevationRequested": False,
                                         "sourceMetadataSha256": metadata["sourceMetadataSha256"]},
                               coverage={"requestedBBox": list(request.bbox)},
                               warnings=("GLOBAL_AXES_NOT_YET_VERIFIED",))
    if longitude is None or latitude is None:
        raise DataError("both actual full coordinate vectors are required")
    x, y = np.asarray(longitude, dtype=np.float64), np.asarray(latitude, dtype=np.float64)
    if x.shape != (columns,) or y.shape != (rows,):
        raise DataError("actual coordinate-vector lengths must match DDS")
    dx, dy = _spacing(x, "longitude", ascending=True), _spacing(y, "latitude")
    if np.any(x < -180) or np.any(x > 180) or np.any(y < -90) or np.any(y > 90):
        raise DataError("actual axes must use conventional geographic coordinates")
    axis_hash = sha256(x.astype("<f8").tobytes() + y.astype("<f8").tobytes())
    trust_hash = sha256(bytes.fromhex(metadata["sourceMetadataSha256"]) + bytes.fromhex(axis_hash))
    outgoing, subsets, absent = [], [], []
    for part in split_dateline(request.bbox):
        west, south, east, north = part
        cols = np.flatnonzero((x >= west) & (x < east))
        selected_rows = np.flatnonzero((y >= south) & (y < north))
        if not len(cols) or not len(selected_rows):
            absent.append(list(part))
            continue
        cells = len(cols) * len(selected_rows)
        if cells == rows * columns:
            raise DataError("full global elevation acquisition is prohibited")
        if cells > max_cells or 8*cells + 32*(len(cols)+len(selected_rows)) + 64*len(selected_rows) + 8192 > cap:
            raise DataError("GEBCO subset exceeds cell or ASCII byte budget")
        first_row, last_row = int(selected_rows[0]), int(selected_rows[-1])
        first_col, last_col = int(cols[0]), int(cols[-1])
        expression = (f"{metadata['variable']}[{first_row}:1:{last_row}]"
                      f"[{first_col}:1:{last_col}]")
        outgoing.append(DownloadRequest(_dap_url(metadata, expression), metadata["sourceId"],
                        metadata["sourceVersion"], cap, bbox=tuple(part),
                        resolution={"spacingDegrees": [abs(dx), abs(dy)]},
                        source_metadata_sha256=trust_hash))
        subsets.append({"bbox": list(part), "rowIndices": [first_row, 1, last_row],
                        "columnIndices": [first_col, 1, last_col], "shape": [len(selected_rows), len(cols)],
                        "x": x[cols].tolist(), "y": y[selected_rows].tolist(),
                        "spacingDegrees": [dx, dy]})
    if not outgoing:
        return AcquisitionPlan("unavailable", "GEBCO_ASCII_SUBSET",
                               metadata={"reason": "NO_ACTUAL_AXIS_SAMPLE_CENTERS"})
    return AcquisitionPlan("planned", "GEBCO_ASCII_SUBSET", tuple(outgoing),
                           metadata={"subsets": subsets, "axisValuesSha256": axis_hash,
                                     "definitionSha256": metadata["sourceMetadataSha256"],
                                     "sourceMetadataSha256": trust_hash,
                                     "globalElevationRequested": False},
                           coverage={"requestedBBox": list(request.bbox), "absentParts": absent},
                           warnings=("PARTIAL_COORDINATE_COVERAGE",) if absent else ())


def _ascii_parts(text):
    split = re.split(r"(?m)^-{8,}\s*$", text, maxsplit=1)
    if len(split) != 2:
        raise DataError("DAP ASCII requires a Dataset header and data separator")
    return split[0], split[1]


def _sections(body):
    sections, current = {}, None
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        label = re.fullmatch(r"(" + _IDENTIFIER + r"(?:\." + _IDENTIFIER + r")?)((?:\[\d+\])+)", line)
        if label:
            current = label[1]
            if current in sections:
                raise DataError("duplicate DAP ASCII section")
            sections[current] = {"shape": [int(n) for n in re.findall(r"\d+", label[2])], "lines": []}
        elif current is None:
            raise DataError("unexpected content before DAP ASCII section")
        else:
            sections[current]["lines"].append(line)
    return sections


def _float_values(lines, count):
    values = []
    for line in lines:
        prefix = re.match(r"^\[(\d+)\],\s*", line)
        if prefix:
            if int(prefix[1]) != len(values):
                raise DataError("coordinate chunk index is not contiguous")
            line = line[prefix.end():]
        for token in line.split(","):
            token = token.strip()
            if not re.fullmatch(_FLOAT, token):
                raise DataError("invalid Float64 coordinate token")
            values.append(float(token))
            if len(values) > count:
                raise DataError("too many coordinate values")
    if len(values) != count:
        raise DataError("truncated coordinate vector")
    result = np.asarray(values, dtype=np.float64)
    if not np.isfinite(result).all():
        raise DataError("nonfinite coordinate values")
    return result


def parse_gebco_axes(data: bytes, metadata, *, expected_sha256=None):
    """Read a coordinate-only DAP ASCII response into actual lon/lat vectors.

    Supported sections contain comma-separated Float64 values, optionally split
    into contiguous ``[start], ...`` chunks. No elevation section is accepted.
    Original response bytes/hashes remain the downloader's raw-cache authority.
    """
    _raw(data, expected_sha256)
    header, body = _ascii_parts(_text(data, maximum=_MAX_BYTES))
    names = (metadata["longitudeName"], metadata["latitudeName"])
    lengths = (metadata["globalShape"][1], metadata["globalShape"][0])
    declaration = r"Float64\s+(" + _IDENTIFIER + r")\s*\[\s*(" + _IDENTIFIER + r")\s*=\s*(\d+)\s*\]\s*;"
    header_match = re.fullmatch(r"\s*Dataset\s*\{(?P<declarations>(?:\s*" + declaration
                                + r")+)\s*\}\s*(?P<dataset>[^;{}]+);\s*", header)
    if header_match is None or header_match["dataset"].strip() != metadata["datasetPath"]:
        raise DataError("coordinate-only DDS dataset identity does not match source")
    declarations = [(name, dim, int(count)) for name, dim, count in re.findall(declaration, header_match["declarations"])]
    if sorted(declarations) != sorted((name, name, count) for name, count in zip(names, lengths)):
        raise DataError("coordinate-only DDS shape does not match source metadata")
    sections = _sections(body)
    if set(sections) != set(names):
        raise DataError("coordinate-only response has unexpected sections")
    axes = []
    for name, count in zip(names, lengths):
        if sections[name]["shape"] != [count]:
            raise DataError("coordinate section shape does not match DDS")
        axes.append(_float_values(sections[name]["lines"], count))
    _spacing(axes[0], "longitude", ascending=True)
    _spacing(axes[1], "latitude")
    return tuple(axes)


def parse_gebco_ascii(data: bytes, metadata, *, plan=None, request_index=0,
                      expected_sha256=None, max_cells=1_000_000) -> RasterData:
    """Decode only a bounded signed Int16 DAP Grid response, preserving maps.

    Require every local row exactly once and validate Int16 range before casting.
    A supplied subset plan additionally binds shape and actual returned axes to
    requested source indices. Singleton axes require that verified plan spacing.
    No default missing sentinel, land mask or positive depth is inferred.
    """
    digest = _raw(data, expected_sha256)
    _integer(max_cells, "max_cells", maximum=16_000_000)
    header, body = _ascii_parts(_text(data, maximum=_MAX_BYTES))
    schema = _dds(header)
    (lat_name, rows), (lon_name, columns) = schema["dimensions"]
    if schema["datasetPath"] != metadata["datasetPath"]:
        raise DataError("response DDS dataset identity differs from source metadata")
    if (schema["variable"] != metadata["variable"] or lat_name != metadata["latitudeName"]
            or lon_name != metadata["longitudeName"]):
        raise DataError("response variable/axis order does not match DDS/DAS")
    if rows > metadata["globalShape"][0] or columns > metadata["globalShape"][1]:
        raise DataError("response dimensions exceed validated global DDS shape")
    if rows * columns > max_cells or [rows, columns] == metadata["globalShape"]:
        raise DataError("response exceeds subset cell budget or contains global elevation")
    selected = None
    if plan is not None:
        if (not isinstance(plan, AcquisitionPlan) or plan.stage != "GEBCO_ASCII_SUBSET"
                or plan.status != "planned" or isinstance(request_index, bool)
                or not isinstance(request_index, int) or not 0 <= request_index < len(plan.requests)):
            raise DataError("invalid GEBCO subset plan/request index")
        selected = plan.metadata["subsets"][request_index]
        planned_request = plan.requests[request_index]
        if (planned_request.source_id != metadata["sourceId"]
                or planned_request.source_version != metadata["sourceVersion"]
                or plan.metadata["definitionSha256"] != metadata["sourceMetadataSha256"]):
            raise DataError("response metadata identity/version differs from subset plan")
        if len(data) > planned_request.max_bytes:
            raise DataError("response exceeds planned byte budget")
        if selected["shape"] != [rows, columns]:
            raise DataError("response shape differs from planned subset")
    sections = _sections(body)
    variable = schema["variable"]
    elevation_name = f"{variable}.{variable}"
    lat_section, lon_section = f"{variable}.{lat_name}", f"{variable}.{lon_name}"
    if set(sections) != {elevation_name, lat_section, lon_section}:
        raise DataError("unexpected or missing DAP Grid sections")
    if (sections[elevation_name]["shape"] != [rows, columns]
            or sections[lat_section]["shape"] != [rows] or sections[lon_section]["shape"] != [columns]):
        raise DataError("ASCII section shapes disagree with response DDS")
    row_lines = sections[elevation_name]["lines"]
    if len(row_lines) != rows:
        raise DataError("truncated or extra elevation rows")
    values = np.empty((rows, columns), dtype=np.int16)
    for row_index, line in enumerate(row_lines):
        match = re.fullmatch(r"\[(\d+)\],\s*(.*)", line)
        if not match or int(match[1]) != row_index:
            raise DataError("elevation local row indices must be contiguous and unique")
        tokens = [token.strip() for token in match[2].split(",")]
        if len(tokens) != columns or any(not re.fullmatch(r"[+-]?\d+", token) for token in tokens):
            raise DataError("elevation row width or signed integer token is invalid")
        if any(len(token) > 16 for token in tokens):
            raise DataError("elevation integer token exceeds supported Int16 representation")
        integers = [int(token) for token in tokens]
        if any(not -32768 <= value <= 32767 for value in integers):
            raise DataError("elevation exceeds signed Int16 range")
        values[row_index] = integers
    x = _float_values(sections[lon_section]["lines"], columns)
    y = _float_values(sections[lat_section]["lines"], rows)
    if selected is not None:
        if (not np.allclose(x, selected["x"], rtol=0, atol=1e-9)
                or not np.allclose(y, selected["y"], rtol=0, atol=1e-9)):
            raise DataError("returned coordinate maps differ from actual planned axes")
        dx, dy = selected["spacingDegrees"]
    else:
        dx, dy = _spacing(x, "longitude", ascending=True), _spacing(y, "latitude")
    if columns > 1:
        _spacing(x, "longitude", ascending=True)
    if rows > 1:
        _spacing(y, "latitude")
    if np.any(x < -180) or np.any(x > 180) or np.any(y < -90) or np.any(y > 90):
        raise DataError("response coordinate maps are outside conventional geographic bounds")
    attrs = metadata["sourceAttributes"].get(variable, {})
    valid = np.ones(values.shape, dtype=np.bool_)
    sentinels = []
    for field in ("_FillValue", "missing_value"):
        if field in attrs:
            value = attrs[field]
            sentinels.extend(value if isinstance(value, list) else [value])
    for sentinel in sentinels:
        if not isinstance(sentinel, (int, float)) or not math.isfinite(sentinel):
            raise DataError("invalid declared nodata value")
        valid &= values != sentinel
    bounds = attrs.get("valid_range")
    if bounds is not None:
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in bounds)
                or bounds[0] > bounds[1]):
            raise DataError("invalid declared elevation valid_range")
        valid &= (values >= bounds[0]) & (values <= bounds[1])
    for field, operator in (("valid_min", np.greater_equal), ("valid_max", np.less_equal)):
        if field in attrs:
            if not isinstance(attrs[field], (int, float)) or not math.isfinite(attrs[field]):
                raise DataError("invalid declared elevation support bound")
            valid &= operator(values, attrs[field])
    if attrs.get("valid_min", -math.inf) > attrs.get("valid_max", math.inf):
        raise DataError("reversed declared elevation support bounds")
    meta = {"format": "OPeNDAP_ASCII_SUBSET", "inputSha256": digest,
            "sourceMetadataSha256": (plan.metadata["sourceMetadataSha256"] if plan is not None
                                     else metadata["sourceMetadataSha256"]),
            "definitionSha256": metadata["sourceMetadataSha256"],
            "sourceId": metadata["sourceId"], "sourceVersion": metadata["sourceVersion"],
            "sourceURL": plan.requests[request_index].url if plan is not None else metadata["sourceURL"],
            "sourceAttributes": deepcopy(metadata["sourceAttributes"]), "crs": metadata["crs"],
            "units": "m", "positive": "up", "verticalDatum": metadata["verticalDatum"],
            "verticalDatumCaveat": "SOURCE_REFERENCE_DOES_NOT_PROVE_HOMOGENEOUS_DATUM",
            "nodata": None if not sentinels else sentinels[0] if len(sentinels) == 1 else sentinels,
            "transform": [float(x[0] - dx/2), dx, 0.0, float(y[0] - dy/2), 0.0, dy],
            "spacing": [dx, dy], "registration": "CELL_CENTER", "sourceDtype": "int16",
            "rowOrder": "SOUTH_TO_NORTH" if dy > 0 else "NORTH_TO_SOUTH",
            "quantity": "SIGNED_ELEVATION", "oceanMaskStatus": "UNRESOLVED"}
    if selected is not None:
        meta["subsetIndices"] = {"rows": selected["rowIndices"], "columns": selected["columnIndices"]}
        meta["axisValuesSha256"] = plan.metadata["axisValuesSha256"]
    return RasterData(values, x, y, valid, meta)


def _child(node, path, *, required=True):
    values = node.findall(path, _NS)
    if len(values) != 1 or values[0].text is None or not values[0].text.strip():
        if not required and not values:
            return None
        raise DataError(f"WMTS requires one {path}")
    return values[0].text.strip()


def _xml_integer(node, path):
    value = _child(node, path)
    if not re.fullmatch(r"\d+", value):
        raise DataError("WMTS dimensions/limits must be integer")
    return int(value)


def _crs_axis_order(crs):
    try:
        with osr.ExceptionMgr():
            source, target = osr.SpatialReference(), osr.SpatialReference()
            source.SetFromUserInput(crs)
            target.ImportFromEPSG(4326)
            if not source.IsSame(target, ["IGNORE_DATA_AXIS_TO_SRS_AXIS_MAPPING=YES",
                                         "CRITERION=EQUIVALENT_EXCEPT_AXIS_ORDER_GEOGCRS"]):
                raise DataError("WMTS supports only 2D WGS84 degree grids")
            orientations = [source.GetAxisOrientation(None, index) for index in (0, 1)]
            if orientations == [osr.OAO_East, osr.OAO_North]:
                order = "LONGITUDE_LATITUDE"
            elif orientations == [osr.OAO_North, osr.OAO_East]:
                order = "LATITUDE_LONGITUDE"
            else:
                raise DataError("unsupported WMTS CRS axis orientation")
            return order, source.GetSemiMajor() * math.pi / 180
    except RuntimeError as exc:
        raise DataError("invalid or unsupported WMTS CRS") from exc


def parse_wmts_metadata(xml: bytes, *, layer_id, source_id, source_version,
                        matrix_set_id=None, layer_metadata=None,
                        source_nominal_resolution_m=None) -> dict:
    """Read actual layer/matrixset declarations, including padded grid extents.

    Degree spacing uses ScaleDenominator and the OGC 0.28 mm pixel definition,
    never XYZ formulas or world width divided by matrix dimensions. Static/time
    status and nominal source resolution are caller-supplied source declarations.
    """
    text = _text(xml)
    if layer_metadata is not None and not isinstance(layer_metadata, dict):
        raise DataError("layer_metadata must contain source-declared metadata")
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.I):
        raise DataError("XML declarations/entities are unsupported")
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DataError("invalid WMTS XML") from exc
    layers = [node for node in root.findall(".//wmts:Layer", _NS)
              if _child(node, "ows:Identifier") == layer_id]
    if len(layers) != 1:
        raise DataError("exactly one requested WMTS layer is required")
    layer = layers[0]
    links = layer.findall("wmts:TileMatrixSetLink", _NS)
    if matrix_set_id is None:
        if len(links) != 1:
            raise DataError("matrix_set_id is required for multiple WMTS links")
        matrix_set_id = _child(links[0], "wmts:TileMatrixSet")
    selected_links = [link for link in links if _child(link, "wmts:TileMatrixSet") == matrix_set_id]
    if len(selected_links) != 1:
        raise DataError("requested matrixset is not uniquely linked by the layer")
    matrixsets = [node for node in root.findall(".//wmts:TileMatrixSet", _NS)
                  if node.find("ows:Identifier", _NS) is not None
                  and _child(node, "ows:Identifier") == matrix_set_id]
    if len(matrixsets) != 1:
        raise DataError("requested WMTS matrixset definition is missing or duplicated")
    matrixset = matrixsets[0]
    crs = _child(matrixset, "ows:SupportedCRS")
    order, meters_per_degree = _crs_axis_order(crs)
    bounds_node = layer.find("ows:WGS84BoundingBox", _NS)
    if bounds_node is None:
        raise DataError("WMTS layer requires actual WGS84BoundingBox")
    try:
        lower = list(map(float, _child(bounds_node, "ows:LowerCorner").split()))
        upper = list(map(float, _child(bounds_node, "ows:UpperCorner").split()))
        if len(lower) != 2 or len(upper) != 2:
            raise ValueError()
        bounds = validate_bbox([lower[0], lower[1], upper[0], upper[1]])
    except ValueError as exc:
        raise DataError("invalid WMTS geographic layer bounds") from exc
    matrices = {}
    for node in matrixset.findall("wmts:TileMatrix", _NS):
        identifier = _child(node, "ows:Identifier")
        if identifier in matrices:
            raise DataError("duplicate WMTS matrix identifier")
        try:
            scale = float(_child(node, "wmts:ScaleDenominator"))
            corner = list(map(float, _child(node, "wmts:TopLeftCorner").split()))
        except ValueError as exc:
            raise DataError("invalid WMTS scale/corner") from exc
        if len(corner) != 2 or not all(math.isfinite(v) for v in [scale, *corner]) or scale <= 0:
            raise DataError("WMTS scale/corner must be finite and scale positive")
        if order == "LATITUDE_LONGITUDE":
            corner = corner[::-1]
        dimensions = {key: _xml_integer(node, f"wmts:{xml_key}") for key, xml_key in
                      (("tileWidth", "TileWidth"), ("tileHeight", "TileHeight"),
                       ("matrixWidth", "MatrixWidth"), ("matrixHeight", "MatrixHeight"))}
        for key, value in dimensions.items():
            _integer(value, key)
        step = scale * .00028 / meters_per_degree
        if (not math.isfinite(step) or step <= 0
                or any(not math.isfinite(step*dimensions[key]) or step*dimensions[key] <= 0
                       for key in ("tileWidth", "tileHeight", "matrixWidth", "matrixHeight"))):
            raise DataError("WMTS derived spacing/spans must be finite and positive")
        matrices[identifier] = {**dimensions, "scaleDenominator": scale,
                                "topLeft": corner, "spacingDegrees": step,
                                "transform": [corner[0], step, 0, corner[1], 0, -step]}
    if not matrices:
        raise DataError("WMTS matrixset contains no matrix definitions")
    link = selected_links[0]
    limit_containers = link.findall("wmts:TileMatrixSetLimits", _NS)
    if len(limit_containers) > 1:
        raise DataError("duplicate WMTS limit container")
    limits = None if not limit_containers else {}
    if limits is not None:
        for node in limit_containers[0].findall("wmts:TileMatrixLimits", _NS):
            identifier = _child(node, "wmts:TileMatrix")
            if identifier not in matrices or identifier in limits:
                raise DataError("WMTS limits reference missing or duplicated matrix")
            record = {key: _xml_integer(node, "wmts:" + xml_key) for key, xml_key in
                      (("minRow", "MinTileRow"), ("maxRow", "MaxTileRow"),
                       ("minCol", "MinTileCol"), ("maxCol", "MaxTileCol"))}
            matrix = matrices[identifier]
            if (not 0 <= record["minRow"] <= record["maxRow"] < matrix["matrixHeight"]
                    or not 0 <= record["minCol"] <= record["maxCol"] < matrix["matrixWidth"]):
                raise DataError("WMTS limits exceed matrix dimensions")
            limits[identifier] = record
    templates = [dict(node.attrib) for node in layer.findall("wmts:ResourceURL", _NS)
                 if node.get("resourceType") == "tile"]
    if not templates:
        raise DataError("WMTS tile ResourceURL metadata is required")
    for template in templates:
        _identity(template.get("template", ""), source_id, source_version)
    if source_nominal_resolution_m is not None:
        if (isinstance(source_nominal_resolution_m, bool)
                or not isinstance(source_nominal_resolution_m, (int, float))
                or not math.isfinite(source_nominal_resolution_m) or source_nominal_resolution_m <= 0):
            raise DataError("nominal source resolution must be positive meters")
    dimensions = {}
    for node in layer.findall("wmts:Dimension", _NS):
        name = _child(node, "ows:Identifier")
        if name in dimensions:
            raise DataError("duplicate WMTS layer dimension")
        dimensions[name] = {"default": _child(node, "wmts:Default", required=False),
                            "values": [n.text.strip() for n in node.findall("wmts:Value", _NS) if n.text]}
    try:
        declarations = json.dumps({"layerMetadata": layer_metadata or {},
                                   "sourceNominalResolutionMeters": source_nominal_resolution_m},
                                  sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError) as exc:
        raise DataError("WMTS source declarations must be finite JSON metadata") from exc
    return {"sourceId": source_id, "sourceVersion": source_version, "layerId": layer_id,
            "matrixSetId": matrix_set_id, "supportedCRS": crs, "serviceAxisOrder": order,
            "crs": "EPSG:4326", "layerBBox": list(bounds), "matrices": matrices, "limits": limits,
            "templates": templates, "formats": [n.text.strip() for n in layer.findall("wmts:Format", _NS) if n.text],
            "styles": [{"identifier": _child(n, "ows:Identifier"), "default": n.get("isDefault") == "true"}
                       for n in layer.findall("wmts:Style", _NS)],
            "dimensions": dimensions, "layerMetadata": deepcopy(layer_metadata or {}),
            "sourceNominalResolutionMeters": source_nominal_resolution_m,
            "wmtsXmlSha256": sha256(xml),
            "sourceMetadataSha256": sha256(b"WMTS\x00" + xml + b"\x00DECLARATIONS\x00" + declarations),
            "liveTileAccessVerified": False}


def plan_wmts_tiles(request: DataRequest, metadata, *, matrix_id, template_index=0,
                    dimensions=None, max_tiles=256, max_bytes=_MAX_BYTES,
                    max_tile_pixels=16_000_000) -> AcquisitionPlan:
    """Plan advertised geographic WMTS tiles, honoring layer and matrix limits.

    Full padded tile transforms stay in plan metadata; DownloadRequest.bbox is
    clipped to declared geographic coverage. JPEG decoding is not performed.
    """
    request.validate()
    cap = _budget(max_bytes)
    _integer(max_tiles, "max_tiles")
    _integer(max_tile_pixels, "max_tile_pixels")
    if matrix_id not in metadata["matrices"]:
        raise DataError("matrix_id is not advertised")
    limits = metadata["limits"]
    if limits is not None and matrix_id not in limits:
        return AcquisitionPlan("unavailable", "NASA_WMTS_TILES",
                               metadata={"reason": "MATRIX_NOT_IN_LAYER_LIMITS"})
    if (isinstance(template_index, bool) or not isinstance(template_index, int)
            or not 0 <= template_index < len(metadata["templates"])):
        raise DataError("invalid WMTS template_index")
    template = metadata["templates"][template_index]
    if template.get("format") not in metadata["formats"]:
        raise DataError("WMTS template format is not advertised by layer")
    matrix = metadata["matrices"][matrix_id]
    if matrix["tileWidth"] * matrix["tileHeight"] > max_tile_pixels:
        raise DataError("WMTS tile pixel budget exceeded")
    provided = dict(dimensions or {})
    if set(provided) - set(metadata["dimensions"]):
        raise DataError("unadvertised WMTS dimension")
    for name, definition in metadata["dimensions"].items():
        if name not in provided:
            if definition["default"] is None:
                raise DataError("WMTS dimension requires explicit value")
            provided[name] = definition["default"]
        if definition["values"] and provided[name] not in definition["values"]:
            raise DataError("WMTS dimension value is not advertised")
    origin_x, origin_y = matrix["topLeft"]
    span_x = matrix["spacingDegrees"] * matrix["tileWidth"]
    span_y = matrix["spacingDegrees"] * matrix["tileHeight"]
    if any(not math.isfinite(value) or value <= 0 for value in (span_x, span_y)):
        raise DataError("WMTS derived tile spans must be finite and positive")
    limit = limits[matrix_id] if limits is not None else {
        "minRow": 0, "maxRow": matrix["matrixHeight"]-1,
        "minCol": 0, "maxCol": matrix["matrixWidth"]-1}
    positions = set()
    for part in split_dateline(request.bbox):
        for layer_part in split_dateline(metadata["layerBBox"]):
            intersection = _intersection(part, layer_part)
            if intersection is None:
                continue
            west, south, east, north = intersection
            first_col, last_col = _index_span(origin_x, span_x, matrix["matrixWidth"], west, east,
                                             centers=False, first_index=limit["minCol"], last_index=limit["maxCol"])
            first_row, last_row = _index_span(origin_y, -span_y, matrix["matrixHeight"], south, north,
                                             centers=False, first_index=limit["minRow"], last_index=limit["maxRow"])
            count = max(0, last_row-first_row+1) * max(0, last_col-first_col+1)
            if count > max_tiles:
                raise DataError("WMTS request exceeds max_tiles")
            positions.update((row, col) for row in range(first_row, last_row+1)
                             for col in range(first_col, last_col+1))
            if len(positions) > max_tiles:
                raise DataError("WMTS request exceeds max_tiles")
    if not positions:
        return AcquisitionPlan("unavailable", "NASA_WMTS_TILES",
                               metadata={"reason": "NO_ADVERTISED_TILE_INTERSECTION"})
    outgoing, tile_metadata = [], []
    for row, col in sorted(positions):
        west, north = origin_x + col*span_x, origin_y - row*span_y
        tile_bounds = (west, north-span_y, west+span_x, north)
        clipped = [_intersection(tile_bounds, part) for part in split_dateline(metadata["layerBBox"])]
        clipped = [bounds for bounds in clipped if bounds is not None]
        if not clipped:
            continue
        replacements = {"TileMatrixSet": metadata["matrixSetId"], "TileMatrix": matrix_id,
                        "TileRow": str(row), "TileCol": str(col), **provided}
        url = template["template"]
        for key, value in replacements.items():
            if not isinstance(value, str):
                raise DataError("WMTS substitutions must be strings")
            url = url.replace("{" + key + "}", quote(value, safe=""))
        if "{" in url or "}" in url:
            raise DataError("WMTS template contains unresolved placeholders")
        outgoing.append(DownloadRequest(url, metadata["sourceId"], metadata["sourceVersion"], cap,
                        bbox=tuple(clipped[0]), resolution={"spacingDegrees": matrix["spacingDegrees"]},
                        source_metadata_sha256=metadata["sourceMetadataSha256"]))
        tile_metadata.append({"row": row, "column": col, "tileBBox": list(tile_bounds),
                              "geographicCoverage": [list(bounds) for bounds in clipped],
                              "transform": [west, matrix["spacingDegrees"], 0, north, 0, -matrix["spacingDegrees"]]})
    declared_grid = (origin_x + limit["minCol"]*span_x, origin_y-(limit["maxRow"]+1)*span_y,
                     origin_x+(limit["maxCol"]+1)*span_x, origin_y-limit["minRow"]*span_y)
    declared_coverage = [_intersection(declared_grid, part) for part in split_dateline(metadata["layerBBox"])]
    declared_coverage = [bounds for bounds in declared_coverage if bounds is not None]
    complete = all(any(bounds[0] <= part[0] and bounds[1] <= part[1]
                       and bounds[2] >= part[2] and bounds[3] >= part[3]
                       for bounds in declared_coverage) for part in split_dateline(request.bbox))
    warnings = ["WMTS_METADATA_PLAN_ONLY_LIVE_TILES_UNVERIFIED",
                "SOURCE_NOMINAL_RESOLUTION_IS_NOT_UNIFORM_METERS_AT_LATITUDE"]
    if not complete:
        warnings.append("PARTIAL_DECLARED_WMTS_GRID_COVERAGE")
    return AcquisitionPlan("planned", "NASA_WMTS_TILES", tuple(outgoing),
                           metadata={"matrixSetId": metadata["matrixSetId"], "matrixId": matrix_id,
                                     "tiles": tile_metadata, "sourceNominalResolutionMeters": metadata["sourceNominalResolutionMeters"],
                                     "layerMetadata": deepcopy(metadata["layerMetadata"]),
                                     "liveTileAccessVerified": False, "imageDecodeExecuted": False},
                           coverage={"requestedBBox": list(request.bbox), "declaredLayerBBox": metadata["layerBBox"],
                                     "matrixLimits": limit, "declaredGridCoverage": declared_coverage,
                                     "completeDeclaredGridCoverage": complete,
                                     "completenessMeaning": "DECLARED_GRID_EXTENT_ONLY_NOT_VALID_PIXEL_SUPPORT",
                                     "validPixelSupport": "UNVERIFIED"}, warnings=tuple(warnings))


def build_wms13_plan(request: DataRequest, *, endpoint, layer, source_id,
                     source_version, width, height, max_bytes=_MAX_BYTES,
                     max_pixels=16_000_000, source_nominal_resolution_m=None,
                     source_metadata_sha256=None) -> AcquisitionPlan:
    """Plan caller-declared WMS 1.3 PNG GetMap with EPSG:4326 lat/lon axis order.

    Width/height describe the requested output grid, not source detail. Crossing
    requests split at the dateline and share total width in proportion to span.
    Source layer/version/endpoint must come from supplied metadata/configuration.
    """
    request.validate()
    cap = _budget(max_bytes)
    _identity(endpoint, source_id, source_version)
    _integer(width, "width")
    _integer(height, "height")
    _integer(max_pixels, "max_pixels")
    if width * height > max_pixels:
        raise DataError("WMS output pixel budget exceeded")
    if not isinstance(layer, str) or not layer.strip():
        raise DataError("explicit WMS layer is required")
    if source_nominal_resolution_m is not None and (isinstance(source_nominal_resolution_m, bool)
            or not isinstance(source_nominal_resolution_m, (int, float))
            or not math.isfinite(source_nominal_resolution_m) or source_nominal_resolution_m <= 0):
        raise DataError("nominal source resolution must be positive meters")
    parts = split_dateline(request.bbox)
    if width < len(parts):
        raise DataError("output width must support every dateline part")
    widths = [width]
    if len(parts) == 2:
        first_width = max(1, min(width-1, round(width * (parts[0][2]-parts[0][0]) /
                                               sum(part[2]-part[0] for part in parts))))
        widths = [first_width, width-first_width]
    with osr.ExceptionMgr():
        reference = osr.SpatialReference()
        reference.ImportFromEPSG(4326)
        projection = reference.ExportToWkt()
    outgoing, grids = [], []
    for bbox, part_width in zip(parts, widths):
        west, south, east, north = bbox
        service_bbox = [south, west, north, east]
        params = {"SERVICE": "WMS", "VERSION": "1.3.0", "REQUEST": "GetMap", "LAYERS": layer,
                  "STYLES": "", "FORMAT": "image/png", "CRS": "EPSG:4326",
                  "BBOX": ",".join(format(value, ".17g") for value in service_bbox),
                  "WIDTH": str(part_width), "HEIGHT": str(height)}
        parsed = urlsplit(endpoint)
        existing = [(key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                    if key.upper() not in params]
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path,
                          urlencode(existing + list(params.items())), ""))
        dx, dy = (east-west)/part_width, -(north-south)/height
        world = "\n".join(format(value, ".17g") for value in
                           (dx, 0, 0, dy, west+dx/2, north+dy/2)) + "\n"
        outgoing.append(DownloadRequest(url, source_id, source_version, cap, bbox=tuple(bbox),
                        resolution={"spacingDegrees": [dx, abs(dy)]},
                        source_metadata_sha256=source_metadata_sha256))
        grids.append({"bbox": list(bbox), "width": part_width, "height": height,
                      "serviceBBox": service_bbox, "worldfile": world,
                      "projectionWkt": projection, "transform": [west, dx, 0, north, 0, dy]})
    return AcquisitionPlan("planned", "NASA_WMS13_GETMAP", tuple(outgoing),
                           metadata={"parts": grids, "sourceId": source_id, "sourceVersion": source_version,
                                     "layer": layer, "serviceAxisOrder": "LATITUDE_LONGITUDE",
                                     "sourceNominalResolutionMeters": source_nominal_resolution_m,
                                     "sourceMetadataSha256": source_metadata_sha256,
                                     "nativeDetailIncreased": False, "downloadExecuted": False},
                           coverage={"requestedBBox": list(request.bbox), "actualValidSupport": "UNVERIFIED"},
                           warnings=("OUTPUT_GRID_RESOLUTION_DOES_NOT_ADD_SOURCE_DETAIL",))


def parse_wms_png(data: bytes, plan: AcquisitionPlan, *, request_index=0,
                   expected_sha256=None) -> RasterData:
    """Preserve PNG channels and derive georeferencing from a planned GetMap.

    An exact dimension match is required. This records the service-request grid,
    not a measured underlying source footprint or a physical albedo/depth map.
    """
    _raw(data, expected_sha256)
    if (not isinstance(plan, AcquisitionPlan) or plan.status != "planned"
            or plan.stage != "NASA_WMS13_GETMAP" or isinstance(request_index, bool)
            or not isinstance(request_index, int) or not 0 <= request_index < len(plan.requests)):
        raise DataError("valid WMS GetMap plan/request index is required")
    grid = plan.metadata["parts"][request_index]
    planned_request = plan.requests[request_index]
    if (planned_request.source_id != plan.metadata["sourceId"]
            or planned_request.source_version != plan.metadata["sourceVersion"]):
        raise DataError("WMS plan source identity/version differs from download request")
    if len(data) > planned_request.max_bytes:
        raise DataError("WMS response exceeds planned byte budget")
    if (len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n")
            or int.from_bytes(data[16:20], "big") != grid["width"]
            or int.from_bytes(data[20:24], "big") != grid["height"]):
        raise DataError("WMS response is not a PNG of the exact planned dimensions")
    from .surface import parse_surface
    raster = parse_surface(data, grid["worldfile"], grid["projectionWkt"],
                           expected_sha256=expected_sha256)
    metadata = deepcopy(raster.metadata)
    metadata.update(sourceId=plan.metadata["sourceId"], sourceVersion=plan.metadata["sourceVersion"],
                    sourceURL=plan.requests[request_index].url,
                    sourceMetadataSha256=plan.metadata["sourceMetadataSha256"],
                    sourceNominalResolutionMeters=plan.metadata["sourceNominalResolutionMeters"],
                    georeferencingSource="WMS13_REQUEST_BBOX_AND_OUTPUT_SIZE",
                    serviceAxisOrder="LATITUDE_LONGITUDE", sourceLayer=plan.metadata["layer"],
                    nativeDetailIncreased=False)
    return RasterData(raster.values, raster.x, raster.y, raster.valid, metadata)
