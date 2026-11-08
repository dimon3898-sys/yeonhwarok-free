"""Bounded integrity checks for the new manifest/startup combination only."""
from pathlib import Path
import argparse
import ast
import json
from types import SimpleNamespace

from prepare_native_manifests import (BASE_RUNTIME, BASE_STARTUP, BOOTSTRAP, COLD,
    GENERATED, HANDOFF, OFFICIAL, RUNTIME, STARTUP, encoded, need, pin, sha, write)


def function_only(path, name, namespace):
    tree = ast.parse(path.read_bytes())
    fn = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])),
                 '<pinned environment function>', 'exec'), namespace)
    return namespace[name]


def qualify(args):
    context_raw = (args.context / 'CONTEXT.json').read_bytes()
    context = json.loads(context_raw)
    closure_raw = args.closure.read_bytes()
    closure = json.loads(closure_raw)
    base_raw = (args.v16_overlay / RUNTIME).read_bytes()
    need(sha(base_raw) == BASE_RUNTIME, 'PUBLISHED_V16_RUNTIME_PIN')
    base = json.loads(base_raw)
    need(sha((args.v16_overlay / STARTUP).read_bytes()) == BASE_STARTUP, 'PUBLISHED_V16_STARTUP_PIN')
    overlay = {}
    for row in context['overlay']:
        raw = (args.context / 'overlay' / row['path']).read_bytes()
        need(pin(row['path'], raw) == row, 'CONTEXT_FILE_PIN')
        overlay[row['path']] = raw
    actual_names = {p.relative_to(args.context).as_posix() for p in args.context.rglob('*') if p.is_file()}
    need(actual_names == {'Dockerfile', 'CONTEXT.json'} | {'overlay/' + name for name in overlay}, 'EXACT_CONTEXT_TREE')
    runtime = json.loads(overlay[RUNTIME])
    startup = json.loads(overlay[STARTUP])
    need(sha(overlay[RUNTIME]) == context['runtimeManifestSHA256'] == startup['runtimeManifestSHA256'], 'RUNTIME_HASH_CHAIN')
    need(sha(overlay[STARTUP]) == context['startupManifestSHA256'] == closure['startupManifestSHA256'], 'STARTUP_HASH_CHAIN')
    entry = context['entrypoint']
    need(entry[entry.index('--startup-manifest-sha256') + 1] == sha(overlay[STARTUP]), 'ENTRYPOINT_STARTUP_PIN')
    need(entry[entry.index('--source-manifest-sha256') + 1] == sha(overlay[RUNTIME]), 'ENTRYPOINT_RUNTIME_PIN')
    for name, row in startup['files'].items():
        body = overlay.get(COLD + name)
        if body is None:
            need(name == 'worker.py', 'UNRECOVERED_STARTUP_FILE')
            body = args.worker.read_bytes()
        need(len(body) == row['bytes'] and sha(body) == row['sha256'], 'STARTUP_FILE_PIN')
    need(set(startup['files']) == {'bootstrap.py', 'worker.py', 'private_bundle.py', 'PRIVATE_PACKAGE_RECEIPT.json'}, 'STARTUP_EXACT_FILE_SET')
    bootstrap = overlay[BOOTSTRAP].decode()
    need("SOURCE_SHA = '" + sha(overlay[RUNTIME]) + "'" in bootstrap, 'BOOTSTRAP_SOURCE_CONSTANT')
    need(bootstrap.index('config = prepare_private(') < bootstrap.index('registry_environment = private_module.install(')
         < bootstrap.index('environment = parent.bootstrap.child_environment(')
         < bootstrap.index('environment.update(registry_environment)'), 'OWNER_BEFORE_INSTALL_BEFORE_CHILD')
    need('module.verify_startup(path, expected)' in args.worker.read_text(), 'UNCHANGED_WORKER_USES_EXPANDED_VERIFIER')
    for name in (BOOTSTRAP, COLD + 'private_bundle.py'):
        ast.parse(overlay[name], filename=name)
    runtime_rows = {row['path']: row for row in runtime['files']}
    full_rows = {row['path']: row for row in closure['files']}
    need(len(runtime_rows) == len(runtime['files']) and len(full_rows) == len(closure['files']), 'UNIQUE_SOURCE_ROWS')
    for row in base['files']:
        expected = pin(row['path'], overlay[row['path']]) if row['path'] in overlay else row
        need(runtime_rows[row['path']] == expected, 'BASELINE_ROW_PRESERVED_OR_EXACT_OVERLAY')
    for name, raw in overlay.items():
        need(full_rows[name] == pin(name, raw), 'COMPLETE_INSTALLED_OVERLAY_CLOSURE')
    for name, row in runtime_rows.items():
        need(full_rows[name] == row, 'COMPLETE_INSTALLED_RUNTIME_CLOSURE')
    for key in ('externalFiles', 'conditionalExternalFiles', 'conditionalExternalPolicy'):
        need(runtime[key] == base[key] == closure[key], 'EXTERNAL_PARENT_CONTRACT_UNCHANGED')
    generated = json.loads(overlay[GENERATED])
    need(len(generated['variants']) == 3, 'THREE_VARIANTS_ONLY')
    frozen = {row['path']: row for row in base['files']}
    for row in generated['variants']:
        need(runtime_rows[row['original']] == frozen[row['original']] and
             frozen[row['original']]['sha256'] == row['originalSHA256'], 'FROZEN_ORIGINAL_SOURCE')
        need(runtime_rows[HANDOFF + row['variant']]['sha256'] == row['variantSHA256'], 'VARIANT_RUNTIME_BINDING')
    native = overlay[OFFICIAL + 'presentation_runtime_nvidia.generated.mjs'].decode()
    need('prepareFrame:official?async frame=>' in native and 'await factory.prepareCandidateFrame(frame)' in native
         and 'assertNvidiaVulkanContext(gl)' in native and 'officialCandidateLifecycle:official' in native,
         'NATIVE_ASSET_PREP_AND_NVIDIA_GUARD_PRESERVED')

    # New environment integration is exercised through both frozen filters.
    original_path = args.dependency_repository / 'world-simulation-shorts-engine/recovery/production-studio-mvp-v1/bootstrap.py'
    https_path = args.dependency_repository / 'world-simulation-shorts-engine/recovery/studio-https-bootstrap-v1/https_bootstrap.py'
    for path in (original_path, https_path):
        rel = path.relative_to(args.dependency_repository).as_posix()
        need(sha(path.read_bytes()) == frozen[rel]['sha256'], 'FROZEN_FILTER_SOURCE_PIN')
    original = function_only(original_path, 'child_environment', {'SECRET_ENV': {'WORLD_ENGINE_STUDIO_OWNER_CODE', 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON'}})
    https = function_only(https_path, 'child_environment', {'original': SimpleNamespace(child_environment=original),
                          'CONFIGURATION_ERROR': 'WORLD_ENGINE_STUDIO_CONFIGURATION_ERROR', '_POLICY_CODES': set()})
    registry_keys = {'WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_FILE': '/workspace/shared/test/registry.json',
                     'WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_SHA256': '1' * 64}
    env = dict(registry_keys, WORLD_ENGINE_STUDIO_OWNER_CODE='NEVER_PROPAGATE',
               WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON='NEVER_PROPAGATE')
    config = {'owner': '/test/owner', 'origin': '', 'home': '/test/home', 'root': '/test/state', 'xdg': {}}
    child = https(https(env, studio=True, config=config), studio=True, config=config)
    need(all(child.get(key) == value for key, value in registry_keys.items()), 'REGISTRY_ENV_SURVIVES_REPEATED_FILTER')
    need('WORLD_ENGINE_STUDIO_OWNER_CODE' not in child and 'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_JSON' not in child,
         'EXISTING_OWNER_SECRET_FILTER_PRESERVED')
    result = {'schema': 'WORLD_ENGINE_NEW_SOURCE_STARTUP_QUALIFICATION_V1', 'status': 'PASS',
              'scope': 'NEW_MANIFEST_BINDING_AND_PRIVATE_STARTUP_INTEGRATION_ONLY',
              'contextSHA256': sha(context_raw), 'sourceClosureSHA256': sha(closure_raw),
              'runtimeManifestSHA256': context['runtimeManifestSHA256'],
              'startupManifestSHA256': context['startupManifestSHA256'],
              'runtimeFiles': len(runtime_rows), 'installedClosureFiles': len(full_rows),
              'overlayFiles': len(overlay), 'oldPASSReruns': 0, 'renders': 0, 'gpuStarts': 0,
              'installedImageValidated': False,
              'checks': ['exact_published_v16_parent', 'overlay_source_hashes', 'three_manifest_entrypoint_hash_chain',
                         'complete_public_installed_file_set', 'frozen_originals_and_external_contract',
                         'three_generated_variants', 'native_optional_asset_preparation',
                         'owner_configuration_before_private_install', 'expanded_startup_verifier_shared_with_worker',
                         'repeated_frozen_child_environment_registry_and_secret_boundary', 'changed_python_syntax']}
    write(args.output, encoded(result))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('context', 'closure', 'v16-overlay', 'worker', 'dependency-repository', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    print(json.dumps(qualify(parser.parse_args()), sort_keys=True))
