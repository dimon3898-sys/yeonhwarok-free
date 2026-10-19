#!/usr/bin/env python3
"""Install only absent, hash-bound original JSON/GeoJSON fixture metadata.

Existing identical files are read and left entirely unchanged. A conflicting,
symlinked, special or unsafe path stops the operation before installation.
No protected source, existing file mode/owner, image, GPU or account is changed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat

HERE=Path(__file__).resolve().parent
SOURCE_COMMIT='61c7fc3a36cc987c3f88844aba98c57bb62fe22e'
INSTALLED_REPO=Path('/opt/rtx-package/repo')
PREFIX='world-simulation-shorts-engine/recovery/'
_HEX=re.compile('[a-f0-9]{64}\\Z')


def _open_tree(path):
 path=Path(path)
 if not path.is_absolute() or '..' in path.parts:raise RuntimeError('COMPLETION_FIXTURE_ROOT_UNSAFE')
 descriptor=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
 try:
  for component in path.parts[1:]:
   child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=descriptor)
   os.close(descriptor);descriptor=child
  return descriptor
 except BaseException:
  os.close(descriptor);raise


def _regular(file,maximum=4*1024**2):
 file=Path(file);parent=_open_tree(file.parent)
 try:
  descriptor=os.open(file.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
  try:
   before=os.fstat(descriptor)
   if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=maximum:
    raise RuntimeError('COMPLETION_FIXTURE_REGULAR_FILE_REQUIRED')
   raw=os.read(descriptor,maximum+1);after=os.fstat(descriptor)
   if len(raw)!=before.st_size or (before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns):
    raise RuntimeError('COMPLETION_FIXTURE_CHANGED_DURING_READ')
   return raw
  finally:os.close(descriptor)
 finally:os.close(parent)


def _canonical(name):
 if (not isinstance(name,str) or '\\' in name or '\x00' in name or PurePosixPath(name).is_absolute()
     or str(PurePosixPath(name))!=name or any(p in {'','.','..'} for p in name.split('/'))
     or not name.startswith(PREFIX) or not name.endswith(('.json','.geojson'))):
  raise RuntimeError('COMPLETION_FIXTURE_PATH_UNSAFE')
 relative=name[len(PREFIX):]
 if not (relative.startswith('verified-front-data-v4-recovery/') or relative=='universal-auto-video-v2/fixtures/NATIVE_PAYLOAD.json'):
  raise RuntimeError('COMPLETION_FIXTURE_TARGET_NOT_ADMITTED')
 return name


def _target_parent(root_fd,relative,*,create=False):
 descriptor=os.dup(root_fd)
 try:
  for component in PurePosixPath(relative).parts[:-1]:
   if create:
    try:os.mkdir(component,0o755,dir_fd=descriptor)
    except FileExistsError:pass
   child=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=descriptor)
   os.close(descriptor);descriptor=child
  return descriptor
 except BaseException:
  os.close(descriptor);raise


def _existing(parent,name):
 try:descriptor=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
 except FileNotFoundError:return None
 try:
  info=os.fstat(descriptor)
  if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=4*1024**2:
   raise RuntimeError('COMPLETION_FIXTURE_EXISTING_PATH_UNSAFE')
  raw=os.read(descriptor,4*1024**2+1)
  if len(raw)!=info.st_size:raise RuntimeError('COMPLETION_FIXTURE_EXISTING_CHANGED')
  return hashlib.sha256(raw).hexdigest()
 finally:os.close(descriptor)


def install(payload_root,*,target_root=INSTALLED_REPO,manifest_file=None):
 payload_root,target_root=Path(payload_root),Path(target_root)
 manifest_file=Path(manifest_file) if manifest_file else HERE/'PACKAGED_FIXTURES.json'
 manifest_raw=_regular(manifest_file);payload_manifest=_regular(payload_root/'PACKAGED_FIXTURES.json')
 if manifest_raw!=payload_manifest:raise RuntimeError('COMPLETION_FIXTURE_MANIFEST_BINDING_MISMATCH')
 manifest=json.loads(manifest_raw);rows=manifest.get('files')
 if (manifest.get('schema')!='WORLD_ENGINE_PACKAGED_FIXTURES_V1' or manifest.get('sourceCommit')!=SOURCE_COMMIT
     or not isinstance(rows,list) or not 1<=len(rows)<=32):
  raise RuntimeError('COMPLETION_FIXTURE_MANIFEST_INVALID')
 prepared=[];seen=set();root=_open_tree(target_root)
 try:
  # Validate the complete source/target set before installing any missing file.
  for row in rows:
   if not isinstance(row,dict) or set(row)!={'repoPath','target','sha256','sourceCommit','bytes'}:
    raise RuntimeError('COMPLETION_FIXTURE_RECORD_INVALID')
   relative=_canonical(row['repoPath'])
   if (relative in seen or row['target']!=str(INSTALLED_REPO/relative) or row['sourceCommit']!=SOURCE_COMMIT
       or not _HEX.fullmatch(str(row['sha256'])) or type(row['bytes']) is not int or not 0<row['bytes']<=4*1024**2):
    raise RuntimeError('COMPLETION_FIXTURE_RECORD_INVALID')
   seen.add(relative);raw=_regular(payload_root/'repo'/relative)
   if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:
    raise RuntimeError('COMPLETION_FIXTURE_SOURCE_SHA_MISMATCH')
   try:parent=_target_parent(root,relative)
   except FileNotFoundError:present=None
   else:
    try:present=_existing(parent,Path(relative).name)
    finally:os.close(parent)
   if present is not None and present!=row['sha256']:raise RuntimeError('COMPLETION_FIXTURE_EXISTING_CONFLICT')
   prepared.append((row,raw,present is not None))
  installed=identical=0
  for row,raw,present in prepared:
   if present:identical+=1;continue
   relative=row['repoPath'];parent=_target_parent(root,relative,create=True);name=Path(relative).name
   temporary='.completion-fixture-'+secrets.token_hex(16);descriptor=None;created=False
   try:
    descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent);created=True
    offset=0
    while offset<len(raw):offset+=os.write(descriptor,raw[offset:])
    os.fsync(descriptor);os.fchmod(descriptor,0o444);os.close(descriptor);descriptor=None
    try:os.link(temporary,name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
    except FileExistsError:
     if _existing(parent,name)!=row['sha256']:raise RuntimeError('COMPLETION_FIXTURE_EXISTING_CONFLICT')
     identical+=1
    else:installed+=1
    os.fsync(parent)
   finally:
    if descriptor is not None:os.close(descriptor)
    if created:os.unlink(temporary,dir_fd=parent)  # Only this invocation's new temp file.
    os.close(parent)
  return {'status':'PASS','files':len(prepared),'installedAbsentFiles':installed,'existingIdenticalPreserved':identical,
   'existingFilesOverwritten':0,'existingModesChanged':0,'existingOwnersChanged':0,'gpuExecuted':False}
 finally:os.close(root)


if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--payload',type=Path,required=True)
 parser.add_argument('--target-root',type=Path,default=INSTALLED_REPO);args=parser.parse_args()
 if args.target_root!=INSTALLED_REPO:raise SystemExit('COMPLETION_FIXTURE_FIXED_TARGET_REQUIRED')
 print(json.dumps(install(args.payload,target_root=args.target_root),sort_keys=True))
