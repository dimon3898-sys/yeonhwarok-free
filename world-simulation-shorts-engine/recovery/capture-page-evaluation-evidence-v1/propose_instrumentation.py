"""Fail-closed, offline-only proposed instrumentation for the pinned capture module.

Do not deploy this directly: capture_vulkan.generated.mjs is hash-pinned in
GENERATED_SOURCE_MANIFEST.json, and derivative manifests/startup pins require
a separately verified image pipeline. This file only prepares a diff.
"""
from pathlib import Path
import argparse
import hashlib

ANCHORS = (
    ("await page.evaluate(async()=>{window.payload=", "PAGE_EVALUATE_RUNTIME_IMPORT"),
    ("const firstNativeProof=await page.evaluate(async()=>{", "PAGE_EVALUATE_FIRST_NATIVE_DRAW"),
    ("await page.evaluate(async frame=>{", "PAGE_EVALUATE_FRAME_CAPTURE"),
)

def propose(original: str) -> str:
    # Do not wrap or change browser expressions: only place stage labels before
    # each existing evaluation, then preserve stage in the private receipt.
    for anchor, _ in ANCHORS:
        if original.count(anchor) != 1:
            raise ValueError("PINNED_CAPTURE_ANCHOR_MISMATCH")
    if original.count("let browser,encoder,encoderExit,service;") != 1:
        raise ValueError("PINNED_CAPTURE_STATE_ANCHOR_MISMATCH")
    if original.count("receipt.failure={code:String(error.message).slice(0,4000)};") != 1:
        raise ValueError("PINNED_CAPTURE_RECEIPT_ANCHOR_MISMATCH")
    changed = original.replace("let browser,encoder,encoderExit,service;",
                               "let browser,encoder,encoderExit,service;let diagnosticStage='BEFORE_PAGE_EVALUATION';", 1)
    for anchor, stage in ANCHORS:
        if stage == "PAGE_EVALUATE_FIRST_NATIVE_DRAW":
            changed = changed.replace(anchor, f"diagnosticStage='{stage}';" + anchor, 1)
        elif stage == "PAGE_EVALUATE_FRAME_CAPTURE":
            changed = changed.replace("const capture=" + anchor, f"diagnosticStage='{stage}';const capture=" + anchor, 1)
        else:
            changed = changed.replace(anchor, f"diagnosticStage='{stage}';" + anchor, 1)
    changed = changed.replace(
        "receipt.failure={code:String(error.message).slice(0,4000)};",
        "receipt.failure={code:String(error.message).slice(0,4000),diagnosticStage};", 1)
    # Private receipt remains private. Existing safe exporter does NOT publish
    # diagnosticStage; an explicit closed enum and updated exporter are required.
    return changed

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args=p.parse_args()
    source=args.source.read_text(encoding="utf-8")
    modified=propose(source)
    if args.output.exists():
        raise FileExistsError("OUTPUT_ALREADY_EXISTS")
    args.output.write_text(modified,encoding="utf-8")
    print("SOURCE_SHA256="+hashlib.sha256(source.encode()).hexdigest())
    print("CANDIDATE_SHA256="+hashlib.sha256(modified.encode()).hexdigest())
    print("STATUS=OFFLINE_CANDIDATE_ONLY_NOT_DEPLOY_READY")

if __name__=="__main__":
    main()
