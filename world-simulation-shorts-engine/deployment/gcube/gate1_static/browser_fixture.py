"""Bounded UI/download integration runner; uses existing PNG fixture bytes."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('release_tests', HERE / 'test_release.py')
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
tests.Contracts.setUpClass()
try:
    with tempfile.TemporaryDirectory(prefix='gate1-browser-download-') as output:
        subprocess.run(['node', str(HERE / 'test_browser.mjs'), 'http://127.0.0.1:' + str(tests.Contracts.http.server_port), output], check=True, timeout=60)
finally:
    tests.Contracts.tearDownClass()
