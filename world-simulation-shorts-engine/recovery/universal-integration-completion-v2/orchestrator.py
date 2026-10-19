"""Use the V1 coordination wrapper in an isolated completion instance."""
from pathlib import Path
import importlib.util
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import execution_manager
execution_manager.authorize_request()
spec = importlib.util.spec_from_file_location('_completion_coordinate_instance', HERE.parent / 'universal-integration-v1/orchestrator.py')
parent = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parent
spec.loader.exec_module(parent)
parent.HERE = HERE
parent.parent.parent.HERE = HERE
if __name__ == '__main__':
    raise SystemExit(parent.parent.main())
