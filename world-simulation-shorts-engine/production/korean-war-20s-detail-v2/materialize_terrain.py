"""Hash-pinned NASA source acquisition and exact native crop, never a renderer."""
import hashlib,json,sys,urllib.request
from pathlib import Path
from PIL import Image

HERE=Path(__file__).resolve().parent
URL='https://assets.science.nasa.gov/content/dam/science/esd/eo/images/bmng/bmng-topography/september/world.topo.200409.3x21600x21600.D1.jpg'
SOURCE_SHA='cecf5427fe6dfaac73cdad11ae44835862e3d8be40093c6b7f6311003eefb944'
SOURCE_BYTES=69967736
BOX=(7200,10560,10800,14400)
sha=lambda b:hashlib.sha256(b).hexdigest()

def main():
    source=Path(sys.argv[1]);destination=HERE/'sources/korea_bmng_500m_native.png'
    if not source.exists():
        source.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(URL,timeout=90) as response,source.open('xb') as out:
            total=0
            while chunk:=response.read(1024*1024):
                total+=len(chunk)
                if total>SOURCE_BYTES:raise RuntimeError('NASA_SOURCE_OVERSIZE')
                out.write(chunk)
    raw=source.read_bytes()
    assert len(raw)==SOURCE_BYTES and sha(raw)==SOURCE_SHA,'NASA_SOURCE_HASH_MISMATCH'
    # This exact NASA 21600-square tile was separately registered from its
    # companion GeoTIFF tags (WGS84, pixel-is-area); do not infer from filename.
    geo=json.loads((HERE/'sources/GEOTIFF_REGISTRATION.json').read_bytes())
    dx,dy,_=geo['pixelScale'];_,_,_,west,north,_=geo['tiePoint']
    Image.MAX_IMAGE_PIXELS=500000000
    with Image.open(source) as im:
        assert im.size==(21600,21600) and im.mode=='RGB'
        crop=im.crop(BOX)
    if not destination.exists():
        with destination.open('xb') as out:crop.save(out,format='PNG',compress_level=6)
    with Image.open(destination) as check:
        assert check.size==crop.size and check.mode=='RGB' and check.tobytes()==crop.tobytes(),'NATIVE_CROP_CHANGED'
    receipt={'schema':'WORLD_ENGINE_EXACT_SOURCE_CROP_V1','sourceURL':URL,'sourceSHA256':SOURCE_SHA,'sourceBytes':SOURCE_BYTES,'sourceDimensions':[21600,21600],
      'sourceEpoch':'2004-09','sourceMeaning':'Modern geographic background; not 1950 imagery, shore survey, military control or reconstructed elevation',
      'pixelBox':list(BOX),'dimensions':list(crop.size),'bounds':[west+BOX[0]*dx,north-BOX[3]*dy,west+BOX[2]*dx,north-BOX[1]*dy],
      'pixelSpacing':[dx,dy],'crs':'EPSG:4326','sha256':sha(destination.read_bytes()),'bytes':destination.stat().st_size,'decodedRGBSHA256':sha(crop.tobytes()),
      'operation':'EXACT_DECODED_JPEG_PIXEL_WINDOW_NO_RESAMPLE_NO_RECOLOR','qualityPass':False,'historicalAccuracyClaimed':False}
    path=HERE/'sources/NATIVE_CROP_RECEIPT.json'
    if path.exists():assert json.loads(path.read_bytes())==receipt,'PINNED_CROP_RECEIPT_CHANGED'
    else:path.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'dimensions':receipt['dimensions'],'bytes':receipt['bytes'],'sha256':receipt['sha256'],'decodedPixelEquality':True}))

if __name__=='__main__':main()
