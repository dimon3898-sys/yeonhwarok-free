"""Compile declarative, source-qualified chronology edits; never infer ownership."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT.parents[1]
REPO = ROOT.parents[2]


def source_bytes(relative):
    name = Path(relative)
    if name.is_absolute() or '..' in name.parts:
        raise ValueError('CANONICAL_REPOSITORY_SOURCE_REQUIRED')
    repository_path = name if name.parts[0] == ENGINE.name else Path(ENGINE.name) / name
    file = REPO / repository_path
    if file.is_file() and not file.is_symlink():
        return file.read_bytes()
    # Sparse checkout is not missing history data: read exact immutable Git bytes
    # without altering the protected checkout or substituting another fixture.
    return subprocess.check_output(['git', 'show', 'ede3fa2b31a71a32f1dee66040f8100cee0d9d90:' + repository_path.as_posix()], cwd=REPO)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def build(plan_file):
    raw = Path(plan_file).read_bytes()
    edits_raw = (ROOT / 'fixtures/HISTORY_EDITS.json').read_bytes()
    edits = json.loads(edits_raw)
    if digest(raw) != edits['sourcePlanSHA256']:
        raise ValueError('SOURCE_HASH_MISMATCH')
    plan = json.loads(raw)
    originals = plan['productionV3']['eventChapters']
    if len(originals) != len(edits['chapterEdits']):
        raise ValueError('HISTORY_EXACT_CHAPTER_SET_REQUIRED')
    by_id = {row['chapterId']: row for row in originals}
    chapters = []
    for edit in edits['chapterEdits']:
        original = by_id[edit['chapterId']]
        chapters.append({**edit, 'eventId': original['eventId'],
                         'startFrame': original['startFrame'], 'endFrame': original['endFrame'],
                         'controlStartState': None, 'controlEndState': None,
                         'truthKind': 'unknown', 'fullControlStatus': 'BLOCKED_FULL_CONTROL_GEOMETRY_MISSING',
                         'historicalUnits': [], 'sourceIds': ['MASTER_OFFICIAL_CHRONOLOGY_REVIEW'],
                         'originalTitle': original['title'], 'originalDisplayLabel': original['displayLabel']})
    next_frame, prior_date, schedule = 0, '', []
    fronts_raw = (ENGINE / 'recovery/verified-front-data-v4-recovery/FRONT_PROFILE.json').read_bytes()
    fronts = json.loads(fronts_raw)
    catalog = {'MASTER_OFFICIAL_CHRONOLOGY_REVIEW': edits['chronologyBasis']}
    additional_file = ROOT / 'source-review/ADDITIONAL_FRONT_BINDINGS.json'
    additional = json.loads(additional_file.read_bytes()).get('fronts', []) if additional_file.exists() else []
    for item in edits['sourceSchedule']:
        row = dict(item)
        if row['startFrame'] != next_frame or row['endFrame'] <= next_frame:
            raise ValueError('HISTORY_CONTIGUOUS_HALF_OPEN_SCHEDULE_REQUIRED')
        chapter = next((x for x in chapters if x['startFrame'] <= next_frame and row['endFrame'] <= x['endFrame']), None)
        if chapter is None:
            raise ValueError('HISTORY_SOURCE_CHAPTER_BINDING_REQUIRED')
        row['chapterId'] = chapter['chapterId']
        row['truthKind'] = {'UNKNOWN': 'unknown', 'SCHEMATIC_HELD_CORE': 'schematic', 'OBSERVED_PARTIAL_FRONT': 'observed'}[row['kind']]
        date = row['sourceDate']
        if date and date < prior_date:
            raise ValueError('HISTORY_SOURCE_DATE_REGRESSION')
        prior_date = date or prior_date
        if row['kind'] == 'UNKNOWN':
            if row['stateId'] is not None:
                raise ValueError('HISTORY_UNKNOWN_MUST_BE_NULL_NOT_PREVIOUS_STATE')
            row.update(sourceIds=[], missingReason='EVENT_SPECIFIC_CONTROL_AND_FRONT_SOURCE_MISSING',
                       visibleQualifier='전선·점령 자료 없음')
        elif row['kind'] == 'OBSERVED_PARTIAL_FRONT':
            extra = next((x for x in additional if x['frontId'] == row['stateId']), None)
            if extra is not None:
                geo_path = ROOT / extra['sourceFile']
                if digest(geo_path.read_bytes()) != extra['geoJsonSha256'] or extra['mapDate'] != date:
                    raise ValueError('ADDITIONAL_FRONT_ACTUAL_SOURCE_SHA_OR_DATE_MISMATCH')
                if extra.get('runtimeAdmission') != 'QUALIFIED_SOURCE_REVIEW_ONLY' or extra.get('fullControlPolygon') is not False:
                    raise ValueError('ADDITIONAL_FRONT_EXPLICIT_SOURCE_ONLY_REVIEW_REQUIRED')
                geo = json.loads(geo_path.read_bytes())
                expected_geometry = {'type': 'MultiLineString', 'coordinates': [x['geometry']['coordinates'] for x in geo['features']]}
                if extra.get('geometry') != expected_geometry:
                    raise ValueError('ADDITIONAL_FRONT_SOURCE_COORDINATES_CHANGED')
                for proof in [extra['source']['registrationReport'], extra['source']['supportedTraceReport'], extra['source']['sourcePixelTrace']]:
                    if digest((ROOT / proof['path']).read_bytes()) != proof['sha256']:
                        raise ValueError('ADDITIONAL_FRONT_REGISTRATION_OR_TRACE_SHA_MISMATCH')
                row.update(sourceIds=[extra['frontId']], visibleQualifier=date.replace('-', '.') + ' 근사 부분선')
                catalog[extra['frontId']] = {**extra, 'truthKind': 'observed',
                    'renderConsumer': 'DIRECTOR_ADDITIONAL_PARTIAL_FRONT'}
                schedule.append(row)
                next_frame = row['endFrame']
                continue
            front = next(x for x in fronts['fronts'] if x['frontId'] == row['stateId'])
            geo = ENGINE / 'recovery/verified-front-data-v4-recovery' / front['sourceFile']
            if digest(geo.read_bytes()) != front['geoJsonSha256'] or front['mapDate'] != date:
                raise ValueError('ARCHIVAL_FRONT_ACTUAL_SOURCE_SHA_OR_DATE_MISMATCH')
            row.update(sourceIds=[front['frontId']], visibleQualifier=date.replace('-', '.') + ' 부분 전선')
            catalog[front['frontId']] = {**front, 'truthKind': 'observed', 'fullControlPolygon': False,
                                       'originalProjection': 'UNKNOWN', 'outputCRS': 'EPSG:4326',
                                       'positionAccuracy': 'UNKNOWN_NOT_CERTIFIED'}
        else:
            state = next(x for x in plan['legacyScenePlan']['time_steps'] if x['id'] == row['stateId'])
            binding = next(x for x in plan['productionV3']['visualBindings']['areaStyles'] if x['sourceStateId'] == row['stateId'])
            row.update(sourceIds=[row['stateId']], visibleQualifier=date.replace('-', '.') + ' 도식')
            proof = binding['sourceProof']
            if digest(source_bytes(proof['factsPath'])) != proof['factsSHA256']:
                raise ValueError('SCHEMATIC_FACTS_ACTUAL_SHA_MISMATCH')
            catalog[row['stateId']] = {'stateId': row['stateId'], 'truthKind': 'schematic',
                'sourceFrame': row['sourceFrame'], 'sourceDate': date, 'fullControlPolygon': False,
                'ownerMeaning': 'AUTHOR_SUPPLIED_ALLIED_HELD_CORE_ONLY', 'enemyComplementAdmitted': False,
                'sourceProof': proof, 'areaIds': state['area_ids'], 'frontIds': state['front_line_ids']}
        schedule.append(row)
        next_frame = row['endFrame']
    if next_frame != plan['totalFrames']:
        raise ValueError('HISTORY_EXACT_TOTAL_FRAMES_REQUIRED')
    profile = {'schema': 'WORLD_ENGINE_QUALIFIED_EVENT_PROFILE_V2', 'version': 2,
        'subjectId': edits['subjectId'], 'sourcePlanSHA256': digest(raw), 'editsSHA256': digest(edits_raw),
        'totalFrames': plan['totalFrames'], 'fps': plan['fps'], 'factions': edits['factions'],
        'presentation': edits['presentation'],
        'locations': [{**x, 'role': 'GEOGRAPHIC_CONTEXT_ONLY', 'troopPosition': False} for x in plan['legacyScenePlan']['locations']],
        'chapters': chapters, 'sourceSchedule': schedule, 'fullControlStates': [], 'controlTransitions': [],
        'audio': {'enabled': False, 'gain': 0, 'cues': [], 'status': 'BLOCKED_AUDIO_SEMANTIC_REVIEW'},
        'markerEvidence': [], 'noUnknownComplement': True, 'noSilentPreviousSnapshotFallback': True}
    for file in sorted((ROOT / 'source-review').glob('*_COORDINATE_RECEIPT.json')):
        receipt = json.loads(file.read_bytes())
        if receipt.get('status') != 'AVAILABLE_GEOGRAPHIC_CONTEXT_ONLY' or receipt.get('geometry', {}).get('type') != 'Point':
            raise ValueError('GEOGRAPHIC_CONTEXT_POINT_RECEIPT_REQUIRED')
        if digest(source_bytes(receipt['sourcePath'])) != receipt['sourceSHA256']:
            raise ValueError('GEOGRAPHIC_CONTEXT_ORIGINAL_SOURCE_HASH_MISMATCH')
        if any(x['id'] == receipt['locationId'] for x in profile['locations']):
            raise ValueError('GEOGRAPHIC_CONTEXT_DUPLICATE_LOCATION')
        profile['locations'].append({'id': receipt['locationId'], 'label': receipt['name'],
            'anchor': receipt['geometry']['coordinates'], 'role': 'GEOGRAPHIC_CONTEXT_ONLY', 'troopPosition': False,
            'sourceReceipt': file.relative_to(ROOT).as_posix(), 'sourceReceiptSHA256': digest(file.read_bytes())})
    source_catalog = {'schema': 'WORLD_ENGINE_HISTORY_SOURCE_CATALOG_V2', 'version': 2,
        'sourcePlanSHA256': digest(raw), 'originalFrontProfileSHA256': digest(fronts_raw),
        'sources': catalog, 'licensePolicy': 'Original per-source policy retained; no original restricted PDF redistribution',
        'overallCartographicAccuracy': 'UNKNOWN_NOT_CERTIFIED'}
    report = {'schema': 'ASTRA_V2_P0_HISTORY_MAPPING_V1', 'mappingStatus': 'PASS_SOURCE_MAPPING_FIX_ONLY',
        'sourceAcquisitionStatus': 'PARTIAL_SEE_P0_SOURCE_ACQUISITION', 'originalChapterIdsAndFramesPreserved': True,
        'sourceDatesMonotonic': True, 'busanActiveOutsideDefenseChapter': False,
        'fullControlStatesAvailable': 0, 'fullHistoricalControlAndMorphReady': False,
        'unknownSourceFrames': sum(x['endFrame']-x['startFrame'] for x in schedule if x['kind']=='UNKNOWN'),
        'schematicHeldCoreFrames': sum(x['endFrame']-x['startFrame'] for x in schedule if x['kind']=='SCHEMATIC_HELD_CORE'),
        'observedPartialFrontFrames': sum(x['endFrame']-x['startFrame'] for x in schedule if x['kind']=='OBSERVED_PARTIAL_FRONT'),
        'historicalUnitsInvented': False, 'sourceGeometryChanged': False, 'originalSourcePlanChanged': False,
        'displayChanges': [{'chapterId': x['chapterId'], 'title': x['title'], 'displayLabel': x['displayLabel']} for x in chapters],
        'blockingReasons': ['FULL_CONTROL_GEOMETRY_MISSING', 'CONTROL_TRANSITION_EVIDENCE_MISSING',
                            'HISTORICAL_UNIT_COORDINATE_EVIDENCE_MISSING'],
        'visualQualityApproved': False}
    return profile, source_catalog, report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--plan-file', required=True)
    args = parser.parse_args()
    profile, catalog, report = build(args.plan_file)
    for name, value in [('fixtures/HISTORY_EVENT_PROFILE_V2.json', profile),
                        ('fixtures/HISTORY_SOURCE_CATALOG.json', catalog), ('reports/P0_HISTORY_MAPPING.json', report)]:
        (ROOT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))
