"""CPU-only dependency checks for the isolated RTX package.

inspect_dependencies() records actual versions and runs tiny unchanged ASTRA
parser probes. validate_report() checks an explicit version/origin contract.
No GPU, browser page, source download, or renderer is started by this module.
"""
import argparse
import ctypes as C
import ctypes.util
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import uuid


class DependencyError(ValueError):
    pass


GDAL_APIS = ("ExceptionMgr", "quiet_errors", "config_option",
             "VSIGetMemFileBuffer_unsafe")
NETCDF_APIS = ("nc_open_mem", "nc_close", "nc_inq", "nc_inq_varndims",
               "nc_inq_var", "nc_inq_dimlen", "nc_inq_attname", "nc_inq_att",
               "nc_get_att", "nc_get_att_text", "nc_get_att_string",
               "nc_free_string", "nc_get_var", "nc_inq_var_fill")
VERSION_NAMES = {"python", "numpy", "pillow", "gdal", "libnetcdf",
                 "node", "playwright", "chromium", "ffmpeg", "ffprobe"}
REQUIRED_PROBES = ("terrain", "bathymetryClassic", "bathymetryNetCDF4",
                   "surface", "neutral")


def _run(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True, timeout=15)
    if result.returncode:
        raise DependencyError("version command failed: " + arguments[0])
    if len(result.stdout) > 65536:
        raise DependencyError("version output exceeds bound")
    return result.stdout.strip()


def _astra(repo_root, name):
    source = Path(repo_root).resolve() / "world-simulation-shorts-engine/recovery/astra-cpu-data-v1"
    if not (source / "astra_cpu").is_dir():
        raise DependencyError("packaged ASTRA source directory is missing")
    sys.path.insert(0, str(source))
    try:
        module = importlib.import_module("astra_cpu." + name)
    finally:
        sys.path.pop(0)
    if not Path(module.__file__).resolve().is_relative_to(source):
        raise DependencyError("ASTRA module was imported from another source root")
    return module


def _terrain(np, gdal, osr, repo_root):
    """Exercise the real GDAL NumPy extension and the unchanged bytes parser."""
    filename = "/vsimem/rtx-dependency-" + uuid.uuid4().hex + ".tif"
    # Include signed zero and a payload-bearing NaN; invalid values stay stored.
    bits = np.array([0x80000000, 0x3fc00000, 0x7fc12345,
                     0xc61c3c00, 0x41200000, 0xc0900000], dtype=np.uint32)
    values = bits.view(np.float32).reshape(2, 3)
    transform = [10.0, .5, 0.0, 51.0, 0.0, -.5]
    dataset = None
    try:
        with gdal.ExceptionMgr(), osr.ExceptionMgr(), gdal.config_option("GDAL_TIFF_INTERNAL_MASK", "YES"):
            dataset = gdal.GetDriverByName("GTiff").Create(filename, 3, 2, 1, gdal.GDT_Float32)
            reference = osr.SpatialReference()
            reference.ImportFromEPSG(4326)
            dataset.SetProjection(reference.ExportToWkt())
            dataset.SetGeoTransform(transform)
            dataset.SetMetadataItem("AREA_OR_POINT", "Point")
            band = dataset.GetRasterBand(1)
            band.SetNoDataValue(-9999.0)
            band.WriteArray(values)
            band.CreateMaskBand(gdal.GMF_PER_DATASET)
            band.GetMaskBand().WriteArray(np.array([[255, 255, 255], [255, 0, 255]], dtype=np.uint8))
            dataset.FlushCache()
            band = None
            dataset = None
            raw = bytes(gdal.VSIGetMemFileBuffer_unsafe(filename))
        raster = _astra(repo_root, "terrain").parse_terrain(
            raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
            vertical_datum="SYNTHETIC_TEST_DATUM")
        if raster.values.dtype != np.float32 or not np.array_equal(raster.values.view(np.uint32).ravel(), bits):
            raise DependencyError("Float32 payload bits changed in terrain probe")
        if not np.array_equal(raster.valid, [[True, True, False], [False, False, True]]):
            raise DependencyError("terrain nodata/mask support changed")
        if list(raster.metadata["transform"]) != transform:
            raise DependencyError("PixelIsPoint corner registration changed")
        if not np.array_equal(raster.x, [10.25, 10.75, 11.25]) or not np.array_equal(raster.y, [50.75, 50.25]):
            raise DependencyError("terrain sample centers changed")
        return raster
    finally:
        dataset = None
        gdal.Unlink(filename)
        gdal.Unlink(filename + ".msk")


def _bathymetry(np, library, repo_root, netcdf4):
    """Create a small CF fixture and read it using ASTRA's actual C library."""
    signatures = {
        "nc_create": ([C.c_char_p, C.c_int, C.POINTER(C.c_int)], C.c_int),
        "nc_def_dim": ([C.c_int, C.c_char_p, C.c_size_t, C.POINTER(C.c_int)], C.c_int),
        "nc_def_var": ([C.c_int, C.c_char_p, C.c_int, C.c_int, C.POINTER(C.c_int), C.POINTER(C.c_int)], C.c_int),
        "nc_put_att_text": ([C.c_int, C.c_int, C.c_char_p, C.c_size_t, C.c_char_p], C.c_int),
        "nc_put_att_short": ([C.c_int, C.c_int, C.c_char_p, C.c_int, C.c_size_t, C.POINTER(C.c_short)], C.c_int),
        "nc_enddef": ([C.c_int], C.c_int),
        "nc_put_var_double": ([C.c_int, C.c_int, C.POINTER(C.c_double)], C.c_int),
        "nc_put_var_short": ([C.c_int, C.c_int, C.POINTER(C.c_short)], C.c_int),
        "nc_close": ([C.c_int], C.c_int),
    }
    for name, (args, result) in signatures.items():
        function = getattr(library, name)
        function.argtypes, function.restype = args, result

    def check(code):
        if code:
            raise DependencyError("native NetCDF fixture operation failed: " + str(code))

    with tempfile.TemporaryDirectory(prefix="rtx-netcdf-") as temporary:
        filename = Path(temporary) / "probe.nc"
        ncid = C.c_int()
        check(library.nc_create(os.fsencode(filename), 0x1000 if netcdf4 else 0, C.byref(ncid)))
        opened = True
        try:
            crs = b"EPSG:4326"
            check(library.nc_put_att_text(ncid.value, -1, b"geospatial_bounds_crs", len(crs), crs))
            dimensions, variables = {}, {}
            for name, size in (("lat", 2), ("lon", 3)):
                dimension = C.c_int()
                check(library.nc_def_dim(ncid.value, name.encode(), size, C.byref(dimension)))
                dimensions[name] = dimension.value
                variable = C.c_int()
                dimids = (C.c_int * 1)(dimension.value)
                check(library.nc_def_var(ncid.value, name.encode(), 6, 1, dimids, C.byref(variable)))
                variables[name] = variable.value
                units = b"degrees_north" if name == "lat" else b"degrees_east"
                check(library.nc_put_att_text(ncid.value, variable.value, b"units", len(units), units))
            elevation = C.c_int()
            dimids = (C.c_int * 2)(dimensions["lat"], dimensions["lon"])
            check(library.nc_def_var(ncid.value, b"elevation", 3, 2, dimids, C.byref(elevation)))
            check(library.nc_put_att_text(ncid.value, elevation.value, b"units", 1, b"m"))
            check(library.nc_put_att_text(ncid.value, elevation.value, b"positive", 2, b"up"))
            sentinel = C.c_short(-32767)
            check(library.nc_put_att_short(ncid.value, elevation.value, b"_FillValue", 3, 1, C.byref(sentinel)))
            check(library.nc_enddef(ncid.value))
            check(library.nc_put_var_double(ncid.value, variables["lat"], (C.c_double * 2)(5, 4)))
            check(library.nc_put_var_double(ncid.value, variables["lon"], (C.c_double * 3)(11, 12, 13)))
            expected = [-11, 0, 37, -32767, 10, -2]
            check(library.nc_put_var_short(ncid.value, elevation.value, (C.c_short * 6)(*expected)))
            check(library.nc_close(ncid.value))
            opened = False
            raw = filename.read_bytes()
        finally:
            if opened:
                library.nc_close(ncid.value)
    raster = _astra(repo_root, "bathymetry").parse_bathymetry(
        raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
        vertical_datum="SYNTHETIC_TEST_DATUM")
    if raster.values.dtype != np.int16 or not np.array_equal(raster.values, np.array(expected, dtype=np.int16).reshape(2, 3)):
        raise DependencyError("signed NetCDF storage changed")
    if not np.array_equal(raster.valid, [[True, True, True], [False, True, True]]):
        raise DependencyError("NetCDF nodata support changed")
    if not np.array_equal(raster.x, [11, 12, 13]) or not np.array_equal(raster.y, [5, 4]):
        raise DependencyError("NetCDF source axes changed")


def _surface(np, pillow, repo_root):
    rgba = np.array([[[0, 128, 255, 0], [11, 22, 33, 255]],
                     [[255, 0, 12, 128], [1, 2, 3, 4]]], dtype=np.uint8)
    buffer = io.BytesIO()
    pillow.fromarray(rgba).save(buffer, format="PNG")
    from osgeo import osr
    with osr.ExceptionMgr():
        projection = osr.SpatialReference()
        projection.ImportFromEPSG(4326)
    raster = _astra(repo_root, "surface").parse_surface(
        buffer.getvalue(), "1\n0\n0\n-1\n10\n20\n", projection.ExportToWkt())
    if raster.values.dtype != np.uint8 or not np.array_equal(raster.values, rgba):
        raise DependencyError("raw PNG channels changed")


def inspect_dependencies(repo_root, *, run_native_probes=True):
    """Return actual CPU observations; failures never become GPU success."""
    report = {"schema": "RTX_DEPENDENCY_REPORT_V1", "gpuExecuted": False,
              "pythonExecutable": str(Path(sys.executable).resolve()),
              "pythonMajorMinor": platform.python_version_tuple()[:2],
              "versions": {"python": platform.python_version()},
              "moduleOrigins": {}, "gdalApis": {}, "netcdfApis": {},
              "probes": {}, "encoders": {}, "errors": []}
    np = gdal = osr = image = library = None
    for name, version_name in (("numpy", "numpy"), ("PIL", "pillow"), ("osgeo.gdal", "gdal"), ("osgeo.osr", None)):
        try:
            module = importlib.import_module(name)
            report["moduleOrigins"][name] = str(Path(module.__file__).resolve())
            if version_name:
                report["versions"][version_name] = module.__version__
            if name == "numpy":
                np = module
            elif name == "PIL":
                image = importlib.import_module("PIL.Image")
            elif name == "osgeo.gdal":
                gdal = module
            else:
                osr = module
        except Exception as error:
            report["errors"].append(name + ": " + str(error))
    if gdal and osr:
        report["gdalApis"] = {name: callable(getattr(gdal, name, None)) for name in GDAL_APIS}
        report["gdalApis"]["osr.ExceptionMgr"] = callable(getattr(osr, "ExceptionMgr", None))
    try:
        library_path = ctypes.util.find_library("netcdf")
        if not library_path:
            raise DependencyError("native libnetcdf was not found")
        library = C.CDLL(library_path)
        library.nc_inq_libvers.restype = C.c_char_p
        report["netcdfLibrary"] = library_path
        report["versions"]["libnetcdf"] = library.nc_inq_libvers().decode().split()[0]
        report["netcdfApis"] = {name: callable(getattr(library, name, None)) for name in NETCDF_APIS}
    except Exception as error:
        report["errors"].append("libnetcdf: " + str(error))
    for key, arguments, pattern in (
        ("node", ["node", "--version"], r"^v?(\d+\.\d+\.\d+)$"),
        ("chromium", [os.environ.get("WORLD_ENGINE_CHROMIUM_REAL", "/usr/bin/chromium"), "--version"], r"(?:Chromium|Google Chrome(?: for Testing)?)\s+(\d+\.\d+\.\d+\.\d+)"),
        ("ffmpeg", ["ffmpeg", "-version"], r"^ffmpeg\s+version\s+(\d+(?:\.\d+){1,2})"),
        ("ffprobe", ["ffprobe", "-version"], r"^ffprobe\s+version\s+(\d+(?:\.\d+){1,2})"),
    ):
        try:
            value = _run(arguments)
            match = re.search(pattern, value)
            if not match:
                raise DependencyError("unrecognized " + key + " version output")
            report["versions"][key] = match.group(1)
        except Exception as error:
            report["errors"].append(key + ": " + str(error))
    try:
        encoders = _run(["ffmpeg", "-hide_banner", "-encoders"])
        report["encoders"]["libx264"] = any(
            len(fields) >= 2 and fields[0].startswith("V") and fields[1] == "libx264"
            for fields in (line.split() for line in encoders.splitlines()))
    except Exception as error:
        report["errors"].append("ffmpeg encoders: " + str(error))
    try:
        package = Path(repo_root) / "cinematic-world-map/node_modules/playwright/package.json"
        report["versions"]["playwright"] = json.loads(package.read_text())["version"]
    except Exception as error:
        report["errors"].append("playwright: " + str(error))
    if run_native_probes:
        terrain = None
        operations = {
            "terrain": lambda: _terrain(np, gdal, osr, repo_root),
            "bathymetryClassic": lambda: _bathymetry(np, library, repo_root, False),
            "bathymetryNetCDF4": lambda: _bathymetry(np, library, repo_root, True),
            "surface": lambda: _surface(np, image, repo_root),
        }
        for name, operation in operations.items():
            try:
                result = operation()
                if name == "terrain":
                    terrain = result
                report["probes"][name] = "PASS"
            except Exception as error:
                report["probes"][name] = "FAIL"
                report["errors"].append(name + ": " + str(error))
        try:
            if terrain is None:
                raise DependencyError("terrain probe is required before neutral roundtrip")
            neutral = _astra(repo_root, "neutral")
            restored = neutral.decode_neutral(neutral.encode_neutral(terrain))
            if (not np.array_equal(restored.values.view(np.uint32), terrain.values.view(np.uint32))
                    or not np.array_equal(restored.valid, terrain.valid)):
                raise DependencyError("neutral Float32 payload/mask changed")
            report["probes"]["neutral"] = "PASS"
        except Exception as error:
            report["probes"]["neutral"] = "FAIL"
            report["errors"].append("neutral: " + str(error))
    return report


def validate_report(report, contract):
    """Validate known fields, actual APIs, origin isolation and CPU probe results."""
    required = {"schema", "pythonExecutable", "pythonMajorMinor", "versions",
                "nodeMinimumMajor", "modulePrefixes"}
    if not isinstance(contract, dict) or set(contract) != required:
        raise DependencyError("dependency contract fields are missing or unknown")
    if contract["schema"] != "RTX_DEPENDENCY_CONTRACT_V1":
        raise DependencyError("unsupported dependency contract")
    if not isinstance(contract["pythonExecutable"], str) or not contract["pythonExecutable"].startswith("/"):
        raise DependencyError("absolute Python executable required")
    if not re.fullmatch(r"3\.\d+", str(contract["pythonMajorMinor"])):
        raise DependencyError("explicit Python major.minor required")
    pins = contract["versions"]
    if (not isinstance(pins, dict) or not pins or set(pins) - VERSION_NAMES
            or any(not isinstance(v, str) or not re.fullmatch(r"\d+(?:\.\d+){1,3}", v) for v in pins.values())):
        raise DependencyError("exact known dependency version pins required")
    minimum = contract["nodeMinimumMajor"]
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 22:
        raise DependencyError("Node minimum must be an integer at least 22")
    prefixes = contract["modulePrefixes"]
    if not isinstance(prefixes, list) or not prefixes or any(not isinstance(p, str) or not p.startswith("/") for p in prefixes):
        raise DependencyError("absolute coherent native module prefixes required")
    errors = list(report.get("errors", []))
    if report.get("gpuExecuted") is not False:
        errors.append("dependency report cannot contain GPU execution")
    if report.get("schema") != "RTX_DEPENDENCY_REPORT_V1":
        errors.append("unsupported dependency report")
    if report.get("pythonExecutable") != str(Path(contract["pythonExecutable"]).resolve()):
        errors.append("wrong Python executable")
    if ".".join(report.get("pythonMajorMinor", ())) != contract["pythonMajorMinor"]:
        errors.append("wrong Python ABI")
    actual = report.get("versions", {})
    for name, expected in pins.items():
        if actual.get(name) != expected:
            errors.append(name + " version does not match explicit pin")
    try:
        if int(actual["node"].split(".")[0]) < minimum:
            errors.append("Node version is below required minimum")
    except (KeyError, ValueError, AttributeError):
        errors.append("Node version was not established")
    for name in ("numpy", "PIL", "osgeo.gdal", "osgeo.osr"):
        path = report.get("moduleOrigins", {}).get(name)
        if not isinstance(path, str) or not any(Path(path).is_relative_to(p) for p in prefixes):
            errors.append(name + " origin is outside the coherent native stack")
    for name in (*GDAL_APIS, "osr.ExceptionMgr"):
        if report.get("gdalApis", {}).get(name) is not True:
            errors.append("required GDAL API missing: " + name)
    for name in NETCDF_APIS:
        if report.get("netcdfApis", {}).get(name) is not True:
            errors.append("required native netCDF API missing: " + name)
    for name in REQUIRED_PROBES:
        if report.get("probes", {}).get(name) != "PASS":
            errors.append("CPU dependency probe not passed: " + name)
    for name in ("ffmpeg", "ffprobe"):
        if name not in actual:
            errors.append("required encoder tool missing: " + name)
    if report.get("encoders", {}).get("libx264") is not True:
        errors.append("required CPU encoder libx264 is unavailable")
    return errors


def verify_dependencies(repo_root, contract):
    report = inspect_dependencies(repo_root)
    errors = validate_report(report, contract)
    return {**report, "status": "FAIL" if errors else "PASS", "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        raw = arguments.contract.read_bytes()
        if len(raw) > 65536:
            raise DependencyError("dependency contract exceeds bound")
        result = verify_dependencies(arguments.repo_root, json.loads(raw))
    except (DependencyError, ValueError, OSError) as error:
        result = {"schema": "RTX_DEPENDENCY_REPORT_V1", "status": "FAIL",
                  "gpuExecuted": False, "errors": [str(error)]}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
