"""New authority only: no old audit rerun, GPU, new history or external data."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("overnight_source_extension_test", ROOT / "data_readiness.py")
OWNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OWNER)


class ExtensionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parent = OWNER.load_existing_catalog()
        cls.parent_sha = hashlib.sha256((OWNER.PARENT / "SOURCE_DATA_CATALOG.json").read_bytes()).hexdigest()

    def extension(self, rows=None):
        return {"schema": OWNER.EXTENSION_SCHEMA, "parentCatalogSHA256": self.parent_sha,
                "trustedSources": deepcopy(rows or [])}

    def merge(self, extension, **options):
        raw = json.dumps(extension, allow_nan=False).encode()
        return OWNER.merge_source_catalog(self.parent, extension, parent_sha256=self.parent_sha,
                    extension_sha256=hashlib.sha256(raw).hexdigest(), **options)

    def staged(self, extension, *, change_sha=False):
        temporary = tempfile.TemporaryDirectory(prefix="overnight-source-extension-", dir="/workspace")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        raw = json.dumps(extension, allow_nan=False).encode()
        (root / "EXTENSION_SOURCES.json").write_bytes(raw)
        (root / "OVERNIGHT_FILES.json").write_text(json.dumps({
            "schema": "WORLD_ENGINE_OVERNIGHT_FILES_V1",
            "files": {"EXTENSION_SOURCES.json": "0" * 64 if change_sha else hashlib.sha256(raw).hexdigest()}}))
        return root

    def synthetic_record(self, role="METRIC", payload=None):
        payload = payload or {"testOnly": True, "value": 80.0, "negativeZero": -0.0,
                              "fraction": 0.0000001}
        return {"sourceId": "isolated-synthetic-extension", "role": role,
                "verificationStatus": "SYNTHETIC_TEST", "payload": payload,
                "sha256": hashlib.sha256(OWNER.canonical_catalog_bytes(payload)).hexdigest()}

    def test_empty_extension_is_manifest_bound_and_keeps_all_parent_records(self):
        original = deepcopy(self.parent)
        catalog, raw, digest = OWNER.load_effective_catalog(extension_root=self.staged(self.extension()))
        self.assertEqual(catalog["trustedSources"], original["trustedSources"])
        self.assertEqual(catalog["sourceFileBindings"], original["sourceFileBindings"])
        self.assertEqual(self.parent, original)
        self.assertEqual(catalog["overnightExtension"]["sourceCount"], 0)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), digest)

    def test_extension_missing_manifest_sha_rejected(self):
        with self.assertRaisesRegex(OWNER.DataReadinessError, "MANIFEST_SHA"):
            OWNER.load_effective_catalog(extension_root=self.staged(self.extension(), change_sha=True))

    def test_changed_parent_identity_and_unknown_fields_rejected(self):
        wrong = self.extension(); wrong["parentCatalogSHA256"] = "f" * 64
        with self.assertRaisesRegex(OWNER.DataReadinessError, "AUTHORITY"):
            self.merge(wrong)
        extra = self.extension(); extra["trustedFromPrompt"] = True
        with self.assertRaisesRegex(OWNER.DataReadinessError, "AUTHORITY"):
            self.merge(extra)

    def test_duplicate_or_overridden_parent_source_id_rejected(self):
        row = deepcopy(self.parent["trustedSources"][0])
        with self.assertRaisesRegex(OWNER.DataReadinessError, "ROLE_OR_ID"):
            self.merge(self.extension([row]))
        row["sourceId"] = "new-alias-existing-real-geometry"
        with self.assertRaisesRegex(OWNER.DataReadinessError, "ROLE_OR_ID"):
            self.merge(self.extension([row, row]))

    def test_unknown_role_and_extra_source_fields_rejected(self):
        row = self.synthetic_record(); row["role"] = "NATIONAL_UNITS_PLAN"
        with self.assertRaisesRegex(OWNER.DataReadinessError, "ROLE_OR_ID"):
            self.merge(self.extension([row]), allow_synthetic=True)
        row = self.synthetic_record(); row["secretOrIgnoredOption"] = True
        with self.assertRaisesRegex(OWNER.DataReadinessError, "ROLE_OR_ID"):
            self.merge(self.extension([row]), allow_synthetic=True)

    def test_production_refuses_synthetic_and_internal_option_is_explicit(self):
        extension = self.extension([self.synthetic_record()])
        with self.assertRaisesRegex(OWNER.DataReadinessError, "SYNTHETIC_NOT_PRODUCTION"):
            OWNER.load_effective_catalog(extension_root=self.staged(extension))
        catalog, _, _ = OWNER.load_effective_catalog(extension_root=self.staged(extension), allow_synthetic=True)
        self.assertEqual(catalog["trustedSources"][-1]["verificationStatus"], "SYNTHETIC_TEST")

    def test_original_javascript_numeric_canonicalization_not_python_float_encoding(self):
        row = self.synthetic_record()
        python_hash = hashlib.sha256(json.dumps(row["payload"], sort_keys=True,
                        separators=(",", ":")).encode()).hexdigest()
        self.assertNotEqual(row["sha256"], python_hash)
        catalog, raw, _ = self.merge(self.extension([row]), allow_synthetic=True)
        self.assertEqual(catalog["trustedSources"][-1]["sha256"], row["sha256"])
        self.assertEqual(hashlib.sha256(OWNER.canonical_catalog_bytes(
            catalog["trustedSources"][-1]["payload"])).hexdigest(), row["sha256"])
        self.assertIn(b'"value":80', raw)
        self.assertNotIn(b'"value":80.0', raw)

    def test_payload_tamper_or_unsafe_json_number_rejected(self):
        row = self.synthetic_record(); row["payload"]["value"] = 81
        with self.assertRaisesRegex(OWNER.DataReadinessError, "PAYLOAD_SHA"):
            self.merge(self.extension([row]), allow_synthetic=True)
        row = self.synthetic_record(); row["payload"]["value"] = 2 ** 54
        with self.assertRaisesRegex(OWNER.DataReadinessError, "SAFE_JSON_NUMBER"):
            self.merge(self.extension([row]), allow_synthetic=True)

    def test_same_geometry_cannot_be_resolved_as_role_specific_plan(self):
        catalog, _, _ = self.merge(self.extension())
        row = catalog["trustedSources"][0]
        for role in ("SCALAR_CONTROL_PLAN", "NATIONAL_UNIT_SCENE", "FLOW_PLAN"):
            with self.assertRaisesRegex(OWNER.DataReadinessError, "ROLE_OR_REVIEW"):
                OWNER.resolve_source_reference(catalog,
                    {"sourceId": row["sourceId"], "sha256": row["sha256"]}, expected_role=role)

    def test_actual_other_hemisphere_scalar_owner_accepts_only_internal_synthetic_catalog(self):
        # Compile the original scalar owner in a generic southern/western box.
        # This creates an isolated test fixture, never historical coordinates.
        module = (ROOT.parent.parent / "web/map_infographic_v1/territory_control_adapter_v1.mjs").as_uri()
        visual = (ROOT / "visual_extensions.mjs").as_uri()
        script = """
        const {compileTerritoryControlPlan}=await import(process.argv[1]);
        const {visualSourceSHA}=await import(process.argv[2]);
        const plan=compileTerritoryControlPlan({semantic_mode:'REFERENCE_VISUAL_STUDY',
         source:{source_type:'SYNTHETIC_TEST_ONLY',source_reference:'OTHER_HEMISPHERE_ISOLATED_CPU',verification_status:'SYNTHETIC_TEST'},
         domain:[{id:'GENERIC_A',geometry:{type:'Polygon',coordinates:[[[-62,-32],[-58,-32],[-58,-28],[-62,-28],[-62,-32]]]}}],
         factions:{winner:{id:'GENERIC_ONE'},loser:{id:'GENERIC_TWO'}},longitudinal_knots:[-62,-58],
         base_boundary_latitudes:[-31,-31],boundary_keyframes:[{frame:0,latitudes:[-31,-31]},{frame:59,latitudes:[-29,-29]}],
         advance_direction:'POSITIVE_LATITUDE',start_frame:0,total_frames:60,fps:30,interpolation:'SMOOTHERSTEP'});
        const payload={schema:'WORLD_ENGINE_SCALAR_CONTROL_SOURCE_V1',plan,
         territoryStyle:{profileName:'ISOLATED_STYLE',losingColor:[.4,.1,.7,.7],existingWinningColor:[.7,.1,.1,.7],gainedWinningColor:[.7,.1,.1,.72]},
         frontierStyle:{profileName:'ISOLATED_LIGHT',centerColor:[1,.985,.94],haloColor:[1,.7,.25],centerWidthPixels:2.5,
          haloSigmaPixels:3.5,haloSupportPixels:10,centerAlpha:1,haloAlpha:.35,settledStrength:.08,
          velocityWindowFrames:6,luminanceAnchor:.36,minimumLightingFactor:.83,reliefLightingEnabled:true},nativeDomain:null};
        const record={sourceId:'isolated-southwest-scalar',role:'SCALAR_CONTROL_PLAN',verificationStatus:'SYNTHETIC_TEST',payload,sha256:await visualSourceSHA(payload)};
        process.stdout.write(JSON.stringify(record));
        """
        result = subprocess.run(["node", "--input-type=module", "-e", script, module, visual],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=20)
        record = json.loads(result.stdout)
        extension = self.extension([record])
        catalog, _, _ = OWNER.load_effective_catalog(extension_root=self.staged(extension), allow_synthetic=True)
        request = {"schema": "WORLD_ENGINE_OVERNIGHT_VISUAL_V1", "nationalUnits": None,
                   "scalarTerritory": {"sourceId": record["sourceId"], "sha256": record["sha256"],
                      "gain": {"enabled": True, "gainBrightness": 1.12, "gainedAlpha": 0.84}, "frontier": None}}
        consume = """
        const {compileVisualExtensions,evaluateVisualExtensionsFrame}=await import(process.argv[1]);
        let raw='';for await(const c of process.stdin)raw+=c;const input=JSON.parse(raw);
        const binding=await compileVisualExtensions({...input,allowSynthetic:true,fps:30,totalFrames:2400});
        process.stdout.write(JSON.stringify({scalar:!!binding.scalar,synthetic:binding.scalar.synthetic,
          firstLongitude:binding.scalar.plan.intent.domain[0].geometry.coordinates[0][0][0],gpuOutputVerified:binding.gpuOutputVerified}));
        """
        result = subprocess.run(["node", "--input-type=module", "-e", consume, visual],
            input=json.dumps({"request": request, "trustedSources": catalog["trustedSources"]}).encode(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=20)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt, {"scalar": True, "synthetic": True, "firstLongitude": -62, "gpuOutputVerified": False})
        with self.assertRaisesRegex(OWNER.DataReadinessError, "SYNTHETIC_NOT_PRODUCTION"):
            OWNER.load_effective_catalog(extension_root=self.staged(extension))

    def test_actual_capture_history_is_checked_without_mutating_original_submission(self):
        submission = json.loads((OWNER.PARENT / "fixtures/VALIDATED_80S_SUBMISSION.json").read_text())
        before = deepcopy(submission)
        merged = self.merge(self.extension())
        with patch.object(OWNER, "load_effective_catalog", return_value=merged):
            result = OWNER.admit_capture_sources(submission, merged[0])
        self.assertTrue(result["dataAdmitted"])
        self.assertTrue(result["parentHistorySourceUnchanged"])
        self.assertEqual(result["eventFlowAdmission"]["status"], "CPU_SOURCE_BOUND")
        self.assertEqual(submission, before)

    def test_original_optional_request_unknown_fields_are_not_emptied_and_ignored(self):
        submission = json.loads((OWNER.PARENT / "fixtures/VALIDATED_80S_SUBMISSION.json").read_text())
        submission["completionV2"]["eventFlow"]["unverifiedForce"] = True
        before = deepcopy(submission)
        merged = self.merge(self.extension())
        with patch.object(OWNER, "load_effective_catalog", return_value=merged):
            with self.assertRaisesRegex(ValueError, "FIELDS_UNSUPPORTED"):
                OWNER.admit_capture_sources(submission, merged[0])
        self.assertEqual(submission, before)

    def test_prompt_supplied_catalog_is_not_authority(self):
        submission = json.loads((OWNER.PARENT / "fixtures/VALIDATED_80S_SUBMISSION.json").read_text())
        merged = self.merge(self.extension())
        changed = deepcopy(merged[0]); changed["trustedSources"] = []
        with patch.object(OWNER, "load_effective_catalog", return_value=merged):
            with self.assertRaisesRegex(OWNER.DataReadinessError, "NOT_PACKAGE_AUTHORITY"):
                OWNER.admit_capture_sources(submission, changed)

    def test_actual_catalog_cli_emits_only_the_same_canonical_public_authority(self):
        catalog, raw, digest = OWNER.load_effective_catalog()
        result = subprocess.run([sys.executable, "-B", str(ROOT / "data_readiness.py"), "--catalog"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30)
        self.assertEqual(result.stdout, raw)
        self.assertEqual(hashlib.sha256(result.stdout).hexdigest(), digest)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(json.loads(result.stdout)["trustedSources"], catalog["trustedSources"])


if __name__ == "__main__":
    unittest.main()
