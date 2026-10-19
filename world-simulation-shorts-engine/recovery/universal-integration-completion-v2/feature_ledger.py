"""Evidence-driven completion ledger for the pinned 151 / 53 audit identities.

Read-only inputs are the published capability catalog, previous decisions and
root-produced CPU connection receipts. Counts are derived from accepted rows.
A source-selected or CPU-instrumented consumer is never GPU/output proof.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AUDIT_PATH = 'world-simulation-shorts-engine/docs/audits/knowledge-handoff-v2-20261019/CAPABILITY_CATALOG.json'
PRIOR_PATH = 'world-simulation-shorts-engine/recovery/universal-integration-v1/reports/FEATURE_DECISIONS_151.json'
AUDIT_SHA = '85f14ba4f52931b0f6248c173104529bc5b837e83655007b5140a2e2fba86861'
PRIOR_SHA = 'e7d93277df56e062057f9fdbd72c4d0df4b377a5deaaab839a6b1006cfe61e01'
COMPLETION_MANIFEST_PATH = 'world-simulation-shorts-engine/recovery/universal-integration-completion-v2/COMPLETION_FILES.json'
BASE_IMAGE_DIGEST = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
STATUSES = frozenset({'SUPPORTING', 'BLOCKED', 'UNVERIFIED', 'NOT_APPLICABLE'})
RELEVANCE = frozenset({'REQUIRED', 'SUPPORTING', 'UNRELATED'})
EXPOSURE = frozenset({'YES', 'INTERNAL_ONLY', 'NO', 'CONDITIONAL'})
ADDRESSABILITY = frozenset({'YES', 'CONDITIONAL', 'NO'})
SELECTION = frozenset({'YES', 'CONDITIONAL', 'NO'})
CONSUMERS = frozenset({'SOURCE_BOUND', 'CPU_INSTRUMENTED', 'NONE'})
RECEIPT_FIELDS = frozenset({'id', 'featureIds', 'implementationExists', 'studioV2Exposed',
    'sceneJSONAddressable', 'runtimeSelected', 'actualRendererConsumer', 'sourceFiles',
    'inputFields', 'factories', 'consumers', 'cpuTests', 'evidenceKind',
    'actualOutputProduced', 'blockingReasons', 'relevance', 'status', 'reason',
    'cpuReceipt', 'outputTrace'})


def _fail(code):
    raise ValueError(code)


def _json_bytes(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        _fail('LEDGER_PINNED_INPUT_SHA_MISMATCH')
    return json.loads(raw)


def load_inputs(repo=REPO):
    return (_json_bytes(repo / AUDIT_PATH, AUDIT_SHA),
            _json_bytes(repo / PRIOR_PATH, PRIOR_SHA))


def _public_source(record, repo):
    if not isinstance(record, dict) or set(record) != {'path', 'sha256'}:
        _fail('LEDGER_SOURCE_RECORD_INVALID')
    name, sha = record['path'], record['sha256']
    if (not isinstance(name, str) or not name.startswith('world-simulation-shorts-engine/')
            or '\\' in name or Path(name).is_absolute() or '..' in Path(name).parts
            or not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{64}', sha)):
        _fail('LEDGER_SOURCE_PATH_OR_SHA_INVALID')
    path = repo / name
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        _fail('LEDGER_SOURCE_FILE_UNAVAILABLE')
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        _fail('LEDGER_SOURCE_SHA_MISMATCH')
    return copy.deepcopy(record)


def _candidate_image(image, repo):
    """Accept an image identity only with checked, source-bound pull proof.

    A test may supply explicitly synthetic proof in its isolated fixture tree;
    that validates this admission contract and is never a real image claim.
    """
    if not isinstance(image, dict):
        _fail('LEDGER_UNVERIFIED_CANDIDATE_IMAGE_CANNOT_BE_CLAIMED')
    if image.get('state') in {'NOT_BUILT', 'NOT_VERIFIED'}:
        if set(image) != {'state', 'digest'} or image['digest'] is not None:
            _fail('LEDGER_UNVERIFIED_CANDIDATE_IMAGE_CANNOT_BE_CLAIMED')
        return copy.deepcopy(image)
    if (set(image) != {'state', 'digest', 'proof'}
            or image.get('state') != 'INDEPENDENT_PULL_VERIFIED'
            or not isinstance(image.get('digest'), str)
            or not re.fullmatch('sha256:[a-f0-9]{64}', image['digest'])):
        _fail('LEDGER_UNVERIFIED_CANDIDATE_IMAGE_CANNOT_BE_CLAIMED')
    proof_ref = _public_source(image['proof'], repo)
    try:
        proof = json.loads((repo / proof_ref['path']).read_bytes())
    except (ValueError, UnicodeError):
        _fail('LEDGER_CANDIDATE_IMAGE_PROOF_INVALID')
    expected = {'schema', 'result', 'independentPullVerified', 'sourceHashesVerified',
                'imageDigest', 'sourceManifestSHA256', 'baseDigest', 'sourceCommit'}
    if (not isinstance(proof, dict) or set(proof) != expected
            or proof.get('schema') != 'WORLD_ENGINE_COMPLETION_IMAGE_PROOF_V1'
            or proof.get('result') != 'PASS'
            or proof.get('independentPullVerified') is not True
            or proof.get('sourceHashesVerified') is not True
            or proof.get('imageDigest') != image['digest']
            or proof.get('baseDigest') != BASE_IMAGE_DIGEST
            or not isinstance(proof.get('sourceCommit'), str)
            or not re.fullmatch('[a-f0-9]{40}', proof['sourceCommit'])):
        _fail('LEDGER_CANDIDATE_IMAGE_PROOF_INVALID')
    manifest = repo / COMPLETION_MANIFEST_PATH
    if any(p.is_symlink() for p in (manifest, *manifest.parents)) or not manifest.is_file():
        _fail('LEDGER_CANDIDATE_SOURCE_MANIFEST_UNAVAILABLE')
    if proof.get('sourceManifestSHA256') != hashlib.sha256(manifest.read_bytes()).hexdigest():
        _fail('LEDGER_CANDIDATE_SOURCE_MANIFEST_MISMATCH')
    return copy.deepcopy(image)


def validate_connections(value, audit, *, repo=REPO):
    """Validate explicit public CPU evidence; do not trust arbitrary status flags."""
    if not isinstance(value, dict) or set(value) - {'schema', 'receipts', 'sourceCommit', 'candidateImage', 'testResult'}:
        _fail('LEDGER_CONNECTION_ENVELOPE_UNKNOWN_FIELD')
    if value.get('schema') != 'WORLD_ENGINE_COMPLETION_CONNECTION_RECEIPTS_V1':
        _fail('LEDGER_CONNECTION_SCHEMA_INVALID')
    image = value.get('candidateImage', {'state': 'NOT_BUILT', 'digest': None})
    _candidate_image(image, repo)
    receipts = value.get('receipts')
    if not isinstance(receipts, list):
        _fail('LEDGER_CONNECTION_RECEIPTS_REQUIRED')
    valid_ids = {f['id'] for f in audit['features']}
    found_ids, found_receipts, result = set(), set(), []
    for original in receipts:
        if not isinstance(original, dict) or set(original) - RECEIPT_FIELDS:
            _fail('LEDGER_CONNECTION_UNKNOWN_FIELD')
        receipt = copy.deepcopy(original)
        name = receipt.get('id')
        if not isinstance(name, str) or not re.fullmatch('[A-Za-z0-9_.-]{1,100}', name) or name in found_receipts:
            _fail('LEDGER_CONNECTION_ID_INVALID')
        found_receipts.add(name)
        ids = receipt.get('featureIds')
        if (not isinstance(ids, list) or not ids or len(ids) != len(set(ids))
                or any(i not in valid_ids for i in ids)):
            _fail('LEDGER_CONNECTION_FEATURE_ID_INVALID')
        if found_ids.intersection(ids):
            _fail('LEDGER_CONNECTION_FEATURE_REPEATED')
        found_ids.update(ids)
        checks = {'implementationExists': {'YES', 'NO', 'NOT_VERIFIED'},
                  'studioV2Exposed': EXPOSURE, 'sceneJSONAddressable': ADDRESSABILITY,
                  'runtimeSelected': SELECTION, 'actualRendererConsumer': CONSUMERS,
                  'evidenceKind': {'CPU_INSTRUMENTATION', 'SOURCE_STATIC'}}
        for field, allowed in checks.items():
            if receipt.get(field) not in allowed:
                _fail('LEDGER_CONNECTION_AXIS_INVALID')
        if receipt.get('actualOutputProduced') is not False:
            _fail('LEDGER_NO_OUTPUT_CLAIM_ALLOWED')
        if receipt.get('status') is not None and receipt['status'] not in STATUSES:
            _fail('LEDGER_NO_APPLIED_OR_UNKNOWN_STATUS')
        if receipt.get('relevance') is not None and receipt['relevance'] not in RELEVANCE:
            _fail('LEDGER_RELEVANCE_INVALID')
        if 'status' in receipt and (not isinstance(receipt.get('reason'), str) or len(receipt['reason']) < 30):
            _fail('LEDGER_RECLASSIFICATION_REASON_REQUIRED')
        files = receipt.get('sourceFiles')
        if not isinstance(files, list) or not files:
            _fail('LEDGER_SOURCE_EVIDENCE_REQUIRED')
        receipt['sourceFiles'] = [_public_source(f, repo) for f in files]
        for field in ('inputFields', 'factories', 'consumers', 'cpuTests'):
            if not isinstance(receipt.get(field), list):
                _fail('LEDGER_CONNECTION_TRACE_ARRAY_REQUIRED')
        for field in ('inputFields', 'factories', 'consumers'):
            if any(not isinstance(i, str) or not i.strip() for i in receipt[field]):
                _fail('LEDGER_CONNECTION_TRACE_TEXT_REQUIRED')
        tests = receipt['cpuTests']
        for test in tests:
            if (not isinstance(test, dict) or set(test) != {'name', 'result'}
                    or not isinstance(test['name'], str) or not test['name']
                    or test['result'] not in {'PASS', 'FAIL', 'SKIP', 'BLOCKED'}):
                _fail('LEDGER_CPU_TEST_RECORD_INVALID')
        instrumented = receipt['actualRendererConsumer'] == 'CPU_INSTRUMENTED'
        if instrumented and (receipt['evidenceKind'] != 'CPU_INSTRUMENTATION'
                or not tests or any(t['result'] != 'PASS' for t in tests)
                or not receipt['factories'] or not receipt['consumers']):
            _fail('LEDGER_CPU_INSTRUMENTATION_PROOF_REQUIRED')
        if receipt.get('status') == 'SUPPORTING' and any(t['result'] in {'FAIL', 'BLOCKED'} for t in tests):
            _fail('LEDGER_SUPPORTING_CANNOT_HIDE_FAILED_TESTS')
        blockers = receipt.get('blockingReasons', [])
        if (not isinstance(blockers, list) or any(not isinstance(b, dict)
                or set(b) != {'code', 'reason'} or not b['code'] or not b['reason'] for b in blockers)):
            _fail('LEDGER_BLOCKER_RECORD_INVALID')
        if blockers and receipt.get('status') not in (None, 'BLOCKED'):
            _fail('LEDGER_BLOCKERS_CANNOT_BE_HIDDEN')
        if 'cpuReceipt' in receipt:
            receipt['cpuReceipt'] = _public_source(receipt['cpuReceipt'], repo)
        trace = receipt.get('outputTrace', {'state': 'NOT_PRODUCED'})
        if not isinstance(trace, dict) or trace.get('state') != 'NOT_PRODUCED':
            _fail('LEDGER_NO_OUTPUT_CLAIM_ALLOWED')
        receipt['outputTrace'] = trace
        result.append(receipt)
    return result


def _original_identity(audit, previous):
    features = audit.get('features', [])
    prior = previous.get('features', [])
    ids = [f.get('id') for f in features]
    if len(ids) != 151 or len(set(ids)) != len(ids):
        _fail('LEDGER_151_DISTINCT_IDS_REQUIRED')
    if {f.get('id') for f in prior} != set(ids) or len(prior) != len(ids):
        _fail('LEDGER_PRIOR_ID_SET_MISMATCH')
    by_id = {f['id']: f for f in prior}
    for original in features:
        old = copy.deepcopy(by_id[original['id']])
        old.pop('integrationReview', None)
        if old != original:
            _fail('LEDGER_PRIOR_AUDIT_IDENTITY_MISMATCH')
    if sum(f['classification'] == 'NOT_WIRED' for f in features) != 53:
        _fail('LEDGER_53_UNWIRED_REQUIRED')
    return by_id


def _status(prior, receipt):
    if not receipt:
        return prior['status'], 'No completion connection receipt was supplied. ' + prior['reason']
    if receipt.get('blockingReasons'):
        return 'BLOCKED', '; '.join(b['reason'] for b in receipt['blockingReasons'])
    if 'status' in receipt:
        return receipt['status'], receipt['reason']
    if prior['status'] in {'BLOCKED', 'NOT_APPLICABLE'}:
        return prior['status'], 'CPU connection does not by itself remove the prior data/semantic decision. ' + prior['reason']
    if receipt['cpuTests'] and all(t['result'] == 'PASS' for t in receipt['cpuTests']):
        return 'SUPPORTING', 'The declared source-bound CPU tests passed for this supporting connection; no GPU/output evidence is claimed.'
    return 'UNVERIFIED', 'Source connection exists but a passing feature-specific CPU consumer receipt is not available.'


def build_ledger(audit, previous, connections, *, repo=REPO):
    previous_by_id = _original_identity(audit, previous)
    receipts = validate_connections(connections, audit, repo=repo)
    by_feature = {feature_id: receipt for receipt in receipts for feature_id in receipt['featureIds']}
    ledger = []
    for original in audit['features']:
        row = copy.deepcopy(original)
        prior = previous_by_id[row['id']]['integrationReview']
        receipt = by_feature.get(row['id'])
        status, reason = _status(prior, receipt)
        absent = row['classification'] == 'NOT_IMPLEMENTED'
        row['implementationExists'] = receipt['implementationExists'] if receipt else ('NO' if absent else row['axes']['SOURCE_EXISTS'])
        row['studioV2Exposed'] = receipt['studioV2Exposed'] if receipt else 'NOT_VERIFIED'
        row['sceneJSONAddressable'] = receipt['sceneJSONAddressable'] if receipt else 'NOT_VERIFIED'
        row['runtimeSelected'] = receipt['runtimeSelected'] if receipt else 'NOT_VERIFIED'
        row['actualRendererConsumer'] = receipt['actualRendererConsumer'] if receipt else 'NOT_VERIFIED'
        row['cpuProof'] = ('PASS' if receipt and receipt['cpuTests'] and all(t['result'] == 'PASS' for t in receipt['cpuTests'])
                           else 'NOT_VERIFIED_FOR_COMPLETION')
        row['gpuProof'] = 'NOT_VERIFIED'
        row['relevantToKoreanWar'] = receipt.get('relevance', prior['relevance']) if receipt else prior['relevance']
        row['status'] = status
        row['reason'] = reason
        row['canonicalId'] = prior['canonicalId']
        row['aliasGroup'] = copy.deepcopy(prior['aliasGroup'])
        row['previousIntegrationReview'] = copy.deepcopy(prior)
        row['completionEvidence'] = {
            'connectionReceiptId': receipt['id'] if receipt else None,
            'sourceFiles': copy.deepcopy(receipt['sourceFiles']) if receipt else [],
            'inputFields': copy.deepcopy(receipt['inputFields']) if receipt else [],
            'factories': copy.deepcopy(receipt['factories']) if receipt else [],
            'consumers': copy.deepcopy(receipt['consumers']) if receipt else [],
            'cpuTests': copy.deepcopy(receipt['cpuTests']) if receipt else [],
            'baselineEvidenceIds': [e['evidenceId'] for e in row['evidence']],
            'traceKind': receipt['evidenceKind'] if receipt else 'PRESERVED_AUDIT_ONLY',
            'blockingReasons': copy.deepcopy(receipt.get('blockingReasons', [])) if receipt else [],
            'outputTrace': copy.deepcopy(receipt['outputTrace']) if receipt else {'state': 'NOT_PRODUCED'},
            'actualOutputProduced': False,
        }
        if receipt and receipt.get('cpuReceipt'):
            row['completionEvidence']['cpuReceipt'] = copy.deepcopy(receipt['cpuReceipt'])
        ledger.append(row)
    summary = dict(sorted(Counter(r['status'] for r in ledger).items()))
    return {
        'schema': 'WORLD_ENGINE_COMPLETION_FEATURE_LEDGER_V1',
        'baselineCatalog': {'path': AUDIT_PATH, 'sha256': AUDIT_SHA, 'sourceCommit': audit['sourceCommit']},
        'previousDecisions': {'path': PRIOR_PATH, 'sha256': PRIOR_SHA},
        'parentOperatingImage': copy.deepcopy(audit['operatingImage']),
        'candidateImage': copy.deepcopy(connections.get('candidateImage', {'state': 'NOT_BUILT', 'digest': None})),
        'axisDefinitions': {
            'implementationExists': 'Feature implementation availability; old source evidence and new source-bound connection receipts remain separate.',
            'studioV2Exposed': 'YES is a strict supported input; INTERNAL_ONLY is deliberately not a public knob; CONDITIONAL requires admitted data. NOT_VERIFIED means no new receipt.',
            'sceneJSONAddressable': 'Explicit source-backed Scene mapping. It never authorizes arbitrary edits to the frozen parent Scene.',
            'runtimeSelected': 'YES/CONDITIONAL refer to source/config selection, never observed GPU execution.',
            'actualRendererConsumer': 'SOURCE_BOUND is a static consumer edge; CPU_INSTRUMENTED means factory/consumer CPU instrumentation, never a WebGL draw.',
            'cpuProof': 'PASS is derived only from named passing CPU tests in a validated source-hash connection receipt.',
            'gpuProof': 'No new GPU/render command is run. All records stay NOT_VERIFIED.',
            'relevantToKoreanWar': 'REQUIRED/SUPPORTING/UNRELATED are source-fixture relevance; all 151 need review, not on-screen use.',
        },
        'featureCount': len(ledger),
        'previouslyUnwiredCount': sum(r['classification'] == 'NOT_WIRED' for r in ledger),
        'canonicalRecordGroups': len({r['canonicalId'] for r in ledger}),
        'statusCounts': summary,
        'axisCounts': {axis: dict(sorted(Counter(r[axis] for r in ledger).items())) for axis in ('implementationExists', 'studioV2Exposed', 'sceneJSONAddressable', 'runtimeSelected', 'actualRendererConsumer', 'cpuProof', 'gpuProof', 'relevantToKoreanWar')},
        'connectionReceiptCount': len(receipts),
        'featuresWithConnectionReceipts': len(by_feature),
        'all151Reviewed': True, 'all53UnwiredReviewed': True,
        'actualOutputAppliedCount': 0, 'gpuRenderingVerified': False,
        'all151RequiredOnScreen': False, 'blindAPIExposureAllowed': False,
        'overallIntegrationPass': False,
        'requiredBlockedIds': [r['id'] for r in ledger if r['relevantToKoreanWar'] == 'REQUIRED' and r['status'] == 'BLOCKED'],
        'requiredUnverifiedIds': [r['id'] for r in ledger if r['relevantToKoreanWar'] == 'REQUIRED' and r['status'] == 'UNVERIFIED'],
        'full80sRenderAllowed': False,
        'features': ledger,
    }


def unwired_ledger(ledger):
    rows = [copy.deepcopy(r) for r in ledger['features'] if r['classification'] == 'NOT_WIRED']
    return {'schema': 'WORLD_ENGINE_COMPLETION_UNWIRED_LEDGER_V1',
            'baselineCatalog': copy.deepcopy(ledger['baselineCatalog']),
            'parentOperatingImage': copy.deepcopy(ledger['parentOperatingImage']),
            'candidateImage': copy.deepcopy(ledger['candidateImage']),
            'count': len(rows), 'allReviewed': True,
            'statusCounts': dict(sorted(Counter(r['status'] for r in rows).items())),
            'actualOutputAppliedCount': 0, 'features': rows}


def ledger_csv(features):
    fields = ['id', 'canonicalId', 'aliasGroup', 'domain', 'name', 'originalClassification',
              'implementationExists', 'studioV2Exposed', 'sceneJSONAddressable', 'runtimeSelected',
              'actualRendererConsumer', 'cpuProof', 'gpuProof', 'relevantToKoreanWar', 'status',
              'reason', 'connectionReceiptId', 'inputFields', 'factories', 'consumers',
              'sourceFiles', 'baselineSourceEvidence', 'originalAxes', 'outputTrace']
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for r in features:
        e = r['completionEvidence']
        item = {field: r[field] for field in fields if field in r}
        item.update({'aliasGroup': ';'.join(r['aliasGroup']), 'originalClassification': r['classification'],
            'connectionReceiptId': e['connectionReceiptId'],
            **{field: json.dumps(e[field], ensure_ascii=False, separators=(',', ':')) for field in ('inputFields', 'factories', 'consumers', 'sourceFiles', 'outputTrace')},
            'baselineSourceEvidence': ';'.join(f"{v['path']}:{v['startLine']}:{v['symbol']}" for v in r['evidence']),
            'originalAxes': json.dumps(r['axes'], ensure_ascii=False, separators=(',', ':'))})
        writer.writerow(item)
    return output.getvalue()


def write_reports(connections_path, *, output=HERE / 'reports', repo=REPO):
    audit, prior = load_inputs(repo)
    connections = json.loads(connections_path.read_bytes())
    ledger = build_ledger(audit, prior, connections, repo=repo)
    unwired = unwired_ledger(ledger)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in (('FEATURE_LEDGER_151', ledger), ('UNWIRED_LEDGER_53', unwired)):
        (output / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (output / (name + '.csv')).write_text(ledger_csv(value['features']), encoding='utf-8')
    return ledger


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connections', type=Path, default=HERE / 'reports/CONNECTION_RECEIPTS.json')
    parser.add_argument('--output', type=Path, default=HERE / 'reports')
    args = parser.parse_args()
    value = write_reports(args.connections, output=args.output)
    print(json.dumps({'features': value['featureCount'], 'unwired': value['previouslyUnwiredCount'],
                      'statusCounts': value['statusCounts'], 'connections': value['connectionReceiptCount'],
                      'featuresWithReceipts': value['featuresWithConnectionReceipts'],
                      'actualOutputAppliedCount': 0, 'gpuRenderingVerified': False}, ensure_ascii=False))
