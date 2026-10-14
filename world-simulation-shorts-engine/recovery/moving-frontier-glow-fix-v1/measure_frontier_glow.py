#!/usr/bin/env python3
"""Measure glow in original raw PNG output, without rendering or changing inputs.

Normal, core-only and edge-off must have identical base material/geometry/camera
and unit data. Off still renders the existing relief-light multiplier. Parent
NORMAL contains its halo, so its FWHM is labelled combined, not isolated core.

Run with the project's pinned /usr/bin/python3 -B. Node is used only to call the
unchanged geographic projection/control/layout oracles, avoiding a copied engine.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ENGINE = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).resolve().parent
PARENT = ENGINE / 'recovery/map-engine-unit-bundle-v1'
FRAMES = (0, 74, 149)
Y_WEIGHTS = np.array([.2126, .7152, .0722], dtype=np.float64)

BRIDGE = r"""
import {readFileSync} from 'node:fs';
import {compileTerritoryControlPlan,evaluateTerritoryControlFrame}
 from './web/map_infographic_v1/territory_control_adapter_v1.mjs';
import {compileReferenceCameraTrack,evaluateReferenceCameraTrackFrame}
 from './web/map_infographic_v1/reference_camera_adapter_v1.mjs';
import {compileReferencePresentationPlan,evaluateReferencePresentationFrame,expandNativeBounds,geoToPresentationScreen}
 from './web/map_infographic_v1/reference_presentation_adapter_v2.mjs';
import {evaluateReferenceCombatLayout} from './web/map_infographic_v1/reference_combat_overlay_v2.mjs';
const root=process.argv[2],load=path=>JSON.parse(readFileSync(path,'utf8')),
 scene=load(root+'/fixtures/SCENE_PLAN.json'),parent=load('recovery/map-engine-unit-bundle-v1/fixtures/SCENE_PLAN.json'),
 off=load(root+'/fixtures/SCENE_GLOW_OFF.json'),core=load(root+'/fixtures/SCENE_CORE_ONLY.json'),
 nativePlan=load('recovery/reference-reproduction-v1/fixtures/REGIONAL-plan.json'),
 plan=compileTerritoryControlPlan(scene.controlIntent),
 camera=compileReferenceCameraTrack({baseCameraPlan:load('recovery/planner-scene-json-v1/fixtures/camera-plan.json'),
  currentNativeFrame:176,keyframes:scene.cameraKeyframes,totalFrames:150,fps:30}),
 presentation=compileReferencePresentationPlan({rollKeyframes:scene.cameraKeyframes.map(k=>({frame:k.frame,rollDegrees:k.rotationDegrees})),
  totalFrames:150,fps:30,overscan:scene.presentationProfile.overscan,width:1080,height:1920});
const keys=['controlIntent','cameraKeyframes','style','terrainProfile','presentationProfile','combatProfile'];
const same=(a,b)=>JSON.stringify(a)===JSON.stringify(b);
const inputsUnchanged=keys.every(key=>same(scene[key],parent[key])&&same(scene[key],off[key])&&same(scene[key],core[key]));
const baseLightUnchanged=['luminanceAnchor','minimumLightingFactor','reliefLightingEnabled'].every(key=>
 [parent,off,core].every(input=>input.frontierProfile[key]===scene.frontierProfile[key]));
const rows=[0,74,149].map(frame=>{
 const cameraFrame=evaluateReferenceCameraTrackFrame(camera,frame),state=evaluateReferencePresentationFrame(presentation,frame),
  bounds=expandNativeBounds({bounds:cameraFrame.flatBounds,referenceStartBounds:camera.startBounds,rollDegrees:state.rollDegrees,
   overscan:state.overscan,width:1080,height:1920,correctMeasuredPan:true}),project=geo=>geoToPresentationScreen(geo,bounds,state),
  controls=evaluateTerritoryControlFrame(plan,frame),curve=controls.longitudinalKnots.map((lon,i)=>project([lon,controls.boundaryLatitudes[i]])),
  landPolygons=scene.controlIntent.domain.flatMap(item=>{
   const polygons=item.geometry.type==='Polygon'?[item.geometry.coordinates]:item.geometry.coordinates;
   return polygons.map(rings=>rings.map(ring=>ring.map(point=>project(point))));
  }),units=evaluateReferenceCombatLayout(scene.combatProfile.units,frame,{project,safeArea:nativePlan.layout.safe,protectedGraphics:[]});
 return {frame,curve,landPolygons,units:units.units.map(unit=>({id:unit.id,footprint:unit.footprint,bounds:unit.bounds})),
  nativeExpandedBounds:bounds,presentation:state,domainGeometryBinding:plan.domainGeometryBinding,boundaryKeyframeBinding:plan.boundaryKeyframeBinding};
});
console.log(JSON.stringify({inputsUnchanged,baseLightUnchanged,rows,profile:scene.frontierProfile,parentProfile:parent.frontierProfile,
 output:[1080,1920],projection:'UNCHANGED_REFERENCE_PRESENTATION_V2_AND_CAMERA_V1',ownership:'UNCHANGED_TERRITORY_CONTROL_V1'}));
"""


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(path: Path, role: str) -> dict:
    return {'path': path.relative_to(ENGINE).as_posix(), 'role': role,
            'sha256': sha(path), 'bytes': path.stat().st_size}


def load_pixels(path: Path) -> np.ndarray:
    image = Image.open(path).convert('RGB')
    if image.size != (1080, 1920):
        raise ValueError(f'CANONICAL_RAW_PNG_REQUIRED: {path}')
    return np.asarray(image, dtype=np.uint8)


def geometry_masks(row: dict, radius: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    shape = (1080, 1920)
    land = Image.new('L', shape, 0)
    for rings in row['landPolygons']:
        part = Image.new('L', shape, 0)
        draw = ImageDraw.Draw(part)
        draw.polygon([tuple(p) for p in rings[0]], fill=255)
        for hole in rings[1:]:
            draw.polygon([tuple(p) for p in hole], fill=0)
        land = Image.fromarray(np.maximum(np.asarray(land), np.asarray(part)))
    band = Image.new('L', shape, 0)
    draw = ImageDraw.Draw(band)
    curve = [tuple(point) for point in row['curve']]
    draw.line(curve, fill=255, width=math.ceil(radius * 2 + 2), joint='curve')
    for x, y in curve:
        draw.ellipse((x-radius-1, y-radius-1, x+radius+1, y+radius+1), fill=255)
    # Only the immutable land mesh emits the glow. Three final pixels cover
    # mask rasterisation plus the unchanged roll/crop bilinear filter footprint.
    expanded_land = land.filter(ImageFilter.MaxFilter(7))
    allowed = (np.asarray(band) != 0) & (np.asarray(expanded_land) != 0)
    badges = Image.new('L', shape, 0)
    badge_draw = ImageDraw.Draw(badges)
    for unit in row['units']:
        badge_draw.polygon([tuple(p) for p in unit['footprint']], fill=255)
    badge_mask = np.asarray(badges.filter(ImageFilter.MaxFilter(5))) != 0
    return np.asarray(land) != 0, allowed, badge_mask


def bilinear(image: np.ndarray, points: np.ndarray) -> np.ndarray:
    # Canvas geometry uses pixel-edge coordinates; PNG index (i,j) represents
    # the fragment centre (i+.5,j+.5), not the edge (i,j).
    coords = points - .5
    x = np.clip(coords[:, 0], 0, image.shape[1]-1)
    y = np.clip(coords[:, 1], 0, image.shape[0]-1)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    x1 = np.minimum(x0+1, image.shape[1]-1); y1 = np.minimum(y0+1, image.shape[0]-1)
    fx = (x-x0)[:, None]; fy = (y-y0)[:, None]
    return ((image[y0, x0]*(1-fx)+image[y0, x1]*fx)*(1-fy)
            +(image[y1, x0]*(1-fx)+image[y1, x1]*fx)*fy)


def fwhm(distances: np.ndarray, values: np.ndarray) -> float | None:
    peak = float(np.max(values))
    if peak <= 1e-8:
        return None
    selected = np.flatnonzero(values >= peak/2)
    if not len(selected):
        return None
    first, last = int(selected[0]), int(selected[-1])
    if first == 0 or last == len(values)-1:
        return None  # support truncated; no fabricated width
    threshold = peak/2
    left = float(np.interp(threshold, values[first-1:first+1], distances[first-1:first+1]))
    right = float(np.interp(threshold, values[last:last+2][::-1], distances[last:last+2][::-1]))
    return right-left


def weighted_radius(distances: np.ndarray, values: np.ndarray, fraction: float=.95) -> float | None:
    values = np.maximum(values, 0)
    if float(np.sum(values)) <= 1e-8:
        return None
    order = np.argsort(np.abs(distances), kind='stable')
    cumulative = np.cumsum(values[order]); target = cumulative[-1]*fraction
    return float(abs(distances[order[min(int(np.searchsorted(cumulative, target)), len(order)-1)]]))


def stats(values: list[float]) -> dict | None:
    if not values:
        return None
    a = np.asarray(values, dtype=np.float64)
    return {'min': float(np.min(a)), 'p05': float(np.quantile(a,.05)),
            'median': float(np.median(a)), 'p95': float(np.quantile(a,.95)), 'max': float(np.max(a))}


def sample_profiles(row: dict, land: np.ndarray, badge_mask: np.ndarray,
                    normal: np.ndarray, off: np.ndarray, core: np.ndarray,
                    parent: np.ndarray, profile: dict) -> list[dict]:
    reach = max(float(profile['haloSupportPixels'])+5, 15)
    clearance = math.ceil(reach+2)
    land_interior = np.asarray(Image.fromarray(land.astype(np.uint8)*255).filter(
        ImageFilter.MinFilter(clearance*2+1))) != 0
    badge_exclusion = np.asarray(Image.fromarray(badge_mask.astype(np.uint8)*255).filter(
        ImageFilter.MaxFilter(clearance*2+1))) != 0
    distances = np.arange(-reach, reach+.125, .25, dtype=np.float64)
    inputs = {key: value.astype(np.float64)/255 for key,value in
              [('normal',normal),('off',off),('core',core),('parent',parent)]}
    target_y = float(np.asarray(profile['centerColor']) @ Y_WEIGHTS)
    output = []
    for segment,(start,end) in enumerate(zip(row['curve'][:-1],row['curve'][1:])):
        start=np.asarray(start); end=np.asarray(end); tangent=end-start
        length=float(np.linalg.norm(tangent))
        if length < 5:
            continue
        axis=np.array([-tangent[1],tangent[0]])/length
        # Midpoints avoid the derivative discontinuity at an authored knot.
        center=(start+end)/2
        x,y=np.floor(center).astype(int)
        if not (clearance <= x < 1080-clearance and clearance <= y < 1920-clearance):
            continue
        if not land_interior[y,x] or badge_exclusion[y,x]:
            continue
        points=center[None,:]+distances[:,None]*axis[None,:]
        curves={key:bilinear(value,points)@Y_WEIGHTS for key,value in inputs.items()}
        core_delta=np.maximum(curves['core']-curves['off'],0)
        new_delta=np.maximum(curves['normal']-curves['off'],0)
        old_delta=np.maximum(curves['parent']-curves['off'],0)
        halo_delta=np.maximum(curves['normal']-curves['core'],0)
        # The isolated core uses a uniform colour and SRC_ALPHA. Dividing its
        # delta by local colour contrast estimates alpha; the measured support
        # includes actual native rasterisation and the presentation filter.
        denominator=np.maximum(target_y-curves['off'],.025)
        alpha_shape=np.maximum(core_delta/denominator,0)
        if float(np.max(core_delta)) < .03 or float(np.sum(alpha_shape)) <= 1e-8:
            continue
        centroid=float(np.sum(distances*alpha_shape)/np.sum(alpha_shape))
        core_width=fwhm(distances,alpha_shape)
        new_width=fwhm(distances,new_delta)
        old_width=fwhm(distances,old_delta)
        halo_radius=weighted_radius(distances,halo_delta)
        old_radius=weighted_radius(distances,old_delta)
        if any(value is None for value in [core_width,new_width,old_width,halo_radius,old_radius]):
            continue
        output.append({'segment':segment,'centerOutputPixels':center.tolist(),
         'coreFwhmOutputPixels':core_width,'newCombinedFwhmOutputPixels':new_width,
         'parentCombinedFwhmOutputPixels':old_width,
         'newHalo95EnergyRadiusOutputPixels':halo_radius,
         'parentCombined95EnergyRadiusOutputPixels':old_radius,
         'corePeakDeltaY':float(np.max(core_delta)),
         'newPeakDeltaY':float(np.max(new_delta)),
         'parentPeakDeltaY':float(np.max(old_delta)),
         'haloPeakDeltaY':float(np.max(halo_delta)),
         'coreCentroidOffsetFromActualFieldPixels':centroid,
         'brightnessGainVsParent':float(np.max(new_delta)/max(float(np.max(old_delta)),1e-8))})
    return output


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'evidence/FRONTIER_GLOW_PIXEL_MEASUREMENTS.json')
    args=parser.parse_args()
    bridge_result=subprocess.run(['node','--input-type=module','-',str(ROOT)],input=BRIDGE,
        text=True,cwd=ENGINE,capture_output=True,check=True)
    context=json.loads(bridge_result.stdout)
    bindings=[record(ROOT/'fixtures'/name,'EXECUTED_SCENE_VARIANT') for name in
        ('SCENE_PLAN.json','SCENE_GLOW_OFF.json','SCENE_CORE_ONLY.json')]
    bindings.append(record(PARENT/'fixtures/SCENE_PLAN.json','IMMUTABLE_PARENT_SCENE'))
    measurements=[]
    for row in context['rows']:
        frame=row['frame']; filename=f'{frame:03d}.png'
        paths={'normal':ROOT/'evidence/native_probe'/filename,
               'off':ROOT/'evidence/glow_off'/filename,
               'core':ROOT/'evidence/core_only'/filename,
               'parent':PARENT/'evidence/native_probe'/filename}
        images={key:load_pixels(path) for key,path in paths.items()}
        bindings.extend(record(path,key.upper()+'_RAW_NATIVE_PNG') for key,path in paths.items())
        radius=max(float(context['profile']['haloSupportPixels']),float(context['parentProfile']['haloSupportPixels']))+3
        land,allowed,badge_mask=geometry_masks(row,radius)
        delta=np.abs(images['normal'].astype(np.int16)-images['parent'].astype(np.int16))
        changed=np.any(delta!=0,axis=2)
        outside=~allowed
        # Off and core-only deliberately retain every base-light uniform.
        off_delta=np.abs(images['normal'].astype(np.int16)-images['off'].astype(np.int16))
        samples=sample_profiles(row,land,badge_mask,images['normal'],images['off'],images['core'],images['parent'],context['profile'])
        metrics={key:stats([sample[key] for sample in samples]) for key in
         ('coreFwhmOutputPixels','newCombinedFwhmOutputPixels','parentCombinedFwhmOutputPixels',
          'newHalo95EnergyRadiusOutputPixels','parentCombined95EnergyRadiusOutputPixels',
          'corePeakDeltaY','newPeakDeltaY','parentPeakDeltaY','haloPeakDeltaY',
          'coreCentroidOffsetFromActualFieldPixels','brightnessGainVsParent')}
        measurements.append({'frame':frame,'output':[1080,1920],
         'projection':context['projection'],'allowedRawDifferenceBandOutputPixels':radius,
         'rawProtection':{'outsideAllowedLandClippedBandPixels':int(np.count_nonzero(outside)),
          'outsideBandChangedPixelsVsParent':int(np.count_nonzero(changed&outside)),
          'outsideBandMaxChannelDeltaVsParent':int(np.max(delta[outside])),
          'outsideBandBitExactVsParent':bool(not np.any(changed&outside)),
          'badgeProtectedFootprintPixels':int(np.count_nonzero(badge_mask)),
          'badgeProtectedFootprintChangedPixelsVsParent':int(np.count_nonzero(changed&badge_mask)),
          'normalVsOffOutsideBandChangedPixels':int(np.count_nonzero(np.any(off_delta!=0,axis=2)&outside))},
         'actualSampleCount':len(samples),'measuredProfileStats':metrics,'samples':samples,
         'parentCoreOnlyMeasured':False,'centroidMethod':'RAW_CORE_ONLY_ALPHA_SHAPE_CENTROID_RELATIVE_TO_SAME_PROJECTED_FIELD',
         'coreWidthMethod':'RAW_CORE_ONLY_CONTRAST_NORMALISED_ALPHA_FWHM',
         'haloMethod':'NORMAL_MINUS_CORE_ONLY_95_PERCENT_POSITIVE_LUMINANCE_ENERGY_RADIUS'})
    errors=[]
    if not context['inputsUnchanged']:errors.append('NON_GLOW_CAMERA_MATERIAL_UNIT_OR_CONTROL_INPUT_CHANGED')
    if not context['baseLightUnchanged']:errors.append('EXISTING_RELIEF_LIGHT_UNIFORMS_CHANGED')
    for row in measurements:
        if not row['rawProtection']['outsideBandBitExactVsParent']:errors.append(f"RAW_NON_GLOW_PIXEL_CHANGE_FRAME_{row['frame']}")
        if row['rawProtection']['normalVsOffOutsideBandChangedPixels']:errors.append(f"RAW_GLOW_OUTSIDE_FINITE_SUPPORT_FRAME_{row['frame']}")
        if row['rawProtection']['badgeProtectedFootprintChangedPixelsVsParent']:errors.append(f"RAW_BADGE_FOOTPRINT_CHANGED_FRAME_{row['frame']}")
        if row['actualSampleCount']<5:errors.append(f"INSUFFICIENT_LAND_INTERIOR_UNOCCLUDED_MEASUREMENTS_FRAME_{row['frame']}")
    result={'schema':'MOVING_FRONTIER_GLOW_RAW_PIXEL_MEASUREMENTS_V1',
     'status':'TECHNICAL_PASS' if not errors else 'TECHNICAL_FAIL','errors':errors,
     'inputBindings':bindings,'actualFrames':list(FRAMES),
     'profile':context['profile'],'parentProfile':context['parentProfile'],
     'nonGlowInputsUnchanged':context['inputsUnchanged'],'baseReliefLightingUnchanged':context['baseLightUnchanged'],
     'publicTimelineChanged':False,'sourceVideoPixelsSampled':False,'rawNativeOutputMeasured':True,
     'decodedMp4Measured':False,'referenceQualityClaimed':False,'visualQualityConclusion':'USER_VIDEO_REVIEW_REQUIRED',
     'methodLimits':['Three actual static frames, not a 150-frame raw-pixel equality claim.',
      'Parent raw NORMAL includes halo; parent width is combined-highlight FWHM, not isolated core width.',
      'Half-pixel canvas-centre and quarter-pixel bilinear samples; PNG is original output, not reencoded.',
      'Land-interior midpoint samples exclude badges, coast clipping and knot derivative discontinuities.',
      'Outside support equality uses raw PNG; lossy H264 can change decoded pixels beyond the light support.'],
     'frames':measurements}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise FileExistsError(f'Preserve existing measurement report: {args.output}')
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'errors':errors,'frames':[
     {'frame':row['frame'],'samples':row['actualSampleCount'],'rawProtection':row['rawProtection'],
      'stats':row['measuredProfileStats']} for row in measurements]},ensure_ascii=False))
    if errors:raise SystemExit(1)


if __name__=='__main__':
    main()
