"""Reuse the preserved public HTTP/SHA verifier, relocated to this new namespace."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
previous = HERE.parent / 'universal-source-pipeline-v2/tools/verify_downloads.py'
spec = importlib.util.spec_from_file_location('g2_recovery_public_verifier', previous)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.HERE = HERE
module.PREFIX = 'world-simulation-shorts-engine/recovery/g2-renderer-recovery-v1/'

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    result = module.verify(parser.parse_args().commit)
    print(json.dumps({'status': result['status'], 'filesVerified': result['filesVerified']}))
