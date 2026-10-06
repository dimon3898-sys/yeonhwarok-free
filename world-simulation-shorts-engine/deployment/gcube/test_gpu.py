"""Hardware admission contracts; synthetic fixtures are not GPU benchmarks."""
from copy import deepcopy
import json
import subprocess
import unittest
from unittest.mock import patch

from deployment.gcube import gpu
from deployment.gcube.chromium_wrapper import (BrowserProfileError, browser_arguments,
                                              browser_executable, browser_profile)


def device():
    return {'name':'NVIDIA GeForce RTX 5070','uuid':'GPU-1234-abcd','driver_version':'570.124.04',
            'memory_total_mib':12288.0,'utilization_gpu_percent':0.0}


def probe(renderer='ANGLE (NVIDIA, NVIDIA GeForce RTX 5070, OpenGL 4.6)'):
    return {'schema_version':1,'browser_version':'140.0.0.0',
            'webgl':{'context_available':True,'context_version':2,'draw_passed':True,
                     'webgl_error':0,'renderer':renderer,'vendor':'Google Inc. (NVIDIA)',
                     'debug_renderer_available':True,'max_texture_size':16384,
                     'max_renderbuffer_size':16384},
            'system_info_available':False,'system_info':None}


class BrowserWrapper(unittest.TestCase):
    def test_gpu_removes_forced_software_without_touching_other_arguments(self):
        preserved=['--no-sandbox','--disable-dev-shm-usage','--window-size=2160,3840',
                   '--remote-debugging-pipe','--user-data-dir=/tmp/browser profile']
        args=preserved+['--enable-unsafe-swiftshader','--use-angle=swiftshader','--disable-gpu']
        actual=browser_arguments(args,{})
        self.assertEqual(actual[:len(preserved)],preserved)
        self.assertNotIn('--enable-unsafe-swiftshader',actual)
        self.assertNotIn('--use-angle=swiftshader',actual)
        self.assertIn('--use-angle=gl-egl',actual)
        self.assertIn('--disable-software-rasterizer',actual)

    def test_split_selectors_and_explicit_vulkan_profile(self):
        args=browser_arguments(['--use-angle','swiftshader','--use-gl=egl','--foo=bar'],
                               {'WORLD_ENGINE_GPU_PROFILE':'vulkan'})
        self.assertEqual(args[0],'--foo=bar')
        self.assertIn('--use-angle=vulkan',args)
        self.assertEqual(sum(a.startswith('--use-angle=') for a in args),1)
        with self.assertRaises(BrowserProfileError):
            browser_arguments(['--use-angle','--headless'],{})

    def test_cpu_fallback_requires_explicit_mode_and_retains_swiftshader(self):
        self.assertEqual(browser_profile({})[0],'gpu-required')
        args=browser_arguments(['--use-angle=vulkan','--disable-software-rasterizer'],
                               {'WORLD_ENGINE_RENDER_MODE':'cpu'})
        self.assertIn('--use-angle=swiftshader',args)
        self.assertIn('--enable-unsafe-swiftshader',args)
        self.assertNotIn('--disable-software-rasterizer',args)
        self.assertNotIn('--use-angle=vulkan',args)

    def test_unknown_mode_profile_and_recursive_executable_fail(self):
        for env in ({'WORLD_ENGINE_RENDER_MODE':'auto'},{'WORLD_ENGINE_GPU_PROFILE':'cuda'}):
            with self.subTest(env=env),self.assertRaises(BrowserProfileError):
                browser_arguments([],env)
        with self.assertRaises(BrowserProfileError):
            browser_executable({'WORLD_ENGINE_CHROMIUM_REAL':str(gpu.HERE/'chromium_wrapper.py')})


class GPUAdmission(unittest.TestCase):
    def test_nvidia_query_records_actual_vram_driver_and_utilization(self):
        rows=gpu.parse_nvidia_smi('NVIDIA GeForce RTX 5070, GPU-1234-abcd, 570.124.04, 12288, 17\n')
        self.assertEqual(rows[0]['memory_total_mib'],12288)
        self.assertEqual(rows[0]['utilization_gpu_percent'],17)
        self.assertEqual(rows[0]['driver_version'],'570.124.04')
        for value in ('','GPU, baduuid, 570.1, 12288, 0','GPU, GPU-abcd, 570.1, NaN, 0',
                      'GPU, GPU-abcd, 570.1, 12288, 101'):
            with self.subTest(value=value),self.assertRaises(gpu.GPUError):
                gpu.parse_nvidia_smi(value)

    def test_nvidia_smi_is_insufficient_if_actual_browser_uses_software(self):
        for name in ('ANGLE (Google, SwiftShader Device)','llvmpipe (LLVM 17)','lavapipe'):
            with self.subTest(renderer=name),self.assertRaisesRegex(gpu.GPUError,'GPU_WEBGL_UNVERIFIED'):
                gpu.classify_probe(probe(name),[device()])
        self.assertTrue(gpu.classify_probe(probe(),[device()]))

    def test_missing_identity_failed_draw_and_unavailable_hardware_fail(self):
        for field,value in (('renderer',None),('debug_renderer_available',False),
                            ('draw_passed',False),('webgl_error',1282),('context_version',1)):
            value_probe=probe()
            value_probe['webgl'][field]=value
            with self.subTest(field=field),self.assertRaises(gpu.GPUError):
                gpu.classify_probe(value_probe,[device()])
        with self.assertRaises(gpu.GPUError):
            gpu.classify_probe(probe(),[])

    def test_explicit_cpu_never_claims_hardware_rendering(self):
        self.assertFalse(gpu.classify_probe(probe('ANGLE (Google, SwiftShader Device)'),[device()],mode='cpu'))
        with self.assertRaisesRegex(gpu.GPUError,'CPU_FALLBACK_UNVERIFIED'):
            gpu.classify_probe(probe(),[device()],mode='cpu')

    def test_fingerprint_separates_driver_browser_and_wrapper_but_not_utilization(self):
        args={'mode':'gpu-required','profile':'egl','source_hashes':{'wrapper':'a'}}
        baseline=gpu.profile_fingerprint(probe(),[device()],**args)
        changed=device()
        changed['utilization_gpu_percent']=99
        self.assertEqual(baseline,gpu.profile_fingerprint(probe(),[changed],**args))
        changed['driver_version']='575.1'
        self.assertNotEqual(baseline,gpu.profile_fingerprint(probe(),[changed],**args))
        changed_probe=probe()
        changed_probe['browser_version']='141.0.0.0'
        self.assertNotEqual(baseline,gpu.profile_fingerprint(changed_probe,[device()],**args))
        args['source_hashes']={'wrapper':'b'}
        self.assertNotEqual(baseline,gpu.profile_fingerprint(probe(),[device()],**args))

    def test_runtime_probe_is_bounded_and_does_not_start_video_encoding(self):
        calls=[]
        def run(command,**kwargs):
            calls.append((command,kwargs))
            if command[0]=='nvidia-smi' and len(command)>1:
                return subprocess.CompletedProcess(command,0,'NVIDIA GeForce RTX 5070, GPU-1234-abcd, 570.124.04, 12288, 0\n','')
            if command[0]=='nvcc':
                raise FileNotFoundError()
            if command==['nvidia-smi']:
                return subprocess.CompletedProcess(command,0,'NVIDIA-SMI 570.124.04   CUDA Version: 12.8','')
            return subprocess.CompletedProcess(command,0,json.dumps(probe()),'')
        with patch.object(gpu,'browser_executable',return_value='/usr/bin/chromium'):
            result=gpu.probe_gpu_runtime(environ={},runner=run)
        self.assertTrue(result['gpu_rendering_verified'])
        self.assertFalse(result['speedup_measured'])
        self.assertTrue(result['cache_namespace'].startswith('gpu-'))
        self.assertEqual([item[1]['timeout'] for item in calls],[10,60,5,5])
        self.assertEqual([item[0][0] for item in calls],['nvidia-smi','node','nvcc','nvidia-smi'])
        self.assertEqual(result['cuda']['driver_supported_cuda_max_version'],'12.8')
        self.assertFalse(result['cuda']['toolkit']['nvcc_present'])
        self.assertEqual(result['cuda']['toolkit']['status'],'not_detected')

    def test_optional_cuda_toolkit_and_driver_versions_remain_distinct(self):
        def run(command,**kwargs):
            text=('Cuda compilation tools, release 12.8, V12.8.93' if command[0]=='nvcc'
                  else '| NVIDIA-SMI 590.12 | Driver Version: 590.12 | CUDA Version: 13.1 |')
            return subprocess.CompletedProcess(command,0,text,'')
        info=gpu.cuda_diagnostics(run,{},hardware_visible=True)
        self.assertEqual(info['toolkit']['version'],'12.8.93')
        self.assertEqual(info['driver_supported_cuda_max_version'],'13.1')
        self.assertFalse(info['driver_maximum_is_toolkit_version'])
        self.assertFalse(info['toolkit']['used_by_renderer'])
        self.assertFalse(info['cuda_required_by_renderer'])

    def test_optional_cuda_failures_do_not_add_gpu_requirements(self):
        for failure in (FileNotFoundError(),subprocess.TimeoutExpired(['nvcc'],5)):
            def run(command,**kwargs):
                raise failure
            info=gpu.cuda_diagnostics(run,{},hardware_visible=True)
            self.assertEqual(info['toolkit']['status'],'not_detected')
            self.assertIsNone(info['driver_supported_cuda_max_version'])

    def test_required_gpu_fails_before_browser_if_no_device(self):
        calls=[]
        def run(command,**kwargs):
            calls.append(command)
            raise FileNotFoundError()
        with patch.object(gpu,'browser_executable',return_value='/usr/bin/chromium'):
            with self.assertRaisesRegex(gpu.GPUError,'GPU_HARDWARE_UNAVAILABLE'):
                gpu.probe_gpu_runtime(environ={},runner=run)
        self.assertEqual(len(calls),1)


if __name__=='__main__':
    unittest.main()
