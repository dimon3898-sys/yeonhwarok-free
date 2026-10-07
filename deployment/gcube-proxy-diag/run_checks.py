"""Bounded public CI proof: test IDs/types/locations, never exception values."""
import io
import json
from pathlib import Path
import sys
import unittest

for candidate in (Path(__file__).resolve().parents[2] / 'world-simulation-shorts-engine',
                  Path('/opt/world-engine/world-simulation-shorts-engine')):
    if (candidate/'deployment/gcube/proxy.py').exists():
        sys.path.insert(0,str(candidate)); break


class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.safe_errors=[]

    def record(self,test,error):
        locations=[];tb=error[2]
        while tb is not None:
            name=Path(tb.tb_frame.f_code.co_filename).name
            if name.endswith('.py'): locations.append({'file':name,'line':tb.tb_lineno})
            tb=tb.tb_next
        self.safe_errors.append({'test':test.id().split(' (',1)[0],
                                 'exception_type':error[0].__name__,'locations':locations[-6:]})

    def addError(self,test,error): self.record(test,error);super().addError(test,error)
    def addFailure(self,test,error): self.record(test,error);super().addFailure(test,error)
    def addSubTest(self,test,subtest,error):
        if error is not None: self.record(test,error)
        super().addSubTest(test,subtest,error)


def main():
    suite=unittest.defaultTestLoader.loadTestsFromNames(sys.argv[1:])
    result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=Result).run(suite)
    proof={'tests_run':result.testsRun,'skipped':len(result.skipped),'failed':len(result.failures),
           'errors':len(result.errors),'success':result.wasSuccessful(),'failure_locations':result.safe_errors}
    print(json.dumps(proof))
    if not result.wasSuccessful():
        # Fixed test metadata only; no exception value/header/body/auth data.
        for item in result.safe_errors[:25]:
            print('::error title=Diagnostic test failed::'+json.dumps(item))
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__': main()
