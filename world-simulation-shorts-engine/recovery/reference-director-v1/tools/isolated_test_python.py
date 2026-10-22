"""Only relocate freshly created test temp directories; never alter assertions."""
import os
from pathlib import Path
import runpy
import sys
import tempfile

root = Path(os.environ['REFERENCE_DIRECTOR_TEST_PRIVATE_ROOT'])
original = tempfile.TemporaryDirectory


class IsolatedTemporaryDirectory(original):
    def __init__(self, *args, **kwargs):
        if kwargs.get('dir') == '/workspace':
            kwargs['dir'] = str(root)
        super().__init__(*args, **kwargs)


tempfile.TemporaryDirectory = IsolatedTemporaryDirectory
args = sys.argv[1:]
if args[:1] == ['-m']:
    module = args[1]
    sys.argv = [module, *args[2:]]
    runpy.run_module(module, run_name='__main__', alter_sys=True)
else:
    file = args[0]
    sys.argv = args
    sys.path.insert(0, str(Path(file).resolve().parent))
    runpy.run_path(file, run_name='__main__')
