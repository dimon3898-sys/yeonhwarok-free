"""Bounded CPU investigation of existing descriptor/env functions, never a GPU test.

Uses the unchanged helper with fake driver symbols and a private fixture root.
Executes only the two exact environment functions extracted from production AST.
Does not import or run Controller, Worker, supervisor, browser or renderer.
"""
from pathlib import Path
import ast
import hashlib
import importlib.util
import json
import os
import stat
import sys
import tempfile
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
ENGINE = ROOT / 'world-simulation-shorts-engine'
BACKEND = ENGINE / 'recovery/codex-to-gcube-handoff-v1/controller/nvidia_backend.py'
HELPER = ENGINE / 'deployment/gcube/graphics_runtime.py'
SELECTORS = ('__EGL_VENDOR_LIBRARY_FILENAMES', 'VK_DRIVER_FILES', 'VK_ICD_FILENAMES')


def main():
    backend_source = BACKEND.read_text()
    nodes = [n for n in ast.parse(backend_source).body if isinstance(n, ast.FunctionDef)
             and n.name in {'_runtime_environment', '_capture_diagnostic_environment'}]
    assert len(nodes) == 2
    environment_functions = {'os': os}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(BACKEND), 'exec'), environment_functions)
    runtime_env = environment_functions['_runtime_environment']
    capture_env = environment_functions['_capture_diagnostic_environment']
    spec = importlib.util.spec_from_file_location('_egl_path_audit_helper', HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    observations = []

    def observe(name, condition, **facts):
        if not condition:
            raise AssertionError(name)
        observations.append({'name': name, 'observationVerified': True, **facts})

    with tempfile.TemporaryDirectory(prefix='world-engine-egl-audit-') as directory:
        private = Path(directory) / 'engine-runtime'
        private.mkdir(mode=0o700)
        helper.RUNTIME_DIRECTORY = private  # Test module only; production files unchanged.
        driver = SimpleNamespace(__egl_Main=object(), vk_icdGetInstanceProcAddr=object())
        fake_loader = lambda name: driver
        initial = {'WORLD_ENGINE_RENDER_MODE': 'gpu-required', 'GPU_BACKEND': 'vulkan'}
        updates, facts = helper.prepare_graphics_runtime(
            initial, loader=fake_loader, runtime_directory=private,
            descriptor_checker=lambda *_: False, vulkan_version_reader=lambda _: '1.0.0')
        observe('helper_generation_in_fixture_only', set(updates) == set(SELECTORS)
                and set(facts['descriptors_created']) == {'egl', 'vulkan'},
                evidenceClass='CPU_FAKE_DRIVER_NOT_REAL_GPU_RECORD', generatedKinds=facts['descriptors_created'])
        readable = all(json.loads(Path(v).read_text())['ICD']['library_path'].endswith('nvidia.so.0')
                       for v in updates.values())
        observe('fixture_descriptors_readable_as_current_uid1000', os.getuid() == 1000 and readable
                and private.stat().st_uid == 1000 and stat.S_IMODE(private.stat().st_mode) == 0o700
                and all(stat.S_IMODE(Path(v).parent.stat().st_mode) == 0o755
                        and stat.S_IMODE(Path(v).stat().st_mode) == 0o644 for v in updates.values()),
                uid=os.getuid(), parentMode='0700', directoryMode='0755', fileMode='0644',
                realContainerFilePermissions='NOT_OBSERVED')
        observe('helper_accepts_its_valid_descriptor_paths',
                helper._existing_descriptor('egl', updates, fake_loader)
                and helper._existing_descriptor('vulkan', updates, fake_loader))
        bad = Path(directory) / 'outside.json'
        bad.write_text(json.dumps({'file_format_version': '1.0.0', 'ICD': {'library_path': 'libEGL_nvidia.so.0'}}))
        calls = []
        def unexpected_loader(name):
            calls.append(name)
            return driver
        rejected = not helper._existing_descriptor('egl', {'__EGL_VENDOR_LIBRARY_FILENAMES': str(bad)}, unexpected_loader)
        observe('helper_rejects_outside_descriptor_before_loading', rejected and not calls,
                scope='Existing helper root-containment gate with private fixture root')
        original = {**initial, **updates, 'WORLD_ENGINE_OWNER_CODE': 'AUDIT_SENTINEL_NOT_A_CREDENTIAL',
                    'GITHUB_TOKEN': 'AUDIT_SENTINEL_NOT_A_CREDENTIAL', 'DEBUG': '*'}
        before = dict(original)
        stages = []
        env = original
        for name in ['Controller_to_Worker', 'Worker_to_supervisor', 'supervisor_runtime_environment']:
            env = runtime_env(env)
            stages.append({'boundary': name, 'selectorsPresent': [k for k in SELECTORS if k in env]})
        env = capture_env(env)
        stages.append({'boundary': 'supervisor_to_capture', 'selectorsPresent': [k for k in SELECTORS if k in env]})
        observe('valid_generated_EGL_and_VK_DRIVER_selectors_dropped',
                all(s['selectorsPresent'] == ['VK_ICD_FILENAMES'] for s in stages),
                stages=stages, result='PROPAGATION_CONTRACT_GAP_CONFIRMED_IN_CPU_FIXTURE',
                wholeWorkerExecution=False)
        observe('existing_VK_ICD_value_survives', env['VK_ICD_FILENAMES'] == updates['VK_ICD_FILENAMES'])
        observe('secrets_and_caller_debug_remain_filtered',
                'WORLD_ENGINE_OWNER_CODE' not in env and 'GITHUB_TOKEN' not in env
                and env.get('DEBUG') == 'pw:browser' and env.get('DEBUG_COLORS') == '0')
        observe('source_environment_not_mutated', original == before)
        untrusted = runtime_env({'VK_ICD_FILENAMES': str(bad)})
        observe('existing_VK_ICD_allowlist_is_not_path_validation',
                untrusted.get('VK_ICD_FILENAMES') == str(bad),
                result='OUTSIDE_PATH_RETAINED_BY_EXISTING_FILTER',
                pathSafetyGate='NOT_PRESENT_IN_RUNTIME_ENVIRONMENT',
                implication='Do not extend selector allowlist without retaining helper containment/content checks')
        parent = dict(initial)
        legacy_local = dict(parent)
        legacy_local.update(updates)
        observe('separate_legacy_environment_updates_do_not_reach_studio_parent',
                all(k not in parent for k in SELECTORS) and all(k in legacy_local for k in SELECTORS),
                evidenceClass='PYTHON_ENVIRONMENT_MODEL_WITH_SOURCE_VERIFIED_PROCESS_BOUNDARIES',
                realLegacyPreparationDuringFailedRun='UNCONFIRMED')

    output = {'schema': 'WORLD_ENGINE_EGL_ENV_INVESTIGATION_PROBE_V1',
              'status': 'AUDIT_COMPLETE_PROPAGATION_GAPS_FOUND_ROOT_CAUSE_BLOCKED',
              'sourceFiles': [{'path': str(f.relative_to(ROOT)), 'sha256': hashlib.sha256(f.read_bytes()).hexdigest()}
                              for f in (BACKEND, HELPER)],
              'executionScope': 'New narrow CPU investigation; exact source functions, fake driver, temporary files. Not a production Worker or GPU result.',
              'observations': observations, 'actualGPUGenerationProved': False,
              'oldPassSuitesRun': 0, 'productionCodeChanges': 0, 'GPUStarts': 0,
              'browserLaunches': 0, 'rendererExecutions': 0, 'GPU_RENDER_PASS': False}
    (HERE / 'ENV_PROPAGATION_PROBE.json').write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'status': output['status'], 'observations': len(observations),
                      'GPUStarts': 0, 'realRunCausationProved': False}))


if __name__ == '__main__':
    main()
