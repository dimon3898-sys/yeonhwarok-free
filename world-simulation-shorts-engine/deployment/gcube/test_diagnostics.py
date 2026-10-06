"""Synthetic fixed-file facts; no GPU/GL command, real render or remote access."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.gcube import diagnostics as module
from deployment.gcube.diagnostics import DiagnosticsError, build_mobile_diagnostics


PRIVATE = "SYNTHETIC_PRIVATE_OWNER_SECRET_NO_REAL_CREDENTIAL"
GPU_ONE = "GPU-aaaa-bbbb-1111"
GPU_TWO = "GPU-cccc-dddd-2222"


def runtime():
    return {"gpu": {"render_mode": "gpu-required", "gpu_profile": "egl", "gpu_rendering_verified": True,
                    "nvidia_devices": [{"name": "NVIDIA GeForce RTX 5070", "uuid": GPU_ONE,
                                        "driver_version": "570.124.04", "memory_total_mib": 12288}],
                    "webgl": {"renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 5070, OpenGL 4.6)",
                              "vendor": "Google Inc. (NVIDIA)", "context_version": 2, "draw_passed": True},
                    "cuda": {"driver_supported_cuda_max_version": "12.8",
                             "toolkit": {"status": "not_detected", "version": None, "nvcc_present": False}},
                    "speedup_measured": False},
            "start": {"server_boot_seconds": 0}, "storage": {"root": "/private/" + PRIVATE},
            "owner": PRIVATE, "environment": {"WORLD_ENGINE_OWNER_CODE": PRIVATE},
            "auth_cookie": PRIVATE}


def sample(t, usage, *, util=0, vram=0, memory=0, peak=0, at="2026-10-06T10:00:00+00:00"):
    return {"at_utc": at, "monotonic_seconds": t, "cpu_stat": f"usage_usec {usage}\nuser_usec 0\nsystem_usec 0",
            "cpu_max": "200000 100000", "memory_current": str(memory), "memory_peak": str(peak),
            "memory_max": "max", "device_wide_gpu_samples": [f"{GPU_ONE}, {util}, {vram}, 12288"],
            "provider_points_consumed": 999999, "password": PRIVATE}


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wss-gcube-diagnostic-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 10, 6, 10, 0, 10, tzinfo=timezone.utc)
        self.write_runtime(runtime())

    def write_runtime(self, value):
        (self.root / "gcube-runtime.json").write_text(json.dumps(value))

    def session(self, rows, *, name=None, mtime=None):
        folder = self.root / "gcube-sessions"
        folder.mkdir(exist_ok=True)
        path = folder / (name or "session_" + "a" * 32 + ".jsonl")
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def report(self):
        return build_mobile_diagnostics(self.root, now_utc=self.now)

    def assert_private_data_absent(self, report):
        text = json.dumps(report)
        for value in (PRIVATE, GPU_ONE, GPU_TWO, str(self.root), "session_" + "a" * 32):
            self.assertNotIn(value, text)
        self.assertIsNone(report["provider_points_consumed"])
        self.assertIsNone(report["actual_gpu_cloud_video_benchmark"])
        self.assertFalse(report["gpu_cloud_speedup_measured"])
        self.assertEqual(report["original_benchmark_backend"], "CPU_LOCAL")
        self.assertFalse(report["original_measurements_modified"])
        self.assertFalse(report["commands_executed"])
        self.assertFalse(report["project_files_inspected"])

    def test_runtime_gpu_model_driver_cuda_identity_are_whitelisted_without_uuid(self):
        report = self.report()
        gpu = report["runtime"]
        self.assertEqual(gpu["render_mode"], "gpu-required")
        self.assertEqual(gpu["nvidia_devices"][0]["model"], "NVIDIA GeForce RTX 5070")
        self.assertEqual(gpu["nvidia_devices"][0]["driver_version"], "570.124.04")
        self.assertEqual(gpu["nvidia_devices"][0]["vram_total_mib"], 12288)
        self.assertEqual(gpu["cuda"]["driver_supported_cuda_max_version"], "12.8")
        self.assertIsNone(gpu["cuda"]["toolkit_version"])
        self.assertFalse(gpu["cuda"]["driver_maximum_is_toolkit_version"])
        self.assertEqual(gpu["server_boot_seconds"], 0)
        self.assert_private_data_absent(report)

    def test_actual_cpu_software_identity_never_claims_gpu_even_hardware_visible(self):
        value = runtime()
        value["gpu"].update(render_mode="cpu", gpu_rendering_verified=False)
        value["gpu"]["webgl"]["renderer"] = "ANGLE (Google, SwiftShader Device, SwiftShader driver)"
        self.write_runtime(value)
        report = self.report()
        self.assertEqual(report["runtime"]["render_mode"], "cpu")
        self.assertFalse(report["runtime"]["recorded_startup_gpu_verification"])
        self.assertTrue(report["runtime"]["webgl"]["cpu_software_renderer_recorded"])
        self.assert_private_data_absent(report)

    def test_real_tesla_model_and_pcie_renderer_suffix_do_not_look_like_absolute_paths(self):
        value = runtime()
        value["gpu"]["nvidia_devices"][0]["name"] = "Tesla T4"
        value["gpu"]["webgl"]["renderer"] = "ANGLE (NVIDIA, NVIDIA Tesla T4/PCIe/SSE2, OpenGL 4.6)"
        self.write_runtime(value)
        report = self.report()
        self.assertEqual(report["runtime"]["nvidia_devices"][0]["model"], "Tesla T4")
        self.assertIn("/PCIe/SSE2", report["runtime"]["webgl"]["renderer"])
        self.assert_private_data_absent(report)

    def test_cpu_average_uses_usage_usec_and_monotonic_span_in_correct_units(self):
        self.session([sample(100, 0), sample(105, 10_000_000), sample(110, 20_000_000)])
        report = self.report()
        cpu = report["session"]["cpu"]
        self.assertEqual(cpu["usage_delta_usec"], 20_000_000)
        self.assertEqual(cpu["usage_monotonic_span_seconds"], 10)
        self.assertEqual(cpu["average_cores"], 2)
        self.assertEqual(cpu["average_percent_one_core"], 200)
        self.assertEqual(cpu["quota_cores"], 2)
        self.assertEqual(report["session"]["sample_intervals_seconds"], {"count": 2, "min": 5, "max": 5, "average": 5})
        self.assertEqual(report["session"]["last_sample_age_seconds"], 10)

    def test_zero_current_gpu_cpu_and_ram_samples_are_measured_zero_not_none(self):
        self.session([sample(1, 0), sample(6, 0)])
        report = self.report()
        readings = report["session"]["gpu"]["devices"][0]
        self.assertEqual(readings["current_utilization_percent"], 0)
        self.assertEqual(readings["peak_utilization_percent"], 0)
        self.assertEqual(readings["current_vram_used_mib"], 0)
        self.assertEqual(report["session"]["memory"]["current_bytes"], 0)
        self.assertEqual(report["session"]["cpu"]["average_cores"], 0)
        self.assert_private_data_absent(report)

    def test_tiny_finite_span_does_not_serialize_infinite_cpu_rates(self):
        for span, usage in ((float.fromhex("0x0.0000000000001p-1022"), 1),
                            (float.fromhex("0x0.0000000000001p-1022"), 2**63 - 1),
                            (1e-313, 1)):
            self.session([sample(0, 0), sample(span, usage)])
            with self.subTest(span=span, usage=usage):
                report = self.report()
                cpu = report["session"]["cpu"]
                self.assertEqual(cpu["usage_delta_usec"], usage)
                self.assertEqual(cpu["usage_monotonic_span_seconds"], span)
                self.assertIsNone(cpu["average_cores"])
                self.assertIsNone(cpu["average_percent_one_core"])
                self.assertIn("CPU_RATE_NONFINITE", report["session"]["measurement_warnings"])
                json.dumps(report, allow_nan=False)
                self.assert_private_data_absent(report)

    def test_tiny_finite_span_with_finite_rate_and_zero_rate_remain_measured(self):
        for span, usage in ((1e-300, 1), (float.fromhex("0x0.0000000000001p-1022"), 0)):
            self.session([sample(0, 0), sample(span, usage)])
            with self.subTest(span=span, usage=usage):
                report = self.report()
                cpu = report["session"]["cpu"]
                self.assertEqual(cpu["average_cores"], usage / 1_000_000 / span)
                self.assertEqual(cpu["average_percent_one_core"], cpu["average_cores"] * 100)
                self.assertNotIn("CPU_RATE_NONFINITE", report["session"]["measurement_warnings"])
                json.dumps(report, allow_nan=False)

    def test_extreme_raw_values_leave_all_returned_numeric_statistics_finite(self):
        maximum = 2**63 - 1
        rows = [sample(0, 0), sample(maximum, maximum, memory=maximum, peak=maximum)]
        rows[-1]["cpu_max"] = f"{maximum} 1"
        self.session(rows)
        report = self.report()
        json.dumps(report, allow_nan=False)
        self.assertEqual(report["session"]["cpu"]["quota_cores"], maximum / 1)
        def inspect(value):
            if isinstance(value, float):
                self.assertTrue(math.isfinite(value))
            elif isinstance(value, dict):
                for item in value.values():
                    inspect(item)
            elif isinstance(value, list):
                for item in value:
                    inspect(item)
        inspect(report)
        rows[-1]["monotonic_seconds"] = 10**1000
        rows[-1]["cpu_stat"] = "usage_usec " + str(10**1000)
        rows[-1]["cpu_max"] = str(10**1000) + " 1"
        self.session(rows)
        report = self.report()
        self.assertIsNone(report["session"]["cpu"]["average_cores"])
        self.assertIsNone(report["session"]["cpu"]["quota_cores"])
        json.dumps(report, allow_nan=False)
        inspect(report)

    def test_gpu_peak_and_latest_current_are_distinct_and_device_wide(self):
        self.session([sample(1, 0, util=90, vram=2048), sample(6, 1_000_000, util=0, vram=0)])
        report = self.report()
        device = report["session"]["gpu"]["devices"][0]
        self.assertEqual(device["peak_utilization_percent"], 90)
        self.assertEqual(device["current_utilization_percent"], 0)
        self.assertEqual(device["peak_vram_used_mib"], 2048)
        self.assertEqual(device["current_vram_used_mib"], 0)
        self.assertIn("not exclusive", report["gpu_util_scope"])
        self.assertIn("latest recorded", report["session"]["gpu"]["current_sample_scope"])

    def test_latest_missing_gpu_query_is_unknown_instead_of_reusing_stale_current(self):
        rows = [sample(1, 0, util=90), sample(6, 1_000_000)]
        rows[-1].pop("device_wide_gpu_samples")
        self.session(rows)
        device = self.report()["session"]["gpu"]["devices"][0]
        self.assertIsNone(device["current_utilization_percent"])
        self.assertEqual(device["peak_utilization_percent"], 90)

    def test_memory_sample_peak_and_cgroup_lifetime_peak_are_distinguished(self):
        self.session([sample(1, 0, memory=100, peak=1000), sample(6, 1_000_000, memory=300, peak=1000)])
        memory = self.report()["session"]["memory"]
        self.assertEqual(memory["current_bytes"], 300)
        self.assertEqual(memory["maximum_sampled_current_bytes"], 300)
        self.assertEqual(memory["reported_cgroup_peak_bytes"], 1000)
        self.assertIn("may predate", memory["peak_scope"])
        self.assertTrue(memory["limit_unbounded"])
        self.assertIsNone(memory["limit_bytes"])

    def test_counter_reset_or_missing_monotonic_prevents_cpu_average(self):
        for kind in ("reset", "missing_time", "equal_time", "only_one"):
            rows = [sample(1, 100), sample(6, 200)]
            if kind == "reset":
                rows[-1]["cpu_stat"] = "usage_usec 0"
            elif kind == "missing_time":
                rows[-1].pop("monotonic_seconds")
            elif kind == "equal_time":
                rows[-1]["monotonic_seconds"] = 1
            else:
                rows = rows[:1]
            self.session(rows)
            with self.subTest(kind=kind):
                self.assertIsNone(self.report()["session"]["cpu"]["average_cores"])

    def test_latest_session_only_never_merges_cpu_counters_across_sessions(self):
        self.session([sample(1, 0, util=100), sample(6, 1_000_000, util=100)],
                     name="session_" + "b" * 32 + ".jsonl", mtime=100)
        self.session([sample(100, 0), sample(105, 0)], mtime=200)
        report = self.report()
        self.assertEqual(report["session"]["sample_count"], 2)
        self.assertEqual(report["session"]["cpu"]["average_cores"], 0)
        self.assertEqual(report["session"]["gpu"]["devices"][0]["peak_utilization_percent"], 0)

    def test_file_count_rows_and_tail_byte_windows_are_bounded_and_declared(self):
        for i in range(12):
            self.session([sample(1, 0), sample(6, 0)],
                         name=f"session_{i:032x}.jsonl", mtime=i + 100)
        report = self.report()
        self.assertEqual(report["session"]["files_considered"], module.MAX_SESSION_FILES)
        self.assertTrue(report["session"]["file_selection_limited"])
        rows = [sample(i * 5, i * 1_000_000) for i in range(10)]
        self.session(rows, mtime=300)
        with patch.object(module, "MAX_SESSION_ROWS", 3):
            report = self.report()
        self.assertEqual(report["session"]["sample_count"], 3)
        self.assertTrue(report["session"]["sample_window_truncated"])
        with patch.object(module, "MAX_SESSION_BYTES", 1200):
            report = self.report()
        self.assertLessEqual(report["session"]["sample_count"], 4)
        self.assertTrue(report["session"]["sample_window_truncated"])

    def test_incomplete_current_writer_row_is_skipped_without_body_leak(self):
        path = self.session([sample(1, 0)])
        with path.open("ab") as stream:
            stream.write(b'{"password":"' + PRIVATE.encode())
        report = self.report()
        self.assertEqual(report["session"]["sample_count"], 1)
        self.assertTrue(report["session"]["incomplete_last_row_skipped"])
        self.assert_private_data_absent(report)

    def test_malformed_complete_session_or_runtime_returns_fixed_error_code(self):
        path = self.session([])
        path.write_text(PRIVATE + "\n")
        with self.assertRaises(DiagnosticsError) as error:
            self.report()
        self.assertEqual(error.exception.code, "DIAGNOSTIC_SESSION_INVALID")
        self.assertNotIn(PRIVATE, str(error.exception))
        (self.root / "gcube-runtime.json").write_text(PRIVATE)
        with self.assertRaises(DiagnosticsError) as error:
            self.report()
        self.assertEqual(error.exception.code, "DIAGNOSTIC_RUNTIME_INVALID")

    def test_deeply_nested_json_returns_fixed_error_without_native_parser_detail(self):
        (self.root / "gcube-runtime.json").write_text("[" * 2000 + "0" + "]" * 2000)
        with self.assertRaises(DiagnosticsError) as error:
            self.report()
        self.assertEqual(error.exception.code, "DIAGNOSTIC_RUNTIME_INVALID")
        self.write_runtime(runtime())
        self.session([]).write_text("[" * 2000 + "0" + "]" * 2000 + "\n")
        with self.assertRaises(DiagnosticsError) as error:
            self.report()
        self.assertEqual(error.exception.code, "DIAGNOSTIC_SESSION_INVALID")

    def test_symlink_runtime_sessions_directory_and_session_file_are_rejected(self):
        outside = self.root / "outside-secret.json"
        outside.write_text(PRIVATE)
        path = self.root / "gcube-runtime.json"
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaises(DiagnosticsError):
            self.report()
        path.unlink()
        self.write_runtime(runtime())
        directory = self.root / "gcube-sessions"
        directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(DiagnosticsError):
            self.report()
        directory.unlink()
        directory.mkdir()
        (directory / ("session_" + "a" * 32 + ".jsonl")).symlink_to(outside)
        with self.assertRaises(DiagnosticsError):
            self.report()
        self.assertEqual(outside.read_text(), PRIVATE)

    def test_absolute_path_owner_uuid_and_unexpected_fields_in_identities_are_not_echoed(self):
        value = runtime()
        value["gpu"]["webgl"]["renderer"] = "ANGLE " + GPU_ONE + " /private/" + PRIVATE
        value["gpu"]["nvidia_devices"][0]["name"] = "NVIDIA " + PRIVATE
        value["gpu"]["nvidia_devices"][0]["driver_version"] = PRIVATE
        value["gpu"]["cuda"]["toolkit"]["version"] = PRIVATE
        self.write_runtime(value)
        report = self.report()
        self.assertIsNone(report["runtime"]["webgl"]["renderer"])
        self.assertIsNone(report["runtime"]["nvidia_devices"][0]["model"])
        self.assert_private_data_absent(report)

    def test_bad_scalar_types_are_redacted_and_not_printed_as_native_errors(self):
        value = runtime()
        value["gpu"]["render_mode"] = {"secret": PRIVATE}
        value["gpu"]["gpu_profile"] = [PRIVATE]
        value["gpu"]["webgl"]["context_version"] = {"secret": PRIVATE}
        value["gpu"]["cuda"]["toolkit"]["status"] = [PRIVATE]
        value["start"]["server_boot_seconds"] = 10**1000
        self.write_runtime(value)
        report = self.report()
        self.assertEqual(report["runtime"]["render_mode"], "unknown")
        self.assertIsNone(report["runtime"]["server_boot_seconds"])
        self.assert_private_data_absent(report)

    def test_gpu_csv_invalid_values_fail_closed_without_uuid_or_csv_echo(self):
        for bad in ("", PRIVATE, f"{GPU_ONE}, NaN, 0, 12288", f"{GPU_ONE}, 101, 0, 12288",
                    f"{GPU_ONE}, 0, 14000, 12288"):
            row = sample(1, 0)
            row["device_wide_gpu_samples"] = [bad]
            self.session([row])
            with self.subTest(value=bad), self.assertRaises(DiagnosticsError) as error:
                self.report()
            self.assertEqual(error.exception.code, "DIAGNOSTIC_GPU_SAMPLE_INVALID")
            self.assertNotIn(PRIVATE, str(error.exception))
            self.assertNotIn(GPU_ONE, str(error.exception))

    def test_gpu_na_utilization_is_unknown_not_zero(self):
        row = sample(1, 0)
        row["device_wide_gpu_samples"] = [f"{GPU_ONE}, N/A, 0, 12288"]
        self.session([row])
        device = self.report()["session"]["gpu"]["devices"][0]
        self.assertIsNone(device["current_utilization_percent"])
        self.assertIsNone(device["peak_utilization_percent"])
        self.assertEqual(device["current_vram_used_mib"], 0)

    def test_multiple_devices_follow_internal_identity_without_publishing_uuid(self):
        value = runtime()
        second = deepcopy(value["gpu"]["nvidia_devices"][0])
        second["uuid"] = GPU_TWO
        value["gpu"]["nvidia_devices"].append(second)
        self.write_runtime(value)
        rows = [sample(1, 0), sample(6, 1_000_000)]
        rows[0]["device_wide_gpu_samples"] = [f"{GPU_ONE}, 90, 10, 12288", f"{GPU_TWO}, 20, 0, 12288"]
        rows[1]["device_wide_gpu_samples"] = [f"{GPU_TWO}, 70, 50, 12288", f"{GPU_ONE}, 0, 0, 12288"]
        self.session(rows)
        report = self.report()
        devices = report["session"]["gpu"]["devices"]
        self.assertEqual([d["current_utilization_percent"] for d in devices], [0, 70])
        self.assertEqual([d["peak_utilization_percent"] for d in devices], [90, 70])
        self.assert_private_data_absent(report)

    def test_unrelated_project_directories_and_files_are_never_read(self):
        directory = self.root / "projects/project_secret"
        directory.mkdir(parents=True)
        (directory / "scene_plan.json").write_text(PRIVATE)
        folder = self.root / "gcube-sessions"
        folder.mkdir()
        (folder / "private-unknown-file.json").write_text(PRIVATE)
        report = self.report()
        self.assertFalse(report["session"]["available"])
        self.assert_private_data_absent(report)
        self.assertEqual((directory / "scene_plan.json").read_text(), PRIVATE)

    def test_oversized_runtime_or_sample_and_fifo_are_rejected(self):
        path = self.root / "gcube-runtime.json"
        path.write_bytes(b"x" * (module.MAX_RUNTIME_BYTES + 1))
        with self.assertRaises(DiagnosticsError) as error:
            self.report()
        self.assertEqual(error.exception.code, "DIAGNOSTIC_FILE_LIMIT")
        self.write_runtime(runtime())
        path = self.session([])
        path.write_text('{"secret":"' + "x" * module.MAX_LINE_BYTES + '"}\n')
        with self.assertRaises(DiagnosticsError) as error:
            self.report()
        self.assertEqual(error.exception.code, "DIAGNOSTIC_SAMPLE_LIMIT")
        path.unlink()
        os.mkfifo(path)
        with self.assertRaises(DiagnosticsError):
            self.report()

    def test_cpu_local_benchmark_label_and_unknown_provider_billing_are_never_overridden(self):
        value = runtime()
        value.update(provider_points_consumed=1234, original_benchmark_backend="GPU_CLOUD")
        value["gpu"]["speedup_measured"] = True
        self.write_runtime(value)
        report = self.report()
        self.assert_private_data_absent(report)


if __name__ == "__main__":
    unittest.main()
