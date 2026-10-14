#!/usr/bin/env python3
"""Create an explicit source-bound context; never builds, pushes or deploys."""
import argparse
import json
from pathlib import Path
from stage_package import ContractError, stage_context, verify_staged_context

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def prepare(destination):
    contract = json.loads((HERE / "source_contract.json").read_text())
    inventory = json.loads((HERE / "package_overlay.json").read_text())
    if inventory.get("schema") != "RTX_PACKAGE_EXPLICIT_OVERLAY_V1":
        raise ContractError("EXPLICIT_PACKAGE_INVENTORY_REQUIRED")
    stage_context(REPO, contract, destination, package_files=inventory["files"])
    return verify_staged_context(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.destination), sort_keys=True))
