#!/usr/bin/env python3
"""Bind the existing CPU/provider/upload layers to one private ASTRA activation.

No network, shader/GPU invocation, new cache, original source rewrite or paid job.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ENGINE=HERE.parents[1]
REPO=ENGINE.parent
SCHEMA='ASTRA_ACTIVATION_FILES_V1'
PROFILE_ID='ASTRA_SOURCE_MATERIAL_V1'
PROFILE_FILE=HERE/'SCENE_MAP_DATA.json'
MANIFEST_FILE=HERE/'ACTIVATION_FILES.json'
_SHA=re.compile(r'[0-9a-f]{64}\Z')
MAX_JSON=2*1024*1024


class ActivationError(ValueError):
    pass


def _regular(path,limit=MAX_JSON):
    path=Path(path)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=limit:
            raise ActivationError('ACTIVATION_REGULAR_BOUNDED_FILE_REQUIRED')
        body=b''
        while len(body)<info.st_size:
            part=os.read(fd,info.st_size-len(body))
            if not part: raise ActivationError('ACTIVATION_FILE_CHANGED')
            body+=part
        after=os.fstat(fd)
        if (info.st_ino,info.st_dev,info.st_size,info.st_mtime_ns)!=(after.st_ino,after.st_dev,after.st_size,after.st_mtime_ns):
            raise ActivationError('ACTIVATION_FILE_CHANGED')
        return body
    finally: os.close(fd)


def _relative(root,value):
    if not isinstance(value,str) or not value or value.startswith('/') or '\\' in value or any(x in ('','.','..') for x in value.split('/')):
        raise ActivationError('ACTIVATION_CANONICAL_PATH_REQUIRED')
    path=Path(root)
    for part in PurePosixPath(value).parts:
        path=path/part
        if path.is_symlink(): raise ActivationError('ACTIVATION_SOURCE_SYMLINK_FORBIDDEN')
    return path


def _sha(body): return hashlib.sha256(body).hexdigest()


def verify_extension(package_root=Path('/opt/rtx-package'),*,require_staged=True):
    """Verify additive closure; production also reuses original immutable contract.

    require_staged=False is CPU source-only verification and returns TEST_ONLY;
    the production launcher and capture never request that option.
    """
    raw=_regular(MANIFEST_FILE); manifest=json.loads(raw)
    if manifest.get('schema')!=SCHEMA or manifest.get('profileId')!=PROFILE_ID or not isinstance(manifest.get('files'),dict) or not manifest['files']:
        raise ActivationError('ACTIVATION_MANIFEST_REQUIRED')
    count=0
    for name,expected in manifest['files'].items():
        if '/' in name or not _SHA.fullmatch(str(expected)) or _sha(_regular(_relative(HERE,name),64*1024*1024))!=expected:
            raise ActivationError('ACTIVATION_EXTENSION_HASH_MISMATCH')
        count+=1
    dependencies=manifest.get('repoDependencies',{})
    if not isinstance(dependencies,dict): raise ActivationError('ACTIVATION_DEPENDENCY_MANIFEST_REQUIRED')
    for relative,expected in dependencies.items():
        if not _SHA.fullmatch(str(expected)) or _sha(_regular(_relative(REPO,relative),64*1024*1024))!=expected:
            raise ActivationError('ACTIVATION_DEPENDENCY_HASH_MISMATCH')
        count+=1
    for item in manifest.get('inheritedFiles',[]):
        if not isinstance(item,dict) or not _SHA.fullmatch(str(item.get('sha256'))):
            raise ActivationError('ACTIVATION_INHERITED_MANIFEST_INVALID')
        selected=Path(item['imagePath']) if require_staged else _relative(REPO,item['repoPath'])
        if _sha(_regular(selected,64*1024*1024))!=item['sha256']:
            raise ActivationError('ACTIVATION_INHERITED_SOURCE_CHANGED')
        count+=1
    original=None
    if require_staged:
        file=REPO/'world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/stage_package.py'
        spec=importlib.util.spec_from_file_location('_astra_original_stage_verifier',file)
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        original=mod.verify_staged_context(package_root)
        if original.get('status')!='PASS': raise ActivationError('ACTIVATION_PARENT_SOURCE_INVALID')
    return {'status':'PASS','schema':SCHEMA,'manifestSha256':_sha(raw),'files':count,
            'sourceCommit':manifest.get('sourceCommit'),'profileId':PROFILE_ID,
            'testOnly':not require_staged,'gpuExecuted':False,'parent':original}


def prepare_activation(private_root,scene_profile_file=None):
    """Lossless regional bundle in a new private directory; never touches old jobs.

    The launcher calls verify_extension before this function. A custom profile is
    a programmatic preparation input only; production CLI always uses the pinned
    image profile. Source selection remains explicit, never country inference.
    """
    sys.path.insert(0,str(HERE.parent/'astra-cpu-data-v1'))
    sys.path.insert(0,str(HERE.parent/'astra-gpu-integration-v1'))
    from astra_cpu.providers import ArchiveCatalog
    from astra_cpu.scene import prepare_scene
    from upload_bundle import prepare_upload_bundle
    profile_path=PROFILE_FILE if scene_profile_file is None else Path(scene_profile_file)
    profile=json.loads(_regular(profile_path))
    allowed={'schema','profileId','fixtureFile','scenePlanFile','visualAdmissionFile','materialProfile','mapData','coveragePolicy'}
    if (set(profile)-allowed or profile.get('schema')!='ASTRA_SCENE_MAP_DATA_PROFILE_V1'
        or profile.get('profileId')!=PROFILE_ID or not isinstance(profile.get('mapData'),dict)
        or profile['mapData'].get('enabled') is not True):
        raise ActivationError('ACTIVATION_PROFILE_INVALID')
    source_scene=_relative(ENGINE,profile['scenePlanFile']); scene_bytes=_regular(source_scene)
    original=json.loads(scene_bytes); augmented=deepcopy(original);augmented['mapData']=deepcopy(profile['mapData'])
    archive=ENGINE/'recovery/astra-map-quality-v1/inputs/ESSENTIAL_MAP_SAMPLES.zip'
    catalog=ArchiveCatalog(archive,license_verified=True)
    preparation=prepare_scene(augmented,catalog)
    if preparation.renderer_scene!=original or preparation.gpu_activation is not False:
        raise ActivationError('ACTIVATION_OLD_SCENE_MUTATED')
    root=Path(private_root)
    if not root.is_absolute() or root.is_symlink(): raise ActivationError('ACTIVATION_PRIVATE_ROOT_REQUIRED')
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        info=os.fstat(fd)
        if info.st_uid!=os.getuid() or info.st_mode&0o077:
            raise ActivationError('ACTIVATION_PRIVATE_ROOT_REQUIRED')
        # tempfile uses exclusive mkdir and unpredictable names beneath this root.
        output=Path(tempfile.mkdtemp(prefix='astra-activation-',dir=root)); output.chmod(0o700)
        if root.stat().st_ino!=info.st_ino or root.stat().st_dev!=info.st_dev:
            raise ActivationError('ACTIVATION_PRIVATE_ROOT_CHANGED')
    finally: os.close(fd)
    bundle_dir=output/'bundle'
    bundle=prepare_upload_bundle(augmented,catalog,bundle_dir,max_bytes=64*1024*1024)
    required={'terrain','bathymetry','surfaceTexture'}
    if set(bundle['sources'])!=required or any(item.get('status')!='available' or not item.get('parts') for item in bundle['sources'].values()):
        raise ActivationError('ACTIVATION_SOURCE_UNAVAILABLE')
    if bundle['rendererPayloadSHA256']!=preparation.renderer_sha256:
        raise ActivationError('ACTIVATION_RENDERER_PAYLOAD_CHANGED')
    manifest_path=bundle_dir/'UPLOAD_BUNDLE.json'; manifest_sha=_sha(_regular(manifest_path))
    activation={key:deepcopy(profile[key]) for key in ('profileId','fixtureFile','scenePlanFile','visualAdmissionFile','materialProfile')}
    activation.update(schema='ASTRA_GPU_ACTIVATION_PROFILE_V1',bundleManifestFile=str(manifest_path),
        bundleManifestSha256=manifest_sha,sceneMapData=deepcopy(profile['mapData']),
        rendererPayloadSha256=preparation.renderer_sha256,scenePlanByteSha256=_sha(scene_bytes))
    body=(json.dumps(activation,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    target=output/'activation.json'
    descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,'wb') as destination:
        destination.write(body);destination.flush();os.fsync(destination.fileno())
    return {'activationFile':str(target),'activationSha256':_sha(body),
        'bundleManifestSha256':manifest_sha,'profileId':PROFILE_ID,
        'rendererPayloadSha256':preparation.renderer_sha256,
        'sources':{role:{'status':item['status'],'parts':len(item['parts']),
                   'sourceSHA256':item['SHA-256'],'coverage':item.get('coverage')}
                   for role,item in bundle['sources'].items()},
        'artifactBytes':bundle['artifactBytes'],'gpuExecuted':False,'sourceProfileModified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--verify-extension',action='store_true')
    group.add_argument('--prepare-activation',action='store_true')
    parser.add_argument('--private-root',type=Path)
    parser.add_argument('--source-only',action='store_true',help='CPU-only verification, never GPU admission')
    args=parser.parse_args()
    try:
        if args.verify_extension: result=verify_extension(require_staged=not args.source_only)
        elif args.private_root is not None and not args.source_only: result=prepare_activation(args.private_root)
        else: raise ActivationError('ACTIVATION_EXPLICIT_ARGUMENTS_REQUIRED')
        print(json.dumps(result,sort_keys=True,allow_nan=False))
    except Exception as error:
        code=str(error)
        if re.fullmatch(r'[A-Z][A-Z0-9_]{1,95}',code) is None: code='ASTRA_ACTIVATION_PREPARATION_FAILED'
        print(json.dumps({'status':'FAIL','errorCode':code,'errorType':type(error).__name__,'gpuExecuted':False}));raise SystemExit(1)
