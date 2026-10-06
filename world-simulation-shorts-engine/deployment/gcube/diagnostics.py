"""Bounded, owner-downloadable facts from fixed GCube runtime/session files.

No command, renderer, environment dump or project-file inspection is performed.
GPU utilization belongs to the allocated device, not exclusively to this app.
These startup/resource records are not a completed-video speed benchmark.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import re
import stat


MAX_RUNTIME_BYTES = 256 * 1024
MAX_SESSION_BYTES = 2 * 1024 * 1024
MAX_SESSION_ROWS = 4096
MAX_LINE_BYTES = 16384
MAX_SESSION_FILES = 8
MAX_DIRECTORY_ENTRIES = 128
MAX_DEVICES = 8
SESSION_NAME = re.compile(r"session_[a-f0-9]{32}\.jsonl")
VERSION = re.compile(r"\d+(?:\.\d+){1,3}")
GPU_ID = re.compile(r"GPU-[a-fA-F0-9-]{4,80}")
UUID_TEXT = re.compile(r"GPU-[a-fA-F0-9-]{4,80}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}")
GPU_SCOPE = "allocated_device_wide; not exclusive process attribution"


class DiagnosticsError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _safe_directory(path):
    if not path.is_absolute() or ".." in path.parts:
        raise DiagnosticsError("DIAGNOSTIC_UNSAFE_PATH")
    try:
        for item in [*reversed(path.parents), path]:
            value = item.lstat()
            if stat.S_ISLNK(value.st_mode) or not stat.S_ISDIR(value.st_mode):
                raise DiagnosticsError("DIAGNOSTIC_UNSAFE_PATH")
    except OSError:
        raise DiagnosticsError("DIAGNOSTIC_UNSAFE_PATH") from None


def _read_file(path, maximum, *, tail=False):
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        value = os.fstat(fd)
        if not stat.S_ISREG(value.st_mode):
            raise DiagnosticsError("DIAGNOSTIC_UNSAFE_PATH")
        truncated = value.st_size > maximum
        if truncated and not tail:
            raise DiagnosticsError("DIAGNOSTIC_FILE_LIMIT")
        if truncated:
            os.lseek(fd, value.st_size - maximum, os.SEEK_SET)
        data = bytearray()
        while len(data) < maximum:
            chunk = os.read(fd, min(65536, maximum - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        return bytes(data), truncated
    except DiagnosticsError:
        raise
    except OSError:
        raise DiagnosticsError("DIAGNOSTIC_READ_FAILED") from None
    finally:
        if fd is not None:
            os.close(fd)


def _number(value, *, maximum=2**63 - 1, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not 0 <= value <= maximum or (isinstance(value, float) and not math.isfinite(value)) or (integer and int(value) != value):
        return None
    return int(value) if integer else value


def _integer_text(value):
    return int(value) if isinstance(value, str) and re.fullmatch(r"\d{1,19}", value) and int(value) <= 2**63 - 1 else None


def _version(value):
    return value if isinstance(value, str) and len(value) <= 32 and VERSION.fullmatch(value) else None


def _identity(value):
    normalized = value.replace("/PCIe/SSE2", "") if isinstance(value, str) else value
    if (not isinstance(value, str) or not 1 <= len(value) <= 256 or not value.isascii() or
            not re.fullmatch(r"[A-Za-z0-9 .,_()+:-]+", normalized) or UUID_TEXT.search(value) or
            re.search(r"password|token|cookie|secret|authorization|owner", value, re.I) or
            not re.search(r"\bNVIDIA\b|\bTesla\b|\bQuadro\b|\bGeForce\b|\bANGLE\b|\bGoogle\b|\bSwiftShader\b|\bllvmpipe\b|\bMesa\b|\bIntel\b|\bAMD\b|\bATI\b|\blavapipe\b|\bsoftpipe\b", value, re.I)):
        return None
    return value


def _runtime_summary(value):
    gpu = value.get("gpu") if isinstance(value.get("gpu"), dict) else {}
    webgl = gpu.get("webgl") if isinstance(gpu.get("webgl"), dict) else {}
    cuda = gpu.get("cuda") if isinstance(gpu.get("cuda"), dict) else {}
    toolkit = cuda.get("toolkit") if isinstance(cuda.get("toolkit"), dict) else {}
    start = value.get("start") if isinstance(value.get("start"), dict) else {}
    mode = gpu.get("render_mode")
    mode = mode if isinstance(mode, str) and mode in {"cpu", "gpu-required"} else "unknown"
    hardware, device_order = [], []
    for record in (gpu.get("nvidia_devices") if isinstance(gpu.get("nvidia_devices"), list) else [])[:MAX_DEVICES]:
        if not isinstance(record, dict):
            continue
        identifier = record.get("uuid")
        device_order.append(identifier if isinstance(identifier, str) and GPU_ID.fullmatch(identifier) else None)
        hardware.append({"device_index": len(hardware) + 1, "model": _identity(record.get("name")),
                         "driver_version": _version(record.get("driver_version")),
                         "vram_total_mib": _number(record.get("memory_total_mib"))})
    profile = gpu.get("gpu_profile")
    profile = profile if isinstance(profile, str) and profile in {"egl", "vulkan", "egl-nvidia"} else None
    context = webgl.get("context_version")
    context = context if isinstance(context, int) and not isinstance(context, bool) and context in {1, 2} else None
    toolkit_status = toolkit.get("status")
    toolkit_status = toolkit_status if isinstance(toolkit_status, str) and toolkit_status in {"detected", "not_detected", "version_unknown"} else "unknown"
    renderer = _identity(webgl.get("renderer"))
    return {
        "render_mode": mode, "gpu_profile": profile,
        "recorded_startup_gpu_verification": gpu.get("gpu_rendering_verified") is True and mode == "gpu-required",
        "webgl": {"renderer": renderer, "vendor": _identity(webgl.get("vendor")),
                  "context_version": context,
                  "draw_passed_recorded": webgl.get("draw_passed") is True,
                  "cpu_software_renderer_recorded": bool(renderer and re.search(r"SwiftShader|llvmpipe|softpipe|lavapipe", renderer, re.I))},
        "nvidia_devices": hardware,
        "cuda": {"driver_supported_cuda_max_version": _version(cuda.get("driver_supported_cuda_max_version")),
                 "toolkit_version": _version(toolkit.get("version")),
                 "toolkit_status": toolkit_status,
                 "nvcc_present_recorded": toolkit.get("nvcc_present") is True,
                 "driver_maximum_is_toolkit_version": False, "cuda_required_by_renderer": False},
        "server_boot_seconds": _number(start.get("server_boot_seconds")),
    }, device_order


def _session_rows(root):
    folder = root / "gcube-sessions"
    if not folder.exists() and not folder.is_symlink():
        return [], {"available": False, "files_considered": 0, "file_selection_limited": False,
                    "sample_window_truncated": False, "incomplete_last_row_skipped": False}
    _safe_directory(folder)
    candidates, scanned, count, scan_limited = [], 0, 0, False
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                scanned += 1
                if scanned > MAX_DIRECTORY_ENTRIES:
                    scan_limited = True
                    break
                if not SESSION_NAME.fullmatch(entry.name):
                    continue
                value = entry.stat(follow_symlinks=False)
                if not stat.S_ISREG(value.st_mode):
                    raise DiagnosticsError("DIAGNOSTIC_UNSAFE_PATH")
                count += 1
                candidates.append((value.st_mtime_ns, entry.name))
                candidates.sort(reverse=True)
                del candidates[MAX_SESSION_FILES:]
    except OSError:
        raise DiagnosticsError("DIAGNOSTIC_READ_FAILED") from None
    info = {"available": bool(candidates), "files_considered": min(count, MAX_SESSION_FILES),
            "file_selection_limited": scan_limited or count > MAX_SESSION_FILES,
            "sample_window_truncated": False, "incomplete_last_row_skipped": False,
            "selection": "latest_recorded_session; not proof of an active render"}
    if not candidates:
        return [], info
    data, truncated = _read_file(folder / candidates[0][1], MAX_SESSION_BYTES, tail=True)
    if truncated:
        data = data.partition(b"\n")[2]
    lines = data.splitlines(keepends=True)
    if lines and not lines[-1].endswith(b"\n"):
        lines.pop()
        info["incomplete_last_row_skipped"] = True
    info["sample_window_truncated"] = truncated or len(lines) > MAX_SESSION_ROWS
    rows = []
    for line in lines[-MAX_SESSION_ROWS:]:
        if len(line) > MAX_LINE_BYTES:
            raise DiagnosticsError("DIAGNOSTIC_SAMPLE_LIMIT")
        try:
            value = json.loads(line)
        except (ValueError, UnicodeError, RecursionError):
            raise DiagnosticsError("DIAGNOSTIC_SESSION_INVALID") from None
        if not isinstance(value, dict):
            raise DiagnosticsError("DIAGNOSTIC_SESSION_INVALID")
        rows.append(value)
    return rows, info


def _usage(row):
    text = row.get("cpu_stat")
    if not isinstance(text, str) or len(text) > 4096:
        return None
    values = [line.split()[1] for line in text.splitlines()
              if len(line.split()) == 2 and line.split()[0] == "usage_usec"]
    return _integer_text(values[0]) if len(values) == 1 else None


def _gpu_rows(row):
    records = {}
    values = row.get("device_wide_gpu_samples")
    if not isinstance(values, list):
        return records
    if len(values) > MAX_DEVICES:
        raise DiagnosticsError("DIAGNOSTIC_DEVICE_LIMIT")
    for text in values:
        if not isinstance(text, str) or len(text) > 512:
            raise DiagnosticsError("DIAGNOSTIC_GPU_SAMPLE_INVALID")
        try:
            columns = next(csv.reader(io.StringIO(text)))
        except (csv.Error, StopIteration):
            raise DiagnosticsError("DIAGNOSTIC_GPU_SAMPLE_INVALID") from None
        if len(columns) != 4:
            raise DiagnosticsError("DIAGNOSTIC_GPU_SAMPLE_INVALID")
        identifier, utilization, used, total = [part.strip() for part in columns]
        if not GPU_ID.fullmatch(identifier) or identifier in records:
            raise DiagnosticsError("DIAGNOSTIC_GPU_SAMPLE_INVALID")
        unavailable_utilization = utilization in {"N/A", "[N/A]", "Not Supported"}
        try:
            utilization = None if unavailable_utilization else _number(float(utilization), maximum=100)
            used, total = _number(float(used)), _number(float(total))
        except ValueError:
            raise DiagnosticsError("DIAGNOSTIC_GPU_SAMPLE_INVALID") from None
        if used is None or total is None or used > total or (utilization is None and not unavailable_utilization):
            raise DiagnosticsError("DIAGNOSTIC_GPU_SAMPLE_INVALID")
        records[identifier] = {"utilization_percent": utilization, "vram_used_mib": used, "vram_total_mib": total}
    return records


def _resources(rows, order, *, now):
    times = [_number(row.get("monotonic_seconds")) for row in rows]
    valid_times = [number for number in times if number is not None]
    increasing = len(valid_times) == len(rows) and all(b > a for a, b in zip(valid_times, valid_times[1:]))
    intervals = [b - a for a, b in zip(valid_times, valid_times[1:]) if b > a]
    usage = [(_number(row.get("monotonic_seconds")), _usage(row)) for row in rows]
    points = [(t, u) for t, u in usage if t is not None and u is not None]
    counter_ok = all(b[1] >= a[1] for a, b in zip(points, points[1:]))
    span = points[-1][0] - points[0][0] if len(points) >= 2 and increasing else None
    delta = points[-1][1] - points[0][1] if span is not None and span > 0 and counter_ok else None
    cores = delta / 1_000_000 / span if delta is not None else None
    percent = cores * 100 if cores is not None else None
    # Finite inputs can still overflow when divided by a subnormal time span.
    # Keep the measured counter/span, but never serialize an infinite rate.
    nonfinite_rate = cores is not None and (not math.isfinite(cores) or not math.isfinite(percent))
    if nonfinite_rate:
        cores = percent = None
    current = rows[-1] if rows else {}
    memory_current = [_integer_text(row.get("memory_current")) for row in rows]
    memory_peak = [_integer_text(row.get("memory_peak")) for row in rows]
    quota = current.get("cpu_max")
    quota_parts = quota.split() if isinstance(quota, str) and len(quota) <= 128 else []
    quota_value = _integer_text(quota_parts[0]) if len(quota_parts) == 2 else None
    period = _integer_text(quota_parts[1]) if len(quota_parts) == 2 else None
    device_samples = [_gpu_rows(row) for row in rows]
    identifiers = [identifier for identifier in order if identifier is not None]
    for readings in device_samples:
        for identifier in readings:
            if identifier not in identifiers:
                identifiers.append(identifier)
    if len(identifiers) > MAX_DEVICES:
        raise DiagnosticsError("DIAGNOSTIC_DEVICE_LIMIT")
    gpu = []
    latest = device_samples[-1] if device_samples else {}
    for identifier in identifiers:
        readings = [record[identifier] for record in device_samples if identifier in record]
        current_gpu = latest.get(identifier, {})
        utilization = [r["utilization_percent"] for r in readings if r["utilization_percent"] is not None]
        used = [r["vram_used_mib"] for r in readings]
        gpu.append({"device_index": len(gpu) + 1, "sample_count": len(readings),
                    "utilization_sample_count": len(utilization),
                    "current_utilization_percent": current_gpu.get("utilization_percent"),
                    "peak_utilization_percent": max(utilization) if utilization else None,
                    "current_vram_used_mib": current_gpu.get("vram_used_mib"),
                    "peak_vram_used_mib": max(used) if used else None,
                    "current_vram_total_mib": current_gpu.get("vram_total_mib")})
    age = None
    try:
        at = current.get("at_utc")
        stamp = datetime.fromisoformat(at.replace("Z", "+00:00")) if isinstance(at, str) and len(at) <= 40 else None
        if stamp and stamp.tzinfo is not None:
            age = max(0, (now - stamp).total_seconds())
    except (ValueError, TypeError):
        pass
    warnings = []
    if rows and not increasing:
        warnings.append("MONOTONIC_SPAN_UNAVAILABLE")
    if not counter_ok:
        warnings.append("CPU_COUNTER_RESET")
    if nonfinite_rate:
        warnings.append("CPU_RATE_NONFINITE")
    return {"sample_count": len(rows), "last_sample_age_seconds": age,
            "monotonic_span_seconds": valid_times[-1] - valid_times[0] if len(valid_times) >= 2 and increasing else None,
            "sample_intervals_seconds": {"count": len(intervals), "min": min(intervals) if intervals else None,
                                         "max": max(intervals) if intervals else None,
                                         "average": sum(intervals) / len(intervals) if intervals else None},
            "cpu": {"usage_sample_count": len(points), "usage_delta_usec": delta,
                    "usage_monotonic_span_seconds": span, "average_cores": cores,
                    "average_percent_one_core": percent,
                    "quota_cores": quota_value / period if quota_value is not None and period else None,
                    "quota_period_usec": period, "scope": "cgroup; includes other container processes"},
            "memory": {"current_bytes": memory_current[-1] if memory_current else None,
                       "maximum_sampled_current_bytes": max((x for x in memory_current if x is not None), default=None),
                       "reported_cgroup_peak_bytes": max((x for x in memory_peak if x is not None), default=None),
                       "peak_scope": "cgroup lifetime counter observed within this window; may predate this session",
                       "limit_bytes": _integer_text(current.get("memory_max")),
                       "limit_unbounded": current.get("memory_max") == "max"},
            "gpu": {"gpu_util_scope": GPU_SCOPE, "current_sample_scope": "latest recorded row; not a live device query",
                    "devices": gpu}, "measurement_warnings": warnings}


def build_mobile_diagnostics(state_root, *, now_utc=None):
    root = Path(state_root)
    _safe_directory(root)
    body, _ = _read_file(root / "gcube-runtime.json", MAX_RUNTIME_BYTES)
    try:
        runtime = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise DiagnosticsError("DIAGNOSTIC_RUNTIME_INVALID") from None
    if not isinstance(runtime, dict):
        raise DiagnosticsError("DIAGNOSTIC_RUNTIME_INVALID")
    summary, order = _runtime_summary(runtime)
    rows, session_info = _session_rows(root)
    return {"format": "gcube-mobile-resource-diagnostics-v1", "runtime": summary,
            "session": {**session_info, **_resources(rows, order, now=now_utc or datetime.now(timezone.utc))},
            "bounds": {"runtime_bytes": MAX_RUNTIME_BYTES, "session_bytes": MAX_SESSION_BYTES,
                       "session_rows": MAX_SESSION_ROWS, "session_files": MAX_SESSION_FILES,
                       "directory_entries": MAX_DIRECTORY_ENTRIES, "sample_line_bytes": MAX_LINE_BYTES},
            "gpu_util_scope": GPU_SCOPE, "provider_points_consumed": None,
            "actual_gpu_cloud_video_benchmark": None, "gpu_cloud_speedup_measured": False,
            "original_benchmark_backend": "CPU_LOCAL", "original_measurements_modified": False,
            "commands_executed": False, "project_files_inspected": False,
            "notes": ["Resource/startup observations are not completed-video render benchmarks.",
                      "Bounded windows do not imply whole-session peaks when truncated.",
                      "Allocated device totals may include other workloads."]}
