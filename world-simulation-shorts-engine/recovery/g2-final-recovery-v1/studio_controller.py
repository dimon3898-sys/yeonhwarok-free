"""Isolated final-recovery entrypoint over the preserved Studio job controller."""
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
HERE = Path(__file__).resolve().parent
BASELINE = '3913ad8e90885c769cdccc91f396072d83e356f2'
OLD = HERE.parent / 'universal-source-pipeline-v2'
REPO = HERE.parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


reused = load('_g2_final_preserved_source_controller', OLD / 'studio_controller.py')
reused.HERE = HERE
StudioError = reused.StudioError
SCHEMA, PROFILE = reused.SCHEMA, reused.PROFILE


def final_gate_checks(gates):
    pinned = isinstance(gates, dict) and gates.get('baselineCommit') == BASELINE
    checks = [{'name': 'G2_FINAL_BASELINE', 'status': 'PASS' if pinned else 'BLOCKED',
               **({} if pinned else {'code': 'G2_FINAL_BASELINE_NOT_PINNED'})}]
    for phase in 'ABC':
        passed = (pinned and isinstance(gates.get('phase' + phase), dict)
                  and gates['phase' + phase].get('status') == 'PASS')
        checks.append({'name': 'G2_FINAL_PHASE_' + phase, 'status': 'PASS' if passed else 'BLOCKED',
                       **({} if passed else {'code': 'G2_FINAL_PHASE_' + phase + '_NOT_PASSED'})})
    history_blocked = pinned and gates.get('historicalG3') == 'BLOCKED'
    checks.append({'name': 'G2_HISTORICAL_G3_STAYS_BLOCKED',
                   'status': 'PASS' if history_blocked else 'BLOCKED',
                   **({} if history_blocked else {'code': 'G2_FINAL_HISTORICAL_SCOPE_INVALID'})})
    free_only = pinned and gates.get('paidGpuExecuted') is False
    checks.append({'name': 'G2_FINAL_FREE_EXECUTION_ONLY',
                   'status': 'PASS' if free_only else 'BLOCKED',
                   **({} if free_only else {'code': 'G2_FINAL_FREE_SCOPE_NOT_CONFIRMED'})})
    return checks


def current_gate_checks():
    file = HERE / 'reports/GATES.json'
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 256 * 1024:
        return final_gate_checks(None)
    try:
        return final_gate_checks(json.loads(file.read_bytes()))
    except (OSError, ValueError):
        return final_gate_checks(None)


def require_final_gates():
    failed = next((row for row in current_gate_checks() if row['status'] != 'PASS'), None)
    if failed:
        raise StudioError(failed['code'])


class StudioController(reused.StudioController):
    def __init__(self, **kwargs):
        root = Path(kwargs.get('control_root', ''))
        if (not root.is_absolute() or root.is_relative_to(REPO)
                or any(part.startswith(('source-studio-private-', 'g2-recovery-studio-private-'))
                       for part in root.parts)):
            raise StudioError('G2_FINAL_SEPARATE_PRIVATE_STATE_REQUIRED')
        super().__init__(**kwargs)

    def _preflight_record(self, root, record):
        result = super()._preflight_record(root, record)
        if record.get('submission', {}).get('schema') != SCHEMA:
            return result
        result = dict(result)
        result['checks'] = [*result.get('checks', []), *current_gate_checks()]
        result['ready'] = all(row.get('status') == 'PASS' for row in result['checks'])
        result.update(historicalRenderAllowed=False, paidRenderAllowed=False,
                      finalRecoveryOnly=True, maxWallSeconds=900, maxRetries=0)
        return result
