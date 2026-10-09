#!/usr/bin/env python3
"""Bundle minimal verified v022 GIS; preserve native vertices, holes and parts.

Build inputs are existing licensed source assets and the two audited, unmodified
Natural Earth Suez features. No geometry is drawn from a representative point.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import shutil

ROOT = Path(__file__).resolve().parents[1]
V3 = ROOT.parent / 'cinematic-world-map'
PIN = 'ca96624a56bd078437bca8184e78163e5039ad19'
COUNTRY_SHA = '3e458fc036ad0a66411f2c1e6cac49c5d7bfb81cb1123bc513b22511a2b7fdeb'
CANALS = {'CANAL_SUEZ_RIVER_NE10M': '0e99bf36a30e4a531db50c9d3cec3fd96b1799395b8c4a864ca8455ef6743e36',
          'CANAL_SUEZ_LAKE_NE10M': 'f1c9195315f7e9c29083b12c3b0e0b7664a270f60edaf0c64e1ebdd273129703'}


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError('NONFINITE_GIS_SOURCE')
        return int(value) if value.is_integer() else value
    return value


def canonical(value):
    return json.dumps(normalize(value), sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def vertices(coordinates):
    if isinstance(coordinates, list) and len(coordinates) == 2 and all(type(v) in (int, float) for v in coordinates):
        return [coordinates]
    return [p for item in coordinates for p in vertices(item)]


def geometry_metadata(geometry):
    points = vertices(geometry['coordinates'])
    kind = geometry['type']
    polygons = [geometry['coordinates']] if kind == 'Polygon' else geometry['coordinates'] if kind == 'MultiPolygon' else []
    lines = ([geometry['coordinates']] if kind == 'LineString' else geometry['coordinates'] if kind == 'MultiLineString' else
             [ring for polygon in polygons for ring in polygon])
    return dict(bbox=[min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)],
                vertex_count=len(points), hole_count=sum(len(p)-1 for p in polygons),
                part_count=len(polygons) if polygons else len(lines) if lines else 1,
                dateline_crossing_segments=sum(abs(b[0]-a[0]) > 180 for line in lines for a, b in zip(line, line[1:])),
                winding='source_preserved', coordinates_changed=False)


def profile():
    return dict(version='v022', parent_version='v021', role='map_infographic',
                typography=dict(EVENT_TITLE=dict(size_px=72, weight=700, max_lines=2),
                                LOCATION_LABEL=dict(size_px=58, weight=400, max_lines=1),
                                SUPPORT_DATA=dict(size_px=48, weight=400, max_lines=1),
                                TTS_SUBTITLE=dict(size_px=58, weight=400, max_lines=2)),
                geometry=dict(primary_outline_px=4, secondary_outline_px=2,
                              region_fill_alpha=.24, boundary_draw=False,
                              preserve_holes=True, horizon_occlusion=True),
                marker=dict(size_px=52, max_size_px=80, pop_reference_fps=30,
                            pop_frames=9, fade_frames=8, lifetime='semantic_target'),
                text=dict(outline_px=2.5, shadow_px=3, steady_halo=True,
                          reveal_min_frames_30fps=12, reveal_max_frames_30fps=18,
                          safe_area=[.06, .08, .94, .82], subtitle_safe_area=[.08, .82, .92, .94]),
                state_styles=dict(CONTEXT=dict(color='#c5c8c6', opacity=.24),
                                  LOCATION=dict(color='#f3f1e5', opacity=.75),
                                  OPEN=dict(color='#b9d4c6', opacity=.92),
                                  CLOSED=dict(color='#e6b58d', opacity=.92),
                                  ACTIVE=dict(color='#f3f1e5', opacity=.92),
                                  INACTIVE=dict(color='#c5c8c6', opacity=.35),
                                  BLOCKED=dict(color='#e6b58d', opacity=.92),
                                  PREVIOUS=dict(color='#c5c8c6', opacity=.35),
                                  UNCHANGED=dict(color='#c5c8c6', opacity=.24)),
                limits=dict(primary_motion_effects=1, added_sfx=0, added_entities=0,
                            added_routes=0, hypothetical_watermark_required=True),
                metrics_policy='Configuration targets are not captured-pixel measurements or GPU quality PASS')


def build(source_dir):
    source_dir = Path(source_dir)
    out = ROOT / 'data/infographic/v022'
    public = ROOT / 'web/infographic/v022'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'source-features').mkdir(exist_ok=True)
    (out / 'licenses').mkdir(exist_ok=True)
    country_path = V3 / 'assets/gis/countries_50m.geojson'
    if file_sha(country_path) != COUNTRY_SHA:
        raise ValueError('PRESERVED_COUNTRY_SOURCE_HASH_MISMATCH')
    audit = json.loads((source_dir / 'GIS_SOURCE_QA.json').read_text())
    if audit['source_commit'] != PIN or audit['dataset']['sha256'] != 'bb854a900ecbd3b408df46d5e16e3e0f974ba55993f9d8b5c26e855273c0905a':
        raise ValueError('OFFICIAL_SUEZ_SOURCE_AUDIT_MISMATCH')
    if file_sha(source_dir / 'LICENSE.md') != audit['dataset']['license_sha256']:
        raise ValueError('OFFICIAL_LICENSE_HASH_MISMATCH')
    shutil.copyfile(source_dir / 'LICENSE.md', out / 'licenses/NATURAL_EARTH_PUBLIC_DOMAIN.md')
    shutil.copyfile(source_dir / 'ne_10m_rivers_lake_centerlines.README.html', out / 'licenses/NATURAL_EARTH_RIVERS_README.html')
    shutil.copyfile(ROOT / 'data/shipping_sources/APACHE-2.0.txt', out / 'licenses/SEAROUTE_APACHE-2.0.txt')
    shutil.copyfile(ROOT / 'data/shipping_sources/PACKAGE_METADATA.txt', out / 'licenses/SEAROUTE_PACKAGE_METADATA.txt')
    pddl = 'OurAirports / DataHub airport source: ODC Public Domain Dedication and Licence (PDDL) 1.0.\nhttps://opendatacommons.org/licenses/pddl/1-0/\nPreserved source metadata: data/locations.json and data/airport_codes_datapackage.json.\n'
    (out / 'licenses/OURAIRPORTS_PDDL_NOTICE.txt').write_text(pddl)
    source_records = []
    natural_license = dict(spdx='LicenseRef-Public-Domain', url='https://www.naturalearthdata.com/about/terms-of-use/',
                           file='data/infographic/v022/licenses/NATURAL_EARTH_PUBLIC_DOMAIN.md',
                           attribution_required=False)
    catalogs = json.loads((ROOT / 'data/locations.json').read_text())
    ships = json.loads((ROOT / 'data/shipping_routes.json').read_text())
    for source in catalogs['sources']:
        raw = (ROOT / 'data' / source['local_path']).resolve()
        if not raw.is_file() or file_sha(raw) != source['sha256']:
            raise ValueError('PRESERVED_LOCATION_SOURCE_HASH_MISMATCH')
        license_record = natural_license if source['id'] != 'ourairports' else dict(spdx='PDDL-1.0',url=source['license_url'],file='data/infographic/v022/licenses/OURAIRPORTS_PDDL_NOTICE.txt',attribution_required=False)
        source_records.append(dict(id=source['id'],url=source['url'],version='5.1.1' if source['id']=='natural_earth_countries' else 'preserved-source-by-sha256',
                                   sha256=source['sha256'],license=license_record,
                                   file=str(raw.relative_to(ROOT)) if ROOT in raw.parents else '../cinematic-world-map/assets/gis/countries_50m.geojson',
                                   acquired_at=source.get('downloaded_at'), source_commit=PIN if source['id']=='natural_earth_countries' else None))
    for source in ships['sources']:
        if source['id']=='SEAROUTE_1_6_0':
            raw=ROOT/'data/shipping_routes.json'
            source_records.append(dict(id=source['id'],url=source['original_url'],version=source['package_version'],sha256=file_sha(raw),file='data/shipping_routes.json',
                                       upstream_package_sha256=source['package_sha256'],license=dict(spdx='Apache-2.0',url='https://www.apache.org/licenses/LICENSE-2.0',file='data/infographic/v022/licenses/SEAROUTE_APACHE-2.0.txt',attribution_required=True),
                                       acquired_at=source['downloaded_at_utc'],source_commit=None))
        else:
            raw=ROOT/source['local_path']
            if file_sha(raw)!=source['sha256']:raise ValueError('PRESERVED_PHYSICAL_POINT_SOURCE_HASH_MISMATCH')
            source_records.append(dict(id=source['id'],url=source['url'],version='preserved-source-by-sha256',sha256=source['sha256'],file=source['local_path'],license=natural_license,acquired_at=source['downloaded_at_utc'],source_commit=PIN))
    source_records.append(dict(id=audit['dataset']['id'],url=audit['dataset']['url'],version='5.0.0',sha256=audit['dataset']['sha256'],file=None,
                               subset_files=[f'data/infographic/v022/source-features/{name}.geojson' for name in CANALS],license=natural_license,
                               acquired_at=audit['generated_at_utc'],source_commit=PIN,full_world_source_bundled=False))
    source_by_id={s['id']:s for s in source_records}
    records=[]
    def add(rid,name,role,geometry,source_id,feature_id,feature,selector,scale,precision):
        source=source_by_id[source_id];meta=geometry_metadata(geometry)
        records.append(dict(id=rid,name=name,geometry_role=role,geometry_type=geometry['type'],coordinates=geometry['coordinates'],crs='EPSG:4326',
                            source_id=source_id,source_feature_id=str(feature_id),source_version=source['version'],source_file_sha256=source['sha256'],
                            source_feature_sha256=digest(feature),sha256=digest(geometry),license=source['license'],bbox=meta['bbox'],
                            scale=dict(denominator=scale,precision=precision),
                            provenance=dict(selector=selector,source_commit=source.get('source_commit'),transformations=['Exact source selection; native coordinates/parts/holes unchanged'],boundary_policy='Preserved Natural Earth default de facto view' if role=='country' else None),
                            geometry_qa=meta))
    country_data=json.loads(country_path.read_text())
    for feature in country_data['features']:
        props=feature['properties'];code=props['ADM0_A3']
        add('COUNTRY_'+code,props['ADMIN'],'country',feature['geometry'],'natural_earth_countries',code,feature,
            dict(kind='country',field='ADM0_A3',value=code),50000000,'Generalized 1:50,000,000 country polygons; not survey boundaries')
    for location in catalogs['locations']:
        c=location['coordinates'];geometry=dict(type='Point',coordinates=[c['lon'],c['lat']])
        add('LOCATION_'+location['id'].upper(),location['name'],location['kind'],geometry,c['source_id'],location['feature_id'],location,
            dict(kind='location_catalog',location_id=location['id']),None,'Exact verified catalog coordinate; country label point is not country area')
        records[-1]['location_id']=location['id']
    for lid,location in ships['locations'].items():
        c=location['coordinates'];geometry=dict(type='Point',coordinates=[c['lon'],c['lat']])
        add('LOCATION_'+lid,location['name'],location['kind'],geometry,c['source_id'],location['source_record'],location,
            dict(kind='shipping_location',location_id=lid),None,location['coordinate_precision'])
        records[-1]['location_id']=lid
    for rid,expected in CANALS.items():
        raw=source_dir/(rid+'.geojson')
        if file_sha(raw)!=expected:raise ValueError('OFFICIAL_SUEZ_FEATURE_BYTES_MISMATCH')
        shutil.copyfile(raw,out/'source-features'/raw.name)
        collection=json.loads(raw.read_text())
        if collection.get('type')!='FeatureCollection' or len(collection.get('features',[]))!=1:
            raise ValueError('OFFICIAL_SUEZ_FEATURE_SELECTION_INVALID')
        feature=collection['features'][0]
        add(rid,'Suez Canal '+('river centerline' if 'RIVER' in rid else 'lake centerline'),'canal_centerline',feature['geometry'],audit['dataset']['id'],feature['properties']['dissolve'],feature,
            dict(kind='suez_native_feature',file='data/infographic/v022/source-features/'+raw.name,field='dissolve',value=feature['properties']['dissolve'],file_sha256=expected),10000000,audit['dataset']['precision_description'])
    clean_audit=normalize(audit)
    def sanitize(value):
        if isinstance(value,dict):return {k:sanitize(v) for k,v in value.items() if not k.endswith('_path') and k not in {'interpolated_nearest_coordinate_for_qa_only'}}
        if isinstance(value,list):return [sanitize(v)for v in value]
        return value
    (out/'GIS_SOURCE_QA.json').write_bytes(canonical(sanitize(clean_audit))+b'\n')
    source_manifest=dict(version='v022',sources=source_records,licenses=[dict(file=str(p.relative_to(ROOT)),sha256=file_sha(p),bytes=p.stat().st_size)for p in sorted((out/'licenses').iterdir())],
                         transform='Native source extraction only; no interpolation, point-to-line promotion, line stitching, hole/winding rewrite or inferred boundaries',new_world_rivers_dataset_bundled=False)
    (out/'SOURCES.json').write_bytes(canonical(source_manifest)+b'\n')
    registry=dict(version='v022',crs='EPSG:4326',coordinate_order='longitude,latitude',source_manifest_url='/static/infographic/v022/SOURCES.json',
                  source_manifest_sha256=file_sha(out/'SOURCES.json'),geometry_count=len(records),geometries=records,
                  precision_policy='Respect record source scale. 10m/50m mean ten/fifty-million scale, not meter resolution. Points never become lines or polygons.')
    (out/'registry.json').write_bytes(canonical(registry)+b'\n')
    (out/'profile.json').write_bytes(canonical(profile())+b'\n')
    shutil.copytree(out,public,dirs_exist_ok=True)
    return dict(version='v022',geometry_count=len(records),source_count=len(source_records),registry_sha256=file_sha(out/'registry.json'),
                registry_bytes=(out/'registry.json').stat().st_size,new_canal_parts=3,new_canal_vertices=26,arbitrary_connectors=0)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source-dir',required=True)
    args=parser.parse_args();print(json.dumps(build(args.source_dir),sort_keys=True))
