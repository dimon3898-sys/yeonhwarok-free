"""Derive new delivery tables from preserved measurements; never rerun tracking/rendering."""
from pathlib import Path
import json, csv, math, hashlib, shutil
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'auto-director-v3-20261114/reference'
read=lambda p:json.loads(p.read_text())
write=lambda n,x:(HERE/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=read(OLD/'FRAME_MEASUREMENTS.json'); timing=read(OLD/'TIMING_ANALYSIS.json')
assert m['sha256']==timing['sourceSHA256']=='853ce5be22dc95c95e0c4b3eddbd603930e499bc88ee40cb4e59b50aad1187bc'
assert [r['frame'] for r in m['records']]==list(range(635))
focus=['Andorra','transition','Spain / Europe / North Africa','Gibraltar strait / Morocco','Ceuta and Melilla labels','marked North African coastal site; identity UNKNOWN','marked coastal site and 85 m graphic','editor outro; excluded']
motion=['slight reframing then transition','cut / blur','pullback','push-in','slight reframing / reading','deep push-in','slow roll and reframing','NOT_MAP_CAMERA']
details=['colored relief','blur','continental terrain / country outlines','relief and coast beneath fill','coast and relief beneath fill','coastal texture changes with scale; source UNKNOWN','buildings / wave texture visible; source UNKNOWN','no map']
rows=[];profile=[];sheets={};scale=1.;previous_segment=None
for r in m['records']:
 f=r['frame']; j=next(j for j,p in enumerate(timing['phases']) if p['startFrame']<=f<p['endFrameExclusive']); p=timing['phases'][j]
 if previous_segment!=j:scale=1.
 valid=r.get('estimatedMotionValid',False) and f>p['startFrame'] and j not in [1,7]
 if valid:scale*=r['affineScale']
 confidence=('HIGH' if r.get('inlierRatio',0)>=.85 else 'MEDIUM') if valid else 'LOW_OR_NOT_APPLICABLE'
 events=[e['name'] for e in timing['events'] if e['startFrame']<=f<e['endFrameExclusive']]
 if 490<=f<500:events.append('85 m annotation assembling; supplementary estimated onset 490 +/- 6 frames')
 if 500<=f<575:events.append('85 m annotation established; source measurement truth UNKNOWN')
 effect='yellow regional fill / pale edge' if 30<=f<575 else 'opening red/orange/blue region fills' if f<29 else 'none'
 if 205<=f<230:effect+='; cyan reveal'
 elif 230<=f<575:effect+='; cyan region maintained'
 if 459<=f<575:effect+='; sustained yellow local boundary glow; NOT territorial conquest'
 start=f//80*80
 if start not in sheets:sheets[start]=np.asarray(Image.open(OLD/f'ALL_FRAMES_{start:03d}.jpg').convert('HSV'))
 k=f-start;x=(k%8)*113;y=(k//8)*262
 # New apparent-color occupancy proxy from existing thumbnails, not new decoding/tracking.
 roi=sheets[start][y+22:y+137,x+3:x+91].astype(float)
 h=roi[:,:,0]*360/255;s=roi[:,:,1]/255;v=roi[:,:,2]/255
 yellow=(h>=35)&(h<=70)&(s>.45)&(v>.35);cyan=(h>=170)&(h<=205)&(s>.35)&(v>.25)
 occupancy={'yellowMaskFraction':round(float(yellow.mean()),5),'cyanMaskFraction':round(float(cyan.mean()),5)} if f<575 else None
 speed=r.get('estimatedCenterSpeedPixelsPerSecond') if valid else None
 evidence=f'../auto-director-v3-20261114/reference/FRAME_MEASUREMENTS.json#/records/{f}; ../auto-director-v3-20261114/reference/ALL_FRAMES_{start:03d}.jpg cell {k}'
 item={'frame':f,'time_sec':r['ptsSeconds'],'segment_id':f'R{j}','camera_motion':motion[j], 'relative_zoom':round(scale,8) if j not in [1,7] else 'UNKNOWN','motion_speed':speed if speed is not None else 'UNKNOWN','focus_region':focus[j],'map_detail':details[j],'territory_effect':effect,'label_event':'; '.join(events) or ('existing opening label / area value' if f<29 else 'no new label event annotated'),'hold_state':'READING_WITH_DRIFT' if j==4 else 'CLOSE_READ_WITH_ROLL' if j==6 else 'OUTRO' if j==7 else 'MOVING','confidence':confidence,'evidence':evidence,'relative_zoom_basis':'segment-local product of valid pairs ONLY; incomplete if invalid pairs','camera_dx_px':r.get('centerDxPixels') if valid else 'UNKNOWN','camera_dy_px':r.get('centerDyPixels') if valid else 'UNKNOWN','acceleration_px_s2':r.get('estimatedSpeedChangePixelsPerSecondSquared') if valid else 'UNKNOWN','apparent_color_occupancy':json.dumps(occupancy),'target_edge_clearance':'UNKNOWN: no validated object segmentation','value_type':'PTS=MEASURED; camera=ESTIMATED; occupancy=THUMBNAIL_PROXY; semantics=ANNOTATED'}
 rows.append(item)
 profile.append({'frame':f,'ptsSeconds':r['ptsSeconds'],'segmentId':f'R{j}','screenTranslationPixels':[r.get('centerDxPixels'),r.get('centerDyPixels')] if valid else None,'pairScale':r.get('affineScale') if valid else None,'segmentRelativeScaleFromValidPairs':scale if j not in [1,7] else None,'rotationDegrees':r.get('rotationDegrees') if valid else None,'speedPixelsPerSecond':speed,'speedChangePixelsPerSecondSquared':r.get('estimatedSpeedChangePixelsPerSecondSquared') if valid else None,'confidence':confidence,'tracked':r.get('tracked'),'inliers':r.get('inliers'),'inlierRatio':r.get('inlierRatio'),'apparentColorOccupancy':occupancy})
 previous_segment=j
with (HERE/'REFERENCE_FRAME_TIMELINE.csv').open('w',newline='') as out:
 w=csv.DictWriter(out,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
write('REFERENCE_MOTION_PROFILE.json',{'schema':'REFERENCE_SCREEN_MOTION_DERIVED_V1','sourceSHA256':m['sha256'],'sourceMeasurementFile':'../auto-director-v3-20261114/reference/FRAME_MEASUREMENTS.json','sourceMeasurementSHA256':sha(OLD/'FRAME_MEASUREMENTS.json'),'frameIndexing':'zero-based; intervals [start,end)','trueCameraCoordinates':'UNKNOWN','projection':'UNKNOWN; locally fit 2D similarity is not a recovered map projection','trackingROIOriginalPixels':m['trackingROIOriginalPixels'],'phasesReused':timing['phases'],'eventsReused':timing['events'],'limitations':timing['limitations']+['No new optical flow / decode verification. UI exclusion mask inherited; color overlays can influence tracks.','Occupancy uses HSV threshold on preserved 103x240 thumbnails within approximate original tracking ROI. It is not geographic area or full-object occupancy.','First frame of each segment resets scale. Invalid pairs remain null; accumulated scale can be incomplete.','The 48.885 deep-zoom estimate is not a reliable design target.','No exact camera-still verdict is inferred from small motion values.'],'frames':profile})
(HERE/'REFERENCE_EVIDENCE').mkdir(exist_ok=True)
for f in [495,500,574]:
 src=Path('/workspace/scratch/f001bad43575/analysis_tmp')/f'reference_{f:03d}_map.png'
 shutil.copyfile(src,HERE/'REFERENCE_EVIDENCE'/src.name)
write('REFERENCE_EVIDENCE/INDEX.json',{'reusedFrameSheets':[{'path':str(p.relative_to(HERE.parent.parent.parent.parent)),'sha256':sha(p)} for p in sorted(OLD.glob('ALL_FRAMES_*.jpg'))],'newEvidencePurpose':'Only previously missing distance-label detail at 495/500/574. Native-size cropped excerpts [20,170,730,1100]; not fresh motion/media tests.','newEvidence':[{'path':p.name,'sha256':sha(p)} for p in (HERE/'REFERENCE_EVIDENCE').glob('*.png')],'visualReview':'All eight preserved sheets inspected; 635-frame coverage inherited and new requested CSV mapping complete.'})
print(json.dumps({'rows':len(rows),'newTrackingRuns':0,'oldPassReruns':0,'rendererRuns':0,'supplementaryCrops':3}))
