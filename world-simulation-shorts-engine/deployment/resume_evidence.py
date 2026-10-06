"""Reconcile only verified checkpoint provenance in new deployment state.

The approved renderer and strict exporter remain unchanged. Media, audits, plans,
results, QC reports and old manifests are preserved; no rendering occurs here.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from deployment.security import owned_path, private_json
from engine.qc import valid_scene_file
from engine.storage import EngineError, canonical, now, plan_hash
from tools.deliverable_evidence import load_completed_version, sha256


def fail(code):
    raise EngineError(code, '완료 증거가 일치하지 않습니다. 기존 파일을 보존했습니다.')


def _read(root, name):
    path = owned_path(root, name)
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        fail('RESUME_EVIDENCE_JSON_INVALID')
    if not isinstance(data, dict):
        fail('RESUME_EVIDENCE_JSON_INVALID')
    return path, data


def _file(version, value, expected):
    if not isinstance(value, str) or not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected):
        fail('RESUME_EVIDENCE_FILE_INVALID')
    path = Path(value)
    if path.is_absolute():
        try:
            path = path.relative_to(version)
        except ValueError:
            fail('RESUME_EVIDENCE_PATH_ESCAPE')
    path = owned_path(version, path)
    if not path.is_file() or sha256(path) != expected:
        fail('RESUME_EVIDENCE_FILE_SHA_MISMATCH')
    return path


def finalize_resume_evidence(state_root, version_dir, *, expected_plan_hash, result=None):
    """Write only provenance corrections after complete independent checks.

    Any other difference fails before creating backups or touching the manifest.
    This function accepts only versions below a deployment-marked owned runtime.
    """
    root = Path(state_root).absolute()
    if root.is_symlink() or root.resolve() != root:
        fail('RESUME_EVIDENCE_STATE_INVALID')
    _, marker = _read(root, 'mobile-state.json')
    if marker.get('format') != 'world-mobile-runtime-v1':
        fail('RESUME_EVIDENCE_STATE_INVALID')
    version = Path(version_dir).absolute()
    try:
        rel = version.relative_to(root)
    except ValueError:
        fail('RESUME_EVIDENCE_PATH_ESCAPE')
    if (len(rel.parts) != 4 or rel.parts[0] != 'projects' or rel.parts[2] != 'versions' or
            not re.fullmatch(r'project_[a-z0-9_]{6,64}', rel.parts[1]) or
            not re.fullmatch(r'v\d{3,}', rel.parts[3])):
        fail('RESUME_EVIDENCE_VERSION_INVALID')
    version = owned_path(root, rel)
    _, plan = _read(version, 'scene_plan.json')
    digest = plan_hash(plan)
    if (digest != expected_plan_hash or plan.get('plan_hash') != digest or
            plan.get('project_id') != rel.parts[1] or plan.get('version') != rel.parts[3]):
        fail('RESUME_EVIDENCE_PLAN_CHANGED')
    _, approval = _read(version, 'approval.json')
    if approval.get('user_approval') is not True or approval.get('plan_hash') != digest:
        fail('RESUME_EVIDENCE_APPROVAL_REQUIRED')
    result_path, actual = _read(version, 'renders/project_result.json')
    result_sha = sha256(result_path)
    if result is not None:
        returned = deepcopy(result)
        if returned.get('reused_final') is True:
            returned.pop('reused_final')
        if returned != actual:
            fail('RESUME_EVIDENCE_RESULT_MISMATCH')
    _, checkpoint = _read(version, 'renders/checkpoint.json')
    if (actual.get('plan_hash') != digest or checkpoint.get('plan_hash') != digest or
            actual.get('qc', {}).get('passed') is not True or checkpoint.get('complete') is not True or
            checkpoint.get('qc_passed') is not True):
        fail('RESUME_EVIDENCE_QC_INCOMPLETE')
    manifest_path, manifest = _read(version, 'renders/scene_results.json')
    if (set(manifest) != {'plan_hash', 'renderer_version', 'scenes'} or
            manifest.get('plan_hash') != digest or manifest.get('renderer_version') != actual.get('renderer_version')):
        fail('RESUME_EVIDENCE_MANIFEST_METADATA_MISMATCH')
    scenes = actual.get('scenes', [])
    ids = [s.get('scene_id') for s in plan.get('scenes', [])]
    saved = manifest.get('scenes', [])
    if (not ids or len(set(ids)) != len(ids) or [s.get('scene_id') for s in scenes] != ids or
            [s.get('scene_id') for s in saved] != ids or
            checkpoint.get('completed_scenes') != len(ids) or checkpoint.get('total_scenes') != len(ids)):
        fail('RESUME_EVIDENCE_SCENE_ORDER_MISMATCH')
    changes = []
    for old, current, scene in zip(saved, scenes, plan['scenes']):
        if old != current:
            old_fields, current_fields = deepcopy(old), deepcopy(current)
            before = old_fields.pop('reuse_reason', None)
            after = current_fields.pop('reuse_reason', None)
            old_reused = old_fields.pop('reused', None)
            new_reused = current_fields.pop('reused', None)
            cache_checkpoint = old_reused is True and before == 'scene_hash_asset_renderer_quality_cache'
            native_checkpoint = (old_reused is False and before is None and
                                 old.get('native_manifest', {}).get('complete') is True)
            if (old_fields != current_fields or old.get('complete') is not True or current.get('complete') is not True or
                    new_reused is not True or after != 'version_checkpoint' or
                    not (cache_checkpoint or native_checkpoint)):
                fail('RESUME_EVIDENCE_NON_PROVENANCE_DIFF')
            if old_reused != new_reused:
                changes.append({'scene_id': scene['scene_id'], 'field': 'reused', 'before': old_reused, 'after': new_reused})
            changes.append({'scene_id': scene['scene_id'], 'field': 'reuse_reason', 'before': before, 'after': after})
        if current.get('complete') is not True:
            fail('RESUME_EVIDENCE_SCENE_INCOMPLETE')
        if current.get('scene_json_sha256') != hashlib.sha256(canonical(scene)).hexdigest():
            fail('RESUME_EVIDENCE_SCENE_JSON_MISMATCH')
        _, stored_scene = _read(version, 'scene_json/' + scene['scene_id'] + '.json')
        if stored_scene != scene:
            fail('RESUME_EVIDENCE_SCENE_JSON_MISMATCH')
        movie = _file(version, current.get('movie'), current.get('video_sha256'))
        audit = _file(version, current.get('audit'), current.get('audit_sha256'))
        quality = current.get('quality', {})
        if not all(isinstance(quality.get(k), (int, float)) and not isinstance(quality[k], bool) and quality[k] > 0
                   for k in ('output_width', 'output_height', 'fps')):
            fail('RESUME_EVIDENCE_MEDIA_SETTINGS_INVALID')
        if not valid_scene_file(movie, scene['duration'], quality['output_width'], quality['output_height'], quality['fps']):
            fail('RESUME_EVIDENCE_MEDIA_INVALID')
        try:
            records = json.loads(audit.read_text())
        except (OSError, ValueError):
            fail('RESUME_EVIDENCE_AUDIT_INVALID')
        if (not isinstance(records, list) or len(records) != round(scene['duration'] * quality['fps']) or
                any(not isinstance(r, dict) or r.get('webglError') or r.get('textClipped') for r in records)):
            fail('RESUME_EVIDENCE_AUDIT_INVALID')
    outputs = actual.get('outputs', {})
    finals = {name: _file(version, outputs.get(name), actual.get('final_sha256', {}).get(name)) for name in ('final', 'muted')}
    qcmd = owned_path(version, Path(outputs.get('qc_report', '')).relative_to(version))
    if not qcmd.is_file():
        fail('RESUME_EVIDENCE_QC_INVALID')
    _, qc = _read(version, qcmd.with_suffix('.json').relative_to(version))
    if qc != actual['qc'] or Path(qc.get('file', '')).absolute() != finals['final']:
        fail('RESUME_EVIDENCE_QC_INVALID')
    if not changes:
        load_completed_version(version)  # Strict unmodified exporter evidence gate.
        return {'changed': False, 'plan_hash': digest, 'scene_count': len(ids), 'render_started': False}
    original = manifest_path.read_bytes()
    original_sha = hashlib.sha256(original).hexdigest()
    replacement = {**manifest, 'scenes': scenes}
    replacement_bytes = (json.dumps(replacement, ensure_ascii=False, indent=2) + '\n').encode()
    replacement_sha = hashlib.sha256(replacement_bytes).hexdigest()
    # Validate once more immediately before any new file or atomic replacement.
    if manifest_path.read_bytes() != original or sha256(result_path) != result_sha:
        fail('RESUME_EVIDENCE_CHANGED_DURING_CHECK')
    backup = manifest_path.with_name('scene_results.pre_resume_' + original_sha + '.json')
    if backup.exists():
        if backup.is_symlink() or backup.read_bytes() != original:
            fail('RESUME_EVIDENCE_BACKUP_CONFLICT')
    else:
        fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
    receipt_path = manifest_path.with_name('resume_evidence_' + uuid.uuid4().hex + '.json')
    receipt = {'format': 'deployment-resume-provenance-v1', 'created_at': now(), 'plan_hash': digest,
               'project_id': plan['project_id'], 'version': plan['version'], 'changed': True,
               'allowed_change': 'verified reused/reuse_reason provenance only; complete native/cache entries to version checkpoint',
               'changes': changes, 'scene_count': len(ids), 'backup': str(backup), 'backup_sha256': original_sha,
               'manifest': str(manifest_path), 'manifest_sha256': replacement_sha,
               'project_result_sha256': sha256(result_path), 'media_or_audits_modified': False, 'render_started': False}
    # Preserve an exclusive intent receipt even if the following atomic write fails.
    with receipt_path.open('x', encoding='utf-8') as stream:
        os.chmod(receipt_path, 0o600)
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    private_json(manifest_path, replacement)
    if sha256(manifest_path) != replacement_sha or backup.read_bytes() != original:
        fail('RESUME_EVIDENCE_FINAL_WRITE_MISMATCH')
    load_completed_version(version)  # Never weaken the exporter's final invariant.
    return {**receipt, 'receipt': str(receipt_path), 'strict_exporter_evidence_passed': True}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-root', required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--plan-hash', required=True)
    args = parser.parse_args(argv)
    root = Path(args.state_root).absolute()
    version = root / 'projects' / args.project / 'versions' / args.version
    try:
        print(json.dumps(finalize_resume_evidence(root, version, expected_plan_hash=args.plan_hash), ensure_ascii=False))
    except (EngineError, OSError, ValueError) as error:
        print(json.dumps({'error': {'code': getattr(error, 'code', 'RESUME_EVIDENCE_FAILED'),
                                   'message': '완료 증거 검증에 실패했습니다. 기존 파일을 확인해 주세요.'}}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
