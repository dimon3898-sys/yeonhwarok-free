"""Focused dependency and bootstrap checks; never launch a GPU or browser."""
from copy import deepcopy
import ctypes as C
import ctypes.util
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import bootstrap
import verify_dependencies as dependencies

REPO = PACKAGE.parents[2]


def contract():
    return {"schema": "RTX_DEPENDENCY_CONTRACT_V1",
            "pythonExecutable": "/usr/bin/python3", "pythonMajorMinor": "3.12",
            "versions": {"gdal": "3.10.3", "playwright": "1.62.1", "node": "24.19.0"},
            "nodeMinimumMajor": 22, "modulePrefixes": ["/usr/lib/python3/dist-packages"]}


def good_report():
    return {"schema": "RTX_DEPENDENCY_REPORT_V1", "gpuExecuted": False,
            "pythonExecutable": str(Path("/usr/bin/python3").resolve()),
            "pythonMajorMinor": ("3", "12"),
            "versions": {"gdal": "3.10.3", "playwright": "1.62.1", "node": "24.19.0",
                         "ffmpeg": "6.1.1", "ffprobe": "6.1.1"},
            "moduleOrigins": {n: "/usr/lib/python3/dist-packages/" + n.replace(".", "/") + "/__init__.py"
                              for n in ("numpy", "PIL", "osgeo.gdal", "osgeo.osr")},
            "gdalApis": {n: True for n in (*dependencies.GDAL_APIS, "osr.ExceptionMgr")},
            "netcdfApis": {n: True for n in dependencies.NETCDF_APIS},
            "probes": {n: "PASS" for n in dependencies.REQUIRED_PROBES},
            "encoders": {"libx264": True}, "errors": []}


class ContractTests(unittest.TestCase):
    def test_verified_report(self):
        self.assertEqual(dependencies.validate_report(good_report(), contract()), [])

    def test_wrong_exact_version(self):
        report = good_report()
        report["versions"]["gdal"] = "3.6.2"
        self.assertIn("gdal version does not match explicit pin", dependencies.validate_report(report, contract()))

    def test_missing_gdal_context_api(self):
        report = good_report()
        report["gdalApis"]["config_option"] = False
        self.assertIn("required GDAL API missing: config_option", dependencies.validate_report(report, contract()))

    def test_missing_native_netcdf_memory_api(self):
        report = good_report()
        report["netcdfApis"].pop("nc_open_mem")
        self.assertIn("required native netCDF API missing: nc_open_mem", dependencies.validate_report(report, contract()))

    def test_missing_ffmpeg_fails(self):
        report = good_report()
        report["versions"].pop("ffmpeg")
        self.assertIn("required encoder tool missing: ffmpeg", dependencies.validate_report(report, contract()))

    def test_missing_ffprobe_fails(self):
        report = good_report()
        report["versions"].pop("ffprobe")
        self.assertIn("required encoder tool missing: ffprobe", dependencies.validate_report(report, contract()))

    def test_missing_libx264_fails(self):
        report = good_report()
        report["encoders"]["libx264"] = False
        self.assertIn("required CPU encoder libx264 is unavailable", dependencies.validate_report(report, contract()))

    def test_mixed_python_origin(self):
        report = good_report()
        report["moduleOrigins"]["osgeo.gdal"] = "/usr/local/lib/python3.12/site-packages/osgeo/gdal.py"
        self.assertIn("osgeo.gdal origin is outside the coherent native stack", dependencies.validate_report(report, contract()))

    def test_prefix_lookalike_is_rejected(self):
        report = good_report()
        report["moduleOrigins"]["numpy"] = "/usr/lib/python3/dist-packages-other/numpy.py"
        self.assertTrue(any("numpy origin" in e for e in dependencies.validate_report(report, contract())))

    def test_wrong_python_abi(self):
        report = good_report()
        report["pythonMajorMinor"] = ("3", "11")
        self.assertIn("wrong Python ABI", dependencies.validate_report(report, contract()))

    def test_probe_skip_is_not_pass(self):
        report = good_report()
        report["probes"].pop("bathymetryNetCDF4")
        self.assertIn("CPU dependency probe not passed: bathymetryNetCDF4", dependencies.validate_report(report, contract()))

    def test_gpu_execution_cannot_pass(self):
        report = good_report()
        report["gpuExecuted"] = True
        self.assertIn("dependency report cannot contain GPU execution", dependencies.validate_report(report, contract()))

    def test_unknown_contract_field(self):
        value = contract()
        value["allowMissing"] = True
        with self.assertRaises(dependencies.DependencyError):
            dependencies.validate_report(good_report(), value)

    def test_versions_must_be_explicit(self):
        for value in ({}, {"gdal": None}, {"gdal": "latest"}, {"unknown": "1.2"}):
            with self.subTest(value=value), self.assertRaises(dependencies.DependencyError):
                settings = contract()
                settings["versions"] = value
                dependencies.validate_report(good_report(), settings)

    def test_node_limit_bounds(self):
        for minimum in (True, 21, "22"):
            with self.subTest(minimum=minimum), self.assertRaises(dependencies.DependencyError):
                settings = contract()
                settings["nodeMinimumMajor"] = minimum
                dependencies.validate_report(good_report(), settings)

    def test_native_origin_requires_absolute_prefix(self):
        settings = contract()
        settings["modulePrefixes"] = ["site-packages"]
        with self.assertRaises(dependencies.DependencyError):
            dependencies.validate_report(good_report(), settings)

    def test_inspection_errors_remain_failures(self):
        report = good_report()
        report["errors"] = ["native library could not load"]
        self.assertIn("native library could not load", dependencies.validate_report(report, contract()))


class ActualNativeProbeTests(unittest.TestCase):
    """This executor's ABI, not a claim about an unbuilt package image."""
    @classmethod
    def setUpClass(cls):
        cls.np = importlib.import_module("numpy")
        cls.gdal = importlib.import_module("osgeo.gdal")
        cls.osr = importlib.import_module("osgeo.osr")
        cls.image = importlib.import_module("PIL.Image")
        cls.library = C.CDLL(ctypes.util.find_library("netcdf"))

    def test_real_float32_point_tiff_parser(self):
        dependencies._terrain(self.np, self.gdal, self.osr, REPO)

    def test_real_signed_classic_netcdf_parser(self):
        dependencies._bathymetry(self.np, self.library, REPO, False)

    def test_real_signed_netcdf4_parser(self):
        dependencies._bathymetry(self.np, self.library, REPO, True)

    def test_real_rgba_surface_parser(self):
        dependencies._surface(self.np, self.image, REPO)

    def test_real_neutral_payload_roundtrip(self):
        raster = dependencies._terrain(self.np, self.gdal, self.osr, REPO)
        neutral = dependencies._astra(REPO, "neutral")
        restored = neutral.decode_neutral(neutral.encode_neutral(raster))
        self.assertTrue(self.np.array_equal(restored.values.view(self.np.uint32), raster.values.view(self.np.uint32)))
        self.assertTrue(self.np.array_equal(restored.valid, raster.valid))


class BootstrapTests(unittest.TestCase):
    def test_docker_normalizes_private_staged_modes_before_checks(self):
        dockerfile = (PACKAGE / "Dockerfile").read_text()
        normalization = dockerfile.index("chmod -R a+rX /opt/rtx-package")
        verification = dockerfile.index("verify-context --package-root /opt/rtx-package")
        self.assertLess(normalization, verification)
        self.assertNotIn("chmod -R a+rX /workspace", dockerfile)

    def test_directory_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary)
            target = parent / "target"
            target.mkdir()
            link = parent / "link"
            link.symlink_to(target)
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap._directory(link, os.getuid(), os.getgid(), root=False)

    def test_directory_rejects_relative_path(self):
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap._directory("relative", os.getuid(), os.getgid(), root=False)

    def test_private_directory_check(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "runtime"
            checked = bootstrap._directory(path, os.getuid(), os.getgid(), root=False)
            self.assertEqual(checked, path)
            path.chmod(0o755)
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap._directory(path, os.getuid(), os.getgid(), root=False)

    def test_path_layout_is_isolated(self):
        self.assertEqual(bootstrap.REPO, REPO)
        self.assertEqual(bootstrap.ENGINE, REPO / "world-simulation-shorts-engine")


if __name__ == "__main__":
    unittest.main()
