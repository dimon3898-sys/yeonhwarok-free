#!/usr/bin/env python3
"""Bind recovered visual intent to the repository's actual, licensed GIS bytes.

No reference analysis is rerun. The low-resolution, unqualified polygons are
replaced by exact matching country features from the pinned native GIS source.
Camera keys remain the user's candidate and require full-envelope admission.
"""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ENGINE = REPO / 'world-simulation-shorts-engine'
def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(value):
 # Use the consumer's JS number serialization (38.0 -> 38, exponent rules).
 return subprocess.check_output(['node', '-e', "const fs=require('fs');const c=x=>Array.isArray(x)?'['+x.map(c).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+c(x[k])).join(',')+'}':JSON.stringify(x);process.stdout.write(c(JSON.parse(fs.readFileSync(0,'utf8'))));"],input=json.dumps(value),text=True)
def write(path, value): path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

catalog = json.loads((ENGINE/'recovery/universal-presentation-v2/REGION_SOURCE_CATALOG.json').read_text())
gis = catalog['gis']; raw = (REPO/gis['file']).read_bytes()
assert sha(raw) == gis['sha256']
assert sha((REPO/gis['licenseFile']).read_bytes()) == gis['licenseSHA256']
features = {f['properties']['ADM0_A3']: f for f in json.loads(raw)['features']}
x = json.loads((HERE/'inputs/REFERENCE_6S_HOLD_BOUNDARY_CORRECTED.json').read_text())
facts = x['data']['scenes'][0]['facts']
source_id = 'NATURAL_EARTH_50M_REPOSITORY'
source_ref = gis['file'] + '#sha256=' + gis['sha256']
facts['source_notes'] = [{'id': source_id, 'source_type': 'GEOGRAPHIC_CONTEXT', 'verification_status': 'VERIFIED',
 'source_reference': source_ref, 'sha256': gis['sha256'], 'license': gis['license'], 'crs': 'EPSG:4326',
 'verification_basis': 'Exact country feature extraction from hash-pinned repository GIS and license bytes; modern geographic context only, no sovereignty or historical control claim.'}]
mapping = {'NE_LOWRES_SPAIN':'ESP','NE_LOWRES_MOROCCO':'MAR','NE_LOWRES_PORTUGAL':'PRT',
 'NE_LOWRES_ALGERIA':'DZA','NE_LOWRES_FRANCE':'FRA','NE_LOWRES_TUNISIA':'TUN','NE_LOWRES_MAURITANIA':'MRT'}
for g in facts['geometries']:
 g['source_id'] = source_id
 g['geometry'] = features[mapping[g['id']]]['geometry']
 # Keep stable IDs from the supplied contract; the provenance records 50m bytes.
facts['stages'] = []
facts['region_layers'] = [
 {'id':'IBERIA_YELLOW','geometry_ref':'NE_LOWRES_SPAIN','start_frame':0,'reveal_frames':1},
 {'id':'MOROCCO_CYAN','geometry_ref':'NE_LOWRES_MOROCCO','start_frame':89,'reveal_frames':31}]
facts['scene_timing'].update(initial_reveal_frames=1,state_transition_frames=0)
# Secondary context framing is not consumed; the geographic layers and all
# country/coordinate bindings remain explicit and qualified by region_source.
facts['native_context']['secondary_country_ids'] = []
x['data']['topic'] = 'Iberia and North Africa geographic map'
x['prompt'] = 'Iberia and North Africa geographic map, 6 seconds at 30fps.'
x['presentation']['initialStateVisibility'] = 'REVEAL'
x['presentation']['mapStyle']['nativeBoundaries'] = True
record_id = 'REF6_GEOGRAPHIC_CONTEXT_20261113'
claim = 'STATIC_MODERN_GEOGRAPHY_ONLY'
x['data']['scenes'][0]['historicalEvidence'] = [{'recordId':record_id,'sourceId':source_id,'claimId':claim,
 'geometryIds':[g['id'] for g in facts['geometries']],'stageIds':[]}]
record = {'id':record_id,'sourceId':source_id,'claimId':claim,'reviewStatus':'VERIFIED',
 'sourceSHA256':gis['sha256'],'sourceReference':source_ref,'canonicalFactsSHA256':sha(canonical(facts).encode()),
 'geometrySHA256ById':{g['id']:sha(canonical(g['geometry']).encode()) for g in facts['geometries']},
 'scope':'GEOGRAPHIC_CONTEXT','historicalOwnershipAllowed':False,'geometryMeaning':'UNCHANGED_MODERN_LAND_CONTEXT',
 'reviewEvidence':{'sourceFile':gis['file'],'licenseFile':gis['licenseFile'],'licenseSHA256':gis['licenseSHA256'],
 'featureIds':mapping,'extraction':'EXACT_GEOJSON_GEOMETRY_NO_SIMPLIFICATION',
 'displayTimingBasis':'Recovered V9: Spain visible at 0; cyan first visible at 90 and dominant at 120. Transition 89..119 is an authored interpolation, not 150 independent measurements.',
 'cameraApproval':'PENDING_ABSOLUTE_REGISTRATION_AND_FULL_ENVELOPE'}}
write(HERE/'REFERENCE_6S_GEOGRAPHIC_INPUT.json',x)
dst=ENGINE/'recovery/universal-data-pipeline-v1/evidence/REVIEWED_GEOGRAPHIC_CONTEXT.json'
write(dst,{'schema':'WORLD_ENGINE_REVIEWED_GEOGRAPHIC_CONTEXT_V1','records':[record]})
digest=sha(dst.read_bytes())
(ENGINE/'recovery/universal-data-pipeline-v1/reviewed_geographic_registry.mjs').write_text(
 "// Server-owned exact dataset binding. Modern geometry only; no historical control.\n"
 "import fs from 'node:fs';\nimport {createHash} from 'node:crypto';\n"
 "const raw=fs.readFileSync(new URL('./evidence/REVIEWED_GEOGRAPHIC_CONTEXT.json',import.meta.url));\n"
 f"if(createHash('sha256').update(raw).digest('hex')!=='{digest}')throw Error('EVIDENCE_GEOGRAPHIC_REGISTRY_MISMATCH');\n"
 "export function reviewedGeographicRecords(){return structuredClone(JSON.parse(raw).records);}\n")
print(json.dumps({'input':str(HERE/'REFERENCE_6S_GEOGRAPHIC_INPUT.json'),'sourceSHA256':gis['sha256'],
 'registrySHA256':digest,'formalCompile':'NOT_RUN','oldPassReruns':0}))
