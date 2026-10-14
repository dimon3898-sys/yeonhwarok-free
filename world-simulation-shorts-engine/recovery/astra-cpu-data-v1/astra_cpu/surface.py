"""Lossless PNG surface samples with worldfile and explicit geographic CRS.

The returned channels are the original encoded bytes, not linear light or a
physical albedo measurement. No resampling, color conversion or reprojection is
performed. Source nominal resolution belongs to the provider's catalog.
"""
from copy import deepcopy
from io import BytesIO
import math
import re
import warnings

import numpy as np
from osgeo import osr
from PIL import Image, UnidentifiedImageError

from .model import DataError, RasterData, sha256


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_COLOR_INFO_KEYS = ("gamma", "srgb", "chromaticity", "icc_profile")


def _sidecar(value, name):
    if isinstance(value, str):
        try:
            raw = value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise DataError(f"{name} must be UTF-8 text") from exc
    elif isinstance(value, bytes):
        raw = value
    else:
        raise DataError(f"{name} must be bytes or text")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataError(f"{name} must be UTF-8 text") from exc
    if not text.strip() or "\x00" in text:
        raise DataError(f"{name} is empty or contains NUL characters")
    return raw, text


def _check_hash(raw, expected, name):
    digest = sha256(raw)
    if expected is not None:
        if not isinstance(expected, str) or re.fullmatch(r"[0-9a-fA-F]{64}", expected) is None:
            raise DataError(f"expected {name} SHA-256 must be 64 hexadecimal characters")
        if digest != expected.lower():
            raise DataError(f"{name} SHA-256 mismatch")
    return digest


def _worldfile(text):
    tokens = text.split()
    if len(tokens) != 6:
        raise DataError("worldfile requires six values in A,D,B,E,C,F order")
    try:
        coefficients = tuple(float(token) for token in tokens)
    except ValueError as exc:
        raise DataError("worldfile requires six finite numeric values") from exc
    if not all(math.isfinite(value) for value in coefficients):
        raise DataError("worldfile requires six finite numeric values")
    a, d, b, e, c, f = coefficients
    if b != 0 or d != 0:
        raise DataError("rotated or sheared worldfile grids are unsupported")
    if a <= 0:
        raise DataError("worldfile x spacing must be positive; westward grids are unsupported")
    if e == 0:
        raise DataError("worldfile y spacing must be nonzero")
    # C,F describe the upper-left pixel CENTER; GDAL origins describe its corner.
    transform = (c - a / 2, a, 0.0, f - e / 2, 0.0, e)
    if not all(math.isfinite(value) for value in transform):
        raise DataError("worldfile corner transform is nonfinite")
    return coefficients, transform


def _projection(text):
    try:
        with osr.ExceptionMgr():
            reference = osr.SpatialReference()
            if reference.ImportFromWkt(text.strip()) != 0 or reference.Validate() != 0:
                raise DataError("invalid projection WKT")
            if reference.IsProjected():
                raise DataError("projected surface grids require explicit reprojection and are unsupported")
            if not reference.IsGeographic() or reference.GetAxesCount() != 2:
                raise DataError("surface projection must be a two-dimensional geographic CRS")
            angular_units = reference.GetAngularUnits()
            if (not math.isfinite(angular_units)
                    or not math.isclose(angular_units, math.pi / 180, rel_tol=1e-12, abs_tol=0)):
                raise DataError("surface geographic coordinates must use degrees")
            geodetic_parameters = (reference.GetSemiMajor(), reference.GetSemiMinor(),
                                   reference.GetInvFlattening(),
                                   float(reference.GetAttrValue("PRIMEM", 1)))
            if not all(math.isfinite(value) for value in geodetic_parameters):
                raise DataError("projection contains nonfinite geodetic parameters")
            # WKT authority axes may say latitude,longitude. A worldfile always
            # describes image x,y; retain its longitude,latitude coordinates.
            reference.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
            authority = reference.GetAuthorityName(None)
            code = reference.GetAuthorityCode(None)
            normalized = reference.ExportToWkt()
    except DataError:
        raise
    except (RuntimeError, TypeError, ValueError) as exc:
        raise DataError("invalid projection WKT") from exc
    return f"{authority}:{code}" if authority and code else normalized, normalized


def _png(data):
    if not data.startswith(_PNG_SIGNATURE):
        raise DataError("expected PNG image; WMS error or non-image payload is unsupported")
    # Pillow can expose some 16-bit PNGs as 8-bit RGB. Inspect IHDR first to
    # reject that silent precision loss, and reject palette/grayscale conversion.
    if len(data) < 33 or data[12:16] != b"IHDR" or int.from_bytes(data[8:12], "big") != 13:
        raise DataError("invalid PNG IHDR")
    if data[24] != 8 or data[25] not in (2, 6):
        raise DataError("surface PNG must contain original 8-bit RGB or RGBA channels")
    width, height = int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
    if not 0 < width * height <= 16_000_000:
        raise DataError('surface subset exceeds bounded CPU raster size')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format != "PNG":
                    raise DataError("expected PNG image")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                if image.mode not in ("RGB", "RGBA"):
                    raise DataError("surface PNG must contain original RGB or RGBA channels")
                if getattr(image, "n_frames", 1) != 1:
                    raise DataError("animated surface PNGs are unsupported")
                image.load()
                values = np.array(image, copy=True)
                info = deepcopy(image.info)
                mode = image.mode
    except DataError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise DataError("invalid or unsupported PNG payload") from exc
    if values.dtype != np.uint8 or values.ndim != 3:
        raise DataError("surface PNG must contain uint8 RGB or RGBA channels")
    if mode == "RGBA":
        valid = values[:, :, 3] != 0
        nodata = {"alpha": 0}
    elif "transparency" in info:
        transparent = info["transparency"]
        if not isinstance(transparent, tuple) or len(transparent) != 3:
            raise DataError("unsupported RGB PNG transparency metadata")
        valid = ~np.all(values == np.asarray(transparent), axis=2)
        nodata = {"transparency": transparent}
    else:
        valid = np.ones(values.shape[:2], dtype=np.bool_)
        nodata = None
    return values, valid, mode, info, nodata


def parse_surface(data: bytes, worldfile: bytes | str, projection: bytes | str, *,
                  expected_sha256: str | None = None,
                  expected_sidecar_sha256: dict | None = None) -> RasterData:
    """Parse raw PNG and sidecars, retaining their hashes and actual coordinates.

    ``expected_sidecar_sha256`` accepts ``worldfile`` and ``projection`` keys.
    Text sidecars are hashed as their exact UTF-8 encoding; bytes are hashed
    unchanged, including any BOM and line endings. Rotated, projected, non-degree
    and westward grids fail explicitly instead of acquiring invented bounds/CRS.
    """
    if not isinstance(data, bytes):
        raise DataError("PNG data must be bytes")
    if expected_sidecar_sha256 is None:
        expected_sidecar_sha256 = {}
    if (not isinstance(expected_sidecar_sha256, dict)
            or set(expected_sidecar_sha256) - {"worldfile", "projection"}):
        raise DataError("expected sidecar SHA-256 keys must be worldfile/projection")
    world_raw, world_text = _sidecar(worldfile, "worldfile")
    projection_raw, projection_text = _sidecar(projection, "projection")
    input_sha = _check_hash(data, expected_sha256, "PNG")
    sidecar_sha = {"worldfile": _check_hash(world_raw, expected_sidecar_sha256.get("worldfile"), "worldfile"),
                   "projection": _check_hash(projection_raw, expected_sidecar_sha256.get("projection"), "projection")}
    coefficients, transform = _worldfile(world_text)
    crs, normalized_wkt = _projection(projection_text)
    values, valid, mode, info, nodata = _png(data)
    height, width = values.shape[:2]
    with np.errstate(over="ignore", invalid="ignore"):
        x = transform[0] + (np.arange(width, dtype=np.float64) + .5) * transform[1]
        y = transform[3] + (np.arange(height, dtype=np.float64) + .5) * transform[5]
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise DataError("worldfile produces nonfinite sample coordinates")
    with np.errstate(over="ignore", invalid="ignore"):
        # Centers alone can be finite while half a final pixel extends to inf.
        # Check the same cell edges used by RasterData.bbox, as well as both
        # affine outer corners, without imposing geographic fixture bounds.
        edges = (x[0] - transform[1] / 2, x[-1] + transform[1] / 2,
                 min(y[0], y[-1]) - abs(transform[5]) / 2,
                 max(y[0], y[-1]) + abs(transform[5]) / 2)
        far_corner = (transform[0] + np.float64(width) * transform[1],
                      transform[3] + np.float64(height) * transform[5])
        finite_edges = all(math.isfinite(value) for value in (*edges, *far_corner))
        strict_axes = (np.all(np.diff(x) > 0)
                       and np.all(np.diff(y) * np.sign(transform[5]) > 0))
    if not finite_edges:
        raise DataError("worldfile produces nonfinite outer pixel edges")
    if not strict_axes or edges[0] >= edges[1] or edges[2] >= edges[3]:
        raise DataError("worldfile spacing collapses sample coordinates or pixel edges in float64")
    color_info = {key: deepcopy(info[key]) for key in _COLOR_INFO_KEYS if key in info}
    if "srgb" in info:
        color_space = "sRGB_ENCODED_BYTES_PRESERVED"
    elif "icc_profile" in info:
        color_space = "ICC_ENCODED_BYTES_PRESERVED"
    else:
        color_space = "UNSPECIFIED_ENCODED_PNG_BYTES_PRESERVED"
    metadata = {
        "inputSha256": input_sha,
        "sidecarSha256": sidecar_sha,
        "crs": crs,
        "crsWkt": normalized_wkt,
        "projectionWkt": projection_text,
        "axisOrder": "LONGITUDE_LATITUDE",
        "transform": list(transform),
        "worldfileCoefficients": list(coefficients),
        "pixelRegistration": "Area",
        "worldfileRegistration": "UPPER_LEFT_PIXEL_CENTER",
        "gridSpacing": [transform[1], transform[5]],
        "horizontalUnits": "degree",
        "units": "uint8_encoded_color",
        "verticalDatum": "NOT_APPLICABLE",
        "rowOrder": "NORTH_TO_SOUTH" if transform[5] < 0 else "SOUTH_TO_NORTH",
        "nodata": nodata,
        "mode": mode,
        "pngInfo": info,
        "pngColorMetadata": color_info,
        "colorSpace": color_space,
        "colorConversion": "NONE",
        "physicalAlbedo": "NOT_INFERRED",
    }
    return RasterData(values, x, y, valid, metadata)
