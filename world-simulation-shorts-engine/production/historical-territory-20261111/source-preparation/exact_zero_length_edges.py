"""Explicit lossless normalization of exactly identical adjacent coordinates.

No tolerance, snapping, rounding, coordinate movement, synthetic edge, area
change, topology repair, or nonzero edge removal is permitted. Exact binary64
point identity is required. All nonzero directed edges and coordinate values
are preserved, and exact rational shoelace area equality is asserted.
"""
from collections import Counter
from copy import deepcopy
from fractions import Fraction


def nonzero_directed_edges(ring):
    return Counter((tuple(a), tuple(b)) for a, b in zip(ring, ring[1:]) if a != b)


def exact_signed_area(ring):
    points = [(Fraction(x), Fraction(y)) for x, y in ring]
    return sum((a[0] * b[1] - b[0] * a[1]
                for a, b in zip(points, points[1:])), Fraction()) / 2


def normalize_ring(ring):
    if len(ring) < 4 or ring[0] != ring[-1]:
        raise ValueError("SOURCE_CLOSED_RING_REQUIRED")
    output, removed = [deepcopy(ring[0])], []
    for index, point in enumerate(ring[1:], 1):
        if tuple(point) == tuple(output[-1]):
            removed.append({"originalPointIndex": index,
                            "originalZeroEdgeIndex": index - 1,
                            "point": deepcopy(point)})
        else:
            output.append(deepcopy(point))
    if len(output) < 4 or output[0] != output[-1]:
        raise ValueError("SOURCE_RING_DEGENERATE_AFTER_ZERO_EDGE_NORMALIZATION")
    assert nonzero_directed_edges(output) == nonzero_directed_edges(ring)
    assert exact_signed_area(output) == exact_signed_area(ring)
    assert set(map(tuple, output)) == set(map(tuple, ring))
    return output, removed


def remove_exact_zero_length_edges(geometry):
    """Return (unchanged-fill geometry, explicit zero-edge removal audit)."""
    if geometry["type"] not in ("Polygon", "MultiPolygon"):
        raise ValueError("POLYGON_GEOMETRY_REQUIRED")
    is_polygon = geometry["type"] == "Polygon"
    polygons = [geometry["coordinates"]] if is_polygon else geometry["coordinates"]
    output, rows = [], []
    for pi, polygon in enumerate(polygons):
        result_polygon = []
        for ri, ring in enumerate(polygon):
            result_ring, removed = normalize_ring(ring)
            result_polygon.append(result_ring)
            if removed:
                rows.append({"polygonIndex": pi, "ringIndex": ri,
                             "removedZeroLengthEdges": len(removed),
                             "removedOccurrences": removed})
        output.append(result_polygon)
    audit = {
        "operation": "EXACT_ADJACENT_ZERO_LENGTH_EDGE_REMOVAL_ONLY",
        "removedZeroLengthEdges": sum(row["removedZeroLengthEdges"] for row in rows),
        "ringResults": rows,
        "nonzeroDirectedEdgeMultisetPreserved": True,
        "exactSignedAreaPreserved": True,
        "allDistinctCoordinateValuesPreserved": True,
        "movedCoordinateValues": 0,
        "addedCoordinateValues": 0,
        "epsilonOrSnapUsed": False}
    return {"type": geometry["type"],
            "coordinates": output[0] if is_polygon else output}, audit
