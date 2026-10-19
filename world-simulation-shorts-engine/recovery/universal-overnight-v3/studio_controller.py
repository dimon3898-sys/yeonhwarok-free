"""Independent namespace; preserved authentication, consent, budget and claims."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import sys
HERE=Path(__file__).resolve().parent

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);value=importlib.util.module_from_spec(spec)
    sys.modules[name]=value;spec.loader.exec_module(value);return value

parent=load('_overnight_v1_controller',HERE.parent/'universal-integration-v1/studio_controller.py')
contract=load('_overnight_studio_contract',HERE/'contract_v3.py')
bridge=load('_overnight_studio_bridge',HERE/'runtime_bridge.py')
StudioError=parent.StudioError

class StudioController(parent.StudioController):
    def __init__(self,*,control_root,export_root,image_digest,backend=None,bridge_module=None):
        self.original_control_root=Path(control_root)
        cache=parent.parent.load_original('cache')
        with cache.PrivateTree(self.original_control_root,create=True):pass
        super().__init__(control_root=Path(control_root)/'universal-overnight-v3',export_root=export_root,
            image_digest=image_digest,backend=backend,bridge=bridge if bridge_module is None else bridge_module)

    def _normal(self,value):
        return contract.normalize_submission(value,image_digest=self.image_digest,backend=self.backend,
            parent_normalize=parent.parent.studio_contracts.normalize_submission)

    def _policy(self,root):
        if root.json('operator_policy.json',optional=True) is not None:
            return parent.parent.StudioController._policy(self,root)
        with self._cache.PrivateTree(self.original_control_root) as original:
            return parent.parent.StudioController._policy(self,original)

    def _preflight_record(self,root,record):
        submission=record['submission']
        if not isinstance(submission.get('overnightV3'),dict):
            raise StudioError('STUDIO_OVERNIGHT_PROFILE_REQUIRED')
        token=self._context.set(deepcopy(submission))
        try:
            # The original controller owns policy, audio gates and public result
            # sanitization. Its backend call is routed to this preview bridge.
            return parent.parent.StudioController._preflight_record(self,root,record)
        finally:
            self._context.reset(token)

    def _integration_gate(self,root,submission):
        report=bridge.preflight(submission,control_root=self.control_root,
            export_root=self.export_root,image_digest=self.image_digest)
        return {'allowed':report.get('renderAllowed') is True,'phase':'PREVIEW_5S',
            'blockers':[{'code':r.get('code','STUDIO_OVERNIGHT_GATE_BLOCKED')}
                        for r in report['checks'] if r['status'] in {'FAIL','BLOCKED'}]}

    def resume(self,*args,**kwargs):
        # Preview is exactly one bounded attempt. Existing failed claims remain
        # available for diagnosis; no automatic retry can spend another budget.
        raise StudioError('STUDIO_OVERNIGHT_PREVIEW_RETRY_REQUIRES_NEW_APPROVAL')

    def revise(self,*args,**kwargs):
        raise StudioError('STUDIO_OVERNIGHT_PREVIEW_REVISION_NOT_SUPPORTED',status=422)
