"""Verify fixture claims against retained source bytes; no network or rendering."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
OLD = HERE.parent / 'universal-data-pipeline-v1'
checks = []


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def check(name, passed, detail):
    checks.append({'id': name, 'status': 'PASS' if passed else 'FAIL', 'detail': detail})


proof = json.loads((HERE / 'evidence/EXTENDED_COORDINATE_PROOF.json').read_bytes())
raw = (REPO / proof['sourcePath']).read_bytes()
check('MODERN_CITY_SOURCE_SHA', sha(raw) == proof['sourceSHA256'], proof['sourcePath'])
features = json.loads(raw)['features']
for claim in proof['claims']:
    matches = [row for row in features if row['properties'].get('ne_id') == claim['ne_id']]
    check('CITY_' + claim['id'], len(matches) == 1 and
          sha(canonical(matches[0])) == claim['featureCanonicalSHA256'] and
          matches[0]['geometry']['coordinates'] == claim['coordinates'],
          'Exact retained city feature and coordinate; no airport/port/traffic claim')

license_proof = json.loads((HERE / 'evidence/RETAINED_LICENSE_PROOF.json').read_bytes())
check('RETAINED_LICENSE_SHA', sha((REPO / license_proof['sourcePath']).read_bytes()) ==
      license_proof['sourceSHA256'], license_proof['sourcePath'])
archive_path = REPO / proof['GISArchive']['path']
check('RETAINED_GIS_ARCHIVE_SHA', sha(archive_path.read_bytes()) == proof['GISArchive']['sha256'],
      str(archive_path.relative_to(REPO)))
with zipfile.ZipFile(archive_path) as archive:
    context = json.loads(archive.read('europe_germany/RECOVERY_RUNTIME.json'))['nativePlan']['geometries']
    for name, country in [('NEW_REGION_JAPAN_NL', 'COUNTRY_JPN'),
                          ('NEW_REGION_AUSTRALIA_NL', 'COUNTRY_AUS')]:
        value = json.loads((HERE / 'examples' / (name + '.json')).read_bytes())
        facts = value['data']['scenes'][0]['facts']
        supplied = next(g['geometry'] for g in facts['geometries'] if g['id'] == country)
        original = next(g for g in context if g['id'] == country)
        check(name + '_COUNTRY_CONTEXT', supplied == {'type': original['geometry_type'],
              'coordinates': original['coordinates']}, 'Exact existing modern country context; not historical control')
        route = next(g['geometry'] for g in facts['geometries'] if g['id'] == 'DECLARED_CONNECTION')
        check(name + '_DECLARED_CONNECTION', route['coordinates'] ==
              [loc['anchor'] for loc in facts['locations']],
              'Explicit illustrative city connection follows only provided modern coordinates')

for new, old in [('AVIATION_EUROPE_NL', 'AVIATION_GERMANY'),
                 ('TRADE_SOUTH_AMERICA_NL', 'TRADE_CHILE'),
                 ('FICTIONAL_AFRICA_NL', 'FICTIONAL_NAMIBIA')]:
    value = json.loads((HERE / 'examples' / (new + '.json')).read_bytes())
    original = json.loads((OLD / 'examples' / (old + '.json')).read_bytes())
    first = deepcopy(value['data']['scenes'][0]['facts'])
    prior = deepcopy(original['scenes'][0]['facts'])
    first.pop('scene_timing', None)
    prior.pop('scene_timing', None)
    check(new + '_ORIGINAL_FIRST_SCENE_FACTS', first == prior,
          'Only display timing removed for exact new 90-frame display allocation')

for new, old in [('HISTORICAL_PARTIAL_SOURCE_NL', 'KOREAN_WAR_PARTIAL_FRONT_UNSUPPORTED'),
                 ('HISTORICAL_MISSING_CONTROL_NL', 'KOREAN_WAR_MISSING_CONTROL')]:
    value = json.loads((HERE / 'examples' / (new + '.json')).read_bytes())
    original = json.loads((OLD / 'examples' / (old + '.json')).read_bytes())
    check(new + '_ORIGINAL_DATA', value['data'] == original,
          'Historical facts, approximate geometry, sources and uncertainty unchanged')
registry = json.loads((HERE / 'evidence/RETAINED_HISTORY_REGISTRY.json').read_bytes())
check('HISTORY_REGISTRY_UNCHANGED', registry == json.loads((OLD / 'evidence/TRUSTED_EVIDENCE.json').read_bytes()),
      'No new trusted evidence or precision promotion')
legacy_proof = json.loads((HERE / 'evidence/LEGACY_PROBE_COORDINATE_PROOF.json').read_bytes())
for claim in legacy_proof['claims']:
    matches = [row for row in features if row['properties'].get('ne_id') == claim['ne_id']]
    check('LEGACY_PROBE_CITY_' + claim['id'], len(matches) == 1 and
          sha(canonical(matches[0])) == claim['featureCanonicalSHA256'] and
          matches[0]['geometry']['coordinates'] == claim['coordinates'],
          'Exact retained modern locality; no historical troop or transport claim')
for relative in ['examples/NEW_REGION_JAPAN_NL.json', 'examples/NEW_REGION_AUSTRALIA_NL.json',
                 'examples/negative/COUNTRY_COORDINATE_CONFLICT.json',
                 'examples/legacy-probes/nepal_himalaya.json', 'examples/legacy-probes/korean_peninsula.json']:
    value = json.loads((HERE / relative).read_bytes())
    facts = value['data']['scenes'][0]['facts']
    native = facts['native_context']
    supplied_countries = {row['country_id'] for row in facts['locations']}
    supplied_locations = {row['id'] for row in facts['locations']}
    supplied_geometry = {row['id'] for row in facts['geometries']}
    check('NATIVE_CONTEXT_' + Path(relative).stem,
          native['primary_country_id'] in supplied_countries and
          set(native['country_ids']) <= supplied_geometry and
          set(native['context_location_ids']) <= supplied_locations,
          'New authored native context references its actual provided country geometry and locations')
report = {'schema': 'WORLD_ENGINE_PRESENTATION_EXAMPLE_EVIDENCE_AUDIT_V2',
          'scope': 'ACTUAL_RETAINED_SOURCE_BYTES_AND_FIXTURE_DATA_ONLY_NO_RENDER',
          'checks': checks, 'summary': {'PASS': sum(x['status'] == 'PASS' for x in checks),
                                       'FAIL': sum(x['status'] == 'FAIL' for x in checks)},
          'networkRequests': 0, 'paidExecution': False}
report_name = sys.argv[1] if len(sys.argv) > 1 else 'EXAMPLE_EVIDENCE_AUDIT.json'
if not report_name.startswith('EXAMPLE_EVIDENCE_') or not report_name.endswith('.json') or '/' in report_name:
    raise ValueError('EXCLUSIVE_EVIDENCE_REPORT_NAME_REQUIRED')
target = HERE / 'reports' / report_name
with target.open('x') as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
    stream.write('\n')
print(json.dumps({'report': str(target), **report['summary']}))
raise SystemExit(1 if report['summary']['FAIL'] else 0)
