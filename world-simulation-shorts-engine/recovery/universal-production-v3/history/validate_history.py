"""Focused fixture/provenance consistency check; no network or historical proof claim."""
from pathlib import Path
import datetime
import hashlib
import json

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    chronology = json.loads((HERE / 'CHRONOLOGY_12.json').read_bytes())
    geometry = json.loads((HERE / 'EXISTING_GEOMETRY_MANIFEST.json').read_bytes())
    ownership = json.loads((HERE / 'AREA_OWNERSHIP.json').read_bytes())
    access = json.loads((HERE / 'OFFICIAL_RETRIEVAL_ATTEMPTS.json').read_bytes())
    checks = []
    source = chronology['sourceManifest']
    for path_key, hash_key in [('factsPath', 'factsSHA256'), ('referencesPath', 'referencesSHA256'),
                               ('participationPolicyPath', 'participationPolicySHA256')]:
        path = (ENGINE / source[path_key]).resolve()
        assert path.is_relative_to(ENGINE.resolve()) and path.is_file()
        assert sha(path) == source[hash_key], path_key
    checks.append('EXISTING_SOURCE_BYTES_SHA_MATCH')
    facts = json.loads((ENGINE / source['factsPath']).read_bytes())
    raw_geometry = {row['id']: row['geometry'] for row in facts['geometries']}
    assert geometry['newGeometryCreated'] is False and len(geometry['states']) == 5
    for state in geometry['states']:
        for row in state['geometryHashes']:
            encoded = json.dumps(raw_geometry[row['id']], ensure_ascii=False, separators=(',', ':')).encode()
            assert hashlib.sha256(encoded).hexdigest() == row['sha256']
    checks.append('FIVE_ORIGINAL_GEOMETRY_HASHES_PRESERVED')
    stages = chronology['stages']
    assert len(stages) == 12 and [row['stageNumber'] for row in stages] == list(range(1, 13))
    assert len({row['eventId'] for row in stages}) == 12
    checks.append('TWELVE_DISTINCT_REQUESTED_CHAPTER_RECORDS')
    source_ids = {row['id'] for row in source['sourceRecords']}
    for row in stages:
        d = row['date']
        if d['value'] is not None:
            datetime.date.fromisoformat(d['value'])
        assert d['officialBodyProofAvailable'] is False
        assert set(d['sourceIds']).issubset(source_ids)
    assert stages[6]['date']['value'] == '1950-10-25'
    assert stages[5]['presentationPolicy']['dateWindow']['end'] < stages[6]['date']['value']
    checks.append('QUALIFIED_DATES_AND_OVERLAP_POLICY_EXPLICIT')
    state_map = {row['stateId']: row for row in geometry['states']}
    for row in stages:
        g = row['geometryEvidence']
        assert g['newGeometryAllowed'] is False
        if g['existingStateId'] is None:
            assert g['geometryRefs'] == []
        else:
            assert g['geometryRefs'] == state_map[g['existingStateId']]['geometryRefs']
        assert row['presentationPolicy']['onScreenSnapshotDateRequired'] is True
        assert row['presentationPolicy']['noExactEventFrontClaim'] is True
        assert set(row['presentationPolicy']['geometryStateIds']).issubset(state_map)
    assert stages[5]['presentationPolicy']['geometryStateIds'] == ['BUSAN']
    assert stages[6]['presentationPolicy']['geometryStateIds'] == ['BUSAN']
    assert stages[7]['presentationPolicy']['geometryStateIds'] == ['NORTH_ADVANCE', 'SEOUL_WITHDRAWAL']
    assert stages[10]['geometryEvidence']['localFrontChangeAnimationAdmitted'] is False
    checks.append('NO_UNSUPPLIED_GEOMETRY_OR_FUTURE_FRONT_SUBSTITUTION')
    styles = ownership['areaStyles']
    scene = json.loads((ENGINE / 'recovery/planner-scene-json-v1/fixtures/SCENE_PLAN.json').read_bytes())
    area_map = {row['id']: row for row in scene['areas']}
    assert len(styles) == 5
    for style in styles:
        assert area_map[style['areaId']]['geometry_ref'] == style['sourceGeometryRef']
        assert style['enemyComplementAdmitted'] is False and style['measuredMilitaryControl'] is False
    assert styles[0]['factionId'] == 'ROK'
    assert all(style['factionId'] == 'ROK_UN_ALLIED' for style in styles[1:])
    checks.append('SOURCE_QUALIFIED_AREA_OWNERSHIP_WITHOUT_ENEMY_COMPLEMENT')
    assert chronology['officialSourceBodiesVerified'] is False
    assert chronology['newOriginalOfficialTextRetrieved'] == 0
    assert all(row['officialBodyRetrieved'] is False and row['officialBodySHA256'] is None for row in access['attempts'])
    assert access['alternateProxyOrCIBypassAttempted'] is False
    checks.append('RETRIEVAL_BLOCK_AND_NO_BODY_PROOF_TRUTHFUL')
    assert chronology['newHistoricalFrontsCreated'] == 0
    assert all(row['unitEvidence']['newUnitPositionAllowed'] is False for row in stages)
    checks.append('NO_NEW_FRONT_OR_UNIT_COORDINATES')
    result = {'schema': 'WORLD_ENGINE_V3_HISTORY_CONSISTENCY_VALIDATION_V1',
              'status': 'PASS', 'checks': [{'name': name, 'status': 'PASS'} for name in checks],
              'officialSourceVerification': 'BLOCKED_PROXY_CONNECT_403',
              'historicalDateBasis': 'CURATED_REFERENCE_ONLY_NOT_NEW_BODY_VERIFICATION',
              'exactHistoricalFrontsVerified': False, 'gpuExecuted': False,
              'files': {p.name: sha(p) for p in sorted(HERE.glob('*.json')) if p.name != 'VALIDATION.json'}}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
