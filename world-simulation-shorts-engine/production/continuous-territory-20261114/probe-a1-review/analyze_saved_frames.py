"""Inspect newly captured PNGs/telemetry only; no renderer or old model tests."""
import gzip, hashlib, json, math
from pathlib import Path
from PIL import Image, ImageDraw

out = Path(__file__).parent
base = out.parent
src = base / 'probe-a1'
sha = lambda b: hashlib.sha256(b).hexdigest()
wire = gzip.decompress((src / 'FRAME_EVIDENCE.json.gz').read_bytes())
rows = json.loads(wire)['frames']
receipt = json.loads((src / 'CAPTURE_RECEIPT.json').read_text())
assert sha(wire) == receipt['frameEvidence']['sha256']
assert receipt['softwareOnly'] and not receipt['paidExecuted']
assert receipt['browserErrors'] == [] and 'SwiftShader' in receipt['runtime']['backend']
assert receipt['renderedFrames'] == len(rows) == 34
assert not list(src.glob('*.mp4'))
for row in rows:
    raw = (src / f"FRAME_{row['frame']:03}.png").read_bytes()
    assert sha(raw) == row['pngSHA256']
    with Image.open(src / f"FRAME_{row['frame']:03}.png") as im:
        assert im.size == (1080, 1920)
    assert row['diagnostic']['glError'] == 0
consecutive = [r for r in rows if 56 <= r['frame'] <= 85]
assert [r['frame'] for r in consecutive] == list(range(56, 86))
merc = lambda lat: 180 / math.pi * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
summary = []
for row in consecutive:
    d = row['diagnostic']
    area = next(f for f in d['features'] if f.get('continuousEvidence'))
    assert area['continuousEvidence']['active']
    assert len(area['sourceAreas']) == 1 and area['sourceAreas'][0]['alpha'] == 1
    assert any(a['drawn'] for dr in area['draws'] for a in dr['draw']['areas'])
    front = next(f for f in d['features'] if f['id'] == 'TERRITORY_DIFFERENCES_V2')
    boundary = next(a for dr in front['draws'] for a in dr['draw']['areas'] if a['id'] == 'MOVING_BOUNDARY')
    assert boundary['drawn'] and boundary['alpha'] > 0
    g = area['sourceAreas'][0]['geometry']
    parts = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    crossings = []
    latitude = 45
    for poly in parts:
        for ring in poly:
            for a, b in zip(ring, ring[1:]):
                if a[1] <= latitude < b[1] or b[1] <= latitude < a[1]:
                    crossings.append(a[0] + (latitude-a[1])*(b[0]-a[0])/(b[1]-a[1]))
    longitude = min(crossings)
    pose = d['camera']['actualFactory']['pose']
    assert pose['rollDegrees'] == 0
    x = 540 + (longitude-pose['center'][0])*pose['scale']
    y = 960 - (merc(latitude)-merc(pose['center'][1]))*pose['scale']
    im = Image.open(src / f"FRAME_{row['frame']:03}.png").convert('RGB')
    candidates = []
    for px in range(round(x)-8, round(x)+9):
        rr, gg, bb = im.getpixel((px, round(y)))
        if rr >= 220 and gg >= 180 and bb < 130:
            candidates.append(px)
    assert candidates, f"Missing amber boundary at frame {row['frame']}"
    actual_x = min(candidates, key=lambda px: abs(px-x))
    measured_lon = pose['center'][0] + (actual_x-540)/pose['scale']
    summary.append({'frame':row['frame'], 'pngSHA256':row['pngSHA256'],
        'geometrySHA256':sha(json.dumps(g,sort_keys=True,separators=(',',':')).encode()),
        'constantAreaAlpha':area['sourceAreas'][0]['alpha'],
        'featureChangedPixels':d['featureChangedPixels'],
        'cameraPose':pose, 'boundaryDrawn':boundary['drawn'],
        'boundaryAlpha':boundary['alpha'], 'scanLatitude':latitude,
        'expectedBoundaryLongitude':longitude, 'observedBoundaryLongitude':measured_lon,
        'observedPixel':[actual_x,round(y)], 'expectedPixel':[x,y],
        'pixelOffset':abs(actual_x-x)})
unique = lambda key: len({json.dumps(r[key],sort_keys=True) for r in summary})
assert unique('geometrySHA256') == unique('cameraPose') == unique('pngSHA256') == 30
assert max(r['pixelOffset'] for r in summary) < 2
assert all(b['observedBoundaryLongitude'] < a['observedBoundaryLongitude'] for a,b in zip(summary,summary[1:]))
assert min(r['featureChangedPixels'] for r in summary) > 0
result = {'status':'SAVED_30_FRAME_PIXEL_AND_TELEMETRY_CHECKS_PASS',
    'captureCommit':'b54f6114d6c943b1208f2e3e4f5a49e4291ec3b3',
    'evidenceCommit':'6604a86c3281a3a84ce96886267757a7ad5e0856',
    'runId':43526265587, 'runtimeSHA256':sha((base/'RUNTIME_REQUEST.json').read_bytes()),
    'capturedFrames':34, 'consecutiveFrames':30, 'frameRangeInclusive':[56,85],
    'sampleDurationAt30fpsSeconds':1, 'firstToLastTimestampSpanSeconds':29/30,
    'uniqueGeometries':unique('geometrySHA256'), 'uniquePNGHashes':unique('pngSHA256'),
    'uniqueActualCameraPoses':unique('cameraPose'), 'allAreaAlphasOne':True,
    'movingBoundaryDrawnFrames':30, 'allPNGsAndUncompressedLedgerMatchCaptureHashes':True,
    'actualPixelScan':{'latitude':45,'rule':'R >= 220, G >= 180, B < 130 within 8px of supplied boundary; closest qualifying pixel',
        'cameraCompensation':'actual Mercator pose: longitude = center.x + (pixel.x - 540) / scale',
        'longitudeFirst':summary[0]['observedBoundaryLongitude'],
        'longitudeLast':summary[-1]['observedBoundaryLongitude'],
        'westwardDegrees':summary[0]['observedBoundaryLongitude']-summary[-1]['observedBoundaryLongitude'],
        'maxAlignmentErrorPixels':max(r['pixelOffset'] for r in summary),
        'strictlyWestwardAtAll29Steps':True,
        'limitation':'One latitude samples the western front; it does not prove every coastline pixel or historical conquest route.'},
    'fullVideoQualityPass':False, 'referenceParity':'NOT_PROVEN', 'gpuStarts':0,
    'oldPassReruns':0, 'rendererRunsByThisScript':0, 'rows':summary}
(out/'PIXEL_AND_MOTION_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
reference = summary[0]['cameraPose']
frames = [56,70,85]
crop = (90,570,370,970)
sheet = Image.new('RGB',(840,430),(15,20,28));draw = ImageDraw.Draw(sheet)
for i,frame in enumerate(frames):
    pose = next(r for r in summary if r['frame']==frame)['cameraPose']
    ratio = pose['scale']/reference['scale']
    tx = 540*(1-ratio)+(reference['center'][0]-pose['center'][0])*pose['scale']
    ty = 960*(1-ratio)-(merc(reference['center'][1])-merc(pose['center'][1]))*pose['scale']
    im=Image.open(src/f'FRAME_{frame:03}.png').convert('RGB')
    im=im.transform((1080,1920),Image.Transform.AFFINE,(ratio,0,tx,0,ratio,ty),Image.Resampling.BICUBIC)
    sheet.paste(im.crop(crop),(i*280,30))
    draw.text((i*280+10,9),f'FRAME {frame} | fixed geography',fill='white')
sheet.save(out/'CAMERA_COMPENSATED_FRONT.jpg',quality=92)
print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
