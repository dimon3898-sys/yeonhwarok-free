"""Prepare declared, nonhistorical data examples; never render or alter originals.

Modern locality coordinates and country geometry are copied from preserved
source bytes. Connections, fictional polygons, display dates and camera scripts
are explicitly authored technical examples, not observed services or history.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zipfile

HERE = Path(__file__).resolve().parents[1]
ENGINE = HERE.parents[1]
REPO = HERE.parents[2]
OLD = HERE.parent / 'universal-data-pipeline-v1'
CITY_SOURCE = ENGINE / 'recovery/verified-front-data-v4-recovery/sources/populated_places_source.geojson'
CITY_SHA = 'fd3fa867a320cbd5c5b6bb5bc550afeec2939fb2cef688e508007282a55ac42f'
GIS_ZIP = ENGINE / 'recovery/g2-final-recovery-v1/fixtures/GENERIC_REGION_INPUTS.zip'
GIS_ZIP_SHA = '29806402e97db3a97cb4f3b95d6851d9bca62810ccbfb29199592ad49b9dd22b'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def read(name):
    return json.loads((OLD / 'examples' / (name + '.json')).read_bytes())


def write(relative, value):
    path = HERE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if path.exists():
        if path.read_bytes() != raw:
            raise ValueError('REFUSE_DIFFERENT_EXISTING_EXAMPLE: ' + relative)
    else:
        with path.open('xb') as stream:
            stream.write(raw)
    return {'path': relative, 'sha256': sha(raw), 'bytes': len(raw)}


def second_scene(first, suffix):
    result = deepcopy(first)
    result['sceneId'] += '-' + suffix
    result['startFrame'], result['endFrame'] = 90, 180
    result['facts'].pop('scene_timing', None)
    return result


def keyframes(center, shift=(.25, .15)):
    return {'mode': 'KEYFRAMES', 'keyframes': [
        {'frame': 0, 'center': [center[0] - shift[0], center[1] - shift[1]], 'zoom': .85},
        {'frame': 40, 'center': [center[0] + shift[0], center[1] + shift[1]], 'zoom': .75},
        {'frame': 89, 'center': list(center), 'zoom': 1},
    ]}


def envelope(prompt, data, region, presentation):
    return {'schema': 'WORLD_ENGINE_PRESENTATION_PROMPT_V2', 'prompt': prompt,
            'data': data, 'region': {'sourceId': 'AUTO', 'crs': 'EPSG:4326', **region},
            'presentation': presentation}


def two_scene_data(name, kind):
    data = read(name)
    data['durationSeconds'] = 6
    data.pop('renderSettings', None)
    first = data['scenes'][0]
    first.pop('renderSettings', None)
    first['facts'].pop('scene_timing', None)
    second = second_scene(first, 'return' if kind != 'area' else 'contract')
    if kind != 'area':
        for route in second['facts']['routes']:
            route['direction'] = 'REVERSE'
    else:
        facts = second['facts']
        facts['time_range'] = {'start': '2026-10-24', 'end': '2026-10-25'}
        facts['stages'] = [
            {'id': 'FICTIONAL_RETRACT_START', 'date': '2026-10-24',
             'label': 'Explicit fictional large zone', 'area_refs': ['ZONE_LARGE'], 'front_refs': ['FRONT_LARGE']},
            {'id': 'FICTIONAL_RETRACT_END', 'date': '2026-10-25',
             'label': 'Explicit fictional contraction', 'area_refs': ['ZONE_SMALL'], 'front_refs': ['FRONT_SMALL']},
        ]
        facts['source_notes'][0]['note'] += (' Second scene is an explicitly authored fictional contraction '
            'of the same two supplied polygons; not a historical observation or a new land claim.')
    data['scenes'].append(second)
    return data


def main():
    raw = CITY_SOURCE.read_bytes()
    if sha(raw) != CITY_SHA or sha(GIS_ZIP.read_bytes()) != GIS_ZIP_SHA:
        raise ValueError('PRESERVED_SOURCE_SHA_MISMATCH')
    cities = json.loads(raw)['features']
    with zipfile.ZipFile(GIS_ZIP) as archive:
        native = json.loads(archive.read('europe_germany/RECOVERY_RUNTIME.json'))['nativePlan']['geometries']
        originals = {name: json.loads(archive.read(name + '/RECOVERY_RUNTIME.json')) for name in [
            'europe_germany', 'south_america_chile', 'namibia_desert_coast', 'korean_peninsula', 'nepal_himalaya']}
    coordinate_claims = []

    def locality(name, country, identifier):
        rows = [feature for feature in cities if feature['properties'].get('name') == name
                and feature['properties'].get('adm0name') == country]
        if len(rows) != 1:
            raise ValueError('EXACT_LOCALITY_FEATURE_REQUIRED: ' + name)
        feature = rows[0]
        coordinate_claims.append({'id': identifier, 'sourceName': name, 'sourceCountry': country,
            'ne_id': feature['properties']['ne_id'], 'coordinates': feature['geometry']['coordinates'],
            'featureCanonicalSHA256': sha(canonical(feature)),
            'scope': 'MODERN_LOCALITY_NOT_AIRPORT_PORT_OR_OBSERVED_TRAFFIC'})
        return {'id': identifier, 'label': identifier, 'anchor': feature['geometry']['coordinates'],
                'country_id': 'COUNTRY_' + ('JPN' if country == 'Japan' else 'AUS')}

    def new_region_data(subject, country_id, locations, anchor):
        data = read('AVIATION_GERMANY')
        data.pop('renderSettings', None)
        data['topic'] = subject + ' transport route'
        row = data['scenes'][0]
        row.pop('renderSettings', None)
        row['sceneId'] = subject.lower().replace(' ', '-')
        facts = row['facts']
        facts['subject'] = {'id': country_id + '_ILLUSTRATIVE', 'label': subject,
                            'aliases': [subject], 'event_family': 'TRANSPORT'}
        facts['locations'] = locations
        facts['native_context'] = {'country_ids': [country_id], 'primary_country_id': country_id,
                                   'secondary_country_ids': [], 'context_location_ids': [x['id'] for x in locations]}
        country = next(value for value in native if value['id'] == country_id)
        facts['geometries'] = [
            {'id': country_id, 'source_id': 'SUPPLIED_FIXTURE',
             'geometry': {'type': country['geometry_type'], 'coordinates': deepcopy(country['coordinates'])}},
            {'id': 'DECLARED_CONNECTION', 'source_id': 'SUPPLIED_FIXTURE',
             'geometry': {'type': 'LineString', 'coordinates': [row['anchor'] for row in locations]}},
        ]
        facts['camera'] = {'anchor': anchor, 'target_geometry_refs': [country_id, 'DECLARED_CONNECTION'],
                          'minimum_context_geometry_refs': [country_id], 'detail_policy': 'FACT_BASED_VISUAL_GRADE'}
        facts['source_notes'][0]['source_reference'] = ('Original illustrative connection; modern coordinates '
            'reused from frozen Natural Earth source in evidence/EXTENDED_COORDINATE_PROOF.json')
        facts['source_notes'][0]['note'] = ('Author-defined technical city connection and playback dates. '
            'No actual airline service, navigable shipping route, trade volume, historical troop or territorial claim.')
        facts.pop('scene_timing', None)
        return data

    cases = []
    data = two_scene_data('AVIATION_GERMANY', 'transport')
    first, second = data['scenes']
    value = envelope(
        '첨부한 HAMBURG, BERLIN, MUNICH 좌표와 두 방향 연결 자료로 6초 항공 연결 영상을 만들어줘. '
        '첫 장면은 카메라를 이동하고 줌아웃한 뒤 줌인해줘. 두 번째 장면은 제공한 역방향 경로를 따라 카메라가 이동해줘. '
        '제공한 도시를 강조하고 두 장면을 전환해줘. 이 연결은 실제 항공편이 아닌 가상 예시야.',
        data, {'center': [10, 51], 'bbox': [0, 35, 20, 67], 'countryId': 'COUNTRY_DEU'},
        {'camera': keyframes([10, 51]),
         'highlights': [{'id': 'hamburg-focus', 'locationId': 'HAMBURG', 'startFrame': 12, 'endFrame': 28}],
         'sceneOverrides': {second['sceneId']: {
             'camera': {'mode': 'ROUTE_FOLLOW', 'routeId': 'ILLUSTRATIVE_ROUTE', 'zoom': .85, 'followStrength': .1},
             'highlights': [{'id': 'munich-focus', 'locationId': 'MUNICH', 'startFrame': 12, 'endFrame': 28}]}},
         'transitions': [{'type': 'CUT', 'frame': 90}]})
    cases.append(('AVIATION_EUROPE_NL', value, 'PASS', 'ACTUAL_STUDIO_CANDIDATE'))

    data = two_scene_data('TRADE_CHILE', 'transport')
    first, second = data['scenes']
    value = envelope(
        'Create a 6 second illustrative trade connection using the attached VALPARAISO, SANTIAGO and CONCEPCION '
        'coordinates. Pan and zoom out, then zoom in during the first scene. Follow the supplied reverse route '
        'with the camera in the second scene. Highlight the supplied cities and cut between the two scenes. '
        'This is an abstract city connection, not an observed or navigable shipping service.',
        data, {'center': [-71.5, -33], 'bbox': [-78, -43, -65, -23], 'countryId': 'COUNTRY_CHL'},
        {'camera': keyframes([-71.5, -33], (.15, .1)),
         'highlights': [{'id': 'valparaiso-focus', 'locationId': 'VALPARAISO', 'startFrame': 12, 'endFrame': 28}],
         'sceneOverrides': {second['sceneId']: {
             'camera': {'mode': 'ROUTE_FOLLOW', 'routeId': 'ILLUSTRATIVE_ROUTE', 'zoom': .85, 'followStrength': .1},
             'highlights': [{'id': 'concepcion-focus', 'locationId': 'CONCEPCION', 'startFrame': 12, 'endFrame': 28}]}},
         'transitions': [{'type': 'CUT', 'frame': 90}]})
    cases.append(('TRADE_SOUTH_AMERICA_NL', value, 'PASS', 'ACTUAL_STUDIO_CANDIDATE'))

    data = two_scene_data('FICTIONAL_NAMIBIA', 'area')
    first, second = data['scenes']
    value = envelope(
        '제공한 가상 영토 자료만 사용해 6초 지도 영상을 만들어줘. 첫 장면에서는 영역 확장과 영토 색상 변화를, '
        '두 번째 장면에서는 같은 영역의 축소를 보여줘. 카메라를 이동하고 줌아웃한 뒤 줌인해줘. '
        '제공한 WINDHOEK 위치를 강조하고 두 장면을 전환해줘. 실제 역사나 실제 점령 주장이 아닌 가상 설정이야.',
        data, {'center': [17.5, -23.5], 'bbox': [11, -30, 24, -17], 'countryId': 'COUNTRY_NAM'},
        {'camera': keyframes([17.5, -23.5], (.18, .12)),
         'territoryColors': {'FICTIONAL_START': [.92, .14, .09, .32], 'FICTIONAL_END': [.1, .35, .95, .35]},
         'highlights': [{'id': 'windhoek-focus', 'locationId': 'WINDHOEK', 'startFrame': 12, 'endFrame': 28}],
         'sceneOverrides': {second['sceneId']: {
             'camera': keyframes([17.5, -23.5], (-.18, .1)),
             'initialStateVisibility': 'PRESERVE_PROVIDED',
             'territoryColors': {'FICTIONAL_RETRACT_START': [.1, .35, .95, .35], 'FICTIONAL_RETRACT_END': [.92, .14, .09, .32]},
             'highlights': [{'id': 'windhoek-return-focus', 'locationId': 'WINDHOEK', 'startFrame': 50, 'endFrame': 68}]}},
         'transitions': [{'type': 'CUT', 'frame': 90}]})
    cases.append(('FICTIONAL_AFRICA_NL', value, 'PASS', 'ACTUAL_STUDIO_CANDIDATE'))

    japan = new_region_data('Japan illustrative aviation', 'COUNTRY_JPN', [
        locality('Tokyo', 'Japan', 'TOKYO'), locality('Kyoto', 'Japan', 'KYOTO')], [138, 37])
    cases.append(('NEW_REGION_JAPAN_NL', envelope(
        'Show the supplied TOKYO to KYOTO illustrative connection for 3 seconds. Move and zoom the camera, '
        'and highlight TOKYO. Use only the attached coordinates; no actual flight service is claimed.',
        japan, {'center': [138, 37], 'bbox': [130, 29, 145, 46], 'countryId': 'COUNTRY_JPN'},
        {'camera': keyframes([138, 37], (.1, .1)), 'highlights': [{'id': 'tokyo-focus', 'locationId': 'TOKYO', 'startFrame': 12, 'endFrame': 28}]}),
        'PASS', 'UNREGISTERED_REGION_DRAW_CANDIDATE'))
    australia = new_region_data('Australia illustrative connection', 'COUNTRY_AUS', [
        locality('Alice Springs', 'Australia', 'ALICE_SPRINGS'), locality('Canberra', 'Australia', 'CANBERRA'),
        locality('Melbourne', 'Australia', 'MELBOURNE')], [139.5, -29.5])
    cases.append(('NEW_REGION_AUSTRALIA_NL', envelope(
        '제공한 ALICE_SPRINGS, CANBERRA, MELBOURNE 좌표를 연결하는 3초 가상 연결 영상을 만들어줘. '
        '카메라 이동과 줌을 적용하고 제공한 도시를 강조해줘. 실제 항공편이나 물류량은 주장하지 않아.',
        australia, {'center': [139.5, -29.5], 'bbox': [126, -42, 153, -17], 'countryId': 'COUNTRY_AUS'},
        {'camera': keyframes([139.5, -29.5], (.15, .1)), 'highlights': [{'id': 'canberra-focus', 'locationId': 'CANBERRA', 'startFrame': 12, 'endFrame': 28}]}),
        'PASS', 'UNREGISTERED_REGION_DRAW_CANDIDATE'))

    partial = read('KOREAN_WAR_PARTIAL_FRONT_UNSUPPORTED')
    cases.append(('HISTORICAL_PARTIAL_SOURCE_NL', envelope(
        '제공한 1951-01-24 부분 전선 자료만 3초 동안 보여줘. 확인되지 않은 전체 점령 영역은 만들지 말고 '
        '제공한 위치를 중심으로 카메라를 이동해줘.', partial,
        {'center': [127.5, 37.1], 'bbox': [124, 34, 131, 40], 'countryId': 'COUNTRY_KOR', 'legacyProfileId': 'korean_peninsula'},
        {'camera': keyframes([127.5, 37.1], (.05, .05))}),
        'UNSUPPORTED', 'QUALIFIED_PARTIAL_SOURCE_NO_CONNECTED_LINE_METRIC_CONSUMER'))
    missing = read('KOREAN_WAR_MISSING_CONTROL')
    cases.append(('HISTORICAL_MISSING_CONTROL_NL', envelope(
        '제공한 한국전쟁 자료로 3초 영상을 만들어줘. 실제 근거가 없는 영토 경계는 만들지 말고 '
        '누락된 자료를 알려줘.', missing,
        {'center': [127, 37], 'bbox': [124, 34, 131, 40], 'countryId': 'COUNTRY_KOR', 'legacyProfileId': 'korean_peninsula'},
        {'camera': keyframes([127, 37], (.05, .05))}),
        'NEEDS_INPUT', 'HISTORICAL_EVIDENCE_AND_FULL_OWNERSHIP_MISSING'))

    rows = []
    for name, value, expected, scope in cases:
        rows.append({'id': name, **write('examples/' + name + '.json', value),
                     'expectedStatus': expected, 'scope': scope})

    base = deepcopy(cases[0][1])
    negatives = []
    value = deepcopy(base); value['prompt'] = 'Create a 6 second connection from UNKNOWN_CITY to BERLIN and follow the route.'
    negatives.append(('UNKNOWN_LOCATION', value, 'NEEDS_INPUT'))
    value = deepcopy(base); value['prompt'] = 'Create a 6 second map of the attached event on 1950-06-25. Follow the route.'
    negatives.append(('DATE_CONFLICT', value, 'CONFLICT'))
    value = deepcopy(base); value['prompt'] = 'Create a 3 second map with the supplied two scenes. Follow the route.'
    negatives.append(('DURATION_CONFLICT', value, 'CONFLICT'))
    value = deepcopy(base); value['data']['scenes'][0]['facts']['locations'][0]['anchor'][0] = 200
    negatives.append(('INVALID_COORDINATE', value, 'INVALID'))
    value = deepcopy(base); del value['data']
    negatives.append(('MISSING_ATTACHED_DATA', value, 'NEEDS_INPUT'))
    value = deepcopy(base); value['data']['scenes'][1]['startFrame'] = 91
    negatives.append(('SCENE_GAP', value, 'CONFLICT'))
    value = deepcopy(base); value['presentation']['camera'] = {'mode': 'ORBIT', 'degrees': 360}
    negatives.append(('UNSUPPORTED_ORBIT', value, 'UNSUPPORTED'))
    value = deepcopy(base); value['presentation']['transitions'][0]['type'] = 'DISSOLVE'
    negatives.append(('UNSUPPORTED_DISSOLVE', value, 'UNSUPPORTED'))
    value = deepcopy(base); value['region'] = {'center': [10, 89], 'bbox': [0, 86, 20, 90], 'sourceId': 'AUTO', 'crs': 'EPSG:4326'}
    negatives.append(('POLAR_PROJECTION_LIMIT', value, 'UNSUPPORTED'))
    value = deepcopy(cases[3][1]); value['region']['countryId'] = 'COUNTRY_FRA'
    negatives.append(('COUNTRY_COORDINATE_CONFLICT', value, 'CONFLICT'))
    negative_rows = [{'id': name, **write('examples/negative/' + name + '.json', value), 'expectedStatus': expected}
                     for name, value, expected in negatives]

    proof = {'schema': 'WORLD_ENGINE_PRESENTATION_LOCALITY_SOURCE_PROOF_V2',
        'sourcePath': CITY_SOURCE.relative_to(REPO).as_posix(), 'sourceSHA256': CITY_SHA,
        'sourceURL': 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places_simple.geojson',
        'license': 'Natural Earth Public Domain', 'licenseURL': 'https://www.naturalearthdata.com/about/terms-of-use/',
        'CRS': 'OGC:CRS84', 'axisOrder': 'longitude_latitude', 'claims': coordinate_claims,
        'retainedOldContextProof': {'path': (OLD / 'evidence/MODERN_COORDINATE_PROOF.json').relative_to(REPO).as_posix(),
                                  'sha256': sha((OLD / 'evidence/MODERN_COORDINATE_PROOF.json').read_bytes())},
        'GISArchive': {'path': GIS_ZIP.relative_to(REPO).as_posix(), 'sha256': GIS_ZIP_SHA},
        'newConnectionsObserved': False, 'newHistoricalGeometryGenerated': False}
    write('evidence/EXTENDED_COORDINATE_PROOF.json', proof)
    registry = json.loads((OLD / 'evidence/TRUSTED_EVIDENCE.json').read_bytes())
    write('evidence/RETAINED_HISTORY_REGISTRY.json', registry)
    write('evidence/HISTORY_SCOPE.json', {'schema': 'WORLD_ENGINE_PRESENTATION_HISTORY_SCOPE_V2',
        'registryOriginalPath': (OLD / 'evidence/TRUSTED_EVIDENCE.json').relative_to(REPO).as_posix(),
        'registryOriginalSHA256': sha((OLD / 'evidence/TRUSTED_EVIDENCE.json').read_bytes()),
        'partialFixtureOriginalSHA256': sha((OLD / 'examples/KOREAN_WAR_PARTIAL_FRONT_UNSUPPORTED.json').read_bytes()),
        'newHistoricalFactOrBoundaryInvented': False, 'priorApproximateRegistrationPromotedToExact': False,
        'claimedScope': 'Existing dated approximate partial line only. No complete bilateral ownership. '
                        'Native LINE_METRIC consumer connection remains a separate engine requirement.'})
    legacy = []
    for name, old in originals.items():
        asset = old['sourceStyle']['terrainAsset']
        legacy.append({'legacySourceRegionId': name, 'originalClosestBounds': old['nativePlan']['framing']['bounds'],
            'originalCameraAnchor': old['eventLocation']['anchor'] if isinstance(old['eventLocation'], dict) and 'anchor' in old['eventLocation'] else old['eventLocation'],
            'originalTerrainAsset': asset, 'preservedOldProfile': True})
    write('examples/LEGACY_FIVE_REGION_MATRIX.json', {'schema': 'WORLD_ENGINE_RETAINED_FIVE_REGION_FIXTURE_V2',
        'scope': 'Input descriptors for source/compatibility tests, not already executed draw results.', 'cases': legacy})
    manifest = {'schema': 'WORLD_ENGINE_PRESENTATION_EXAMPLE_CASES_V2', 'cases': rows,
                'negativeCases': negative_rows, 'status': 'PREPARED_NOT_EXECUTED',
                'actualDemosAllowedOnlyAfterGates': True, 'paidExecutionAllowed': False}
    write('examples/CASE_MANIFEST.json', manifest)
    print(json.dumps({'prepared': len(rows), 'negative': len(negative_rows),
                      'modernSourceSHA256': CITY_SHA, 'renderingStarted': False}))


if __name__ == '__main__':
    main()
