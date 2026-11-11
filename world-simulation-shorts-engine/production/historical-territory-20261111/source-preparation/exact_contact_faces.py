"""Split only proven exact repeated contacts, without changing any edge.

Source-independent geometry helper. This is not a general polygon repair tool.
The caller must prove every permitted point is a shared exact source point.
Unsupported opposite-winding loops or holes fail closed. No tolerance, snap,
buffer, MakeValid, coordinate rounding, or inferred connecting edge is used.
"""
from collections import Counter
from copy import deepcopy
from fractions import Fraction


def ring_edges(ring):
    return Counter((tuple(a), tuple(b)) for a, b in zip(ring, ring[1:]))


def exact_signed_area(ring):
    """Exact binary64-input shoelace area, including very small loops."""
    points = [(Fraction(x), Fraction(y)) for x, y in ring]
    return sum((a[0] * b[1] - b[0] * a[1]
                for a, b in zip(points, points[1:])), Fraction()) / 2


def split_ring_at_proven_contacts(ring, proven_points):
    """Return simple-contact faces only for approved exact tuple identities.

    Directed-edge multiset equality is a proof that every non-boundary
    horizontal-ray crossing count, even-odd support, and winding sum remains
    identical. The newly separated closures are existing edges, not new ones.
    """
    if ring[0] != ring[-1]:
        raise ValueError("SOURCE_RING_NOT_CLOSED")
    allowed = {tuple(p) for p in proven_points}
    pending, output, events = [deepcopy(ring)], [], []
    while pending:
        current = pending.pop()
        previous = {}
        pair = None
        for j, point in enumerate(current[:-1]):
            key = tuple(point)
            if key in previous:
                i = previous[key]
                if key not in allowed:
                    raise ValueError("UNPROVEN_EXACT_SELF_CONTACT")
                if j - i < 3 or len(current) - (j - i) < 4:
                    raise ValueError("CONTACT_WOULD_PRODUCE_DEGENERATE_FACE")
                pair = i, j
                break
            previous[key] = j
        if pair is None:
            output.append(current)
            continue
        i, j = pair
        little = current[i:j + 1]
        main = current[:i + 1] + current[j + 1:]
        area0, area1, area2 = map(exact_signed_area, (current, main, little))
        if area1 * area2 <= 0 or area0 != area1 + area2:
            raise ValueError("CONTACT_REQUIRES_UNPROVEN_HOLE_REINTERPRETATION")
        if ring_edges(current) != ring_edges(main) + ring_edges(little):
            raise AssertionError("DIRECTED_EDGE_MULTISET_CHANGED")
        events.append({"point": current[i], "indicesInCurrentRing": [i, j],
                       "newCoordinates": 0, "movedCoordinates": 0,
                       "directedEdgeMultisetPreserved": True,
                       "exactSignedAreaPreserved": True})
        pending.extend([little, main])
    if ring_edges(ring) != sum((ring_edges(r) for r in output), Counter()):
        raise AssertionError("FINAL_DIRECTED_EDGE_MULTISET_CHANGED")
    return output, events


def split_geometry_at_proven_contacts(geometry, proven_points):
    if geometry["type"] not in ("Polygon", "MultiPolygon"):
        raise ValueError("POLYGON_GEOMETRY_REQUIRED")
    polygons = ([geometry["coordinates"]] if geometry["type"] == "Polygon"
                else geometry["coordinates"])
    output, audit = [], []
    for pi, polygon in enumerate(polygons):
        faces, events = split_ring_at_proven_contacts(polygon[0], proven_points)
        if events and len(polygon) != 1:
            raise ValueError("CONTACT_WITH_HOLES_REQUIRES_SEPARATE_PROOF")
        if events:
            output.extend([[face] for face in faces])
            audit.extend(dict(event, polygonIndex=pi, ringIndex=0)
                         for event in events)
        else:
            output.append(deepcopy(polygon))
    return {"type": "MultiPolygon", "coordinates": output}, audit
