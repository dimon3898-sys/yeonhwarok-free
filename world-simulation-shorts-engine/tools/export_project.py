#!/usr/bin/env python3
"""Export an exact QC-passed immutable version, or verify/split an existing ZIP."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from deliverable_evidence import (EvidenceError, MIB, create_export, export_inventory,
                                 load_completed_version, split_zip, verify_parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    export = actions.add_parser("export", help="Write a new archive exclusively; never alter the project")
    export.add_argument("version_dir", type=Path)
    export.add_argument("--output", required=True, type=Path)
    export.add_argument("--split-mib", type=int, choices=range(1, 91), metavar="1..90")
    inspect = actions.add_parser("inspect", help="Read-only approval/QC/hash and inventory validation")
    inspect.add_argument("version_dir", type=Path)
    split = actions.add_parser("split", help="Preserve an existing ZIP and create new verified binary parts")
    split.add_argument("zip", type=Path)
    split.add_argument("--max-part-mib", type=int, default=90, choices=range(1, 91), metavar="1..90")
    verify = actions.add_parser("verify", help="Verify every part and concatenated ZIP SHA without writing")
    verify.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "verify":
            result = verify_parts(args.manifest)
        elif args.action == "split":
            result = split_zip(args.zip, args.max_part_mib * MIB)
        else:
            completed = load_completed_version(args.version_dir)
            if args.action == "inspect":
                files = export_inventory(completed)
                result = {"automatic_qc_passed": True, "plan_hash": completed["plan_hash"],
                          "files": files, "uncompressed_bytes": sum(item["bytes"] for item in files),
                          "aesthetic_review_required": completed["result"].get("aesthetic_review_required", True)}
            else:
                result = create_export(completed, args.output)
                if args.split_mib:
                    result["split"] = split_zip(args.output, args.split_mib * MIB)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (EvidenceError, OSError, KeyError, ValueError) as error:
        print(json.dumps({"error": str(error), "existing_source_files_preserved": True},
                         ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
