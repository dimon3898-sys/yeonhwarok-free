"""One image-proof owner: re-export the overnight manifest authority."""
from pathlib import Path
import importlib.util

_spec = importlib.util.spec_from_file_location('_overnight_boot_manifest_proof', Path(__file__).with_name('package_manifest.py'))
_owner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_owner)
ENV = _owner.ENV
install = _owner.install_image_proof
read = _owner.read_image_proof
validate = _owner.validate_image_proof
