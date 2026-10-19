"""Add only private profile sidecar; original admission/VRAM/lease/capture stay."""
from contextlib import contextmanager
from pathlib import Path
import importlib.util,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import execution_manager
execution_manager.runtime()  # checks the complete extension/frozen-source seal
_path=HERE.parent/'verified-front-data-v4-recovery/render_adapter.py'
_spec=importlib.util.spec_from_file_location('_integration_fixed_front_render',_path)
parent=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=parent;_spec.loader.exec_module(parent)
parent.parent.HERE=HERE
RenderError,native_gpu=parent.RenderError,parent.native_gpu
_parent_imports=parent._parent_imports

@contextmanager
def common_gpu_lease():
 execution_manager.authorize_request()
 with parent.common_gpu_lease():yield

def prepare_job(plan,private_root,*,approval):
 request=execution_manager.read_request()
 execution_manager.authorize_request(plan)
 if request['videoPlanSHA256']!=parent.parent.canonical_sha256(plan):raise RuntimeError('INTEGRATION_CAPTURE_PLAN_BINDING_REQUIRED')
 return parent.prepare_job(plan,private_root,approval=approval)

def render_segment(plan,scene,output_directory,*,approval,progress=None):
 request=execution_manager.read_request()
 execution_manager.authorize_request(plan)
 if request['videoPlanSHA256']!=parent.parent.canonical_sha256(plan):raise RuntimeError('INTEGRATION_CAPTURE_PLAN_BINDING_REQUIRED')
 with parent.parent.PrivateTree(Path(output_directory)) as attempt:attempt.write_json('INTEGRATION_REQUEST.json',request)
 return parent.render_segment(plan,scene,output_directory,approval=approval,progress=progress)
