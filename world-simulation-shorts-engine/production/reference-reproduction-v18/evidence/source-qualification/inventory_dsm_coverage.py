"""Inventory published DSM cells; never treat missing tiles as zero elevation."""
import datetime, hashlib, json, math, pathlib, urllib.request
BASE = 'https://copernicus-dem-30m.s3.amazonaws.com/'
BOUNDS = [123.27404215372272, 32.2, 131.72595784627728, 44.2]
HEAD = '5d56a86c218b74e0f0b37eb8d87d10b70235881f'
def inventory(raw):
    published = set(raw.decode('utf-8-sig').splitlines())
    cells = []
    for lat in range(math.floor(BOUNDS[1]), math.ceil(BOUNDS[3])):
        for lon in range(math.floor(BOUNDS[0]), math.ceil(BOUNDS[2])):
            name = f'Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM'
            available = name in published
            cells.append({'latitude':lat,'longitude':lon,'tile':name,
              'inventoryStatus':'PUBLISHED' if available else 'ABSENT_REQUIRES_LAND_OCEAN_CLASSIFICATION',
              'url':BASE + name + '/' + name + '.tif' if available else None,
              'qualificationStatus':'PRIOR_SINGLE_TILE_RECEIPT_PRESERVED' if (lat,lon)==(37,126) else 'NOT_ACQUIRED_OR_QUALIFIED_THIS_WORK'})
    return {'schema':'WORLD_ENGINE_DSM_COVERAGE_INVENTORY_V1',
      'status':'INVENTORY_ONLY_NOT_SOURCE_ADMISSION','baseCommit':HEAD,
      'sourceIndexUrl':BASE+'tileList.txt','sourceIndexSha256':hashlib.sha256(raw).hexdigest(),
      'cameraBounds':BOUNDS,'boundsSource':'production/reference-reproduction-v18/evidence/source-qualification/SURFACE_CANDIDATE_REVIEW.json',
      'cellSelection':'One-degree nominal footprints intersecting the preserved camera envelope; not a per-frame LOD or coastline classification.',
      'cellCount':len(cells),'publishedCellCount':sum(c['inventoryStatus']=='PUBLISHED' for c in cells),
      'absentCellCount':sum(c['inventoryStatus']!='PUBLISHED' for c in cells),
      'priorQualifiedTileCount':1,'newRasterDownloads':0,'newRasterQualification':False,
      'fullTimelineAdmitted':False,'missingTileZeroFillAllowed':False,
      'nextStep':'Classify absent cells with an authoritative land mask; acquire and qualify necessary land tiles, resolution/LOD and border alignment before Studio binding.',
      'caveat':'Public inventory presence does not establish raster validity, completeness, historical fidelity, or acceptable zoom resolution. GLO30 is modern DSM, not 1950 terrain.',
      'cells':cells}
if __name__ == '__main__':
    root=pathlib.Path(__file__).parent
    with urllib.request.urlopen(BASE+'tileList.txt',timeout=30) as r: raw=r.read()
    (root/'copernicus_tileList.txt').write_bytes(raw)
    result=inventory(raw)
    result['retrievedUtc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (root/'DSM_COVERAGE_INVENTORY.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cells'},indent=2))
