"""Offline plans, preserved archived responses and generic synthetic geography."""
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import unittest
import uuid
from urllib.parse import parse_qs, unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile
import zlib

import numpy as np
from PIL import Image
from osgeo import gdal, osr

from astra_cpu.acquisition import (
    CogBlock, CogLayout, CogLevel, IndexedTerrainTile, build_copernicus_index_request, build_wms13_plan,
    parse_copernicus_index,
    parse_gebco_ascii, parse_gebco_axes, parse_gebco_metadata, parse_wms_png,
    parse_wmts_metadata, plan_cog_ranges, plan_copernicus_tiles,
    plan_gebco_subset, plan_wmts_tiles,
)
from astra_cpu.bathymetry import parse_bathymetry
from astra_cpu.model import DataError, sha256
from astra_cpu.providers import DataRequest
from astra_cpu.surface import parse_surface


_URL = "https://data.example.test/version-pinned/grid.nc"
_ID, _VERSION = "synthetic-grid", "fixture-release-v3"


def grid_dds(rows=6, columns=8, *, full=True):
    prefix = f"Float64 lon[lon = {columns}]; Float64 lat[lat = {rows}]; String crs;" if full else ""
    return (f"Dataset {{ {prefix} Grid {{ ARRAY: Int16 elevation[lat = {rows}][lon = {columns}];"
            f" MAPS: Float64 lat[lat = {rows}]; Float64 lon[lon = {columns}];"
            " } elevation; } fixture/grid.nc;").encode()


def grid_das(*, extra="", positive="up", unit="m"):
    return ("Attributes {"
            ' lon { String standard_name "longitude"; String units "degrees_east"; String axis "X"; }'
            ' lat { String standard_name "latitude"; String units "degrees_north"; String axis "Y"; }'
            ' crs { String grid_mapping_name "latitude_longitude"; String epsg_code "EPSG:4326"; }'
            f' elevation {{ String units "{unit}"; String grid_mapping "crs"; {extra} }}'
            f' NC_GLOBAL {{ String geospatial_vertical_positive "{positive}";'
            ' String geospatial_bounds_vertical_crs "Synthetic declared datum"; Float64 node_offset 1; }'
            " }").encode()


def synthetic_metadata(*, rows=6, columns=8, **options):
    return parse_gebco_metadata(grid_dds(rows, columns), grid_das(**options),
                                source_id=_ID, source_version=_VERSION, source_url=_URL)


def grid_ascii(values, x, y):
    values = np.asarray(values)
    rows, columns = values.shape
    lines = [grid_dds(rows, columns, full=False).decode(), "-"*45,
             f"elevation.elevation[{rows}][{columns}]"]
    lines += [f"[{index}], " + ", ".join(str(int(value)) for value in row)
              for index, row in enumerate(values)]
    lines += [f"elevation.lat[{rows}]", ", ".join(format(value, ".17g") for value in y),
              f"elevation.lon[{columns}]", ", ".join(format(value, ".17g") for value in x)]
    return ("\n".join(lines) + "\n").encode()


def axes_ascii(x, y):
    return (f"Dataset {{ Float64 lon[lon = {len(x)}]; Float64 lat[lat = {len(y)}]; }} fixture/grid.nc;\n"
            + "-"*45 + f"\nlon[{len(x)}]\n"
            + ", ".join(format(value, ".17g") for value in x)
            + f"\nlat[{len(y)}]\n"
            + ", ".join(format(value, ".17g") for value in y) + "\n").encode()


def synthetic_cog(*, south_up=False):
    tile = IndexedTerrainTile("synthetic-terrain", "fixture-v1", "https://data.example.test/tile.tif",
                              (-2, 0, 0, 2), 4096, '"pinned-etag"', sha256(b"full source fixture"))
    transform = (-2, .5, 0, 0 if south_up else 2, 0, .5 if south_up else -.5)
    blocks = tuple(CogBlock(row, col, 1000 + (row*2+col)*100, 80)
                   for row in range(2) for col in range(2))
    native = CogLevel("native", 4, 4, transform, 2, 2, blocks)
    overview = CogLevel("overview-a", 2, 2, (-2, 1, 0, 2, 0, -1), 1, 1,
                        tuple(CogBlock(row, col, 2000 + (row*2+col)*50, 40)
                              for row in range(2) for col in range(2)))
    return CogLayout(tile, (native, overview), sha256(b"supplied synthetic IFD metadata"))


def wmts_xml(*, limits="", supported_crs="urn:ogc:def:crs:OGC:1.3:CRS84", corner="-180 90"):
    # A geographic 1-degree/pixel grid, intentionally 3x2 rather than XYZ.
    scale = (6378137 * np.pi / 180) / .00028
    return (f'<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:ows="http://www.opengis.net/ows/1.1">'
            '<Contents><Layer><ows:Identifier>fixture-layer</ows:Identifier>'
            '<ows:WGS84BoundingBox><ows:LowerCorner>-180 -90</ows:LowerCorner>'
            '<ows:UpperCorner>180 90</ows:UpperCorner></ows:WGS84BoundingBox>'
            '<Style isDefault="true"><ows:Identifier>default</ows:Identifier></Style><Format>image/jpeg</Format>'
            f'<TileMatrixSetLink><TileMatrixSet>fixture-matrixset</TileMatrixSet>{limits}</TileMatrixSetLink>'
            '<ResourceURL resourceType="tile" format="image/jpeg" '
            'template="https://data.example.test/tiles/{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.jpeg" />'
            '</Layer><TileMatrixSet><ows:Identifier>fixture-matrixset</ows:Identifier>'
            f'<ows:SupportedCRS>{supported_crs}</ows:SupportedCRS>'
            '<TileMatrix><ows:Identifier>coarse-a</ows:Identifier>'
            f'<ScaleDenominator>{scale:.17g}</ScaleDenominator><TopLeftCorner>{corner}</TopLeftCorner>'
            '<TileWidth>120</TileWidth><TileHeight>120</TileHeight>'
            '<MatrixWidth>3</MatrixWidth><MatrixHeight>2</MatrixHeight>'
            '</TileMatrix></TileMatrixSet></Contents></Capabilities>').encode()


def synthetic_wmts(**options):
    return parse_wmts_metadata(wmts_xml(**options), layer_id="fixture-layer",
                                source_id="synthetic-surface", source_version="fixture-static-v1",
                                layer_metadata={"ongoing": False}, source_nominal_resolution_m=750)


class CopernicusPlanTests(unittest.TestCase):
    def index_plan(self, **options):
        return build_copernicus_index_request(index_url="https://data.example.test/pinned-tile-keys.txt",
                                              base_url="https://data.example.test/pinned-objects/",
                                              source_id="synthetic-indexed-terrain", source_version="fixture-v7", **options)

    def test_text_index_records_preserve_raw_sha_version_and_listed_hemisphere_urls(self):
        stems = ["Copernicus_DSM_COG_10_N37_00_E128_00_DEM",
                 "Copernicus_DSM_COG_10_S35_00_W071_00_DEM",
                 "Copernicus_DSM_COG_10_N89_00_W180_00_DEM",
                 "Copernicus_DSM_COG_10_S90_00_E179_00_DEM"]
        data = ("\ufeff" + stems[0] + "\r\n" + stems[1] + "/" + stems[1] + ".tif\r\n"
                + stems[2] + "\r\n" + stems[3] + "\r\n").encode()
        records, digest = parse_copernicus_index(data, self.index_plan(expected_sha256=sha256(data)))
        self.assertEqual(digest, sha256(data))
        self.assertEqual([record.bbox for record in records], [(128, 37, 129, 38), (-71, -35, -70, -34),
                                                               (-180, 89, -179, 90), (179, -90, 180, -89)])
        self.assertEqual([record.url for record in records], ["https://data.example.test/pinned-objects/"
                                                               + stem + "/" + stem + ".tif" for stem in stems])
        self.assertTrue(all(record.source_version == "fixture-v7" for record in records))
        self.assertTrue(all(record.object_bytes is None and record.sha256 is None for record in records))
        self.assertEqual(self.index_plan().metadata["liveIndexFormat"], "UNVERIFIED_NOT_ARCHIVED")

    def test_text_index_produced_entries_feed_real_intersection_and_dateline_planner(self):
        stems = ["Copernicus_DSM_COG_10_S20_00_E179_00_DEM",
                 "Copernicus_DSM_COG_10_S20_00_W180_00_DEM",
                 "Copernicus_DSM_COG_10_N45_00_W073_00_DEM"]
        records, digest = parse_copernicus_index(("\n".join(stems)+"\n").encode(), self.index_plan())
        plan = plan_copernicus_tiles(DataRequest((179.5, -20, -179.5, -19)), records,
                                     source_id=records[0].source_id, source_version=records[0].source_version,
                                     index_metadata_sha256=digest)
        self.assertEqual(len(plan.requests), 2)
        self.assertTrue(all(request.source_metadata_sha256 == digest for request in plan.requests))
        self.assertEqual({request.url for request in plan.requests}, {records[0].url, records[1].url})
        self.assertFalse(plan.coverage["partsWithNoIndexEntry"])
        absent = plan_copernicus_tiles(DataRequest((10, 10, 11, 11)), records,
                                       source_id=records[0].source_id, source_version=records[0].source_version)
        self.assertEqual(absent.status, "unavailable")
        self.assertFalse(absent.requests)

    def test_text_index_duplicate_keys_and_same_origin_aliases_are_rejected(self):
        stem = "Copernicus_DSM_COG_10_N00_00_E000_00_DEM"
        for text in (stem+"\n"+stem, stem+"\n"+stem+"/"+stem+".tif",
                     stem+"\nCopernicus_DSM_COG_10_S00_00_W000_00_DEM"):
            with self.subTest(text=text), self.assertRaisesRegex(DataError, "duplicate"):
                parse_copernicus_index(text.encode(), self.index_plan())

    def test_text_index_bad_keys_paths_prefixes_and_coordinates_reject(self):
        stem = "Copernicus_DSM_COG_10_N37_00_E128_00_DEM"
        bad = [b"", b"  \n", b"\xff", b"<html>error</html>", b"../"+stem.encode(),
               ("https://other.example.test/"+stem).encode(),
               (stem+"/other.tif").encode(), (stem+".tif").encode(),
               stem.replace("N37_00", "N37_30").encode(), stem.replace("COG_10", "COG_30").encode(),
               stem.replace("N37", "N90").encode(), stem.replace("E128", "E180").encode(),
               stem.replace("N37", "S91").encode(), stem.replace("E128", "W181").encode(),
               stem.replace("N37", "N３７").encode()]
        for data in bad:
            with self.subTest(data=data[:50]), self.assertRaises(DataError):
                parse_copernicus_index(data, self.index_plan())

    def test_text_index_pinned_versions_and_hash_mismatch_reject_before_records(self):
        data = b"Copernicus_DSM_COG_10_N37_00_E128_00_DEM\n"
        changed = self.index_plan(observed_source_version="fixture-v8")
        self.assertEqual(changed.status, "version_changed")
        self.assertFalse(changed.requests)
        with self.assertRaisesRegex(DataError, "PINNED_INDEX_VERSION_MISMATCH"):
            parse_copernicus_index(data, self.index_plan(), observed_source_version="fixture-v8")
        with self.assertRaisesRegex(DataError, "SHA-256 mismatch"):
            parse_copernicus_index(data, self.index_plan(expected_sha256="0"*64))
        with self.assertRaises(DataError):
            self.index_plan(observed_source_version="")

    def test_text_index_byte_record_url_and_request_bounds_are_enforced(self):
        data = b"Copernicus_DSM_COG_10_N37_00_E128_00_DEM\n"
        with self.assertRaisesRegex(DataError, "bounded response bytes"):
            parse_copernicus_index(data, self.index_plan(max_bytes=10))
        two = data + b"Copernicus_DSM_COG_10_S35_00_W071_00_DEM\n"
        with self.assertRaisesRegex(DataError, "record budget"):
            parse_copernicus_index(two, self.index_plan(), max_tiles=1)
        with self.assertRaises(DataError):
            self.index_plan(max_bytes=65*1024*1024)
        with self.assertRaises(DataError):
            build_copernicus_index_request(index_url="http://data.example.test/index", base_url="https://data.example.test/",
                                           source_id=_ID, source_version=_VERSION)
        with self.assertRaisesRegex(DataError, "must not contain a query"):
            build_copernicus_index_request(index_url="https://data.example.test/index", base_url="https://data.example.test/?query=1",
                                           source_id=_ID, source_version=_VERSION)

    def test_generated_cog_offsets_select_exact_compressed_source_block_bytes(self):
        path = "/vsimem/acquisition-cog-" + uuid.uuid4().hex + ".tif"
        source = dataset = band = None
        values = np.arange(256*256, dtype=np.float32).reshape(256, 256)
        try:
            with gdal.ExceptionMgr(), osr.ExceptionMgr():
                source = gdal.GetDriverByName("MEM").Create("", 256, 256, 1, gdal.GDT_Float32)
                source.SetGeoTransform((-10, .01, 0, 20, 0, -.01))
                reference = osr.SpatialReference()
                reference.ImportFromEPSG(4326)
                source.SetSpatialRef(reference)
                source.SetMetadataItem("AREA_OR_POINT", "Point")
                source.GetRasterBand(1).WriteArray(values)
                generated = gdal.GetDriverByName("COG").CreateCopy(path, source, options=[
                    "BLOCKSIZE=128", "COMPRESS=DEFLATE", "PREDICTOR=NO", "OVERVIEWS=NONE"])
                generated = None
                data = bytes(gdal.VSIGetMemFileBuffer_unsafe(path))
                dataset = gdal.OpenEx(path, gdal.OF_READONLY | gdal.OF_RASTER)
                self.assertEqual(dataset.GetMetadata("IMAGE_STRUCTURE").get("LAYOUT"), "COG")
                band = dataset.GetRasterBand(1)
                blocks = tuple(CogBlock(row, col,
                               int(band.GetMetadataItem(f"BLOCK_OFFSET_{col}_{row}", "TIFF")),
                               int(band.GetMetadataItem(f"BLOCK_SIZE_{col}_{row}", "TIFF")))
                               for row in range(2) for col in range(2))
                transform = dataset.GetGeoTransform()
                tile = IndexedTerrainTile("generated-cog", "synthetic-v1", "https://data.example.test/generated.tif",
                                          (-10, 17.44, -7.44, 20), len(data), '"synthetic-etag"', sha256(data))
                level = CogLevel("native", 256, 256, transform, 128, 128, blocks)
                metadata_hash = sha256(json.dumps([transform, [vars(block) for block in blocks]], sort_keys=True).encode())
                plan = plan_cog_ranges(CogLayout(tile, (level,), metadata_hash), DataRequest((-9.99, 18.75, -8.75, 19.99)))
                self.assertEqual(len(plan.requests), 1)
                first, last = plan.requests[0].byte_range
                self.assertEqual((first, last), (blocks[0].offset, blocks[0].offset+blocks[0].byte_count-1))
                dtype = "<f4" if data[:2] == b"II" else ">f4"
                decoded = np.frombuffer(zlib.decompress(data[first:last+1]), dtype=dtype).reshape(128, 128)
                np.testing.assert_array_equal(decoded, values[:128, :128])
                self.assertIsNone(plan.requests[0].expected_sha256)
        finally:
            band = dataset = source = None
            gdal.Unlink(path)

    def test_index_intersection_uses_only_supplied_entries_and_preserves_version(self):
        tile = synthetic_cog().tile
        unrelated = replace(tile, url="https://data.example.test/unrelated.tif", bbox=(20, -30, 21, -29))
        plan = plan_copernicus_tiles(DataRequest((-1.9, .1, -.1, 1.9)), [unrelated, tile],
                                     source_id=tile.source_id, source_version=tile.source_version,
                                     index_metadata_sha256=sha256(b"actual supplied index fixture"))
        self.assertEqual(plan.status, "planned")
        self.assertEqual(plan.stage, "COPERNICUS_COG_METADATA_REQUIRED")
        self.assertEqual(len(plan.requests), 1)
        request = plan.requests[0]
        self.assertEqual(request.url, tile.url)
        self.assertEqual(request.source_version, tile.source_version)
        self.assertEqual(request.byte_range, (0, tile.object_bytes-1))
        self.assertIsNone(request.expected_sha256)
        self.assertEqual(plan.metadata["objects"][0]["wholeObjectSha256"], tile.sha256)
        self.assertEqual(plan.coverage["catalogCompleteness"], "UNVERIFIED")

    def test_index_missing_and_touching_edge_do_not_synthesize_tile_existence(self):
        tile = synthetic_cog().tile
        for entries, bbox in (([], (-2, 0, 0, 2)), ([tile], (0, 0, 1, 1))):
            with self.subTest(bbox=bbox):
                plan = plan_copernicus_tiles(DataRequest(bbox), entries,
                                             source_id=tile.source_id, source_version=tile.source_version)
                self.assertEqual(plan.status, "unavailable")
                self.assertFalse(plan.requests)
                self.assertEqual(plan.metadata["reason"], "NO_SUPPLIED_INDEX_INTERSECTION")

    def test_index_hemisphere_dateline_and_version_mismatch(self):
        base = synthetic_cog().tile
        east = replace(base, url="https://data.example.test/east.tif", bbox=(179, -20, 180, -19))
        west = replace(base, url="https://data.example.test/west.tif", bbox=(-180, -20, -179, -19))
        request = DataRequest((179.5, -20, -179.5, -19))
        plan = plan_copernicus_tiles(request, [east, west], source_id=base.source_id, source_version=base.source_version)
        self.assertEqual(len(plan.requests), 2)
        self.assertFalse(plan.coverage["partsWithNoIndexEntry"])
        mismatch = plan_copernicus_tiles(request, [east, replace(west, source_version="different")],
                                         source_id=base.source_id, source_version=base.source_version)
        self.assertEqual(mismatch.status, "version_changed")
        self.assertFalse(mismatch.requests)

    def test_explicit_bounded_full_tile_fallback_uses_whole_object_hash(self):
        tile = synthetic_cog().tile
        args = dict(source_id=tile.source_id, source_version=tile.source_version, allow_full_tile=True)
        plan = plan_copernicus_tiles(DataRequest(tile.bbox), [tile], **args)
        self.assertEqual(plan.stage, "COPERNICUS_BOUNDED_FULL_TILE")
        self.assertIsNone(plan.requests[0].byte_range)
        self.assertEqual(plan.requests[0].expected_sha256, tile.sha256)
        for bad in (replace(tile, object_bytes=None), replace(tile, object_bytes=65*1024*1024)):
            with self.subTest(size=bad.object_bytes):
                plan = plan_copernicus_tiles(DataRequest(tile.bbox), [bad], **args)
                self.assertEqual(plan.status, "unavailable")
                self.assertFalse(plan.requests)

    def test_duplicate_index_and_unbounded_response_are_rejected(self):
        tile = synthetic_cog().tile
        for entries, options in (([tile, tile], {}), ([tile], {"max_bytes": 65*1024*1024})):
            with self.subTest(options=options), self.assertRaises(DataError):
                plan_copernicus_tiles(DataRequest(tile.bbox), entries,
                                      source_id=tile.source_id, source_version=tile.source_version, **options)

    def test_world_bbox_and_many_index_entries_cannot_schedule_global_tile_batch(self):
        stems = []
        for west in range(-180, 77):
            hemisphere = "W" if west < 0 else "E"
            stems.append(f"Copernicus_DSM_COG_10_N00_00_{hemisphere}{abs(west):03d}_00_DEM")
        records, digest = parse_copernicus_index(("\n".join(stems)+"\n").encode(), self.index_plan())
        self.assertEqual(len(records), 257)
        with self.assertRaisesRegex(DataError, "exceed max_tiles"):
            plan_copernicus_tiles(DataRequest((-180, -90, 180, 90)), records,
                                  source_id=records[0].source_id, source_version=records[0].source_version,
                                  index_metadata_sha256=digest)

    def test_full_tile_aggregate_bytes_are_bounded_before_batch_is_returned(self):
        first = synthetic_cog().tile
        second = replace(first, url="https://data.example.test/other.tif", bbox=(0, 0, 2, 2))
        args = dict(source_id=first.source_id, source_version=first.source_version, allow_full_tile=True)
        with self.assertRaisesRegex(DataError, "full-tile batch exceeds max_total_bytes"):
            plan_copernicus_tiles(DataRequest((-2, 0, 2, 2)), [first, second],
                                  max_total_bytes=first.object_bytes, **args)
        plan = plan_copernicus_tiles(DataRequest((-2, 0, 2, 2)), [first, second],
                                     max_total_bytes=2*first.object_bytes, **args)
        self.assertEqual(plan.metadata["plannedResponseBytes"], 8192)
        self.assertEqual(plan.metadata["selectedTileCount"], 2)
        self.assertEqual(len(plan.requests), 2)

    def test_metadata_probe_aggregate_and_tighter_tile_caps_are_enforced(self):
        first = synthetic_cog().tile
        second = replace(first, url="https://data.example.test/other.tif", bbox=(0, 0, 2, 2))
        args = dict(source_id=first.source_id, source_version=first.source_version)
        with self.assertRaisesRegex(DataError, "metadata-probe batch exceeds max_total_bytes"):
            plan_copernicus_tiles(DataRequest((-2, 0, 2, 2)), [first, second],
                                  metadata_probe_bytes=32, max_total_bytes=63, **args)
        with self.assertRaisesRegex(DataError, "exceed max_tiles"):
            plan_copernicus_tiles(DataRequest((-2, 0, 2, 2)), [first, second], max_tiles=1, **args)
        plan = plan_copernicus_tiles(DataRequest((-2, 0, 2, 2)), [first, second],
                                     metadata_probe_bytes=32, max_total_bytes=64, **args)
        self.assertEqual(plan.metadata["plannedResponseBytes"], 64)

    def test_batch_limits_reject_unbounded_or_invalid_values(self):
        tile = synthetic_cog().tile
        for options in ({"max_tiles": 0}, {"max_tiles": True}, {"max_tiles": 257},
                        {"max_total_bytes": 0}, {"max_total_bytes": 513*1024*1024},
                        {"max_total_bytes": float("inf")}):
            with self.subTest(options=options), self.assertRaises(DataError):
                plan_copernicus_tiles(DataRequest(tile.bbox), [tile],
                                      source_id=tile.source_id, source_version=tile.source_version, **options)

    def test_cog_native_ranges_use_actual_compressed_block_offsets(self):
        layout = synthetic_cog()
        plan = plan_cog_ranges(layout, DataRequest((-1.9, 1.1, -1.1, 1.9)))
        self.assertEqual(plan.status, "planned")
        self.assertEqual(len(plan.requests), 1)
        request = plan.requests[0]
        self.assertEqual(request.byte_range, (1000, 1079))
        self.assertEqual(request.max_bytes, 80)
        self.assertIsNone(request.expected_sha256)
        self.assertEqual(request.total_object_bytes, 4096)
        self.assertEqual(request.expected_etag, layout.tile.etag)
        self.assertEqual(request.source_metadata_sha256, layout.metadata_sha256)
        self.assertEqual(plan.coverage["sourcePixelWindows"], [[0, 0, 2, 2]])
        self.assertFalse(plan.metadata["rangeDecodeExecuted"])

    def test_cog_south_up_and_explicit_source_overview_are_supported(self):
        south_up = plan_cog_ranges(synthetic_cog(south_up=True), DataRequest((-1.9, 1.1, -1.1, 1.9)))
        self.assertEqual(south_up.requests[0].byte_range, (1200, 1279))
        self.assertEqual(south_up.coverage["sourcePixelWindows"], [[0, 2, 2, 2]])
        overview = plan_cog_ranges(synthetic_cog(), DataRequest((-2, 1, -1, 2)), level_id="overview-a")
        self.assertEqual(overview.requests[0].byte_range, (2000, 2039))
        self.assertEqual(overview.metadata["transform"], [-2, 1, 0, 2, 0, -1])
        self.assertIn("EXPLICIT_SOURCE_OVERVIEW_SELECTED", overview.warnings)

    def test_cog_missing_centers_invalid_layout_and_block_budgets(self):
        layout = synthetic_cog()
        self.assertEqual(plan_cog_ranges(layout, DataRequest((20, 0, 21, 1))).status, "unavailable")
        native = layout.levels[0]
        invalid_levels = [replace(native, blocks=native.blocks[:-1]),
                          replace(native, blocks=(replace(native.blocks[0], offset=4090), *native.blocks[1:])),
                          replace(native, transform=(-2, .5, .1, 2, 0, -.5))]
        for invalid in invalid_levels:
            with self.subTest(level=invalid.level_id), self.assertRaises(DataError):
                plan_cog_ranges(replace(layout, levels=(invalid,)), DataRequest(layout.tile.bbox))
        with self.assertRaisesRegex(DataError, "max_blocks"):
            plan_cog_ranges(layout, DataRequest(layout.tile.bbox), max_blocks=1)
        with self.assertRaisesRegex(DataError, "response cap"):
            plan_cog_ranges(layout, DataRequest(layout.tile.bbox), max_bytes=40)

    def test_cog_very_narrow_bbox_keeps_actual_center_without_epsilon_snapping(self):
        plan = plan_cog_ranges(synthetic_cog(), DataRequest((-1.750000000001, 1.749999999999,
                                                            -1.749999999999, 1.750000000001)))
        self.assertEqual(plan.status, "planned")
        self.assertEqual(plan.coverage["sourcePixelWindows"], [[0, 0, 1, 1]])


class GebcoSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.metadata = synthetic_metadata()
        self.x = np.arange(8, dtype=np.float64) - 3.5
        self.y = np.arange(6, dtype=np.float64) - 2.5

    def test_without_axes_plan_requests_coordinates_only_not_global_elevation(self):
        plan = plan_gebco_subset(DataRequest((-2, -1, 1, 1)), self.metadata)
        query = unquote(urlsplit(plan.requests[0].url).query)
        self.assertEqual(query, "lon[0:1:7],lat[0:1:5]")
        self.assertEqual(plan.stage, "GEBCO_COORDINATE_METADATA_REQUIRED")
        self.assertNotIn("elevation", query)
        self.assertFalse(plan.metadata["globalElevationRequested"])
        with self.assertRaisesRegex(DataError, "byte budget"):
            plan_gebco_subset(DataRequest((-2, -1, 1, 1)), self.metadata, max_bytes=100)

    def test_actual_coordinate_response_and_chunks_are_parsed_without_elevation(self):
        data = axes_ascii(self.x, self.y)
        x, y = parse_gebco_axes(data, self.metadata, expected_sha256=sha256(data))
        np.testing.assert_array_equal(x, self.x)
        np.testing.assert_array_equal(y, self.y)
        chunked = data.replace(b"-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5",
                               b"[0], -3.5, -2.5, -1.5, -0.5\n[4], 0.5, 1.5, 2.5, 3.5")
        np.testing.assert_array_equal(parse_gebco_axes(chunked, self.metadata)[0], self.x)
        with self.assertRaises(DataError):
            parse_gebco_axes(chunked.replace(b"[4]", b"[5]"), self.metadata)

    def test_actual_axes_select_half_open_bbox_and_inclusive_dap_indices(self):
        plan = plan_gebco_subset(DataRequest((-2, -1, 1, 1)), self.metadata, self.x, self.y)
        self.assertEqual(unquote(urlsplit(plan.requests[0].url).query), "elevation[2:1:3][2:1:4]")
        subset = plan.metadata["subsets"][0]
        self.assertEqual(subset["shape"], [2, 3])
        self.assertEqual(subset["x"], [-1.5, -.5, .5])
        self.assertEqual(subset["y"], [-.5, .5])
        self.assertNotEqual(plan.metadata["sourceMetadataSha256"], self.metadata["sourceMetadataSha256"])

    def test_actual_axes_can_be_descending_latitude_or_global_dateline(self):
        descending = plan_gebco_subset(DataRequest((-2, -1, 1, 1)), self.metadata, self.x, self.y[::-1])
        self.assertEqual(descending.metadata["subsets"][0]["y"], [.5, -.5])
        global_x = np.linspace(-157.5, 157.5, 8)
        split = plan_gebco_subset(DataRequest((150, -1, -150, 1)), self.metadata, global_x, self.y)
        self.assertEqual(len(split.requests), 2)
        self.assertEqual(split.metadata["subsets"][0]["columnIndices"], [7, 1, 7])
        self.assertEqual(split.metadata["subsets"][1]["columnIndices"], [0, 1, 0])

    def test_axis_shapes_irregularity_global_grid_and_budgets_reject_explicitly(self):
        pairs = [(self.x[:-1], self.y), (self.x[::-1], self.y),
                 (self.x + np.array([0, 0, .1, 0, 0, 0, 0, 0]), self.y),
                 (self.x, np.array([np.nan, *self.y[1:]]))]
        for x, y in pairs:
            with self.subTest(shape=x.shape), self.assertRaises(DataError):
                plan_gebco_subset(DataRequest((-2, -1, 1, 1)), self.metadata, x, y)
        with self.assertRaisesRegex(DataError, "global elevation"):
            plan_gebco_subset(DataRequest((-10, -10, 10, 10)), self.metadata, self.x, self.y)
        with self.assertRaisesRegex(DataError, "budget"):
            plan_gebco_subset(DataRequest((-2, -1, 1, 1)), self.metadata, self.x, self.y, max_cells=1)
        with self.assertRaisesRegex(DataError, "both actual"):
            plan_gebco_subset(DataRequest((-2, -1, 1, 1)), self.metadata, self.x)

    def test_signed_ascii_preserves_values_axes_datum_and_independent_nodata(self):
        metadata = synthetic_metadata(extra="Int16 _FillValue -32767; Int16 valid_range -30000, 30000;")
        values = np.array([[-32767, -12, 0], [9, 32767, -4]], dtype=np.int16)
        data = grid_ascii(values, [-1.5, -.5, .5], [-.5, .5])
        raster = parse_gebco_ascii(data, metadata, expected_sha256=sha256(data))
        np.testing.assert_array_equal(raster.values, values)
        np.testing.assert_array_equal(raster.valid, [[False, True, True], [True, False, True]])
        self.assertEqual(raster.values.dtype, np.dtype(np.int16))
        self.assertEqual(raster.metadata["nodata"], -32767)
        self.assertEqual(raster.metadata["verticalDatum"], "Synthetic declared datum")
        self.assertEqual(raster.metadata["quantity"], "SIGNED_ELEVATION")
        self.assertEqual(raster.metadata["oceanMaskStatus"], "UNRESOLVED")
        self.assertEqual(raster.metadata["transform"], [-2, 1, 0, -1, 0, 1])
        self.assertEqual(raster.metadata["inputSha256"], sha256(data))

    def test_ascii_plan_binds_returned_shape_axes_version_and_singleton_spacing(self):
        request = DataRequest((-2, -1, 1, 1))
        plan = plan_gebco_subset(request, self.metadata, self.x, self.y)
        data = grid_ascii([[-9, 0, 2], [4, 5, -6]], [-1.5, -.5, .5], [-.5, .5])
        raster = parse_gebco_ascii(data, self.metadata, plan=plan)
        self.assertEqual(raster.metadata["subsetIndices"], {"rows": [2, 1, 3], "columns": [2, 1, 4]})
        with self.assertRaisesRegex(DataError, "planned axes"):
            parse_gebco_ascii(data.replace(b"-1.5, -0.5, 0.5", b"-1.4, -0.4, 0.6"), self.metadata, plan=plan)
        changed = dict(self.metadata, sourceVersion="changed-version")
        with self.assertRaisesRegex(DataError, "identity/version"):
            parse_gebco_ascii(data, changed, plan=plan)
        one = plan_gebco_subset(DataRequest((-.6, -.6, -.4, -.4)), self.metadata, self.x, self.y)
        singleton = parse_gebco_ascii(grid_ascii([[-8]], [-.5], [-.5]), self.metadata, plan=one)
        self.assertEqual(singleton.values[0, 0], -8)
        self.assertEqual(singleton.metadata["transform"], [-1, 1, 0, -1, 0, 1])

    def test_ascii_truncation_duplicate_indices_overflow_invalid_tokens_and_sections(self):
        data = grid_ascii([[-9, 0, 2], [4, 5, -6]], [-1.5, -.5, .5], [-.5, .5])
        bad = [data.replace(b"[1],", b"[0],"), data.replace(b"[1], 4, 5, -6\n", b""),
               data.replace(b"-9, 0, 2", b"-32769, 0, 2"),
               data.replace(b"-9, 0, 2", b"-9.5, 0, 2"),
               data.replace(b"-9, 0, 2", b"-9, 0"),
               data + b"elevation.lon[3]\n-1.5, -0.5, 0.5\n", b"<html>service error</html>",
               data.replace(b"elevation.lat[2]", b"elevation.lat[3]")]
        for malformed in bad:
            with self.subTest(bytes=len(malformed)), self.assertRaises(DataError):
                parse_gebco_ascii(malformed, self.metadata)
        with self.assertRaisesRegex(DataError, "SHA-256 mismatch"):
            parse_gebco_ascii(data, self.metadata, expected_sha256="0"*64)
        with self.assertRaisesRegex(DataError, "cell budget"):
            parse_gebco_ascii(data, self.metadata, max_cells=1)

    def test_dds_das_type_axes_units_packing_and_duplicate_declarations_reject(self):
        variations = [grid_dds().replace(b"Int16 elevation", b"Float32 elevation"),
                      grid_dds().replace(b"Float64 lon[lon = 8];", b"Float64 lon[lon = 7];", 1),
                      grid_dds().replace(b"String crs;", b"String crs; String crs;")]
        for dds in variations:
            with self.subTest(dds=dds[:40]), self.assertRaises(DataError):
                parse_gebco_metadata(dds, grid_das(), source_id=_ID, source_version=_VERSION, source_url=_URL)
        for das in [grid_das(unit="feet"), grid_das(positive="down"), grid_das(extra="Float64 scale_factor .1;"),
                    grid_das(extra='String _Unsigned "true";'),
                    grid_das().replace(b'"EPSG:4326"', b'"EPSG:3857"'),
                    grid_das().replace(b'String units "m";', b'String units "m"; String units "m";')]:
            with self.subTest(das=das[-40:]), self.assertRaises(DataError):
                parse_gebco_metadata(grid_dds(), das, source_id=_ID, source_version=_VERSION, source_url=_URL)

    def test_response_dataset_identity_and_source_dimension_limits_are_bound(self):
        data = grid_ascii([[-9, 0, 2], [4, 5, -6]], [-1.5, -.5, .5], [-.5, .5])
        with self.assertRaisesRegex(DataError, "dataset identity"):
            parse_gebco_ascii(data.replace(b"fixture/grid.nc", b"other/changed.nc"), self.metadata)
        too_wide = grid_ascii(np.zeros((2, 9), dtype=np.int16), np.arange(9)-4, [-.5, .5])
        with self.assertRaisesRegex(DataError, "global DDS shape"):
            parse_gebco_ascii(too_wide, self.metadata)
        axes = axes_ascii(self.x, self.y)
        with self.assertRaisesRegex(DataError, "dataset identity"):
            parse_gebco_axes(axes.replace(b"fixture/grid.nc", b"other/changed.nc"), self.metadata)
        with self.assertRaises(DataError):
            parse_gebco_axes(axes.replace(b"} fixture/grid.nc", b"Int16 unexpected; } fixture/grid.nc"), self.metadata)

    def test_source_dds_requires_standalone_axes_and_declared_geodesy_must_match(self):
        with self.assertRaisesRegex(DataError, "standalone Float64"):
            parse_gebco_metadata(grid_dds(full=False), grid_das(), source_id=_ID, source_version=_VERSION, source_url=_URL)
        for extra in (b"Float64 semi_major_axis 1;", b"Float64 inverse_flattening 2;",
                      b"Float64 longitude_of_prime_meridian 1;", b"Float64 earth_radius 6371000;"):
            das = grid_das().replace(b'String epsg_code "EPSG:4326";', b'String epsg_code "EPSG:4326"; '+extra)
            with self.subTest(extra=extra), self.assertRaisesRegex(DataError, "conflicts with WGS84"):
                parse_gebco_metadata(grid_dds(), das, source_id=_ID, source_version=_VERSION, source_url=_URL)

    def test_malformed_das_containers_and_deep_nesting_raise_dataerror(self):
        malformed = grid_das().replace(b'lon { String standard_name "longitude"; String units "degrees_east"; String axis "X"; }',
                                       b'String lon "oops";')
        deep = (b"Attributes { " + b"nested { "*40 + b"String value \"x\"; " + b"} "*40 + b"}")
        for das in (malformed, deep):
            with self.subTest(size=len(das)), self.assertRaises(DataError):
                parse_gebco_metadata(grid_dds(), das, source_id=_ID, source_version=_VERSION, source_url=_URL)


class NasaSyntheticTests(unittest.TestCase):
    def test_wmts_non_xyz_matrix_geometry_boundaries_and_padded_extents(self):
        metadata = synthetic_wmts()
        self.assertEqual(metadata["matrices"]["coarse-a"]["matrixWidth"], 3)
        self.assertAlmostEqual(metadata["matrices"]["coarse-a"]["spacingDegrees"], 1)
        matrix = metadata["matrices"]["coarse-a"]
        span = matrix["spacingDegrees"]*matrix["tileWidth"]
        # Use actual declared edges, including their representable precision.
        plan = plan_wmts_tiles(DataRequest((-180+span, 90-span, -180+2*span, 90)), metadata, matrix_id="coarse-a")
        self.assertEqual(len(plan.requests), 1)
        self.assertEqual(plan.metadata["tiles"][0]["row"], 0)
        self.assertEqual(plan.metadata["tiles"][0]["column"], 1)
        self.assertIn("/coarse-a/0/1.jpeg", plan.requests[0].url)
        padded = plan_wmts_tiles(DataRequest((-179, -89, -178, -88)), metadata, matrix_id="coarse-a")
        tile = padded.metadata["tiles"][0]
        np.testing.assert_allclose(tile["tileBBox"], [-180, -150, -60, -30], rtol=0, atol=1e-10)
        self.assertEqual(padded.requests[0].bbox[1], -90)
        self.assertFalse(padded.metadata["liveTileAccessVerified"])

    def test_wmts_epsg4326_authority_axis_order_and_dateline_split(self):
        metadata = synthetic_wmts(supported_crs="EPSG:4326", corner="90 -180")
        self.assertEqual(metadata["serviceAxisOrder"], "LATITUDE_LONGITUDE")
        np.testing.assert_array_equal(metadata["matrices"]["coarse-a"]["topLeft"], [-180, 90])
        plan = plan_wmts_tiles(DataRequest((179, -1, -179, 1)), metadata, matrix_id="coarse-a")
        self.assertEqual({tile["column"] for tile in plan.metadata["tiles"]}, {0, 2})
        self.assertEqual(len(plan.requests), 2)

    def test_wmts_actual_limits_control_available_levels_and_tiles(self):
        limits = ('<TileMatrixSetLimits><TileMatrixLimits><TileMatrix>coarse-a</TileMatrix>'
                  '<MinTileRow>0</MinTileRow><MaxTileRow>0</MaxTileRow>'
                  '<MinTileCol>1</MinTileCol><MaxTileCol>1</MaxTileCol>'
                  '</TileMatrixLimits></TileMatrixSetLimits>')
        metadata = synthetic_wmts(limits=limits)
        self.assertEqual(plan_wmts_tiles(DataRequest((-179, 0, -170, 10)), metadata,
                                         matrix_id="coarse-a").status, "unavailable")
        available = plan_wmts_tiles(DataRequest((-10, 0, 10, 10)), metadata, matrix_id="coarse-a")
        self.assertEqual(len(available.requests), 1)
        self.assertEqual(available.coverage["matrixLimits"]["maxCol"], 1)
        metadata["limits"] = {}
        self.assertEqual(plan_wmts_tiles(DataRequest((-10, 0, 10, 10)), metadata,
                                         matrix_id="coarse-a").status, "unavailable")

    def test_wmts_unknown_crs_entities_missing_layer_and_request_caps_reject(self):
        for data in [wmts_xml(supported_crs="EPSG:3857"),
                     wmts_xml().replace(b"<Contents>", b'<!DOCTYPE x [<!ENTITY a "x">]><Contents>'),
                     wmts_xml().replace(b"fixture-layer", b"other-layer")]:
            with self.subTest(size=len(data)), self.assertRaises(DataError):
                parse_wmts_metadata(data, layer_id="fixture-layer", source_id=_ID, source_version=_VERSION)
        with self.assertRaisesRegex(DataError, "max_tiles"):
            plan_wmts_tiles(DataRequest((-180, -90, 180, 90)), synthetic_wmts(), matrix_id="coarse-a", max_tiles=1)
        with self.assertRaisesRegex(DataError, "pixel budget"):
            plan_wmts_tiles(DataRequest((-10, 0, 10, 10)), synthetic_wmts(), matrix_id="coarse-a", max_tile_pixels=10)

    def test_wmts_tiny_scale_and_nonfinite_derived_span_are_rejected(self):
        for scale in (b"5e-324", b"1e308"):
            data = wmts_xml()
            begin = data.index(b"<ScaleDenominator>")+len(b"<ScaleDenominator>")
            end = data.index(b"</ScaleDenominator>")
            data = data[:begin]+scale+data[end:]
            if scale == b"1e308":
                data = data.replace(b"<TileWidth>120</TileWidth>", b"<TileWidth>1000000000000</TileWidth>")
            with self.subTest(scale=scale), self.assertRaisesRegex(DataError, "derived spacing/spans"):
                parse_wmts_metadata(data, layer_id="fixture-layer",
                                     source_id=_ID, source_version=_VERSION)

    def test_wmts_narrow_boundary_request_and_partial_declared_grid_coverage(self):
        plan = plan_wmts_tiles(DataRequest((-60.000000000001, 0, -59.999999999999, 1)),
                               synthetic_wmts(), matrix_id="coarse-a")
        self.assertEqual(plan.status, "planned")
        self.assertEqual({tile["column"] for tile in plan.metadata["tiles"]}, {0, 1})
        limits = ('<TileMatrixSetLimits><TileMatrixLimits><TileMatrix>coarse-a</TileMatrix>'
                  '<MinTileRow>0</MinTileRow><MaxTileRow>0</MaxTileRow>'
                  '<MinTileCol>1</MinTileCol><MaxTileCol>1</MaxTileCol>'
                  '</TileMatrixLimits></TileMatrixSetLimits>')
        partial = plan_wmts_tiles(DataRequest((-100, 0, 100, 10)), synthetic_wmts(limits=limits), matrix_id="coarse-a")
        self.assertFalse(partial.coverage["completeDeclaredGridCoverage"])
        self.assertIn("PARTIAL_DECLARED_WMTS_GRID_COVERAGE", partial.warnings)
        self.assertEqual(partial.coverage["validPixelSupport"], "UNVERIFIED")

    def test_wmts_trust_input_hash_includes_source_declarations(self):
        data = wmts_xml()
        first = parse_wmts_metadata(data, layer_id="fixture-layer", source_id=_ID, source_version=_VERSION,
                                    layer_metadata={"ongoing": False}, source_nominal_resolution_m=750)
        second = parse_wmts_metadata(data, layer_id="fixture-layer", source_id=_ID, source_version=_VERSION,
                                     layer_metadata={"ongoing": True}, source_nominal_resolution_m=750)
        self.assertEqual(first["wmtsXmlSha256"], sha256(data))
        self.assertEqual(first["wmtsXmlSha256"], second["wmtsXmlSha256"])
        self.assertNotEqual(first["sourceMetadataSha256"], second["sourceMetadataSha256"])

    def test_wms13_axis_order_dateline_widths_and_declared_source_resolution(self):
        plan = build_wms13_plan(DataRequest((-72, -35, -70, -33)), endpoint="https://data.example.test/wms",
                                layer="fixture-layer", source_id=_ID, source_version=_VERSION,
                                width=4, height=4, source_nominal_resolution_m=750)
        query = parse_qs(urlsplit(plan.requests[0].url).query)
        self.assertEqual(query["BBOX"], ["-35,-72,-33,-70"])
        self.assertEqual(query["CRS"], ["EPSG:4326"])
        self.assertEqual(plan.metadata["parts"][0]["transform"], [-72, .5, 0, -33, 0, -.5])
        self.assertEqual(plan.metadata["sourceNominalResolutionMeters"], 750)
        self.assertFalse(plan.metadata["nativeDetailIncreased"])
        split = build_wms13_plan(DataRequest((179, -2, -177, 2)), endpoint="https://data.example.test/wms",
                                 layer="fixture-layer", source_id=_ID, source_version=_VERSION,
                                 width=8, height=4)
        self.assertEqual([part["width"] for part in split.metadata["parts"]], [2, 6])
        self.assertEqual(len(split.requests), 2)

    def test_wms_png_preserves_encoded_channels_alpha_and_request_derived_grid(self):
        colors = np.array([[[20, 30, 40, 255], [0, 0, 0, 0]],
                           [[70, 80, 90, 255], [200, 100, 0, 255]]], dtype=np.uint8)
        output = BytesIO()
        Image.fromarray(colors).save(output, format="PNG")
        data = output.getvalue()
        plan = build_wms13_plan(DataRequest((-72, -35, -70, -33)), endpoint="https://data.example.test/wms",
                                layer="fixture-layer", source_id=_ID, source_version=_VERSION,
                                width=2, height=2)
        raster = parse_wms_png(data, plan, expected_sha256=sha256(data))
        np.testing.assert_array_equal(raster.values, colors)
        np.testing.assert_array_equal(raster.valid, [[True, False], [True, True]])
        np.testing.assert_array_equal(raster.x, [-71.5, -70.5])
        np.testing.assert_array_equal(raster.y, [-33.5, -34.5])
        self.assertEqual(raster.metadata["inputSha256"], sha256(data))
        self.assertEqual(raster.metadata["colorConversion"], "NONE")
        self.assertEqual(raster.metadata["georeferencingSource"], "WMS13_REQUEST_BBOX_AND_OUTPUT_SIZE")
        self.assertEqual(raster.metadata["sourceVersion"], _VERSION)

    def test_wms_wrong_size_service_error_hash_and_size_bounds_reject(self):
        plan = build_wms13_plan(DataRequest((-2, -1, 2, 1)), endpoint="https://data.example.test/wms",
                                layer="fixture-layer", source_id=_ID, source_version=_VERSION, width=2, height=2)
        output = BytesIO()
        Image.new("RGB", (3, 2)).save(output, format="PNG")
        for data in (output.getvalue(), b"<ServiceExceptionReport>no layer</ServiceExceptionReport>"):
            with self.subTest(size=len(data)), self.assertRaises(DataError):
                parse_wms_png(data, plan)
        with self.assertRaisesRegex(DataError, "SHA-256 mismatch"):
            parse_wms_png(output.getvalue(), plan, expected_sha256="0"*64)
        for options in ({"width": 0}, {"width": 100, "max_pixels": 10}, {"max_bytes": 65*1024*1024}):
            with self.subTest(options=options), self.assertRaises(DataError):
                build_wms13_plan(DataRequest((-2, -1, 2, 1)), endpoint="https://data.example.test/wms",
                                 layer="fixture-layer", source_id=_ID, source_version=_VERSION,
                                 **dict({"width": 2, "height": 2}, **options))


class ArchivedAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        archive = (Path(__file__).resolve().parents[2] / "astra-map-quality-v1"
                   / "inputs" / "ESSENTIAL_MAP_SAMPLES.zip")
        cls.files = {}
        with zipfile.ZipFile(archive) as bundle:
            cls.manifest = json.loads(bundle.read("DATA_MANIFEST.json"))
            cls.bathymetry = next(x for x in cls.manifest["datasets"] if x["data_class"] == "ocean_bathymetry")
            cls.surface = next(x for x in cls.manifest["datasets"] if x["data_class"] == "land_surface_texture")
            names = ["provenance/GEBCO_2026.dds", "provenance/GEBCO_2026.das",
                     "provenance/GEBCO_2026_subset_opendap.ascii", "provenance/bathymetry_acquisition.json",
                     "provenance/BlueMarble_WMTS_selected.xml", "provenance/BlueMarble_NextGeneration_metadata.json",
                     cls.bathymetry["relative_path"], cls.surface["relative_path"]]
            names += [x["relative_path"] for x in cls.surface["sidecars"]]
            cls.files = {name: bundle.read(name) for name in names}
        entry = cls.bathymetry
        cls.ge = parse_gebco_metadata(cls.files["provenance/GEBCO_2026.dds"], cls.files["provenance/GEBCO_2026.das"],
                                      source_id=entry["id"], source_version=entry["version"], source_url=entry["original_url"])
        xml = cls.files["provenance/BlueMarble_WMTS_selected.xml"]
        layer_id = ET.fromstring(xml).find("{http://www.opengis.net/wmts/1.0}Layer/{http://www.opengis.net/ows/1.1}Identifier").text
        entry = cls.surface
        cls.wm = parse_wmts_metadata(xml, layer_id=layer_id, source_id=entry["id"], source_version=entry["version"],
                                     layer_metadata=json.loads(cls.files["provenance/BlueMarble_NextGeneration_metadata.json"]),
                                     source_nominal_resolution_m=500)

    def test_real_dds_das_preserve_shapes_sign_datum_and_coordinate_evidence_limits(self):
        self.assertEqual(self.ge["globalShape"], [43200, 86400])
        self.assertEqual(self.ge["dtype"], "Int16")
        self.assertEqual(self.ge["verticalDatum"], "EPSG:5831")
        self.assertEqual(self.ge["positive"], "up")
        self.assertEqual(self.ge["sourceAttributes"]["NC_GLOBAL"]["date_created"], "2026-04-17")
        self.assertEqual(self.ge["globalAxisVerification"], "ACTUAL_VECTORS_REQUIRED")
        plan = plan_gebco_subset(DataRequest(tuple(self.bathymetry["sample_extent"])), self.ge)
        self.assertEqual(plan.stage, "GEBCO_COORDINATE_METADATA_REQUIRED")
        self.assertNotIn("elevation", unquote(urlsplit(plan.requests[0].url).query))

    def test_real_ascii_equals_all_packaged_signed_netcdf_cells_and_axes(self):
        data = self.files["provenance/GEBCO_2026_subset_opendap.ascii"]
        actual = parse_gebco_ascii(data, self.ge)
        expected = parse_bathymetry(self.files[self.bathymetry["relative_path"]], expected_sha256=self.bathymetry["sha256"])
        np.testing.assert_array_equal(actual.values, expected.values)
        np.testing.assert_array_equal(actual.x, expected.x)
        np.testing.assert_array_equal(actual.y, expected.y)
        np.testing.assert_array_equal(actual.valid, expected.valid)
        self.assertEqual(int((actual.values < 0).sum()), self.bathymetry["negative_elevation_cells"])
        self.assertEqual(actual.metadata["inputSha256"], sha256(data))
        self.assertIsNone(actual.metadata["nodata"])

    def test_real_wmts_metadata_is_crs84_non_xyz_and_coarse_tiles_are_padded(self):
        metadata = self.wm
        self.assertEqual(metadata["matrixSetId"], "500m")
        self.assertEqual(metadata["serviceAxisOrder"], "LONGITUDE_LATITUDE")
        self.assertEqual(metadata["matrices"]["1"]["matrixWidth"], 3)
        self.assertEqual(metadata["matrices"]["1"]["tileWidth"], 512)
        self.assertAlmostEqual(metadata["matrices"]["7"]["spacingDegrees"], .00439453125)
        self.assertFalse(metadata["layerMetadata"]["ongoing"])
        self.assertEqual(metadata["layerMetadata"]["title"], "Blue Marble (August 2004)")
        plan = plan_wmts_tiles(DataRequest((-180, -90, 180, 90)), metadata, matrix_id="0")
        self.assertEqual(len(plan.requests), 2)
        self.assertGreater(plan.metadata["tiles"][1]["tileBBox"][2], 180)
        self.assertGreaterEqual(min(req.bbox[1] for req in plan.requests), -90)
        self.assertFalse(plan.metadata["imageDecodeExecuted"])

    def test_real_wms_png_raw_colors_match_existing_sidecar_parser(self):
        entry = self.surface
        parsed = urlsplit(entry["original_url"])
        endpoint = parsed.scheme + "://" + parsed.netloc + parsed.path
        query = parse_qs(parsed.query)
        plan = build_wms13_plan(DataRequest(tuple(entry["sample_extent"])), endpoint=endpoint,
                                layer=query["LAYERS"][0], source_id=entry["id"], source_version=entry["version"],
                                width=entry["dimensions"][0], height=entry["dimensions"][1],
                                source_nominal_resolution_m=500,
                                source_metadata_sha256=self.wm["sourceMetadataSha256"])
        output_query = parse_qs(urlsplit(plan.requests[0].url).query)
        self.assertEqual(list(map(float, output_query["BBOX"][0].split(","))), entry["request_bbox_wms13_latlon"])
        actual = parse_wms_png(self.files[entry["relative_path"]], plan, expected_sha256=entry["sha256"])
        sidecars = {Path(x["relative_path"]).suffix: self.files[x["relative_path"]] for x in entry["sidecars"]}
        expected = parse_surface(self.files[entry["relative_path"]], sidecars[".pgw"], sidecars[".prj"],
                                  expected_sha256=entry["sha256"])
        np.testing.assert_array_equal(actual.values, expected.values)
        np.testing.assert_allclose(actual.x, expected.x, rtol=0, atol=1e-12)
        np.testing.assert_allclose(actual.y, expected.y, rtol=0, atol=1e-12)
        np.testing.assert_allclose(actual.bbox, entry["sample_extent"], rtol=0, atol=1e-12)
        self.assertEqual(actual.metadata["sourceVersion"], entry["version"])
        self.assertFalse(actual.metadata["nativeDetailIncreased"])


if __name__ == "__main__":
    unittest.main()
