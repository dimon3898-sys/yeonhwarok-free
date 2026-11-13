"""Compile source-bounded geometric display interpolation, never historical routes.

Requires Shapely 2.1.2. Coordinates are only scaled for the display-distance
calculation; authoritative endpoints and the map projection are unchanged.
Connected differences grow from the shared source boundary. Detached components
use independent interior seeds, simultaneously, with no invented connecting land.
"""
import json
import math
import sys

from shapely import affinity
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union


def polygons(g):
    if g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    return [p for part in g.geoms for p in polygons(part)]


def polygonal(g):
    parts = polygons(g)
    return unary_union(parts) if parts else MultiPolygon([])


def wire(g):
    g = polygonal(g)
    return {"type": "MultiPolygon", "coordinates": [mapping(p)["coordinates"] for p in polygons(g)]}


def wave_parts(delta, anchor):
    result = []
    for p in polygons(delta):
        shared = p.boundary.intersection(anchor)
        detached = shared.is_empty
        seed = p.representative_point() if detached else shared
        x0, y0, x1, y1 = p.bounds
        hi = math.hypot(x1 - x0, y1 - y0) * 2
        lo = 0.0
        # Find the covering distance, including hole interiors and concavities.
        # A vertex-only maximum would miss some interior distance maxima.
        for _ in range(34):
            mid = (lo + hi) / 2
            if p.difference(seed.buffer(mid, quad_segs=12)).is_empty:
                hi = mid
            else:
                lo = mid
        result.append((p, seed, hi * (1 + 1e-9), detached))
    return result


def wave(parts, fraction):
    if fraction <= 0:
        return MultiPolygon([])
    if fraction >= 1:
        return unary_union([p for p, *_ in parts])
    return polygonal(unary_union([
        p.intersection(seed.buffer(radius * fraction, quad_segs=12))
        for p, seed, radius, _ in parts
    ]))


def compile_transition(previous, following, frames, band_width=0.035):
    if not isinstance(frames, int) or not 2 <= frames <= 600:
        raise ValueError('CONTINUOUS_FRAME_BUDGET')
    a, b = shape(previous), shape(following)
    for g in (a, b):
        if not isinstance(g, (Polygon, MultiPolygon)) or not g.is_valid:
            raise ValueError('CONTINUOUS_VALID_SOURCE_POLYGON_REQUIRED')
        if not g.is_empty and (g.bounds[0] <= -180 or g.bounds[2] >= 180 or g.bounds[1] <= -85 or g.bounds[3] >= 85):
            raise ValueError('CONTINUOUS_UNWRAPPED_DOMAIN_REQUIRED')
        for p in polygons(g):
            for r in [p.exterior, *p.interiors]:
                if any(abs(q[0] - r.coords[i][0]) >= 180 for i, q in enumerate(list(r.coords)[1:])):
                    raise ValueError('CONTINUOUS_ANTIMERIDIAN_UNSUPPORTED')
    envelope = a.union(b)
    if envelope.is_empty:
        factor = 1
    else:
        factor = max(.1, math.cos(math.radians((envelope.bounds[1] + envelope.bounds[3]) / 2)))
    scale = lambda g: affinity.scale(g, xfact=factor, yfact=1, origin=(0, 0))
    unscale = lambda g: affinity.scale(g, xfact=1 / factor, yfact=1, origin=(0, 0))
    a, b = scale(a), scale(b)
    common, added, removed = a.intersection(b), b.difference(a), a.difference(b)
    growth, retreat = wave_parts(added, a), wave_parts(removed, b)
    rows, prior, max_outside, max_band_outside = [], None, 0, 0
    tol = max(1e-9, a.union(b).area * 1e-10)
    for f in range(frames):
        u = f / (frames - 1)
        # Mild cubic acceleration, rather than a long near-static quintic tail.
        progress = u * u * (3 - 2 * u)
        gain, loss_left = wave(growth, progress), wave(retreat, 1 - progress)
        current = polygonal(unary_union([common, gain, loss_left]))
        if f == 0:
            current = a
        elif f == frames - 1:
            current = b
        if not current.is_valid:
            raise ValueError('CONTINUOUS_INVALID_INTERMEDIATE')
        outside = current.difference(a.union(b)).area
        missing_common = common.difference(current).area
        if outside > tol or missing_common > tol:
            raise ValueError('CONTINUOUS_SOURCE_ENVELOPE_VIOLATION')
        # Only changing boundary, excluding stationary source edges. The entire
        # luminous band is clipped to current territory (no outward bloom).
        stationary = a.boundary.union(b.boundary).buffer(1e-8)
        front = current.boundary.difference(stationary) if 0 < f < frames - 1 else GeometryCollection()
        band = polygonal(front.buffer(band_width, quad_segs=4).intersection(current))
        band_outside = band.difference(current).area
        if band_outside > tol or not band.is_valid:
            raise ValueError('CONTINUOUS_FRONT_BAND_INVALID')
        max_outside, max_band_outside = max(max_outside, outside), max(max_band_outside, band_outside)
        change = None if prior is None else current.symmetric_difference(prior).area
        # Check monotonic growth/retreat independently, including mixed changes.
        if prior is not None:
            if prior.intersection(added).difference(current).area > tol or current.intersection(removed).difference(prior).area > tol:
                raise ValueError('CONTINUOUS_NON_MONOTONIC_COMPONENT')
        geo = previous if f == 0 else following if f == frames - 1 else wire(unscale(current))
        glow = wire(unscale(band))
        rows.append({"geometry": geo, "boundaryBand": glow, "progress": progress,
                     "alpha": 1, "boundaryAlpha": math.sin(math.pi * u) ** .65,
                     "audit": {"valid": True, "areaDisplayUnits": current.area,
                               "changedAreaFromPrior": change, "outsideSourceUnion": outside,
                               "frontLengthDisplayUnits": front.length,
                               "bandOutsideCurrent": band_outside}})
        prior = current
    return {"schema": "CONTINUOUS_TERRITORY_V1", "frames": rows,
            "semantics": "GEOMETRIC_VISUAL_INTERPOLATION_NOT_HISTORICAL_ROUTE",
            "distanceModel": "LOCAL_LON_COS_MIDLAT_DISPLAY_DISTANCE_NOT_PHYSICAL_SPEED",
            "sourceEndpointsExact": True, "sourceGeometryChanged": False,
            "historicalOrderInferred": False,
            "addedComponents": len(growth), "removedComponents": len(retreat),
            "detachedAddedComponents": sum(x[3] for x in growth),
            "detachedRemovedComponents": sum(x[3] for x in retreat),
            "maxOutsideSourceUnion": max_outside, "maxBandOutsideCurrent": max_band_outside,
            "maximumDisplayTravel": max([x[2] for x in growth + retreat], default=0)}


if __name__ == '__main__':
    data = json.load(sys.stdin)
    output = [compile_transition(x['previous'], x['following'], x['frames'], x.get('bandWidth', .035)) for x in data['transitions']]
    json.dump(output, sys.stdout, separators=(',', ':'), allow_nan=False)
