"""Local cgroup and device measurements, deliberately not a provider bill."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import threading
import time
import uuid


def sample_resources():
    result = {'at_utc': datetime.now(timezone.utc).isoformat(),
              'monotonic_seconds': time.monotonic(), 'provider_points_consumed': None}
    for name in ('cpu.stat', 'memory.current', 'memory.peak', 'memory.max', 'cpu.max'):
        try:
            text = (Path('/sys/fs/cgroup') / name).read_text().strip()
            if len(text) <= 4096:
                result[name.replace('.', '_')] = text
        except OSError:
            pass
    try:
        r = subprocess.run(['nvidia-smi', '--query-gpu=uuid,utilization.gpu,memory.used,memory.total',
                            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and len(r.stdout) < 65536:
            result['device_wide_gpu_samples'] = [x.strip() for x in r.stdout.splitlines()]
            result['gpu_sample_scope'] = 'allocated device total; not exclusive process attribution'
    except (OSError, subprocess.SubprocessError):
        pass
    return result


class Telemetry:
    def __init__(self, runtime, interval=5):
        root = Path(runtime) / 'gcube-sessions'
        root.mkdir(mode=0o700, exist_ok=True)
        self.path = root / ('session_' + uuid.uuid4().hex + '.jsonl')
        self.stop_event = threading.Event()
        self.interval = interval
        self.thread = None

    def start(self):
        def run():
            with self.path.open('x') as f:
                self.path.chmod(0o600)
                while True:
                    f.write(json.dumps(sample_resources(), sort_keys=True) + '\n')
                    f.flush()
                    if self.stop_event.wait(self.interval):
                        break
        self.thread = threading.Thread(target=run, daemon=True, name='gcube-resource-measurements')
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(5)
