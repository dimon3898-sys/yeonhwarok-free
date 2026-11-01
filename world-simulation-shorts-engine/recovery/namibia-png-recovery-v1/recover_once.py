#!/usr/bin/env python3
"""Add one verified original asset to the pinned image; one build/push, no retry."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

BASE = '8bf86d4280c7506cf04551dd15e1a65e77bb800b'
BRANCH = 'refs/heads/recovery/namibia-png-20261101'
REC = 'world-simulation-shorts-engine/recovery/'
TASK = REC + 'namibia-png-recovery-v1/'
PNG = REC + 'g2-renderer-recovery-v1/assets/terrain/namibia_desert_coast_ne1_native.png'
PNG_SHA = '0d7d5e2db7770aad365c00a055044b92954d8711fa7d202ef4d495ee83c82068'
PNG_BYTES = 6518687
PARENT_DIGEST = 'sha256:f230489d451e1c517fda51c5a7938940d1f01db81e585daa106bfbd4828fa42f'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT = IMAGE + '@' + PARENT_DIGEST
IMAGE_ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
TARGET = IMAGE_ROOT + '/' + PNG


def need(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def module(file, name):
    spec = importlib.util.spec_from_file_location(name, file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def prepare(repo, context):
    """Only PNG + two-instruction Dockerfile; never modify the original."""
    source = repo / PNG
    need(source.is_file() and not any(p.is_symlink() for p in (source, *source.parents)), 'ORIGINAL_PATH_UNSAFE')
    raw = source.read_bytes()
    need(len(raw) == PNG_BYTES and sha(raw) == PNG_SHA, 'ORIGINAL_PNG_MISMATCH')
    expected = ('FROM ' + PARENT + '\nCOPY --chown=0:0 --chmod=0644 ' +
                json.dumps([Path(PNG).name, TARGET]) + '\n').encode()
    need((repo / TASK / 'Dockerfile').read_bytes() == expected, 'SINGLE_ASSET_DOCKERFILE_REQUIRED')
    context.mkdir(mode=0o755)
    (context / Path(PNG).name).write_bytes(raw)
    (context / 'Dockerfile').write_bytes(expected)
    for path in context.iterdir():
        path.chmod(0o644)
    return {'status': 'PASS', 'parentDigest': PARENT_DIGEST,
            'source': PNG, 'target': TARGET, 'bytes': PNG_BYTES, 'sha256': PNG_SHA,
            'dockerfileSHA256': sha(expected), 'runtimeFilesAdded': 1,
            'runtimeFilesModified': 0, 'startupOrManifestChanges': 0}


def main():
    need(os.environ.get('GITHUB_REPOSITORY') == 'dimon3898-sys/yeonhwarok-free', 'REPOSITORY_GUARD')
    need(os.environ.get('GITHUB_RUN_ATTEMPT') == '1' and os.environ.get('GITHUB_REF') == BRANCH, 'SINGLE_RUN_GUARD')
    repo, temp = Path(os.environ['GITHUB_WORKSPACE']), Path(os.environ['RUNNER_TEMP'])
    out = temp / 'namibia-evidence'
    out.mkdir()
    def write(name, value):
        with (out / name).open('x') as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write('\n')
    keep = None
    try:
        h = module(repo / REC / 'up2-detail-display-v1/build_once.py', '_existing_io')
        h.PARENT_DIGEST, h.PARENT, h.OLD_TAG = PARENT_DIGEST, PARENT, 'up2-details-v1-41274003859'
        need(h.run_command(['git', 'rev-parse', 'HEAD']) == os.environ['GITHUB_SHA'], 'CHECKOUT_CHANGED')
        need(h.run_command(['git', 'rev-parse', 'HEAD^']) == BASE, 'BASE_CHANGED')
        plan = prepare(repo, temp / 'namibia-context')
        write('CONTEXT.json', plan)
        tag_name = 'namibia-png-v1-' + os.environ['GITHUB_RUN_ID']
        target = IMAGE + ':' + tag_name
        h.old_tag()
        h.absent(tag_name)
        docker_root = h.docker('info', '--format', '{{.DockerRootDir}}')
        need(shutil.disk_usage(docker_root).free >= 12 * 1024**3, 'PREPULL_CAPACITY')
        h.run_command(['docker', '--host=unix:///var/run/docker.sock', 'login', 'ghcr.io', '-u', os.environ['GITHUB_ACTOR'], '--password-stdin'], input=os.environ['GH_TOKEN'])
        keep = module(repo / REC / 'label355-publication-v1/retain_label355_image.py', '_existing_backup')
        keep.ROOT = temp / 'namibia-retention'
        keep.ROOT.mkdir()
        keep.SOURCE, keep.PARENT = os.environ['GITHUB_SHA'], PARENT_DIGEST
        keep.RELEASE_TAG = 'namibia-png-image-backup-' + os.environ['GITHUB_RUN_ID']
        release = keep.api(keep.API + '/releases', {'tag_name': keep.RELEASE_TAG,
            'target_commitish': keep.SOURCE, 'name': 'Original Namibia PNG image backup ' + os.environ['GITHUB_RUN_ID'],
            'body': 'One original PNG added to the pinned UP2 image. No GPU or Studio preflight claim.',
            'draft': False, 'prerelease': True, 'make_latest': 'false'})
        keep.write('RELEASE.json', release)
        keep.write('RESERVATION.json', {'sourceCommit': keep.SOURCE, 'parentDigest': PARENT_DIGEST,
            'maxBuilds': 1, 'maxGHCRPublications': 1, 'retries': 0})
        proof = keep.upload(release, keep.ROOT / 'RESERVATION.json')
        keep.write('RESERVATION_RESULT.json', {'status': 'PASS', 'releaseURL': release['html_url'], 'asset': proof})
        write('PULL_ATTEMPT.json', {'attempt': 1, 'parent': PARENT})
        h.docker_once(['pull', PARENT])
        parent = json.loads(h.docker('image', 'inspect', PARENT))[0]
        need(PARENT in parent.get('RepoDigests', []), 'PARENT_DIGEST_NOT_PRESENT')
        need(shutil.disk_usage(docker_root).free >= parent['Size'] * 3 + 2 * 1024**3, 'PREBUILD_ARCHIVE_CAPACITY')
        local = 'world-engine-namibia:unpublished-' + os.environ['GITHUB_RUN_ID']
        write('BUILD_ATTEMPT.json', {'attempt': 1, 'tag': local})
        h.docker_once(['build', '--network', 'none', '--pull=false', '-t', local, str(temp / 'namibia-context')])
        candidate = json.loads(h.docker('image', 'inspect', local))[0]
        need(candidate['Config'] == parent['Config'], 'INHERITED_CONFIG_CHANGED')
        need(candidate['RootFS']['Layers'][:-1] == parent['RootFS']['Layers'], 'NOT_EXACTLY_ONE_ADDED_LAYER')
        need((candidate['Os'], candidate['Architecture']) == (parent['Os'], parent['Architecture']), 'PLATFORM_CHANGED')
        probe = ("import hashlib,json,os,pathlib,stat; p=pathlib.Path(" + repr(TARGET) + "); "
                 "assert p.resolve()==p and p.is_file() and not p.is_symlink(); "
                 "s=p.stat(); assert (s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))==(0,0,0o644); "
                 "b=p.read_bytes(); assert len(b)==" + str(PNG_BYTES) + " and hashlib.sha256(b).hexdigest()==" + repr(PNG_SHA) + "; "
                 "assert os.getuid()==1000; print('NAMIBIA_ORIGINAL_READABLE_MATCH')")
        write('ASSET_CHECK_ATTEMPT.json', {'attempt': 1, 'scope': 'NEW_PNG_ONLY_NO_APPLICATION_START'})
        need(h.docker('run', '--rm', '--network', 'none', '--read-only', '--user', '1000:1000', '--entrypoint', '/usr/bin/python3', local, '-I', '-B', '-c', probe) == 'NAMIBIA_ORIGINAL_READABLE_MATCH', 'NEW_PNG_CHECK_FAILED')
        write('CANDIDATE.json', {'status': 'PASS', 'imageID': candidate['Id'], **plan,
            'uid1000NewAssetReadable': True, 'allParentLayersPreserved': True, 'inheritedConfigUnchanged': True,
            'oldPASSReruns': 0, 'gpuStarts': 0, 'compiles': 0, 'renders': 0})
        os.environ['TAG'] = local
        keep.archive()
        h.old_tag()
        h.absent(tag_name)
        h.docker('tag', local, target)
        write('PUBLICATION_ATTEMPT.json', {'attempt': 1, 'tag': target, 'imageID': candidate['Id']})
        h.docker_once(['push', target])
        raw, digest = h.registry(tag_name)
        pinned, confirmed = h.registry(digest)
        need(raw == pinned and digest == confirmed and json.loads(raw)['config']['digest'] == candidate['Id'], 'REMOTE_IMAGE_IDENTITY')
        h.old_tag()
        write('RESULT.json', {'status': 'PASS', 'scope': 'ORIGINAL_PNG_IMAGE_RECOVERY_ONLY',
            'tag': target, 'digest': digest, 'imageID': candidate['Id'], 'parentDigest': PARENT_DIGEST,
            'sourceCommit': os.environ['GITHUB_SHA'], 'imageRelease': keep.read('RETENTION_RESULT.json')['releaseURL'],
            'pngSHA256': PNG_SHA, 'builds': 1, 'publications': 1, 'retries': 0,
            'oldPASSReruns': 0, 'gpuStarts': 0, 'renders': 0, 'oldTagUnchanged': True,
            'remoteStudioPreflight': 'NOT_RUN', 'entireRegionFailureResolved': 'NOT_ESTABLISHED'})
    except Exception as error:
        write('BLOCKED.json', {'status': 'BLOCKED', 'errorType': type(error).__name__,
            'reason': str(error) if isinstance(error, RuntimeError) else 'COMMAND_OR_SERVICE_OPERATION_FAILED',
            'automaticRetries': 0, 'gpuStarts': 0})
        raise
    finally:
        for path in sorted(out.glob('*.json')):
            raw = path.read_bytes()
            print('NAMIBIA_EVIDENCE=' + json.dumps({'name': path.name, 'sha256': sha(raw), 'base64': base64.b64encode(raw).decode()}), flush=True)
            if keep is not None and (keep.ROOT / 'RELEASE.json').exists():
                keep.upload(keep.read('RELEASE.json'), path)


if __name__ == '__main__':
    main()
