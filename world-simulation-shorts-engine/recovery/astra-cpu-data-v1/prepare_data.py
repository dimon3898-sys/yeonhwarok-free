"""Explicit local CLI; preserves Scene payload and emits neutral CPU artifacts."""
import argparse
import json
from pathlib import Path
import sys

from astra_cpu.cache import FileCache
from astra_cpu.model import DataError, sha256
from astra_cpu.neutral import encode_neutral
from astra_cpu.pipeline import CpuDataPipeline
from astra_cpu.providers import ArchiveCatalog
from astra_cpu.scene import prepare_scene


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--cache-dir', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--accept-recorded-license-evidence', action='store_true',
                        help='Explicitly assert the previously preserved Phase A license review; does not waive source terms')
    args = parser.parse_args()
    try:
        if args.scene.stat().st_size > 2*1024*1024:
            raise DataError('scene exceeds 2 MiB input limit')
        scene = json.loads(args.scene.read_bytes())
        # Disabled/legacy configuration must not inspect a source archive.
        extension = scene.get('mapData') if isinstance(scene, dict) else None
        enabled = isinstance(extension, dict) and extension.get('enabled') is True
        preliminary = None if enabled else prepare_scene(scene)
        catalog = None if preliminary is not None else ArchiveCatalog(
            args.archive, license_verified=args.accept_recorded_license_evidence)
        prepared = preliminary if preliminary is not None else prepare_scene(scene, catalog)
        policy = prepared.cache_policy
        mode = policy.get('mode', 'read_write')
        cache = None if args.cache_dir is None or mode == 'bypass' or not prepared.enabled else FileCache(
            args.cache_dir, max_bytes=policy.get('maxBytes', 64*1024*1024))
        result = CpuDataPipeline(catalog, cache, mode=mode).prepare(prepared)
        args.output.mkdir(parents=True, exist_ok=True)
        manifest = result.to_dict()
        manifest['artifacts'] = []
        for role, source in result.results.items():
            for index, raster in enumerate(source.rasters):
                if source.status != 'available':
                    continue
                name = f'{role}-{index:02d}.npz'
                data = encode_neutral(raster)
                destination = args.output/name
                # Existing proof artifacts are immutable; repeat writes only if identical.
                if destination.exists() and destination.read_bytes() != data:
                    raise DataError('output artifact differs; select a new output directory')
                destination.write_bytes(data)
                manifest['artifacts'].append({'file': name, 'sha256': sha256(data), 'role': role,
                                              'sourceId': source.source_id, 'sourceVersion': source.source_version})
        encoded = (json.dumps(manifest, sort_keys=True, indent=2, allow_nan=False)+'\n').encode()
        target = args.output/'CPU_PREPARATION_MANIFEST.json'
        if target.exists() and target.read_bytes() != encoded:
            raise DataError('output manifest differs; select a new output directory')
        target.write_bytes(encoded)
        print(json.dumps({'enabled': result.enabled,
                          'statusByRole': {role: item.status for role, item in result.results.items()},
                          'artifacts': len(manifest['artifacts']), 'gpuActivation': False,
                          'networkRequestsExecuted': False}))
        return 0 if all(item.status == 'available' for item in result.results.values()) else 2
    except (DataError, OSError, ValueError, KeyError) as error:
        print(json.dumps({'status': 'invalid_data', 'error': str(error), 'gpuActivation': False}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
