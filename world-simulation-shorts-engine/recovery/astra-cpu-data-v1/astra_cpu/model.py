"""Neutral numeric raster contract shared by sample parsers and future GPU ingest."""
from dataclasses import dataclass
from copy import deepcopy
import hashlib
import math

import numpy as np


class DataError(ValueError):
    """Invalid/unsupported input, without coercing missing data into values."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_bbox(bbox):
    if (not isinstance(bbox, (list, tuple)) or len(bbox) != 4
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   or not math.isfinite(v) for v in bbox)):
        raise DataError("bbox must be four finite numbers [west,south,east,north]")
    west, south, east, north = map(float, bbox)
    if not (-180 <= west <= 180 and -180 <= east <= 180
            and -90 <= south < north <= 90 and west != east):
        raise DataError("invalid geographic bbox")
    return west, south, east, north


def split_dateline(bbox):
    west, south, east, north = validate_bbox(bbox)
    if west < east:
        return [(west, south, east, north)]
    parts = []
    if west < 180:
        parts.append((west, south, 180.0, north))
    if east > -180:
        parts.append((-180.0, south, east, north))
    if not parts:
        raise DataError("empty dateline request")
    return parts


@dataclass(frozen=True)
class RasterData:
    """Values remain in their original numeric dtype and georeferenced orientation.

    x/y are actual sample centers. valid is an independent H×W support mask;
    invalid numeric cells are retained, never zero-filled. metadata must contain
    a GDAL-style six-value corner transform, CRS, spacing/registration, units,
    vertical datum and input SHA. This is not a GPU upload/memory-layout format.
    """
    values: np.ndarray
    x: np.ndarray
    y: np.ndarray
    valid: np.ndarray
    metadata: dict

    def __post_init__(self):
        values = np.array(self.values, copy=True)
        x = np.array(self.x, dtype=np.float64, copy=True)
        y = np.array(self.y, dtype=np.float64, copy=True)
        valid = np.array(self.valid, dtype=np.bool_, copy=True)
        meta = deepcopy(self.metadata)
        if (values.ndim not in (2, 3) or not values.shape[0] or not values.shape[1]
                or x.ndim != 1 or y.ndim != 1
                or values.shape[:2] != (len(y), len(x)) or valid.shape != values.shape[:2]
                or not np.isfinite(x).all() or not np.isfinite(y).all()):
            raise DataError("inconsistent raster values, axes or support mask")
        if values.dtype.kind not in "fiu":
            raise DataError("only numeric raster values are supported")
        if values.ndim == 3 and values.shape[2] not in (3, 4):
            raise DataError("color rasters must have RGB/RGBA channels")
        finite = np.isfinite(values)
        if values.ndim == 3:
            finite = finite.all(axis=2)
        if np.any(valid & ~finite):
            raise DataError("nonfinite values marked valid")
        transform = meta.get("transform")
        if (not isinstance(transform, (tuple, list)) or len(transform) != 6
                or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in transform)
                or transform[1] <= 0 or transform[2] != 0 or transform[4] != 0 or transform[5] == 0):
            raise DataError("rectilinear transform required; rotated grids are explicit unsupported inputs")
        expected_x = transform[0] + (np.arange(len(x)) + .5) * transform[1]
        expected_y = transform[3] + (np.arange(len(y)) + .5) * transform[5]
        if not (np.allclose(x, expected_x, rtol=0, atol=1e-9)
                and np.allclose(y, expected_y, rtol=0, atol=1e-9)):
            raise DataError("actual sample axes do not agree with transform")
        for array in (values, x, y, valid):
            array.setflags(write=False)
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)
        object.__setattr__(self, "valid", valid)
        object.__setattr__(self, "metadata", meta)

    @property
    def bbox(self):
        t = self.metadata["transform"]
        return (float(self.x[0] - t[1] / 2), float(min(self.y[0], self.y[-1]) - abs(t[5]) / 2),
                float(self.x[-1] + t[1] / 2), float(max(self.y[0], self.y[-1]) + abs(t[5]) / 2))

    def crop(self, bbox):
        """Extract cells whose centers are in bbox, without interpolation/padding.

        A crossing request is handled as separate parts by the provider. Output
        reports actual selected cell edges, rather than claiming requested bounds.
        """
        west, south, east, north = validate_bbox(bbox)
        if west >= east:
            raise DataError("split dateline bbox before crop")
        columns = np.flatnonzero((self.x >= west) & (self.x < east))
        rows = np.flatnonzero((self.y >= south) & (self.y < north))
        if not len(columns) or not len(rows):
            raise DataError("bbox contains no supplied sample centers")
        xs = slice(int(columns[0]), int(columns[-1]) + 1)
        ys = slice(int(rows[0]), int(rows[-1]) + 1)
        meta = deepcopy(self.metadata)
        t = [float(v) for v in meta["transform"]]
        t[0] += columns[0] * t[1]
        t[3] += rows[0] * t[5]
        meta["transform"] = t
        meta["requestedBBox"] = list(bbox)
        meta["cropPolicy"] = "CENTER_IN_HALF_OPEN_BBOX_NO_RESAMPLING"
        return RasterData(self.values[ys, xs], self.x[xs], self.y[ys], self.valid[ys, xs], meta)

    def north_up(self):
        """Lossless row reordering only; original values and sign are preserved."""
        if self.metadata["transform"][5] < 0:
            return self
        meta = deepcopy(self.metadata)
        t = [float(v) for v in meta["transform"]]
        t[3] += len(self.y) * t[5]
        t[5] = -t[5]
        meta.update(transform=t, rowOrder="NORTH_TO_SOUTH", sourceRowOrder="SOUTH_TO_NORTH")
        return RasterData(self.values[::-1], self.x, self.y[::-1], self.valid[::-1], meta)
