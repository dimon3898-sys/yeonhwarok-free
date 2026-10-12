#!/usr/bin/env python3
"""Read-only V5 final storage and clean-reproduction verification.

This endpoint never changes, installs, builds or renders the engine. Candidate
metadata remains historical. A final result requires --require-persisted and
actual committed final evidence; a precommit inspection cannot complete a Gate.
"""
import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
import re
import subprocess
from pathlib import Path


CANDIDATE = '941860391aa740772f822f18a972aeeca20a4a7f'
ORIGIN = 'https://github.com/dimon3898-sys/yeonhwarok-free.git'
V5 = 'world-simulation-shorts-engine/recovery/v5'
FINAL = V5 + '/manifests/final/'
EVIDENCE = V5 + '/evidence/final/'
BASELINE = FINAL + 'BASELINE_MANIFEST.json'
HASHES = FINAL + 'FINAL_HASH_MANIFEST.json'
RECEIPT = EVIDENCE + 'CLEAN_REPRODUCTION_RECEIPT.json'
SECRET = EVIDENCE + 'SECRET_SCAN.json'
SELF = 'tools/validate_v5_final.py'
VERIFICATION_ONLY = 'world-simulation-shorts-engine/recovery/v4/review/reproduced-final-hold.png'
POLICY = FINAL + 'PERMANENT_GATE_POLICY.md'
GOLDEN = 'fe0bc9666ccb61c36d9b428abc29051a6d51e10c81777d7e56f6fb309f2e9673'
GOLDEN_RGBA = 'cee0e480f1a0941f13d7bbe675952abe5a3bef53dd0bcc44c001f856982e7376'
MP4 = '2855d69924af7db00ac1f8182de0ca898f5d5aeb72d9f21ddf6471488e3db64d'
CONDITIONS = ('SOURCE_PERSISTED', 'ASSETS_PERSISTED', 'HASH_MANIFEST_PASS',
              'DEPENDENCY_MANIFEST_PASS', 'IMPORT_MANIFEST_PASS',
              'NO_REQUIRED_TEMP_FILES', 'CLEAN_ENV_REPRODUCIBLE')


def load_candidate(repo):
    spec = importlib.util.spec_from_file_location('v5_frozen_candidate', repo / 'tools/validate_v5_candidate.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(repo, require_persisted=False):
    candidate = load_candidate(repo)
    helper = candidate.helpers()
    legacy = helper.legacy(repo)
    errors, checks, checked = [], {}, {}

    def require(value, code):
        if not value:
            raise ValueError(code)

    def document(path):
        return json.loads(legacy.safe_file(repo, path).read_text())

    def actual(path):
        if path not in checked:
            checked[path] = legacy.hash_file(legacy.safe_file(repo, path))
        return checked[path]

    def phase(name, action):
        try:
            action()
            checks[name] = 'PASS'
        except (OSError, ValueError, KeyError, TypeError, IndexError,
                subprocess.SubprocessError, ImportError) as exc:
            checks[name] = 'FAIL'
            code = str(exc) if isinstance(exc, ValueError) and re.fullmatch('[A-Z0-9_]+', str(exc)) else 'EVIDENCE_OR_INPUT_INVALID'
            errors.append({'check': name, 'code': code})

    baseline, hashes, receipt, secret = {}, {}, {}, {}
    candidate_report, rows, paths = {}, {}, set()

    def documents():
        nonlocal baseline, hashes, receipt, secret, rows
        baseline, hashes, receipt, secret = map(document, (BASELINE, HASHES, RECEIPT, SECRET))
        require(hashes['schema'] == 1 and hashes['approved_candidate_commit'] == CANDIDATE,
                'FINAL_HASH_SCHEMA_OR_APPROVED_COMMIT_DIFFERS')
        for row in hashes['files']:
            path = row['path']
            require(path not in rows and path not in (BASELINE, HASHES), 'FINAL_HASH_CYCLE_OR_DUPLICATE')
            require(actual(path) == {'sha256': row['sha256'], 'bytes': row['bytes']}, 'FINAL_BOUND_FILE_HASH_DIFFERS')
            rows[path] = row
        require(baseline['baseline_name'] == 'V5_CAMERA_DIRECTOR_FINAL_BASELINE' and
                baseline['development_branch'] == 'development/camera-director-v5-20261012' and
                baseline['commit'] == CANDIDATE and baseline['commit_role'] == 'APPROVED_RUNTIME_SOURCE' and
                baseline['user_video_review'] == 'PASS', 'FINAL_BASELINE_IDENTITY_OR_APPROVAL_INVALID')
        require(baseline['context_algorithm_version'] in
                ('CAMERA_DIRECTOR_V5', 'MINIMUM_PRIMARY_EVENT_CONTEXT_V5'),
                'FINAL_CONTEXT_ALGORITHM_VERSION_INVALID')
        require(baseline['permanent_gate_result'] == 'V5_GATE_COMPLETE' and
                baseline['permanent_conditions'] == dict.fromkeys(CONDITIONS, 'PASS'), 'FINAL_GATE_DECLARATION_INVALID')
        parent = baseline['parent_v4_baseline']
        require(isinstance(parent, dict) and parent.get('baseline_name', parent.get('name')) ==
                'V4_RECOVERED_EQUIVALENT_BASELINE' and parent.get('source_commit', parent.get('commit')) ==
                helper.BASELINE_SOURCE and parent.get('manifest_sha256') == helper.BASELINE_SHA,
                'FINAL_V4_PARENT_BASELINE_DIFFERS')
        require(receipt['schema'] == 1 and receipt['approved_candidate_commit'] == CANDIDATE and
                receipt['user_video_review'] == 'PASS', 'CLEAN_RECEIPT_IDENTITY_OR_APPROVAL_INVALID')
        for key in ('source_manifest', 'asset_manifest', 'dependency_manifest', 'import_manifest',
                    'build_input_manifest', 'clean_reproduction_receipt', 'secret_scan'):
            binding = baseline[key]
            require(binding['path'] in rows and actual(binding['path']) ==
                    {'sha256': binding['sha256'], 'bytes': binding['bytes']}, 'BASELINE_MANIFEST_BINDING_DIFFERS')
        require(baseline['clean_reproduction_receipt']['path'] == RECEIPT and
                baseline['secret_scan']['path'] == SECRET, 'BASELINE_FINAL_RECEIPT_PATH_DIFFERS')
        require(baseline['hash_manifest']['path'] == HASHES and actual(HASHES) ==
                {k: baseline['hash_manifest'][k] for k in ('sha256', 'bytes')}, 'BASELINE_FINAL_HASH_BINDING_DIFFERS')
        require(SELF in rows and RECEIPT in rows and SECRET in rows and POLICY in rows,
                'FINAL_REQUIRED_DOCUMENT_OR_POLICY_NOT_BOUND')
        policy = legacy.safe_file(repo, POLICY).read_text()
        require(all(name in policy for name in CONDITIONS) and 'V5_GATE_COMPLETE' in policy,
                'FINAL_PERMANENT_POLICY_CONDITIONS_INCOMPLETE')

    phase('FINAL_HASH_AND_BASELINE_BINDINGS', documents)

    def preflight():
        nonlocal candidate_report, paths
        candidate_report = candidate.check(repo)
        require(candidate_report['preflight_status'] == 'PASS' and
                candidate_report['permanent_conditions']['SOURCE_PERSISTED']['status'] == 'PASS',
                'ACTUAL_CANDIDATE_BODY_AST_DEPENDENCY_OR_PERSISTENCE_FAILED')
        dep = document(V5 + '/manifests/DEPENDENCY_MANIFEST.json')
        media = document(V5 + '/manifests/MEDIA_MANIFEST.json')
        paths = {r['path'] for r in dep['required_files']} | {
            V5 + '/manifests/' + name for name in (*helper.NAMES, 'MEDIA_MANIFEST.json')
        } | {r['path'] for r in media['files']}
        require(len(dep['required_files']) == 112 and len(media['files']) == 12 and paths <= set(rows),
                'FINAL_HASH_REQUIRED_CANDIDATE_CLOSURE_INCOMPLETE')
        frozen, head = helper.tree(repo, CANDIDATE), helper.tree(repo, 'HEAD')
        require(all(frozen.get(p) == head.get(p) and p in frozen for p in paths),
                'APPROVED_CANDIDATE_SOURCE_ASSET_METADATA_OR_MEDIA_CHANGED')
        require(VERIFICATION_ONLY in rows and actual(VERIFICATION_ONLY)['sha256'] == GOLDEN and
                frozen.get(VERIFICATION_ONLY) == head.get(VERIFICATION_ONLY) and VERIFICATION_ONLY in frozen,
                'FROZEN_COMPARATOR_ONLY_DEPENDENCY_MISSING_OR_CHANGED')
        mp4 = baseline['candidate_mp4']
        require(mp4['path'] == V5 + '/public-review/SUEZ_CAMERA_DIRECTOR_V5.mp4' and
                mp4['sha256'] == MP4 and actual(mp4['path']) == {k: mp4[k] for k in ('sha256', 'bytes')},
                'APPROVED_VIDEO_BYTES_CHANGED')
        wanted = {r['path']: {k: r[k] for k in ('sha256', 'bytes')} for r in media['files'] if r['path'].endswith('.png')}
        observed = {r['path']: {k: r[k] for k in ('sha256', 'bytes')} for r in baseline['checkpoints']}
        require(wanted == observed and len(observed) == 7, 'FINAL_CHECKPOINT_BINDINGS_DIFFER')

    phase('APPROVED_CANDIDATE_IMMUTABLE_CLOSURE', preflight)

    def final_source_assets_build():
        dep = document(V5 + '/manifests/DEPENDENCY_MANIFEST.json')
        expected = {r['path']: r for r in dep['required_files']}

        def bound(row):
            path = row['path']
            require(path in rows and actual(path) == {k: row[k] for k in ('sha256', 'bytes')},
                    'FINAL_SOURCE_ASSET_BUILD_ROW_NOT_BODY_BOUND')
            wanted = expected.get(path)
            if wanted is not None:
                require({k: row[k] for k in ('sha256', 'bytes')} ==
                        {k: wanted[k] for k in ('sha256', 'bytes')}, 'FINAL_CLOSURE_ROW_DIFFERS_FROM_CANDIDATE')

        source = document(baseline['source_manifest']['path'])
        require(source['schema'] == 1 and source['approved_candidate_commit'] == CANDIDATE and
                source['candidate_payload_files'] == 112 and source['immutable_v4_files'] == 98,
                'FINAL_SOURCE_INVENTORY_SCOPE_INVALID')
        original_source = source['candidate_source_manifest']
        require(original_source['path'] == V5 + '/manifests/SOURCE_MANIFEST.json', 'FINAL_SOURCE_CANDIDATE_BINDING_PATH_DIFFERS')
        bound(original_source)
        require({r['path'] for r in source['source_files']} ==
                {r['path'] for r in dep['required_files'] if r['kind'] in ('source', 'procedure')},
                'FINAL_SOURCE_ACTUAL_SOURCE_PROCEDURE_CLOSURE_INCOMPLETE')
        for row in source['source_files']:
            bound(row)
        require({r['path'] for r in source['final_verification_files']} == {SELF},
                'FINAL_VERIFICATION_SOURCE_CLOSURE_DIFFERS')
        for row in source['final_verification_files']:
            bound(row)

        assets = document(baseline['asset_manifest']['path'])
        require(assets['schema'] == 1 and assets['approved_candidate_commit'] == CANDIDATE,
                'FINAL_RUNTIME_ASSET_MANIFEST_IDENTITY_DIFFERS')
        inherited = document('world-simulation-shorts-engine/recovery/v4/preservation/RUNTIME_ASSET_MANIFEST.json')
        old_build = document('world-simulation-shorts-engine/recovery/v4/preservation/BUILD_INPUT_MANIFEST.json')
        old_entries = {r['path']: r for r in inherited['entries']}
        gis = 'cinematic-world-map/assets/gis/countries_50m.geojson'
        require({r['path'] for r in assets['entries']} == set(old_entries) | {gis},
                'FINAL_RUNTIME_ASSET_SEVEN_PLUS_GIS_CLOSURE_DIFFERS')
        for row in assets['entries']:
            bound(row)
            if row['path'] in old_entries:
                require(all(row.get(k) == v for k, v in old_entries[row['path']].items()),
                        'FINAL_INHERITED_RUNTIME_ASSET_CONTRACT_CHANGED')
        plan_paths = {'world-simulation-shorts-engine/recovery/v4/equivalent-plans/REGIONAL-plan.json',
                      'world-simulation-shorts-engine/recovery/v4/equivalent-plans/CONTINENT-plan.json',
                      V5 + '/inputs/scene.json', V5 + '/inputs/camera-plan.json'}
        require({r['path'] for r in assets['plan_inputs']} == plan_paths,
                'FINAL_RUNTIME_PLAN_INPUT_CLOSURE_DIFFERS')
        for row in assets['plan_inputs']:
            bound(row)
        require({r['path'] for r in assets['verification_inputs']} == {VERIFICATION_ONLY},
                'FINAL_COMPARATOR_INPUT_CLOSURE_DIFFERS')
        for row in assets['verification_inputs']:
            bound(row)
        reveal_binding = assets['reveal_plan']
        bound(reveal_binding)
        require(document(reveal_binding['path']) == document(V5 + '/evidence/runtime-diagnostic.json')['revealPlan'],
                'FINAL_COMPILED_REVEAL_PLAN_DIFFERS_FROM_APPROVED_CANDIDATE')

        build = document(baseline['build_input_manifest']['path'])
        require(build['schema'] == 1 and build['approved_candidate_commit'] == CANDIDATE and
                build['datasets'] == old_build['datasets'], 'FINAL_BUILD_INPUT_OR_DATASET_PROVENANCE_DIFFERS')
        wanted = {r['path']: {k: r[k] for k in ('sha256', 'bytes')} for r in old_build['entries']}
        require({r['path']: {k: r[k] for k in ('sha256', 'bytes')} for r in build['entries']} == wanted and
                len(build['entries']) == 12, 'FINAL_BUILD_INPUT_TWELVE_CLOSURE_DIFFERS')
        for row in build['entries']:
            bound(row)
        require(build['recipe']['path'] == old_build['recipe'], 'FINAL_DETERMINISTIC_BUILD_RECIPE_PATH_CHANGED')
        bound(build['recipe'])
        require({r['path'] for r in build['dependency_locks']} == set(old_build['dependency_locks']),
                'FINAL_BUILD_DEPENDENCY_LOCK_CLOSURE_DIFFERS')
        for row in build['dependency_locks']:
            bound(row)

    phase('FINAL_SOURCE_RUNTIME_ASSET_AND_BUILD_CLOSURES', final_source_assets_build)

    evidence = receipt.get('evidence', {})

    def evidence_path(name):
        value = evidence[name]
        if isinstance(value, dict):
            value = value['path']
        require(value in rows, 'CLEAN_EVIDENCE_FILE_NOT_HASH_BOUND')
        return value

    def clean_environment():
        clean = receipt['checkout']
        require(clean['origin'] == ORIGIN and clean['head'] == CANDIDATE and
                clean['independent_clone'] is True and clean['git_alternates'] is False and
                clean['sparse_required_closure'] is True and clean['status_before_render'] == [] and
                clean['status_after_render'] == [], 'INDEPENDENT_CLEAN_CHECKOUT_EVIDENCE_INVALID')
        require(receipt['required_payload_files'] == 112 and receipt['immutable_v4_files'] == 98 and
                receipt['required_temp_only_files'] == 0 and receipt['candidate_preflight'] == 'PASS',
                'CLEAN_CLOSURE_OR_TEMP_FILE_EVIDENCE_INVALID')
        lfs = receipt['remote_lfs']
        require(lfs['status'] == 'PASS' and lfs['local_cache_reused'] is False, 'LFS_REMOTE_RETRIEVAL_INVALID')
        expected = {'world-simulation-shorts-engine/library/flat/terrain/NE1_HR_LC_SR_W_DR.tif',
                    'world-simulation-shorts-engine/web/dem/glo30/height.f32'}
        require({r['path'] for r in lfs['objects']} == expected and len(lfs['objects']) == 2,
                'LFS_REQUIRED_OBJECT_INVENTORY_DIFFERS')
        for row in lfs['objects']:
            require(row['downloaded_from_remote'] is True and actual(row['path']) ==
                    {k: row[k] for k in ('sha256', 'bytes')}, 'LFS_RETRIEVED_OBJECT_BODY_DIFFERS')
        require(receipt['dependency_setup']['status'] == 'PASS', 'CLEAN_DEPENDENCY_SETUP_FAILED')
        for name in ('dependency_log', 'static_log', 'video_log', 'lfs_log'):
            require(actual(evidence_path(name))['bytes'] > 0, 'CLEAN_EXECUTION_LOG_ABSENT')

    phase('CLEAN_CHECKOUT_AND_REMOTE_ASSETS', clean_environment)

    def synthetic():
        result = receipt['synthetic']
        require(result['status'] == 'PASS' and result['passed'] == 21 and result['failed'] == 0 and
                all(result[k] == 'PASS' for k in ('fixture_a', 'fixture_b', 'fixture_c', 'context_used', 'context_skipped')),
                'GENERAL_CONTEXT_USED_OR_SKIPPED_REGRESSION_FAILED')
        log = legacy.safe_file(repo, evidence_path('synthetic_log')).read_text()
        require(re.search(r'(?:#|ℹ)\s*tests\s+21\b', log) is not None and
                re.search(r'(?:#|ℹ)\s*pass\s+21\b', log) is not None and
                re.search(r'(?:#|ℹ)\s*fail\s+0\b', log) is not None, 'ACTUAL_SYNTHETIC_21_TEST_LOG_DIFFERS')

    phase('GENERAL_CONTEXT_REGRESSION', synthetic)

    def report(name, phase_name):
        value = document(evidence_path(name))
        require(value['source_commit'] == CANDIDATE and value['status'] == 'CAPTURE_COMPLETE' and
                value['phase'] == phase_name and value['command']['exit_code'] == 0 and
                value['errors'] == [] and value['viewport'] == [1080, 1920] and value['fps'] == 30 and
                value['audio'] is False and value['chromium'] == '154.0.8037.57' and
                'SwiftShader' in value['backend']['renderer'], 'ACTUAL_CLEAN_CAPTURE_REPORT_INVALID')
        start = dt.datetime.fromisoformat(value['started_at_utc'].replace('Z', '+00:00'))
        end = dt.datetime.fromisoformat(value['completed_at_utc'].replace('Z', '+00:00'))
        require(start.tzinfo is not None and end.tzinfo is not None and
                start < end <= dt.datetime.now(dt.timezone.utc), 'CLEAN_CAPTURE_TIME_INVALID')
        dep = document(V5 + '/manifests/DEPENDENCY_MANIFEST.json')
        required = {r['path'] for r in dep['required_files']} | {
            V5 + '/manifests/' + name for name in helper.NAMES}
        require(set(value['required_inputs']) == required, 'CLEAN_CAPTURE_FULL_INPUT_INVENTORY_DIFFERS')
        for p, binding in value['required_inputs'].items():
            require(actual(p) == {k: binding[k] for k in ('sha256', 'bytes')}, 'CLEAN_CAPTURE_REQUIRED_INPUT_HASH_DIFFERS')
        return value, start, end

    static_report, video_report = {}, {}

    def static():
        nonlocal static_report
        from PIL import Image
        static_report, _, _ = report('static_report', 'checkpoints')
        expected = receipt['static']
        require(expected['status'] == 'PASS' and expected['classification'] in ('BIT_EXACT', 'PIXEL_EXACT') and
                expected['expected_sha256'] == GOLDEN and expected['changed_pixels'] == 0,
                'CLEAN_STATIC_PREREQUISITE_FAILED')
        path = evidence_path('static_png')
        value = actual(path)
        with Image.open(legacy.safe_file(repo, path)) as image:
            require(image.format == 'PNG' and image.size == (1080, 1920) and
                    hashlib.sha256(image.convert('RGBA').tobytes()).hexdigest() == GOLDEN_RGBA,
                    'ACTUAL_CLEAN_STATIC_RGBA_DIFFERS')
        require(expected['actual_sha256'] == value['sha256'] and
                (expected['classification'] != 'BIT_EXACT' or value['sha256'] == GOLDEN),
                'ACTUAL_CLEAN_STATIC_SHA_DIFFERS')
        require(static_report['final_hold_comparison']['changed_pixels'] == 0 and
                static_report['final_hold_comparison']['actual_sha256'] == value['sha256'],
                'ACTUAL_STATIC_REPORT_AND_OUTPUT_DIFFER')

    phase('CLEAN_STATIC_PIXEL_COMPARISON', static)

    def video():
        nonlocal video_report
        require(checks.get('CLEAN_STATIC_PIXEL_COMPARISON') == 'PASS', 'STATIC_NOT_PASSED_BEFORE_VIDEO')
        video_report, video_start, _ = report('video_report', 'video')
        _, _, static_end = report('static_report', 'checkpoints')
        require(static_end <= video_start, 'VIDEO_STARTED_BEFORE_STATIC_PASS')
        original = document(V5 + '/evidence/runtime-diagnostic.json')
        require(video_report['cameraPlan'] == original['cameraPlan'] and
                video_report['revealPlan'] == original['revealPlan'] and
                video_report['checkpoints'] == original['checkpoints'], 'CAMERA_REVEAL_OR_CHECKPOINT_PLAN_CHANGED')
        require(len(video_report['frames']) == 250 and [r['frame'] for r in video_report['frames']] == list(range(250)) and
                video_report['frames'] == original['frames'], 'ACTUAL_250_RENDERED_FRAME_RGBA_OR_PNG_HASH_DIFFERS')
        diagnostic_path = evidence_path('video_frame_diagnostics')
        old = [json.loads(line) for line in legacy.safe_file(repo, V5 + '/evidence/frame-diagnostics.jsonl').read_text().splitlines()]
        new = [json.loads(line) for line in legacy.safe_file(repo, diagnostic_path).read_text().splitlines()]
        require(len(new) == 250 and new == old, 'ACTUAL_250_FRAME_CAMERA_REVEAL_LAYOUT_DIAGNOSTICS_DIFFER')
        for row in new:
            require(row['gpu']['glError'] == 0 and row['gpu']['factoryCount'] == 1 and
                    row['gpu']['layoutValidation']['valid'] is True and row['gpu']['finishedFrameMix'] is False and
                    row['gpu']['projectionChange'] is False and row['admission']['status'] == 'LOCAL_NOT_ADMITTED' and
                    row['admission']['localUsed'] is False and row['geographicAnchor'] == original['cameraPlan']['anchor'],
                    'ACTUAL_FRAME_PROTECTED_RUNTIME_CONTRACT_FAILED')
        root = evidence['checkpoint_directory']
        require(isinstance(root, str) and not root.startswith('/') and '..' not in Path(root).parts,
                'INVALID_CLEAN_CHECKPOINT_DIRECTORY')
        from PIL import Image
        for filename, frame in original['checkpoints'].items():
            path, approved = root.rstrip('/') + '/' + filename, V5 + '/public-review/' + filename
            require(path in rows, 'CLEAN_CHECKPOINT_NOT_BOUND')
            with Image.open(legacy.safe_file(repo, path)) as clean, Image.open(legacy.safe_file(repo, approved)) as golden:
                require(clean.format == 'PNG' and clean.size == golden.size == (1080, 1920) and
                        clean.convert('RGBA').tobytes() == golden.convert('RGBA').tobytes(), 'ACTUAL_CLEAN_CHECKPOINT_PIXELS_DIFFER')
            require(actual(path)['sha256'] == video_report['frames'][frame]['png_sha256'],
                    'CLEAN_CHECKPOINT_AND_RENDERED_FRAME_HASH_DIFFER')
        path = evidence_path('video_mp4')
        actual_video = actual(path)
        require(video_report['video']['sha256'] == actual_video['sha256'] and
                video_report['video']['bytes'] == actual_video['bytes'], 'ACTUAL_CLEAN_VIDEO_REPORT_BODY_DIFFERS')
        ffprobe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                                                     '-show_format', '-of', 'json', str(legacy.safe_file(repo, path))]))
        require(len(ffprobe['streams']) == 1, 'CLEAN_VIDEO_AUDIO_OR_EXTRA_STREAM')
        stream = ffprobe['streams'][0]
        require(stream['codec_type'] == 'video' and stream['codec_name'] == 'h264' and
                [stream['width'], stream['height']] == [1080, 1920] and stream['avg_frame_rate'] == '30/1' and
                int(stream['nb_read_frames']) == 250 and math.isclose(float(stream['duration']), 250 / 30, abs_tol=.001),
                'ACTUAL_CLEAN_VIDEO_SPECIFICATIONS_DIFFER')
        expected = receipt['video']
        require(expected['status'] == 'PASS' and expected['comparison'] in ('BIT_EXACT', 'PIXEL_EXACT', 'PIXEL_EQUIVALENT') and
                expected['frames'] == 250 and expected['fps'] == 30 and expected['dimensions'] == [1080, 1920] and
                expected['audio'] is False and math.isclose(expected['duration_seconds'], 250 / 30, abs_tol=.001) and
                expected['sha256'] == actual_video['sha256'] and expected['checkpoint_files_match'] == 7 and
                expected['decoded_mp4_frames_match'] == 250 and all(expected[k] is True for k in
                    ('all_frame_rgba_match', 'all_frame_png_match', 'diagnostics_match', 'camera_plan_match',
                     'reveal_plan_match', 'checkpoint_map_match')), 'CLEAN_VIDEO_COMPARISON_RECEIPT_DIFFERS')
        if actual_video['sha256'] == MP4:
            require(expected['comparison'] == 'BIT_EXACT', 'EXACT_VIDEO_CLASSIFICATION_DIFFERS')
        else:
            require(expected['comparison'] != 'BIT_EXACT', 'NONEXACT_VIDEO_CANNOT_BE_BIT_EXACT')
            def decoded(file):
                return subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(file), '-map', '0:v:0',
                    '-an', '-pix_fmt', 'rgba', '-f', 'framemd5', '-hash', 'sha256', '-']).splitlines()
            approved_file = legacy.safe_file(repo, V5 + '/public-review/SUEZ_CAMERA_DIRECTOR_V5.mp4')
            clean_rows = [r for r in decoded(legacy.safe_file(repo, path)) if not r.startswith(b'#')]
            approved_rows = [r for r in decoded(approved_file) if not r.startswith(b'#')]
            require(len(clean_rows) == 250 and clean_rows == approved_rows, 'ACTUAL_DECODED_MP4_FRAMES_DIFFER')

    phase('CLEAN_FULL_VIDEO_PIXEL_COMPARISON', video)

    def secrets():
        require(secret.get('status', secret.get('result')) == 'NO_SECRET_EXPOSURE_FOUND', 'FINAL_SECRET_SCAN_DID_NOT_PASS')
        require(secret.get('findings', secret.get('findings_count')) == 0, 'FINAL_SECRET_FINDINGS_PRESENT_OR_UNKNOWN')
        scanner = secret.get('scanner', {})
        require(scanner.get('exit_code', secret.get('exit_code')) == 0, 'FINAL_SECRET_SCANNER_EXIT_UNVERIFIED')
        scanned = {}
        for row in secret['scanned_files']:
            path = row['path']
            require(path not in scanned and path in rows and actual(path) ==
                    {k: row[k] for k in ('sha256', 'bytes')}, 'FINAL_SECRET_SCAN_SCOPE_HASH_DIFFERS')
            scanned[path] = row
        log_path = scanner['log_path']
        require(log_path in rows and actual(log_path)['bytes'] > 0, 'FINAL_SECRET_SCANNER_LOG_UNBOUND_OR_EMPTY')
        if 'log_sha256' in scanner:
            require(actual(log_path)['sha256'] == scanner['log_sha256'], 'FINAL_SECRET_SCANNER_LOG_HASH_DIFFERS')
        # Scan source/metadata contents, not the generated circular scan/hash/
        # baseline containers. Renderer media and original candidate records are
        # immutable and separately body-bound; final text records must be fresh.
        required_scope = {SELF} | {path for path in rows if
            (path.startswith(FINAL) or path.startswith(EVIDENCE)) and
            Path(path).suffix.lower() in ('.json', '.jsonl', '.md', '.py', '.mjs', '.js', '.html', '.sh') and
            path not in (SECRET, BASELINE, HASHES, log_path)}
        report_path = scanner.get('report_path')
        if report_path is not None:
            require(report_path in rows and document(report_path) == [], 'FINAL_RAW_SCANNER_REPORT_HAS_FINDINGS')
            required_scope.discard(report_path)
        require(required_scope <= set(scanned), 'FINAL_SECRET_SCAN_REQUIRED_METADATA_OR_TOOL_NOT_SCANNED')

    phase('FINAL_SECRET_SCAN', secrets)

    def persisted():
        require(require_persisted, 'FINAL_PERSISTENCE_CHECK_NOT_REQUESTED')
        tree, index = legacy.inventory(repo, True), legacy.inventory(repo)
        algorithm = legacy.git(repo, 'rev-parse', '--show-object-format').decode().strip()
        for path in set(rows) | {BASELINE, HASHES}:
            require(path in tree and tree[path] == index.get(path) and tree[path][0] in ('100644', '100755'),
                    'FINAL_FILE_NOT_PERSISTED_IN_HEAD_AND_INDEX')
            mode, oid = tree[path]
            body_size = int(legacy.git(repo, 'cat-file', '-s', oid))
            if body_size < 1024:
                pointer = legacy.LFS.fullmatch(legacy.git(repo, 'cat-file', 'blob', oid))
                if pointer:
                    require(actual(path) == {'sha256': pointer[1].decode(), 'bytes': int(pointer[2])},
                            'FINAL_LFS_HYDRATED_BODY_DIFFERS')
                    continue
            file = legacy.safe_file(repo, path)
            digest = hashlib.new(algorithm)
            digest.update(('blob ' + str(file.stat().st_size) + '\0').encode())
            with file.open('rb') as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    digest.update(chunk)
            require(digest.hexdigest() == oid, 'FINAL_WORKTREE_BODY_DIFFERS_FROM_COMMIT')

    if require_persisted:
        phase('FINAL_COMMITTED_STORAGE', persisted)
    else:
        checks['FINAL_COMMITTED_STORAGE'] = 'NOT_RUN'

    preflight = all(value == 'PASS' for key, value in checks.items() if key != 'FINAL_COMMITTED_STORAGE')
    complete = preflight and checks['FINAL_COMMITTED_STORAGE'] == 'PASS'
    conditions = {
        'SOURCE_PERSISTED': 'PASS' if all(checks[k] == 'PASS' for k in ('FINAL_COMMITTED_STORAGE', 'APPROVED_CANDIDATE_IMMUTABLE_CLOSURE', 'FINAL_SOURCE_RUNTIME_ASSET_AND_BUILD_CLOSURES')) else 'NOT_RUN' if not require_persisted else 'FAIL',
        'ASSETS_PERSISTED': 'PASS' if all(checks[k] == 'PASS' for k in ('CLEAN_CHECKOUT_AND_REMOTE_ASSETS', 'FINAL_SOURCE_RUNTIME_ASSET_AND_BUILD_CLOSURES')) else 'FAIL',
        'HASH_MANIFEST_PASS': 'PASS' if all(checks[k] == 'PASS' for k in ('FINAL_HASH_AND_BASELINE_BINDINGS', 'FINAL_SOURCE_RUNTIME_ASSET_AND_BUILD_CLOSURES')) else 'FAIL',
        'DEPENDENCY_MANIFEST_PASS': 'PASS' if candidate_report.get('candidate_preflight', {}).get('DEPENDENCY_MANIFEST_PASS') == 'PASS' and checks['CLEAN_CHECKOUT_AND_REMOTE_ASSETS'] == 'PASS' else 'FAIL',
        'IMPORT_MANIFEST_PASS': candidate_report.get('candidate_preflight', {}).get('IMPORT_MANIFEST_PASS', 'FAIL'),
        'NO_REQUIRED_TEMP_FILES': 'PASS' if checks['APPROVED_CANDIDATE_IMMUTABLE_CLOSURE'] == 'PASS' and checks['CLEAN_CHECKOUT_AND_REMOTE_ASSETS'] == 'PASS' else 'FAIL',
        'CLEAN_ENV_REPRODUCIBLE': 'PASS' if all(checks[k] == 'PASS' for k in ('CLEAN_STATIC_PIXEL_COMPARISON', 'CLEAN_FULL_VIDEO_PIXEL_COMPARISON', 'GENERAL_CONTEXT_REGRESSION', 'CLEAN_CHECKOUT_AND_REMOTE_ASSETS')) else 'FAIL'
    }
    return {'schema': 1, 'scope': 'USER_APPROVED_CAMERA_DIRECTOR_V5_FINAL_FREEZE',
            'approved_candidate_commit': CANDIDATE, 'head': legacy.git(repo, 'rev-parse', 'HEAD').decode().strip(),
            'checks': checks, 'conditions': conditions, 'preflight_status': 'PASS' if preflight else 'FAIL',
            'final_permanent_gate': 'V5_GATE_COMPLETE' if complete else 'V5_GATE_INCOMPLETE',
            'decision': 'CAMERA_DIRECTOR_V5_FINAL' if complete else 'CAMERA_DIRECTOR_V5_FINAL_BLOCKED',
            'errors': errors, 'bound_files_verified': len(checked), 'render_executed': False,
            'verification_only_dependencies': [{'path': VERIFICATION_ONLY, 'expected_sha256': GOLDEN,
                'role': 'PNG_COMPARATOR_REFERENCE_ONLY_NOT_RENDER_INPUT',
                'status': 'PASS' if checks['APPROVED_CANDIDATE_IMMUTABLE_CLOSURE'] == 'PASS' else 'FAIL'}],
            'engine_executed': False, 'git_mutations': 0, 'next_stage_automatically_started': False,
            'receipt_limit': 'Actual evidence bytes are checked; evidence is not cryptographic execution attestation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).absolute().parent.parent)
    parser.add_argument('--require-persisted', action='store_true')
    args = parser.parse_args()
    try:
        result = check(args.repo.absolute(), args.require_persisted)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError, ImportError):
        result = {'decision': 'CAMERA_DIRECTOR_V5_FINAL_BLOCKED', 'preflight_status': 'FAIL',
                  'errors': [{'code': 'FINAL_VALIDATION_INPUT_UNAVAILABLE_OR_INVALID'}]}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get('preflight_status') == 'PASS' and (not args.require_persisted or
        result.get('decision') == 'CAMERA_DIRECTOR_V5_FINAL') else 1


if __name__ == '__main__':
    raise SystemExit(main())
