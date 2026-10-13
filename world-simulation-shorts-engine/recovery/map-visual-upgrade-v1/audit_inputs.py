#!/usr/bin/env python3
"""Freshly decode the full relevant reference interval and saved candidate.

The reference's 958-frame whole-video audit is preserved and rebound by the
original MP4 SHA. This audit freshly decodes every selected 5-second frame and
every current candidate frame. It never reencodes or mutates either input.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'reference-reproduction-v1'
PREVIOUS=HERE.parent/'reference-quality-rework-v2'
spec=importlib.util.spec_from_file_location('preserved_input_audit_metrics',PREVIOUS/'audit_inputs.py')
helpers=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
REFERENCE_SHA='5bfe11c8d034a6681bd1ce1ca81fa66c142d58c18a1ea8d2f1c80c903a8476a6'
CANDIDATE_SHA='3e424c9af11a30bce69d98ddf3d2313b2d2138a69da020daf7c59b05df8aec88'
START,END=5.181813,10.181813
TIMES=[0,.5,1,1.5,2,2.5,3,3.5,4,4.5,149/30]
ROOT=HERE/'evidence/input_audit'

def json_save(file,data):
    file.parent.mkdir(parents=True,exist_ok=True)
    pending=file.with_name(file.name+'.pending')
    pending.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    pending.replace(file)

def audit(role,source,expected_sha,previous_rows):
    before=helpers.digest(source)
    if before!=expected_sha:raise RuntimeError('ACTUAL_INPUT_SHA_MISMATCH '+role)
    meta,pts=helpers.video_metadata(source)
    v=[s for s in meta['streams'] if s['codec_type']=='video']
    if len(v)!=1:raise RuntimeError('ONE_VIDEO_STREAM_REQUIRED')
    video=v[0];w,h=video['width'],video['height']
    if role=='reference':
        if (w,h,len(pts))!=(1080,2520,958) or abs(float(meta['format']['duration'])-31.813189)>1e-5:
            raise RuntimeError('FULL_REFERENCE_IDENTITY_DURATION_SHAPE_MISMATCH')
        indices=[i for i,t in enumerate(pts) if START<=t<END]
        if indices!=list(range(160,311)):raise RuntimeError('FULL_RELEVANT_REFERENCE_INTERVAL_REQUIRED')
        filter_args=['-vf',f'select=between(n\\,{indices[0]}\\,{indices[-1]})']
    else:
        if (w,h,len(pts))!=(1080,1920,150) or float(meta['format']['duration'])!=5:
            raise RuntimeError('CURRENT_5S_CANDIDATE_IDENTITY_FORMAT_MISMATCH')
        indices=list(range(150));filter_args=[]
    if any(b<=a for a,b in zip(pts,pts[1:])):raise RuntimeError('CHRONOLOGICAL_PTS_REQUIRED')
    prior=json.loads(previous_rows.read_text())
    destination=ROOT/role;destination.mkdir(parents=True,exist_ok=True)
    json_save(destination/'FFPROBE.json',meta)
    selected={min(indices,key=lambda i:abs(pts[i]-(START+t if role=='reference' else t))):t for t in TIMES}
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14)
    command=['ffmpeg','-v','error','-threads','2','-i',str(source),'-map','0:v:0','-an',*filter_args,
             '-vsync','0','-pix_fmt','rgb24','-f','rawvideo','pipe:1']
    rows=[];samples=[];sheets=[];mismatches=[];sheet=None
    stderr_file=destination/'DECODE_STDERR.txt'
    with stderr_file.open('wb') as stderr:
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=stderr)
        try:
            for ordinal,index in enumerate(indices):
                raw=helpers.read_exact(proc.stdout,w*h*3)
                if len(raw)!=w*h*3:raise RuntimeError('INCOMPLETE_RGB_FRAME '+role+' '+str(index))
                decoded=hashlib.sha256(raw).hexdigest()
                saved=prior[index]
                agree=(decoded==saved['decoded_rgb_sha256'] and abs(pts[index]-saved['pts_seconds'])<1e-6)
                if not agree:mismatches.append(index)
                image=Image.frombytes('RGB',(w,h),raw)
                content=image.crop((0,211,1080,2131)) if role=='reference' else image
                metrics=helpers.screen_metrics(content)
                if metrics['blank_flag']:raise RuntimeError('BLACK_OR_BLANK_FRAME '+role+' '+str(index))
                rows.append({'sourceFrame':index,'intervalOrdinal':ordinal,'ptsSeconds':pts[index],
                    'relativeSeconds':pts[index]-(START if role=='reference' else 0),
                    'decodedRgbSha256':decoded,'matchesPreservedFullRgbAudit':agree,'screenMetrics':metrics})
                tile=ordinal%30
                if tile==0:sheet=Image.new('RGB',(1080,1720),'#111111')
                x=(tile%6)*180;y=(tile//6)*344
                sheet.paste(content.resize((180,320),Image.Resampling.LANCZOS),(x,y))
                ImageDraw.Draw(sheet).text((x+3,y+324),f'{index:03d} | {rows[-1]["relativeSeconds"]:.3f}s',font=font,fill='white')
                if tile==29 or ordinal==len(indices)-1:
                    name=f'CONTACT_{len(sheets):02d}_FRAMES_{indices[ordinal-tile]:03d}_{index:03d}.png'
                    sheet.save(destination/name,optimize=True)
                    sheets.append({'file':name,'firstSourceFrame':indices[ordinal-tile],'lastSourceFrame':index,
                        'frames':tile+1,'sha256':helpers.digest(destination/name)})
                if index in selected:
                    name=f'{role.upper()}_REL_{selected[index]:06.3f}_FRAME_{index:03d}.png'
                    content.save(destination/name,optimize=True)
                    samples.append({'file':name,'sha256':helpers.digest(destination/name),'sourceFrame':index,
                        'ptsSeconds':pts[index],'requestedRelativeSeconds':selected[index]})
                if ordinal%30==0 or ordinal==len(indices)-1:
                    print(json.dumps({'role':role,'decodedRelevantFrames':ordinal+1,'sourceFrame':index,'preservedRgbMismatches':len(mismatches)}),flush=True)
            if proc.stdout.read(1) or proc.wait()!=0 or stderr_file.stat().st_size:
                raise RuntimeError('REFERENCE_INTERVAL_OR_CANDIDATE_DECODE_ERROR '+role)
        except BaseException:
            proc.kill();proc.wait();raise
    if helpers.digest(source)!=before or mismatches:raise RuntimeError('INPUT_MUTATED_OR_PRIOR_FRAME_PIXELS_CHANGED '+role)
    report={'schema':'MAP_VISUAL_RELEVANT_INPUT_DECODE_V1','status':'PASS','role':role,'inputSha256':before,
        'inputUnchanged':True,'reencoded':False,'sourceDurationSeconds':float(meta['format']['duration']),
        'sourceTotalFrames':len(pts),'freshDecodedRelevantFrames':len(rows),'firstSourceFrame':indices[0],
        'lastSourceFrame':indices[-1],'everyRelevantFrameMatchesPreservedRgbAudit':True,'chronologicalPts':True,
        'fullDurationChronologicalContactCoverage':True,'contacts':sheets,'samples':samples,
        'decodeStderrBytes':0,'command':command,'technicalPassOnly':True,'visualQualityPassClaimed':False}
    json_save(destination/'FRAMES.json',rows);json_save(destination/'REPORT.json',report)
    return report

def main():
    reference=audit('reference',BASE/'data/REFERENCE_65379_COMPRESSED.mp4',REFERENCE_SHA,
                    BASE/'evidence/reference_audit/FRAMES.json')
    candidate=audit('candidate',PREVIOUS/'public-review/WORLD_ENGINE_REFERENCE_65379_QUALITY_REWORK_5S.mp4',
                    CANDIDATE_SHA,PREVIOUS/'evidence/candidate_audit/FRAMES.json')
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',22)
    comparisons=[]
    for index,(left,right) in enumerate(zip(reference['samples'],candidate['samples'])):
        a=Image.open(ROOT/'reference'/left['file']).convert('RGB');b=Image.open(ROOT/'candidate'/right['file']).convert('RGB')
        figure=Image.new('RGB',(2184,1990),'#111111');figure.paste(a,(0,70));figure.paste(b,(1104,70))
        draw=ImageDraw.Draw(figure)
        draw.text((18,12),f'REFERENCE relative {left["requestedRelativeSeconds"]:.3f}s / PTS {left["ptsSeconds"]:.6f}s',font=font,fill='white')
        draw.text((1122,12),f'PRESERVED 65406 / frame {right["sourceFrame"]} / {right["ptsSeconds"]:.6f}s',font=font,fill='white')
        name=f'INPUT_COMPARE_{index:02d}_REL_{left["requestedRelativeSeconds"]:06.3f}.png'
        figure.save(ROOT/name,optimize=True);comparisons.append({'file':name,'sha256':helpers.digest(ROOT/name),
            'reference':left,'currentCandidate':right})
    previous_whole=json.loads((BASE/'evidence/REFERENCE_AUDIT_SUMMARY.json').read_text())
    result={'schema':'MAP_VISUAL_INPUT_BINDING_V1','status':'PASS','reference':reference,'currentCandidate':candidate,
        'referenceIntervalSeconds':[START,END],'timeSeriesComparisons':comparisons,
        'wholeReferenceAuditReused':{'referenceShaIdentical':True,'preservedFrameCount':958,
            'preservedWholeVisualReview':previous_whole['chronologicalVisualInspection'],
            'record':'recovery/reference-reproduction-v1/evidence/REFERENCE_AUDIT_SUMMARY.json',
            'freshRelevant151FrameRgbMatch':True,'whole958ReDecodeClaimedThisRun':False},
        'semanticMode':'EXISTING_COUNTERFACTUAL_REFERENCE_VISUAL_STUDY_NOT_HISTORICAL_ASSERTION',
        'visualQualityPassClaimed':False,'actualChronologicalVisualInspection':'PENDING',
        'nativeRealtimePlaybackClaimed':False,'inputsModified':False,'requiredTempOnlyFiles':0}
    json_save(ROOT/'REPORT.json',result)
    print(json.dumps({'status':'PASS','referenceRelevantFrames':reference['freshDecodedRelevantFrames'],
        'candidateFrames':candidate['freshDecodedRelevantFrames'],'comparisonImages':len(comparisons)}),flush=True)

if __name__=='__main__':main()
