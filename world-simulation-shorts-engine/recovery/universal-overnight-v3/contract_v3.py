"""Explicit preview-only opt-in over the preserved, strict Studio V2 input.

This is not free-form AI planning or an operator authorization. Historical
videoPlan data stays byte-for-byte identical to the parent normalizer result.
"""
from copy import deepcopy
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'universal-integration-completion-v2'
ORIGINAL = Path('/opt/world-engine-production-studio') if HERE.is_relative_to('/opt') else HERE.parent / 'production-studio-mvp-v1'
if str(ORIGINAL) not in sys.path:
    sys.path.insert(0, str(ORIGINAL))
from studio_contracts import StudioContractError, _bounded_json
SCHEMA = 'WORLD_ENGINE_OVERNIGHT_SAFE_V3'
PROFILE = 'OVERNIGHT_SAFE_V3'
VISUAL_DEFAULT = {'schema':'WORLD_ENGINE_OVERNIGHT_VISUAL_V1','scalarTerritory':None,'nationalUnits':None}


def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    spec.loader.exec_module(module);return module


def fail(code, field='overnight'):
    raise StudioContractError(code, '지원되는 5초 Preview 입력과 자료 참조를 확인하세요.', (field,))


def normalize_visual(value):
    """The JS owner is the only parser for actual optional visual contracts."""
    _bounded_json(value)
    if not isinstance(value,dict): fail('STUDIO_OVERNIGHT_VISUAL_INVALID')
    script=HERE/'visual_extensions.mjs'
    if not script.is_file() or script.is_symlink():
        fail('STUDIO_OVERNIGHT_VISUAL_MODULE_UNAVAILABLE')
    result=subprocess.run(['node',str(script),'--normalize'], input=json.dumps(value,allow_nan=False).encode(),
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20,check=False)
    if result.returncode or len(result.stdout)>1024*1024:
        fail('STUDIO_OVERNIGHT_VISUAL_INVALID')
    try: normalized=json.loads(result.stdout)
    except (ValueError,TypeError): fail('STUDIO_OVERNIGHT_VISUAL_INVALID')
    return normalized


def normalize_overnight(value):
    _bounded_json(value)
    if not isinstance(value,dict) or set(value)-{'schema','profile','operation','startFrame','visualExtensions'}:
        fail('STUDIO_OVERNIGHT_FIELD_UNSUPPORTED')
    if value.get('schema')!=SCHEMA or value.get('profile')!=PROFILE:
        fail('STUDIO_OVERNIGHT_PROFILE_REQUIRED')
    if value.get('operation','PREVIEW_5S')!='PREVIEW_5S':
        fail('STUDIO_OVERNIGHT_FULL_VIDEO_REQUIRES_REVIEW')
    start=value.get('startFrame')
    if 'startFrame' in value and (type(start) is not int or start<0):
        fail('STUDIO_OVERNIGHT_PREVIEW_RANGE_INVALID','overnight.startFrame')
    result={'schema':SCHEMA,'profile':PROFILE,'operation':'PREVIEW_5S',
        'visualExtensions':normalize_visual(deepcopy(value.get('visualExtensions',VISUAL_DEFAULT)))}
    if start is not None: result['startFrame']=start
    return result


def normalize_submission(value, *, image_digest, backend, parent_normalize):
    parent=load('_overnight_preserved_contract',PARENT/'contract_v2.py')
    old=parent.preserved_contract()
    structured=old._v2_prompt(value)
    if structured is None or 'overnight' not in structured:
        fail('STUDIO_OVERNIGHT_PROFILE_REQUIRED')
    if 'completion' not in structured:
        fail('STUDIO_OVERNIGHT_COMPLETION_REQUIRED')
    overnight=normalize_overnight(structured['overnight'])
    lowered=deepcopy(structured);lowered.pop('overnight')
    outer=deepcopy(value);outer['prompt']=json.dumps(lowered,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    result=parent.normalize_submission(outer,image_digest=image_digest,backend=backend,parent_normalize=parent_normalize)
    result=deepcopy(result);result['promptText']=value['prompt'];result['overnightV3']=overnight
    if result['videoPlan']['fps']!=30 or result['videoPlan']['totalFrames']<150:
        fail('STUDIO_OVERNIGHT_PREVIEW_SOURCE_INVALID')
    return result
