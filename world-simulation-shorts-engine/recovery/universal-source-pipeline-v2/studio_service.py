"""Preserved real Studio HTTP/auth service selecting the new source controller."""
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


controller_module = load("_source_studio_actual_controller", HERE / "studio_controller.py")
server = load("_source_studio_preserved_http", HERE.parent / "production-studio-mvp-v1/server.py")
StudioController = controller_module.StudioController


def local_application(*, state_root, owner_file, export_root, port, image_digest, **kwargs):
    state_root = Path(state_root)
    controller = StudioController(control_root=state_root / "control", export_root=export_root,
        image_digest=image_digest, **kwargs)
    config = server.StudioConfig(state_root, owner_file, f"http://127.0.0.1:{port}", export_root,
        host="127.0.0.1", port=port, local_test_only=True)
    return server.StudioApplication(config, controller)
