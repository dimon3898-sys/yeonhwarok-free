"""CPU provider API: explicit identity, coverage, license and failure states."""
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from copy import deepcopy
import json
import math
import re
from urllib.parse import urlsplit
import zipfile

from .model import DataError, RasterData, split_dateline, validate_bbox, sha256
from .neutral import json_value

STATUSES = frozenset({'available', 'unavailable', 'auth_required', 'version_changed',
                      'license_unverified', 'invalid_data'})


@dataclass(frozen=True)
class DataRequest:
    bbox: tuple
    crs: str = 'EPSG:4326'
    target_ground_resolution: float | None = None

    def validate(self):
        validate_bbox(self.bbox)
        if self.crs != 'EPSG:4326':
            raise DataError('CPU source extraction currently supports geographic EPSG:4326 only; no implicit reprojection')
        resolution = self.target_ground_resolution
        if resolution is not None:
            try:
                valid = (not isinstance(resolution, bool) and isinstance(resolution, (int, float))
                         and math.isfinite(float(resolution)) and resolution > 0)
            except (ValueError, TypeError, OverflowError):
                valid = False
            if not valid:
                raise DataError('targetGroundResolution must be finite positive meters')


@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    source_version: str
    source_url: str
    data_class: str
    relative_path: str
    sha256: str
    native_resolution: object
    vertical_datum: str | None
    attribution: str
    license_verified: bool = False
    metadata: dict = field(default_factory=dict)
    sidecars: tuple = ()

    def __post_init__(self):
        if not isinstance(self.license_verified, bool):
            raise DataError('license verification must be an explicit boolean')
        for value in (self.source_id, self.source_version, self.source_url, self.data_class, self.relative_path):
            if not isinstance(value, str) or not value.strip():
                raise DataError('source identity/version/path must be nonempty strings')
        url = urlsplit(self.source_url)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment:
            raise DataError('source URL must be HTTPS without embedded credentials or fragment')
        if not isinstance(self.sha256, str) or re.fullmatch('[0-9a-f]{64}', self.sha256) is None:
            raise DataError('source hash must be lowercase SHA-256')

    @classmethod
    def from_manifest(cls, item, attribution, *, license_verified=False):
        return cls(item['id'], item['version'], item['original_url'], item['data_class'],
                   item['relative_path'], item['sha256'],
                   {'description': item['native_resolution'],
                    'sampleSpacingDegrees': item.get('sample_resolution_degrees')},
                   item.get('vertical_datum'), attribution, license_verified,
                   deepcopy(item), tuple(deepcopy(item.get('sidecars', ()))))


@dataclass(frozen=True)
class ProviderResult:
    status: str
    source_id: str
    source_version: str
    source_url: str
    bbox: object
    crs: str
    native_resolution: object
    output_resolution: object
    vertical_datum: str | None
    nodata: object
    attribution: str
    sha256: str | None
    error: dict | None
    rasters: tuple = ()
    warnings: tuple = ()
    coverage: dict = field(default_factory=dict)

    def to_dict(self):
        return json_value({'status': self.status, 'sourceId': self.source_id,
                           'sourceVersion': self.source_version, 'sourceURL': self.source_url,
                           'bbox': self.bbox, 'CRS': self.crs,
                           'nativeResolution': self.native_resolution, 'outputResolution': self.output_resolution,
                           'verticalDatum': self.vertical_datum, 'nodata': self.nodata,
                           'attribution': self.attribution, 'SHA-256': self.sha256, 'error': self.error,
                           'warnings': self.warnings, 'coverage': self.coverage,
                           'rasters': [{'shape': list(x.values.shape), 'dtype': x.values.dtype.str,
                                        'bbox': list(x.bbox), 'metadata': x.metadata} for x in self.rasters],
                           'gpuUploadExecuted': False})


class RasterProvider:
    data_class = None

    def __init__(self, spec: SourceSpec, read_bytes):
        self.spec = spec
        self.read_bytes = read_bytes

    def _result(self, status, *, error=None, rasters=(), warnings=(), coverage=None):
        spec = self.spec
        if status not in STATUSES:
            raise DataError('unknown provider status')
        actual_bbox = None
        if len(rasters) == 1:
            actual_bbox = list(rasters[0].bbox)
        elif len(rasters) > 1:
            actual_bbox = [rasters[0].bbox[0], min(x.bbox[1] for x in rasters),
                           rasters[-1].bbox[2], max(x.bbox[3] for x in rasters)]
        return ProviderResult(status, spec.source_id, spec.source_version, spec.source_url,
                              actual_bbox, rasters[0].metadata['crs'] if rasters else spec.metadata.get('horizontal_crs', 'UNKNOWN'), spec.native_resolution,
                              [{'spacingDegrees': [abs(x.metadata['transform'][1]), abs(x.metadata['transform'][5])],
                                'dimensions': [len(x.x), len(x.y)], 'resampling': 'NONE'} for x in rasters],
                              rasters[0].metadata.get('verticalDatum') if rasters else spec.vertical_datum,
                              [x.metadata.get('nodata') for x in rasters],
                              spec.attribution, spec.sha256, error, tuple(rasters), tuple(warnings), coverage or {})

    def provide(self, request: DataRequest, *, source_version=None):
        spec = self.spec
        try:
            if not isinstance(request, DataRequest):
                raise DataError('provider requires a DataRequest')
            request.validate()
            if spec.data_class != self.data_class:
                raise DataError('provider class does not match source data class')
            if source_version is not None and source_version != spec.source_version:
                return self._result('version_changed', error={'code': 'PINNED_VERSION_MISMATCH', 'message': 'source version differs'})
            if not spec.license_verified:
                return self._result('license_unverified', error={'code': 'LICENSE_REVIEW_REQUIRED', 'message': 'source use conditions unverified'})
            url = urlsplit(spec.source_url)
            if url.scheme != 'https' or url.username or url.password:
                raise DataError('source URL must be HTTPS without embedded credentials')
            raw = self.read_bytes(spec.relative_path)
            raster = self.parse(raw)
            if raster.metadata.get('crs') != request.crs:
                raise DataError('native CRS differs from requested CRS; reprojection is not implemented')
            parts = split_dateline(request.bbox)
            rasters, absent, warnings = [], [], []
            for part in parts:
                try:
                    rasters.append(raster.crop(part))
                except DataError as error:
                    if 'no supplied sample centers' not in str(error):
                        raise
                    absent.append(list(part))
            if not rasters:
                return self._result('unavailable', error={'code': 'NO_SOURCE_COVERAGE', 'message': 'no requested sample centers in supplied source'},
                                    coverage={'requestedBBox': list(request.bbox), 'absentParts': absent})
            if not any(x.valid.any() for x in rasters):
                return self._result('unavailable', rasters=rasters,
                                    error={'code': 'NO_VALID_SAMPLE_SUPPORT', 'message': 'all requested cells are nodata/invalid'},
                                    coverage={'requestedBBox': list(request.bbox), 'gridPresent': True, 'validSamples': 0})
            supplied = raster.bbox
            # Match the axis/transform roundoff tolerance; this does not add a
            # pixel of support, pad arrays or relax a visual admission rule.
            epsilon = 1e-9
            complete = not absent and all(supplied[0] <= p[0] + epsilon and supplied[1] <= p[1] + epsilon
                                         and supplied[2] >= p[2] - epsilon and supplied[3] >= p[3] - epsilon for p in parts)
            if not complete:
                warnings.append('PARTIAL_SOURCE_COVERAGE_NO_PADDING_OR_EXTRAPOLATION')
            if request.target_ground_resolution is not None:
                warnings.append('TARGET_RESOLUTION_IS_INTENT_ONLY_ORIGINAL_GRID_PRESERVED_NO_NEW_DETAIL')
            if self.data_class == 'ocean_bathymetry':
                warnings.append('OCEAN_MASK_REQUIRED_FOR_DEPTH_CLASSIFICATION; SIGNED_ELEVATION_IS_NOT_A_LAND_MASK')
            return self._result('available', rasters=rasters, warnings=warnings,
                                coverage={'requestedBBox': list(request.bbox), 'sourceBBox': list(supplied),
                                          'complete': complete, 'completenessMeaning': 'GRID_EXTENT_ONLY_NOT_GROUND_ACCURACY_OR_NODATA',
                                          'validSampleCount': sum(int(x.valid.sum()) for x in rasters),
                                          'actualBBoxes': [list(x.bbox) for x in rasters],
                                          'absentParts': absent, 'paddingApplied': False})
        except PermissionError:
            return self._result('auth_required', error={'code': 'ACCESS_AUTH_REQUIRED', 'message': 'source access requires configured authorization'})
        except (FileNotFoundError, KeyError):
            return self._result('unavailable', error={'code': 'SOURCE_NOT_FOUND', 'message': 'source asset unavailable'})
        except (DataError, ValueError, OSError, zipfile.BadZipFile) as error:
            return self._result('invalid_data', error={'code': 'INVALID_SOURCE_OR_REQUEST', 'message': str(error)})


class TerrainSource(RasterProvider):
    data_class = 'land_elevation'

    def parse(self, raw):
        from .terrain import parse_terrain
        return parse_terrain(raw, expected_sha256=self.spec.sha256, vertical_datum=self.spec.vertical_datum)


class BathymetrySource(RasterProvider):
    data_class = 'ocean_bathymetry'

    def parse(self, raw):
        from .bathymetry import parse_bathymetry
        return parse_bathymetry(raw, expected_sha256=self.spec.sha256, vertical_datum=self.spec.vertical_datum)


class SurfaceTextureSource(RasterProvider):
    data_class = 'land_surface_texture'

    def parse(self, raw):
        from .surface import parse_surface
        sidecars = {PurePosixPath(x['relative_path']).suffix.lower(): x for x in self.spec.sidecars}
        if set(sidecars) != {'.pgw', '.prj'}:
            raise DataError('surface source requires exactly PGW and PRJ sidecars')
        world, projection = sidecars['.pgw'], sidecars['.prj']
        return parse_surface(raw, self.read_bytes(world['relative_path']), self.read_bytes(projection['relative_path']),
                             expected_sha256=self.spec.sha256,
                             expected_sidecar_sha256={'worldfile': world['sha256'], 'projection': projection['sha256']})


class ArchiveCatalog:
    """Reuse the preserved package; each parser verifies only its used source bytes.

    The already-completed all-member audit is not repeated on each request.
    License approval is an explicit caller assertion tied to recorded evidence.
    """
    def __init__(self, archive_path, *, license_verified=False):
        self.archive_path = archive_path
        self.manifest = json.loads(self._read_member('DATA_MANIFEST.json', 2*1024*1024))
        attribution = self._read_member('licenses/ATTRIBUTION.txt', 1024*1024).decode()
        self.sources = {}
        for item in self.manifest['datasets']:
            spec = SourceSpec.from_manifest(item, attribution, license_verified=license_verified)
            if spec.source_id in self.sources:
                raise DataError('duplicate source identity')
            self.sources[spec.source_id] = spec

    def read_bytes(self, relative_path):
        return self._read_member(relative_path, 64*1024*1024)

    def _read_member(self, relative_path, max_bytes):
        if not isinstance(relative_path, str) or '\\' in relative_path:
            raise DataError('source archive path must be canonical POSIX relative text')
        path = PurePosixPath(relative_path)
        if path.is_absolute() or '..' in path.parts or path.as_posix() != relative_path:
            raise DataError('unsafe source archive path')
        with zipfile.ZipFile(self.archive_path) as archive:
            entries = [x for x in archive.infolist() if x.filename == relative_path]
            if not entries:
                raise FileNotFoundError('source archive member missing')
            if len(entries) != 1 or entries[0].is_dir() or entries[0].file_size > max_bytes:
                raise DataError('duplicate/oversized source asset')
            return archive.read(relative_path)

    def provider(self, source_id):
        spec = self.sources[source_id]
        classes = {'land_elevation': TerrainSource, 'ocean_bathymetry': BathymetrySource,
                   'land_surface_texture': SurfaceTextureSource}
        if spec.data_class not in classes:
            raise DataError('unsupported source class')
        return classes[spec.data_class](spec, self.read_bytes)
