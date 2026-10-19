"""Local immutable extension inventory. No image build, upload, or rendering."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'INTEGRATION_FILES.json'
BASE_COMMIT = 'c05ec96933d6e9e28cb96fd27602d82989a3a3e7'
BASE_IMAGE = 'sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
PARENT_FILES = (
 'production-studio-mvp-v1/studio_contracts.py', 'production-studio-mvp-v1/studio_runtime.py',
 'production-studio-mvp-v1/studio_controller.py', 'production-studio-mvp-v1/studio_audio.py',
 'production-studio-mvp-v1/studio_delivery.py', 'production-studio-mvp-v1/studio_common.py',
 'verified-front-data-v4-recovery/front_adapter.mjs', 'verified-front-data-v4-recovery/front_runtime.mjs',
 'verified-front-data-v4-recovery/front_visual.mjs', 'verified-front-data-v4-recovery/scene_binding.py',
 'verified-front-data-v4-recovery/VIDEO_PLAN_80S.json', 'verified-front-data-v4-recovery/FRONT_PROFILE.json',
 'universal-production-v3/production_area_pass.mjs', 'universal-production-v3/production_native_camera.mjs',
 'universal-production-v3/production_visual_profile.mjs', 'universal-auto-video-v2/long_runtime.mjs',
 'verified-front-data-v4-recovery/render_adapter.py', 'verified-front-data-v4-recovery/orchestrator.py',
 'universal-auto-video-v2/long_capture.mjs')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read_regular(path, limit=16*1024*1024):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('INTEGRATION_SOURCE_PATH_UNSAFE')
    before = path.stat()
    if not path.is_file() or not 0 < before.st_size <= limit:
        raise RuntimeError('INTEGRATION_SOURCE_SIZE_INVALID')
    raw = path.read_bytes(); after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns) or len(raw) != before.st_size:
        raise RuntimeError('INTEGRATION_SOURCE_CHANGED_DURING_READ')
    return raw


def parent_path(name):
    if HERE.is_relative_to('/opt') and name.startswith('production-studio-mvp-v1/'):
        return Path('/opt/world-engine-production-studio')/name.split('/',1)[1]
    return HERE.parent/name


def build_manifest():
    files = {}
    for file in sorted(HERE.iterdir()):
        if file.is_file() and file.suffix in {'.py', '.mjs', '.json'} and file.name not in {'INTEGRATION_FILES.json', 'RUNTIME_SOURCE_MANIFEST.json'}:
            files[file.name] = sha(read_regular(file))
    parent = {name: sha(read_regular(parent_path(name))) for name in PARENT_FILES}
    value = {'schema': 'WORLD_ENGINE_UNIVERSAL_INTEGRATION_FILES_V1',
        'sourceBaseCommit': BASE_COMMIT, 'baseOperatingImageDigest': BASE_IMAGE,
        'registeredCandidateImageDigest': None, 'files': files, 'parentFiles': parent,
        'rendererOrShaderCopied': False, 'gpuVerified': False}
    MANIFEST.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode()+b'\n')
    source = {'schema': 'WORLD_ENGINE_UNIFIED_RUNTIME_SOURCE_MANIFEST_V1',
        'files': [{'path': name, 'sha256': digest} for name,digest in sorted(files.items())],
        'parentFiles': parent, 'sourceBaseCommit': BASE_COMMIT}
    (HERE/'RUNTIME_SOURCE_MANIFEST.json').write_bytes(json.dumps(source, ensure_ascii=False, indent=2).encode()+b'\n')
    return value


def verify_sources():
    raw = read_regular(MANIFEST)
    value = json.loads(raw)
    if value.get('schema') != 'WORLD_ENGINE_UNIVERSAL_INTEGRATION_FILES_V1' or value.get('sourceBaseCommit') != BASE_COMMIT:
        raise RuntimeError('INTEGRATION_SOURCE_MANIFEST_INVALID')
    files, parent = value.get('files'), value.get('parentFiles')
    if not isinstance(files, dict) or not files or set(parent or {}) != set(PARENT_FILES):
        raise RuntimeError('INTEGRATION_SOURCE_CLOSURE_INCOMPLETE')
    for root, entries in [(HERE,files),(HERE.parent,parent)]:
        for name,expected in entries.items():
            if not isinstance(name,str) or Path(name).is_absolute() or any(p in {'','..','.'} for p in name.split('/')) or '\\' in name:
                raise RuntimeError('INTEGRATION_SOURCE_NAME_INVALID')
            target=parent_path(name) if root==HERE.parent else root/name
            if sha(read_regular(target)) != expected:
                raise RuntimeError('INTEGRATION_SOURCE_HASH_MISMATCH')
    return {'status':'PASS','manifestSHA256':sha(raw),'files':len(files),'parentFiles':len(parent),
        'registeredCandidateImageDigest':value['registeredCandidateImageDigest'],'gpuVerified':False}


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build: build_manifest()
    print(json.dumps(verify_sources(),sort_keys=True))
