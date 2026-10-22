"""Source-only NE1 coverage policy. No raster interpolation or rendering code."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path

from PIL import Image

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
STYLE_ID='NE1_SOURCE_NATIVE_COVERAGE'
RECEIPT_SCHEMA='WORLD_ENGINE_G2_MAP_STYLE_RECEIPT_V1'
SOURCE_SHA256='b47bdddd1336b07f498c50eba5d70699ec57dd726a7ea0a85d2dca243236c9eb'
SOURCE_BYTES=699969932
SOURCE_DIMENSIONS=(21600,10800)
SOURCE_BOUNDS=(-180,-90,180,90)
NATIVE_SPACING=1/60
ASSET_PREFIX='world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/assets/terrain/'

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def file_sha(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk:=stream.read(1024*1024):result.update(chunk)
    return result.hexdigest()

def fail(code):raise ValueError(code)

def bounds(value):
    if not isinstance(value,(list,tuple)) or len(value)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in value):
        fail('TERRAIN_FINITE_GEOGRAPHIC_BOUNDS_REQUIRED')
    west,south,east,north=value
    if west>=east:fail('TERRAIN_DATELINE_WRAP_OR_DEGENERATE_EXTENT_UNSUPPORTED')
    if south>=north or west< -180 or east>180 or south< -90 or north>90:
        fail('TERRAIN_OUTSIDE_GLOBAL_SOURCE_OR_POLAR_EXTENT')
    return list(value)

def envelope(schedule):
    if not isinstance(schedule,list) or not 1<=len(schedule)<=240:
        fail('TERRAIN_BOUNDED_CAMERA_SEQUENCE_REQUIRED')
    windows=[]
    for index,row in enumerate(schedule):
        if not isinstance(row,dict) or row.get('frame')!=index:fail('TERRAIN_CAMERA_FRAME_GAP')
        windows.append(bounds(row.get('flatBounds')))
    return [min(w[0] for w in windows),min(w[1] for w in windows),max(w[2] for w in windows),max(w[3] for w in windows)]

def world_file_contract(text,projection):
    try:values=[float(v) for v in text.split()]
    except (TypeError,ValueError):fail('TERRAIN_WORLD_FILE_INVALID')
    if len(values)!=6 or not all(math.isfinite(v) for v in values):fail('TERRAIN_WORLD_FILE_INVALID')
    a,d,b,e,c,f=values
    if b!=0 or d!=0:fail('TERRAIN_ROTATED_SOURCE_UNSUPPORTED')
    expected=[NATIVE_SPACING,0,0,-NATIVE_SPACING,-180+NATIVE_SPACING/2,90-NATIVE_SPACING/2]
    if any(abs(x-y)>1e-10 for x,y in zip(values,expected)):
        fail('TERRAIN_SOURCE_TRANSFORM_NOT_PINNED_NATIVE_GRID')
    if 'GCS_WGS_1984' not in projection or 'WGS_1984' not in projection:
        fail('TERRAIN_SOURCE_CRS_NOT_WGS84')
    return {'CRS':'EPSG:4326','axisOrder':'longitude_latitude',
        'worldFileCoefficients':values,'pixelCenterConvention':True,
        'firstSample':[-180+NATIVE_SPACING/2,90-NATIVE_SPACING/2],
        'pixelSpacing':[NATIVE_SPACING,NATIVE_SPACING],
        'pixelEdgeBounds':list(SOURCE_BOUNDS),'dimensions':list(SOURCE_DIMENSIONS),
        'worldFileDecimalRoundingMaxDegrees':max(abs(x-y) for x,y in zip(values,expected))}

@dataclass(frozen=True)
class NativeWindow:
    pixel_box:tuple
    geographic_bounds:tuple
    dimensions:tuple
    camera_envelope:tuple
    max_density:tuple
    gutter_pixels:int

def native_window(schedule,*,gutter_pixels=8,max_texture_dimension=4096,output=(1080,1920)):
    area=envelope(schedule)
    if type(gutter_pixels) is not int or not 1<=gutter_pixels<=256:
        fail('TERRAIN_SOURCE_GUTTER_REQUIRED')
    if type(max_texture_dimension) is not int or not 2<=max_texture_dimension<=16384:
        fail('TERRAIN_TEXTURE_BUDGET_INVALID')
    if tuple(output)!=(1080,1920):fail('TERRAIN_CANONICAL_OUTPUT_REQUIRED')
    densities=[[output[0]*NATIVE_SPACING/(r['flatBounds'][2]-r['flatBounds'][0]),
                output[1]*NATIVE_SPACING/(r['flatBounds'][3]-r['flatBounds'][1])] for r in schedule]
    maximum=[max(pair[axis] for pair in densities) for axis in (0,1)]
    if max(maximum)>1:fail('TERRAIN_NATIVE_PIXEL_BUDGET_EXCEEDED')
    west,south,east,north=area
    box=(math.floor((west+180)*60)-gutter_pixels,math.floor((90-north)*60)-gutter_pixels,
         math.ceil((east+180)*60)+gutter_pixels,math.ceil((90-south)*60)+gutter_pixels)
    if box[0]<0 or box[1]<0 or box[2]>SOURCE_DIMENSIONS[0] or box[3]>SOURCE_DIMENSIONS[1]:
        fail('TERRAIN_SOURCE_EDGE_GUTTER_UNAVAILABLE')
    size=(box[2]-box[0],box[3]-box[1])
    if max(size)>max_texture_dimension:fail('TERRAIN_TEXTURE_DIMENSION_LIMIT')
    geographic=(-180+box[0]/60,90-box[3]/60,-180+box[2]/60,90-box[1]/60)
    return NativeWindow(box,geographic,size,tuple(area),tuple(maximum),gutter_pixels)

def validate_style(receipt,camera_schedule,asset_root=None):
    if not isinstance(receipt,dict) or receipt.get('schema')!=RECEIPT_SCHEMA or receipt.get('styleId')!=STYLE_ID:
        fail('TERRAIN_SINGLE_SOURCE_STYLE_REQUIRED')
    asset=receipt.get('terrainAsset');source=receipt.get('sourceOriginal')
    if not isinstance(asset,dict) or not isinstance(source,dict):fail('TERRAIN_PINNED_ASSET_REQUIRED')
    if source.get('sha256')!=SOURCE_SHA256 or source.get('bytes')!=SOURCE_BYTES or source.get('dimensions')!=list(SOURCE_DIMENSIONS):
        fail('TERRAIN_ORIGINAL_SOURCE_PIN_MISMATCH')
    if source.get('CRS')!='EPSG:4326' or source.get('license')!='Public Domain' or source.get('pixelSpacing')!=[NATIVE_SPACING,NATIVE_SPACING]:
        fail('TERRAIN_SOURCE_CRS_RESOLUTION_LICENSE_REQUIRED')
    original=receipt.get('nativeWindowPolicy',{})
    window=native_window(camera_schedule,gutter_pixels=original.get('gutterSourcePixels',8),
        max_texture_dimension=original.get('maxTextureDimension',4096))
    if (receipt.get('frameCount')!=len(camera_schedule) or receipt.get('cameraEnvelope')!=list(window.camera_envelope)
            or receipt.get('cropSourcePixelBox')!=list(window.pixel_box)):
        fail('TERRAIN_CAMERA_OR_NATIVE_WINDOW_BINDING_MISMATCH')
    if (asset.get('bounds')!=list(window.geographic_bounds) or asset.get('dimensions')!=list(window.dimensions)
            or asset.get('pixelSpacing')!=[NATIVE_SPACING,NATIVE_SPACING] or asset.get('CRS')!='EPSG:4326'
            or asset.get('classification')!='BAKED HILLSHADE' or asset.get('sourceOriginalSHA256')!=SOURCE_SHA256
            or asset.get('NoData','MISSING') is not None):
        fail('TERRAIN_ASSET_REGISTRATION_OR_SOURCE_MISMATCH')
    name=asset.get('path')
    if not isinstance(name,str) or not name.startswith(ASSET_PREFIX) or '..' in Path(name).parts or '\\' in name:
        fail('TERRAIN_ASSET_PATH_SCOPE_REJECTED')
    basename=Path(name).name
    if asset.get('url')!='/recovery-assets/'+basename or not basename.endswith('.png'):
        fail('TERRAIN_EXPLICIT_ASSET_ROUTE_REQUIRED')
    root=Path(asset_root or REPO).resolve();file=root/name
    if not file.resolve().is_relative_to(root) or any(p.is_symlink() for p in [file,*file.parents]):
        fail('TERRAIN_ASSET_SYMLINK_OR_PATH_ESCAPE')
    if not file.is_file() or file.stat().st_size!=asset.get('bytes') or file_sha(file)!=asset.get('sha256'):
        fail('TERRAIN_ASSET_BYTES_OR_SHA_MISMATCH')
    with Image.open(file) as image:
        if image.format!='PNG' or image.mode!='RGB' or list(image.size)!=asset['dimensions']:
            fail('TERRAIN_ACTUAL_PNG_FORMAT_DIMENSIONS_MISMATCH')
    return {'ready':True,'schema':RECEIPT_SCHEMA,'styleId':STYLE_ID,
        'sourceStyleSHA256':hashlib.sha256(canonical(receipt)).hexdigest(),
        'cameraEnvelope':list(window.camera_envelope),'frameCount':len(camera_schedule),
        'coverageFull':True,'maxProjectedPixelsPerNativeTexel':list(window.max_density),
        'terrainAsset':dict(asset),'actualSourceStyleOnly':True,'rendererOrShaderModified':False,
        'newElevationGenerated':False,'historicalQualification':False}
