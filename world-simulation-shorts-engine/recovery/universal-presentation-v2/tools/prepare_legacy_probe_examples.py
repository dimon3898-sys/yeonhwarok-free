"""Add source-backed legacy provider probes; no old assets or caches are written."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
OLD = HERE.parent / 'universal-data-pipeline-v1'
CITY = REPO / 'world-simulation-shorts-engine/recovery/verified-front-data-v4-recovery/sources/populated_places_source.geojson'
CITY_SHA = 'fd3fa867a320cbd5c5b6bb5bc550afeec2939fb2cef688e508007282a55ac42f'
ARCHIVE = HERE.parent / 'g2-final-recovery-v1/fixtures/GENERIC_REGION_INPUTS.zip'
ARCHIVE_SHA = '29806402e97db3a97cb4f3b95d6851d9bca62810ccbfb29199592ad49b9dd22b'
sha = lambda raw: hashlib.sha256(raw).hexdigest()
canonical = lambda obj: json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def write(relative, value):
    target = HERE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError('REFUSE_DIFFERENT_PROBE: ' + relative)
    else:
        with target.open('xb') as stream:
            stream.write(raw)
    return {'path': relative, 'sha256': sha(raw)}


if sha(CITY.read_bytes()) != CITY_SHA or sha(ARCHIVE.read_bytes()) != ARCHIVE_SHA:
    raise ValueError('PRESERVED_SOURCE_SHA_MISMATCH')
cities = json.loads(CITY.read_bytes())['features']
claims = []


def city(name, country, identifier, country_id):
    rows = [x for x in cities if x['properties'].get('name') == name and x['properties'].get('adm0name') == country]
    if len(rows) != 1:
        raise ValueError('UNIQUE_SOURCE_CITY_REQUIRED: ' + name)
    item = rows[0]
    claims.append({'id': identifier, 'sourceName': name, 'sourceCountry': country,
                   'ne_id': item['properties']['ne_id'], 'coordinates': item['geometry']['coordinates'],
                   'featureCanonicalSHA256': sha(canonical(item)),
                   'scope': 'MODERN_LOCALITY_ONLY_NO_HISTORICAL_TROOP_OR_REAL_TRANSPORT_CLAIM'})
    return {'id': identifier, 'label': identifier, 'anchor': item['geometry']['coordinates'], 'country_id': country_id}


legacy = json.loads((HERE / 'examples/LEGACY_FIVE_REGION_MATRIX.json').read_bytes())['cases']
catalog = {x['legacySourceRegionId']: x for x in legacy}
with zipfile.ZipFile(ARCHIVE) as archive:
    native = json.loads(archive.read('europe_germany/RECOVERY_RUNTIME.json'))['nativePlan']['geometries']
    by_id = {x['id']: x for x in native}
new_regions = {
    'nepal_himalaya': ('COUNTRY_NPL', 'Nepal', [city('Kathmandu', 'Nepal', 'KATHMANDU', 'COUNTRY_NPL'),
                                             city('Pokhara', 'Nepal', 'POKHARA', 'COUNTRY_NPL')]),
    'korean_peninsula': ('COUNTRY_KOR', 'Korea modern locality connection',
                         [city('Seoul', 'South Korea', 'SEOUL', 'COUNTRY_KOR'),
                          city('Daejeon', 'South Korea', 'DAEJEON', 'COUNTRY_KOR')]),
}
reuse = {'europe_germany': 'AVIATION_EUROPE_NL', 'south_america_chile': 'TRADE_SOUTH_AMERICA_NL',
         'namibia_desert_coast': 'FICTIONAL_AFRICA_NL'}
rows = []
for alias in ['europe_germany', 'south_america_chile', 'namibia_desert_coast', 'korean_peninsula', 'nepal_himalaya']:
    old = catalog[alias]
    center = old['originalCameraAnchor']
    if alias in reuse:
        value = json.loads((HERE / 'examples' / (reuse[alias] + '.json')).read_bytes())
        data = deepcopy(value['data'])
        data['durationSeconds'] = 3
        data['scenes'] = [data['scenes'][0]]
        country_id = value['region']['countryId']
    else:
        country_id, subject, locations = new_regions[alias]
        data = json.loads((OLD / 'examples/AVIATION_GERMANY.json').read_bytes())
        data.pop('renderSettings', None)
        data['topic'] = subject + ' transport route'
        row = data['scenes'][0]
        row.pop('renderSettings', None)
        facts = row['facts']
        facts['subject'] = {'id': country_id + '_ILLUSTRATIVE', 'label': subject,
                            'aliases': [subject], 'event_family': 'TRANSPORT'}
        facts['locations'] = locations
        facts['native_context'] = {'country_ids': [country_id], 'primary_country_id': country_id,
                                   'secondary_country_ids': [], 'context_location_ids': [x['id'] for x in locations]}
        geometry = by_id[country_id]
        facts['geometries'] = [
            {'id': country_id, 'source_id': 'SUPPLIED_FIXTURE',
             'geometry': {'type': geometry['geometry_type'], 'coordinates': geometry['coordinates']}},
            {'id': 'DECLARED_CONNECTION', 'source_id': 'SUPPLIED_FIXTURE',
             'geometry': {'type': 'LineString', 'coordinates': [x['anchor'] for x in locations]}},
        ]
        facts['camera'] = {'anchor': center, 'target_geometry_refs': [country_id, 'DECLARED_CONNECTION'],
                           'minimum_context_geometry_refs': [country_id], 'detail_policy': 'FACT_BASED_VISUAL_GRADE'}
        facts['source_notes'][0]['source_reference'] = 'Declared technical connection; exact frozen city proof: evidence/LEGACY_PROBE_COORDINATE_PROOF.json'
        facts['source_notes'][0]['note'] = ('Author-defined nonhistorical city connection and playback dates. '
                                           'Not a flight schedule, navigable route, troop position or control claim.')
    row = data['scenes'][0]
    row['sceneId'] = 'legacy-probe-' + alias
    row['startFrame'], row['endFrame'] = 0, 90
    row['facts'].pop('scene_timing', None)
    location_id = row['facts']['locations'][0]['id']
    value = {'schema': 'WORLD_ENGINE_PRESENTATION_PROMPT_V2',
             'prompt': ('Show only the supplied nonhistorical data for 3 seconds. '
                        'Move the camera, zoom out then zoom in, and highlight the supplied location.'),
             'data': data,
             'region': {'center': center, 'bbox': old['originalClosestBounds'], 'countryId': country_id,
                        'sourceId': 'AUTO', 'crs': 'EPSG:4326'},
             'presentation': {'camera': {'mode': 'KEYFRAMES', 'keyframes': [
                 {'frame': 0, 'center': [center[0] - .05, center[1]], 'zoom': .97},
                 {'frame': 44, 'center': [center[0] + .05, center[1] + .03], 'zoom': .95},
                 {'frame': 89, 'center': center, 'zoom': 1}]},
                 'highlights': [{'id': 'legacy-focus', 'locationId': location_id, 'startFrame': 12, 'endFrame': 28}]}}
    name = 'examples/legacy-probes/' + alias + '.json'
    info = write(name, value)
    rows.append({'legacyProfileId': alias, **info, 'expectedCompilerStatus': 'PASS',
                 'runtimeRegionOverride': {'legacyProfileId': alias},
                 'runtimePresentationOverride': {'camera': {'mode': 'KEYFRAMES', 'keyframes': [
                     {'frame': 0, 'center': [(old['originalClosestBounds'][0] + old['originalClosestBounds'][2]) / 2 - .05,
                                              (old['originalClosestBounds'][1] + old['originalClosestBounds'][3]) / 2], 'zoom': .97},
                     {'frame': 44, 'center': [(old['originalClosestBounds'][0] + old['originalClosestBounds'][2]) / 2 + .05,
                                               (old['originalClosestBounds'][1] + old['originalClosestBounds'][3]) / 2 + .03], 'zoom': .95},
                     {'frame': 89, 'center': [(old['originalClosestBounds'][0] + old['originalClosestBounds'][2]) / 2,
                                               (old['originalClosestBounds'][1] + old['originalClosestBounds'][3]) / 2], 'zoom': 1}]}},
                 'overrideCameraScope': 'EXACT_OLD_APPROVED_FRAMING_CENTER_NOT_EVENT_ANCHOR',
                 'overrideScope': 'DIRECT_PROVIDER_REGRESSION_ONLY_NOT_NATURAL_LANGUAGE_ENVELOPE_SYNTAX',
                 'drawFrames': [0, 44, 89]})
write('examples/LEGACY_NATIVE_PROBE_REQUESTS.json', {
    'schema': 'WORLD_ENGINE_LEGACY_NATIVE_PROVIDER_PROBES_V2',
    'status': 'PREPARED_NOT_EXECUTED',
    'instructions': 'Compile each real explicit-region prompt first; for exact old-provider framing probes only, override compiled segment.region with runtimeRegionOverride and segment.presentation.camera with runtimePresentationOverride.camera. Camera centers use original approved framing center, not the event anchor. This descriptor is not supported user prompt alias syntax.',
    'cases': rows})
write('evidence/LEGACY_PROBE_COORDINATE_PROOF.json', {
    'schema': 'WORLD_ENGINE_LEGACY_PROBE_LOCALITY_PROOF_V2', 'sourcePath': CITY.relative_to(REPO).as_posix(),
    'sourceSHA256': CITY_SHA, 'license': 'Natural Earth Public Domain',
    'licenseEvidencePath': 'evidence/RETAINED_LICENSE_PROOF.json',
    'GISArchivePath': ARCHIVE.relative_to(REPO).as_posix(), 'GISArchiveSHA256': ARCHIVE_SHA,
    'claims': claims, 'newHistoricalClaim': False, 'drawExecuted': False})
print(json.dumps({'prepared': len(rows), 'newSourceBackedLocalities': len(claims), 'rendered': False}))
