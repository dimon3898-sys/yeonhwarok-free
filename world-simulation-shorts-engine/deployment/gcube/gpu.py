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

HERE = Path(__file__).resolve().parent
SOFTWARE = re.compile(r"swiftshader|llvmpipe|softpipe|software|microsoft basic|lavapipe", re.I)


class GPUError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


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


def classify_probe(probe, hardware, *, mode='gpu-required'):
    """nvidia-smi alone, missing renderer identity or software fallback cannot pass."""
    if mode not in {'gpu-required','cpu'} or not isinstance(probe, dict):
        raise GPUError('GPU_WEBGL_UNVERIFIED')
    webgl = probe.get('webgl')
    if (not isinstance(webgl, dict) or webgl.get('context_available') is not True or
            webgl.get('context_version') != 2 or webgl.get('draw_passed') is not True or
            webgl.get('webgl_error') != 0 or not isinstance(probe.get('browser_version'), str) or
            not probe['browser_version']):
        raise GPUError('GPU_WEBGL_UNVERIFIED')
    renderer, vendor = webgl.get('renderer'), webgl.get('vendor')
    identity = ' '.join(value for value in (renderer,vendor) if isinstance(value,str))
    hardware_webgl = bool(hardware and isinstance(renderer,str) and renderer and
                          webgl.get('debug_renderer_available') is True and
                          re.search(r'\bnvidia\b',identity,re.I) and not SOFTWARE.search(identity))
    if mode == 'gpu-required' and not hardware_webgl:
        raise GPUError('GPU_WEBGL_UNVERIFIED')
    if mode == 'cpu' and not SOFTWARE.search(identity):
        raise GPUError('CPU_FALLBACK_UNVERIFIED')
    return hardware_webgl if mode == 'gpu-required' else False


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
    try:
        mode, profile = browser_profile(env)
        real_browser = browser_executable(env)
    except BrowserProfileError as error:
        raise GPUError(str(error)) from None
    wrapper = HERE / 'chromium_wrapper.py'
    if not os.access(wrapper, os.X_OK):
        raise GPUError('GPU_WRAPPER_NOT_EXECUTABLE')
    hardware, hardware_status = [], 'unavailable'
    try:
        response = run(['nvidia-smi','--query-gpu=name,uuid,driver_version,memory.total,utilization.gpu',
                        '--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=10,env=env,check=False)
        if response.returncode != 0:
            raise GPUError('GPU_HARDWARE_UNAVAILABLE')
        hardware = parse_nvidia_smi(response.stdout)
        hardware_status = 'visible'
    except (GPUError,OSError,subprocess.SubprocessError):
        if mode == 'gpu-required':
            raise GPUError('GPU_HARDWARE_UNAVAILABLE') from None
    env['WORLD_ENGINE_CHROMIUM_REAL'] = real_browser
    try:
        response = run(['node',str(HERE/'gpu_probe.mjs'),str(wrapper)],capture_output=True,text=True,
                       timeout=60,env=env,check=False)
        if response.returncode != 0 or len(response.stdout) > 65536:
            raise GPUError('GPU_BROWSER_PROBE_FAILED')
        probe = json.loads(response.stdout)
    except (OSError,subprocess.SubprocessError,ValueError,TypeError):
        raise GPUError('GPU_BROWSER_PROBE_FAILED') from None
    verified = classify_probe(probe,hardware,mode=mode)
    cuda = cuda_diagnostics(run,env,hardware_visible=bool(hardware))
    source_hashes = {name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                     for name in ('gpu.py','chromium_wrapper.py','gpu_probe.mjs')}
    fingerprint = profile_fingerprint(probe,hardware,mode=mode,profile=profile,source_hashes=source_hashes)
    return {'schema_version':1,'observed_at':datetime.now(timezone.utc).isoformat(),
            'render_mode':mode,'gpu_profile':profile,'gpu_rendering_verified':verified,
            'hardware_status':hardware_status,'nvidia_devices':hardware,
            'browser_version':probe['browser_version'],'webgl':probe['webgl'],
            'system_info_available':probe.get('system_info_available',False),'system_info':probe.get('system_info'),
            'cuda':cuda,
            'adapter_source_hashes':source_hashes,'profile_fingerprint':fingerprint,
            'cache_namespace':('gpu-' if verified else 'cpu-')+fingerprint,
            'video_encoder':'preserved_libx264','speedup_measured':False}
