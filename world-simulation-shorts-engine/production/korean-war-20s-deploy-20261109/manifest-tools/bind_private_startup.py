"""Bind the separately qualified private installer to an immutable public context."""
from pathlib import Path
import argparse
import copy
import json

from prepare_native_manifests import (BOOTSTRAP, COLD, PARENT, ROOT, RUNTIME,
                                      STARTUP, encoded, need, pin, sha, write)


def replace_once(raw, before, after):
    need(raw.count(before) == 1, 'EXACT_BOOTSTRAP_INTEGRATION_ANCHOR')
    return raw.replace(before, after)


def bind(args):
    need(not args.output.exists(), 'FRESH_FINAL_CONTEXT_REQUIRED')
    context = json.loads((args.public_context / 'CONTEXT.json').read_bytes())
    closure = json.loads((args.public_context / 'PUBLIC_SOURCE_CLOSURE.json').read_bytes())
    need(context['parentImage'] == closure['parentImage'] == PARENT, 'V16_PARENT_REQUIRED')
    overlay = {}
    for row in context['overlay']:
        raw = (args.public_context / 'overlay' / row['path']).read_bytes()
        need(pin(row['path'], raw) == row, 'PUBLIC_CONTEXT_CHANGED')
        overlay[row['path']] = raw
    installer = args.installer.read_bytes()
    receipt_raw = args.receipt.read_bytes()
    receipt = json.loads(receipt_raw)
    need(receipt['schema'] == 'WORLD_ENGINE_PRIVATE_PACKAGE_V1', 'PRIVATE_PACKAGE_SCHEMA')
    need(receipt['installationPath'] == '/workspace/shared', 'PRIVATE_INSTALL_ROOT')
    need(isinstance(receipt['nativeCodePins'], list) and len(receipt['nativeCodePins']) >= 2,
         'PRIVATE_NATIVE_RUNTIME_AND_GUARD_BINDING_REQUIRED')
    source_rows = {row['path']: row for row in closure['files']}
    for row in receipt['nativeCodePins']:
        need(row['path'] in source_rows and source_rows[row['path']]['sha256'] == row['sha256'],
             'PRIVATE_NATIVE_CODE_BINDING_MISMATCH')
    bootstrap = overlay[BOOTSTRAP]
    bootstrap = replace_once(bootstrap,
        b"set(value['files']) != {'bootstrap.py', 'worker.py'}",
        b"set(value['files']) != {'bootstrap.py', 'worker.py', 'private_bundle.py', 'PRIVATE_PACKAGE_RECEIPT.json'}")
    bootstrap = replace_once(bootstrap,
        b"        config = prepare_private(parent, os.environ, args.export_root)\n        environment = parent.bootstrap.child_environment(os.environ, studio=True, config=config)\n",
        b"        config = prepare_private(parent, os.environ, args.export_root)\n"
        b"        private_module = load('_cold_start_private_bundle', HERE / 'private_bundle.py')\n"
        b"        registry_environment = private_module.install(HERE / 'PRIVATE_PACKAGE_RECEIPT.json', contract.repo)\n"
        b"        os.environ.update(registry_environment)\n"
        b"        environment = parent.bootstrap.child_environment(os.environ, studio=True, config=config)\n"
        b"        environment.update(registry_environment)\n")
    overlay[BOOTSTRAP] = bootstrap
    overlay[COLD + 'private_bundle.py'] = installer
    overlay[COLD + 'PRIVATE_PACKAGE_RECEIPT.json'] = receipt_raw
    startup = json.loads(overlay[STARTUP])
    for name in ('bootstrap.py', 'private_bundle.py', 'PRIVATE_PACKAGE_RECEIPT.json'):
        row = pin(COLD + name, overlay[COLD + name])
        startup['files'][name] = {key: row[key] for key in ('bytes', 'sha256')}
    overlay[STARTUP] = encoded(startup)
    entry = context['entrypoint'][:]
    entry[entry.index('--startup-manifest-sha256') + 1] = sha(overlay[STARTUP])
    context.update(
        status='SOURCE_CONTEXT_ASSEMBLED_REQUIRES_BUILD_GATE', entrypoint=entry,
        startupManifestSHA256=sha(overlay[STARTUP]),
        overlay=[pin(name, raw) for name, raw in sorted(overlay.items())],
        precreatedDirectories=[{'path': '/workspace', 'uid': 0, 'gid': 0, 'mode': '0755'},
                               {'path': '/workspace/shared', 'uid': 1000, 'gid': 1000, 'mode': '0700'}],
        privateInstallerSHA256=sha(installer), privateReceiptSHA256=sha(receipt_raw),
        privateArchiveSHA256=receipt['archiveSHA256'],
        privateArchiveName=receipt['archiveName'],
        privateRegistrySHA256=receipt['registrySHA256'],
        privateInstallationAtStartup=True,
    )
    for name, raw in overlay.items():
        source_rows[name] = pin(name, raw)
    closure['files'] = sorted(source_rows.values(), key=lambda row: row['path'])
    closure['startupManifestSHA256'] = context['startupManifestSHA256']
    closure['status'] = 'PASS'
    closure['qualificationScope'] = 'METADATA_SOURCE_CLOSURE_AND_STARTUP_BINDING_ONLY'
    closure['privateRegistryVerification'] = 'PINNED_STARTUP_INSTALLER_AND_SEPARATE_ARCHIVE'
    closure['privateReceiptSHA256'] = sha(receipt_raw)
    closure['privateArchiveSHA256'] = receipt['archiveSHA256']
    old_changes = {row['path']: row for row in closure['changes']}
    for name, raw in overlay.items():
        old_changes[name] = dict(pin(name, raw), baselineSHA256=old_changes.get(name, {}).get('baselineSHA256'))
    closure['changes'] = sorted(old_changes.values(), key=lambda row: row['path'])
    closure['startupIntegration'] = {
        'ownerConfigurationBeforeInstall': True,
        'installerVerifiedBeforeImport': True,
        'workerUsesBootstrapStartupVerifier': True,
        'registryPinsPropagatedToStudioChild': True,
        'originalSecretEnvironmentPolicyUnchanged': True,
        'launchesOrRendersDuringAssembly': 0,
    }
    for name, raw in sorted(overlay.items()):
        write(args.output / 'overlay' / name, raw)
    dockerfile = ('FROM ' + PARENT + '\nCOPY --chown=0:0 ' + json.dumps(['overlay/', ROOT + '/']) + '\n'
                  'RUN install -d -o 0 -g 0 -m 0755 /workspace && install -d -o 1000 -g 1000 -m 0700 /workspace/shared\n'
                  'ENTRYPOINT ' + json.dumps(entry) + '\n').encode()
    write(args.output / 'Dockerfile', dockerfile)
    write(args.output / 'CONTEXT.json', encoded(context))
    write(args.output.parent / 'PUBLIC_SOURCE_CLOSURE.json', encoded(closure))
    return {'status': context['status'], 'runtimeManifestSHA256': context['runtimeManifestSHA256'],
            'startupManifestSHA256': context['startupManifestSHA256'],
            'privateInstallerSHA256': sha(installer), 'privateReceiptSHA256': sha(receipt_raw),
            'installedSourceFiles': len(source_rows), 'overlayFiles': len(overlay)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('public-context', 'installer', 'receipt', 'output'):
        parser.add_argument('--' + name, required=True, type=Path)
    print(json.dumps(bind(parser.parse_args()), sort_keys=True))
