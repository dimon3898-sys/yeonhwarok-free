"""Prepare source-bound inert inputs only; never admit or start a GPU/job."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import sys

HERE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location('_overnight_prepare_' + name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def prepare(destination, *, image_digest=None, activation_file=None, activation_sha256=None):
    manifest = load('manifest', HERE / 'package_manifest.py')
    proof = manifest.verify_sources()
    image_digest = image_digest or manifest.BASE_IMAGE
    directory = Path(destination)
    if (not directory.is_absolute() or any(p.is_symlink() for p in (directory, *directory.parents))
            or directory.exists()):
        raise RuntimeError('OVERNIGHT_NEW_PRIVATE_INPUT_DIRECTORY_REQUIRED')
    directory.mkdir(mode=0o700, parents=True)
    if directory.stat().st_mode & 0o077:
        raise RuntimeError('OVERNIGHT_PRIVATE_INPUT_PERMISSIONS_REQUIRED')
    original = Path('/opt/world-engine-production-studio') if HERE.is_relative_to('/opt') else HERE.parent / 'production-studio-mvp-v1'
    sys.path.insert(0, str(original))
    import studio_contracts
    import studio_runtime
    contract = load('contract', HERE / 'contract_v3.py')
    profile = json.loads(manifest.read_regular(HERE / 'PREVIEW_PROFILE.json'))
    submission = contract.normalize_submission({'prompt': json.dumps(profile, ensure_ascii=False),
        'durationSeconds': profile['durationSeconds'], 'profile': profile['profile'],
        'sfx': profile['sfx']}, image_digest=image_digest, backend=studio_runtime,
        parent_normalize=studio_contracts.normalize_submission)
    bridge = load('bridge', HERE / 'runtime_bridge.py')
    request = bridge.prepare_runtime_request(submission, image_digest=image_digest)
    values = {'SUBMISSION.json': submission, 'PLAN.json': submission['videoPlan'],
              'OVERNIGHT_REQUEST.json': request, 'PREVIEW_REQUEST.json': request['preview'],
              'INTEGRATION_REQUEST.json': request['parentCaptureRequest']}
    for name, value in values.items():
        descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(manifest.canonical(value))
            output.flush()
            os.fsync(output.fileno())
    authority = load('authority', HERE / 'runtime_authority.py')
    authority.verify_runtime_sidecars(directory / 'OVERNIGHT_REQUEST.json', directory / 'PLAN.json')
    front = HERE.parent / 'verified-front-data-v4-recovery'
    front_manifest_raw = manifest.read_regular(front / 'FRONT_FILES.json')
    front_manifest = json.loads(front_manifest_raw)
    options = {'planFile': str(directory / 'PLAN.json'),
        'expectedPlanSha256': manifest.sha((directory / 'PLAN.json').read_bytes()),
        'sceneId': request['preview']['sceneSlices'][0]['sceneId'],
        'requestFile': str(directory / 'PREVIEW_REQUEST.json'),
        'overnightRequestFile': str(directory / 'OVERNIGHT_REQUEST.json'),
        'submissionFile': str(directory / 'SUBMISSION.json'),
        'frontProfileFile': str(front / 'FRONT_PROFILE.json'),
        'expectedFrontProfileSha256': front_manifest['files']['FRONT_PROFILE.json'],
        'frontManifestFile': str(front / 'FRONT_FILES.json'),
        'expectedFrontManifestSha256': manifest.sha(front_manifest_raw)}
    activation_file = activation_file or os.environ.get('WORLD_ENGINE_ASTRA_ACTIVATION_FILE')
    activation_sha256 = activation_sha256 or os.environ.get('WORLD_ENGINE_ASTRA_ACTIVATION_SHA256')
    if bool(activation_file) != bool(activation_sha256):
        raise RuntimeError('OVERNIGHT_ACTIVATION_FILE_AND_SHA_REQUIRED_TOGETHER')
    if activation_file:
        raw = manifest.read_regular(Path(activation_file))
        if manifest.sha(raw) != activation_sha256:
            raise RuntimeError('OVERNIGHT_ACTIVATION_ACTUAL_SHA_MISMATCH')
        options.update(activationFile=activation_file, expectedActivationSha256=activation_sha256)
    result = {'status': 'PASS', 'options': options, 'previewRange': request['preview']['range'],
              'sourceManifestSHA256': proof['manifestSHA256'], 'imageDigest': image_digest,
              'sourceBaseCommit': manifest.BASE_COMMIT, 'renderStarted': False,
              'gpuVerified': False, 'full80sRenderAllowed': False}
    descriptor = os.open(directory / 'PREPARED.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as output:
        json.dump(result, output, ensure_ascii=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', required=True)
    parser.add_argument('--image-digest')
    parser.add_argument('--activation-file')
    parser.add_argument('--activation-sha256')
    args = parser.parse_args()
    print(json.dumps(prepare(args.destination, image_digest=args.image_digest,
        activation_file=args.activation_file, activation_sha256=args.activation_sha256), ensure_ascii=False))
