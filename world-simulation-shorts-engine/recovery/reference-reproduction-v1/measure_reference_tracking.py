#!/usr/bin/env python3
"""Focused source-derived matching stills and static-terrain camera tracking.

Does not alter/reencode input, inspect completed FINAL source, or rerun the full
reference audit. Tracking is a screen-space approximation, not georeferencing.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "data/REFERENCE_65379_COMPRESSED.mp4"
OUTPUT = HERE / "evidence/reference_tracking"
EXPECTED_SHA = "5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6"
START, END = 5.181813, 10.181813
RELATIVE_TIMES = [0, 1.25, 2.5, 3.75, 4.9667, 5]
MAP_CROP = [0, 211, 1080, 2131]
TERRAIN_ROI = [220, 250, 650, 430]
DOWNSAMPLE = 4


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(name: str, data) -> None:
    target = OUTPUT / name
    temporary = target.with_name(target.name + ".partial")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(target)


def extract_frames(indices: list[int]) -> list[Image.Image]:
    selection = "+".join(f"eq(n\\,{index})" for index in indices)
    command = ["ffmpeg", "-v", "error", "-threads", "2", "-i", str(SOURCE), "-vf", f"select={selection}", "-map", "0:v:0", "-an", "-vsync", "0", "-frames:v", str(len(indices)), "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    stride = 1080 * 2520 * 3
    if len(process.stdout) != len(indices) * stride or process.stderr:
        raise RuntimeError("Focused actual reference frame extraction failed")
    return [Image.frombytes("RGB", (1080,2520), process.stdout[offset:offset+stride]) for offset in range(0,len(process.stdout),stride)]


def highpass(image: Image.Image) -> np.ndarray:
    grayscale = image.convert("L")
    return np.asarray(grayscale, dtype=np.float64) - np.asarray(grayscale.filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float64)


def next_power(value: int) -> int:
    return 1 << (value - 1).bit_length()


def template_match(target: np.ndarray, template: np.ndarray, mask: np.ndarray) -> tuple[float, int, int, float]:
    """Masked normalized cross correlation at every valid target translation."""
    height, width = target.shape
    th, tw = template.shape
    if tw >= width or th >= height or mask.sum() < 400:
        return -1.0, 0, 0, 0.0
    shape = (next_power(height+th), next_power(width+tw))
    target_fft = np.fft.rfft2(target, s=shape)
    mask_fft = np.fft.rfft2(mask, s=shape)
    total = float(mask.sum())
    centered = (template - float((template * mask).sum() / total)) * mask
    source_ss = float((centered**2).sum())
    cross = np.fft.irfft2(target_fft * np.conj(np.fft.rfft2(centered, s=shape)), s=shape)
    patch_sum = np.fft.irfft2(target_fft * np.conj(mask_fft), s=shape)
    patch_ss = np.fft.irfft2(np.fft.rfft2(target**2, s=shape) * np.conj(mask_fft), s=shape)
    target_variance = np.maximum(patch_ss - patch_sum**2 / total, 1e-8)
    ncc = cross / np.sqrt(target_variance * max(source_ss, 1e-8))
    ncc = ncc[:height-th+1, :width-tw+1]
    # Match only real map texture, not phone chrome/subtitles at its bottom.
    ncc[:54] = -1
    ncc[300:] = -1
    y, x = np.unravel_index(np.argmax(ncc), ncc.shape)
    score = float(ncc[y,x])
    alternative = ncc.copy()
    alternative[max(0,y-12):y+13,max(0,x-12):x+13] = -1
    second_score = float(alternative.max())
    return score, int(x), int(y), second_score


def bilinear(array: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x0 = np.clip(x0,0,array.shape[1]-2)
    y0 = np.clip(y0,0,array.shape[0]-2)
    fx, fy = x-x0, y-y0
    return array[y0,x0]*(1-fx)*(1-fy)+array[y0,x0+1]*fx*(1-fy)+array[y0+1,x0]*(1-fx)*fy+array[y0+1,x0+1]*fx*fy


def fit_transform(reference: Image.Image, target: Image.Image) -> dict:
    small_target = target.resize((270,630), Image.Resampling.BOX)
    target_texture = highpass(small_target)
    source_patch = reference.crop(tuple(TERRAIN_ROI))
    hsv = np.asarray(source_patch.convert("HSV"))
    rgb = np.asarray(source_patch)
    # Exclude colored territory and any player/icon black/white pixels.
    orange = (hsv[:,:,0] <= 35) & (hsv[:,:,1] >= 105) & (hsv[:,:,2] >= 60)
    purple = (hsv[:,:,0] >= 170) & (hsv[:,:,0] <= 225) & (hsv[:,:,1] >= 80)
    eligible = ~(orange | purple) & (rgb.mean(axis=2) > 20) & (rgb.mean(axis=2) < 230)
    source_mask = Image.fromarray((eligible * 255).astype(np.uint8))
    ranked = []
    for angle in np.arange(-2,9,1.0):
        for scale in np.arange(0.95, 1.355, 0.01):
            size = tuple(max(1,round(dimension * float(scale) / DOWNSAMPLE)) for dimension in source_patch.size)
            rotated = source_patch.resize(size, Image.Resampling.BOX).rotate(float(angle),resample=Image.Resampling.BICUBIC,expand=True)
            rotated_mask = source_mask.resize(size,Image.Resampling.BOX).rotate(float(angle),resample=Image.Resampling.BICUBIC,expand=True).filter(ImageFilter.MinFilter(3))
            mask = np.asarray(rotated_mask,dtype=float)/255
            score, x, y, alternative = template_match(target_texture, highpass(rotated), mask)
            ranked.append({"scale":float(scale),"screen_rotation_degrees":-float(angle),"score":score,"x":x,"y":y,"rotated_size":list(rotated.size),"alternative_translation_score":alternative})
    ranked.sort(key=lambda item: item["score"], reverse=True)
    best = ranked[0]
    scale = best["scale"]
    angle = best['screen_rotation_degrees']
    source_center = np.asarray([(TERRAIN_ROI[0]+TERRAIN_ROI[2])/2,(TERRAIN_ROI[1]+TERRAIN_ROI[3])/2])
    theta = np.deg2rad(angle)
    matrix = scale*np.asarray([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    target_center = np.asarray([best['x']*4+best['rotated_size'][0]*2,best['y']*4+best['rotated_size'][1]*2])
    tx,ty = (target_center-matrix@source_center).tolist()
    # Refine four model parameters against actual full-screen high-pass texture
    # using bilinear samples. This avoids treating a 4px FFT grid as precision.
    small_reference=reference.resize((270,630),Image.Resampling.BOX)
    source_texture=highpass(small_reference)
    small_hsv=np.asarray(small_reference.convert('HSV'))
    small_rgb=np.asarray(small_reference)
    ys,xs=np.mgrid[int(np.ceil(TERRAIN_ROI[1]/4)):int(TERRAIN_ROI[3]/4),int(np.ceil(TERRAIN_ROI[0]/4)):int(TERRAIN_ROI[2]/4)]
    colors=small_hsv[ys,xs]
    good=~(((colors[:,:,0]<=35)&(colors[:,:,1]>=105)&(colors[:,:,2]>=60))|((colors[:,:,0]>=170)&(colors[:,:,0]<=225)&(colors[:,:,1]>=80)))
    good&=(small_rgb[ys,xs].mean(axis=2)>20)&(small_rgb[ys,xs].mean(axis=2)<230)
    source_x,source_y=xs[good].astype(float)*4+1.5,ys[good].astype(float)*4+1.5
    source_values=source_texture[ys[good],xs[good]]
    source_values=source_values-source_values.mean()
    def sample_score(parameters):
        s,a,t_x,t_y=parameters
        radians=np.deg2rad(a)
        x=(s*(np.cos(radians)*source_x-np.sin(radians)*source_y)+t_x-1.5)/4
        y=(s*(np.sin(radians)*source_x+np.cos(radians)*source_y)+t_y-1.5)/4
        if x.min()<0 or x.max()>268 or y.min()<54 or y.max()>300:
            return -1.0
        sampled=bilinear(target_texture,x,y)
        sampled=sampled-sampled.mean()
        return float(source_values@sampled/np.sqrt(max(float(source_values@source_values)*float(sampled@sampled),1e-12)))
    parameters=np.asarray([scale,angle,tx,ty],dtype=float)
    refined_score=sample_score(parameters)
    # Coordinate descent keeps this focused, dependency-free fit bounded.
    for steps in [[.005,.5,2,2],[.002,.2,1,1],[.001,.1,.5,.5],[.0005,.05,.25,.25]]:
        for _ in range(8):
            improved=False
            for dimension,step in enumerate(steps):
                trials=[]
                for sign in [-1,1]:
                    trial=parameters.copy();trial[dimension]+=sign*step
                    trials.append((sample_score(trial),trial))
                score,trial=max(trials,key=lambda value:value[0])
                if score>refined_score+1e-7:
                    refined_score=score;parameters=trial;improved=True
            if not improved:break
    if reference.tobytes()==target.tobytes():
        parameters=np.asarray([1,0,0,0],dtype=float);refined_score=1.0
    scale,angle,tx,ty=parameters.tolist()
    theta=np.deg2rad(angle)
    matrix=scale*np.asarray([[np.cos(theta),-np.sin(theta)],[np.sin(theta),np.cos(theta)]])
    center = np.asarray([540.0,1171.0]) # map-crop centre in full recording coordinates
    center_delta = matrix@center + np.asarray([tx,ty])-center
    reliable = refined_score >= 0.5 and best["score"] - best["alternative_translation_score"] >= 0.10
    return {
        "status": "MEASURED_SCREEN_SIMILARITY_APPROXIMATION" if reliable else "NOT_MEASURABLE_RELIABLY",
        "model": "target_point = scale * rotation(screen_angle) * source_point + translation",
        "scale": round(scale,6) if reliable else None,
        "screen_rotation_degrees":round(angle,4) if reliable else None,
        "rotation_direction":'COUNTERCLOCKWISE' if reliable and angle<0 else 'CLOCKWISE' if reliable and angle>0 else 'NONE_OR_NOT_MEASURABLE',
        "translation_full_source_pixels": [round(tx,3),round(ty,3)] if reliable else None,
        "map_crop_center_displacement_pixels": center_delta.round(3).tolist() if reliable else None,
        "normalized_terrain_texture_correlation": round(refined_score,6),
        "coarse_fft_terrain_texture_correlation":round(best['score'],6),
        "alternate_translation_correlation": round(best["alternative_translation_score"],6),
        "confidence_margin": round(best["score"]-best["alternative_translation_score"],6),
        "fitted_best_candidate_for_diagnostics": {"scale":round(scale,6),"screen_rotation_degrees":round(angle,4),"translation_pixels":[round(tx,3),round(ty,3)]},
        "coarse_scale_search_step":0.01,
        "coarse_angle_search_step_degrees":1.0,
        "translation_search_step_source_pixels":4,
        "bilinear_refinement_steps":{"scale":.0005,"rotation_degrees":.05,"translation_source_pixels":.25},
        "source_eligible_texture_fraction":round(float(eligible.mean()),6),
        "top_grid_candidates": [{"scale":round(item['scale'],6),"screen_rotation_degrees":item['screen_rotation_degrees'],"correlation":round(item['score'],6)} for item in ranked[:5]],
    }


def main() -> None:
    OUTPUT.mkdir(parents=True,exist_ok=True)
    input_sha = sha(SOURCE.read_bytes())
    if input_sha != EXPECTED_SHA:
        raise RuntimeError("Approved compressed reference SHA differs")
    timestamps = json.loads((HERE/'evidence/reference_audit/FRAME_TIMESTAMPS.json').read_text())
    frame_rows = json.loads((HERE/'evidence/reference_audit/FRAMES.json').read_text())
    selected = []
    for relative in RELATIVE_TIMES:
        index = min(range(len(timestamps)),key=lambda i:abs(float(timestamps[i]['best_effort_timestamp_time'])-START-relative))
        selected.append({"requested_relative_seconds":relative,"requested_absolute_seconds":START+relative,"frame":index,"actual_pts_seconds":float(timestamps[index]['best_effort_timestamp_time'])})
    cached=[OUTPUT/f"REFERENCE_REL_{item['requested_relative_seconds']:06.3f}_FRAME_{item['frame']:03d}_FULL.png" for item in selected]
    images=[Image.open(path).convert('RGB') for path in cached] if all(path.exists() for path in cached) else extract_frames([item['frame'] for item in selected])
    records=[]
    for item,image in zip(selected,images):
        prefix=f"REFERENCE_REL_{item['requested_relative_seconds']:06.3f}_FRAME_{item['frame']:03d}"
        full_path=OUTPUT/f"{prefix}_FULL.png"
        crop_path=OUTPUT/f"{prefix}_MAP.png"
        image.save(full_path,optimize=True)
        image.crop(tuple(MAP_CROP)).save(crop_path,optimize=True)
        rgb_sha=sha(image.tobytes())
        if rgb_sha != frame_rows[item['frame']]['decoded_rgb_sha256']:
            raise RuntimeError("Focused extraction does not equal the completed full reference audit RGB")
        tracking=fit_transform(images[0],image)
        row={**item,"pts_difference_from_requested_seconds":round(item['actual_pts_seconds']-item['requested_absolute_seconds'],6),"full_png":full_path.name,"full_png_sha256":sha(full_path.read_bytes()),"map_png":crop_path.name,"map_png_sha256":sha(crop_path.read_bytes()),"decoded_rgb_sha256":rgb_sha,"matches_full_audit_rgb":True,"screen_color_measurements":frame_rows[item['frame']]['screen_color_measurements'],"camera_screen_tracking":tracking}
        records.append(row)
        write_json('TRACKING_PROGRESS.json',{'status':'IN_PROGRESS','input_sha256':input_sha,'records':records})
        print(json.dumps({'frame':item['frame'],'pts':item['actual_pts_seconds'],'tracking':tracking}),flush=True)
    report={'status':'FOCUSED_MEASUREMENT_COMPLETE','input_sha256':input_sha,'input_sha256_after':sha(SOURCE.read_bytes()),'selected_reference_interval_seconds':[START,END],'selected_reference_interval_duration_seconds':5.0,'map_crop_source_pixels':MAP_CROP,'static_terrain_source_roi':TERRAIN_ROI,'method':'Pillow downsample/1.2px high-pass static north-China terrain; HSV mask excludes orange/purple; Numpy FFT masked NCC coarse scale/rotation/translation followed by bilinear coordinate-descent refinement','rotation_fixed_zero':False,'source_input_unchanged':sha(SOURCE.read_bytes())==input_sha,'full_reference_audit_repeated':False,'source_input_reencoded':False,'records':records,'limits':['Screen-space transform on one unchanged north-China terrain patch only; no geographic camera position inferred','Similarity approximation; perspective/nonrigid terrain effects may lower correlation','Search resolution is not estimation accuracy; global/camera-pose accuracy not certified','Matches nearest source PTS; compressed VFR phone footage cannot provide exactly requested temporal sample','Camera centre displacement is apparent image motion, not inferred Earth camera movement','Static texture excludes faction changes but finite ROI does not prove global framing equality'],'visual_acceptance_claimed':False,'required_temp_only_files':0}
    write_json('TRACKING_REPORT.json',report)
    write_json('TRACKING_PROGRESS.json',{'status':'PASS','input_sha256':input_sha,'records':records})
    print(json.dumps({'status':report['status'],'records':len(records),'input_unchanged':report['source_input_unchanged']}),flush=True)


if __name__=='__main__':
    main()
