#!/usr/bin/env python3
"""Bounded CPU-only startup reproduction of one immutable, existing image.

Run only on a free public standard GitHub ubuntu-24.04 runner. No Docker build,
push, GPU device, deployment, cache deletion or container removal is supported.
An expected CPU-only refusal is a test result, never hardware/startup approval.
"""
from __future__ import annotations

from dataclasses import dataclass
import glob
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid


IMAGE = ("ghcr.io/dimon3898-sys/world-simulation-shorts-engine@"
         "sha256:82a4d9086edc2345cd3f00430ff4c354ee3fbaedcef5f0b927a0d5f9c5e16a37")
CONFIG_ID = "sha256:1e784975dd022458c06f95fcd8804f1c6adc0ed0640db106e6e588f1049adb4a"
BOOTSTRAP = "/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1/bootstrap.py"
STORAGE = "/world-storage/rtx-gpu-package-v1"
MAX_OUTPUT = 1024 * 1024
CASE_TIMEOUT = 180
MIN_FREE = 20 * 1024**3


class MatrixError(RuntimeError):
    """Fixed-code diagnostic: no environment values or credential details."""


def write_new(path, data):
    data = data if isinstance(data, bytes) else (json.dumps(data, indent=2, sort_keys=True) + "\n").encode()
    with Path(path).open("xb") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)


def sha(data):
    return hashlib.sha256(data).hexdigest()


@dataclass
class Command:
    returncode: int
    stdout: bytes
    stderr: bytes
    timed_out: bool
    output_exceeded: bool
    elapsed_seconds: float


def _kill_group(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def bounded_command(arguments, timeout):
    """Bound both streams while reading; never collect unbounded subprocess output."""
    started = time.monotonic()
    process = subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    streams = {"stdout": bytearray(), "stderr": bytearray()}
    timed_out = exceeded = False
    selector = selectors.DefaultSelector()
    try:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        while selector.get_map():
            if time.monotonic() - started >= timeout:
                timed_out = True
                _kill_group(process)
                break
            for key, _ in selector.select(0.2):
                body = os.read(key.fileobj.fileno(), 65536)
                if not body:
                    selector.unregister(key.fileobj)
                    continue
                remaining = MAX_OUTPUT - len(streams[key.data])
                streams[key.data].extend(body[:remaining])
                if len(body) > remaining:
                    exceeded = True
                    _kill_group(process)
                    break
            if exceeded:
                break
        process.wait(timeout=10)
    finally:
        _kill_group(process)
        process.wait(timeout=10)
        selector.close()
        process.stdout.close()
        process.stderr.close()
    return Command(process.returncode, bytes(streams["stdout"]), bytes(streams["stderr"]),
                   timed_out, exceeded, round(time.monotonic() - started, 3))


class Matrix:
    def __init__(self, evidence):
        self.evidence = Path(evidence)
        if not self.evidence.is_absolute() or self.evidence.is_symlink():
            raise MatrixError("ABSOLUTE_NONSYMLINK_EVIDENCE_DIRECTORY_REQUIRED")
        self.evidence.mkdir(parents=True, exist_ok=True)
        existing = list(self.evidence.iterdir())
        if any(path.name != "PROTECTION.json" or path.is_symlink() or not path.is_file()
               for path in existing):
            raise MatrixError("NEW_EVIDENCE_OR_PROTECTION_ONLY_DIRECTORY_REQUIRED")
        self.commands = []
        self.cases = []
        self.prefix = "we-startup-" + uuid.uuid4().hex[:12]
        self.containers = []
        self.mounts_root = None

    def command(self, label, arguments, timeout=60, *, require_success=True):
        number = len(self.commands) + 1
        relative = f"command-{number:02d}-{label}"
        result = bounded_command(arguments, timeout)
        write_new(self.evidence / (relative + ".stdout"), result.stdout)
        write_new(self.evidence / (relative + ".stderr"), result.stderr)
        record = {"label": label, "returncode": result.returncode, "timedOut": result.timed_out,
                  "outputExceeded": result.output_exceeded, "elapsedSeconds": result.elapsed_seconds}
        for stream in ("stdout", "stderr"):
            body = getattr(result, stream)
            record[stream] = {"file": relative + "." + stream, "bytes": len(body), "sha256": sha(body)}
        self.commands.append(record)
        if require_success and (result.returncode != 0 or result.timed_out or result.output_exceeded):
            raise MatrixError("BOUNDED_COMMAND_FAILED_" + label.upper())
        return result, record

    def preflight(self):
        expected = {"GITHUB_REPOSITORY": "dimon3898-sys/yeonhwarok-free",
                    "STARTUP_REPOSITORY_PUBLIC": "true", "STARTUP_RUNNER_LABEL": "ubuntu-24.04",
                    "RUNNER_ENVIRONMENT": "github-hosted"}
        if any(os.environ.get(key) != value for key, value in expected.items()):
            raise MatrixError("FREE_PUBLIC_STANDARD_GITHUB_RUNNER_REQUIRED")
        if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
            raise MatrixError("LINUX_AMD64_RUNNER_REQUIRED")
        if glob.glob("/dev/nvidia*"):
            raise MatrixError("CPU_ONLY_RUNNER_REQUIRED")
        docker_root, _ = self.command("docker-root", ["docker", "info", "--format", "{{json .DockerRootDir}}"])
        try:
            root = Path(json.loads(docker_root.stdout))
            if not root.is_absolute() or not root.is_dir():
                raise ValueError()
            disk = shutil.disk_usage(root)
        except (OSError, ValueError, TypeError):
            raise MatrixError("DOCKER_DISK_UNVERIFIED") from None
        if disk.free < MIN_FREE:
            raise MatrixError("DOCKER_DISK_20_GIB_REQUIRED")
        runner_temp = Path(os.environ.get("RUNNER_TEMP", ""))
        if not runner_temp.is_absolute() or not runner_temp.is_dir():
            raise MatrixError("ABSOLUTE_RUNNER_TEMP_DIRECTORY_REQUIRED")
        # Actual private mount contents are not part of the public CI evidence.
        self.mounts_root = Path(tempfile.mkdtemp(prefix=self.prefix + "-mounts-", dir=runner_temp))
        return {"repositoryPublic": True, "runnerLabel": "ubuntu-24.04", "githubHosted": True,
                "platform": "linux/amd64", "minimumFreeBytes": MIN_FREE,
                "freeBytesBeforePull": disk.free, "largerRunner": False,
                "gpuDeviceVisible": False, "existingFilesDeleted": False}

    def pull_and_inspect(self):
        self.command("pull-immutable", ["docker", "pull", "--platform", "linux/amd64", IMAGE], 600)
        template = ('{"id":{{json .Id}},"os":{{json .Os}},"architecture":{{json .Architecture}},'
                    '"entrypoint":{{json .Config.Entrypoint}},"cmd":{{json .Config.Cmd}},'
                    '"user":{{json .Config.User}}}')
        result, _ = self.command("image-identity", ["docker", "image", "inspect", "--format", template, IMAGE])
        try:
            identity = json.loads(result.stdout)
        except (ValueError, TypeError):
            raise MatrixError("IMAGE_IDENTITY_INVALID") from None
        if (identity.get("id") != CONFIG_ID or identity.get("os") != "linux"
                or identity.get("architecture") != "amd64"
                or identity.get("entrypoint") != ["/usr/bin/tini", "-g", "--", "/usr/bin/python3", BOOTSTRAP]
                or identity.get("cmd") not in (None, [])
                or identity.get("user") not in ("", "root", "0", "0:0")):
            raise MatrixError("PINNED_IMAGE_IDENTITY_MISMATCH")
        return identity

    def permissions(self, path, uid, mode):
        resolved = path.resolve(strict=True)
        if (self.mounts_root is None or not resolved.is_relative_to(self.mounts_root.resolve())
                or path.is_symlink() or not resolved.is_dir()):
            raise MatrixError("NEW_TEST_DIRECTORY_REQUIRED")
        self.command("test-dir-chown", ["sudo", "-n", "chown", "--", f"{uid}:{uid}", str(resolved)])
        self.command("test-dir-chmod", ["sudo", "-n", "chmod", "--", format(mode, "o"), str(resolved)])

    @staticmethod
    def directory_facts(path):
        if path is None:
            return None
        details = path.lstat()
        return {"uid": details.st_uid, "gid": details.st_gid,
                "mode": format(stat.S_IMODE(details.st_mode), "04o"),
                "isDirectory": stat.S_ISDIR(details.st_mode), "isSymlink": stat.S_ISLNK(details.st_mode)}

    def case(self, name, *, mount_owner=None, readonly=False, nonroot=False, deny=None, check=True):
        container = self.prefix + "-" + name
        root = target = None
        options = ["docker", "create", "--name", container, "--restart=no", "--network=none",
                   "--runtime=runc", "--shm-size=2g", "--memory=4g", "--cpus=2", "--pids-limit=256",
                   "--log-driver=json-file",
                   "--log-opt=max-size=4m", "--log-opt=max-file=1",
                   "--label", "world-engine.startup-repro=" + self.prefix]
        if mount_owner is not None:
            if self.mounts_root is None:
                raise MatrixError("PREFLIGHT_REQUIRED_BEFORE_TEST_MOUNT")
            root = self.mounts_root / (name + "-mount")
            root.mkdir(mode=0o755)
            root.chmod(0o755)
            target = root / "rtx-gpu-package-v1"
            target.mkdir(mode=0o700)
            self.permissions(target, mount_owner, 0o700)
            mount = f"type=bind,source={root},target=/world-storage"
            options += ["--mount", mount + (",readonly" if readonly else "")]
        before = self.directory_facts(target)
        if nonroot:
            options += ["--user", "1000:1000"]
        if deny:
            probe = Path(__file__).resolve().with_name("bootstrap_probe.py")
            if not probe.is_file() or probe.is_symlink():
                raise MatrixError("MOCK_PROBE_FILE_REQUIRED")
            options += ["--mount", f"type=bind,source={probe},target=/startup-repro/bootstrap_probe.py,readonly",
                        "--entrypoint", "/usr/bin/python3"]
        options.append(IMAGE)
        if deny:
            options += ["/startup-repro/bootstrap_probe.py", "--deny", deny, "--"]
        if check:
            options += ["--check"]
        self.command("create-" + name, options)
        self.containers.append(container)
        self.command("start-" + name, ["docker", "start", container])
        waited, _ = self.command("wait-" + name, ["docker", "wait", container], CASE_TIMEOUT, require_success=False)
        if waited.timed_out or waited.output_exceeded or waited.returncode != 0:
            self.command("kill-" + name, ["docker", "kill", "--signal", "KILL", container], require_success=False)
        inspected, _ = self.command("state-" + name, [
            "docker", "inspect", "--format",
            '{"exitCode":{{.State.ExitCode}},"running":{{.State.Running}},"oomKilled":{{.State.OOMKilled}}}',
            container])
        try:
            state = json.loads(inspected.stdout)
        except ValueError:
            raise MatrixError("CONTAINER_STATE_INVALID") from None
        logs, record = self.command("logs-" + name, ["docker", "logs", container], require_success=False)
        after = self.directory_facts(target)
        text = logs.stderr.decode("utf-8", "replace")
        safe = []
        for line in text.splitlines():
            try:
                candidate = json.loads(line)
            except ValueError:
                continue
            if isinstance(candidate, dict) and candidate.get("schema") == "RTX_GPU_ADMISSION_V1":
                safe.append(candidate)
        reason = safe[-1].get("reasonCode") if safe else None
        bootstrap_failure = state.get("exitCode") == 1 and "RTX_BOOTSTRAP_FAILED:" in text
        metadata_failure = (STORAGE in text and any(value in text for value in
                            ("[Errno 1]", "[Errno 13]", "[Errno 30]")))
        privacy_failure = "runtime/storage directory must be private and engine-owned" in text
        if state.get("exitCode") == 2 and reason == "GPU_HARDWARE_UNAVAILABLE":
            actual = "EXPECTED_NO_GPU_REFUSAL"
            failure_stage = "GPU_DEVICE_QUERY"
        elif bootstrap_failure and (metadata_failure or privacy_failure):
            actual = "BOOTSTRAP_STORAGE_REFUSAL"
            failure_stage = "STORAGE_METADATA" if metadata_failure else "RUNTIME_OR_STORAGE_PRIVACY"
        elif bootstrap_failure:
            actual = "BOOTSTRAP_OTHER_FAILURE"
            failure_stage = "DEPENDENCY_CHECK" if "CPU_DEPENDENCY_CHECK_FAILED" in text else "BOOTSTRAP_UNKNOWN"
        else:
            actual = "UNEXPECTED_EXIT_OR_OUTPUT"
            failure_stage = "UNKNOWN"
        expected = "BOOTSTRAP_STORAGE_REFUSAL" if deny or readonly or nonroot else "EXPECTED_NO_GPU_REFUSAL"
        healthy_output = not (logs.timed_out or logs.output_exceeded or logs.returncode != 0)
        passed = (actual == expected and healthy_output and not waited.timed_out
                  and not waited.output_exceeded and waited.returncode == 0
                  and state.get("running") is False and state.get("oomKilled") is False)
        if deny:
            passed = passed and '"event": "mock_storage_metadata_denied"' in text
        if mount_owner is not None and not (readonly or nonroot or deny):
            passed = passed and after == {"uid": 1000, "gid": 1000, "mode": "0700",
                                         "isDirectory": True, "isSymlink": False}
        case = {"name": name, "status": "PASS" if passed else "FAIL", "container": container,
                "imageReference": IMAGE, "actualExitCode": state.get("exitCode"),
                "containerState": state, "waitTimedOut": waited.timed_out,
                "classification": actual, "expectedClassification": expected,
                "failureStage": failure_stage,
                "reasonCode": reason, "mountBefore": before, "mountAfter": after,
                "mocked": bool(deny), "mockOperation": deny,
                "mockScope": STORAGE if deny else None,
                "entrypoint": "TEST_ONLY_ORIGINAL_BOOTSTRAP_WRAPPER" if deny else "UNCHANGED_IMAGE_ENTRYPOINT",
                "gpuValidated": False, "gCubeActualPVCReproduced": False,
                "containerConstraints": {"memoryBytes": 4 * 1024**3, "cpus": 2, "pidsLimit": 256,
                                         "sharedMemoryBytes": 2 * 1024**3, "network": "none", "runtime": "runc"},
                "sourceAndDependencyBoundaryReached": actual == "EXPECTED_NO_GPU_REFUSAL",
                "logs": {key: record[key] for key in ("stdout", "stderr")}}
        self.cases.append(case)
        write_new(self.evidence / (name + ".json"), case)

    def run(self):
        summary = {"schema": "GCUBE_STARTUP_REPRO_V1", "sourceBaseline": "9034e18",
                   "packageBaseline": "2f9158b", "imageReference": IMAGE,
                   "gCubeWorkload": 5373, "actualGcubeCause": "UNKNOWN",
                   "actualGcubeExitCode": None, "actualGcubeLogsObtained": False,
                   "gpuValidation": "NOT_EXECUTED", "gCubeDeployed": False,
                   "imageBuilt": False, "imagePushed": False, "sourceModified": False,
                   "existingFilesDeleted": False, "containersRemoved": False,
                   "overallDecision": "BLOCKED_PENDING_ACTUAL_WORKLOAD_LOGS"}
        error = None
        try:
            summary["freeRunner"] = self.preflight()
            summary["imageIdentity"] = self.pull_and_inspect()
            self.case("default-start", check=False)
            self.case("no-mount-check")
            self.case("writable-owned", mount_owner=1000)
            self.case("foreign-owner-root", mount_owner=42)
            self.case("mock-chown-eperm", mount_owner=1000, deny="chown")
            self.case("mock-chmod-eperm", mount_owner=1000, deny="chmod")
            self.case("readonly-mount", mount_owner=1000, readonly=True)
            self.case("foreign-owner-nonroot", mount_owner=42, nonroot=True)
        except (MatrixError, OSError, subprocess.SubprocessError) as exception:
            error = str(exception) if isinstance(exception, MatrixError) else type(exception).__name__
        finally:
            # Only kill running containers created by this exact invocation.
            # Do not rm containers, images, caches, volumes or evidence files.
            for container in self.containers:
                try:
                    running, _ = self.command("final-state", ["docker", "inspect", "--format", "{{.State.Running}}", container], require_success=False)
                    if running.stdout.strip() == b"true":
                        self.command("final-kill", ["docker", "kill", "--signal", "KILL", container], require_success=False)
                except (MatrixError, OSError, subprocess.SubprocessError):
                    error = error or "CREATED_CONTAINER_STOP_UNVERIFIED"
            summary.update(cases=self.cases, commands=self.commands, createdContainers=self.containers,
                           createdMountDirectoriesPreserved=(str(self.mounts_root) if self.mounts_root else None),
                           matrixResult=("PASS" if error is None and len(self.cases) == 8
                                         and all(case["status"] == "PASS" for case in self.cases) else "FAIL"),
                           error=error)
            write_new(self.evidence / "SUMMARY.json", summary)
            print(json.dumps({key: summary[key] for key in
                              ("matrixResult", "actualGcubeCause", "gpuValidation", "overallDecision", "error")}, sort_keys=True))
        return 0 if summary["matrixResult"] == "PASS" else 1


def main():
    evidence = os.environ.get("STARTUP_EVIDENCE_DIR")
    if not evidence:
        print("STARTUP_EVIDENCE_DIR_REQUIRED", file=sys.stderr)
        return 1
    try:
        return Matrix(evidence).run()
    except (MatrixError, OSError) as error:
        print(str(error) if isinstance(error, MatrixError) else type(error).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
