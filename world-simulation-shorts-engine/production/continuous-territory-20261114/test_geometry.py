import sys,json,importlib.util,hashlib
from pathlib import Path
from shapely.geometry import box,Polygon,MultiPolygon,shape,mapping
from shapely.ops import unary_union
root=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('continuous',root/'recovery/universal-presentation-v2/continuous_territory.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
out=Path(__file__).parent/'evidence'
r=box(10,10,14,14);big=box(8,8,18,18)
hole=Polygon([(8,8),(18,8),(18,18),(8,18)],holes=[[(11,11),(13,11),(13,13),(11,13)]])
separate=MultiPolygon([box(8,10,11,14),box(13,10,18,14)])
cases=[('expansion',r,big),('contraction',big,r),('split',box(8,10,18,14),separate),('merge',separate,box(8,10,18,14)),('multi_region',MultiPolygon([r,box(25,10,28,14)]),MultiPolygon([big,box(23,8,30,17)])),('detached',r,MultiPolygon([r,box(25,10,28,14)])),('holes',hole,Polygon([(7,7),(20,7),(20,20),(7,20)],holes=[[(11,11),(13,11),(13,13),(11,13)]])),('hole_created',big,hole),('hole_removed',hole,big),('unchanged',r,r),('tiny_change',r,box(10,10,14.00001,14)),('mixed',r,box(12,8,18,13)),('empty_start',MultiPolygon([]),r),('empty_end',r,MultiPolygon([]))]
rows=[]
for name,a,b in cases:
 result=mod.compile_transition(mapping(a),mapping(b),30)
 tol=max(1e-8,a.union(b).area*1e-10)
 assert result['frames'][0]['geometry']==mapping(a)
 assert result['frames'][-1]['geometry']==mapping(b)
 previous=None;changes=[]
 for row in result['frames']:
  g=shape(row['geometry']);band=shape(row['boundaryBand'])
  assert g.is_valid and band.is_valid
  assert g.difference(a.union(b)).area<tol
  assert a.intersection(b).difference(g).area<tol
  assert band.difference(g).area<tol
  assert row['alpha']==1
  if previous is not None:changes.append(g.symmetric_difference(previous).area)
  previous=g
 if name!='unchanged':assert all(v>0 for v in changes),(name,changes)
 else:assert all(v==0 for v in changes)
 rows.append({'name':name,'status':'PASS','frames':30,'changedIntervals':sum(v>0 for v in changes),'minChangedArea':min(changes),'detachedAddedComponents':result['detachedAddedComponents'],'maxOutside':result['maxOutsideSourceUnion']})
 print(name,'PASS',flush=True)
(out/'GEOMETRY_TESTS.json').write_text(json.dumps({'status':'PASS','scope':'new continuous geometry only','oldPassReruns':0,'cases':rows},indent=2)+'\n')
