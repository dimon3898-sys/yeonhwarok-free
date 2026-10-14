#!/usr/bin/env python3
"""Run actual CPU checks and preserve distinct test outcomes; no GPU invocation."""
import argparse
from io import StringIO
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def record(self, test, status, detail=None):
        self.cases.append({'test': test.id(), 'result': status, 'detail': detail})

    def addSuccess(self, test):
        super().addSuccess(test); self.record(test, 'PASS')

    def addFailure(self, test, err):
        super().addFailure(test, err); self.record(test, 'FAIL', self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err); self.record(test, 'FAIL', self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.record(test, 'SKIP', reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err); self.record(test, 'BLOCKED', 'expected failure')

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test); self.record(test, 'FAIL', 'unexpected success')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['B_C', 'ALL'], default='ALL')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    patterns = ['test_model.py', 'test_terrain.py', 'test_bathymetry.py', 'test_surface.py', 'test_providers.py'] if args.phase == 'B_C' else ['test_*.py']
    suite = unittest.TestSuite()
    for pattern in patterns:
        suite.addTests(unittest.defaultTestLoader.discover(str(ROOT/'tests'), pattern=pattern))
    stream = StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2, resultclass=RecordedResult).run(suite)
    counts = {status: sum(x['result'] == status for x in result.cases) for status in ('PASS','FAIL','SKIP','BLOCKED')}
    report = {'schema':'ASTRA_CPU_TEST_RESULTS_V1', 'phase':args.phase, 'command':sys.argv,
              'testsRun':result.testsRun, 'counts':counts, 'successful':result.wasSuccessful(),
              'gpuTestsExecuted':False, 'vendorNetworkRequestsExecuted':False, 'cases':result.cases}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    args.output.with_suffix('.log').write_text(stream.getvalue())
    print(json.dumps({k:v for k,v in report.items() if k != 'cases'}))
    return 0 if result.wasSuccessful() and result.testsRun else 1


if __name__ == '__main__':
    raise SystemExit(main())
