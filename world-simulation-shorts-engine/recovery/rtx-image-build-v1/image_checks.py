#!/usr/bin/env python3
"""Validate a built image as UID 1000 without its GPU entrypoint or a network.

Mount this helper read-only; it is not part of the preserved image context.
Whole-image privileged credential-path and Docker Config.Env checks are separate
CI gates. This helper checks process environment, staged sources and engine HOME.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import tempfile

PACKAGE_ROOT = Path("/opt/rtx-package")
PACKAGE_REL = "world-simulation-shorts-engine/recovery/rtx-gpu-package-v1"
SOURCE_CONTRACT_SHA256 = "5938d0f33168daae415d9573701cafe290bcdd9850a14f4cb61c966560640180"
SOURCE_COMMITS = {"cpu": "a002d89492734bfa9d17b98145ee6cb9a3b366a2",
                  "glow": "45af879d7417abba58e9ebd59d8e6630a785ac28"}
CREDENTIAL_ENV = {"GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN",
                  "GHCR_TOKEN", "DOCKER_AUTH_CONFIG", "DOCKER_CONFIG", "REGISTRY_AUTH_FILE"}
MAX_JSON_BYTES = 1024 * 1024
VERSION = re.compile(r"\d+(?:\.\d+){1,3}\Z")
VERSION_KEYS = {"python", "numpy", "pillow", "gdal", "libnetcdf", "node", "playwright", "chromium", "ffmpeg", "ffprobe"}
GDAL_KEYS = {"ExceptionMgr", "quiet_errors", "config_option", "VSIGetMemFileBuffer_unsafe", "osr.ExceptionMgr"}
NETCDF_KEYS = {"nc_open_mem", "nc_close", "nc_inq", "nc_inq_varndims", "nc_inq_var", "nc_inq_dimlen",
               "nc_inq_attname", "nc_inq_att", "nc_get_att", "nc_get_att_text", "nc_get_att_string",
               "nc_free_string", "nc_get_var", "nc_inq_var_fill"}
PROBE_KEYS = {"terrain", "bathymetryClassic", "bathymetryNetCDF4", "surface", "neutral"}
SAFE_ERROR_CODES = {
    "INVALID_STAGED_PATH", "STAGED_SOURCE_OWNERSHIP_OR_PERMISSIONS", "STAGED_SOURCE_NOT_REGULAR",
    "STAGED_SOURCE_UNREADABLE", "STAGED_METADATA_TOO_LARGE", "STAGED_METADATA_INVALID",
    "PINNED_SOURCE_CONTRACT_MISMATCH", "PINNED_ORIGINAL_FILE_COUNT_MISMATCH", "STAGED_INVENTORY_INVALID",
    "STAGED_CREDENTIAL_OR_DUPLICATE_FILE", "STAGED_TREE_UNREADABLE", "STAGED_CREDENTIAL_PATH_PRESENT",
    "UNEXPECTED_STAGED_FILE", "STAGED_FILE_MISSING", "CREDENTIAL_ENV_PRESENT", "ENGINE_HOME_UNAVAILABLE",
    "ENGINE_HOME_CREDENTIAL_SCOPE_UNREADABLE", "ENGINE_HOME_CREDENTIAL_OR_SYMLINK_PRESENT",
    "NETWORK_NONE_REQUIRED", "NETWORK_ISOLATION_UNVERIFIED", "PACKAGED_VERIFIER_UNAVAILABLE",
    "CPU_COMMAND_UNAVAILABLE_OR_TIMEOUT", "CPU_COMMAND_FAILED", "PLAYWRIGHT_PROBE_JSON_INVALID",
    "PLAYWRIGHT_MODULE_CONTRACT_FAILED", "CODEC_PROBE_JSON_INVALID", "SYNTHETIC_CODEC_STREAM_INVALID",
    "SYNTHETIC_CODEC_CONTRACT_FAILED", "UID_1000_REQUIRED", "PACKAGED_SOURCE_VERIFICATION_FAILED",
    "STRICT_NATIVE_DEPENDENCY_CHECK_FAILED", "NATIVE_REPORT_INVALID", "NATIVE_API_OR_PROBE_FAILED",
}
NODE_PLAYWRIGHT_PROBE = r"""
const {createRequire}=require('node:module');
const path=require('node:path');
const local=createRequire(path.join(process.argv[1],'cinematic-world-map/package.json'));
const pw=local('playwright'), version=local('playwright/package.json').version;
if(process.version!=='v24.19.0'||version!=='1.62.1'||
   !pw.chromium||typeof pw.chromium.launch!=='function')throw Error('PLAYWRIGHT_MODULE_CONTRACT');
process.stdout.write(JSON.stringify({node:process.versions.node,playwright:version,chromiumLaunchAPI:true}));
"""


class ImageCheckError(RuntimeError):
    """A fixed, safe error code; subprocess output and secrets are never logged."""


def _canonical(value):
    if (not isinstance(value, str) or not value or value.startswith("/") or "\\" in value
            or "\x00" in value or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ImageCheckError("INVALID_STAGED_PATH")
    return value


def _credential_path(relative):
    parts = Path(relative).parts
    name = parts[-1] if parts else ""
    parent = parts[-2] if len(parts) >= 2 else ""
    private_ssh = parent == ".ssh" and (name in {"id_rsa", "id_ed25519", "id_dsa", "id_ecdsa",
                                               "id_ed25519_sk", "id_ecdsa_sk", "identity"}
                                           or name.endswith((".pem", ".key")))
    gcube_auth = parent == ".gcube" and name in {"config.yaml", "config.yml", "config.json", "config.toml",
                                               "credentials", "token"}
    return (name in {".env", ".git-credentials", ".netrc", ".npmrc"} or name.startswith(".env.")
            or private_ssh or gcube_auth
            or ".git" in parts or tuple(parts[-2:]) in {(".docker", "config.json"), (".aws", "credentials")}
            or tuple(parts[-3:]) == (".config", "gh", "hosts.yml"))


def _root_owned_readonly(path, *, directory=False):
    try:
        info = path.lstat()
        kind = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
        if (not kind or info.st_uid != 0 or info.st_mode & 0o022
                or not os.access(path, os.R_OK | (os.X_OK if directory else 0))
                or os.access(path, os.W_OK)):
            raise ImageCheckError("STAGED_SOURCE_OWNERSHIP_OR_PERMISSIONS")
        if not directory:
            fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as source:
                if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                    raise ImageCheckError("STAGED_SOURCE_NOT_REGULAR")
                source.read(1)  # Readability as UID 1000, without logging any body.
    except OSError as error:
        raise ImageCheckError("STAGED_SOURCE_UNREADABLE") from error


def _read_json(path):
    _root_owned_readonly(path)
    try:
        if path.stat().st_size > MAX_JSON_BYTES:
            raise ImageCheckError("STAGED_METADATA_TOO_LARGE")
        body = path.read_bytes()
        if len(body) > MAX_JSON_BYTES:
            raise ImageCheckError("STAGED_METADATA_TOO_LARGE")
        return json.loads(body), hashlib.sha256(body).hexdigest()
    except (OSError, ValueError) as error:
        raise ImageCheckError("STAGED_METADATA_INVALID") from error


def _check_source_tree(root):
    root = Path(root)
    # Protect replaceable ancestors too, not only the file inode.
    for ancestor in [*reversed(root.parents), root]:
        _root_owned_readonly(ancestor, directory=True)
    contract, contract_hash = _read_json(root / "source_contract.json")
    receipt, receipt_hash = _read_json(root / "STAGING_RECEIPT.json")
    if contract_hash != SOURCE_CONTRACT_SHA256 or not isinstance(contract, dict) or not isinstance(receipt, dict):
        raise ImageCheckError("PINNED_SOURCE_CONTRACT_MISMATCH")
    if not isinstance(contract.get("files"), list) or len(contract["files"]) != 140:
        raise ImageCheckError("PINNED_ORIGINAL_FILE_COUNT_MISMATCH")
    copied = receipt.get("files")
    if not isinstance(copied, list):
        raise ImageCheckError("STAGED_INVENTORY_INVALID")
    expected = {"source_contract.json", "STAGING_RECEIPT.json"}
    for record in copied:
        if not isinstance(record, dict):
            raise ImageCheckError("STAGED_INVENTORY_INVALID")
        relative = "repo/" + _canonical(record.get("repoPath"))
        if relative in expected or _credential_path(relative):
            raise ImageCheckError("STAGED_CREDENTIAL_OR_DUPLICATE_FILE")
        expected.add(relative)
    installed = root / "repo/cinematic-world-map/node_modules"
    observed = set()

    def walk_error(_error):
        raise ImageCheckError("STAGED_TREE_UNREADABLE")

    for parent, directories, filenames in os.walk(root, followlinks=False, onerror=walk_error):
        parent = Path(parent)
        _root_owned_readonly(parent, directory=True)
        for name in list(directories):
            candidate = parent / name
            _root_owned_readonly(candidate, directory=True)
            if candidate == installed:
                # Installed packages are checked by npm integrity and the native
                # dependency gate; their .bin symlinks/examples are not sources.
                directories.remove(name)
            elif _credential_path(candidate.relative_to(root)):
                raise ImageCheckError("STAGED_CREDENTIAL_PATH_PRESENT")
        for name in filenames:
            candidate = parent / name
            relative = candidate.relative_to(root).as_posix()
            if relative not in expected or _credential_path(relative):
                raise ImageCheckError("UNEXPECTED_STAGED_FILE")
            _root_owned_readonly(candidate)
            observed.add(relative)
    if observed != expected:
        raise ImageCheckError("STAGED_FILE_MISSING")
    return {"files": len(copied), "sourceContractSha256": contract_hash,
            "stagingReceiptSha256": receipt_hash}


def _check_credentials(environ):
    if any(name in environ for name in CREDENTIAL_ENV):
        raise ImageCheckError("CREDENTIAL_ENV_PRESENT")
    try:
        home = Path(pwd.getpwuid(1000).pw_dir)
        if not home.is_absolute() or home.is_symlink() or not home.is_dir():
            raise ImageCheckError("ENGINE_HOME_UNAVAILABLE")

        def walk_error(_error):
            raise ImageCheckError("ENGINE_HOME_CREDENTIAL_SCOPE_UNREADABLE")

        for parent, directories, filenames in os.walk(home, followlinks=False, onerror=walk_error):
            parent = Path(parent)
            for name in [*directories, *filenames]:
                candidate = parent / name
                if candidate.is_symlink() or _credential_path(candidate.relative_to(home)):
                    raise ImageCheckError("ENGINE_HOME_CREDENTIAL_OR_SYMLINK_PRESENT")
    except (OSError, KeyError) as error:
        raise ImageCheckError("ENGINE_HOME_CREDENTIAL_SCOPE_UNREADABLE") from error
    return {"processEnvironment": "PASS", "stagedSources": "PASS", "engineHome": "PASS",
            "rootHome": "SEPARATE_PRIVILEGED_CI_CHECK_REQUIRED"}


def _check_network():
    try:
        if {p.name for p in Path("/sys/class/net").iterdir()} != {"lo"}:
            raise ImageCheckError("NETWORK_NONE_REQUIRED")
    except OSError as error:
        raise ImageCheckError("NETWORK_ISOLATION_UNVERIFIED") from error


def _module(path, name):
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise ImageCheckError("PACKAGED_VERIFIER_UNAVAILABLE")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except (OSError, ImportError) as error:
        raise ImageCheckError("PACKAGED_VERIFIER_UNAVAILABLE") from error


def _command(arguments, *, timeout=30):
    try:
        result = subprocess.run(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ImageCheckError("CPU_COMMAND_UNAVAILABLE_OR_TIMEOUT") from error
    if result.returncode or len(result.stdout) > MAX_JSON_BYTES or len(result.stderr) > MAX_JSON_BYTES:
        raise ImageCheckError("CPU_COMMAND_FAILED")
    return result.stdout


def _playwright(repo):
    try:
        result = json.loads(_command(["node", "-e", NODE_PLAYWRIGHT_PROBE, str(repo)]))
    except ValueError as error:
        raise ImageCheckError("PLAYWRIGHT_PROBE_JSON_INVALID") from error
    if (not isinstance(result, dict) or set(result) != {"node", "playwright", "chromiumLaunchAPI"}
            or result["node"] != "24.19.0" or result["playwright"] != "1.62.1"
            or result["chromiumLaunchAPI"] is not True):
        raise ImageCheckError("PLAYWRIGHT_MODULE_CONTRACT_FAILED")
    return {"node": result["node"], "playwright": result["playwright"], "moduleLoaded": True,
            "browserPageOpened": False}


def _codec():
    with tempfile.TemporaryDirectory(prefix="rtx-ci-codec-") as temporary:
        output = str(Path(temporary) / "synthetic.mp4")
        _command(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
                  "color=c=black:s=16x16:r=1", "-frames:v", "2", "-an", "-c:v", "libx264",
                  "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-y", output])
        try:
            data = json.loads(_command(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
                                       "-show_entries", "stream=codec_name,width,height,pix_fmt,nb_read_frames",
                                       "-of", "json", output]))
        except ValueError as error:
            raise ImageCheckError("CODEC_PROBE_JSON_INVALID") from error
        streams = data.get("streams") if isinstance(data, dict) else None
        if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
            raise ImageCheckError("SYNTHETIC_CODEC_STREAM_INVALID")
        stream = streams[0]
        if (stream.get("codec_name") != "h264" or type(stream.get("width")) is not int or stream["width"] != 16
                or type(stream.get("height")) is not int or stream["height"] != 16
                or stream.get("pix_fmt") != "yuv420p" or stream.get("nb_read_frames") != "2"):
            raise ImageCheckError("SYNTHETIC_CODEC_CONTRACT_FAILED")
    return {"encoder": "libx264", "codec": "h264", "width": 16, "height": 16,
            "frames": 2, "syntheticBlackFramesOnly": True}


def run_checks(*, package_root=PACKAGE_ROOT, hashes_only=False, environ=None):
    if os.getuid() != 1000 or os.geteuid() != 1000:
        raise ImageCheckError("UID_1000_REQUIRED")
    env = os.environ if environ is None else environ
    if any(name in env for name in CREDENTIAL_ENV):
        raise ImageCheckError("CREDENTIAL_ENV_PRESENT")
    _check_network()
    root = Path(package_root)
    tree = _check_source_tree(root)
    credentials = _check_credentials(env)
    package = root / "repo" / PACKAGE_REL
    stage = _module(package / "stage_package.py", "rtx_ci_stage_verifier")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        source = stage.verify_staged_context(root)
    if (not isinstance(source, dict) or source.get("status") != "PASS" or source.get("gpuExecuted") is not False
            or source.get("sourceContractSha256") != SOURCE_CONTRACT_SHA256
            or source.get("sourceCommits") != SOURCE_COMMITS or type(source.get("files")) is not int
            or source["files"] != tree["files"]):
        raise ImageCheckError("PACKAGED_SOURCE_VERIFICATION_FAILED")
    summary = {"schema": "RTX_BUILT_IMAGE_CPU_CHECK_V1", "status": "PASS", "uid": 1000,
               "gpuExecuted": False, "browserPageOpened": False, "networkIsolation": "LOOPBACK_ONLY",
               "mode": "hashes-only" if hashes_only else "full-cpu",
               "source": {**tree, "originalFiles": 140, "sourceCommits": SOURCE_COMMITS},
               "credentials": credentials, "sourceOwnership": "ROOT_OWNED_READABLE_NOT_WRITABLE"}
    if hashes_only:
        return summary
    contract, _ = _read_json(package / "dependency_contract.json")
    native = _module(package / "verify_dependencies.py", "rtx_ci_dependency_verifier")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        report = native.verify_dependencies(root / "repo", contract)
    if (not isinstance(report, dict) or report.get("status") != "PASS" or report.get("gpuExecuted") is not False
            or report.get("errors") != []):
        raise ImageCheckError("STRICT_NATIVE_DEPENDENCY_CHECK_FAILED")
    versions = report.get("versions")
    encoders = report.get("encoders")
    if (not isinstance(versions, dict) or set(versions) != VERSION_KEYS or any(not isinstance(v, str) or not VERSION.fullmatch(v)
            for v in versions.values()) or not isinstance(encoders, dict) or encoders.get("libx264") is not True):
        raise ImageCheckError("NATIVE_REPORT_INVALID")
    gdal, netcdf, probes = report.get("gdalApis"), report.get("netcdfApis"), report.get("probes")
    if (not all(isinstance(r, dict) and r for r in (gdal, netcdf, probes))
            or set(gdal) != GDAL_KEYS or set(netcdf) != NETCDF_KEYS or set(probes) != PROBE_KEYS
            or not all(value is True for value in [*gdal.values(), *netcdf.values()])
            or not all(value == "PASS" for value in probes.values())):
        raise ImageCheckError("NATIVE_API_OR_PROBE_FAILED")
    playwright = _playwright(root / "repo")
    codec = _codec()
    summary.update({"versions": {key: versions[key] for key in sorted(versions)},
                    "nativeAPIs": {"gdal": {key: gdal[key] for key in sorted(gdal)},
                                   "netcdf": {key: netcdf[key] for key in sorted(netcdf)}},
                    "nativeProbes": {key: probes[key] for key in sorted(probes)},
                    "playwright": playwright, "codec": codec})
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hashes-only", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        # Packaged Python verifiers cannot add output beside the JSON report.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = run_checks(hashes_only=arguments.hashes_only)
    except ImageCheckError as error:
        result = {"schema": "RTX_BUILT_IMAGE_CPU_CHECK_V1", "status": "FAIL", "gpuExecuted": False,
                  "errorCode": str(error) if str(error) in SAFE_ERROR_CODES else "UNEXPECTED_CHECK_FAILURE"}
    except Exception:
        result = {"schema": "RTX_BUILT_IMAGE_CPU_CHECK_V1", "status": "FAIL", "gpuExecuted": False,
                  "errorCode": "UNEXPECTED_CHECK_FAILURE"}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
