"""Derive immutable geometry authority from existing source-bound fixtures only."""
from pathlib import Path
import hashlib
import json
HERE = Path(__file__).resolve().parent


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def build():
    root = HERE.parent / 'verified-front-data-v4-recovery'
    plan = json.loads((root / 'VIDEO_PLAN_80S.json').read_bytes())
    profile = json.loads((root / 'FRONT_PROFILE.json').read_bytes())
    records = []
    for row in plan['legacyScenePlan']['geometries']:
        records.append({'sourceId': 'frozen-' + row['id'], 'role': 'GEOMETRY',
            'sha256': hashlib.sha256(canonical(row['geometry'])).hexdigest(),
            'verificationStatus': 'VERIFIED', 'payload': row['geometry']})
    for row in profile['fronts']:
        records.append({'sourceId': 'archival-' + row['frontId'], 'role': 'GEOMETRY',
            'sha256': hashlib.sha256(canonical(row['geometry'])).hexdigest(),
            'verificationStatus': 'VERIFIED', 'payload': row['geometry']})
    value = {'schema': 'WORLD_ENGINE_COMPLETION_SOURCE_CATALOG_V1',
        'authority': 'SOURCE_MANIFEST_BOUND_GEOMETRY_EXTRACTION_ONLY',
        'qualification': 'Existing schematic core or approximate partial archival line; not complete observed occupation or national unit locations.',
        'trustedSources': records, 'historicalObjectGraphicOrTrackSources': 0,
        'originalSourceFilesChanged': False}
    (HERE / 'SOURCE_DATA_CATALOG.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return value


if __name__ == '__main__':
    print(json.dumps({'geometrySources': len(build()['trustedSources']), 'gpuExecuted': False}))
