"""Select new entrypoints while retaining the original Studio job implementation."""
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = Path(__file__).resolve().parent
OLD = HERE.parent / "universal-source-pipeline-v2"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# The legacy implementation roots its normalizer/worker in HERE. Load its exact
# bytes in a separate module instance, then configure that one entrypoint root.
# No old source/module instance, inherited auth or claim operation is changed.
reused = load("_g2_recovery_isolated_source_controller", OLD / "studio_controller.py")
reused.HERE = HERE
StudioError = reused.StudioError
SCHEMA, PROFILE = reused.SCHEMA, reused.PROFILE


def recovery_gate_checks(gates):
    checks = []
    for phase in range(3):
        passed = (isinstance(gates, dict) and isinstance(gates.get(f"phase{phase}"), dict)
            and gates[f"phase{phase}"].get("status") == "PASS")
        checks.append({"name": f"G2_RECOVERY_PHASE_{phase}",
            "status": "PASS" if passed else "BLOCKED",
            **({} if passed else {"code": f"G2_RECOVERY_PHASE_{phase}_NOT_PASSED"})})
    blocked_history = isinstance(gates, dict) and gates.get("historicalG3") == "BLOCKED"
    checks.append({"name": "G2_HISTORICAL_G3_STAYS_BLOCKED",
        "status": "PASS" if blocked_history else "BLOCKED"})
    return checks


def current_gate_checks():
    file = HERE / "reports/GATES.json"
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 256 * 1024:
        return recovery_gate_checks(None)
    try:
        return recovery_gate_checks(json.loads(file.read_bytes()))
    except (OSError, ValueError):
        return recovery_gate_checks(None)


def require_recovery_gates():
    checks = current_gate_checks()
    failed = next((row for row in checks if row["status"] != "PASS"), None)
    if failed:
        raise StudioError(failed.get("code", "G2_RECOVERY_HISTORICAL_GATE_INVALID"))


class StudioController(reused.StudioController):
    def __init__(self, **kwargs):
        root = Path(kwargs.get("control_root", ""))
        if (not root.is_absolute() or root.is_relative_to(OLD)
                or any(part.startswith("source-studio-private-20261022-") for part in root.parts)):
            raise StudioError("G2_RECOVERY_SEPARATE_PRIVATE_STATE_REQUIRED")
        super().__init__(**kwargs)

    def _preflight_record(self, root, record):
        result = super()._preflight_record(root, record)
        if record.get("submission", {}).get("schema") != SCHEMA:
            return result
        result = dict(result)
        result["checks"] = [*result.get("checks", []), *current_gate_checks()]
        result["ready"] = all(row.get("status") == "PASS" for row in result["checks"])
        result["historicalRenderAllowed"] = False
        result["paidRenderAllowed"] = False
        result["recoveryOnly"] = True
        return result
