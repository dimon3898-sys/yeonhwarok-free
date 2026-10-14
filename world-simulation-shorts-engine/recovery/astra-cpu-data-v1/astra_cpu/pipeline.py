"""Local CPU provider/cache composition; no network or renderer activation.

SourceCatalog is structural: ``sources`` maps identifiers to SourceSpec and
``read_bytes(relative_path)`` returns the preserved original asset bytes.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from pathlib import PurePosixPath
import re

from .cache import CacheError, CacheRequest, FileCache
from .model import DataError, RasterData, sha256, split_dateline
from .neutral import json_value
from .providers import DataRequest, TerrainSource, BathymetrySource, SurfaceTextureSource

_CLASSES = {'land_elevation': TerrainSource, 'ocean_bathymetry': BathymetrySource,
            'land_surface_texture': SurfaceTextureSource}
_SUMMARY = 'cpuProviderCacheSummary'
_CACHE_FIELDS = {_SUMMARY, 'cacheTransformVersion', 'cacheSourceMetadataSha256'}


def source_metadata_sha256(spec):
    """Bind sidecars, CRS/datum, attribution, version and license assertion."""
    return sha256(json.dumps(json_value(asdict(spec)), sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode())


def implementation_version():
    """Automatic transform identity: changed parsing code cannot reuse old output."""
    root = Path(__file__).resolve().parent
    files = ('model.py', 'terrain.py', 'bathymetry.py', 'surface.py', 'providers.py',
             'neutral.py', 'pipeline.py')
    inventory = [(name, sha256((root/name).read_bytes())) for name in files]
    return 'ASTRA_CPU_EXTRACT_V1:' + sha256(json.dumps(inventory).encode())


@dataclass(frozen=True)
class CpuPreparationResult:
    enabled: bool
    renderer_sha256: str
    results: dict
    gpu_activation: bool = field(default=False, init=False)

    def to_dict(self):
        return {'schema': 'ASTRA_CPU_PREPARATION_V1', 'enabled': self.enabled,
                'rendererPayloadSHA256': self.renderer_sha256,
                'sources': {role: result.to_dict() for role, result in self.results.items()},
                'gpuActivation': False, 'networkRequestsExecuted': False}


class CpuDataPipeline:
    """Reuse providers and the shared neutral cache without changing their APIs.

    ``read_only`` may read the supplied local catalog on a miss, but never writes
    cache entries. ``bypass`` does neither. No mode starts an external request.
    Partial coverage is retained explicitly; absent parts are never cached as
    successful rasters. Ocean classification still requires an external mask.
    """
    def __init__(self, catalog, cache=None, *, mode='read_write'):
        if mode not in {'read_write', 'read_only', 'bypass'}:
            raise DataError('unsupported CPU cache mode')
        if cache is not None and not isinstance(cache, FileCache):
            raise DataError('pipeline cache must be FileCache or None')
        self.catalog = catalog
        self.cache = cache
        self.mode = mode
        self.transform_version = implementation_version()

    def _raw_reader(self, spec):
        def asset_path(path):
            if not isinstance(path,str) or '\\' in path:
                raise DataError('source/sidecar path must be canonical relative POSIX text')
            value=PurePosixPath(path)
            if value.is_absolute() or '..' in value.parts or value.as_posix()!=path:
                raise DataError('unsafe source/sidecar asset path')
        asset_path(spec.relative_path)
        if spec.data_class=='land_surface_texture':
            if len(spec.sidecars)!=2 or {PurePosixPath(s['relative_path']).suffix.lower() for s in spec.sidecars}!={'.pgw','.prj'}:
                raise DataError('surface source must declare exactly one PGW and one PRJ sidecar')
        identities = {spec.relative_path: spec.sha256}
        for sidecar in spec.sidecars:
            path, digest = sidecar['relative_path'], sidecar['sha256']
            asset_path(path)
            if not isinstance(digest,str) or re.fullmatch('[0-9a-f]{64}',digest) is None:
                raise DataError('sidecar digest must be lowercase SHA-256')
            if path in identities:
                raise DataError('duplicate source/sidecar path')
            identities[path] = digest
        metadata_sha = source_metadata_sha256(spec)

        def read(path):
            if path not in identities:
                raise DataError('parser requested an undeclared original asset')
            key = CacheRequest(spec.source_id, spec.source_version,
                               source_sha256=identities[path],
                               source_metadata_sha256=metadata_sha)
            if self.cache is None or self.mode == 'bypass':
                return self.catalog.read_bytes(path)
            if self.mode == 'read_only':
                entry = self.cache.get_raw(key)
                return entry.data if entry is not None else self.catalog.read_bytes(path)
            return self.cache.get_or_create_raw(key, lambda: self.catalog.read_bytes(path)).data
        return read

    def _derived_request(self, spec, request, bbox):
        # Each cached part carries aggregate coverage for its original request.
        # Bind that whole request too: a dateline half must never reuse another
        # request's totals, warnings or absent-part description.
        context = {'targetGroundResolution': request.target_ground_resolution,
                   'wholeRequestBBox': list(request.bbox), 'resampling': 'NONE'}
        return CacheRequest(spec.source_id, spec.source_version, tuple(bbox), request.crs,
                            context, spec.sha256,
                            self.transform_version, source_metadata_sha256(spec))

    def provide(self, source_id, request, *, source_version=None):
        try:
            spec = self.catalog.sources[source_id]
        except (KeyError, TypeError) as error:
            raise DataError('source identifier is absent from explicit catalog') from error
        if spec.data_class not in _CLASSES:
            raise DataError('unsupported CPU source role')
        provider = _CLASSES[spec.data_class](spec, self.catalog.read_bytes)
        # Let the existing provider validate failures before any cache lookup.
        if not isinstance(request, DataRequest) or not spec.license_verified or (
                source_version is not None and source_version != spec.source_version):
            return provider.provide(request, source_version=source_version)
        try:
            provider.read_bytes = self._raw_reader(spec)
            request.validate()
            parts = split_dateline(request.bbox)
            keys = [self._derived_request(spec, request, part) for part in parts]
            if self.cache is not None and self.mode != 'bypass':
                cached = [self.cache.get_derived(key) for key in keys]
                if all(raster is not None for raster in cached):
                    summaries = [r.metadata.get(_SUMMARY) for r in cached]
                    if any(not isinstance(s, dict) or set(s) != {'coverage', 'warnings'} for s in summaries):
                        raise CacheError('derived provider summary missing or invalid')
                    if any(summary != summaries[0] for summary in summaries[1:]):
                        raise CacheError('derived multipart provider summaries disagree')
                    rasters = []
                    for raster in cached:
                        metadata = {key: deepcopy(value) for key, value in raster.metadata.items()
                                    if key not in _CACHE_FIELDS}
                        rasters.append(RasterData(raster.values, raster.x, raster.y, raster.valid, metadata))
                    if not any(r.valid.any() for r in rasters):
                        raise CacheError('cached available provider has no valid sample support')
                    return provider._result('available', rasters=rasters,
                                            coverage=deepcopy(summaries[0]['coverage']),
                                            warnings=tuple(summaries[0]['warnings']))
            result = provider.provide(request, source_version=source_version)
            if result.status != 'available' or self.cache is None or self.mode != 'read_write':
                return result
            summary = {'coverage': deepcopy(result.coverage), 'warnings': list(result.warnings)}
            for raster in result.rasters:
                if _CACHE_FIELDS.intersection(raster.metadata):
                    raise DataError('source metadata uses reserved CPU cache fields')
                # A rectangular raster belongs to one split part; never cross-pad.
                matches = [index for index, part in enumerate(parts)
                           if (raster.x >= part[0]).all() and (raster.x < part[2]).all()
                           and (raster.y >= part[1]).all() and (raster.y < part[3]).all()]
                if len(matches) != 1:
                    raise DataError('extracted raster has ambiguous request-part identity')
                metadata = deepcopy(raster.metadata)
                metadata[_SUMMARY] = summary
                self.cache.put_derived(keys[matches[0]],
                    RasterData(raster.values, raster.x, raster.y, raster.valid, metadata))
            return result
        except (DataError, ValueError, OSError, KeyError, TypeError) as error:
            return provider._result('invalid_data', error={'code': 'CPU_CACHE_OR_EXTRACTION_INVALID',
                                                         'message': str(error)})

    def prepare(self, preparation):
        """Execute only the explicit, CPU-enabled ScenePreparation bindings."""
        if getattr(preparation, 'gpu_activation', None) is not False:
            raise DataError('CPU preparation cannot activate a GPU renderer')
        if not preparation.enabled:
            return CpuPreparationResult(False, preparation.renderer_sha256, {})
        policy = preparation.cache_policy
        if self.cache is not None and self.cache.max_bytes > policy['maxBytes']:
            raise DataError('provided cache limit exceeds explicit scene cache policy')
        executor = CpuDataPipeline(self.catalog, self.cache, mode=policy['mode'])
        results = {}
        for role, binding in preparation.source_bindings.items():
            if self.catalog.sources.get(binding.source_id) != binding:
                raise DataError('prepared source binding changed before extraction')
            results[role] = executor.provide(binding.source_id, preparation.request,
                                         source_version=binding.source_version)
        return CpuPreparationResult(True, preparation.renderer_sha256, results)
