"""Reuse commit-pinned anonymous HTTP/SHA verification for real frame delivery."""
from pathlib import Path
import argparse
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
source = ROOT.parent / 'universal-overnight-v3/tools/verify_downloads.py'
spec = importlib.util.spec_from_file_location('preserved_public_download_verifier', source)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
verifier.ROOT, verifier.REPO = ROOT, REPO

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    result = verifier.verify(args.commit)
    print(json.dumps({'status': result['status'], 'files': len(result['artifacts']), 'commit': args.commit}))
