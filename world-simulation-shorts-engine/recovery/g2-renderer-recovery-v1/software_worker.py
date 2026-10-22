"""Run the preserved worker with a separately rooted capture entrypoint."""
import argparse
import importlib.util
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reused = load("_g2_recovery_isolated_worker",
    HERE.parent / "universal-source-pipeline-v2/software_worker.py")
reused.HERE = HERE
validate_package, validate_capture = reused.validate_package, reused.validate_capture


def run(args):
    controller = load("_g2_recovery_worker_gate", HERE / "studio_controller.py")
    controller.require_recovery_gates()
    return reused.run(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--plan-sha256", required=True)
    run(parser.parse_args())
