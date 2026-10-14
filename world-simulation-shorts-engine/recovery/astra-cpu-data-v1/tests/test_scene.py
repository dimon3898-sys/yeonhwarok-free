"""Config-only optional mapData bridge, including preserved stored scenes."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from astra_cpu.model import DataError, sha256, split_dateline
from astra_cpu.providers import ArchiveCatalog, SourceSpec
from astra_cpu.scene import ScenePreparation, prepare_scene, renderer_fingerprint


def source_spec(role, *, version="fixture-source-v1", license_verified=False):
    data_class = {"terrain": "land_elevation", "bathymetry": "ocean_bathymetry",
                  "surfaceTexture": "land_surface_texture"}[role]
    return SourceSpec("fixture-"+role, version, "https://data.example.test/"+role,
                      data_class, "fixture/"+role, sha256(role.encode()),
                      {"description": "Synthetic source resolution"}, "Synthetic declared datum",
                      "Synthetic fixture attribution", license_verified=license_verified)


def registry():
    return {spec.source_id: spec for spec in (source_spec(role) for role in
                                             ("terrain", "bathymetry", "surfaceTexture"))}


def enabled_map(*roles, bbox=None):
    settings = {"enabled": True, "bbox": bbox if bbox is not None else [-74, -35, -70, -31],
                "crs": "EPSG:4326", "targetGroundResolution": 750}
    for role in roles or ("terrain",):
        settings[role] = {"sourceId": "fixture-"+role, "version": "fixture-source-v1"}
    return settings


class SceneConfigTests(unittest.TestCase):
    def setUp(self):
        self.scene = {"metadata": {"schema": "SYNTHETIC_SCENE"}, "layout": {"width": 1080, "height": 1920},
                      "cameraKeyframes": [{"frame": 0, "bounds": [1, 2, 3, 4]}],
                      "units": [{"id": "fixture-unit", "anchor": [5, 6]}],
                      "timeline": {"start": 0, "end": 10}, "arbitraryOriginalField": {"value": "unchanged"}}

    def test_missing_mapdata_preserves_input_payload_fingerprint_and_does_no_work(self):
        before = deepcopy(self.scene)
        with patch("astra_cpu.providers.ArchiveCatalog.provider", side_effect=AssertionError("provider called")), \
             patch("astra_cpu.cache.FileCache.__init__", side_effect=AssertionError("cache created")):
            result = prepare_scene(self.scene)
        self.assertEqual(self.scene, before)
        self.assertEqual(result.renderer_scene, before)
        self.assertEqual(result.renderer_sha256, renderer_fingerprint(before))
        self.assertIsNot(result.renderer_scene, self.scene)
        self.assertFalse(result.enabled)
        self.assertFalse(result.gpu_activation)
        self.assertIsNone(result.map_data)
        self.assertIsNone(result.request)
        self.assertFalse(result.source_bindings)
        result.renderer_scene["metadata"]["schema"] = "mutated output"
        self.assertEqual(self.scene, before)

    def test_disabled_partial_config_does_not_resolve_sources_or_fill_input_defaults(self):
        self.scene["mapData"] = {"terrain": {"sourceId": "not-yet-registered"}, "cache": {"mode": "read_only"}}
        before = deepcopy(self.scene)
        result = prepare_scene(self.scene, sources=object())
        self.assertFalse(result.enabled)
        self.assertFalse(result.source_bindings)
        self.assertIsNone(result.request)
        self.assertEqual(result.map_data, before["mapData"])
        self.assertNotIn("mapData", result.renderer_scene)
        self.assertEqual(result.cache_policy["mode"], "read_only")
        self.assertEqual(result.cache_policy["maxBytes"], 64*1024*1024)
        self.assertEqual(self.scene, before)
        self.assertNotIn("enabled", self.scene["mapData"])

    def test_enabled_configuration_binds_only_explicit_roles_and_does_not_fetch(self):
        self.scene["mapData"] = enabled_map("terrain", "bathymetry", "surfaceTexture")
        sources = registry()
        before = deepcopy(self.scene)
        with patch("astra_cpu.providers.RasterProvider.provide", side_effect=AssertionError("source fetched")), \
             patch("astra_cpu.cache.FileCache.__init__", side_effect=AssertionError("cache created")):
            result = prepare_scene(self.scene, sources)
        self.assertTrue(result.enabled)
        self.assertEqual(set(result.source_bindings), {"terrain", "bathymetry", "surfaceTexture"})
        self.assertEqual(result.source_bindings["terrain"], sources["fixture-terrain"])
        self.assertIsNot(result.source_bindings["terrain"], sources["fixture-terrain"])
        self.assertFalse(result.source_bindings["terrain"].license_verified)
        self.assertEqual(result.request.bbox, (-74, -35, -70, -31))
        self.assertEqual(result.request.target_ground_resolution, 750)
        self.assertEqual(self.scene, before)
        expected_renderer = deepcopy(before)
        del expected_renderer["mapData"]
        self.assertEqual(result.renderer_scene, expected_renderer)
        self.assertEqual(result.renderer_sha256, renderer_fingerprint(expected_renderer))
        self.assertFalse(result.to_dict()["sourceFetchExecuted"])
        self.assertFalse(result.to_dict()["cacheCreated"])
        self.assertFalse(result.to_dict()["gpuActivation"])

    def test_one_role_and_dateline_bbox_are_valid_cpu_config(self):
        self.scene["mapData"] = enabled_map("bathymetry", bbox=[179, -10, -179, 10])
        result = prepare_scene(self.scene, registry())
        self.assertEqual(set(result.source_bindings), {"bathymetry"})
        self.assertEqual(split_dateline(result.request.bbox), [(179, -10, 180.0, 10), (-180.0, -10, -179, 10)])
        self.assertFalse(result.gpu_activation)

    def test_source_bindings_snapshot_nested_metadata_and_sidecars(self):
        spec = source_spec("surfaceTexture")
        spec.metadata["nested"] = {"registration": "original", "nativeSpacing": [.01, .01]}
        sidecar = {"relative_path": "fixture/surface.pgw", "sha256": sha256(b"original sidecar"),
                   "metadata": {"format": "original-worldfile"}}
        from dataclasses import replace
        spec = replace(spec, sidecars=(sidecar,))
        sources = {spec.source_id: spec}
        scene = dict(self.scene, mapData=enabled_map("surfaceTexture"))
        prepared = prepare_scene(scene, sources)
        binding = prepared.source_bindings["surfaceTexture"]
        self.assertEqual(binding, spec)
        self.assertIsNot(binding, spec)
        self.assertIsNot(binding.metadata, spec.metadata)
        self.assertIsNot(binding.sidecars[0], spec.sidecars[0])
        spec.metadata["nested"]["registration"] = "changed"
        spec.metadata["nested"]["nativeSpacing"][0] = 99
        spec.sidecars[0]["sha256"] = sha256(b"changed sidecar")
        spec.sidecars[0]["metadata"]["format"] = "changed-worldfile"
        self.assertNotEqual(binding, sources[spec.source_id])
        self.assertEqual(binding.metadata["nested"], {"registration": "original", "nativeSpacing": [.01, .01]})
        self.assertEqual(binding.sidecars[0]["sha256"], sha256(b"original sidecar"))
        self.assertEqual(binding.sidecars[0]["metadata"]["format"], "original-worldfile")
        binding.metadata["nested"]["registration"] = "binding-only change"
        self.assertEqual(spec.metadata["nested"]["registration"], "changed")

    def test_unknown_source_version_role_and_registry_identity_reject(self):
        settings = enabled_map()
        cases = [(dict(settings, terrain={"sourceId": "unknown", "version": "fixture-source-v1"}), registry()),
                 (dict(settings, terrain={"sourceId": "fixture-terrain", "version": "changed"}), registry()),
                 (dict(settings, terrain={"sourceId": "fixture-bathymetry", "version": "fixture-source-v1"}), registry()),
                 (settings, {"fixture-terrain": source_spec("bathymetry")}), (settings, None)]
        for settings, sources in cases:
            scene = dict(self.scene, mapData=settings)
            before = deepcopy(scene)
            with self.subTest(selector=settings.get("terrain")), self.assertRaises(DataError):
                prepare_scene(scene, sources)
            self.assertEqual(scene, before)

    def test_enabled_requires_bbox_and_complete_at_least_one_selector(self):
        cases = [{"enabled": True}, {"enabled": True, "bbox": [-2, -1, 2, 1]},
                 {"enabled": True, "terrain": {"sourceId": "fixture-terrain", "version": "fixture-source-v1"}},
                 {"enabled": True, "bbox": [-2, -1, 2, 1], "terrain": {}},
                 {"enabled": True, "bbox": [-2, -1, 2, 1], "terrain": {"sourceId": "fixture-terrain"}}]
        for settings in cases:
            with self.subTest(settings=settings), self.assertRaises(DataError):
                prepare_scene(dict(self.scene, mapData=settings), registry())

    def test_known_fields_and_cpu_only_flags_are_strict_even_when_disabled(self):
        cases = [None, [], "disabled", {"enabled": 0}, {"enabled": "false"}, {"gpuActivation": True},
                 {"country": "inferred"}, {"terrain": {"sourceURL": "https://other.example.test/"}},
                 {"cache": {"root": "/tmp/should-not-create"}}, {"cache": {"networkEnabled": True}},
                 {"surfaceTexture": None}, {"terrain": {"version": " "}},
                 {"cache": {"resume": 1}}, {"cache": {"mode": "automatic_network"}}]
        for settings in cases:
            with self.subTest(settings=settings), self.assertRaises(DataError):
                prepare_scene(dict(self.scene, mapData=settings))

    def test_finite_bbox_crs_and_resolution_are_required_when_present(self):
        cases = [{"bbox": [-2, 1, 2, -1]}, {"bbox": [0, 0, 0, 1]}, {"bbox": [-181, 0, 0, 1]},
                 {"bbox": [True, 0, 2, 1]}, {"bbox": [float("nan"), 0, 2, 1]},
                 {"bbox": [-2, 0, 2]}, {"crs": "EPSG:3857"}, {"crs": None},
                 {"targetGroundResolution": 0}, {"targetGroundResolution": -1},
                 {"targetGroundResolution": True}, {"targetGroundResolution": float("inf")},
                 {"targetGroundResolution": None}]
        for settings in cases:
            with self.subTest(settings=settings), self.assertRaises(DataError):
                prepare_scene(dict(self.scene, mapData=settings))

    def test_cache_limits_modes_and_boundary_values_match_config_contract(self):
        valid = {"mode": "bypass", "maxBytes": 1, "maxConcurrency": 8, "maxRetries": 5,
                 "timeoutSeconds": .01, "deadlineSeconds": 3600, "retryAfterCeilingSeconds": 0, "resume": True}
        result = prepare_scene(dict(self.scene, mapData={"enabled": False, "cache": valid}))
        self.assertEqual(result.cache_policy, valid)
        for key, value in [("maxBytes", 0), ("maxBytes", 64*1024*1024+1), ("maxConcurrency", 0),
                           ("maxConcurrency", 9), ("maxRetries", -1), ("maxRetries", 6), ("maxRetries", True),
                           ("timeoutSeconds", 0), ("deadlineSeconds", 3601), ("retryAfterCeilingSeconds", -1),
                           ("timeoutSeconds", float("nan")), ("deadlineSeconds", float("inf"))]:
            with self.subTest(key=key, value=value), self.assertRaises(DataError):
                prepare_scene(dict(self.scene, mapData={"cache": {key: value}}))

    def test_gpu_flag_cannot_be_configured_or_changed(self):
        result = prepare_scene(self.scene)
        with self.assertRaises(FrozenInstanceError):
            result.gpu_activation = True
        with self.assertRaises(TypeError):
            ScenePreparation({}, "hash", None, False, None, {}, {}, gpu_activation=True)
        self.assertFalse(result.gpu_activation)

    def test_cache_integral_json_numbers_normalize_without_mutating_input(self):
        scene = dict(self.scene, mapData={"cache": {"maxBytes": 1024.0, "maxConcurrency": 2.0, "maxRetries": 0.0}})
        before = deepcopy(scene)
        result = prepare_scene(scene)
        self.assertEqual(scene, before)
        self.assertIsInstance(scene["mapData"]["cache"]["maxBytes"], float)
        for name, expected in (("maxBytes", 1024), ("maxConcurrency", 2), ("maxRetries", 0)):
            self.assertIs(type(result.cache_policy[name]), int)
            self.assertEqual(result.cache_policy[name], expected)
        for name in ("maxBytes", "maxConcurrency", "maxRetries"):
            with self.subTest(name=name), self.assertRaises(DataError):
                prepare_scene(dict(self.scene, mapData={"cache": {name: 1.5}}))

    def test_non_json_types_and_deep_nesting_are_explicit_errors(self):
        cases = [[], {1: "nonstring key"}, {"values": (1, 2)}, {"values": object()}, {"x": float("nan")}]
        nested = {}
        for _ in range(66):
            nested = {"nested": nested}
        cases.append(nested)
        for scene in cases:
            with self.subTest(kind=type(scene).__name__), self.assertRaises(DataError):
                prepare_scene(scene)


class StoredSceneCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine_root = Path(__file__).resolve().parents[3]
        cls.paths = [cls.engine_root / "recovery/map-engine-unit-bundle-v1/fixtures/SCENE_PLAN.json",
                     cls.engine_root / "recovery/planner-night-run-v1/fixtures/SCENE_PLAN.json"]
        archive = cls.engine_root / "recovery/astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip"
        cls.catalog = ArchiveCatalog(archive, license_verified=False)

    def test_actual_stored_unit_and_planner_scenes_preserve_entire_renderer_payload(self):
        expected_schemas = {"MAP_ENGINE_UNIT_SCENE_V4", "PLANNER_SCENE_JSON_V1"}
        seen = set()
        for path in self.paths:
            raw_before = path.read_bytes()
            scene = json.loads(raw_before)
            before = deepcopy(scene)
            seen.add(scene.get("schema", scene.get("metadata", {}).get("schema")))
            with self.subTest(path=path.name):
                result = prepare_scene(scene)
                self.assertEqual(scene, before)
                self.assertEqual(result.renderer_scene, before)
                self.assertEqual(result.renderer_sha256, renderer_fingerprint(before))
                self.assertEqual(path.read_bytes(), raw_before)
                self.assertFalse(result.gpu_activation)
        self.assertEqual(seen, expected_schemas)

    def test_actual_augmented_scenes_strip_only_mapdata_and_bind_all_archive_roles(self):
        roles = {"land_elevation": "terrain", "ocean_bathymetry": "bathymetry",
                 "land_surface_texture": "surfaceTexture"}
        settings = {"enabled": True, "bbox": [128.25, 37.25, 128.75, 37.75],
                    "targetGroundResolution": 750, "cache": {"mode": "read_only"}}
        for spec in self.catalog.sources.values():
            settings[roles[spec.data_class]] = {"sourceId": spec.source_id, "version": spec.source_version}
        for path in self.paths:
            original = json.loads(path.read_bytes())
            augmented = deepcopy(original)
            augmented["mapData"] = deepcopy(settings)
            before = deepcopy(augmented)
            with self.subTest(path=path.name), \
                 patch.object(self.catalog, "read_bytes", side_effect=AssertionError("source bytes read")), \
                 patch.object(self.catalog, "provider", side_effect=AssertionError("provider invoked")), \
                 patch("astra_cpu.cache.FileCache.__init__", side_effect=AssertionError("cache created")):
                result = prepare_scene(augmented, self.catalog)
            self.assertEqual(result.renderer_scene, original)
            self.assertEqual(result.renderer_sha256, renderer_fingerprint(original))
            self.assertEqual(augmented, before)
            self.assertEqual(set(result.source_bindings), {"terrain", "bathymetry", "surfaceTexture"})
            self.assertFalse(result.gpu_activation)
            self.assertFalse(result.to_dict()["sourceFetchExecuted"])

    def test_additive_schema_describes_wrapper_without_extending_existing_strict_schemas(self):
        schema = json.loads((Path(__file__).resolve().parents[1] / "fixtures/map_data.schema.json").read_bytes())
        self.assertTrue(schema["additionalProperties"])
        self.assertNotIn("required", schema)
        self.assertEqual(set(schema["properties"]), {"mapData"})
        self.assertFalse(schema["$defs"]["mapData"]["additionalProperties"])
        self.assertFalse(schema["$defs"]["selector"]["additionalProperties"])
        self.assertEqual(schema["$defs"]["mapData"]["properties"]["enabled"]["default"], False)
        self.assertNotIn("gpuActivation", schema["$defs"]["mapData"]["properties"])
        existing = json.loads((self.engine_root / "web/map_infographic_v1/planner_scene_v1.schema.json").read_bytes())
        self.assertFalse(existing["additionalProperties"])
        self.assertNotIn("mapData", existing["properties"])


if __name__ == "__main__":
    unittest.main()
