"""Distinguish visible NVIDIA hardware from an actually drawing WebGL renderer."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess

from deployment.gcube.chromium_wrapper import (BrowserProfileError, browser_arguments,
                                              browser_executable, browser_profile)
from deployment.gcube.gpu_runtime_facts import graphics_runtime_inventory

HERE = Path(__file__).resolve().parent
SOFTWARE = re.compile(r"swiftshader|llvmpipe|softpipe|software|microsoft basic|lavapipe", re.I)
REASON_CODES = frozenset({
    'GPU_HARDWARE_UNAVAILABLE', 'GPU_WEBGL_UNVERIFIED', 'GPU_BROWSER_PROBE_FAILED',
    'GPU_WRAPPER_NOT_EXECUTABLE', 'GPU_BROWSER_UNAVAILABLE', 'GPU_PROFILE_INVALID',
    'CPU_FALLBACK_UNVERIFIED', 'NOT_RUN', 'DEVICE_NODES_VISIBLE', 'NVIDIA_QUERY_VISIBLE',
    'GPU_GRAPHICS_RUNTIME_PATH_UNSAFE', 'GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE',
    'GPU_GRAPHICS_DRIVER_API_UNAVAILABLE',
    'DEVICE_NODES_ABSENT', 'NVIDIA_QUERY_FAILED', 'NVIDIA_QUERY_TIMEOUT',
    'CHROMIUM_STARTED', 'CHROMIUM_START_FAILED', 'CHROMIUM_TIMEOUT',
    'CHROMIUM_EVALUATION_FAILED', 'PROBE_OUTPUT_INVALID', 'DRIVER_GRAPHICS_MISSING',
    'WEBGL2_CONTEXT_CREATED', 'WEBGL2_CONTEXT_UNAVAILABLE', 'DEBUG_RENDERER_UNAVAILABLE',
    'SOFTWARE_RENDERER_REJECTED', 'NVIDIA_RENDERER_MISSING', 'NVIDIA_DEVICE_MISMATCH',
    'NVIDIA_DEVICE_MATCHED', 'SOFTWARE_RENDERER_CONFIRMED', 'WEBGL_DRAW_VERIFIED',
    'WEBGL_DRAW_FAILED', 'GPU_PROBE_SHADER_FAILED', 'GPU_PROBE_PROGRAM_FAILED',
    'VERIFIED',
})
_STAGE_NAMES = {'A': 'NVIDIA device visible', 'B': 'nvidia-smi query',
                'C': 'Chromium startup', 'D': 'WebGL2 context',
                'E': 'NVIDIA renderer identity', 'F': 'Actual pixel draw'}


def _safe_identity(value, *, model=False, version=False):
    if not isinstance(value, str) or not value or len(value) > (160 if model else 512):
        return None
    if (re.search(r'GPU-[a-f0-9-]+', value, re.I) or '/' in value.replace('/PCIe', '').replace('/SSE2', '')
            or '\\' in value or any(ord(char) < 32 or ord(char) > 126 for char in value)):
        return None
    if version:
        return value if re.fullmatch(r'\d+(?:\.\d+){1,4}', value) else None
    # Only real browser graphics identity fields, never arbitrary error text.
    if not re.search(r'\b(?:ANGLE|NVIDIA|GeForce|Tesla|RTX|Quadro|WebKit|Google|Mesa|llvmpipe|'
                     r'SwiftShader|lavapipe|softpipe|Software|Intel|AMD|ATI|Adreno|Apple)\b', value, re.I):
        return None
    return value


def _safe_int(value, minimum=0, maximum=65536):
    return value if isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum else None


def _enum(value, allowed, default=None):
    return value if isinstance(value, str) and value in allowed else default


def _safe_webgl(value):
    source = value if isinstance(value, dict) else {}
    result = {key: source.get(key) is True for key in
              ('context_available', 'webgl2', 'draw_passed', 'debug_renderer_available')}
    result['webgl2'] = result['webgl2'] or source.get('context_version') == 2
    for key in ('renderer', 'vendor', 'gl_renderer', 'gl_vendor', 'unmasked_renderer', 'unmasked_vendor'):
        result[key] = _safe_identity(source.get(key))
    result['unmasked_renderer'] = result['unmasked_renderer'] or result['renderer']
    result['unmasked_vendor'] = result['unmasked_vendor'] or result['vendor']
    for key in ('context_version', 'webgl_error', 'max_texture_size', 'max_renderbuffer_size'):
        result[key] = _safe_int(source.get(key))
    pixel = source.get('pixel')
    result['pixel'] = (list(pixel) if isinstance(pixel, list) and len(pixel) == 4 and
                       all(_safe_int(item, maximum=255) is not None for item in pixel) else None)
    identity = ' '.join(value for value in (result['renderer'], result['vendor'],
                                           result['unmasked_renderer'], result['unmasked_vendor']) if value)
    result['software_renderer'] = bool(SOFTWARE.search(identity))
    reason = source.get('reason_code')
    result['reason_code'] = _enum(reason, REASON_CODES)
    return result


def sanitize_gpu_diagnostics(value, *, include_attempts=True):
    """Pure allowlist for the owner diagnostic page and blocked startup panel."""
    if not isinstance(value, dict) or not value:
        return {}
    source = value
    result = {'schema_version': 1,
              'render_mode': _enum(source.get('render_mode'), {'gpu-required', 'cpu'}),
              'gpu_profile': _enum(source.get('gpu_profile'), {'egl', 'vulkan'}),
              'failed_stage': _enum(source.get('failed_stage'), _STAGE_NAMES),
              'reason_code': _enum(source.get('reason_code'), REASON_CODES, 'GPU_WEBGL_UNVERIFIED'),
              'browser_version': _safe_identity(source.get('browser_version'), version=True),
              'webgl': _safe_webgl(source.get('webgl')), 'stages': [], 'nvidia_devices': []}
    stage_source = source.get('stages') if isinstance(source.get('stages'), list) else []
    by_id = {_enum(item.get('id'), _STAGE_NAMES): item for item in stage_source[:6] if isinstance(item, dict)}
    for stage_id, name in _STAGE_NAMES.items():
        item = by_id.get(stage_id, {})
        result['stages'].append({'id': stage_id, 'name': name,
                                'status': _enum(item.get('status'), {'PASS', 'FAIL', 'NOT_RUN'}, 'NOT_RUN'),
                                'reason_code': _enum(item.get('reason_code'), REASON_CODES, 'NOT_RUN')})
    devices = source.get('nvidia_devices') if isinstance(source.get('nvidia_devices'), list) else []
    for item in devices[:16]:
        if not isinstance(item, dict):
            continue
        name = _safe_identity(item.get('name'), model=True)
        driver = _safe_identity(item.get('driver_version'), version=True)
        memory = item.get('memory_total_mib')
        if name:
            result['nvidia_devices'].append({'name': name, 'driver_version': driver,
                'memory_total_mib': memory if isinstance(memory, (int, float)) and not isinstance(memory, bool)
                and math.isfinite(memory) and 0 < memory < 2**30 else None})
    runtime = source.get('runtime') if isinstance(source.get('runtime'), dict) else {}
    environments = runtime.get('environment') if isinstance(runtime.get('environment'), dict) else {}
    result['runtime'] = {'environment': {}, 'devices': {}, 'libraries': {}, 'driver_delivery': {}}
    for name in ('NVIDIA_VISIBLE_DEVICES', 'CUDA_VISIBLE_DEVICES'):
        item = environments.get(name) if isinstance(environments.get(name), dict) else {}
        result['runtime']['environment'][name] = {'present': item.get('present') is True,
            'selection': _enum(item.get('selection'), {'unset', 'all', 'none', 'index-list', 'configured'}, 'unset')}
    for group, names in (('devices', ('nvidia', 'dri')), ('libraries', tuple(('egl', 'gles', 'opengl', 'vulkan', 'nvidia_egl', 'nvidia_vulkan'))),
                         ('driver_delivery', ('egl_vendor_manifest', 'vulkan_nvidia_icd'))):
        items = runtime.get(group) if isinstance(runtime.get(group), dict) else {}
        for name in names:
            result['runtime'][group][name] = (_safe_int(items.get(name), maximum=256) or 0) if group == 'devices' else items.get(name) is True
    cdp = source.get('system_info') if isinstance(source.get('system_info'), dict) else {}
    auxiliary = cdp.get('auxiliary') if isinstance(cdp.get('auxiliary'), dict) else {}
    result['system_info'] = {'auxiliary': {key: _safe_identity(auxiliary.get(key))
                            for key in ('glRenderer', 'glVendor')}, 'devices': [], 'feature_status': {}}
    cdp_devices = cdp.get('devices') if isinstance(cdp.get('devices'), list) else []
    for item in cdp_devices[:16]:
        if not isinstance(item, dict):
            continue
        result['system_info']['devices'].append({key: _safe_int(item.get(key)) if key.endswith('Id') else
            _safe_identity(item.get(key), version=key == 'driverVersion') for key in
            ('vendorId', 'deviceId', 'vendorString', 'deviceString', 'driverVendor', 'driverVersion')})
    features = cdp.get('feature_status') if isinstance(cdp.get('feature_status'), dict) else {}
    for key in ('webgl', 'webgl2', 'gpu_compositing', 'vulkan', 'rasterization'):
        entry = features.get(key)
        if isinstance(entry, str) and re.fullmatch(r'[a-z_]{1,64}', entry):
            result['system_info']['feature_status'][key] = entry
    if include_attempts:
        result['profile_attempts'] = []
        attempts = source.get('profile_attempts') if isinstance(source.get('profile_attempts'), list) else []
        for item in attempts[:2]:
            if not isinstance(item, dict) or _enum(item.get('backend'), {'egl', 'vulkan'}) is None:
                continue
            result['profile_attempts'].append({'backend': item['backend'],
                'status': _enum(item.get('status'), {'failed', 'verified'}, 'failed'),
                'error_code': _enum(item.get('error_code'), REASON_CODES),
                'diagnostics': sanitize_gpu_diagnostics(item.get('diagnostics'), include_attempts=False)})
    return result


class GPUError(RuntimeError):
    def __init__(self, code, *, diagnostics=None):
        self.code = _enum(code, REASON_CODES, 'GPU_WEBGL_UNVERIFIED')
        self.diagnostics = sanitize_gpu_diagnostics(diagnostics)
        super().__init__(self.code)


def parse_nvidia_smi(text):
    records = []
    if not isinstance(text, str) or len(text) > 65536:
        raise GPUError('GPU_HARDWARE_UNAVAILABLE')
    for row in csv.reader(io.StringIO(text)):
        if len(row) != 5:
            raise GPUError('GPU_HARDWARE_UNAVAILABLE')
        name, uuid, driver, memory, utilization = (value.strip() for value in row)
        if (not name or len(name) > 256 or not re.fullmatch(r'GPU-[a-fA-F0-9-]+', uuid) or
                not re.fullmatch(r'\d+(?:\.\d+){1,3}', driver)):
            raise GPUError('GPU_HARDWARE_UNAVAILABLE')
        try:
            memory_value = float(memory)
            utilization_value = None if utilization in {'[N/A]', 'N/A', 'Not Supported'} else float(utilization)
        except ValueError:
            raise GPUError('GPU_HARDWARE_UNAVAILABLE') from None
        if (not math.isfinite(memory_value) or memory_value <= 0 or
                (utilization_value is not None and (not math.isfinite(utilization_value) or
                                                    not 0 <= utilization_value <= 100))):
            raise GPUError('GPU_HARDWARE_UNAVAILABLE')
        records.append({'name':name,'uuid':uuid,'driver_version':driver,
                        'memory_total_mib':memory_value,'utilization_gpu_percent':utilization_value})
    if not records:
        raise GPUError('GPU_HARDWARE_UNAVAILABLE')
    return records


def _model_matches(renderer, hardware):
    """Correlate WebGL's physical adapter model with one visible NVIDIA GPU."""
    # Compare complete model tokens: A10 is not A100, RTX 3070 is not 3070 Ti.
    pattern = re.compile(r'\b(?:rtx\s*a|rtx|gtx|a|h|l|p|t|v|m)\s*\d+(?:\s*(?:ti|super|s|g))?(?![a-z0-9])', re.I)
    renderer_models = {re.sub(r'\s+', '', token.group(0).lower()) for token in pattern.finditer(renderer)}
    for item in hardware:
        if not isinstance(item, dict) or not isinstance(item.get('name'), str):
            continue
        name = item['name']
        hardware_models = {re.sub(r'\s+', '', token.group(0).lower()) for token in pattern.finditer(name)}
        if hardware_models and hardware_models & renderer_models:
            return True
        if not hardware_models:
            model = re.sub(r'\b(?:NVIDIA|GeForce|Tesla|Quadro)\b', '', name, flags=re.I).strip()
            if model and re.search(r'(?<![a-z0-9])' + re.escape(model) + r'(?![a-z0-9])', renderer, re.I):
                return True
    return False


def probe_failure(probe, hardware, *, mode='gpu-required'):
    """Return the exact failed stage/reason; identity never substitutes a draw."""
    if mode not in {'gpu-required', 'cpu'} or not isinstance(probe, dict):
        return 'C', 'PROBE_OUTPUT_INVALID'
    if (probe.get('browser_started') is False or not isinstance(probe.get('browser_version'), str)
            or not probe.get('browser_version')):
        reason = probe.get('error_code')
        return 'C', _enum(reason, REASON_CODES, 'CHROMIUM_START_FAILED')
    webgl = probe.get('webgl')
    if (not isinstance(webgl, dict) or webgl.get('context_available') is not True or
            webgl.get('context_version') != 2):
        return 'D', 'WEBGL2_CONTEXT_UNAVAILABLE'
    renderer = webgl.get('unmasked_renderer', webgl.get('renderer'))
    vendor = webgl.get('unmasked_vendor', webgl.get('vendor'))
    identity = ' '.join(value for value in (renderer, vendor) if isinstance(value, str))
    if mode == 'gpu-required':
        if webgl.get('debug_renderer_available') is not True:
            return 'E', 'DEBUG_RENDERER_UNAVAILABLE'
        if SOFTWARE.search(identity):
            return 'E', 'SOFTWARE_RENDERER_REJECTED'
        if not isinstance(renderer, str) or not re.search(r'\bnvidia\b', renderer, re.I):
            return 'E', 'NVIDIA_RENDERER_MISSING'
        if not hardware or not _model_matches(renderer, hardware):
            return 'E', 'NVIDIA_DEVICE_MISMATCH'
    elif not SOFTWARE.search(identity):
        return 'E', 'NVIDIA_RENDERER_MISSING'
    pixel = webgl.get('pixel')
    actual_red = (isinstance(pixel, list) and len(pixel) == 4 and
                  all(_safe_int(item, maximum=255) is not None for item in pixel) and
                  pixel[0] >= 250 and pixel[1] <= 5 and pixel[2] <= 5 and pixel[3] >= 250)
    if (webgl.get('draw_passed') is not True or webgl.get('webgl_error') != 0 or not actual_red):
        reason = webgl.get('reason_code')
        return 'F', _enum(reason, {'GPU_PROBE_SHADER_FAILED', 'GPU_PROBE_PROGRAM_FAILED'}, 'WEBGL_DRAW_FAILED')
    return None, 'VERIFIED'


def classify_probe(probe, hardware, *, mode='gpu-required'):
    """nvidia-smi, a renderer string and a mocked PASS flag are insufficient."""
    stage, _ = probe_failure(probe, hardware, mode=mode)
    if stage is not None:
        raise GPUError('GPU_WEBGL_UNVERIFIED' if mode != 'cpu' else 'CPU_FALLBACK_UNVERIFIED')
    return mode == 'gpu-required'


def profile_fingerprint(probe, hardware, *, mode, profile, source_hashes):
    stable_hardware = [{key:row[key] for key in ('name','uuid','driver_version','memory_total_mib')}
                       for row in hardware]
    info = {'schema_version':1,'mode':mode,'profile':profile,
            'browser_version':probe['browser_version'],'hardware':stable_hardware,
            'webgl_renderer':probe['webgl'].get('renderer'),'webgl_vendor':probe['webgl'].get('vendor'),
            'adapter_source_hashes':source_hashes,
            'browser_arguments':browser_arguments([],{'WORLD_ENGINE_RENDER_MODE':mode,
                                                       'WORLD_ENGINE_GPU_PROFILE':profile})}
    return hashlib.sha256(json.dumps(info,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def cuda_diagnostics(run, env, *, hardware_visible):
    """Optional facts only: driver CUDA compatibility is not a toolkit install."""
    toolkit = {'status':'not_detected','nvcc_present':False,'version':None,
               'used_by_renderer':False,'evidence':'nvcc_unavailable'}
    driver_maximum = None
    try:
        response = run(['nvcc','--version'],capture_output=True,text=True,timeout=5,env=env,check=False)
        if response.returncode == 0 and isinstance(response.stdout,str) and len(response.stdout) <= 16384:
            match = re.search(r'\bV(\d+(?:\.\d+){1,3})\b',response.stdout)
            if match is None:
                match = re.search(r'\brelease\s+(\d+(?:\.\d+){1,3})\b',response.stdout)
            toolkit = {'status':'detected' if match else 'version_unknown','nvcc_present':True,
                       'version':match.group(1) if match else None,
                       'used_by_renderer':False,'evidence':'nvcc_version_command'}
    except (OSError,subprocess.SubprocessError):
        pass
    if hardware_visible:
        try:
            response = run(['nvidia-smi'],capture_output=True,text=True,timeout=5,env=env,check=False)
            if response.returncode == 0 and isinstance(response.stdout,str) and len(response.stdout) <= 65536:
                match = re.search(r'CUDA Version:\s*(\d+(?:\.\d+){1,3})\b',response.stdout)
                if match:
                    driver_maximum = match.group(1)
        except (OSError,subprocess.SubprocessError):
            pass
    return {'toolkit':toolkit,'driver_supported_cuda_max_version':driver_maximum,
            'driver_maximum_is_toolkit_version':False,'cuda_required_by_renderer':False}


def probe_gpu_runtime(*, environ=None, runner=None):
    """Bounded startup probe; no videos, remote network, CUDA toolkit or codec changes."""
    env = dict(os.environ if environ is None else environ)
    run = subprocess.run if runner is None else runner
    runtime = graphics_runtime_inventory(env)
    hardware, hardware_status = [], 'unavailable'
    diagnostic = {'schema_version': 1, 'render_mode': 'gpu-required', 'gpu_profile': 'egl',
                  'runtime': runtime, 'nvidia_devices': [], 'webgl': {}, 'browser_version': None,
                  'system_info': {}, 'failed_stage': None, 'reason_code': 'NOT_RUN',
                  'stages': [{'id': key, 'name': name, 'status': 'NOT_RUN', 'reason_code': 'NOT_RUN'}
                             for key, name in _STAGE_NAMES.items()]}

    def stage(stage_id, status, reason):
        entry = diagnostic['stages'][ord(stage_id) - ord('A')]
        entry.update(status=status, reason_code=reason)

    def fail(code, failed_stage, reason):
        stage(failed_stage, 'FAIL', reason)
        diagnostic.update(failed_stage=failed_stage, reason_code=reason)
        raise GPUError(code, diagnostics=diagnostic) from None

    device_visible = runtime['devices']['nvidia'] > 0
    stage('A', 'PASS' if device_visible else 'FAIL',
          'DEVICE_NODES_VISIBLE' if device_visible else 'DEVICE_NODES_ABSENT')
    try:
        mode, profile = browser_profile(env)
        diagnostic.update(render_mode=mode, gpu_profile=profile)
        real_browser = browser_executable(env)
    except BrowserProfileError as error:
        fail(str(error), 'C', str(error))
    wrapper = HERE / 'chromium_wrapper.py'
    if not os.access(wrapper, os.X_OK):
        fail('GPU_WRAPPER_NOT_EXECUTABLE', 'C', 'GPU_WRAPPER_NOT_EXECUTABLE')
    try:
        response = run(['nvidia-smi','--query-gpu=name,uuid,driver_version,memory.total,utilization.gpu',
                        '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10,env=env,check=False)
        if response.returncode != 0:
            raise GPUError('GPU_HARDWARE_UNAVAILABLE')
        hardware = parse_nvidia_smi(response.stdout)
        hardware_status = 'visible'
        diagnostic['nvidia_devices'] = hardware
        if not device_visible:
            stage('A', 'PASS', 'NVIDIA_QUERY_VISIBLE')
        stage('B', 'PASS', 'NVIDIA_QUERY_VISIBLE')
    except (GPUError, OSError, subprocess.SubprocessError) as error:
        reason = 'NVIDIA_QUERY_TIMEOUT' if isinstance(error, subprocess.TimeoutExpired) else 'NVIDIA_QUERY_FAILED'
        stage('B', 'FAIL', reason)
        if mode == 'gpu-required':
            fail('GPU_HARDWARE_UNAVAILABLE', 'B', reason)
    env['WORLD_ENGINE_CHROMIUM_REAL'] = real_browser
    try:
        response = run(['node',str(HERE/'gpu_probe.mjs'),str(wrapper)],capture_output=True,text=True,
                       timeout=60,env=env,check=False)
        if not isinstance(response.stdout, str) or len(response.stdout) > 65536:
            fail('GPU_BROWSER_PROBE_FAILED', 'C', 'PROBE_OUTPUT_INVALID')
        probe = json.loads(response.stdout)
        if not isinstance(probe, dict):
            fail('GPU_BROWSER_PROBE_FAILED', 'C', 'PROBE_OUTPUT_INVALID')
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as error:
        reason = 'CHROMIUM_TIMEOUT' if isinstance(error, subprocess.TimeoutExpired) else 'PROBE_OUTPUT_INVALID'
        fail('GPU_BROWSER_PROBE_FAILED', 'C', reason)
    diagnostic.update(browser_version=probe.get('browser_version'), webgl=probe.get('webgl'),
                      system_info=probe.get('system_info'))
    failed_stage, reason = probe_failure(probe, hardware, mode=mode)
    for stage_id, success_reason in (('C', 'CHROMIUM_STARTED'), ('D', 'WEBGL2_CONTEXT_CREATED'),
            ('E', 'NVIDIA_DEVICE_MATCHED' if mode == 'gpu-required' else 'SOFTWARE_RENDERER_CONFIRMED'),
            ('F', 'WEBGL_DRAW_VERIFIED')):
        if failed_stage == stage_id:
            if (stage_id == 'D' and mode == 'gpu-required' and
                    not runtime['libraries']['nvidia_egl'] and not runtime['libraries']['nvidia_vulkan']):
                reason = 'DRIVER_GRAPHICS_MISSING'
            failure = 'GPU_BROWSER_PROBE_FAILED' if stage_id == 'C' else (
                'GPU_WEBGL_UNVERIFIED' if mode == 'gpu-required' else 'CPU_FALLBACK_UNVERIFIED')
            fail(failure, stage_id, reason)
        stage(stage_id, 'PASS', success_reason)
    if response.returncode != 0:
        fail('GPU_BROWSER_PROBE_FAILED', 'C', 'CHROMIUM_EVALUATION_FAILED')
    verified = classify_probe(probe, hardware, mode=mode)
    diagnostic.update(failed_stage=None, reason_code='VERIFIED')
    cuda = cuda_diagnostics(run,env,hardware_visible=bool(hardware))
    source_hashes = {name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                     for name in ('gpu.py','chromium_wrapper.py','gpu_probe.mjs','gpu_runtime_facts.py')}
    fingerprint = profile_fingerprint(probe,hardware,mode=mode,profile=profile,source_hashes=source_hashes)
    return {'schema_version':1,'observed_at':datetime.now(timezone.utc).isoformat(),
            'render_mode':mode,'gpu_profile':profile,'gpu_rendering_verified':verified,
            'hardware_status':hardware_status,'nvidia_devices':hardware,
            'browser_version':probe['browser_version'],'webgl':probe['webgl'],
            'system_info_available':probe.get('system_info_available',False),'system_info':probe.get('system_info'),
            'diagnostics': sanitize_gpu_diagnostics(diagnostic),
            'cuda':cuda,
            'adapter_source_hashes':source_hashes,'profile_fingerprint':fingerprint,
            'cache_namespace':('gpu-' if verified else 'cpu-')+fingerprint,
            'video_encoder':'preserved_libx264','speedup_measured':False}
