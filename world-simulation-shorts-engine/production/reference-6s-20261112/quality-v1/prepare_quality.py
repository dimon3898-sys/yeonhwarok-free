"""Reuse measured V10 anchors; correct only temporal interpolation and boundary presentation."""
import hashlib,json,math,subprocess
from pathlib import Path
import numpy as np
from scipy.interpolate import PchipInterpolator,CubicHermiteSpline
P=Path(__file__).resolve().parent; old=json.loads((P.parent/'REFERENCE_6S_REGISTERED_INPUT.json').read_text());new=json.loads(json.dumps(old));v10=json.loads((P.parent/'inputs/REFERENCE_5S_CAMERA_BRIDGE_V10.json').read_text())
poses=old['presentation']['camera']['frames']; keys=[x['frame'] for x in v10['frames'] if x['method']=='MEASURED_ENDPOINT'];assert keys[-1]==149
merc=lambda t:math.degrees(math.log(math.tan(math.pi/4+math.radians(t)/2)))
inv=lambda t:math.degrees(2*math.atan(math.exp(math.radians(t)))-math.pi/2)
y=np.array([[p['center'][0],merc(p['center'][1]),math.log(p['scale']),p['rollDegrees']] for p in poses[:150]])
support=sorted(set(keys+[6,24,36,54,66,84,126,135,144]));x=np.array(support);values=y[x];pchip=PchipInterpolator(x,values);vel=pchip.derivative()(x);vel[-1]=0
curve=CubicHermiteSpline(x,values,vel);smooth=curve(np.arange(150))
frames=[{'center':[float(v[0]),inv(float(v[1]))],'scale':math.exp(float(v[2])),'rollDegrees':float(v[3])} for v in smooth]
for f in keys:frames[f]=poses[f] # preserve exact source key poses, not just float equivalence
frames+= [poses[149]]*30
new['presentation']['camera']['frames']=frames
new['presentation']['mapStyle']['boundaryTrace']={'preset':'BOUNDARY_TRACE','countryIds':['COUNTRY_ESP','COUNTRY_PRT','COUNTRY_FRA','COUNTRY_MAR','COUNTRY_DZA','COUNTRY_TUN','COUNTRY_MRT'],'startFrame':0,'endFrame':54,'startVertex':'NORTHMOST','direction':'FORWARD'}
# Endpoint output, source facts, palette, pins, labels, timing are unchanged.
check=json.loads(json.dumps(new));check['presentation']['camera']=old['presentation']['camera'];del check['presentation']['mapStyle']['boundaryTrace'];assert check==old
assert frames[149:]==poses[149:]
def dump(name,value):(P/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
dump('REFERENCE_6S_QUALITY_INPUT.json',new)
# The stored native frame samples are a piecewise path. Quantify the log-zoom slope breaks at measured anchors.
before=np.diff(y,axis=0);after=np.diff(smooth,axis=0)
junctions=[k for k in keys[1:-1]]
metric=lambda d:np.array([abs(d[k,2]-d[k-1,2]) for k in junctions])
b,a=metric(before),metric(after)
# Screen displacement compares the same world points; this bounds composition drift at the sampled anchors/scene.
points=[[-5.30675127,35.88810209],[-2.93680807082062,35.2922515360894],[-3.7,40],[0,36]]
def project(p,q):
 dx=q[0]-p['center'][0];dy=-merc(q[1])+merc(p['center'][1]);t=math.radians(p['rollDegrees']);return np.array([540+p['scale']*(math.cos(t)*dx-math.sin(t)*dy),960+p['scale']*(math.sin(t)*dx+math.cos(t)*dy)])
drift=[max(np.linalg.norm(project(poses[f],q)-project(frames[f],q)) for q in points) for f in range(150)]
report={'status':'MEASURED_INPUT_TIMING_DEFECT_CORRECTED_CPU_DRAW_PENDING','source':'Existing V10 measured anchors, exact registered poses reused; no new reference optical-flow fit','sourceAnchors':keys,'trajectorySupportFrames':[f for f in support if f not in keys],'cause':'Piecewise per-frame path has derivative discontinuities at measured-anchor boundaries, including every3frames90..120; final linear segment stops abruptly at149','correction':'Shape-preserving C1 cubic Hermite of projected center, log scale and roll, exact measured poses retained; zero final derivative before hold','junctionLogZoomJumpBefore':b.tolist(),'junctionLogZoomJumpAfter':a.tolist(),'junctionJumpRmsBefore':float(np.sqrt(np.mean(b*b))),'junctionJumpRmsAfter':float(np.sqrt(np.mean(a*a))),'maximumMeasuredLandmarkDriftPx':float(max(drift)),'maxDriftFrame':int(np.argmax(drift)),'measuredKeyframeDriftPx':0,'finalPoseUnchanged':True,'last30FramesUnchanged':True,'pixelRoundingInCameraPath':False,'referenceTimingCaveat':'4..9s already contains complete borders. Requested tracing is an authored0..54frame presentation adaptation of the preceding reference buildup; original onset/direction within4..9s cannot be claimed. Each native ring starts at its northernmost existing vertex and follows source winding.','oldPassSuitesRerun':0,'GPUExecutions':0}
dump('CAMERA_DELTA.json',report);print(json.dumps({k:v for k,v in report.items() if k in ['junctionJumpRmsBefore','junctionJumpRmsAfter','maximumMeasuredLandmarkDriftPx','maxDriftFrame']}))
