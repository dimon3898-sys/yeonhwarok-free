#!/usr/bin/env python3
"""Transparent launch capture; existing GPU wrapper still owns browser flags.

Preserves Playwright's debugging pipe descriptors. Never changes visual code.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

from bootstrap import LIMIT, redact
from chromium_wrapper import browser_arguments, browser_executable


def main():
    destination = Path(os.environ['GATE1_CAPTURE_DIR'])
    destination.mkdir(parents=True, exist_ok=True)
    record = {'real_executable': browser_executable(),
              'arguments': [redact(arg) for arg in browser_arguments(sys.argv[1:])],
              'exit_code': 'UNKNOWN', 'signal': 'UNKNOWN', 'capture_limit_bytes': LIMIT}
    status_path = destination / 'chromium-process.json'
    status_path.write_text(json.dumps(record))
    child = subprocess.Popen([sys.executable, str(Path(__file__).with_name('chromium_wrapper.py')), *sys.argv[1:]],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=False)

    def relay(source, sink, filename):
        written = 0
        with (destination / filename).open('w', encoding='utf-8') as output:
            while True:
                # Keep split writes on one line together before redaction.
                chunk = source.readline(LIMIT)
                if not chunk:
                    break
                if written < LIMIT:
                    text = redact(chunk.decode('utf-8', errors='replace'))
                    text = text[:LIMIT - written]
                    output.write(text)
                    output.flush()
                    written += len(text)
                try:
                    sink.write(chunk)
                    sink.flush()
                except (BrokenPipeError, OSError):
                    pass

    def forward(signum, _):
        if child.poll() is None:
            child.send_signal(signum)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    threads = [threading.Thread(target=relay, args=(source, sink, filename), daemon=True)
               for source, sink, filename in [(child.stdout, sys.stdout.buffer, 'chromium.stdout.log'),
                                               (child.stderr, sys.stderr.buffer, 'chromium.stderr.log')]]
    for thread in threads:
        thread.start()
    code = child.wait()
    for thread in threads:
        thread.join(timeout=3)
    record.update(exit_code=code if code >= 0 else None, signal=-code if code < 0 else None)
    status_path.write_text(json.dumps(record))
    return code if code >= 0 else 128 - code


if __name__ == '__main__':
    sys.exit(main())
