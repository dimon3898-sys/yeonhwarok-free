"""Existing Studio HTTP/auth adapter plus the opt-in source-regression controller.

This is a local software verification service, not a deployment. Production
HTTPS bootstrap and hardware admission are deliberately not spoofed here.
"""
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


controller_module = load("_gates_actual_controller", HERE / "studio_controller.py")
server = load("_gates_preserved_http_server", HERE.parent / "production-studio-mvp-v1/server.py")
StudioController = controller_module.StudioController


def local_application(*, state_root, owner_file, export_root, port, image_digest, **kwargs):
    controller = StudioController(control_root=state_root / "control", export_root=export_root,
        image_digest=image_digest, **kwargs)
    config = server.StudioConfig(state_root, owner_file, f"http://127.0.0.1:{port}", export_root,
        host="127.0.0.1", port=port, local_test_only=True)
    return server.StudioApplication(config, controller)
