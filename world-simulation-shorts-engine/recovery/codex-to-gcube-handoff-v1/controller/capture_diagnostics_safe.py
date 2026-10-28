"""Post-cleanup, best-effort, bounded, allowlisted diagnostic handoff.
No raw logs, secrets, private paths or source content are exported.
"""
from datetime import datetime, timezone
from pathlib import Path
import re
from safe_capture_export import export_failure

_JOB = re.compile(r'^studio-[a-f0-9]{32}$')

def export_after_cleanup(job_root, export_root, execution_deadline):
    job = Path(job_root)
    export = Path(export_root)
    if not _JOB.fullmatch(job.name):
        raise ValueError('DIAGNOSTIC_JOB_ID_INVALID')
    if not export.is_dir() or export.is_symlink():
        raise ValueError('DIAGNOSTIC_EXPORT_ROOT_INVALID')
    deadline = datetime.fromisoformat(execution_deadline)
    if deadline.tzinfo is None:
        raise ValueError('DIAGNOSTIC_DEADLINE_INVALID')
    remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        raise TimeoutError('DIAGNOSTIC_DEADLINE_EXPIRED')
    return export_failure(job, export / ('capture-diagnostic-' + job.name), deadline_seconds=min(5,remaining))
