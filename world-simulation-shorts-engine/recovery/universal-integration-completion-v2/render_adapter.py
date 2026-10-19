"""Select completion capture through the unchanged hardware/lease wrapper."""
from pathlib import Path
import importlib.util
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
spec = importlib.util.spec_from_file_location('_completion_render_instance', HERE.parent / 'universal-integration-v1/render_adapter.py')
parent = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parent
spec.loader.exec_module(parent)
parent.HERE = HERE
parent.parent.parent.HERE = HERE
RenderError = parent.RenderError
native_gpu = parent.native_gpu
_parent_imports = parent._parent_imports
common_gpu_lease = parent.common_gpu_lease
prepare_job = parent.prepare_job
render_segment = parent.render_segment
