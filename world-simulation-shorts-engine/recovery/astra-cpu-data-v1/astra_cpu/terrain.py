"""Decode geographic Float32 terrain without modifying its numeric samples."""
import math
import re
import uuid

import numpy as np
from osgeo import gdal, osr

from .model import DataError, RasterData, sha256


def _geographic_crs(dataset):
    """Require the supported two-dimensional WGS84 longitude/latitude CRS."""
    source = dataset.GetSpatialRef()
    target = osr.SpatialReference()
    target.ImportFromEPSG(4326)
    options = ["IGNORE_DATA_AXIS_TO_SRS_AXIS_MAPPING=YES",
               "CRITERION=EQUIVALENT_EXCEPT_AXIS_ORDER_GEOGCRS"]
    if (source is None or not source.IsGeographic() or source.IsCompound()
            or not source.IsSame(target, options)):
        raise DataError("terrain CRS must be WGS84 geographic 2D degrees; "
                        "unknown, projected and other CRSs are unsupported")
    return source.ExportToWkt()


def parse_terrain(data: bytes, *, expected_sha256: str | None = None,
                  vertical_datum: str | None = None) -> RasterData:
    """Read a one-band Float32 WGS84 GeoTIFF into the neutral CPU contract.

    Values are meters under the terrain input contract. An absent band unit is
    recorded explicitly; a declared different unit or packed scale/offset is an
    unsupported input. Vertical datum is never inferred from a dataset name:
    supply the documented source datum when it is not encoded in the TIFF.

    GDAL already returns a corner transform corrected for RasterPixelIsPoint.
    Both registration types therefore use corner + half a cell for centers,
    with no additional point shift. Neither row order nor missing values are
    changed. Use RasterData.crop()/north_up() for lossless selection/reordering.
    """
    if not isinstance(data, bytes) or not data:
        raise DataError("terrain input must be nonempty GeoTIFF bytes")
    digest = sha256(data)
    if expected_sha256 is not None:
        if (not isinstance(expected_sha256, str)
                or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256)):
            raise DataError("expected_sha256 must be a 64-character SHA-256 hex digest")
        if digest != expected_sha256.lower():
            raise DataError(f"terrain input SHA-256 mismatch: expected {expected_sha256.lower()}, "
                            f"received {digest}")
    if vertical_datum is not None and (not isinstance(vertical_datum, str)
                                       or not vertical_datum.strip()):
        raise DataError("vertical_datum must be a nonempty declared datum or None")

    path = f"/vsimem/astra-terrain-{uuid.uuid4().hex}.tif"
    dataset = band = None
    try:
        with (gdal.ExceptionMgr(), osr.ExceptionMgr(), gdal.quiet_errors(),
              gdal.config_option("GTIFF_POINT_GEO_IGNORE", "FALSE")):
            gdal.FileFromMemBuffer(path, data)
            # Restrict decoding to TIFF; no VRT, remote path or external reader.
            dataset = gdal.OpenEx(path, gdal.OF_RASTER | gdal.OF_READONLY,
                                  allowed_drivers=["GTiff"])
            if dataset is None or dataset.RasterCount != 1:
                raise DataError("terrain must be a readable single-band GeoTIFF")
            band = dataset.GetRasterBand(1)
            if band.DataType != gdal.GDT_Float32:
                raise DataError("terrain requires Float32 samples; numeric conversion is unsupported")
            wkt = _geographic_crs(dataset)
            transform = dataset.GetGeoTransform(can_return_null=True)
            if (transform is None or len(transform) != 6
                    or not all(math.isfinite(v) for v in transform)
                    or transform[1] <= 0 or transform[2] != 0
                    or transform[4] != 0 or transform[5] == 0):
                raise DataError("terrain requires an explicit finite rectilinear transform "
                                "with eastward columns; rotated grids are unsupported")
            source_unit = band.GetUnitType()
            if source_unit.strip().lower() not in ("", "m", "meter", "meters", "metre", "metres"):
                raise DataError("terrain declared units must be meters")
            scale, offset = band.GetScale(), band.GetOffset()
            if scale not in (None, 1.0) or offset not in (None, 0.0):
                raise DataError("packed terrain scale/offset is unsupported; Float32 meters are required")
            registration = dataset.GetMetadataItem("AREA_OR_POINT") or "Area"
            if registration not in ("Area", "Point"):
                raise DataError("unsupported terrain pixel registration")
            values = band.ReadAsArray()
            if values is None or values.dtype != np.dtype(np.float32):
                raise DataError("terrain decoder did not return original Float32 samples")
            support = band.GetMaskBand().ReadAsArray()
            if support is None or support.shape != values.shape:
                raise DataError("terrain decoder did not return a consistent support mask")
            valid = (support != 0) & np.isfinite(values)
            nodata = band.GetNoDataValue()
            if nodata is not None:
                if math.isnan(nodata):
                    valid &= ~np.isnan(values)
                else:
                    valid &= values != nodata
            x = transform[0] + (np.arange(dataset.RasterXSize, dtype=np.float64) + .5) * transform[1]
            y = transform[3] + (np.arange(dataset.RasterYSize, dtype=np.float64) + .5) * transform[5]
            if (not np.isfinite(x).all() or not np.isfinite(y).all()
                    or np.any(x < -180 - 1e-9) or np.any(x > 180 + 1e-9)
                    or np.any(y < -90 - 1e-9) or np.any(y > 90 + 1e-9)):
                raise DataError("terrain sample centers must be conventional geographic "
                                "longitude [-180,180] and latitude [-90,90]")
            source_metadata = dataset.GetMetadata()
            band_metadata = band.GetMetadata()
            declared_datum = (band_metadata.get("VERTICAL_DATUM")
                              or source_metadata.get("VERTICAL_DATUM"))
            metadata = {
                "format": "GeoTIFF", "dataClass": "terrain", "dtype": "Float32",
                "transform": list(transform), "crs": "EPSG:4326", "crsWkt": wkt,
                "axisOrder": "LONGITUDE_LATITUDE", "spacing": [transform[1], abs(transform[5])],
                "pixelRegistration": registration,
                "rowOrder": "NORTH_TO_SOUTH" if transform[5] < 0 else "SOUTH_TO_NORTH",
                "units": "m", "sourceUnit": source_unit or None,
                "unitsSource": "TIFF_BAND" if source_unit else "TERRAIN_INPUT_CONTRACT",
                "verticalDatum": vertical_datum if vertical_datum is not None else declared_datum,
                "verticalDatumSource": ("CALLER" if vertical_datum is not None else
                                        "TIFF_METADATA" if declared_datum else "UNDECLARED"),
                "nodata": nodata, "maskFlags": band.GetMaskFlags(),
                "sourceScale": scale, "sourceOffset": offset, "inputSha256": digest,
                "sourceMetadata": source_metadata, "sourceBandMetadata": band_metadata,
            }
            return RasterData(values, x, y, valid, metadata)
    except RuntimeError as exc:
        raise DataError(f"invalid or unsupported terrain GeoTIFF: {exc}") from exc
    finally:
        band = dataset = None
        gdal.Unlink(path)
