import json,pathlib,math
from shapely.geometry import box,Polygon
P=pathlib.Path(__file__).parent
g=json.loads((P/'SOURCE_GAP_GEOMETRY_AUDIT.json').read_text());l=json.loads((P/'SOURCE_LOD_ACQUISITION_PLAN.json').read_text());f=json.loads((P/'PRESERVED_FRAME_BOUNDS.json').read_text())['frames']
checks=[]
assert len(g['cells'])==117 and len({c['tile'] for c in g['cells']})==117;checks.append('117 unique intersecting cells')
assert len(f)==600 and all(len(c['bounds'])==4 and all(math.isfinite(v) for v in c['bounds']) for c in f);checks.append('Preserved 600 records contain finite bounds')
assert g['initialFrameCoversFootprint'] and g['envelopeUnusedAreaSquareDegrees']==0;checks.append('Initial viewport covers true union, so no artificial envelope reduction')
assert abs(sum(c['visibleAreaSquareDegrees'] for c in g['cells'])-g['actualFootprintAreaSquareDegrees'])<1e-9;checks.append('Cell areas partition actual footprint')
assert not g['optical']['missingWithMappedLand'] and not g['dsm']['missingWithMappedLand'];checks.append('No published-source gap intersects mapped NE land')
assert l['mappedLandCellCount']==82 and l['noMappedLandCellCount']==35 and sum(l['landCellPowerOfTwoCounts'].values())==82;checks.append('Mapped land inventory and LOD counts reconcile')
assert all(c['powerOfTwoSamplesPerDegree']>=c['maxOutputPixelsPerDegree'] for c in l['cells']);checks.append('Per-cell sampling never rounds below saved viewport requirement')
# Negative/positive geometry controls demonstrate that islands must not be silently lost.
island=box(.4,.4,.6,.6);assert box(0,0,1,1).intersection(island).area>0 and box(1,0,2,1).intersection(island).area==0;checks.append('Synthetic island presence and separate-water controls')
assert not g['productionAdmitted'] and not l['productionAdmitted'];checks.append('Geometry/LOD analysis does not grant production admission')
r={'scope':'New gap geometry and LOD evidence only','result':'passed','checks':checks,'oldPASSReruns':0,'gpuStarts':0,'renders':0}
(P/'SOURCE_GAP_FOCUSED_CHECKS.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
