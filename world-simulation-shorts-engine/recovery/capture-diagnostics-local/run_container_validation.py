"""Run focused diagnostics in the pinned production image, without GPU or network."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

BASE = Path("/opt/world-engine-handoffs/studio-v2/repo")
REL = Path("world-simulation-shorts-engine/recovery")
CTRL = REL / "codex-to-gcube-handoff-v1/controller"
TESTS = REL / "capture-diagnostics-local/tests"
CANDIDATE = Path("/candidate")
WORK = Path("/tmp/diagnostics-runtime")
EXPECTED_WORKER = "5ade50beefc2cbca93ad2bc3bd8ba2e49199bc8f2acef1c43ff0eb90ba041723"
original = BASE / CTRL / "nvidia_worker.py"
assert hashlib.sha256(original.read_bytes()).hexdigest() == EXPECTED_WORKER
assert not WORK.exists()
shutil.copytree(BASE, WORK, symlinks=False)
for name in ("nvidia_worker.py", "safe_capture_export.py", "capture_diagnostics_safe.py"):
    shutil.copyfile(CANDIDATE / CTRL / name, WORK / CTRL / name)
shutil.copytree(CANDIDATE / TESTS, WORK / TESTS, dirs_exist_ok=True)
rows = []
for name in ("test_actual_worker_diagnostics.py", "test_worker_real_except_integration.py", "test_receipt_contract.py"):
    # Run under the actual production Python with UID/GID1000; no owner or policy.
    proc = subprocess.run(["/usr/bin/python3", "-I", str(WORK / TESTS / name)],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=25,
        env={"PATH":"/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE":"1"}, user=1000, group=1000)
    if proc.returncode:
        print(json.dumps({"status":"CONTAINER_TEST_FAILED", "test":name, "exit":proc.returncode}))
        # Test fixtures are synthetic, but do not publish arbitrary stderr.
        raise SystemExit(1)
    cases = json.loads(proc.stdout)
    assert cases and all(value == "PASS" for value in cases.values())
    rows.append({"test":name,"cases":cases})
assert hashlib.sha256(original.read_bytes()).hexdigest() == EXPECTED_WORKER
print(json.dumps({"status":"PRODUCTION_IMAGE_DIAGNOSTICS_CPU_PASS", "tests":rows,
    "uid":1000,"gid":1000,"originalImageUnchanged":True,
    "gpuExecuted":False,"fullStudioStartupVerified":False,"deployReady":False},sort_keys=True))
