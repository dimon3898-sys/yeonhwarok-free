#!/usr/bin/env python3
"""One guarded additive image, exact backup recovery, then one GHCR publication.

Runs only in the explicitly activated free public GitHub Actions workflow.
No render, GPU, gCube API call, service start, retry, or existing tag mutation.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import urllib.request

REPOSITORY = 'dimon3898-sys/yeonhwarok-free'
BRANCH = 'deploy/korean-war-20s-20261109'
WORKFLOW = '.github/workflows/world-engine-korean-war-20s-image-once.yml'
PACKAGE = 'world-simulation-shorts-engine/production/korean-war-20s-deploy-20261109'
IMAGE = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PARENT_DIGEST = 'sha256:1ab43dd68e5ccdd364b6ec97d61d2f877070213cc42101412f45e17c54871e4b'
PARENT = IMAGE + '@' + PARENT_DIGEST
OLD_TAG = 'worker-launch-v16-42446481907'
OLD_BACKUP_TAG = 'worker-launch-image-backup-42446481907'
ROOT = '/opt/world-engine-handoffs/studio-capture-diagnostics-g2-v1/repo'
HERE = Path(__file__).resolve().parent
HELPERS = 'world-simulation-shorts-engine/recovery/reference-label-quality-v1'
HEX = re.compile(r'[a-f0-9]{64}')


def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_relative(path):
    need(isinstance(path, str) and path and not path.startswith('/')
         and '..' not in PurePosixPath(path).parts and '\\' not in path
         and str(PurePosixPath(path)) == path, 'MANIFEST_RELATIVE_PATH')
    return path


def file_receipt(repo, row):
    path = repo / safe_relative(row['path'])
    need(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(repo),
         'SOURCE_REGULAR_FILE')
    raw = path.read_bytes()
    need(type(row['bytes']) is int and row['bytes'] == len(raw)
         and HEX.fullmatch(row['sha256']) and sha(raw) == row['sha256'], 'SOURCE_HASH_OR_SIZE')
    return raw


def private_asset_evidence(repo, private):
    receipt = json.loads(file_receipt(repo, private['receipt']))
    archive = json.loads(file_receipt(repo, private['archiveVerification']))
    backup = json.loads(file_receipt(repo, private['backupEvidence']))
    need(receipt.get('schema') == 'WORLD_ENGINE_PRIVATE_PACKAGE_V1'
         and archive.get('schema') == 'WORLD_ENGINE_PRIVATE_ARCHIVE_VERIFICATION_V1'
         and archive.get('status') == 'PASS' and backup.get('status') == 'PASS'
         and backup.get('downloadVerified') is True, 'PRIVATE_ARCHIVE_AND_REMOTE_BACKUP_REQUIRED')
    need(HEX.fullmatch(receipt.get('archiveSHA256', ''))
         and type(receipt.get('archiveBytes')) is int and receipt['archiveBytes'] > 0
         and all(record.get('archiveSHA256') == receipt['archiveSHA256']
                 and record.get('archiveBytes') == receipt['archiveBytes'] for record in (archive, backup)),
         'PRIVATE_ARCHIVE_BACKUP_BYTES_MISMATCH')
    need(private['installationPath'] == receipt['installationPath']
         and receipt.get('rawAssetsExcludedFromPublicContext') is True
         and archive.get('rawAssetsExcludedFromPublicContext') is True, 'PRIVATE_INSTALL_CONTRACT_MISMATCH')
    return receipt


def qualification(repo):
    gate_file = HERE / 'BUILD_GATE.json'
    raw = gate_file.read_bytes()
    need(HEX.fullmatch(os.environ.get('WORLD_ENGINE_BUILD_GATE_SHA256', ''))
         and sha(raw) == os.environ['WORLD_ENGINE_BUILD_GATE_SHA256'], 'BUILD_GATE_PIN')
    gate = json.loads(raw)
    need(gate.get('schema') == 'WORLD_ENGINE_KOREAN_WAR_20S_BUILD_GATE_V1'
         and gate.get('status') == 'PASS' and gate.get('parentImage') == PARENT
         and re.fullmatch(r'[a-f0-9]{40}', gate.get('sourceCommit', '')), 'BUILD_GATE_REQUIRED')
    cpu = gate['cpuEvidence']
    need(cpu.get('status') == 'PASS' and cpu.get('sourceCommit') == gate['sourceCommit']
         and cpu.get('oldPASSReruns') == 0 and cpu.get('gpuStarts') == 0
         and bool(cpu.get('evidence')), 'CPU_ACCEPTED_EVIDENCE_REQUIRED')
    for row in cpu['evidence']:
        file_receipt(repo, row)
    private = gate['privateAssets']
    need(private.get('status') == 'PASS' and private.get('sourceBackupAvailable') is True
         and private.get('rawAssetsExcludedFromPublicContext') is True
         and private.get('installationPath', '').startswith('/')
         and not private['installationPath'].startswith(ROOT), 'PRIVATE_ASSET_QUALIFICATION_REQUIRED')
    private_receipt = private_asset_evidence(repo, private)
    studio = gate['studioInputs']
    need(studio.get('status') == 'PASS' and studio.get('officialPipeline') is True
         and len(studio.get('inputs', [])) == 2, 'OFFICIAL_STUDIO_INPUTS_REQUIRED')
    for row in studio['inputs']:
        file_receipt(repo, row)
    closure = json.loads(file_receipt(repo, gate['sourceClosure']))
    need(closure.get('status') == 'PASS' and len(closure.get('files', [])) >= 361,
         'COMPLETE_SOURCE_CLOSURE_REQUIRED')
    rows = {safe_relative(row['path']): row for row in closure['files']}
    need(len(rows) == len(closure['files']) and all(HEX.fullmatch(row['sha256'])
         and type(row['bytes']) is int and row['bytes'] > 0 for row in rows.values()),
         'CLOSURE_FILE_PINS')
    plan = json.loads(file_receipt(repo, gate['contextManifest']))
    cold = 'world-simulation-shorts-engine/recovery/studio-cold-start-v2/'
    need(plan.get('privateReceiptSHA256') == private['receipt']['sha256']
         == rows[cold + 'PRIVATE_PACKAGE_RECEIPT.json']['sha256']
         and plan.get('privateInstallerSHA256') == rows[cold + 'private_bundle.py']['sha256']
         and plan.get('privateArchiveSHA256') == private_receipt['archiveSHA256']
         and plan.get('privateRegistrySHA256') == private_receipt['registrySHA256'],
         'IMAGE_PRIVATE_INSTALLER_RECEIPT_AND_ASSET_BINDING')
    context = HERE / 'final-context'
    need(plan.get('parentImage') == PARENT and HEX.fullmatch(plan['runtimeManifestSHA256'])
         and HEX.fullmatch(plan['startupManifestSHA256']), 'CONTEXT_PARENT_AND_MANIFESTS')
    listed = set()
    for row in gate['contextFiles']:
        file_receipt(repo, row)
        path = repo / row['path']
        need(path.is_relative_to(context), 'CONTEXT_FILE_OUTSIDE_TREE')
        listed.add(path.relative_to(context).as_posix())
    actual = set()
    for path in context.rglob('*'):
        need(not path.is_symlink(), 'CONTEXT_SYMLINK_FORBIDDEN')
        if path.is_file():
            actual.add(path.relative_to(context).as_posix())
    need(actual == listed and len(listed) == len(gate['contextFiles']), 'EXACT_CONTEXT_TREE')
    need(set(actual) == {'Dockerfile', 'CONTEXT.json'} |
         {'overlay/' + safe_relative(row['path']) for row in plan['overlay']}, 'CONTEXT_ONLY_QUALIFIED_OVERLAY')
    need(len(plan['overlay']) == len({row['path'] for row in plan['overlay']}), 'DUPLICATE_OVERLAY_PATH')
    for row in plan['overlay']:
        need(row['path'] in rows and all(row[k] == rows[row['path']][k] for k in ('path', 'bytes', 'sha256')),
             'OVERLAY_CLOSURE_DISAGREEMENT')
        need(Path(row['path']).suffix in ('.py', '.mjs', '.js', '.json', '.md', '.LICENSE'), 'PUBLIC_IMAGE_SOURCE_FILES_ONLY')
    # Permit only the fixed parent, copy of audited public files, pinned private-root
    # directory creation and manifest-bound existing ENTRYPOINT. Never RUN arbitrary code.
    dockerfile = (context / 'Dockerfile').read_text()
    commands = ['FROM ' + PARENT,
                'COPY --chown=0:0 ' + json.dumps(['overlay/', ROOT + '/'])]
    directories = plan.get('precreatedDirectories', [])
    allowed_directories = [
        {'path': '/workspace', 'uid': 0, 'gid': 0, 'mode': '0755'},
        {'path': '/workspace/shared', 'uid': 1000, 'gid': 1000, 'mode': '0700'},
    ]
    if directories:
        need(directories == allowed_directories, 'PRIVATE_DIRECTORY_CONTRACT')
        commands.append('RUN install -d -o 0 -g 0 -m 0755 /workspace && install -d -o 1000 -g 1000 -m 0700 /workspace/shared')
    commands.append('ENTRYPOINT ' + json.dumps(plan['entrypoint']))
    need(dockerfile == '\n'.join(commands) + '\n', 'DOCKERFILE_EXACT_ALLOWLIST')
    prefix = ['/usr/bin/tini', '-g', '--', '/usr/bin/python3', '-I', '-B',
              ROOT + '/world-simulation-shorts-engine/recovery/studio-cold-start-v2/bootstrap.py']
    expected = prefix + ['--startup-manifest', ROOT + '/world-simulation-shorts-engine/recovery/studio-cold-start-v2/STARTUP_MANIFEST.json',
                        '--startup-manifest-sha256', plan['startupManifestSHA256'],
                        '--source-manifest', ROOT + '/world-simulation-shorts-engine/recovery/codex-to-gcube-handoff-v1/RUNTIME_SOURCE_MANIFEST.json',
                        '--source-manifest-sha256', plan['runtimeManifestSHA256'], '--export-root', '/world-storage']
    need(plan['entrypoint'] == expected, 'EXISTING_ENTRYPOINT_CONTRACT')
    return gate, plan, closure, context


def installed_probe(common, tag, plan, closure):
    command = ['docker', '--host=unix:///var/run/docker.sock', 'run', '--rm', '-i', '--network', 'none',
               '--read-only', '--user', '1000:1000', '--cap-drop=ALL', '--security-opt=no-new-privileges',
               '--tmpfs', '/tmp:rw,nosuid,size=64m', '-e', 'NVIDIA_VISIBLE_DEVICES=void',
               '-e', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', '/usr/bin/python3', tag,
               '-I', '-B', '-c', (HERE / 'probe_installed.py').read_text()]
    result = json.loads(common.run_command(command, input=json.dumps({'root': ROOT, 'plan': plan, 'closure': closure})))
    need(result.get('status') == 'PASS' and result.get('gpuStarts') == 0
         and result.get('renderedFrames') == 0 and result.get('filesChecked') == len(closure['files']),
         'INSTALLED_CLOSURE_PROBE_FAILED')
    return result


def entrypoint_probe(common, tag, image_id):
    args = ['docker', '--host=unix:///var/run/docker.sock', 'run', '--rm', '--network', 'none',
            '--read-only', '--cap-drop=ALL', '--cap-add=CHOWN', '--security-opt=no-new-privileges',
            '--tmpfs', '/run:rw,nosuid,size=16m', '--tmpfs', '/world-storage:rw,nosuid,size=16m',
            '-e', 'NVIDIA_VISIBLE_DEVICES=void', '-e', 'GPU_BACKEND=vulkan',
            '-e', 'WORLD_ENGINE_DEPLOYMENT_IMAGE_DIGEST=' + image_id,
            '-e', 'WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST=' + image_id,
            '-e', 'WORLD_ENGINE_STUDIO_STATE_ROOT=/run/final-cpu-only-private',
            '-e', 'WORLD_ENGINE_STUDIO_OWNER_CODE=', '-e', 'WORLD_ENGINE_OWNER_CODE=', tag]
    completed = subprocess.run(args, capture_output=True, text=True, timeout=60)
    lines = [json.loads(line) for line in completed.stdout.splitlines() if line.strip()]
    need(completed.returncode == 1 and not completed.stderr and len(lines) == 1, 'ENTRYPOINT_SINGLE_AUTH_BOUNDARY')
    row = lines[0]
    need(row.get('stage') == 'COLD_START_BLOCKED' and row.get('errorCode') == 'STUDIO_OWNER_CONFIGURATION_REQUIRED'
         and row.get('listenerStarted') is False and row.get('renderAutomaticallyStarted') is False,
         'ENTRYPOINT_UNEXPECTED_BLOCKER_OR_SIDE_EFFECT')
    return {'status': 'PASS', 'scope': 'ACTUAL_ENTRYPOINT_EXPECTED_MISSING_OWNER_BOUNDARY',
            'observed': row, 'listenerStarted': False, 'privateInstallAttempted': False,
            'gpuStarts': 0, 'renderedFrames': 0, 'oldPASSReruns': 0}


def old_backup(keep):
    release = keep.api(keep.API + '/releases/tags/' + OLD_BACKUP_TAG)
    need(release.get('draft') is False and release.get('tag_name') == OLD_BACKUP_TAG, 'PARENT_BACKUP_RELEASE')
    assets = keep.api(keep.API + '/releases/' + str(release['id']) + '/assets?per_page=100')
    matches = [a for a in assets if a['name'] == 'RETENTION_RESULT.json']
    need(len(matches) == 1, 'PARENT_BACKUP_RECEIPT_MISSING')
    asset = matches[0]
    with urllib.request.urlopen(asset['browser_download_url'], timeout=60) as response:
        raw = response.read(4 * 1024**2)
    need(len(raw) == asset['size'] and 'sha256:' + sha(raw) == asset['digest'], 'PARENT_BACKUP_RECEIPT_HASH')
    retained = json.loads(raw)
    need(retained.get('status') == 'PASS' and retained.get('archiveRootDigest') == PARENT_DIGEST,
         'PARENT_BACKUP_DIGEST')
    available = {a['id']: a for a in assets}
    for row in retained['assets']:
        need(row['id'] in available and all(row[k] == available[row['id']][k]
             for k in ('name', 'size', 'digest', 'browser_download_url')), 'PARENT_BACKUP_ASSET_AVAILABILITY')
    return retained


def private_installer_qualification(temp, plan):
    result = json.loads((temp / 'korean-war-20s-private-fixture-result.json').read_bytes())
    need(result.get('schema') == 'WORLD_ENGINE_PRIVATE_INSTALLER_QUALIFICATION_V1'
         and result.get('status') == 'PASS' and result.get('productionUid1000Verified') is True
         and len(result.get('checks', [])) == 7
         and all(row.get('status') == 'PASS' for row in result['checks'])
         and result.get('installerSHA256') == sha((HERE / 'private-package/private_bundle.py').read_bytes())
         == plan.get('privateInstallerSHA256'),
         'NEW_PRIVATE_INSTALLER_PRODUCTION_OWNERSHIP_REQUIRED')
    return result


def main():
    keep = None
    output = None
    release = None
    try:
        need(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REPOSITORY') == REPOSITORY
             and os.environ.get('GITHUB_RUN_ATTEMPT') == '1'
             and os.environ.get('GITHUB_REF') == 'refs/heads/' + BRANCH
             and os.environ.get('GITHUB_EVENT_NAME') == 'push', 'AUTHORIZED_SINGLE_ATTEMPT_ACTION_REQUIRED')
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_bytes())
        need(event['repository'].get('private') is False and event['before'] == os.environ['WORLD_ENGINE_EXPECTED_PREPARATION_HEAD']
             and event.get('head_commit', {}).get('message') == 'WORLD_ENGINE_KOREAN_WAR_20S_IMAGE_A1', 'PUBLIC_ACTIVATION_EVENT_GUARD')
        repo = Path(os.environ['GITHUB_WORKSPACE']).resolve()
        need(HERE == repo / PACKAGE, 'BUILDER_INSTALL_PATH')
        temp = Path(os.environ['RUNNER_TEMP'])
        output = temp / 'korean-war-20s-build-evidence'
        output.mkdir(exist_ok=False)
        def write(name, value):
            (output / name).write_bytes(encoded(value))
        common = load('_reused_reference_image_helpers', repo / HELPERS / 'build_once.py')
        need(common.run_command(['git', 'rev-parse', 'HEAD']) == os.environ['GITHUB_SHA']
             and common.run_command(['git', 'rev-parse', 'HEAD^']) == os.environ['WORLD_ENGINE_EXPECTED_PREPARATION_HEAD'],
             'EXACT_ACTIVATION_PARENT')
        need(common.run_command(['git', 'diff', '--name-only', 'HEAD^', 'HEAD']).splitlines() == [WORKFLOW],
             'ACTIVATION_ONLY_WORKFLOW_CHANGE')
        gate, plan, closure, context = qualification(repo)
        write('PRIVATE_INSTALLER_QUALIFICATION.json', private_installer_qualification(temp, plan))
        write('BUILD_GATE_ACCEPTED.json', {'status': 'PASS', 'gateSHA256': sha((HERE / 'BUILD_GATE.json').read_bytes()),
                                         'sourceCommit': gate['sourceCommit'], 'buildCommit': os.environ['GITHUB_SHA'],
                                         'oldPASSReruns': 0, 'gpuStarts': 0})
        write('PLAN.json', plan)
        need(common.registry(OLD_TAG)[1] == PARENT_DIGEST, 'PRESERVED_V16_TAG_CHANGED')
        tag = 'korean-war-20s-v17-' + os.environ['GITHUB_RUN_ID']
        remote = IMAGE + ':' + tag
        common.absent(tag)
        info = json.loads(common.docker('info', '--format', '{{json .}}'))
        need(['driver-type', 'io.containerd.snapshotter.v1'] in info.get('DriverStatus', []), 'CONTAINERD_IMAGE_STORE_REQUIRED')
        need(shutil.disk_usage(temp).free > 12 * 1024**3, 'INITIAL_ARCHIVE_DISK_CAPACITY')
        auth = temp / 'korean-war-20s-docker-auth'
        auth.mkdir(mode=0o700)
        os.environ['DOCKER_CONFIG'] = str(auth)
        common.run_command(['docker', '--host=unix:///var/run/docker.sock', 'login', 'ghcr.io',
                            '--username', os.environ['GITHUB_ACTOR'], '--password-stdin'], input=os.environ['GH_TOKEN'])
        common.docker_once(['pull', PARENT])
        parent = json.loads(common.docker('image', 'inspect', PARENT))[0]
        need(PARENT in parent['RepoDigests'], 'PULLED_PARENT_DIGEST')
        need(shutil.disk_usage(temp).free > parent['Size'] * 3 + 2 * 1024**3, 'ARCHIVE_AND_RECOVERY_DISK_CAPACITY')
        keep = load('_reused_image_retention', repo / HELPERS / 'retain_quality_image.py')
        keep.ROOT = temp / 'korean-war-20s-image-backup'
        keep.ROOT.mkdir(exist_ok=False)
        keep.SOURCE = os.environ['GITHUB_SHA']
        keep.PARENT = PARENT_DIGEST
        keep.RELEASE_TAG = 'korean-war-20s-image-backup-' + os.environ['GITHUB_RUN_ID']
        recovery = load('_image_backup_recovery', HERE / 'verify_backup.py')
        retained_parent = old_backup(keep)
        if gate.get('parentBackupRecovery'):
            reused = json.loads(file_receipt(repo, gate['parentBackupRecovery']))
            need(reused.get('status') == 'PASS' and reused.get('archiveRootDigest') == PARENT_DIGEST
                 and reused.get('dockerLoadVerified') is True, 'PARENT_RECOVERY_PASS_INVALID')
            parent_proof = {'status': 'PASS', 'reusedRecoveryPASS': gate['parentBackupRecovery'],
                            'archiveRootDigest': PARENT_DIGEST, 'releaseURL': retained_parent['releaseURL']}
        else:
            parent_proof = recovery.verify(keep, retained_parent, keep.ROOT / 'parent-roundtrip.tar', PARENT_DIGEST)
        write('PARENT_BACKUP_VERIFICATION.json', parent_proof)
        release = keep.api(keep.API + '/releases', {
            'tag_name': keep.RELEASE_TAG, 'target_commitish': os.environ['GITHUB_SHA'],
            'name': 'Korean war 20s image backup ' + os.environ['GITHUB_RUN_ID'],
            'body': 'One authorized public-code image backup before GHCR publication. Private raw data excluded. No GPU or rendering. Existing tags preserved.',
            'draft': False, 'prerelease': True, 'make_latest': 'false'})
        keep.write('RELEASE.json', release)
        keep.write('RESERVATION.json', {'sourceCommit': keep.SOURCE, 'parentDigest': PARENT_DIGEST,
                                      'maxBuilds': 1, 'maxGHCRPublications': 1, 'retries': 0})
        asset = keep.upload(release, keep.ROOT / 'RESERVATION.json')
        keep.write('RESERVATION_RESULT.json', {'status': 'PASS', 'releaseURL': release['html_url'], 'asset': asset})
        local_tag = 'world-engine-korean-war-20s:unpublished-' + os.environ['GITHUB_RUN_ID']
        os.environ['TAG'] = local_tag
        common.docker_once(['build', '--platform', 'linux/amd64', '--provenance=false', '--sbom=false',
                            '--network', 'none', '--pull=false', '--tag', local_tag, str(context)])
        candidate = json.loads(common.docker('image', 'inspect', local_tag))[0]
        config = dict(parent['Config'])
        config['Entrypoint'] = plan['entrypoint']
        need(candidate['Config'] == config, 'ONLY_MANIFEST_BOUND_ENTRYPOINT_CONFIG_CHANGE')
        parent_layers, layers = parent['RootFS']['Layers'], candidate['RootFS']['Layers']
        need(layers[:len(parent_layers)] == parent_layers
             and len(layers) == len(parent_layers) + 1 + bool(plan.get('precreatedDirectories')), 'EXACT_ADDITIVE_IMAGE_LAYERS')
        probe_failure = None
        try:
            write('INSTALLED_PROBE.json', installed_probe(common, local_tag, plan, closure))
            write('ENTRYPOINT_PROBE.json', entrypoint_probe(common, local_tag, candidate['Id']))
        except Exception as error:
            probe_failure = error
        # Preserve the one built candidate even if its new closure probe blocks publication.
        keep.archive()
        retained = keep.read('RETENTION_RESULT.json')
        need(retained.get('status') == 'PASS' and retained['archiveRootDigest'] == candidate['Id']
             and retained['rootFSDiffIDs'] == layers, 'BACKUP_EXACT_CANDIDATE')
        archive = keep.ROOT / 'candidate-image.tar'
        with archive.open('rb') as stream:
            original_tar_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
        archive.unlink()
        for part in keep.ROOT.glob('candidate-image.tar.gz.part-*'):
            part.unlink()
        proof = recovery.verify(keep, retained, keep.ROOT / 'candidate-roundtrip.tar', candidate['Id'],
                                original_tar_sha256=original_tar_sha)
        write('BACKUP_DOWNLOAD_RESTORE.json', proof)
        if probe_failure is not None:
            raise probe_failure
        common.absent(tag)
        need(common.registry(OLD_TAG)[1] == PARENT_DIGEST, 'PRESERVED_V16_TAG_CHANGED_BEFORE_PUSH')
        common.docker('tag', local_tag, remote)
        common.docker_once(['push', remote])
        raw, digest = common.registry(tag)
        pinned, confirmed = common.registry(digest)
        need(raw == pinned and digest == confirmed == candidate['Id'] == retained['archiveRootDigest'],
             'PUBLISHED_ROOT_DESCRIPTOR_IDENTITY')
        manifest = json.loads(raw)
        if 'manifests' in manifest:
            need(len(manifest['manifests']) == 1 and manifest['manifests'][0]['digest'] == retained['imageManifestDigest'],
                 'PUBLISHED_SINGLE_PLATFORM_IDENTITY')
            image_raw, image_digest = common.registry(retained['imageManifestDigest'])
            need(image_digest == retained['imageManifestDigest'], 'PUBLISHED_IMAGE_MANIFEST_IDENTITY')
            manifest = json.loads(image_raw)
        need(manifest['config']['digest'] == retained['configDigest'], 'PUBLISHED_CONFIG_IDENTITY')
        need(common.registry(OLD_TAG)[1] == PARENT_DIGEST, 'PRESERVED_V16_TAG_CHANGED_AFTER_PUSH')
        write('RESULT.json', {'status': 'PASS', 'scope': 'IMAGE_AND_BACKUP_READY_GPU_PENDING',
                             'sourceCommit': gate['sourceCommit'], 'buildCommit': os.environ['GITHUB_SHA'],
                             'image': remote, 'digest': digest, 'pinnedImage': IMAGE + '@' + digest,
                             'parentImage': PARENT, 'parentTagPreserved': OLD_TAG,
                             'configDigest': retained['configDigest'], 'imageManifestDigest': retained['imageManifestDigest'],
                             'backupReleaseURL': retained['releaseURL'], 'backupDownloadAndLoadVerified': True,
                             'runtimeManifestSHA256': plan['runtimeManifestSHA256'],
                             'startupManifestSHA256': plan['startupManifestSHA256'],
                             'publicSourceClosureSHA256': gate['sourceClosure']['sha256'],
                             'privateAssetReceiptSHA256': gate['privateAssets']['receipt']['sha256'],
                             'studioInputs': gate['studioInputs']['inputs'], 'builds': 1, 'publications': 1,
                             'retries': 0, 'oldPASSReruns': 0, 'gpuStarts': 0, 'renderedFrames': 0,
                             'gCubeConfigurationSaved': False, 'gpuCompatibility': 'GPU_PENDING'})
        print('WORLD_ENGINE_IMAGE_BUILD_STATUS=PASS', flush=True)
    except Exception as error:
        reason = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        if output is not None:
            (output / 'RESULT.json').write_bytes(encoded({'status': 'BLOCKED', 'reason': reason,
                                                       'automaticRetryForbidden': True,
                                                       'gpuStarts': 0, 'renderedFrames': 0}))
        print('WORLD_ENGINE_IMAGE_BUILD_STATUS=BLOCKED:' + reason, flush=True)
        raise SystemExit(1)
    finally:
        if keep is not None and release is not None and output is not None:
            for file in sorted(output.glob('*.json')):
                keep.upload(release, file)


if __name__ == '__main__':
    main()
