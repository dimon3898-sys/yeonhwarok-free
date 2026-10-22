"""Use the preserved public GET/hash verifier with only its output root relocated."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_g2_final_public_verifier',
    HERE.parent/'universal-source-pipeline-v2/tools/verify_downloads.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.HERE=HERE
module.PREFIX='world-simulation-shorts-engine/recovery/g2-final-recovery-v1/'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True)
    report=module.verify(p.parse_args().commit)
    print(json.dumps({'status':report['status'],'filesVerified':report['filesVerified']}))
