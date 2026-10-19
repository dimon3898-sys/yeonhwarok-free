#!/usr/bin/env python3
"""Reuse source-frozen V4 coordination in a presentation-scoped namespace."""
from pathlib import Path
import importlib.util,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import execution_manager
execution_manager.authorize_request()
_path=HERE.parent/'verified-front-data-v4-recovery/orchestrator.py'
_spec=importlib.util.spec_from_file_location('_integration_fixed_front_coordinator',_path)
parent=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=parent;_spec.loader.exec_module(parent)
parent.parent.HERE=HERE
_adapter=None

def adapter():
 global _adapter
 if _adapter is None:
  spec=importlib.util.spec_from_file_location('_integration_selected_hardware_adapter',HERE/'render_adapter.py')
  _adapter=importlib.util.module_from_spec(spec);sys.modules[spec.name]=_adapter;spec.loader.exec_module(_adapter)
 return _adapter
parent._fixed_adapter=adapter
if __name__=='__main__':raise SystemExit(parent.main())
