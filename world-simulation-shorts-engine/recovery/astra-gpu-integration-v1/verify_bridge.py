#!/usr/bin/env python3
"""Focused real-source CPU -> browser-contract cross-check; no GPU or network."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from upload_bundle import prepare_upload_bundle, MANIFEST_NAME
from astra_cpu.providers import ArchiveCatalog
from astra_cpu.scene import prepare_scene


def main():
    cpu=HERE.parent/'astra-cpu-data-v1'
    archive=HERE.parent/'astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip'
    scene_path=HERE.parent/'moving-frontier-glow-fix-v1/fixtures/SCENE_PLAN.json'
    original=json.loads(scene_path.read_text())
    original_bytes=scene_path.read_bytes()
    fixture=json.loads((cpu/'fixtures/LOCAL_DATA_SCENE.json').read_text())
    scene=deepcopy(original); scene['mapData']=deepcopy(fixture['mapData'])
    scene['mapData']['cache']={'mode':'bypass'}
    catalog=ArchiveCatalog(archive,license_verified=True)
    prep=prepare_scene(scene,catalog)
    assert prep.renderer_scene==original and prep.gpu_activation is False
    with tempfile.TemporaryDirectory(prefix='astra-cross-language-') as temp:
        output=Path(temp)/'upload'
        manifest=prepare_upload_bundle(scene,catalog,output)
        assert set(manifest['sources'])=={'terrain','bathymetry','surfaceTexture'}
        assert all(item['status']=='available' and item['parts'] for item in manifest['sources'].values())
        for artifact in manifest['artifacts']:
            body=(output/artifact['file']).read_bytes()
            assert len(body)==artifact['bytes'] and hashlib.sha256(body).hexdigest()==artifact['sha256']
        digest=hashlib.sha256((output/MANIFEST_NAME).read_bytes()).hexdigest()
        result=subprocess.run(['node',str(HERE/'crosscheck_bundle.mjs'),str(output),digest],check=False,text=True,capture_output=True,timeout=60)
        assert result.returncode==0,'CROSS_LANGUAGE_CHECK_FAILED'
        cross=json.loads(result.stdout)
        assert cross['cpuOnly'] and cross['gpuExecuted'] is False and cross['roles']==sorted(manifest['sources'])
        assert scene_path.read_bytes()==original_bytes
        return {'schema':'ASTRA_REAL_SOURCE_UPLOAD_BRIDGE_CHECK_V1','status':'PASS',
            'scope':'EXISTING_THREE_SOURCES_SMALL_SAVED_ROI_CPU_AND_JS_CONTRACT_ONLY',
            'roles':{role:{'status':source['status'],'parts':len(source['parts']),
                'dimensions':[part['dimensions'] for part in source['parts']],
                'quantity':[part['quantity'] for part in source['parts']],
                'sourceSHA256':source['SHA-256']} for role,source in manifest['sources'].items()},
            'artifactCount':len(manifest['artifacts']),'artifactBytes':manifest['artifactBytes'],
            'manifestSHA256':digest,'rendererPayloadSHA256':manifest['rendererPayloadSHA256'],
            'legacySceneByteUnchanged':True,'sceneConfigurationReused':True,'crossLanguage':cross,
            'archiveReacquired':False,'archive24MemberAuditRepeated':False,'gpuExecuted':False,
            'gpuTextureUploaded':False,'displayMaterialApplied':False,'fullCameraCoverageClaimed':False}

if __name__=='__main__':
    try: print(json.dumps(main(),indent=2))
    except Exception as error:
        print(json.dumps({'schema':'ASTRA_REAL_SOURCE_UPLOAD_BRIDGE_CHECK_V1','status':'FAIL',
            'errorType':type(error).__name__,'gpuExecuted':False}))
        raise SystemExit(1)
