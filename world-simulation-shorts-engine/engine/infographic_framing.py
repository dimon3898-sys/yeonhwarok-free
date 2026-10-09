"""Optional v022 native-geometry framing over the certified spherical solver.

Point records remain points. Local framing projects the complete supplied GIS
extent, including multipart boundaries and holes, without manufacturing a
circle around a representative coordinate. Legacy camera plans never opt in.
"""
from copy import deepcopy
import hashlib
import math

from . import adaptive_wide as rig
from . import visual_quality

VERSION = 'NATIVE_GEOMETRY_FRAMING_v022'
PROFILE = 'GEOMETRY_LOCAL_CLOSE_v022'


def _number(value, code):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(code)
    return float(value)


def _parts(record):
    from .infographic_contract import validate_geometry
    validate_geometry(record)
    kind, coords = record['geometry_type'], record['coordinates']
    if kind == 'Point':
        raise ValueError('LOCAL_CLOSE_REQUIRES_NATIVE_EXTENT')
    if kind == 'LineString':
        return [coords]
    if kind in {'MultiLineString', 'Polygon'}:
        return coords
    if kind == 'MultiPolygon':
        return [ring for polygon in coords for ring in polygon]
    raise ValueError('LOCAL_CLOSE_GEOMETRY_UNSUPPORTED')


def geometry_samples(records, *, max_step_degrees=.25):
    """Sample native edges on the inherited sphere; no new geographic feature."""
    step = _number(max_step_degrees, 'LOCAL_CLOSE_SAMPLE_POLICY_INVALID')
    if not 0 < step <= 5 or not isinstance(records, list) or not records:
        raise ValueError('LOCAL_CLOSE_GEOMETRY_REQUIRED')
    result = []
    for record in records:
        for part in _parts(record):
            for a, b in zip(part, part[1:]):
                av, bv = rig._vector(dict(lon=a[0], lat=a[1])), rig._vector(dict(lon=b[0], lat=b[1]))
                angle = math.degrees(math.acos(max(-1., min(1., rig._dot(av, bv)))))
                count = max(2, math.ceil(angle/step)+1)
                result.extend(rig._geographic(v) for v in rig._arc(av, bv, count))
    if not result or len(result) > 200000:
        raise ValueError('LOCAL_CLOSE_GEOMETRY_COMPLEXITY_INVALID')
    return result


def reserved_safe_area(safe_area=None, *, title_bottom=.18, subtitle_top=.80):
    """Reserve actual overlay bands, rather than pretending text has no area."""
    area = rig._safe_area(safe_area)
    top = _number(title_bottom, 'LOCAL_CLOSE_TEXT_RESERVATION_INVALID')
    bottom = _number(subtitle_top, 'LOCAL_CLOSE_TEXT_RESERVATION_INVALID')
    if not 0 <= top < .5 < bottom <= 1:
        raise ValueError('LOCAL_CLOSE_TEXT_RESERVATION_INVALID')
    area['y_min'] = max(area['y_min'], top)
    area['y_max'] = min(area['y_max'], bottom)
    return rig._safe_area(area)


def select_regional_lod(records, *, camera=None, width=1080, height=1920,
                        allow_partial=False):
    """Choose only existing, checked native v018 pairs for the actual targets.

Coverage is explicitly geometry coverage, not a claim that every peripheral
viewport pixel has local data. Uncovered targets keep the global texture and
receive a limitation; no TIFF conversion, invented detail or new upload occurs.
"""
    if type(allow_partial) is not bool or type(width) is not int or type(height) is not int or min(width, height) <= 0:
        raise ValueError('REGIONAL_LOD_SELECTION_INVALID')
    from .infographic_contract import validate_geometry, _vertices, load_registry, canonical_sha
    known={r['id']:r for r in load_registry()['geometries']}
    points = []
    for record in records:
        validate_geometry(record)
        if record.get('id')not in known or canonical_sha(record)!=canonical_sha(known[record['id']]):
            raise ValueError('REGIONAL_LOD_SOURCE_BINDING_INVALID')
        points.extend(_vertices(record['coordinates']))
    if not points:
        raise ValueError('REGIONAL_LOD_GEOMETRY_REQUIRED')
    assets = visual_quality.asset_records()
    grouped = {}
    for asset in assets:
        grouped.setdefault(asset['region_id'], []).append(asset)
    selected = []
    covered = set()
    for region, pair in sorted(grouped.items()):
        west, south, east, north = pair[0]['bounds']
        contained = {i for i, point in enumerate(points) if west <= point[0] <= east and south <= point[1] <= north}
        if contained and (allow_partial or len(contained) == len(points)):
            selected.append(dict(region_id=region, bounds=deepcopy(pair[0]['bounds']),
                textures=[{k:deepcopy(a[k]) for k in ('file','url','sha256','role','width','height','bytes')} for a in pair],
                native_source_resolution=[21600,10800], texels_per_degree=60.,
                geometry_vertices_covered=len(contained), coverage='TARGET_GEOMETRY'))
            covered.update(contained)
    warnings = []
    if len(covered) != len(points):
        warnings.append(dict(code='REGIONAL_LOD_UNAVAILABLE',
                             message='Native regional source does not cover every target; global source retained'))
    density = None
    if camera is not None and selected:
        # Project a small geographic increment with the original projector.
        # The result is planning density, never a measured GPU quality verdict.
        center = dict(lon=camera['lon'], lat=camera['lat'])
        nearby = dict(lon=min(180., center['lon']+.01), lat=center['lat'])
        a = rig.project_location(camera, center, aspect=width/height)
        b = rig.project_location(camera, nearby, aspect=width/height)
        span = abs(nearby['lon']-center['lon'])
        if span and a['x'] is not None and b['x'] is not None:
            density = abs(b['x']-a['x'])*width/(60.*span)
            if density > 2.5:
                warnings.append(dict(code='SOURCE_TEXEL_MAGNIFICATION_LIMIT',
                                     screen_pixels_per_native_texel=density))
    from . import event_quality
    return dict(version=VERSION, source_manifest_sha256=hashlib.sha256(visual_quality.MANIFEST.read_bytes()).hexdigest(),
        visual_quality_contract=visual_quality._contract(),event_quality_contract=event_quality._contract(),
        selected_regions=selected, coverage_complete=len(covered)==len(points),
        new_textures=0, selected_texture_count=sum(len(r['textures']) for r in selected),
        selected_disk_bytes=sum(t['bytes'] for r in selected for t in r['textures']),
        uncompressed_texture_bytes=sum(t['width']*t['height']*(3 if t['role']=='regional_day_relief' else 1) for r in selected for t in r['textures']),
        screen_pixels_per_native_texel=density, warnings=warnings,
        physical_gpu='NOT_RUN', rendered_quality='NOT_RUN')


def fit_native_geometry(records, *, enabled=True, baseline_camera=None, profile=PROFILE,
                        registry=None, fov=64, aspect=9/16, safe_area=None,
                        title_bottom=.18, subtitle_top=.80, minimum_height=.08):
    """Fit native line/polygon extent into the exact existing portrait rig."""
    if type(enabled) is not bool:
        raise ValueError('LOCAL_CLOSE_ENABLE_INVALID')
    if not enabled:
        return dict(version=VERSION, enabled=False, camera=deepcopy(baseline_camera),
                    unchanged=True, physical_gpu='NOT_RUN')
    if profile != PROFILE:
        raise ValueError('LOCAL_CLOSE_PROFILE_UNSUPPORTED')
    from .infographic_contract import validate_registry, canonical_sha, load_registry
    registry=registry if registry is not None else load_registry()
    if not validate_registry(registry)['passed']:
        raise ValueError('LOCAL_CLOSE_REGISTRY_INVALID')
    known = {r['id']:r for r in registry['geometries']}
    if any(r.get('id') not in known or canonical_sha(r)!=canonical_sha(known[r['id']]) for r in records):
        raise ValueError('LOCAL_CLOSE_SOURCE_BINDING_INVALID')
    fov=_number(fov,'LOCAL_CLOSE_FOV_INVALID');aspect=_number(aspect,'LOCAL_CLOSE_ASPECT_INVALID')
    if not 20<=fov<=80 or aspect<=0:
        raise ValueError('LOCAL_CLOSE_CAMERA_INVALID')
    area = reserved_safe_area(safe_area, title_bottom=title_bottom, subtitle_top=subtitle_top)
    samples = geometry_samples(records)
    vectors = [rig._vector(p) for p in samples]
    focus = rig._geographic(tuple(sum(p[i] for p in vectors) for i in range(3)))
    # Reuse the exact inherited two-location allocator as the starting bound.
    furthest = max(samples, key=lambda p:math.acos(max(-1.,min(1.,rig._dot(rig._vector(focus),rig._vector(p))))))
    seed = rig.adaptive_wide(focus, furthest, fov=fov, aspect=aspect,
                             safe_area=area, minimum_height=minimum_height)
    camera = {**seed['camera'], **focus, 'target_lon':focus['lon'], 'target_lat':focus['lat']}
    def projects(height):
        candidate = {**camera,'height':height}
        return [rig.project_location(candidate,p,aspect=aspect,safe_area=area) for p in samples]
    def fits(height):
        return all(p['in_safe_area'] for p in projects(height))
    low = _number(minimum_height,'LOCAL_CLOSE_MINIMUM_INVALID')
    if not .08 <= low <= 20:
        raise ValueError('LOCAL_CLOSE_MINIMUM_INVALID')
    if not fits(low):
        high = max(low*2,seed['camera']['height'])
        while not fits(high):
            low,high=high,min(20.,high*2)
            if low>=20:
                raise ValueError('LOCAL_CLOSE_GEOMETRY_NOT_IN_SINGLE_HEMISPHERE')
        for _ in range(56):
            midpoint=(low+high)/2
            if fits(midpoint):high=midpoint
            else:low=midpoint
        camera['height']=high+1e-8
    else:camera['height']=low
    screen=projects(camera['height'])
    return dict(version=VERSION,profile=PROFILE,enabled=True,camera=camera,
        geometry_refs=[r['id']for r in records],native_geometry_sha256s={r['id']:r['sha256']for r in records},
        method='INHERITED_SPHERICAL_SOLVER_COMPLETE_NATIVE_EXTENT',safe_area=area,
        screen_bounds={key:operation(p[axis]for p in screen)for key,axis,operation in [('x_min','x',min),('x_max','x',max),('y_min','y',min),('y_max','y',max)]},
        projected_sample_count=len(screen),all_samples_in_safe_area=all(p['in_safe_area']for p in screen),
        holes_preserved=True,native_parts_preserved=True,point_promoted_to_polygon=False,
        source_precision=[dict(geometry_ref=r['id'],source_scale=deepcopy(r.get('scale')),geometry_role=r.get('geometry_role'))for r in records],
        regional_lod=select_regional_lod(records,camera=camera),physical_gpu='NOT_RUN')
