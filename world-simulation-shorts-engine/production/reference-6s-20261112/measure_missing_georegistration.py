from PIL import Image,ImageDraw
import numpy as np,json,math
from scipy.optimize import differential_evolution
from pathlib import Path
import argparse
args=argparse.ArgumentParser()
args.add_argument('--frame0',required=True)
args.add_argument('--output',required=True)
cli=args.parse_args()
root=Path(__file__).resolve().parents[3]
outdir=Path(cli.output);outdir.mkdir(parents=True,exist_ok=False)
f=next(x for x in json.loads((root/'cinematic-world-map/assets/gis/countries_50m.geojson').read_text())['features'] if x['properties']['ADM0_A3']=='ESP')
ring=np.array(max(f['geometry']['coordinates'],key=lambda p:len(p[0]))[0])
img=Image.open(cli.frame0).convert('RGB'); rgb=np.asarray(img)
# Only new missing absolute registration. Raw source polygons are never rewritten.
x0,y0,x1,y1=145,610,365,770
r=rgb[y0:y1,x0:x1].astype(float)
obs=(r[:,:,0]>150)&(r[:,:,1]>120)&(r[:,:,2]<110)&(r[:,:,0]>r[:,:,2]*1.5)
origin=[-3,40];q=(ring-origin)*[math.cos(math.radians(38)), -1]

def projected(params):
    scale,theta,dx,dy=params;a=math.radians(theta); rot=np.array([[math.cos(a),-math.sin(a)],[math.sin(a),math.cos(a)]])
    return q@rot.T*scale+[dx,dy]
def score(params):
    pts=projected(params)-[x0,y0];im=Image.new('1',(x1-x0,y1-y0));ImageDraw.Draw(im).polygon([tuple(x) for x in pts],fill=1)
    mask=np.asarray(im); inter=(mask&obs).sum(); union=(mask|obs).sum()
    return 1-inter/max(1,union)
fit=differential_evolution(score,[(14,24),(-18,10),(225,275),(670,710)],seed=17,popsize=18,maxiter=220,tol=1e-7,polish=False)
p=fit.x;out={'status':'APPROXIMATE_FIRST_FRAME_REGISTRATION_ONLY','method':'Spain mainland unchanged Natural Earth 50m polygon fitted against observed yellow-mask silhouette','parameters':{'pixelsPerProjectedDegree':p[0],'rollDegrees':p[1],'originGeographic':origin,'standardParallelDegrees':38,'originPixel':[p[2],p[3]]},'maskIoU':1-fit.fun,'sourceROI':[x0,y0,x1,y1],'limits':['One country silhouette; not whole-view geodetic accuracy','Regional projection approximation','No camera or source admission inferred','Phone UI excluded from measurement','Prior V10 relative transform unchanged']}
print(json.dumps(out,indent=2));(outdir/'calibration_fit.json').write_text(json.dumps(out,indent=2)+'\n')
d=ImageDraw.Draw(img);d.line([tuple(x) for x in projected(p)],fill='red',width=2);img.save(outdir/'calibration_overlay.png')
