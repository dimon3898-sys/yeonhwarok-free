"""Focused additive native-slot gate checks; no NVIDIA or production rendering."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_test_reconcile_native', HERE / 'native_capabilities.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def empty():
    return {'schema': 'WORLD_ENGINE_OVERNIGHT_VISUAL_V1',
        'scalarTerritory': None, 'nationalUnits': None}


def admission(*, scalar=False, national=False):
    # Receipt-shaped fixture only. It cannot bypass the retained real owner.
    return {'status': 'CPU_ADMITTED', 'scalarControlSelected': scalar,
        'nationalUnitsSelected': national}


class NativeCapabilitiesTests(unittest.TestCase):
    def test_current_capabilities_are_bound_to_exact_preserved_27_plus_55(self):
        result = native.inspect_native_capabilities()
        self.assertEqual(result['frozenSource']['overnightFilesVerified'], 27)
        self.assertEqual(result['frozenSource']['parentFilesVerified'], 55)
        self.assertEqual(result['frozenSource']['sourceCommit'], native.FROZEN_SOURCE_COMMIT)
        self.assertEqual(set(result['frozenSource']['components']),
            {'nativePublisher', 'privateFrameContext', 'optionalCompositor', 'optionalConsumer'})
        self.assertFalse(result['capabilities']['internalBoundarySegments'])
        self.assertFalse(result['capabilities']['sameFramePreTerritoryTerrainTexture'])
        self.assertFalse(result['capabilities']['sameFrameNativeRoleCoverage'])
        self.assertFalse(result['gpuVerified'])
        self.assertFalse(result['renderAllowed'])

    def test_null_selection_remains_eligible_for_all_original_gates(self):
        original = empty()
        result = native.guard_native_selection(original, source_admission=admission())
        self.assertEqual(result['status'], 'NATIVE_GUARD_PASSED')
        self.assertEqual(result['selected'], {'scalarTerritory': False, 'nationalUnits': False})
        self.assertFalse(result['sourceAdmissionRequired'])
        self.assertFalse(result['renderAllowed'])
        self.assertEqual(original, empty())
        self.assertEqual(native.guard_submission({'overnightV3': {'visualExtensions': original}})['status'],
            'NATIVE_GUARD_PASSED')

    def test_selected_scalar_fails_before_any_gpu_or_renderer_manager(self):
        request = empty()
        request['scalarTerritory'] = {'sourceId': 'SOURCE_BOUND_BY_OLD_OWNER'}
        before = deepcopy(request)
        with self.assertRaises(native.NativeCapabilityError) as caught:
            native.guard_native_selection(request, source_admission=admission(scalar=True))
        self.assertEqual(caught.exception.code, 'RECONCILE_NATIVE_SCALAR_COMPOSITION_UNAVAILABLE')
        self.assertIn('INTERNAL_BOUNDARY_SEGMENTS', caught.exception.details['missingNativeSlots'])
        self.assertIn('SCALAR_PARENT_COMPOSITION_SLOT', caught.exception.details['missingNativeSlots'])
        self.assertFalse(caught.exception.details['renderAllowed'])
        self.assertFalse(caught.exception.details['historicalDataFabricated'])
        self.assertEqual(request, before)

    def test_national_selection_does_not_invent_unavailability_or_source_approval(self):
        request = empty()
        request['nationalUnits'] = {'sourceId': 'ONLY_RETAINED_OWNER_CAN_VALIDATE'}
        pending = native.guard_native_selection(request)
        self.assertEqual(pending['status'], 'NATIVE_GUARD_PASSED')
        self.assertTrue(pending['sourceAdmissionRequired'])
        self.assertFalse(pending['historicalUnitPositionsVerified'])
        result = native.guard_native_selection(request, source_admission=admission(national=True))
        self.assertFalse(result['sourceAdmissionRequired'])
        self.assertTrue(result['existingSourceAdmissionRetained'])
        self.assertFalse(result['renderAllowed'])

    def test_source_admission_mismatch_is_not_silently_accepted(self):
        for result in [admission(scalar=True), admission(national=True), {'status': 'GPU_PASS'}, {}]:
            with self.assertRaisesRegex(native.NativeCapabilityError, 'SOURCE_ADMISSION_MISMATCH'):
                native.guard_native_selection(empty(), source_admission=result)

    def test_public_fields_or_capability_map_cannot_grant_native_slots(self):
        for request in [None, {}, {**empty(), 'nativeCapabilities': {'scalarParentCompositionSlot': True}},
                {**empty(), 'scalarTerritory': True}, {**empty(), 'nationalUnits': []}]:
            with self.assertRaisesRegex(native.NativeCapabilityError, 'EXACT_VISUAL_REQUEST_REQUIRED'):
                native.guard_native_selection(request)
        with self.assertRaises(TypeError):
            native.guard_native_selection(empty(), capabilities={'scalarParentCompositionSlot': True})
        with self.assertRaisesRegex(native.NativeCapabilityError, 'OVERNIGHT_SUBMISSION_REQUIRED'):
            native.guard_submission({'nativeCapabilities': {'scalarParentCompositionSlot': True}})

    def test_changed_manifest_fails_closed_without_editing_frozen_files(self):
        real_read = native._read_bytes
        def changed(path):
            original = real_read(path)
            return original + b'\n' if Path(path).name == 'OVERNIGHT_FILES.json' else original
        with patch.object(native, '_read_bytes', side_effect=changed):
            with self.assertRaisesRegex(native.NativeCapabilityError, 'SOURCE_MANIFEST_CHANGED'):
                native.inspect_native_capabilities()

    def test_changed_component_fails_closed_without_editing_frozen_files(self):
        real_read = native._read_bytes
        def changed(path):
            original = real_read(path)
            return original + b'\n' if Path(path).name == 'production_camera_bridge.mjs' else original
        with patch.object(native, '_read_bytes', side_effect=changed):
            with self.assertRaisesRegex(native.NativeCapabilityError, 'COMPONENT_CHANGED'):
                native.inspect_native_capabilities()

    def test_actual_original_cpu_compile_then_missing_native_context_failure(self):
        # Only the original test-only generic fixture is constructed. No
        # historical source label, production source catalog, GPU or mock
        # shader is used. This reproduces the structural late-failure path.
        source = r'''
import {compileVisualExtensions,evaluateVisualExtensionsFrame,visualSourceSHA} from '__VISUAL__';
import {compileTerritoryControlPlan} from '__CONTROL__';
const rect=(id,west,east)=>({id,geometry:{type:'Polygon',coordinates:[[[west,-2],[east,-2],[east,2],[west,2],[west,-2]]]}});
const plan=compileTerritoryControlPlan({semantic_mode:'REFERENCE_VISUAL_STUDY',source:{source_type:'SYNTHETIC_TEST_ONLY',source_reference:'CPU_REPRO_NATIVE_CAPABILITY_GAP',verification_status:'SYNTHETIC_TEST'},domain:[rect('GENERIC_A',-4,-2),rect('GENERIC_B',-2,0)],factions:{winner:{id:'GENERIC_WINNER'},loser:{id:'GENERIC_LOSER'}},longitudinal_knots:[-4,-2,0],base_boundary_latitudes:[-1,-1,-1],boundary_keyframes:[{frame:0,latitudes:[-1,-1,-1]},{frame:24,latitudes:[.8,1,.8]},{frame:59,latitudes:[.8,1,.8]}],advance_direction:'POSITIVE_LATITUDE',start_frame:0,total_frames:60,fps:30,interpolation:'SMOOTHERSTEP'});
const payload={schema:'WORLD_ENGINE_SCALAR_CONTROL_SOURCE_V1',plan,territoryStyle:{profileName:'CPU_REPRO_STYLE',losingColor:[.4,.1,.7,.7],existingWinningColor:[.7,.1,.1,.7],gainedWinningColor:[.7,.1,.1,.72]},frontierStyle:{profileName:'CPU_REPRO_LIGHT',centerColor:[1,.985,.94],haloColor:[1,.7,.25],centerWidthPixels:2.5,haloSigmaPixels:3.5,haloSupportPixels:10,centerAlpha:1,haloAlpha:.35,settledStrength:.08,velocityWindowFrames:6,luminanceAnchor:.36,minimumLightingFactor:.83,reliefLightingEnabled:true},nativeDomain:null};
const record={sourceId:'cpu-repro-only',sha256:await visualSourceSHA(payload),role:'SCALAR_CONTROL_PLAN',verificationStatus:'SYNTHETIC_TEST',payload};
const request={schema:'WORLD_ENGINE_OVERNIGHT_VISUAL_V1',scalarTerritory:{sourceId:record.sourceId,sha256:record.sha256,gain:{enabled:true,gainBrightness:1.12,gainedAlpha:.84},frontier:null},nationalUnits:null};
const binding=await compileVisualExtensions({request,trustedSources:[record],fps:30,totalFrames:60,allowSynthetic:true});
const context={project:p=>p,safeArea:[0,0,1080,1920],protectedGraphics:[],parentGeographicFrontPresent:false,parentTerritoryFillPresent:false,nativeBoundarySourceVerified:true,boundarySegments:[]};
let firstDrawFailure;try{evaluateVisualExtensionsFrame(binding,10,context);}catch(e){firstDrawFailure=e.code??e.message;}
const repairedContext={...context,internalBoundarySegments:[]};
const originalEvaluation=evaluateVisualExtensionsFrame(binding,10,repairedContext);
console.log(JSON.stringify({testOnly:true,sourceSynthetic:true,productionAdmissionAttempted:false,cpuBindingCompiled:!!binding.scalar,firstDrawFailure,completeContextEvaluation:!!originalEvaluation.scalar,gpuPixelsRendered:false}));
'''
        engine = HERE.parents[1]
        source = source.replace('__VISUAL__', (native.OVERNIGHT / 'visual_extensions.mjs').as_uri())
        source = source.replace('__CONTROL__', (engine / 'web/map_infographic_v1/territory_control_adapter_v1.mjs').as_uri())
        result = subprocess.run(['node', '--input-type=module'], input=source, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        facts = json.loads(result.stdout)
        self.assertTrue(facts['cpuBindingCompiled'])
        self.assertEqual(facts['firstDrawFailure'], 'OVERNIGHT_SCALAR_PARENT_COMPOSITION_SLOT_REQUIRED')
        self.assertTrue(facts['completeContextEvaluation'])
        self.assertFalse(facts['productionAdmissionAttempted'])
        self.assertFalse(facts['gpuPixelsRendered'])


if __name__ == '__main__':
    unittest.main()
