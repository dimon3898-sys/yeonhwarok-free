"""Independent re-read of compiled geometry, not a rerun of old PASS tests."""
import json,hashlib
from pathlib import Path
from shapely.geometry import shape
base=Path(__file__).parent
raw=(base/'RUNTIME_REQUEST.json').read_bytes();r=json.loads(raw);rows=[]
for e in r['segments'][0]['presentation']['territoryChanges']['items']:
 frames=e['continuous']['frames'];a=shape(frames[0]['geometry']);b=shape(frames[-1]['geometry']);allowed=a.union(b);common=a.intersection(b);prev=None;changes=[]
 for i,row in enumerate(frames):
  g=shape(row['geometry']);band=shape(row['boundaryBand']);tol=max(1e-8,allowed.area*1e-10)
  assert g.is_valid and band.is_valid
  assert g.difference(allowed).area<tol
  assert common.difference(g).area<tol
  assert band.difference(g).area<tol
  assert row['alpha']==1
  if prev is not None:
   difference=g.symmetric_difference(prev).area;assert difference>0;changes.append(difference)
  prev=g
 rows.append({'start':e['startFrame'],'end':e['endFrame'],'frames':len(frames),'uniqueGeometries':len({json.dumps(x['geometry'],sort_keys=True) for x in frames}),'minChangedArea':min(changes),'allValid':True,'allWithinSourceUnion':True,'allBandsInsideCurrent':True,'constantOpacity':True})
(base/'evidence/FRAME_GEOMETRY_GATE.json').write_text(json.dumps({'status':'PASS','runtimeSHA256':hashlib.sha256(raw).hexdigest(),'transitions':rows},indent=2)+'\n');print(rows)
