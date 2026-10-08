"""Nearest portrait framing of two sourced locations for the v017 camera test.

The geometry matches ``installSingleCamera``: unit Earth, geographic north up,
radial camera position, and lookAt(radial_normal * .99). A type is assigned only
after solving the framing; a distance category never chooses camera distance.
"""
import math
from copy import deepcopy

EARTH_RADIUS_KM = 6371.0088
DEFAULT_SAFE_AREA = {'x_min': .13, 'x_max': .87, 'y_min': .12, 'y_max': .82}


class AdaptiveFramingError(ValueError):
    code = 'ADAPTIVE_WIDE_FRAMING_INVALID'


def _coordinate(value):
    if not isinstance(value, dict):
        raise AdaptiveFramingError('A sourced geographic coordinate is required')
    point = value.get('coordinates', value)
    if not isinstance(point, dict):
        raise AdaptiveFramingError('A sourced geographic coordinate is required')
    try:
        lon, lat = float(point['lon']), float(point['lat'])
    except (KeyError, TypeError, ValueError) as exc:
        raise AdaptiveFramingError('Invalid geographic coordinate') from exc
    if not math.isfinite(lon) or not math.isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise AdaptiveFramingError('Invalid geographic coordinate')
    return {'lon': lon, 'lat': lat}


def _dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def _unit(v):
    size = math.sqrt(_dot(v, v))
    if size < 1e-12:
        raise AdaptiveFramingError('Antipodal locations cannot share a visible Earth hemisphere')
    return tuple(x / size for x in v)


def _vector(location):
    p = _coordinate(location)
    lon, lat = math.radians(p['lon']), math.radians(p['lat'])
    return (math.cos(lat)*math.cos(lon), math.sin(lat), -math.cos(lat)*math.sin(lon))


def _geographic(vector):
    n = _unit(vector)
    return {'lon': math.degrees(math.atan2(-n[2], n[0])), 'lat': math.degrees(math.asin(max(-1., min(1., n[1]))))}


def _safe_area(value):
    area = deepcopy(DEFAULT_SAFE_AREA if value is None else value)
    keys = ('x_min', 'x_max', 'y_min', 'y_max')
    if not isinstance(area, dict) or any(k not in area for k in keys):
        raise AdaptiveFramingError('Invalid screen safe area')
    try:
        area = {k: float(area[k]) for k in keys}
    except (TypeError, ValueError) as exc:
        raise AdaptiveFramingError('Invalid screen safe area') from exc
    if not all(math.isfinite(v) for v in area.values()) or not (0 < area['x_min'] < .5 < area['x_max'] < 1 and 0 < area['y_min'] < .5 < area['y_max'] < 1):
        raise AdaptiveFramingError('Invalid screen safe area')
    return area


def _view(camera, aspect):
    p = _coordinate(camera)
    n = _vector(p)
    lon, lat = math.radians(p['lon']), math.radians(p['lat'])
    # The right vector is forward x north-up, exactly THREE.lookAt.
    right = (-math.sin(lon), 0., -math.cos(lon))
    up = (-math.sin(lat)*math.cos(lon), math.cos(lat), math.sin(lat)*math.sin(lon))
    distance = 1 + float(camera['height'])
    fov = float(camera['fov'])
    if not math.isfinite(distance) or distance <= 1 or not math.isfinite(fov) or not 0 < fov < 180 or not math.isfinite(aspect) or aspect <= 0:
        raise AdaptiveFramingError('Invalid radial camera')
    position = tuple(distance*x for x in n)
    return n, right, up, position, math.tan(math.radians(fov)/2)


def project_location(camera, location, *, aspect=9/16, safe_area=None):
    """Project a real unit-Earth location with actual camera occlusion checks."""
    area = _safe_area(safe_area)
    n, right, up, position, tangent = _view(camera, float(aspect))
    point = _vector(location)
    offset = tuple(x-y for x, y in zip(point, position))
    depth = -_dot(offset, n)
    # dot(point, position) > 1 is the true unit-sphere horizon test.
    visible = depth > 0 and _dot(point, position) > 1 + 1e-9
    if depth <= 0:
        return {'x': None, 'y': None, 'visible': False, 'in_safe_area': False}
    x = .5 + .5*_dot(offset, right)/(depth*tangent*aspect)
    y = .5 - .5*_dot(offset, up)/(depth*tangent)
    inside = visible and area['x_min']-1e-10 <= x <= area['x_max']+1e-10 and area['y_min']-1e-10 <= y <= area['y_max']+1e-10
    return {'x': x, 'y': y, 'visible': visible, 'in_safe_area': inside}


def _arc(a, b, count=33):
    angle = math.acos(max(-1., min(1., _dot(a, b))))
    if angle < 1e-10:
        return [a]
    sine = math.sin(angle)
    if abs(sine) < 1e-12:
        raise AdaptiveFramingError('Antipodal locations cannot share a visible Earth hemisphere')
    return [tuple((math.sin((1-t)*angle)*x + math.sin(t*angle)*y)/sine for x, y in zip(a, b)) for t in (i/(count-1) for i in range(count))]


def adaptive_wide(current, next_location, *, fov=64, aspect=9/16, safe_area=None, minimum_height=.2):
    """Return the nearest north-up midpoint framing plus auditable screen data.

    Camera distance is searched continuously against exact projection and sphere
    visibility of both locations and their connecting great-circle span. Safe
    margins leave space for existing labels. Longitude wrapping and polar pairs
    use spherical vectors rather than arithmetic latitude/longitude midpoints.
    """
    area = _safe_area(safe_area)
    try:
        fov, aspect, minimum_height = float(fov), float(aspect), float(minimum_height)
    except (TypeError, ValueError) as exc:
        raise AdaptiveFramingError('Invalid framing parameters') from exc
    if not math.isfinite(minimum_height) or not .08 <= minimum_height <= 20:
        raise AdaptiveFramingError('Invalid minimum camera height')
    a, b = _vector(current), _vector(next_location)
    target = _geographic(tuple(x+y for x, y in zip(a, b)))
    camera = {**target, 'height': minimum_height, 'fov': fov, 'yaw': 0., 'tilt': 0., 'bank': 0.}
    _view(camera, aspect)
    samples = [_geographic(p) for p in _arc(a, b)]

    def fits(height):
        candidate = {**camera, 'height': height}
        return all(project_location(candidate, p, aspect=aspect, safe_area=area)['in_safe_area'] for p in samples)

    if not fits(minimum_height):
        low, high = minimum_height, max(.4, minimum_height*2)
        while not fits(high):
            low, high = high, min(20., high*2)
            if low >= 20:
                raise AdaptiveFramingError('The two locations cannot fit a readable single camera hemisphere')
        for _ in range(64):
            mid = (low+high)/2
            if fits(mid):
                high = mid
            else:
                low = mid
        # Stay just inside the bounds, avoiding floating point disagreements at
        # the exact viewport edge between Python and Chromium/THREE.
        camera['height'] = high + 1e-8

    angle = math.acos(max(-1., min(1., _dot(a, b))))
    distance = 1 + camera['height']
    tangent = math.tan(math.radians(fov)/2)
    # The actual perspective silhouette, not an orthographic size estimate.
    earth_width = 1/(math.sqrt(distance*distance-1)*tangent*aspect)
    # Assign a reporting type after framing. A whole Earth disk comfortably
    # inside the usable width is a world overview. Otherwise local angular span
    # plus a cropped Earth footprint identifies a regional framing.
    if earth_width <= area['x_max']-area['x_min']:
        wide_type = 'WORLD_WIDE'
    elif angle <= math.radians(30) and camera['height'] <= .8:
        wide_type = 'REGIONAL_WIDE'
    else:
        wide_type = 'CONTINENT_WIDE'
    screen = [project_location(camera, p, aspect=aspect, safe_area=area) for p in samples]
    return {
        'wide_type': wide_type,
        'camera': camera,
        'target': deepcopy(target),
        'camera_distance': distance,
        'distance_km': EARTH_RADIUS_KM*angle,
        'angular_span_degrees': math.degrees(angle),
        'current_screen': project_location(camera, current, aspect=aspect, safe_area=area),
        'next_screen': project_location(camera, next_location, aspect=aspect, safe_area=area),
        'safe_area': area,
        'framing': {
            'method': 'SPHERICAL_MIDPOINT_EXACT_PORTRAIT_SAFE_AREA_MINIMUM_DISTANCE',
            'aspect': aspect,
            'sample_count': len(samples),
            'earth_horizontal_occupancy': earth_width,
            'screen_bounds': {'x_min': min(p['x'] for p in screen), 'x_max': max(p['x'] for p in screen), 'y_min': min(p['y'] for p in screen), 'y_max': max(p['y'] for p in screen)},
            'all_samples_in_safe_area': all(p['in_safe_area'] for p in screen),
        },
    }
