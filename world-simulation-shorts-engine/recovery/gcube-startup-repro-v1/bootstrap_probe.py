#!/usr/bin/env python3
"""TEST ONLY: inject one storage metadata failure into unchanged bootstrap.

The old source files are neither replaced nor edited. All source/dependency
checks still call their original implementations, and exec still enters the
original gpu-required launcher. This is not evidence about gCube's actual PVC.
"""
from __future__ import annotations

import argparse
import errno
import json
import os
from pathlib import Path
import runpy
import sys


PACKAGE = Path("/opt/rtx-package/repo/world-simulation-shorts-engine/recovery/rtx-gpu-package-v1")
STORAGE = "/world-storage/rtx-gpu-package-v1"


def trace(event, **facts):
    print("STARTUP_REPRO_TRACE " + json.dumps(
        {"testOnly": True, "event": event, **facts}, sort_keys=True),
        file=sys.stderr, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deny", required=True, choices=("chown", "chmod"))
    parser.add_argument("bootstrap_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    forwarded = args.bootstrap_args
    if forwarded[:1] == ["--"]:
        forwarded = forwarded[1:]
    if forwarded not in ([], ["--check"]):
        parser.error("only default startup or --check is allowed")
    if os.getuid() != 0:
        raise RuntimeError("mock probe requires the original root bootstrap")
    sys.path.insert(0, str(PACKAGE))
    import stage_package
    import verify_dependencies

    original_source = stage_package.verify_staged_context
    original_dependencies = verify_dependencies.verify_dependencies
    original_operation = getattr(os, args.deny)
    original_exec = os.execv

    def source_check(*positional, **keywords):
        result = original_source(*positional, **keywords)
        trace("source_contract_returned", status=result.get("status"),
              files=result.get("files"), uid=os.getuid())
        return result

    def dependency_check(*positional, **keywords):
        result = original_dependencies(*positional, **keywords)
        trace("dependency_check_returned", status=result.get("status"), uid=os.getuid())
        return result

    def denied_operation(path, *positional, **keywords):
        # File-descriptor calls and every other path retain the native operation.
        if isinstance(path, (str, bytes, os.PathLike)):
            candidate = os.fsdecode(os.fspath(path))
            if os.path.abspath(candidate) == STORAGE:
                trace("mock_storage_metadata_denied", operation=args.deny,
                      storage=STORAGE, uid=os.getuid())
                raise PermissionError(errno.EPERM, "TEST_ONLY storage metadata operation denied", STORAGE)
        return original_operation(path, *positional, **keywords)

    def exec_original(program, arguments):
        if (program != sys.executable or len(arguments) < 2
                or arguments[1] != str(PACKAGE / "gpu_launcher.py")
                or list(arguments[2:]) not in ([], ["--check"])):
            raise RuntimeError("unexpected bootstrap exec target")
        trace("exec_original_gpu_launcher", uid=os.getuid(), gid=os.getgid())
        original_exec(program, arguments)

    stage_package.verify_staged_context = source_check
    verify_dependencies.verify_dependencies = dependency_check
    setattr(os, args.deny, denied_operation)
    os.execv = exec_original
    sys.argv = [str(PACKAGE / "bootstrap.py"), *forwarded]
    trace("mock_probe_started", deniedOperation=args.deny, target=STORAGE)
    namespace = runpy.run_path(str(PACKAGE / "bootstrap.py"), run_name="startup_repro_original_bootstrap")
    return namespace["main"]()


if __name__ == "__main__":
    raise SystemExit(main())
