"""Derive native NE1 PNG windows from the exact verified original TIFF."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

from PIL import Image

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_recovery_terrain_style',HERE/'terrain_style.py')
style=importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name]=style;spec.loader.exec_module(style)

def write_new(file,value):
    raw=json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False).encode()+b'\n'
    if file.exists():
        if file.read_bytes()!=raw:raise ValueError('TERRAIN_REFUSE_OVERWRITE_DIFFERENT_METADATA')
    else:file.write_bytes(raw)

def build(source_file,old_source_root):
    config=json.loads((HERE/'fixtures/MAP_STYLE.json').read_bytes())
    if config['styleId']!=style.STYLE_ID:raise ValueError('TERRAIN_STYLE_CONFIG_MISMATCH')
    if source_file.is_symlink() or source_file.stat().st_size!=style.SOURCE_BYTES or style.file_sha(source_file)!=style.SOURCE_SHA256:
        raise ValueError('TERRAIN_ORIGINAL_BYTES_NOT_VERIFIED')
    provenance=HERE/'source-provenance';provenance.mkdir(exist_ok=True)
    old=Path('/workspace/yeonhwarok-free')
    inputs=[('world-simulation-shorts-engine/library/flat/terrain/ORIGINAL_SOURCE_RECORD.json','ORIGINAL_SOURCE_RECORD.json'),
        ('world-simulation-shorts-engine/library/flat/terrain/NE1_HR_LC_SR_W_DR.tfw','NE1.tfw'),
        ('world-simulation-shorts-engine/library/flat/terrain/NE1_HR_LC_SR_W_DR.prj','NE1.prj'),
        ('world-simulation-shorts-engine/library/flat/terrain/NE1_HR_LC_SR_W_DR.README.html','NE1.README.html'),
        ('cinematic-world-map/assets/gis/natural-earth-license.html','NATURAL_EARTH_PUBLIC_DOMAIN.txt')]
    provenance_rows=[]
    for relative,name in inputs:
        origin=old/relative;target=provenance/name;raw=origin.read_bytes()
        if target.exists() and target.read_bytes()!=raw:raise ValueError('TERRAIN_PROVENANCE_BYTES_DIFFER')
        if not target.exists():target.write_bytes(raw)
        provenance_rows.append({'path':target.relative_to(HERE).as_posix(),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'originalPath':relative})
    registration=style.world_file_contract((provenance/'NE1.tfw').read_text(),(provenance/'NE1.prj').read_text())
    record=json.loads((provenance/'ORIGINAL_SOURCE_RECORD.json').read_bytes())
    for name,key in [('NE1.tfw','world_file_sha256'),('NE1.prj','projection_file_sha256'),('NE1.README.html','source_readme_sha256')]:
        if style.file_sha(provenance/name)!=record[key]:raise ValueError('TERRAIN_PROVENANCE_PIN_MISMATCH')
    native=json.loads((old_source_root/'demo/NATIVE.json').read_bytes())
    cases=[{'id':'RECOVERY_DEMO','schedule':native['cameraSchedule'],'receipt':'RECOVERY_STYLE_RECEIPT.json'},
        *[{**case,'schedule':[{'frame':index,'flatBounds':b} for index,b in enumerate(case['cameraBounds'])]}
            for case in config['additionalCases']]]
    original_limit=Image.MAX_IMAGE_PIXELS;Image.MAX_IMAGE_PIXELS=style.SOURCE_DIMENSIONS[0]*style.SOURCE_DIMENSIONS[1]+1
    assets=HERE/'assets/terrain';assets.mkdir(parents=True,exist_ok=True)
    receipts=[]
    try:
        with Image.open(source_file) as source:
            if source.format!='TIFF' or source.mode!='RGB' or source.size!=style.SOURCE_DIMENSIONS:
                raise ValueError('TERRAIN_ORIGINAL_TIFF_FORMAT_MISMATCH')
            # Pillow performs a lossless native window copy. No resize or transform.
            for case in cases:
                window=style.native_window(case['schedule'],gutter_pixels=config['gutterSourcePixels'],max_texture_dimension=config['maxTextureDimension'])
                name=case['id'].lower()+'_ne1_native.png';target=assets/name
                if target.exists():raise ValueError('TERRAIN_DERIVED_FILE_ALREADY_EXISTS')
                crop=source.crop(window.pixel_box);raw_hash=hashlib.sha256(crop.tobytes()).hexdigest();crop.save(target,format='PNG',compress_level=6)
                with Image.open(target) as check:
                    if hashlib.sha256(check.tobytes()).hexdigest()!=raw_hash:raise ValueError('TERRAIN_LOSSLESS_PNG_READBACK_FAILED')
                asset={'path':target.relative_to(style.REPO).as_posix(),'url':'/recovery-assets/'+name,'sha256':style.file_sha(target),'bytes':target.stat().st_size,
                    'bounds':list(window.geographic_bounds),'dimensions':list(window.dimensions),'pixelSpacing':[style.NATIVE_SPACING]*2,'CRS':'EPSG:4326',
                    'classification':'BAKED HILLSHADE','sourceOriginalSHA256':style.SOURCE_SHA256,'NoData':None,'license':'Public Domain'}
                receipt={'schema':style.RECEIPT_SCHEMA,'styleId':style.STYLE_ID,'caseId':case['id'],'terrainAsset':asset,
                    'cameraEnvelope':list(window.camera_envelope),'frameCount':len(case['schedule']),'cropSourcePixelBox':list(window.pixel_box),
                    'sourceOriginal':{'id':'NE1_HR_LC_SR_W_DR','url':record['url'],'version':record['source_pinned_commit'],'sha256':style.SOURCE_SHA256,'bytes':style.SOURCE_BYTES,
                        'dimensions':list(style.SOURCE_DIMENSIONS),'bounds':list(style.SOURCE_BOUNDS),'pixelSpacing':[style.NATIVE_SPACING]*2,'CRS':'EPSG:4326','license':'Public Domain'},
                    'nativeWindowPolicy':{'gutterSourcePixels':config['gutterSourcePixels'],'maxTextureDimension':config['maxTextureDimension'],'operation':'LOSSLESS_NATIVE_WINDOW_COPY_NO_RESAMPLE'},
                    'sourceRegistration':registration,'provenanceFiles':provenance_rows,'decodedNativeCropRGBSHA256':raw_hash,
                    'dataQualification':'Cartographic shaded RGB; not DEM, current satellite imagery, or historical control data.',
                    'outsideSupportPolicy':'FAIL_PREFLIGHT_BEFORE_RENDER_NO_GLOBAL_STYLE_FALLBACK',
                    'unsupportedPolicy':'Nonwrapping EPSG4326 flat view only. Dateline wrap and source-edge viewports without required native gutter fail explicitly.'}
                result=style.validate_style(receipt,case['schedule'])
                receipt_name=case.get('receipt',case['id']+'_STYLE_RECEIPT.json');write_new(HERE/'fixtures'/receipt_name,receipt)
                receipts.append({'caseId':case['id'],'receipt':'fixtures/'+receipt_name,'asset':asset,'validation':result,'cameraSchedule':case['schedule'] if case['id']!='RECOVERY_DEMO' else 'UNCHANGED_SOURCE_NATIVE_SCHEDULE_180'})
            # Compare the original regional raster's decoded pixels to its true source window.
            existing=style.REPO/'world-simulation-shorts-engine/web/flat_assets/natural_earth_1_east_asia.png'
            with Image.open(existing) as regional:
                exact=source.crop(tuple(record['crop_source_pixel_box']));overlap_equal=exact.size==regional.size and exact.tobytes()==regional.tobytes()
            if not overlap_equal:raise ValueError('TERRAIN_EXISTING_REGIONAL_SOURCE_PIXELS_DIFFER')
    finally:Image.MAX_IMAGE_PIXELS=original_limit
    report={'schema':'WORLD_ENGINE_G2_NATIVE_TERRAIN_PREPARATION_V1','status':'PASS','sourceSHA256':style.SOURCE_SHA256,'sourceBytes':style.SOURCE_BYTES,
        'originalRegionalDecodedRGBEqualsPinnedSourceWindow':overlap_equal,'registration':registration,'provenanceFiles':provenance_rows,
        'cases':receipts,'resamplingPerformed':False,'smoothingPerformed':False,'rendererOrShaderChanged':False,'nvidiaVerified':False,'qualityApproved':False}
    write_new(HERE/'reports/TERRAIN_PREPARATION.json',report)
    print(json.dumps({'status':'PASS','cases':len(receipts),'sourceSHA256':style.SOURCE_SHA256,'regionalSourcePixelsExact':overlap_equal}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--old-source-root',type=Path,required=True)
    args=p.parse_args();build(args.source,args.old_source_root)
