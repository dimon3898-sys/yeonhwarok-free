"""Anonymous, commit-pinned public downloads through the preserved verifier."""
from pathlib import Path
import argparse
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "_preserved_anonymous_download_verifier",
    ROOT.parent / "universal-overnight-v3/tools/verify_downloads.py",
)
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
owner.ROOT = ROOT
owner.REPO = ROOT.parents[2]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    result = owner.verify(args.commit)
    print(json.dumps({"status": result["status"], "files": len(result["artifacts"]),
                      "publishCommit": result["publishCommit"]}))
