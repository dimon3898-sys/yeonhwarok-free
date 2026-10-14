"""Portable CPU values + georeferencing, not a GPU texture/VRAM allocation."""
from io import BytesIO
import base64
import json
import math

import numpy as np

from .model import DataError, RasterData, sha256


def json_value(value):
    if isinstance(value, bytes):
        return {"__binary_metadata__": base64.b64encode(value).decode('ascii')}
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return {"__numeric_metadata__": "NaN" if math.isnan(value) else ("+Inf" if value > 0 else "-Inf")}
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise DataError("non-JSON raster metadata")


def _decode_metadata(value):
    if isinstance(value, dict):
        if set(value) == {"__binary_metadata__"}:
            try:
                return base64.b64decode(value["__binary_metadata__"], validate=True)
            except (ValueError, TypeError) as error:
                raise DataError("invalid binary metadata marker") from error
        if set(value) == {"__numeric_metadata__"}:
            marker = value["__numeric_metadata__"]
            if marker not in ("NaN", "+Inf", "-Inf"):
                raise DataError("unknown numeric metadata marker")
            return {"NaN": float('nan'), "+Inf": float('inf'), "-Inf": float('-inf')}[marker]
        return {k: _decode_metadata(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode_metadata(v) for v in value]
    return value


def encode_neutral(raster: RasterData) -> bytes:
    metadata = {"schema": "ASTRA_NEUTRAL_RASTER_V1", "metadata": json_value(raster.metadata),
                "numericDtype": raster.values.dtype.str, "shape": list(raster.values.shape),
                "actualBBox": list(raster.bbox), "gpuMemoryLayout": "NOT_ASSIGNED"}
    encoded = json.dumps(metadata, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    output = BytesIO()
    np.savez_compressed(output, values=raster.values, x=raster.x, y=raster.y,
                        valid=raster.valid, metadata=np.frombuffer(encoded, dtype=np.uint8))
    return output.getvalue()


def decode_neutral(data: bytes, *, expected_sha256=None, max_expanded_bytes=256*1024*1024) -> RasterData:
    import zipfile
    if expected_sha256 and sha256(data) != expected_sha256:
        raise DataError("neutral cache SHA-256 mismatch")
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            entries = archive.infolist()
            if (len(entries) != 5 or len({x.filename for x in entries}) != 5
                    or {x.filename for x in entries} != {'values.npy', 'x.npy', 'y.npy', 'valid.npy', 'metadata.npy'}
                    or sum(x.file_size for x in entries) > max_expanded_bytes):
                raise DataError("invalid/oversized neutral archive")
        with np.load(BytesIO(data), allow_pickle=False) as archive:
            marker = archive['metadata']
            if marker.ndim != 1 or marker.dtype != np.uint8 or marker.size > 1024*1024:
                raise DataError("invalid neutral metadata")
            envelope = json.loads(marker.tobytes())
            if envelope.get('schema') != 'ASTRA_NEUTRAL_RASTER_V1':
                raise DataError("unsupported neutral schema")
            values = archive['values']
            if values.dtype.str != envelope['numericDtype'] or list(values.shape) != envelope['shape']:
                raise DataError("neutral dtype/shape mismatch")
            if archive['valid'].dtype != np.bool_:
                raise DataError("neutral support mask must be boolean")
            raster = RasterData(values, archive['x'], archive['y'], archive['valid'],
                                _decode_metadata(envelope['metadata']))
            if not np.allclose(raster.bbox, envelope['actualBBox'], rtol=0, atol=1e-9):
                raise DataError("neutral bbox mismatch")
            return raster
    except DataError:
        raise
    except Exception as error:
        raise DataError("invalid neutral data: " + type(error).__name__) from error
