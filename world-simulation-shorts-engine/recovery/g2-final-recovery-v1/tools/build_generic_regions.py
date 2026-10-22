"""Prepare five source-qualified regional inputs; no browser or rendering occurs.

Original Namibia/Nepal runtime JSON is copied byte-for-byte into a fresh output.
Other examples call the unchanged preparer, V5 evaluator, registry and GEOS
compiler. All five inputs remain generic synthetic observation zones, not history.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

from PIL import Image

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
PREVIOUS = HERE.parent / 'g2-renderer-recovery-v1'


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


old = load('_final_generic_source_builder', PREVIOUS / 'tools/build_generic_probes.py')
style = load('_final_generic_native_style', PREVIOUS / 'terrain_style.py')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def write_new(file, raw):
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.exists():
        if file.read_bytes() != raw:
            raise ValueError('FINAL_GENERIC_REFUSE_OVERWRITE')
    else:
        file.write_bytes(raw)
    return {'path': str(file), 'sha256': sha(raw), 'bytes': len(raw)}


def compile_style_runtime(native, receipt):
    """Only the new truthful asset descriptor changes; reuse the Scale compiler."""
    bridge = r'''
import {compileScalePlan} from './world-simulation-shorts-engine/web/map_infographic_v1/scale_contract.mjs';
import {readFileSync} from 'node:fs';
const {native,receipt}=JSON.parse(readFileSync(0,'utf8')),copy=structuredClone(native),a=receipt.terrainAsset,s=receipt.sourceOriginal;
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const original=JSON.stringify(native),base=structuredClone(native.nativePlan);
base.assets.terrain={file:a.path,url:a.url,bounds:structuredClone(a.bounds),dimensions:structuredClone(a.dimensions),pixelSpacing:structuredClone(a.pixelSpacing),sha256:a.sha256,classification:a.classification,license:'Public Domain',
 source:{name:'Natural Earth I with shaded relief, water and drainages',sha256:s.sha256,url:s.url,license:s.license,crs:s.CRS,version:s.version,resolution:structuredClone(s.dimensions),geographicExtent:structuredClone(s.bounds),pixelSpacing:structuredClone(s.pixelSpacing)},
 lodPreparation:{method:'EXACT_NATIVE_PIXEL_WINDOW_NO_RESAMPLE_OR_RECOLOR',cropSourcePixelBox:structuredClone(receipt.cropSourcePixelBox),gutterSourcePixels:receipt.nativeWindowPolicy.gutterSourcePixels}};
copy.nativePlan=compileScalePlan(base,'REGIONAL',{allCountries:base.geometries});
for(const k of ['anchor','framing','geometries','layout','primary','secondary','text','theme'])if(!same(copy.nativePlan[k],native.nativePlan[k]))throw Error('FINAL_GENERIC_NATIVE_DESIGN_CHANGED');
copy.sourceBindings=native.sourceBindings.map(row=>row.role==='terrain'?{role:'terrain',path:a.path,sha256:a.sha256,bytes:a.bytes}:structuredClone(row));
if(copy.sourceBindings.filter(r=>r.role==='terrain').length!==1)throw Error('FINAL_GENERIC_ONE_TERRAIN_SOURCE_REQUIRED');
if(copy.nativePlan.scale.lod.rasterCoverage!=='FULL_REGIONAL_CROP')throw Error('FINAL_GENERIC_NATIVE_COVERAGE_REQUIRED');
copy.sourceStyle=receipt;copy.evidence={...copy.evidence,recoveryStyleId:receipt.styleId,originalSourceSHA256:s.sha256,actualAssetSHA256:a.sha256,cameraUnchanged:true,geometryUnchanged:true};
if(JSON.stringify(native)!==original||!same(copy.cameraPlan,native.cameraPlan)||!same(copy.cameraSchedule,native.cameraSchedule))throw Error('FINAL_GENERIC_SOURCE_INPUT_MUTATED');
process.stdout.write(JSON.stringify(copy));
'''
    result = subprocess.run(['node', '--input-type=module', '-e', bridge], cwd=REPO,
        input=canonical({'native': native, 'receipt': receipt}), capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError('FINAL_GENERIC_STYLE_COMPILE_FAILED:' + result.stderr.decode(errors='replace')[-1500:])
    return json.loads(result.stdout)


def source_receipt(case_id, source, schedule):
    window = style.native_window(schedule, gutter_pixels=8, max_texture_dimension=4096)
    file = HERE / 'assets/terrain' / (case_id + '_ne1_native.png')
    file.parent.mkdir(parents=True, exist_ok=True)
    crop = source.crop(window.pixel_box)
    decoded_sha = sha(crop.tobytes())
    if not file.exists():
        crop.save(file, format='PNG', compress_level=6)
    with Image.open(file) as check:
        if check.mode != 'RGB' or check.size != window.dimensions or sha(check.tobytes()) != decoded_sha:
            raise ValueError('FINAL_GENERIC_LOSSLESS_NATIVE_CROP_MISMATCH')
    base = json.loads((PREVIOUS / 'fixtures/RECOVERY_STYLE_RECEIPT.json').read_bytes())
    asset = {'path': file.relative_to(REPO).as_posix(), 'url': '/recovery-assets/' + file.name,
        'sha256': style.file_sha(file), 'bytes': file.stat().st_size, 'bounds': list(window.geographic_bounds),
        'dimensions': list(window.dimensions), 'pixelSpacing': [style.NATIVE_SPACING] * 2, 'CRS': 'EPSG:4326',
        'classification': 'BAKED HILLSHADE', 'sourceOriginalSHA256': style.SOURCE_SHA256,
        'NoData': None, 'license': 'Public Domain'}
    base.update(caseId=case_id.upper(), terrainAsset=asset, cameraEnvelope=list(window.camera_envelope),
                frameCount=len(schedule), cropSourcePixelBox=list(window.pixel_box), decodedNativeCropRGBSHA256=decoded_sha)
    # A separate module instance scopes the same unchanged source checker to the
    # new asset directory; no old module or existing receipt is modified.
    style.ASSET_PREFIX = HERE.relative_to(REPO).as_posix() + '/assets/terrain/'
    validated = style.validate_style(base, schedule)
    return base, validated


def verify_partition(runtime, domain):
    reports = []
    with old.control._Geos() as geos:
        base = geos.geometry(domain)
        for field in runtime['frames']:
            owners = [geos.geometry(row['geometry']) for row in field['ownerMasks']]
            union = owners[0]
            for value in owners[1:]:
                union = geos.operation('union', union, value)
            outside = sum(geos.area(geos.operation('difference', value, base)) for value in owners)
            missing = geos.area(geos.operation('difference', base, union))
            overlap = sum(geos.area(geos.operation('intersection', a, b)) for i, a in enumerate(owners) for b in owners[i+1:])
            reports.append({'frame': field['frame'], 'outsideAreaDegreesSquared': outside,
                            'unassignedAreaDegreesSquared': missing, 'overlapAreaDegreesSquared': overlap,
                            'compiledUnassignedAreaDegreesSquared': field['unassignedAreaDegreesSquared'],
                            'completeExplicitDomainPartition': field['completeExplicitDomainPartition']})
            if not field['completeExplicitDomainPartition'] or any(v != 0 for v in (outside, missing, overlap, field['unassignedAreaDegreesSquared'])):
                raise ValueError('FINAL_GENERIC_PARTITION_FAILED')
    return reports


def persist_package(output):
    target = HERE / 'fixtures/GENERIC_REGION_INPUTS.zip'
    if target.exists():
        raise ValueError('FINAL_GENERIC_PERSISTENCE_REFUSE_OVERWRITE')
    rows = []
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for file in sorted(output.rglob('*')):
            if not file.is_file():
                continue
            name = file.relative_to(output).as_posix()
            raw = file.read_bytes()
            rows.append({'path': name, 'sha256': sha(raw), 'bytes': len(raw)})
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100600 << 16
            z.writestr(info, raw)
        z.writestr('PERSISTENCE_MANIFEST.json', canonical({'files': rows}))
    with zipfile.ZipFile(target) as z:
        if z.testzip() is not None or not all(sha(z.read(r['path'])) == r['sha256'] for r in rows):
            raise ValueError('FINAL_GENERIC_PERSISTENCE_READBACK_FAILED')
    return {'path': target.relative_to(HERE).as_posix(), 'sha256': style.file_sha(target),
            'bytes': target.stat().st_size, 'files': rows, 'readback': 'PASS'}


def build(output, source, original_probes, seed):
    output, source, original_probes, seed = map(Path, [output, source, original_probes, seed])
    if output.exists():
        raise ValueError('FINAL_GENERIC_OUTPUT_MUST_BE_NEW')
    if source.is_symlink() or source.stat().st_size != style.SOURCE_BYTES or style.file_sha(source) != style.SOURCE_SHA256:
        raise ValueError('FINAL_GENERIC_PINNED_NATIVE_TIFF_REQUIRED')
    configs = json.loads((HERE / 'fixtures/GENERIC_REGIONS.json').read_bytes())
    if configs['cameraSourceFrames'] != [0, 54, 0] or len(configs['cases']) != 5:
        raise ValueError('FINAL_GENERIC_FIVE_REGISTERED_CASES_REQUIRED')
    output.mkdir(parents=True)
    defaults = json.loads((PREVIOUS.parent / 'universal-source-pipeline-v2/fixtures/NATIVE_DEMO_CONFIG.json').read_bytes())
    report = {'schema': 'WORLD_ENGINE_G2_FINAL_GENERIC_INPUTS_V1', 'status': 'PREPARED_NOT_RENDERED',
              'sourceSHA256': style.SOURCE_SHA256, 'sourceBytes': style.SOURCE_BYTES,
              'sourceRedownloaded': False, 'rendererExecuted': False, 'historicalClaims': False,
              'cameraSourceFrames': configs['cameraSourceFrames'], 'cases': []}
    limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = style.SOURCE_DIMENSIONS[0] * style.SOURCE_DIMENSIONS[1] + 1
    try:
        with Image.open(source) as raster:
            if raster.mode != 'RGB' or raster.size != style.SOURCE_DIMENSIONS:
                raise ValueError('FINAL_GENERIC_SOURCE_RASTER_FORMAT')
            for case in configs['cases']:
                root = output / case['id']
                if 'reuse' in case:
                    origin = original_probes / case['reuse']
                    if not origin.is_dir() or origin.is_symlink():
                        raise ValueError('FINAL_GENERIC_ORIGINAL_PROBE_MISSING')
                    shutil.copytree(origin, root)
                    raw = (origin / 'RECOVERY_RUNTIME.json').read_bytes()
                    if (root / 'RECOVERY_RUNTIME.json').read_bytes() != raw:
                        raise ValueError('FINAL_GENERIC_ORIGINAL_RUNTIME_CHANGED')
                    runtime = json.loads(raw)
                    receipt = runtime['sourceStyle']
                    validated = {'ready': True, 'reusedOriginalReceipt': True,
                                 'terrainSHA256': receipt['terrainAsset']['sha256']}
                    original = {'path': str(origin / 'RECOVERY_RUNTIME.json'), 'sha256': sha(raw),
                                'copiedRuntimeBytesExact': True}
                else:
                    config = {k: deepcopy(case[k]) for k in ['primary_id', 'event_location', 'final_bounds', 'start_bounds']}
                    config.update(total_frames=180, fps=30, camera_profile=defaults['camera_profile'])
                    native = old.prepare_native(seed, config, configs['cameraSourceFrames'])
                    old.build_case(case, native, root)
                    payload = json.loads((root / 'RUNTIME.json').read_bytes())
                    receipt, validated = source_receipt(case['id'], raster, payload['cameraSchedule'])
                    runtime = compile_style_runtime(payload, receipt)
                    raw = canonical(runtime)
                    write_new(root / 'RECOVERY_RUNTIME.json', raw)
                    original = None
                receipt_file = HERE / 'fixtures' / (case['id'].upper() + '_STYLE_RECEIPT.json')
                receipt_raw = json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False).encode() + b'\n'
                write_new(receipt_file, receipt_raw)
                report['cases'].append({'id': case['id'], 'region': case['region'], 'terrainCondition': case['terrain_condition'],
                    'runtime': {'path': str(root / 'RECOVERY_RUNTIME.json'), 'sha256': sha(raw), 'bytes': len(raw)},
                    'originalRuntime': original, 'receipt': {'path': receipt_file.relative_to(HERE).as_posix(), 'sha256': sha(receipt_raw)},
                    'terrainValidation': validated, 'partition': verify_partition(runtime, json.loads((root / 'DOMAIN.geojson').read_bytes())),
                    'cameraUnchanged': True, 'geometryUnchanged': True, 'layoutAdapted': False,
                    'actualDraw': 'NOT_EXECUTED', 'labelVisibleInExistingRuntime': False})
    finally:
        Image.MAX_IMAGE_PIXELS = limit
    write_new(output / 'GENERIC_REGIONS_PREPARED.json', canonical(report))
    report['persistence'] = persist_package(output)
    write_new(HERE / 'reports/GENERIC_REGIONS_PREPARATION.json', json.dumps(report, indent=2, ensure_ascii=False).encode() + b'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--source', type=Path, default=Path('/tmp/g2-source-cache-20261022/NE1_HR_LC_SR_W_DR.tif'))
    parser.add_argument('--original-probes', type=Path, default=Path('/workspace/g2-recovery-generic-probes-20261022'))
    parser.add_argument('--seed', type=Path, default=Path('/workspace/exact-65422-capsule-20261020/world-simulation-shorts-engine/recovery/reference-reproduction-v1/fixtures/REGIONAL-plan.json'))
    args = parser.parse_args()
    result = build(args.output, args.source, args.original_probes, args.seed)
    print(json.dumps({'status': result['status'], 'cases': len(result['cases']), 'archive': result['persistence']['path'], 'rendererExecuted': False}))
