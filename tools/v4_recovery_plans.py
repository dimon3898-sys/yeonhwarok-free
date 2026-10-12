#!/usr/bin/env python3
"""Build bounded V4 equivalent-plan candidates from preserved evidence.

This is a data assembler, not a Scale/Camera/Reveal compiler. It neither renders
nor changes protected engine sources. Original plan identity is not claimed.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'world-simulation-shorts-engine'
STATE = ENGINE / 'recovery/v4/V4-state-records'
OUT = ENGINE / 'recovery/v4/equivalent-plans'
FIXTURE = ENGINE / 'tests/fixtures/map_infographic_v1/source-scene-plan.json'
STATUS = 'RECOVERED_EQUIVALENT_V4_PLAN_CANDIDATE'
ACCEPTED_STATUS = 'RECOVERED_EQUIVALENT_V4_PLAN'
GLOBAL_GIS = ROOT / 'cinematic-world-map/assets/gis/countries_50m.geojson'
GLOBAL_GIS_SHA = '3e458fc036ad0a66411f2c1e6cac49c5d7bfb81cb1123bc513b22511a2b7fdeb'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def intersects(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def retained_layout(out, diagnostics):
    path = out / 'approved-measured-output.json'
    if diagnostics:
        with diagnostics.open(encoding='utf-8') as stream:
            rows = (json.loads(line) for line in stream)
            row = next(item for item in rows if item['frame'] == 330)
        retained = {'status': 'PRESERVED_APPROVED_MEASUREMENT', 'frame': 330,
                    'source_sha256': sha(diagnostics), 'source_member': 'frame-diagnostics.jsonl',
                    'layout': row['gpu']['layout'], 'validation': row['gpu']['layoutValidation']}
        write(path, retained)
    if not path.is_file():
        raise ValueError('Preserved approved-measured-output.json or --diagnostics is required')
    return read(path)


def typography(layout):
    items = {item['role']: item for item in layout if item['kind'] == 'TEXT'}
    expected = {'COUNTRY': (42, 1), 'LOCATION_LABEL': (36, 1.4),
                'EVENT_TITLE': (50, 1.3), 'SCENARIO_DISCLOSURE': (26, 1.2)}
    styles = {}
    widths = {}
    for role, (size, outline) in expected.items():
        item = items[role]
        assert item['fontSize'] == size and item['outlineRadius'] == outline
        assert item['lineHeight'] == 1.28 and len(item['lines']) == 1
        assert item['fits'] and not item['lineLimitExceeded']
        # Finite width exceeds both preserved advance and actual ink width.
        # This reproduces the successful single-line branch, not old limits.
        width = math.ceil(max(item['inkDimensions'][0],
                              *(ink['advance'] for ink in item['measuredInk']))) + 1
        widths[role] = width
        styles[role] = {'fontSize': size, 'minFontSize': size,
                        'fontFamily': item['fontFamily'], 'lineHeight': 1.28,
                        'outlineRadius': outline, 'maxWidth': width, 'maxLines': 1}
    styles['LOCATION_LABEL']['gap'] = 18
    styles['EVENT_TITLE'].update(maxWidthFraction=widths['EVENT_TITLE'] / 1080,
                                padding=[22, 16], clearance=24, panelOpacity=0.64)
    styles['SCENARIO_DISCLOSURE'].update(maxWidthFraction=widths['SCENARIO_DISCLOSURE'] / 1080, inset=12)
    return {'version': 'KOREAN_LAYOUT_STAGE3_V1', 'markerSize': 40,
            'country': styles['COUNTRY'], 'location': styles['LOCATION_LABEL'],
            'event': styles['EVENT_TITLE'], 'disclosure': styles['SCENARIO_DISCLOSURE']}, widths


def add_global_coverage(out):
    """Add the one evidence-authorized coverage candidate, retaining initial files."""
    if sha(GLOBAL_GIS) != GLOBAL_GIS_SHA:
        raise ValueError('Preserved global country source hash mismatch')
    features = read(GLOBAL_GIS)['features']
    codes = [feature['properties']['ADM0_A3'] for feature in features]
    if len(features) != 242 or len(set(codes)) != 242:
        raise ValueError('Original 242-feature source identity/order required')
    fixture_records = read(FIXTURE)['scenes'][0]['bold_infographic']['geometries']
    catalog = {record['id']: record for record in fixture_records}
    records, identities = [], []
    for index, feature in enumerate(features):
        code = feature['properties']['ADM0_A3']
        identity = f'COUNTRY_{code}'
        geometry = feature['geometry']
        if geometry['type'] not in ['Polygon', 'MultiPolygon']:
            raise ValueError('Preserved country polygon required')
        if identity in catalog:
            record = copy.deepcopy(catalog[identity])
            assert record['geometry_type'] == geometry['type']
            assert record['coordinates'] == geometry['coordinates']
            wrapper_status = 'PRESERVED_FIXTURE_RECORD'
        else:
            # Runtime wrapper only: original geometry is copied without edits.
            # The original wrapped-record hash is unknown; do not invent it.
            record = {'id': identity, 'geometry_type': geometry['type'],
                      'coordinates': copy.deepcopy(geometry['coordinates']),
                      'geometry_role': 'country', 'crs': 'EPSG:4326',
                      'name': feature['properties'].get('NAME_EN') or feature['properties'].get('NAME'),
                      'source_feature_id': code, 'source_file_sha256': GLOBAL_GIS_SHA,
                      'source_id': 'natural_earth_countries', 'source_version': '5.1.1',
                      'scale': {'denominator': 50000000, 'precision': 'Preserved native Natural Earth country polygons'},
                      'provenance': {'selector': {'kind': 'country', 'field': 'ADM0_A3', 'value': code},
                                     'source_feature_index': index,
                                     'transformations': ['Native geometry/parts/rings/vertices unchanged; runtime wrapper only']},
                      '_recovery': {'wrapper_status': 'EVIDENCE_DERIVED_RUNTIME_WRAPPER',
                                    'original_wrapped_record_sha256': 'NOT_ESTABLISHED'}}
            wrapper_status = 'EVIDENCE_DERIVED_RUNTIME_WRAPPER'
        records.append(record)
        identities.append({'source_feature_index': index, 'id': identity, 'wrapper_status': wrapper_status})
    regional = read(out / 'REGIONAL-plan.json')
    continent = read(out / 'CONTINENT-plan.json')
    assert regional['_recovery']['candidate'] == 'FIXTURE_ORDER-CONTEXT5'
    assert regional['secondary'] == ['COUNTRY_LBY', 'COUNTRY_SDN', 'COUNTRY_ISR', 'COUNTRY_JOR', 'COUNTRY_SAU']
    candidate = 'GLOBAL_SOURCE_ORDER-CONTEXT5'
    continent['geometries'] = records
    continent['_recovery'] = {**continent['_recovery'], 'candidate': candidate,
                             'geometry_order': 'GLOBAL_SOURCE_ORDER_242',
                             'context_coverage_source': str(GLOBAL_GIS.relative_to(ROOT)),
                             'context_coverage_source_sha256': GLOBAL_GIS_SHA,
                             'pixel_comparison': 'NOT_RUN'}
    # REGIONAL keeps the complete initial data, including seven native records
    # and the five-role map. Only CONTINENT coverage receives the new records.
    scene = read(out / 'scene.json')
    write(out / 'CONTINENT-plan-GLOBAL_SOURCE_ORDER.json', continent)
    write(out / f'candidate-{candidate}.json', {'status': STATUS, 'candidate': candidate,
                                             'plans': {'CONTINENT': continent, 'REGIONAL': regional}, 'scene': scene})
    write(out / 'GLOBAL_SOURCE_ORDER_PROVENANCE.json', {
        'status': STATUS, 'candidate': candidate, 'source': str(GLOBAL_GIS.relative_to(ROOT)),
        'source_sha256': GLOBAL_GIS_SHA, 'source_feature_count': 242,
        'source_order': identities, 'regional_file': 'REGIONAL-plan.json',
        'regional_sha256_unchanged': sha(out / 'REGIONAL-plan.json'),
        'initial_continent_sha256_unchanged': sha(out / 'CONTINENT-plan.json'),
        'new_continent_file': 'CONTINENT-plan-GLOBAL_SOURCE_ORDER.json',
        'trigger': {'source': 'Root actual candidate01 PNG comparison', 'changed_pixels': 317829,
                    'changed_percent_reported': 15.3274, 'typography_layout': 'MATCH_APPROVED_F330',
                    'observed_difference': 'Absent neutral-country geometry renders those land regions as ocean blue',
                    'visible_neutral_examples': ['Greece', 'Turkey', 'Syria', 'Iraq', 'Chad', 'Ethiopia']},
        'identity_policy': 'COUNTRY_ + original ADM0_A3; COUNTRY_PSX is retained regardless of ISO_A3=PSE',
        'geometry_policy': 'Original 242 feature order and unmodified native coordinate arrays',
        'runtime_combination': 'Initial REGIONAL seven records, followed by nonduplicate CONTINENT records in original dataset order',
        'original_plan_identity': 'NOT_CLAIMED', 'pixel_comparison': 'NOT_RUN', 'render': 'NOT_RUN'})
    print(json.dumps({'status': STATUS, 'candidate': candidate, 'global_features': 242,
                      'new_continent_file': 'CONTINENT-plan-GLOBAL_SOURCE_ORDER.json',
                      'regional': 'INITIAL_UNCHANGED', 'render': 'NOT_RUN'}))


def add_native_draw_order(out):
    """Reorder only REGIONAL's seven retained records using native GIS order."""
    if sha(GLOBAL_GIS) != GLOBAL_GIS_SHA:
        raise ValueError('Preserved global country source hash mismatch')
    regional = read(out / 'REGIONAL-plan.json')
    catalog = {record['id']: record for record in regional['geometries']}
    indexed = [(index, 'COUNTRY_' + feature['properties']['ADM0_A3'])
               for index, feature in enumerate(read(GLOBAL_GIS)['features'])
               if 'COUNTRY_' + feature['properties']['ADM0_A3'] in catalog]
    assert len(indexed) == len(catalog) == 7
    candidate = 'GLOBAL_DRAW_ORDER-CONTEXT5'
    regional['geometries'] = [catalog[identity] for _, identity in indexed]
    regional['_recovery'] = {**regional['_recovery'], 'candidate': candidate,
                            'geometry_order': 'GLOBAL_SOURCE_ORDER_SUBSET_7',
                            'draw_order_source': str(GLOBAL_GIS.relative_to(ROOT)),
                            'draw_order_source_sha256': GLOBAL_GIS_SHA,
                            'pixel_comparison': 'NOT_RUN'}
    continent = read(out / 'CONTINENT-plan-GLOBAL_SOURCE_ORDER.json')
    write(out / 'REGIONAL-plan-GLOBAL_SOURCE_ORDER.json', regional)
    write(out / f'candidate-{candidate}.json', {
        'status': STATUS, 'candidate': candidate,
        'plans': {'REGIONAL': regional, 'CONTINENT': continent}, 'scene': read(out / 'scene.json')})
    secondary = set(regional['secondary'])
    write(out / 'GLOBAL_DRAW_ORDER_PROVENANCE.json', {
        'status': STATUS, 'candidate': candidate, 'source_sha256': GLOBAL_GIS_SHA,
        'regional_native_source_order': [{'source_feature_index': i, 'id': identity} for i, identity in indexed],
        'secondary_ribbon_order': [identity for _, identity in indexed if identity in secondary],
        'changes': 'REGIONAL seven-record permutation only; native geometry bytes, role membership, assets, theme, typography unchanged',
        'continent_file': 'CONTINENT-plan-GLOBAL_SOURCE_ORDER.json',
        'continent_sha256_unchanged': sha(out / 'CONTINENT-plan-GLOBAL_SOURCE_ORDER.json'),
        'initial_regional_sha256_unchanged': sha(out / 'REGIONAL-plan.json'),
        'trigger': {'source': 'Root actual candidate02 PNG comparison', 'changed_pixels': 200,
                    'max_channel_difference': 2, 'localized_pairs': ['COUNTRY_ISR/COUNTRY_JOR', 'COUNTRY_LBY/COUNTRY_SDN']},
        'consumer_evidence': {'ring_append': 'renderer.mjs:384-393', 'triangle_index_order': 'renderer.mjs:330-338'},
        'selection_reason': 'Native source order reverses both residual shared-boundary pairs; ROLE_RECORD_ORDER keeps both pair directions',
        'original_plan_identity': 'NOT_CLAIMED', 'pixel_comparison': 'NOT_RUN', 'render': 'NOT_RUN'})
    print(json.dumps({'status': STATUS, 'candidate': candidate,
                      'new_regional_file': 'REGIONAL-plan-GLOBAL_SOURCE_ORDER.json',
                      'regional_geometry_ids': [identity for _, identity in indexed], 'render': 'NOT_RUN'}))


def verify_accepted(out):
    binding = read(out / 'BINDING_RECOVERY.json')
    if binding['status'] != ACCEPTED_STATUS:
        raise ValueError('Accepted binding receipt required')
    for name, expected in binding['canonical_component_sha256'].items():
        if sha(out / name) != expected:
            raise ValueError(f'Accepted component hash changed: {name}')
    print(json.dumps({'status': ACCEPTED_STATUS, 'operation': 'VERIFY_WITHOUT_OVERWRITE',
                      'canonical_component_sha256': binding['canonical_component_sha256']}))


def add_full_native_regional(out):
    """One focused runtime-path candidate; never change accepted components."""
    if sha(GLOBAL_GIS) != GLOBAL_GIS_SHA:
        raise ValueError('Preserved global country source hash mismatch')
    regional = read(out / 'REGIONAL-plan.json')
    continent = read(out / 'CONTINENT-plan.json')
    if regional['_recovery']['status'] != ACCEPTED_STATUS:
        raise ValueError('Verified static canonical source binding required')
    native = continent['geometries']
    features = read(GLOBAL_GIS)['features']
    assert len(native) == len(features) == 242
    for record, feature in zip(native, features):
        assert record['id'] == 'COUNTRY_' + feature['properties']['ADM0_A3']
        assert record['geometry_type'] == feature['geometry']['type']
        assert record['coordinates'] == feature['geometry']['coordinates']
    source_regional_sha = sha(out / 'REGIONAL-plan.json')
    candidate = 'REG_FULL_SOURCE_ORDER-CONTEXT5'
    regional['geometries'] = copy.deepcopy(native)
    regional['_recovery'] = {**regional['_recovery'], 'status': STATUS, 'candidate': candidate,
                            'accepted_candidate': 'NOT_SELECTED', 'binding_receipt': 'NOT_SELECTED',
                            'validated_source_candidate_sha256': None,
                            'derived_from_static_canonical_sha256': source_regional_sha,
                            'geometry_order': 'GLOBAL_SOURCE_ORDER_242_NATIVE_REGIONAL_PATH',
                            'pixel_comparison': 'NOT_RUN',
                            'validation_scope': 'NEW_FULL_RUNTIME_BINDING_CANDIDATE',
                            'full_camera_validation': 'NOT_RUN',
                            'secondary_status': 'PRESERVED_STATIC_EQUIVALENT_MEMBERSHIP_NEW_GEOMETRY_PATH_UNVERIFIED',
                            'original_plan_identity': 'NOT_CLAIMED'}
    new_name = 'REGIONAL-plan-FULL_SOURCE_ORDER.json'
    write(out / new_name, regional)
    write(out / f'candidate-{candidate}.json', {
        'status': STATUS, 'candidate': candidate,
        'plans': {'REGIONAL': regional, 'CONTINENT': continent}, 'scene': read(out / 'scene.json')})
    write(out / 'REG_FULL_SOURCE_ORDER_PROVENANCE.json', {
        'status': STATUS, 'candidate': candidate, 'new_regional_file': new_name,
        'source_gis': {'file': str(GLOBAL_GIS.relative_to(ROOT)), 'sha256': GLOBAL_GIS_SHA, 'features': 242},
        'canonical_regional_sha256_unchanged': source_regional_sha,
        'canonical_continent_sha256_unchanged': sha(out / 'CONTINENT-plan.json'),
        'new_native_regional_geometry_ids': [record['id'] for record in native],
        'changes': 'REGIONAL receives all 242 native source records in original source order; CONTINENT, role membership, framing, theme, typography and assets unchanged',
        'consumer_evidence': {'native_or_context_atlas_selection': 'renderer.mjs:389',
                              'coordinate_copy_no_lon_normalization': 'scale_projection.mjs:15-18',
                              'unwrap_and_periodic_atlas_copies': 'scale_projection.mjs:81-128'},
        'trigger': {'source': 'Root actual six-checkpoint comparison of canonical seven-record REGIONAL',
                    'bit_exact_frames': [0, 136, 269, 290, 330], 'mismatching_frame': 93,
                    'changed_pixels_frame93': 43, 'max_channel_difference_frame93': 200},
        'hypothesis': 'Native full-source REGIONAL avoids extra-context atlas path and restores original complete source draw order',
        'hypothesis_limit': 'No lon+180/-180 normalization exists in the helper; last-bit normalization cause is not established',
        'original_plan_identity': 'NOT_CLAIMED', 'pixel_comparison': 'NOT_RUN',
        'candidate_bound': 'Exactly one extra full-runtime binding candidate; no combinatorial variants', 'render': 'NOT_RUN'})
    print(json.dumps({'status': STATUS, 'candidate': candidate, 'new_regional_file': new_name,
                      'native_regional_geometry_count': 242, 'canonical_components': 'UNCHANGED', 'render': 'NOT_RUN'}))


def select_accepted(out, evidence_root):
    if evidence_root is None:
        raise ValueError('--comparison-dir with the three actual comparison receipts is required')
    ledger = []
    candidates = ['FIXTURE_ORDER-CONTEXT5', 'GLOBAL_SOURCE_ORDER-CONTEXT5', 'GLOBAL_DRAW_ORDER-CONTEXT5']
    for number, candidate in enumerate(candidates, 1):
        directory = evidence_root / f'candidate-{number:02d}'
        receipt_path = directory / 'pixel-comparison.json'
        receipt = read(receipt_path)
        if sha(directory / 'FINAL_HOLD.png') != receipt['actual_sha256']:
            raise ValueError('Actual rendered PNG identity does not match comparison receipt')
        ledger.append({'trial': number, 'candidate': candidate, 'comparison_receipt_sha256': sha(receipt_path),
                       'private_evidence_location_NOT_RUNTIME_INPUT': str(receipt_path),
                       **{key: receipt[key] for key in ['expected_sha256', 'actual_sha256',
                          'expected_rgba_sha256', 'actual_rgba_sha256', 'expected_dimensions', 'actual_dimensions',
                          'changed_pixels', 'total_pixels', 'changed_fraction', 'max_channel_difference', 'classification']}})
    final = ledger[-1]
    if (final['classification'] != 'BIT_EXACT' or final['changed_pixels'] != 0 or
        final['expected_sha256'] != final['actual_sha256'] or
        final['expected_rgba_sha256'] != final['actual_rgba_sha256']):
        raise ValueError('Actual bit-exact unchanged-renderer comparison required')
    selected = {'REGIONAL-plan.json': 'REGIONAL-plan-GLOBAL_SOURCE_ORDER.json',
                'CONTINENT-plan.json': 'CONTINENT-plan-GLOBAL_SOURCE_ORDER.json'}
    source_hashes = {destination: sha(out / source) for destination, source in selected.items()}
    plans = {name: read(out / source) for name, source in selected.items()}
    regional, continent = plans['REGIONAL-plan.json'], plans['CONTINENT-plan.json']
    union = list(regional['geometries'])
    present = {record['id'] for record in union}
    union.extend(record for record in continent['geometries'] if record['id'] not in present)
    expected_gpu = [{'id': record['id'], 'gpuID': index + 1,
                     'role': 2 if record['id'] == regional['primary'] else
                             1 if record['id'] in regional['secondary'] else 0}
                    for index, record in enumerate(union)]
    diagnostic_path = evidence_root / 'candidate-03/diagnostic.json'
    diagnostic = read(diagnostic_path)
    actual_gpu = [{key: record[key] for key in ['id', 'gpuID', 'role']}
                  for record in diagnostic['diagnostic']['geometry']]
    if actual_gpu != expected_gpu or diagnostic['errors'] or diagnostic['diagnostic']['glError'] != 0:
        raise ValueError('Actual renderer geometry/GPU-role union does not match selected source order')
    for name, plan in plans.items():
        plan['_recovery'] = {**plan['_recovery'], 'status': ACCEPTED_STATUS,
                             'accepted_candidate': 'GLOBAL_DRAW_ORDER-CONTEXT5',
                             'validated_source_candidate_sha256': source_hashes[name],
                             'binding_receipt': 'BINDING_RECOVERY.json',
                             'secondary_status': 'EQUIVALENT_FOR_VERIFIED_APPROVED_STATIC_RESULT',
                             'typography_limits': 'EQUIVALENT_SUCCESS_BRANCH_VERIFIED_FOR_APPROVED_FIXTURE',
                             'pixel_comparison': 'BIT_EXACT_APPROVED_STATIC_FINAL_HOLD',
                             'validation_scope': 'STATIC_APPROVED_FINAL_HOLD_ONLY',
                             'full_camera_validation': 'PENDING_SEPARATE_FULL_CLI_RECEIPT',
                             'original_plan_identity': 'NOT_CLAIMED'}
        if name == 'CONTINENT-plan.json':
            plan['_recovery']['inactive_historical_asset_descriptors'] = {
                'assets.terrain': {'runtime_required': False, 'runtime_loaded': False,
                                  'reason': 'V4 supplies explicit contextTerrain; the factory loads REGIONAL assets',
                                  'historical_file_reference_NOT_REQUIRED': plan['assets']['terrain']['file'],
                                  'policy': 'Historical provenance only; no temporary path is a required runtime input'}}
        write(out / name, plan)
    components = {name: sha(out / name) for name in [*plans, 'scene.json']}
    binding = {'status': ACCEPTED_STATUS, 'accepted_candidate': 'GLOBAL_DRAW_ORDER-CONTEXT5',
               'original_plan_identity': 'NOT_CLAIMED', 'validation_scope': 'STATIC_APPROVED_FINAL_HOLD_ONLY',
               'full_camera_validation': 'PENDING_SEPARATE_FULL_CLI_RECEIPT',
               'actual_trials': ledger, 'trial_count': 3, 'corrections_after_initial': 2,
               'validated_source_candidate_sha256': source_hashes, 'canonical_component_sha256': components,
               'canonical_metadata_policy': 'Runtime data unchanged from verified candidate; acceptance metadata only',
               'source_gis': {'file': str(GLOBAL_GIS.relative_to(ROOT)), 'sha256': GLOBAL_GIS_SHA, 'feature_count': 242},
               'regional_geometry_ids': [record['id'] for record in regional['geometries']],
               'continent_geometry_ids': [record['id'] for record in continent['geometries']],
               'runtime_gpu_union_order_and_roles': actual_gpu,
               'runtime_geometry_count': len(actual_gpu), 'primary': regional['primary'],
               'secondary_membership': regional['secondary'], 'neutral_PSX': 'ACTUAL_GPU_ROLE_0_AND_BIT_EXACT_STATIC_RESULT',
               'effective_typography': regional['layout']['measured'],
               'safe_area': regional['layout']['safe'], 'country_labels': regional['layout']['countryLabels'],
               'approved_measurement_evidence': {'file': 'approved-measured-output.json',
                                                 'sha256': sha(out / 'approved-measured-output.json')},
               'actual_diagnostic_evidence': {'sha256': sha(diagnostic_path),
                                              'webgl_raw_rgba_sha256': diagnostic['raw_rgba_sha256'],
                                              'webgl_raw_rgba_orientation': diagnostic['raw_rgba_orientation']},
               'asset_runtime_policy': 'Explicit contextTerrain and REGIONAL asset routes are runtime inputs; CONTINENT historical terrain descriptor is inactive',
               'scene_identity': 'Scene4 consumer binding only; original serialized Scene hash not claimed',
               'hash_policy': 'Canonical component hashes live only in this external receipt; no input/self-hash circularity',
               'future_default_generation': 'Verify accepted components without overwriting; explicit --select is required for selection'}
    write(out / 'BINDING_RECOVERY.json', binding)
    print(json.dumps({'status': ACCEPTED_STATUS, 'canonical_component_sha256': components,
                      'actual_trials': 3, 'changed_pixels_final': 0, 'runtime_geometry_count': len(actual_gpu)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=OUT)
    parser.add_argument('--diagnostics', type=Path,
                        help='Existing approved diagnostics; extracts f330 into tracked candidate evidence')
    parser.add_argument('--add-global-coverage', action='store_true',
                        help='Add the one comparison-authorized 242-country coverage candidate; retain initial plans')
    parser.add_argument('--add-native-draw-order', action='store_true',
                        help='Add the one residual-boundary comparison candidate; retain initial plans')
    parser.add_argument('--add-full-native-regional', action='store_true',
                        help='Add one runtime-path validation candidate without changing accepted components')
    parser.add_argument('--select', choices=['GLOBAL_DRAW_ORDER-CONTEXT5'],
                        help='Explicitly select the actually verified equivalent candidate')
    parser.add_argument('--comparison-dir', type=Path,
                        help='Existing private evidence directory containing actual candidate01/02/03 receipts')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    if out != OUT.resolve():
        raise ValueError('Output is restricted to recovery/v4/equivalent-plans')
    out.mkdir(parents=True, exist_ok=True)
    if args.select:
        if args.add_global_coverage or args.add_native_draw_order or args.add_full_native_regional or args.diagnostics:
            raise ValueError('Selection must be explicit and separate from candidate generation')
        select_accepted(out, args.comparison_dir)
        return
    if args.add_full_native_regional:
        if args.add_global_coverage or args.add_native_draw_order or args.diagnostics:
            raise ValueError('Full native candidate must be explicit and separate from other generation')
        add_full_native_regional(out)
        return
    if (out / 'BINDING_RECOVERY.json').is_file():
        if args.add_global_coverage or args.add_native_draw_order or args.diagnostics:
            raise ValueError('Accepted canonical plans are frozen; no implicit candidate reset is permitted')
        verify_accepted(out)
        return
    for name in ['REGIONAL-plan.json', 'CONTINENT-plan.json']:
        path = out / name
        if path.is_file() and read(path).get('_recovery', {}).get('status') == ACCEPTED_STATUS:
            raise ValueError('Accepted plan exists without binding receipt; preserve it and use explicit verified selection')
    if args.add_global_coverage and args.add_native_draw_order:
        raise ValueError('Choose one bounded candidate addition at a time')
    if args.add_global_coverage:
        add_global_coverage(out)
        return
    if args.add_native_draw_order:
        add_native_draw_order(out)
        return
    manifest_path, camera_path = STATE / 'input-manifest.json', STATE / 'camera-plan.json'
    manifest, camera = read(manifest_path), read(camera_path)
    intent = camera['intent']
    bold = read(FIXTURE)['scenes'][0]['bold_infographic']
    geometries = bold['geometries']
    assert bold['geometry_ids'] == [record['id'] for record in geometries]
    catalog = {record['id']: record for record in geometries}
    context_ids = [record['id'] for record in intent['contextGeometry']]
    role_ids = [record['geometry_ref'] for record in bold['regions']
                if record['event_id'] == 'MAP_E001' and record['role'] == 'SECONDARY']
    primary = intent['primaryRegionId']
    for record in [intent['primaryGeometry'], *intent['contextGeometry']]:
        assert catalog[record['id']]['sha256'] == record['sha256']
        assert catalog[record['id']]['coordinates'] == record['coordinates']
    assert 'COUNTRY_PSX' in role_ids and 'COUNTRY_PSX' not in context_ids
    retained = retained_layout(out, args.diagnostics)
    measured, widths = typography(retained['layout'])
    text_items = {item['role']: item for item in retained['layout'] if item['kind'] == 'TEXT'}
    assert text_items['COUNTRY']['text'] == intent['texts']['primaryLabel']
    assert text_items['LOCATION_LABEL']['text'] == intent['texts']['locationLabel']
    assert text_items['EVENT_TITLE']['text'] == intent['texts']['eventTitle']
    country_anchor = text_items['COUNTRY']['placement']['sourceGeographicAnchor']
    scene = {'primary_region_id': primary, 'primary_label': intent['texts']['primaryLabel'],
             'location_label': intent['texts']['locationLabel'], 'event_title': intent['texts']['eventTitle']}
    source = {'fixture': str(FIXTURE.relative_to(ROOT)), 'fixture_sha256': sha(FIXTURE),
              'input_manifest': str(manifest_path.relative_to(ROOT)), 'input_manifest_sha256': sha(manifest_path),
              'camera_plan': str(camera_path.relative_to(ROOT)), 'camera_plan_sha256': sha(camera_path),
              'approved_output': 'approved-measured-output.json',
              'scene_hash': 'UNRESOLVED_ORIGINAL_SERIALIZED_SCENE_IDENTITY',
              'original_scene_hash_reference': manifest['sceneHash']}
    bounds = {scale: manifest['scales'][scale]['framing']['bounds'] for scale in ['CONTINENT', 'REGIONAL']}
    # Finite order candidates retain native records; no coordinate synthesis.
    selected = {scale: [g['id'] for g in geometries if intersects(g['bbox'], bounds[scale])]
                for scale in bounds}
    orders = {'FIXTURE_ORDER': selected}
    orders['ROLE_RECORD_ORDER'] = {
        scale: [i for i in [primary, *role_ids] if i in selected[scale]] +
               [i for i in selected[scale] if i not in {primary, *role_ids}]
        for scale in bounds}
    variants = []
    for order_name, order in orders.items():
        for membership_name, secondary in [('CONTEXT5', context_ids), ('FIXTURE6', role_ids)]:
            plans = {}
            candidate = f'{order_name}-{membership_name}'
            for scale in ['CONTINENT', 'REGIONAL']:
                frozen = manifest['scales'][scale]
                marker = 28 if scale == 'CONTINENT' else 40
                profile = copy.deepcopy(measured)
                profile['markerSize'] = marker
                plan = {'primary': primary, 'secondary': list(secondary),
                        'anchor': {'geometry_type': 'Point', 'crs': 'EPSG:4326', 'coordinates': intent['anchor']},
                        'geometries': [copy.deepcopy(catalog[i]) for i in order[scale]],
                        'framing': copy.deepcopy(frozen['framing']), 'theme': copy.deepcopy(frozen['theme']),
                        'assets': copy.deepcopy(frozen['assets']),
                        'text': {'locationLabel': scene['location_label'], 'eventTitle': scene['event_title'],
                                 'watermark': text_items['SCENARIO_DISCLOSURE']['text']},
                        'layout': {'canonical': intent['display']['canonicalOutput'], 'safe': intent['display']['safeArea'],
                                   'markerSize': marker, 'measured': profile,
                                   'countryLabels': [{'text': scene['primary_label'], 'coordinates': country_anchor,
                                                      'geometry_ref': primary}]},
                        'scale': {'version': 'MAP_INFOGRAPHIC_SCALE_V1', 'name': scale,
                                  'canonicalOutput': intent['display']['canonicalOutput'],
                                  'marker': {'pixels': marker, 'geographicAnchor': intent['anchor']},
                                  'information': {'location': scale == 'REGIONAL', 'country': True,
                                                  'title': True, 'disclosure': True}},
                        '_recovery': {'status': STATUS, 'candidate': candidate, 'provenance': source,
                                      'original_scale_plan_sha256_NOT_REPRODUCED': frozen['hash'],
                                      'secondary_basis': membership_name,
                                      'secondary_status': 'EVIDENCE_DERIVED_CANDIDATE_NOT_ORIGINAL_ARRAY',
                                      'geometry_order': order_name, 'typography_limits': 'EQUIVALENT_SUCCESS_BRANCH_CANDIDATE',
                                      'asset_descriptors': 'PRESERVED_DESCRIPTOR_RUNTIME_BYTES_BOUND_BY_HARNESS',
                                      'pixel_comparison': 'NOT_RUN'}}
                plans[scale] = plan
            write(out / f'candidate-{candidate}.json', {'status': STATUS, 'candidate': candidate, 'plans': plans, 'scene': scene})
            variants.append({'candidate': candidate, 'file': f'candidate-{candidate}.json',
                             'geometry_ids': order, 'secondary_ids': secondary})
            if candidate == 'FIXTURE_ORDER-CONTEXT5':
                for scale in plans:
                    write(out / f'{scale}-plan.json', plans[scale])
    write(out / 'scene.json', scene)
    write(out / 'CANDIDATE_PROVENANCE.json', {'status': STATUS, 'initial_candidate': 'FIXTURE_ORDER-CONTEXT5',
          'sources': source, 'finite_candidates': variants, 'typography_finite_widths': widths,
          'secondary_counterevidence': 'Approved FinalHold PSX interior neutral pixels favor CONTEXT5; FIXTURE6 retained only as alternative',
          'limitations': ['No original plan/Scene hash claim', 'Geometry draw/GPU order not yet verified',
                          'Historical typography constraints unavailable; finite single-line success branch only',
                          'CONTINENT.secondary is not consumed by V4 factory; REGIONAL role map owns context colors',
                          'Assets retain preserved descriptors; actual runtime source descriptors are independently bound by harness',
                          'Pixel equivalence and Reveal schedule not established until actual unchanged-engine comparison'],
          'render': 'NOT_RUN'})
    print(json.dumps({'status': STATUS, 'initial_candidate': 'FIXTURE_ORDER-CONTEXT5',
                      'candidate_count': len(variants), 'files': [f'{s}-plan.json' for s in plans] + ['scene.json']}))


if __name__ == '__main__':
    main()
