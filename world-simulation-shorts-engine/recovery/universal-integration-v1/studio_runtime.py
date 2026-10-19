#!/usr/bin/env python3
"""Fixed detached worker entry; original worker, SFX and delivery are unchanged."""
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
if str(HERE) not in sys.path:sys.path.insert(0,str(HERE))
import execution_manager

def main(argv=None):
 execution_manager.authorize_request()
 return execution_manager.runtime().main(sys.argv[1:] if argv is None else argv)
if __name__=='__main__':raise SystemExit(main())
