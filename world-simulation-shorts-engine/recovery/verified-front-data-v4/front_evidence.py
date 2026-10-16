"""Offline, evidence-bound front digitization candidates, never historical approval.

The adapter does not fetch, infer fronts, close territory, simplify coordinates,
change a Scene, or authorize rendering. Original map interpretation and legal
reuse still require documented human review. Numerical georeferencing is owned
by the adjacent generic georeference module, not duplicated here.
"""
from __future__ import annotations

from copy import deepcopy
import argparse
import datetime as dt
import hashlib
import importlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
from urllib.parse import urlsplit

SCHEMA = 'WORLD_ENGINE_FRONT_EVIDENCE_CANDIDATE_V1'
OUTPUT_SCHEMA = 'WORLD_ENGINE_FRONT_TECHNICAL_CANDIDATE_V1'
MAX_AREA_LINE_VERTICES = 129
MAX_TOTAL_VERTICES = 32768
MAX_FILE_BYTES = 64 * 1024**2
SHA = re.compile(r'[a-f0-9]{64}\Z')
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z')


class FrontEvidenceError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _require(condition, code):
    if not condition:
        raise FrontEvidenceError(code)


def _text(value, code, limit=4000):
    _require(isinstance(value, str) and 0 < len(value.strip()) <= limit
             and not any(ord(char) < 32 and char not in '\n\t' for char in value), code)
    return value


def _record(value, code):
    _require(isinstance(value, dict), code)
    return value


def _date(value, code):
    _require(isinstance(value, str), code)
    try:
        parsed = dt.date.fromisoformat(value)
    except ValueError:
        raise FrontEvidenceError(code) from None
    _require(parsed.isoformat() == value, code)
    return value


def _sha(value):
    return hashlib.sha256(value).hexdigest()


def _read_bound(root, reference, *, limit=MAX_FILE_BYTES):
    _record(reference, 'FILE_REFERENCE_REQUIRED')
    name, expected = reference.get('path'), reference.get('sha256')
    _require(isinstance(name, str) and name and '\\' not in name and '\x00' not in name
             and not PurePosixPath(name).is_absolute() and str(PurePosixPath(name)) == name
             and all(part not in ('', '.', '..') for part in name.split('/')), 'CANONICAL_RELATIVE_PATH_REQUIRED')
    _require(isinstance(expected, str) and SHA.fullmatch(expected), 'FILE_SHA256_REQUIRED')
    cursor = Path(root).absolute()
    _require(not any(item.is_symlink() for item in [cursor, *cursor.parents]), 'SOURCE_SYMLINK_FORBIDDEN')
    for component in name.split('/'):
        cursor /= component
        _require(not cursor.is_symlink(), 'SOURCE_SYMLINK_FORBIDDEN')
    try:
        descriptor = os.open(cursor, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise FrontEvidenceError('SOURCE_FILE_UNAVAILABLE') from None
    try:
        before = os.fstat(descriptor)
        _require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= limit, 'BOUNDED_REGULAR_SOURCE_REQUIRED')
        chunks, remaining = [], before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024**2))
            _require(bool(chunk), 'SOURCE_CHANGED_DURING_READ')
            chunks.append(chunk)
            remaining -= len(chunk)
        raw, after = b''.join(chunks), os.fstat(descriptor)
        current = os.stat(cursor, follow_symlinks=False)
    except OSError:
        raise FrontEvidenceError('SOURCE_FILE_UNAVAILABLE') from None
    finally:
        os.close(descriptor)
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
    _require(identity(before) == identity(after) == identity(current), 'SOURCE_CHANGED_DURING_READ')
    _require(_sha(raw) == expected, 'SOURCE_SHA256_MISMATCH')
    return cursor, raw


def _json(raw):
    def unique_pairs(pairs):
        output = {}
        for key, value in pairs:
            if key in output:
                raise ValueError('duplicate JSON key')
            output[key] = value
        return output
    try:
        return json.loads(raw, object_pairs_hook=unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeDecodeError, ValueError, TypeError):
        raise FrontEvidenceError('VALID_FINITE_JSON_REQUIRED') from None


def _media(raw, expected):
    beginning = raw[:4096].lstrip().lower()
    _require(not beginning.startswith((b'<!doctype html', b'<html', b'<head', b'<body', b'http/'))
             and b'<html' not in beginning and b'proxy connect 403' not in beginning,
             'HTML_OR_ACCESS_ERROR_NOT_SOURCE_MAP')
    detected = ('application/pdf' if raw.startswith(b'%PDF-') and b'%%EOF' in raw[-2048:]
                else 'image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n')
                else 'image/jpeg' if raw.startswith(b'\xff\xd8\xff') and raw.endswith(b'\xff\xd9')
                else 'image/tiff' if raw[:4] in (b'II*\x00', b'MM\x00*') else None)
    _require(detected is not None and detected == expected, 'SOURCE_MEDIA_SIGNATURE_MISMATCH')
    return detected


def _page(locator, *, required):
    _record(locator, 'MAP_PAGE_LOCATOR_REQUIRED')
    page = locator.get('pdfPageIndex0')
    _require((type(page) is int and page >= 0) if required else (page is None or type(page) is int and page >= 0),
             'PDF_PAGE_INDEX_REQUIRED')
    printed = locator.get('printedPage')
    _require(printed is None or isinstance(printed, str) and 0 < len(printed) <= 100, 'PRINTED_PAGE_LOCATOR_INVALID')
    _text(locator.get('caption'), 'MAP_CAPTION_REQUIRED')


def _source(manifest, root):
    source, map_record = (_record(manifest.get(name), name.upper() + '_REQUIRED') for name in ('source', 'map'))
    source_id = source.get('sourceId')
    _require(isinstance(source_id, str) and IDENTIFIER.fullmatch(source_id), 'SOURCE_ID_REQUIRED')
    for field in ('publisher', 'documentTitle', 'retrievedAt'):
        _text(source.get(field), 'SOURCE_' + field.upper() + '_REQUIRED')
    url = _text(source.get('sourceURL'), 'SOURCE_URL_REQUIRED')
    parsed = urlsplit(url)
    synthetic = manifest['dataMode'] == 'SYNTHETIC_TEST'
    _require(parsed.scheme == ('synthetic' if synthetic else 'https') and parsed.netloc
             and parsed.username is None and parsed.password is None, 'SOURCE_URL_MODE_MISMATCH')
    original_path, original = _read_bound(root, source.get('original'))
    original_type = _media(original, source['original'].get('mediaType'))
    license_record = _record(source.get('license'), 'LICENSE_EVIDENCE_REQUIRED')
    expected_license = 'SYNTHETIC_TEST' if synthetic else 'DOCUMENTED_BASIS_REVIEW_REQUIRED'
    _require(license_record.get('status') == expected_license, 'LICENSE_REUSE_BASIS_REQUIRED')
    for field in ('basis', 'reference', 'attribution', 'scope'):
        _text(license_record.get(field), 'LICENSE_' + field.upper() + '_REQUIRED')
    _require(not synthetic or 'SYNTHETIC' in license_record['basis'], 'SYNTHETIC_LICENSE_LABEL_REQUIRED')
    map_id = map_record.get('mapId')
    _require(isinstance(map_id, str) and IDENTIFIER.fullmatch(map_id), 'MAP_ID_REQUIRED')
    _date(map_record.get('mapDate'), 'MAP_DATE_REQUIRED')
    _page(map_record.get('locator'), required=original_type == 'application/pdf')
    _require(map_record.get('lineMeaning') == 'OBSERVED_FRONT_POSITION', 'OBSERVED_FRONT_MEANING_REQUIRED')
    classification = _record(map_record.get('classificationEvidence'), 'MAP_CLASSIFICATION_EVIDENCE_REQUIRED')
    for field in ('legendExcerpt', 'legendLocator', 'interpretationRationale'):
        _text(classification.get(field), 'CLASSIFICATION_' + field.upper() + '_REQUIRED')
    raster_path, raster = _read_bound(root, map_record.get('raster'))
    raster_type = _media(raster, map_record['raster'].get('mediaType'))
    _require(raster_type.startswith('image/'), 'MAP_RASTER_IMAGE_REQUIRED')
    if original_type == 'application/pdf':
        recipe = _record(map_record.get('rasterDerivation'), 'DOCUMENT_PAGE_DERIVATION_REQUIRED')
        _require(recipe.get('originalDocumentSHA256') == _sha(original)
                 and recipe.get('derivedRasterSHA256') == _sha(raster)
                 and recipe.get('pdfPageIndex0') == map_record['locator']['pdfPageIndex0'],
                 'DOCUMENT_RASTER_PAGE_BINDING_MISMATCH')
        for field in ('tool', 'toolVersion', 'recipe', 'sourcePageSelection'):
            _text(recipe.get(field), 'RASTER_DERIVATION_' + field.upper() + '_REQUIRED')
    else:
        _require(original_path == raster_path and original == raster, 'DIRECT_MAP_RASTER_MUST_EQUAL_ORIGINAL')
        _require(map_record.get('rasterDerivation') is None, 'UNNEEDED_RASTER_DERIVATION_FORBIDDEN')
    return source, map_record, raster_path, _sha(original), _sha(raster)


def _review(manifest, source_sha, raster_sha):
    review = _record(manifest.get('reviewRecord'), 'BOUND_REVIEW_RECORD_REQUIRED')
    for field in ('reviewId', 'reviewer', 'reviewedAt', 'mapInterpretationNotes', 'uncertaintyNotes'):
        _text(review.get(field), 'REVIEW_' + field.upper() + '_REQUIRED')
    _require(review.get('decision') == 'TECHNICAL_CANDIDATE_ONLY'
             and review.get('originalDocumentSHA256') == source_sha
             and review.get('mapRasterSHA256') == raster_sha
             and review.get('georeferenceReportSHA256') == manifest['georeferenceReport']['sha256']
             and review.get('digitizationSHA256') == manifest['digitization']['sha256'], 'REVIEW_EVIDENCE_BINDING_REQUIRED')
    _require(isinstance(review.get('checkedFeatureIds'), list) and review['checkedFeatureIds']
             and all(isinstance(item, str) and IDENTIFIER.fullmatch(item) for item in review['checkedFeatureIds'])
             and isinstance(review.get('unresolvedIssues'), list)
             and all(isinstance(item, str) and 0 < len(item) <= 4000 for item in review['unresolvedIssues']),
             'REVIEW_SCOPE_REQUIRED')
    return review


def _event_bindings(manifest, map_date):
    bindings = manifest.get('eventBindings')
    _require(isinstance(bindings, list) and bindings, 'EVENT_DATE_BINDINGS_REQUIRED')
    seen = set()
    for binding in bindings:
        _record(binding, 'EVENT_BINDING_REQUIRED')
        event_id = binding.get('eventId')
        _require(isinstance(event_id, str) and IDENTIFIER.fullmatch(event_id) and event_id not in seen, 'UNIQUE_EVENT_ID_REQUIRED')
        seen.add(event_id)
        date = _date(binding.get('eventDate'), 'EVENT_DATE_REQUIRED')
        _text(binding.get('eventDateEvidenceReference'), 'EVENT_DATE_EVIDENCE_REQUIRED')
        _require(binding.get('displayMapDate') == map_date, 'SOURCE_MAP_DATE_DISCLOSURE_REQUIRED')
        _require(map_date <= date, 'FUTURE_MAP_AS_EVENT_FRONT_FORBIDDEN')
        usage = binding.get('usage')
        _require(usage in ('SAME_DATE_SNAPSHOT', 'SOURCE_DATED_CONTEXT'), 'EVENT_MAP_USAGE_REQUIRED')
        _require(usage != 'SAME_DATE_SNAPSHOT' or date == map_date, 'EVENT_DATE_NOT_MAP_DATE')
        _require(binding.get('exactEventFrontClaimed') is False, 'EXACT_EVENT_FRONT_CLAIM_FORBIDDEN')
    return bindings


def _coordinates(value, code):
    _require(isinstance(value, list) and len(value) >= 2, code)
    for point in value:
        _require(isinstance(point, list) and len(point) == 2
                 and all(not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x) for x in point), code)
    return value


def _georef_module():
    module = importlib.import_module('georeference')
    _require(Path(module.__file__).resolve() == Path(__file__).with_name('georeference.py').resolve(), 'GEOREFERENCE_MODULE_ORIGIN_REQUIRED')
    return module


def validate_front_candidate(manifest, *, root):
    """Return lossless GeoJSON and audit status; no candidate is runtime-admitted.

    Root is an existing evidence directory. Every document, page raster, report
    and digitization reference is a bounded relative path with an exact raw SHA.
    Report originalSHA256 identifies the map RASTER, not its PDF document.
    """
    _record(manifest, 'FRONT_EVIDENCE_MANIFEST_REQUIRED')
    _require(manifest.get('schema') == SCHEMA, 'FRONT_EVIDENCE_SCHEMA_REQUIRED')
    _require(manifest.get('dataMode') in ('SOURCE_DOCUMENT', 'SYNTHETIC_TEST'), 'EXPLICIT_DATA_MODE_REQUIRED')
    source, map_record, raster_path, document_sha, raster_sha = _source(manifest, root)
    _, report_raw = _read_bound(root, manifest.get('georeferenceReport'), limit=2 * 1024**2)
    report = _record(_json(report_raw), 'GEOREFERENCE_REPORT_REQUIRED')
    _require(report.get('schema') == 'WORLD_ENGINE_GEOREFERENCE_CANDIDATE_V1'
             and report.get('mapId') == map_record['mapId'] and report.get('originalSHA256') == raster_sha,
             'MAP_GEOREFERENCE_BINDING_MISMATCH')
    expected_mode = 'SYNTHETIC' if manifest['dataMode'] == 'SYNTHETIC_TEST' else 'SOURCE_MAP'
    _require(report.get('mode') == expected_mode, 'GEOREFERENCE_DATA_MODE_MISMATCH')
    _, geo_raw = _read_bound(root, manifest.get('digitization'), limit=8 * 1024**2)
    geojson = _record(_json(geo_raw), 'DIGITIZATION_GEOJSON_REQUIRED')
    _require(geojson.get('type') == 'FeatureCollection' and isinstance(geojson.get('features'), list)
             and 0 < len(geojson['features']) <= 256 and 'crs' not in geojson, 'WGS84_FEATURE_COLLECTION_REQUIRED')
    review = _review(manifest, document_sha, raster_sha)
    bindings = _event_bindings(manifest, map_record['mapDate'])
    transformer = _georef_module().transform_verified_vertices
    features, seen, total = [], set(), 0
    for feature in geojson['features']:
        _record(feature, 'FRONT_FEATURE_REQUIRED')
        feature_id = feature.get('id')
        _require(feature.get('type') == 'Feature' and isinstance(feature_id, str)
                 and IDENTIFIER.fullmatch(feature_id) and feature_id not in seen, 'UNIQUE_FRONT_FEATURE_ID_REQUIRED')
        seen.add(feature_id)
        props, geometry = (_record(feature.get(name), 'FRONT_' + name.upper() + '_REQUIRED') for name in ('properties', 'geometry'))
        _require(props.get('sourceId') == source['sourceId'] and props.get('mapId') == map_record['mapId']
                 and props.get('mapDate') == map_record['mapDate'], 'FEATURE_SOURCE_DATE_BINDING_MISMATCH')
        _require(props.get('lineMeaning') == 'OBSERVED_FRONT_POSITION'
                 and props.get('coverage') == 'PARTIAL_OBSERVED_FRONT_ONLY'
                 and props.get('wholeFrontClaimed') is False and props.get('inferredCoordinates') is False
                 and props.get('createsTerritory') is False and props.get('enemyComplementAllowed') is False,
                 'PARTIAL_OBSERVED_LINE_ONLY_REQUIRED')
        _require(set(geometry) == {'type', 'coordinates'} and geometry.get('type') in ('LineString', 'MultiLineString'),
                 'OPEN_FRONT_LINE_GEOMETRY_REQUIRED')
        parts = [geometry['coordinates']] if geometry['type'] == 'LineString' else geometry['coordinates']
        evidence_parts = props.get('digitizedParts')
        _require(isinstance(parts, list) and parts and isinstance(evidence_parts, list)
                 and len(parts) == len(evidence_parts), 'EXACT_DIGITIZED_PART_PROVENANCE_REQUIRED')
        for part_index, (part, evidence) in enumerate(zip(parts, evidence_parts)):
            points = _coordinates(part, 'FINITE_FRONT_COORDINATES_REQUIRED')
            total += len(points)
            _require(total <= MAX_TOTAL_VERTICES, 'FRONT_VERTEX_BUDGET_EXCEEDED')
            _require(points[0] != points[-1], 'CLOSED_FRONT_TERRITORY_INFERENCE_FORBIDDEN')
            _require(all(-180 <= p[0] <= 180 and -90 <= p[1] <= 90 for p in points), 'WGS84_FRONT_COORDINATES_REQUIRED')
            _require(all(abs(a[0] - b[0]) <= 180 for a, b in zip(points, points[1:])), 'WRAPPED_FRONT_UNSUPPORTED')
            _require(any(a != b for a, b in zip(points, points[1:])), 'NONZERO_FRONT_REQUIRED')
            _record(evidence, 'DIGITIZED_PART_PROVENANCE_REQUIRED')
            segments = evidence.get('observedSegmentIndices')
            _require(type(evidence.get('partIndex')) is int and evidence['partIndex'] == part_index
                     and isinstance(segments, list) and all(type(index) is int for index in segments)
                     and segments == list(range(len(points) - 1)), 'EVERY_SEGMENT_OBSERVATION_REQUIRED')
            _text(evidence.get('sourceRegionReference'), 'SOURCE_PIXEL_REGION_REFERENCE_REQUIRED')
            width = evidence.get('sourceLineWidthPixels')
            _require(not isinstance(width, bool) and isinstance(width, (int, float)) and math.isfinite(width) and width > 0,
                     'SOURCE_LINE_WIDTH_UNCERTAINTY_REQUIRED')
            pixels = _coordinates(evidence.get('sourcePixels'), 'SOURCE_PIXEL_COORDINATES_REQUIRED')
            _require(len(pixels) == len(points), 'ONE_SOURCE_PIXEL_PER_VERTEX_REQUIRED')
            try:
                expected_points = transformer(raster_path, report, pixels)
            except ValueError as error:
                code = getattr(error, 'code', 'GEOREFERENCE_TRANSFORM_REJECTED')
                raise FrontEvidenceError(code) from None
            _require(len(expected_points) == len(points)
                     and all(max(abs(a[i] - b[i]) for i in (0, 1)) <= 1e-9 for a, b in zip(points, expected_points)),
                     'GEOMETRY_NOT_DERIVED_FROM_SOURCE_PIXELS')
            # Duplicate only the shared chunk endpoint. Every original edge is
            # retained once; disjoint parts are never connected or resampled.
            for chunk_index, start in enumerate(range(0, len(points) - 1, MAX_AREA_LINE_VERTICES - 1)):
                stop = min(len(points), start + MAX_AREA_LINE_VERTICES)
                features.append({'type': 'Feature', 'id': f'{feature_id}__p{part_index}__c{chunk_index}',
                    'geometry': {'type': 'LineString', 'coordinates': deepcopy(points[start:stop])},
                    'properties': {'sourceFeatureId': feature_id, 'sourcePartIndex': part_index,
                        'sourceVertexRangeInclusive': [start, stop - 1], 'sourcePixelVertices': deepcopy(pixels[start:stop]),
                        'sourceId': source['sourceId'], 'mapId': map_record['mapId'], 'mapDate': map_record['mapDate'],
                        'originalDocumentSHA256': document_sha, 'mapRasterSHA256': raster_sha,
                        'georeferenceReportSHA256': manifest['georeferenceReport']['sha256'],
                        'digitizationSHA256': manifest['digitization']['sha256'],
                        'sourceRegionReference': evidence['sourceRegionReference'], 'sourceLineWidthPixels': width,
                        'lineMeaning': 'OBSERVED_FRONT_POSITION', 'coverage': 'PARTIAL_OBSERVED_FRONT_ONLY',
                        'coordinateInterpolation': False, 'simplificationApplied': False,
                        'territoryCreated': False, 'historicalAccuracyVerified': False,
                        'reviewStatus': 'TECHNICAL_CANDIDATE_REVIEW_REQUIRED'}})
    _require(set(review['checkedFeatureIds']) == seen and len(review['checkedFeatureIds']) == len(seen), 'REVIEW_FEATURE_SCOPE_MISMATCH')
    return {'schema': OUTPUT_SCHEMA, 'status': 'TECHNICAL_CANDIDATE_REVIEW_REQUIRED',
            'dataMode': manifest['dataMode'], 'runtimeAdmission': 'NOT_ADMITTED',
            'historicalTruthVerified': False, 'humanIdentityOrCertificationVerified': False,
            'licenseHumanReviewRequired': manifest['dataMode'] != 'SYNTHETIC_TEST',
            'sourceRasterDerivationReproduced': source['original']['sha256'] == map_record['raster']['sha256'],
            'originalDocumentSHA256': document_sha, 'mapRasterSHA256': raster_sha,
            'georeferenceReportSHA256': manifest['georeferenceReport']['sha256'],
            'digitizationSHA256': manifest['digitization']['sha256'],
            'mapDate': map_record['mapDate'], 'eventBindings': deepcopy(bindings),
            'inputFeatureCount': len(seen), 'inputVertexCount': total, 'outputPartCount': len(features),
            'coordinatesPreserved': True, 'unobservedGapsBridged': False,
            'territoryCreated': False, 'enemyComplementInferred': False,
            'runtimeConnected': False, 'gpuExecuted': False,
            'geojson': {'type': 'FeatureCollection', 'features': features},
            'reviewRecord': deepcopy(review)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        manifest_path = args.manifest.absolute()
        _require(not any(item.is_symlink() for item in [manifest_path, *manifest_path.parents]), 'SOURCE_SYMLINK_FORBIDDEN')
        descriptor = os.open(manifest_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            _require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'BOUNDED_MANIFEST_REQUIRED')
            raw = stream.read(2 * 1024**2 + 1)
        _require(0 < len(raw) <= 2 * 1024**2, 'BOUNDED_MANIFEST_REQUIRED')
        result = validate_front_candidate(_json(raw), root=args.root)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, sort_keys=True))
        return 0
    except (FrontEvidenceError, OSError) as error:
        code = getattr(error, 'code', 'EVIDENCE_FILE_UNAVAILABLE')
        print(json.dumps({'status': 'BLOCKED', 'errorCode': code, 'runtimeAdmission': 'NOT_ADMITTED', 'gpuExecuted': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
