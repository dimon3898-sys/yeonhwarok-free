"""Drop to the engine account before the isolated hardware launcher runs."""
import os
from pathlib import Path
import pwd
import stat
import sys


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[2]
ENGINE = REPO / "world-simulation-shorts-engine"


class BootstrapError(RuntimeError):
    pass


def _directory(path, uid, gid, *, root):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise BootstrapError("runtime/storage directory must be an absolute non-symlink path")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise BootstrapError("runtime/storage path is not a directory")
    if root:
        os.chown(path, uid, gid)
        os.chmod(path, 0o700)
    details = path.stat()
    if details.st_uid != uid or stat.S_IMODE(details.st_mode) != 0o700:
        raise BootstrapError("runtime/storage directory must be private and engine-owned")
    return path


def prepare_environment(account, *, runtime="/run/world-engine", storage="/world-storage/rtx-gpu-package-v1"):
    """Preserve provider device groups; never install drivers or start a GPU."""
    root = os.getuid() == 0
    if not root and os.getuid() != account.pw_uid:
        raise BootstrapError("bootstrap must run as root or the engine account")
    runtime = _directory(runtime, account.pw_uid, account.pw_gid, root=root)
    storage = _directory(storage, account.pw_uid, account.pw_gid, root=root)
    home = Path(account.pw_dir)
    if not home.is_absolute() or not home.is_dir() or home.is_symlink():
        raise BootstrapError("engine account HOME is unavailable")
    if root:
        sys.path.insert(0, str(ENGINE))
        try:
            from deployment.gcube.gpu_access import collect_device_groups
            groups = collect_device_groups()
        finally:
            sys.path.pop(0)
        os.setgroups(groups)
        os.setgid(account.pw_gid)
        os.setuid(account.pw_uid)
    for name, destination in (("XDG_RUNTIME_DIR", runtime / "xdg-runtime"),
                              ("XDG_CACHE_HOME", runtime / "xdg-cache"),
                              ("XDG_CONFIG_HOME", runtime / "xdg-config")):
        os.environ[name] = str(_directory(destination, account.pw_uid, account.pw_gid, root=False))
    os.environ["HOME"] = str(home)
    os.environ["WORLD_ENGINE_RUNTIME_DIR"] = str(runtime)
    os.environ["RTX_STORAGE_ROOT"] = str(storage)
    os.environ["WORLD_ENGINE_RENDER_MODE"] = "gpu-required"
    if os.environ.get("WORLD_ENGINE_GPU_PROFILE") not in {None, "vulkan", "egl"}:
        raise BootstrapError("hardware profile must be vulkan or egl")
    os.environ["WORLD_ENGINE_CHROMIUM_REAL"] = "/usr/bin/chromium"
    return {"uid": os.getuid(), "runtime": str(runtime), "storage": str(storage)}


def main():
    try:
        prepare_environment(pwd.getpwnam("engine"))
        from stage_package import verify_staged_context
        verify_staged_context(PACKAGE.parents[3])
        from verify_dependencies import verify_dependencies
        import json
        contract = json.loads((PACKAGE / "dependency_contract.json").read_text())
        result = verify_dependencies(REPO, contract)
        if result["status"] != "PASS":
            raise BootstrapError("CPU_DEPENDENCY_CHECK_FAILED: " + "; ".join(result["errors"]))
        command = [sys.executable, str(PACKAGE / "gpu_launcher.py"), *sys.argv[1:]]
        os.execv(sys.executable, command)
    except (BootstrapError, ValueError, OSError, ImportError) as error:
        print("RTX_BOOTSTRAP_FAILED: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
