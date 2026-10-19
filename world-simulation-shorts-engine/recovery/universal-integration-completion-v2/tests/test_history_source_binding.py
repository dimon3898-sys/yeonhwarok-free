"""Actual four-file binding and isolated synthetic path/integrity regressions."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("completion_history_source_binding", ROOT / "history_source_binding.py")
binding = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(binding)


def raw(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


class HistorySourceBindingTests(unittest.TestCase):
    def actual_objects(self):
        catalog = json.loads((ROOT / "SOURCE_DATA_CATALOG.json").read_text())
        plan = json.loads((ROOT / "fixtures/VALIDATED_80S_SUBMISSION.json").read_text())["videoPlan"]
        front = json.loads((ROOT.parent / "verified-front-data-v4-recovery/FRONT_PROFILE.json").read_text())
        return catalog, plan, front, plan["renderProfile"]["imageDigest"]

    def synthetic(self, root):
        directory = root / "verified-front-data-v4-recovery"
        directory.mkdir()
        parent = raw({"schema": "WORLD_ENGINE_UNIVERSAL_VIDEO_V2"})
        profile = raw({"schema": "WORLD_ENGINE_VERIFIED_FRONT_PROFILE_V4",
                       "runtimeProfile": "VERIFIED_ARCHIVAL_FRONT_V4", "unchangedBasePlanSha256": sha(parent)})
        manifest = raw({"schema": "WORLD_ENGINE_VERIFIED_FRONT_FILES_V4", "profileId": "VERIFIED_ARCHIVAL_FRONT_V4",
                        "files": {"FRONT_PROFILE.json": sha(profile), "PARENT_PLAN_80S.json": sha(parent)}})
        plan = raw({"schema": "WORLD_ENGINE_UNIVERSAL_VIDEO_V2", "sourceManifest": {"archivalFrontV4": {
            "profileSha256": sha(profile), "sourceManifestSha256": sha(manifest)}}})
        values = {"VIDEO_PLAN_80S.json": plan, "FRONT_PROFILE.json": profile,
                  "FRONT_FILES.json": manifest, "PARENT_PLAN_80S.json": parent}
        catalog = {"schema": "WORLD_ENGINE_COMPLETION_SOURCE_CATALOG_V1", "sourceFileBindings": {}}
        for name, content in values.items():
            (directory / name).write_bytes(content)
            catalog["sourceFileBindings"][name] = {**binding.SOURCE_FILE_SPECS[name], "sha256": sha(content)}
        return catalog, values

    def test_actual_four_preserved_source_hashes_and_history_api(self):
        catalog = json.loads((ROOT / "SOURCE_DATA_CATALOG.json").read_text())
        actual = binding.verify_declared_source_files(catalog, ROOT.parent)
        self.assertEqual(set(actual), set(binding.SOURCE_FILE_SPECS))
        for name, digest in actual.items():
            self.assertEqual(digest, sha((ROOT.parent / binding.SOURCE_FILE_SPECS[name]["path"]).read_bytes()))
        history_spec = importlib.util.spec_from_file_location("binding_history_admission", ROOT / "history_admission.py")
        history = importlib.util.module_from_spec(history_spec)
        history_spec.loader.exec_module(history)
        plan = json.loads((ROOT.parent / catalog["sourceFileBindings"]["VIDEO_PLAN_80S.json"]["path"]).read_text())
        front = json.loads((ROOT.parent / catalog["sourceFileBindings"]["FRONT_PROFILE.json"]["path"]).read_text())
        result = history.assess_history(plan, front, source_bindings=actual)
        self.assertTrue(result["dataAdmitted"])
        self.assertTrue(result["sourceChecks"]["preservedReceiptCrossBindingsMatch"])
        self.assertFalse(result["renderAllowed"])

    def test_valid_synthetic_authority_has_no_geographic_payload(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, values = self.synthetic(root)
            self.assertEqual(binding.verify_declared_source_files(catalog, root), {key: sha(value) for key, value in values.items()})

    def test_tampered_content_fails_actual_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, _ = self.synthetic(root)
            file = root / binding.SOURCE_FILE_SPECS["PARENT_PLAN_80S.json"]["path"]
            file.write_bytes(file.read_bytes() + b" ")
            with self.assertRaisesRegex(binding.HistorySourceBindingError, "HISTORY_SOURCE_ACTUAL_SHA_MISMATCH"):
                binding.verify_declared_source_files(catalog, root)

    def test_whitelist_roles_schema_and_exact_four_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            catalog, _ = self.synthetic(root)
            for field, value in (("path", "../outside.json"), ("role", "SECRET"), ("schema", "WRONG")):
                changed = deepcopy(catalog)
                changed["sourceFileBindings"]["VIDEO_PLAN_80S.json"][field] = value
                with self.subTest(field=field), self.assertRaisesRegex(binding.HistorySourceBindingError, "HISTORY_SOURCE_WHITELIST_ROLE_OR_SCHEMA_INVALID"):
                    binding.verify_declared_source_files(changed, root)
            del catalog["sourceFileBindings"]["PARENT_PLAN_80S.json"]
            with self.assertRaisesRegex(binding.HistorySourceBindingError, "HISTORY_SOURCE_EXACT_FOUR_BINDINGS_REQUIRED"):
                binding.verify_declared_source_files(catalog, root)

    def test_file_and_directory_symlinks_are_rejected(self):
        for location in ("file", "directory", "root"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as temp:
                base = Path(temp)
                root = base / "recovery"
                root.mkdir()
                catalog, _ = self.synthetic(root)
                directory = root / "verified-front-data-v4-recovery"
                if location == "file":
                    file = directory / "VIDEO_PLAN_80S.json"
                    renamed = directory / "original.json"
                    file.rename(renamed)
                    file.symlink_to(renamed)
                elif location == "directory":
                    renamed = root / "renamed"
                    directory.rename(renamed)
                    directory.symlink_to(renamed, target_is_directory=True)
                else:
                    alternate = base / "recovery-link"
                    alternate.symlink_to(root, target_is_directory=True)
                    root = alternate
                with self.assertRaisesRegex(binding.HistorySourceBindingError, "HISTORY_SOURCE_PATH_UNSAFE_OR_UNAVAILABLE"):
                    binding.verify_declared_source_files(catalog, root)

    def test_bounded_regular_file_required(self):
        for kind in ("empty", "oversize", "fifo"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                catalog, _ = self.synthetic(root)
                file = root / binding.SOURCE_FILE_SPECS["VIDEO_PLAN_80S.json"]["path"]
                file.unlink()
                if kind == "fifo":
                    os.mkfifo(file)
                else:
                    with file.open("wb") as output:
                        output.truncate(0 if kind == "empty" else 16 * 1024 * 1024 + 1)
                with self.assertRaisesRegex(binding.HistorySourceBindingError, "HISTORY_SOURCE_BOUNDED_REGULAR_JSON_REQUIRED"):
                    binding.verify_declared_source_files(catalog, root)

    def test_json_schema_and_cross_links_are_checked_after_hashes(self):
        for invalid in ("document_schema", "cross_link"):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                catalog, _ = self.synthetic(root)
                file = root / binding.SOURCE_FILE_SPECS["VIDEO_PLAN_80S.json"]["path"]
                value = json.loads(file.read_text())
                if invalid == "document_schema":
                    value["schema"] = "WRONG"
                    error = "HISTORY_SOURCE_DOCUMENT_SCHEMA_INVALID"
                else:
                    value["sourceManifest"]["archivalFrontV4"]["profileSha256"] = "0" * 64
                    error = "HISTORY_SOURCE_AUTHORITY_CROSS_BINDING_MISMATCH"
                content = raw(value)
                file.write_bytes(content)
                catalog["sourceFileBindings"]["VIDEO_PLAN_80S.json"]["sha256"] = sha(content)
                with self.assertRaisesRegex(binding.HistorySourceBindingError, error):
                    binding.verify_declared_source_files(catalog, root)

    def test_actual_plan_and_profile_allow_only_all_existing_image_rebindings(self):
        catalog, plan, front, image = self.actual_objects()
        before = deepcopy((catalog, plan, front))
        result = binding.verify_bound_history_objects(catalog, ROOT.parent, plan=plan, front_profile=front,
                                                       image_digest=image)
        self.assertEqual(set(result), set(binding.SOURCE_FILE_SPECS))
        self.assertEqual(before, (catalog, plan, front))
        self.assertEqual(1 + len(plan["scenes"]), 13)
        self.assertTrue(all(scene["renderProfile"]["imageDigest"] == image for scene in plan["scenes"]))

    def test_geometry_and_chapter_tamper_rejected_despite_unchanged_claimed_hashes(self):
        for field in ("geometry", "chapter"):
            with self.subTest(field=field):
                catalog, plan, front, image = self.actual_objects()
                claimed = deepcopy(plan["sourceManifest"])
                if field == "geometry":
                    plan["legacyScenePlan"]["geometries"][0]["geometry"] = {
                        "type": "LineString", "coordinates": [[-70, -40], [-69, -39]]}
                else:
                    plan["productionV3"]["eventChapters"][0]["title"] += " changed"
                self.assertEqual(plan["sourceManifest"], claimed)
                with self.assertRaisesRegex(binding.HistorySourceBindingError, "HISTORY_ASSESSED_PLAN_DIFFERS_FROM_VERIFIED_SOURCE"):
                    binding.verify_bound_history_objects(catalog, ROOT.parent, plan=plan,
                                                          front_profile=front, image_digest=image)

    def test_front_profile_tamper_rejected_despite_unchanged_claimed_hashes(self):
        catalog, plan, front, image = self.actual_objects()
        claimed = front["fronts"][0]["geoJsonSha256"]
        front["fronts"][0]["geometry"]["coordinates"][0][0] += .001
        self.assertEqual(front["fronts"][0]["geoJsonSha256"], claimed)
        with self.assertRaisesRegex(binding.HistorySourceBindingError, "HISTORY_ASSESSED_FRONT_PROFILE_DIFFERS_FROM_VERIFIED_SOURCE"):
            binding.verify_bound_history_objects(catalog, ROOT.parent, plan=plan,
                                                  front_profile=front, image_digest=image)

    def test_all_image_slots_must_match_selected_image(self):
        for field in ("scene_image", "root_image", "invalid_digest"):
            with self.subTest(field=field):
                catalog, plan, front, image = self.actual_objects()
                if field == "scene_image":
                    plan["scenes"][0]["renderProfile"]["imageDigest"] = "sha256:" + "0" * 64
                elif field == "root_image":
                    plan["renderProfile"]["imageDigest"] = "sha256:" + "0" * 64
                else:
                    image = "mutable-tag"
                with self.assertRaises(binding.HistorySourceBindingError):
                    binding.verify_bound_history_objects(catalog, ROOT.parent, plan=plan,
                                                          front_profile=front, image_digest=image)

    def test_extra_fields_and_number_type_coercions_are_not_ignored(self):
        for field in ("extra", "duration_type"):
            with self.subTest(field=field):
                catalog, plan, front, image = self.actual_objects()
                if field == "extra":
                    plan["extraClientDirective"] = {"imageDigest": image}
                else:
                    plan["durationSeconds"] = int(plan["durationSeconds"])
                with self.assertRaisesRegex(binding.HistorySourceBindingError, "HISTORY_ASSESSED_PLAN_DIFFERS_FROM_VERIFIED_SOURCE"):
                    binding.verify_bound_history_objects(catalog, ROOT.parent, plan=plan,
                                                          front_profile=front, image_digest=image)


if __name__ == "__main__":
    unittest.main()
