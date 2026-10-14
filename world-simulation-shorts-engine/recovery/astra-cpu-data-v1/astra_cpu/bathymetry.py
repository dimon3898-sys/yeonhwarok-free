"""Read rectilinear NetCDF elevation without resampling or ocean inference.

The installed C NetCDF library reads raw numeric storage, including compressed
NetCDF4. No Python NetCDF package, GDAL orientation conversion, or GPU is needed.
"""
from copy import deepcopy
import ctypes as C
import ctypes.util
from functools import lru_cache
import math
import re
import threading

import numpy as np

from .model import DataError, RasterData, sha256


_DTYPES = {1: "i1", 3: "i2", 4: "i4", 5: "f4", 6: "f8", 7: "u1",
           8: "u2", 9: "u4", 10: "i8", 11: "u8"}
_HEIGHT_NAMES = {"height", "height_above_mean_sea_level", "surface_altitude",
                 "height_above_reference_ellipsoid"}
_NETCDF_LOCK = threading.RLock()
_MAX_CELLS = 16_000_000


@lru_cache(maxsize=1)
def _netcdf():
    path = ctypes.util.find_library("netcdf")
    if not path:
        raise DataError("installed libnetcdf is required for NetCDF bathymetry")
    try:
        lib = C.CDLL(path)
    except OSError as exc:
        raise DataError("installed libnetcdf is unavailable") from exc
    integer, size = C.POINTER(C.c_int), C.POINTER(C.c_size_t)
    signatures = {
        "nc_open_mem": [C.c_char_p, C.c_int, C.c_size_t, C.c_void_p, integer],
        "nc_close": [C.c_int],
        "nc_inq": [C.c_int, integer, integer, integer, integer],
        "nc_inq_varndims": [C.c_int, C.c_int, integer],
        "nc_inq_var": [C.c_int, C.c_int, C.c_char_p, integer, integer, integer, integer],
        "nc_inq_dimlen": [C.c_int, C.c_int, size],
        "nc_inq_attname": [C.c_int, C.c_int, C.c_int, C.c_char_p],
        "nc_inq_att": [C.c_int, C.c_int, C.c_char_p, integer, size],
        "nc_get_att": [C.c_int, C.c_int, C.c_char_p, C.c_void_p],
        "nc_get_att_text": [C.c_int, C.c_int, C.c_char_p, C.c_void_p],
        "nc_get_att_string": [C.c_int, C.c_int, C.c_char_p, C.POINTER(C.c_char_p)],
        "nc_free_string": [C.c_size_t, C.POINTER(C.c_char_p)],
        "nc_get_var": [C.c_int, C.c_int, C.c_void_p],
        "nc_inq_var_fill": [C.c_int, C.c_int, integer, C.c_void_p],
    }
    try:
        for name, args in signatures.items():
            function = getattr(lib, name)
            function.argtypes, function.restype = args, C.c_int
        lib.nc_strerror.argtypes = [C.c_int]
        lib.nc_strerror.restype = C.c_char_p
        if hasattr(lib, "H5Eget_auto2") and hasattr(lib, "H5Eset_auto2"):
            lib.H5Eget_auto2.argtypes = [C.c_longlong, C.POINTER(C.c_void_p), C.POINTER(C.c_void_p)]
            lib.H5Eget_auto2.restype = C.c_int
            lib.H5Eset_auto2.argtypes = [C.c_longlong, C.c_void_p, C.c_void_p]
            lib.H5Eset_auto2.restype = C.c_int
    except AttributeError as exc:
        raise DataError("installed libnetcdf lacks required in-memory read API") from exc
    return lib


class _Dataset:
    def __init__(self, data):
        self.lib = _netcdf()
        self.buffer = C.create_string_buffer(data)
        ncid = C.c_int()
        self.check(self.lib.nc_open_mem(b"bathymetry.nc", 0, len(data),
                                       self.buffer, C.byref(ncid)))
        self.ncid = ncid.value

    def check(self, code):
        if code:
            message = self.lib.nc_strerror(code).decode("utf-8", "replace")
            raise DataError("NetCDF read failed: " + message)

    def close(self):
        self.check(self.lib.nc_close(self.ncid))

    def attributes(self, varid, count):
        if count > 10000:
            raise DataError("NetCDF attribute count exceeds supported limits")
        result = {}
        for index in range(count):
            name = C.create_string_buffer(257)  # NC_MAX_NAME + terminator
            self.check(self.lib.nc_inq_attname(self.ncid, varid, index, name))
            kind, length = C.c_int(), C.c_size_t()
            self.check(self.lib.nc_inq_att(self.ncid, varid, name,
                                          C.byref(kind), C.byref(length)))
            if length.value > 1_000_000:
                raise DataError("NetCDF attribute exceeds supported subset limits")
            if kind.value == 2:  # NC_CHAR
                value = C.create_string_buffer(length.value + 1)
                self.check(self.lib.nc_get_att_text(self.ncid, varid, name, value))
                value = value.raw[:length.value].decode("utf-8", "replace")
            elif kind.value == 12:  # NC_STRING owns library allocations
                strings = (C.c_char_p * length.value)()
                self.check(self.lib.nc_get_att_string(self.ncid, varid, name, strings))
                try:
                    value = [s.decode("utf-8", "replace") if s else "" for s in strings]
                    if len(value) == 1:
                        value = value[0]
                finally:
                    self.check(self.lib.nc_free_string(length.value, strings))
            elif kind.value in _DTYPES:
                array = np.empty(length.value, dtype=_DTYPES[kind.value])
                self.check(self.lib.nc_get_att(self.ncid, varid, name, array.ctypes.data))
                value = array[0].item() if length.value == 1 else array.tolist()
            else:
                raise DataError("unsupported NetCDF attribute type for " + name.value.decode())
            result[name.value.decode()] = value
        return result

    def variables(self):
        ndims, nvars, natts, unlimited = (C.c_int() for _ in range(4))
        self.check(self.lib.nc_inq(self.ncid, C.byref(ndims), C.byref(nvars),
                                  C.byref(natts), C.byref(unlimited)))
        if ndims.value > 64 or nvars.value > 10000 or natts.value > 10000:
            raise DataError("NetCDF schema exceeds supported subset limits")
        variables = {}
        for varid in range(nvars.value):
            count = C.c_int()
            self.check(self.lib.nc_inq_varndims(self.ncid, varid, C.byref(count)))
            if count.value > 64:
                raise DataError("NetCDF variable dimensionality exceeds supported limits")
            dims = (C.c_int * count.value)()
            name, kind, attrs = C.create_string_buffer(257), C.c_int(), C.c_int()
            # A scalar CRS has zero dimensions, and is never read into a raster.
            self.check(self.lib.nc_inq_var(self.ncid, varid, name, C.byref(kind),
                                          C.byref(count), dims, C.byref(attrs)))
            shape = []
            for dim in dims:
                length = C.c_size_t()
                self.check(self.lib.nc_inq_dimlen(self.ncid, dim, C.byref(length)))
                shape.append(length.value)
            variables[name.value.decode()] = {
                "id": varid, "type": kind.value, "dims": tuple(dims),
                "shape": tuple(shape), "attrs": self.attributes(varid, attrs.value)}
        return variables, self.attributes(-1, natts.value)

    def read(self, var):
        if var["type"] not in _DTYPES:
            raise DataError("unsupported nonnumeric NetCDF variable")
        if not all(var["shape"]) or math.prod(var["shape"]) > _MAX_CELLS:
            raise DataError("NetCDF variable exceeds supported nonempty subset size")
        values = np.empty(var["shape"], dtype=_DTYPES[var["type"]])
        self.check(self.lib.nc_get_var(self.ncid, var["id"], values.ctypes.data))
        return values

    def default_fill(self, var):
        no_fill = C.c_int()
        fill = np.empty(1, dtype=_DTYPES[var["type"]])
        self.check(self.lib.nc_inq_var_fill(self.ncid, var["id"], C.byref(no_fill),
                                           fill.ctypes.data))
        return None if no_fill.value else fill[0].item()


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _unpacked(attrs, label):
    for name, expected in (("scale_factor", 1), ("add_offset", 0)):
        value = attrs.get(name, expected)
        if isinstance(value, (str, list)) or not np.isfinite(value) or value != expected:
            raise DataError(label + " has unsupported packed " + name)
    if _text(attrs.get("_Unsigned")).lower() in ("true", "yes", "1"):
        raise DataError(label + " has unsupported _Unsigned reinterpretation")


def _axis(variables, axis):
    names = {"x": {"lon", "longitude"}, "y": {"lat", "latitude"}}[axis]
    standard = "longitude" if axis == "x" else "latitude"
    candidates = [v for name, v in variables.items()
                  if len(v["dims"]) == 1 and
                  (name.lower() in names or _text(v["attrs"].get("standard_name")) == standard)]
    if len(candidates) != 1:
        raise DataError("exactly one rectilinear " + standard + " axis is required")
    var = candidates[0]
    declared_standard = _text(var["attrs"].get("standard_name"))
    declared_axis = _text(var["attrs"].get("axis")).upper()
    if ((declared_standard and declared_standard != standard)
            or (declared_axis and declared_axis != axis.upper())):
        raise DataError("conflicting " + standard + " axis declaration")
    units = _text(var["attrs"].get("units")).lower()
    accepted = ({"degrees_east", "degree_east", "degrees_e", "degree_e"} if axis == "x"
                else {"degrees_north", "degree_north", "degrees_n", "degree_n"})
    if units not in accepted:
        raise DataError("unsupported " + standard + " coordinate units")
    _unpacked(var["attrs"], standard)
    return var


def _spacing(values, label):
    if len(values) < 2 or not np.isfinite(values).all():
        raise DataError(label + " axis needs at least two finite sample centers")
    spacing = float((values[-1] - values[0]) / (len(values) - 1))
    if spacing == 0 or not np.allclose(values, values[0] + np.arange(len(values)) * spacing,
                                      rtol=0, atol=1e-9):
        raise DataError("unsupported irregular " + label + " axis")
    if label == "longitude" and spacing < 0:
        raise DataError("descending longitude is unsupported by the raster contract")
    return spacing


def _declared_validity(values, attrs, label):
    """Validate CF support bounds before comparisons, including coordinate axes."""
    valid = np.isfinite(values)
    for field in ("valid_min", "valid_max"):
        if field in attrs:
            bound = attrs[field]
            if not isinstance(bound, (int, float)) or not math.isfinite(bound):
                raise DataError("invalid " + label + " " + field)
    if attrs.get("valid_min", -math.inf) > attrs.get("valid_max", math.inf):
        raise DataError("reversed " + label + " validity bounds")
    for field, operator in (("valid_min", np.greater_equal), ("valid_max", np.less_equal)):
        if field in attrs:
            valid &= operator(values, attrs[field])
    if "valid_range" in attrs:
        bounds = attrs["valid_range"]
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in bounds)
                or bounds[0] > bounds[1]):
            raise DataError("invalid " + label + " valid_range")
        valid &= (values >= bounds[0]) & (values <= bounds[1])
    return valid


def _parse_bathymetry_unlocked(data: bytes, *, expected_sha256: str | None = None,
                               vertical_datum: str | None = None) -> RasterData:
    """Preserve signed elevation, source axes, cell centers, and missing values.

    Accepted inputs are metre-valued, positive-up, unpacked rectilinear lat/lon
    grids. Unsupported packing, units, sign semantics and grids fail explicitly.
    Unknown vertical datum is recorded as unresolved rather than inferred.
    """
    if not isinstance(data, bytes) or not data:
        raise DataError("nonempty NetCDF bytes are required")
    digest = sha256(data)
    if expected_sha256 is not None:
        if not isinstance(expected_sha256, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
            raise DataError("expected SHA-256 must contain 64 hexadecimal characters")
        if digest != expected_sha256.lower():
            raise DataError("input SHA-256 mismatch")
    if vertical_datum is not None and not _text(vertical_datum):
        raise DataError("vertical datum declaration must be a nonempty string")
    dataset = _Dataset(data)
    try:
        variables, global_attrs = dataset.variables()
        lon, lat = _axis(variables, "x"), _axis(variables, "y")
        candidates = [(name, v) for name, v in variables.items()
                      if v["dims"] == (lat["dims"][0], lon["dims"][0]) and
                      (name.lower() in {"elevation", "height", "z", "bathymetry"} or
                       _text(v["attrs"].get("standard_name")) in _HEIGHT_NAMES)]
        if len(candidates) != 1:
            raise DataError("exactly one elevation variable in latitude/longitude order is required")
        name, elevation = candidates[0]
        attrs = elevation["attrs"]
        if (elevation["type"] not in _DTYPES or not all(elevation["shape"])
                or math.prod(elevation["shape"]) > _MAX_CELLS):
            raise DataError("unsupported elevation type or nonempty subset size")
        node_offset = attrs.get("node_offset", global_attrs.get("node_offset", 1))
        if not isinstance(node_offset, (int, float)) or node_offset != 1:
            raise DataError("unsupported grid-node registration; cell centers are required")
        _unpacked(attrs, "elevation")
        units = _text(attrs.get("units", global_attrs.get("geospatial_vertical_units")))
        if units.lower() not in {"m", "meter", "meters", "metre", "metres"}:
            raise DataError("unsupported elevation units; metres are required")
        positive = _text(attrs.get("positive", global_attrs.get("geospatial_vertical_positive"))).lower()
        if not positive and _text(attrs.get("standard_name")) in _HEIGHT_NAMES:
            positive = "up"
        if positive != "up":
            raise DataError("unsupported or unresolved elevation sign; positive up is required")
        mapping_name = _text(attrs.get("grid_mapping"))
        mapping = variables.get(mapping_name)
        crs_attrs = mapping["attrs"] if mapping else {}
        if mapping_name and mapping is None:
            raise DataError("referenced CRS variable is missing")
        mapping_kind = _text(crs_attrs.get("grid_mapping_name"))
        if mapping_kind and mapping_kind != "latitude_longitude":
            raise DataError("unsupported projected or rotated NetCDF grid mapping")
        source_crs = _text(global_attrs.get("geospatial_bounds_crs"))
        crs = (_text(crs_attrs.get("epsg_code")) or _text(crs_attrs.get("spatial_ref"))
               or _text(crs_attrs.get("crs_wkt")) or source_crs)
        if not crs:
            raise DataError("horizontal CRS is unresolved")
        if crs != "EPSG:4326":
            raise DataError("unsupported horizontal CRS; EPSG:4326 degree axes are required")
        epsg = _text(crs_attrs.get("epsg_code"))
        if epsg and source_crs and epsg != source_crs:
            raise DataError("conflicting source horizontal CRS declarations")
        x, y = dataset.read(lon).astype(np.float64), dataset.read(lat).astype(np.float64)
        if np.any((x < -180) | (x > 180)) or np.any((y < -90) | (y > 90)):
            raise DataError("EPSG:4326 sample centers exceed supported longitude/latitude ranges")
        for variable, coordinates in ((lon, x), (lat, y)):
            if not _declared_validity(coordinates, variable["attrs"], "coordinate").all():
                raise DataError("coordinate axis contains invalid sample centers")
            for field in ("_FillValue", "missing_value"):
                if field in variable["attrs"]:
                    missing = np.asarray(variable["attrs"][field]).reshape(-1)
                    if np.isin(coordinates, missing).any():
                        raise DataError("coordinate axis contains missing sample centers")
            default_coordinate_fill = dataset.default_fill(variable)
            if default_coordinate_fill is not None and np.any(coordinates == default_coordinate_fill):
                raise DataError("coordinate axis contains uninitialized sample centers")
        dx, dy = _spacing(x, "longitude"), _spacing(y, "latitude")
        values = dataset.read(elevation)
        valid = _declared_validity(values, attrs, "elevation")
        sentinels = []
        for field in ("_FillValue", "missing_value"):
            if field in attrs:
                value = attrs[field]
                sentinels.extend(value if isinstance(value, list) else [value])
        default_fill = dataset.default_fill(elevation)
        for sentinel in sentinels + ([] if default_fill is None else [default_fill]):
            if not isinstance(sentinel, (int, float)):
                raise DataError("nonnumeric elevation nodata declaration")
            valid &= values != sentinel
        source_datum = (_text(attrs.get("vertical_datum"))
                        or _text(global_attrs.get("geospatial_bounds_vertical_crs"))
                        or _text(global_attrs.get("vertical_datum")) or None)
        datum = vertical_datum if vertical_datum is not None else source_datum
        metadata = {
            "inputSha256": digest, "crs": crs, "units": units, "verticalDatum": datum,
            "verticalDatumStatus": ("DECLARED_CALLER" if vertical_datum is not None else
                                    "DECLARED_SOURCE" if source_datum else "UNRESOLVED"),
            "sourceVerticalDatum": source_datum,
            "nodata": None if not sentinels else sentinels[0] if len(sentinels) == 1 else sentinels,
            "defaultFillValue": default_fill, "positive": positive,
            "transform": [float(x[0] - dx / 2), dx, 0.0, float(y[0] - dy / 2), 0.0, dy],
            "spacing": [dx, dy], "registration": "CELL_CENTER",
            "rowOrder": "SOUTH_TO_NORTH" if dy > 0 else "NORTH_TO_SOUTH",
            "variable": name, "sourceDtype": str(values.dtype), "dtype": str(values.dtype),
            "quantity": "SIGNED_ELEVATION", "oceanMaskStatus": "UNRESOLVED",
            "sourceAttributes": {"global": global_attrs, "elevation": attrs,
                                 "longitude": lon["attrs"], "latitude": lat["attrs"],
                                 "crs": crs_attrs},
        }
        return RasterData(values, x, y, valid, metadata)
    finally:
        dataset.close()


def parse_bathymetry(data: bytes, *, expected_sha256: str | None = None,
                     vertical_datum: str | None = None) -> RasterData:
    """Read an unpacked positive-up metre NetCDF subset, preserving raw cells.

    The C library and its HDF5 backend are serialized for concurrent CPU callers.
    Input axes and orientation remain intact; an ocean mask is never inferred.
    """
    with _NETCDF_LOCK:
        lib = _netcdf()
        callback, context = C.c_void_p(), C.c_void_p()
        restore_errors = False
        # nc_open_mem probes its logical name as a disk file before using memory.
        # HDF5 prints this expected failed probe on new threads. Preserve that
        # thread's error callback; actual NetCDF failures still raise DataError.
        if hasattr(lib, "H5Eget_auto2") and hasattr(lib, "H5Eset_auto2"):
            if lib.H5Eget_auto2(0, C.byref(callback), C.byref(context)) == 0:
                restore_errors = lib.H5Eset_auto2(0, None, None) == 0
        try:
            return _parse_bathymetry_unlocked(data, expected_sha256=expected_sha256,
                                             vertical_datum=vertical_datum)
        finally:
            if restore_errors and lib.H5Eset_auto2(0, callback, context) != 0:
                raise DataError("HDF5 error callback restoration failed")


def depth_with_ocean_mask(raster: RasterData, ocean_mask=None) -> RasterData:
    """Derive max(0, -elevation) only on an explicitly supplied ocean mask.

    The input remains immutable. Land and missing cells are unsupported NaNs in
    the derived raster, never valid zero depths. A negative land elevation does
    not establish ocean membership. Mask alignment must be supplied by caller.
    """
    if ocean_mask is None:
        raise DataError("ocean mask unresolved; negative elevation does not establish ocean")
    if raster.values.ndim != 2 or raster.metadata.get("positive") != "up":
        raise DataError("derived depth requires a positive-up elevation raster")
    if raster.metadata.get("quantity") != "SIGNED_ELEVATION":
        raise DataError("derived depth requires signed source elevation")
    try:
        mask = np.asarray(ocean_mask)
    except (TypeError, ValueError) as exc:
        raise DataError("ocean mask must be a boolean HxW array aligned to the source raster") from exc
    if mask.dtype != np.bool_ or mask.shape != raster.values.shape:
        raise DataError("ocean mask must be a boolean HxW array aligned to the source raster")
    valid = raster.valid & mask
    values = np.full(raster.values.shape, np.nan, dtype=np.float64)
    values[valid] = np.maximum(0.0, -raster.values[valid].astype(np.float64))
    metadata = deepcopy(raster.metadata)
    metadata.update(quantity="DERIVED_OCEAN_DEPTH", positive="down", nodata=None,
                    dtype=str(values.dtype),
                    sourcePositive="up", sourceNodata=raster.metadata.get("nodata"),
                    oceanMaskStatus="SUPPLIED_CALLER", oceanMaskPolicy="SOURCE_VALID_AND_CALLER_OCEAN",
                    oceanMaskSha256=sha256(mask.astype(np.uint8).tobytes(order="C")),
                    derivation="max(0,-signedElevation)", invalidRepresentation="NaN")
    return RasterData(values, raster.x, raster.y, valid, metadata)
