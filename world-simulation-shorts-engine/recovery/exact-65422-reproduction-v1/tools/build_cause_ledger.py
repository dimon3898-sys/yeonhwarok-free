"""Recheck primary 65422 artifacts; write a scoped, falsifiable cause ledger.

No renderer, original Scene, old proof, cache, or secret is changed. This does
not treat a prior narrative report as proof of an unavailable named movie.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
ENGINE = REPO / "world-simulation-shorts-engine"
OLD = "world-simulation-shorts-engine/recovery/moving-frontier-glow-fix-v1/"
SOURCE = "2c097df2d02432a3f9ae4dae5d714dbc9eacd434"
PROOF = "45af879d7417abba58e9ebd59d8e6630a785ac28"
BASE = "8e5053c3317a8b7ded366069274ca2d10a5dc8e2"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git_json(commit, relative):
    raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
    return json.loads(raw), {"commit": commit, "path": relative,
                             "sha256": sha(raw), "bytes": len(raw)}


def file_json(relative):
    raw = (REPO / relative).read_bytes()
    return json.loads(raw), {"commit": BASE, "path": relative,
                             "sha256": sha(raw), "bytes": len(raw)}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def main():
    original, original_ref = git_json(PROOF, OLD + "evidence/proof/REPORT.json")
    scene, scene_ref = git_json(SOURCE, OLD + "fixtures/SCENE_PLAN.json")
    fixture, fixture_ref = git_json(SOURCE, OLD + "fixtures/RUNTIME_FIXTURE.json")
    current, current_ref = file_json("world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/proof/ACTUAL_FRAME_TRACE_150.json")
    new_provenance, new_ref = file_json("world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/reports/NEW_OUTPUT_PROVENANCE.json")
    # Prior provenance is used only for original paths and links. The original
    # Git report, exact fixture, current actual traces, and source are re-read.
    assert original_ref["sha256"] == "550c1d7db502b91dc94548284ddfb10ff27f8e52cdf7efac7e7df68bfa768656"
    assert scene_ref["sha256"] == "aac147932d687f065469c224dbe2a02494f17c01a9be87383e771ada3f275159"
    assert len(original["frames"]) == len(current["frames"]) == 150
    assert original["sourceCommit"] == SOURCE
    assert original["video"]["sha256"] == "f3de1bdf9244171a47c6e5eccca6aae1370f58d8bf4721a7658b6bca2eed2ef6"
    assert [f["frame"] for f in original["frames"]] == list(range(150))
    assert [f["globalFrame"] for f in current["frames"]] == list(range(1400, 1550))
    assert all(f["scalarSelected"] is False and f["nationalUnitsSelected"] is False for f in current["frames"])
    assert all(f["globalClockPreserved"] is True for f in current["frames"])
    assert all(len(f["diagnostic"]["units"]["units"]) == 8 for f in original["frames"])

    runtime = OLD + "reference_runtime.mjs"
    renderer = "world-simulation-shorts-engine/web/map_infographic_v1/map_engine_unit_gpu_adapter_v4.mjs"
    core = "world-simulation-shorts-engine/recovery/"
    ev = {
        "ORIGINAL_CAPTURE": original_ref,
        "ORIGINAL_SCENE": scene_ref,
        "ORIGINAL_FIXTURE": fixture_ref,
        "KNOWN_CURRENT_CAPTURE": current_ref,
        "KNOWN_CURRENT_PROVENANCE": new_ref,
    }
    for name, relative, commit in [
        ("ORIGINAL_RUNTIME", runtime, SOURCE),
        ("ORIGINAL_RENDER_RUNNER", OLD + "render_proof.mjs", SOURCE),
        ("ORIGINAL_ADAPTER", renderer, SOURCE),
        ("CURRENT_RUNNER", core + "universal-overnight-v3/free_preview_runner.mjs", BASE),
        ("CURRENT_VISUAL_EXTENSIONS", core + "universal-overnight-v3/visual_extensions.mjs", BASE),
        ("CURRENT_AREA_ADAPTER", core + "verified-front-data-v4-recovery/front_adapter.mjs", BASE),
        ("STUDIO_INPUT", core + "production-studio-mvp-v1/studio_contracts.py", BASE),
        ("CURRENT_PREVIEW_PROFILE", core + "universal-overnight-v3/PREVIEW_PROFILE.json", BASE),
    ]:
        raw = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=REPO)
        ev[name] = {"commit": commit, "path": relative, "sha256": sha(raw), "bytes": len(raw)}

    rows = []

    def add(identifier, category, status, scope, finding, evidence, action, cause=False):
        assert status in {"CONFIRMED", "RULED_OUT", "UNVERIFIED"}
        rows.append({"id": identifier, "category": category, "status": status,
                     "scope": scope, "confirmedDifferenceCause": cause,
                     "finding": finding, "evidence": evidence, "action": action})

    known = "65422 versus known SHA3899 historical output; filenames66461/66463 not bound"
    exact = "Original65422 restoration, independent direct runtime"
    add("C01", "Original media identity", "CONFIRMED", exact,
        "Original proof binds f3de1bdf... MP4, original source2c097df, capture signatured8b2150b..., runtime signatureb81774e0....",
        ["ORIGINAL_CAPTURE:video,sourceCommit,resume,runtimeSourceSignature"], "Use this exact artifact as baseline.")
    add("C02", "66461 media identity", "UNVERIFIED", "User-named66461.mp4",
        "No file, SHA-to-name binding, or producing job receipt has been supplied for66461; known3899 remains separately identified.",
        ["KNOWN_CURRENT_PROVENANCE:userNamedArtifact"], "Do not attribute known3899 results to66461 without a source-bound mapping.")
    add("C03", "66463 media identity", "UNVERIFIED", "User-named66463.mp4",
        "No independently supplied66463.mp4 or name-to-SHA receipt was located in the inspected evidence.",
        ["KNOWN_CURRENT_CAPTURE:sourceCheckoutCommit,frames"], "Exact65422 restoration proceeds independently; named comparison remains unverified.")
    add("C04", "Original source revision", "CONFIRMED", exact,
        "The producing capture explicitly records2c097df2d02432a3f9ae4dae5d714dbc9eacd434;45af879 is the later persisted report snapshot, not the render source.",
        ["ORIGINAL_CAPTURE:sourceCommit,sourceBindings"], "Restore rendered source bytes, not an arbitrary latest branch.")
    add("C05", "Producing OCI digest", "UNVERIFIED", exact,
        "Original proof records a local Node/Chromium SwiftShader source run and no producing container digest. Later inclusion of sources in an image does not identify the original producing image.",
        ["ORIGINAL_CAPTURE:runtime.backend,performance,encodeCommand"], "Record source-run environment; no invented digest and no unnecessary image rebuild.")
    add("C06", "Original entrypoint versus different producer", "CONFIRMED", known,
        "Original entrypoint directly compiles the scalar Scene and createsMapEngineUnitGpuAdapterV4. Known3899 goes through long runtime→production→archivalfront→completion→optionalvisuals.",
        ["ORIGINAL_RUNTIME:126-150", "CURRENT_RUNNER:67-99", "KNOWN_CURRENT_CAPTURE:frames[0].instantiatedFactories"],
        "Select the preserved original direct runtime in an independent capsule.", True)
    add("C07", "Original Scene schema and body", "CONFIRMED", known,
        "Original MAP_ENGINE_UNIT_SCENE_V4 aac14793... is a150frame counterfactual scalar Scene. Known output selects VERIFIED_FRONT_V4_80S and preserves a2400frame historical plan.",
        ["ORIGINAL_SCENE", "ORIGINAL_FIXTURE:totalFrames", "KNOWN_CURRENT_PROVENANCE:scene"], "Restore original Scene exactly; do not convert or replace with Korean War data.", True)
    add("C08", "Scalar ownership not selected", "CONFIRMED", known,
        "Original64longitudinal knots and11boundary keyframes drive complementary ORANGE/PURPLE ownership. Current trace has scalarSelected=false on150/150frames.",
        ["ORIGINAL_SCENE:controlIntent", "KNOWN_CURRENT_CAPTURE:frames[*].scalarSelected", "CURRENT_VISUAL_EXTENSIONS:86-112,151-159"],
        "Supply the original scalar Scene to its original consumer, not invented historical enemy geometry.", True)
    add("C09", "Snapshot area versus continuous boundary", "CONFIRMED", known,
        "Original evaluates one continuously moving scalar boundary. Known historical branch evaluates supplied Area snapshots/fronts; source qualification and alpha transitions do not produce the original complementary field.",
        ["ORIGINAL_ADAPTER:163-177", "CURRENT_AREA_ADAPTER:92-128", "KNOWN_CURRENT_PROVENANCE:actual150FrameExecution"], "Use originalcontrolIntent and original evaluation clock.", True)
    add("C10", "Territory palette/coverage", "CONFIRMED", known,
        "Original territory style explicitly uses orange/red versus purple across the complementary domain; historical production palette colors only supplied ROK/Allied held-core polygons cyan/blue and does not infer opponents.",
        ["ORIGINAL_SCENE:style,controlIntent.factions", "KNOWN_CURRENT_PROVENANCE:scene.productionPalette,ownershipPolicy"], "Preserve original style and domain, not new color tuning.", True)
    add("C11", "Camera path/keyframes", "CONFIRMED", known,
        "Original5 authored bounds/roll keys give150distinct bounds. Known historical window has48numerically distinct bounds with effectively nozoom and≈0.6021px net translation.",
        ["ORIGINAL_SCENE:cameraKeyframes", "ORIGINAL_CAPTURE:frames[*].cameraBounds", "KNOWN_CURRENT_PROVENANCE:actual150FrameExecution"], "Use original keyframes/base camera anchor176 without changing approved camera code.", True)
    add("C12", "Presentation rotation", "CONFIRMED", known,
        "Original coherent map presentation roll spans4.99708°–11.99708°. Known trace reports actualV5Turn=false on150/150frames and does not invoke original presentation roll consumer.",
        ["ORIGINAL_SCENE:cameraKeyframes,presentationProfile", "ORIGINAL_ADAPTER:92-104,175-179", "KNOWN_CURRENT_CAPTURE:frames[*].actualV5Turn"], "Reuse original presentation adapter and keys.", True)
    add("C13", "National unit selection", "CONFIRMED", known,
        "Original renders8fixture-owned national-unit tablets on every frame; known trace has nationalUnitsSelected=false on150/150frames and source unitPositions=[].",
        ["ORIGINAL_CAPTURE:frames[*].diagnostic.units", "KNOWN_CURRENT_CAPTURE:frames[*].nationalUnitsSelected", "KNOWN_CURRENT_PROVENANCE:scene.unitPositions"], "Restore original8units/profile tables, not inferred historical troops.", True)
    add("C14", "Flag identities and historical semantics", "CONFIRMED", known,
        "Original counterfactual input explicitly includes DPRK1948,PRC1949,ROK1949,USmodern50star,RUSmoderntricolor; these are graphic study symbols, not sourced Korean War troop claims.",
        ["ORIGINAL_SCENE:metadata,combatProfile", "ORIGINAL_ADAPTER:129-142,181-190"], "Retain explicit original semantic mode and all flag profiles.", True)
    add("C15", "History policy silently deleting original units", "RULED_OUT", known,
        "For the inspected known output, optional national selection is null before badge instantiation. Original direct branch explicitly does not run historical policy in its public shader. No evidence shows a historical gate silently stripping an admitted original8unit fixture.",
        ["CURRENT_VISUAL_EXTENSIONS:49-62,113-123", "ORIGINAL_ADAPTER:137-140,181-190"], "Do not weaken historical or national admission policies.")
    add("C16", "Land/ocean material source", "CONFIRMED", known,
        "Original NE1 baked-relief color material/oceanV4 differs from the later ASTRA terrain,bathymetry,surfaceTexture material. Actual known150frame trace confirms ASTRA3roles/6textures; it is not an absent ASTRA fallback.",
        ["ORIGINAL_SCENE:terrainProfile", "ORIGINAL_ADAPTER:163-174", "KNOWN_CURRENT_PROVENANCE:actual150FrameExecution"], "Reuse original NE1 texture/material; do not tune ASTRA to mimic it.", True)
    add("C17", "Physical DEM or bathymetry required by original", "RULED_OUT", exact,
        "Original native draw explicitly passes dem:false; its report labels NE1 baked relief and does not claim physical-elevation lighting. ASTRA elevation/bathymetry samples are not original65422 runtime dependencies.",
        ["ORIGINAL_ADAPTER:163-169", "ORIGINAL_CAPTURE:reference.materialDataLimit,physicalElevationLightingClaimed"], "Do not add new DEM/bathymetry data or GPU dependencies.")
    add("C18", "Frontier profile", "CONFIRMED", known,
        "Original frontierV3 uses2.5px near-white core,3.5px halo sigma,10px support,.35haloalpha,.08settledStrength,12frame velocity window and original scalar boundary. Historical source-front profile and snapshot inputs are different.",
        ["ORIGINAL_SCENE:frontierProfile", "ORIGINAL_ADAPTER:129-132,172-177", "KNOWN_CURRENT_PROVENANCE:scene.completionProfile.frontier"], "Restore exact original profile and consumer, no new effect.", True)
    add("C19", "Terrain texture supplied to frontier lighting", "CONFIRMED", known,
        "Original frontier draw receives actualTerrainTexture:terrain.outputTexture before presentation. Known current historical trace summary reports frontTerrainLightingConnectedFrames=0.",
        ["ORIGINAL_ADAPTER:172-177", "KNOWN_CURRENT_PROVENANCE:actual150FrameExecution.frontTerrainLightingConnectedFrames"], "Retain original terrain-linked composition instead of overlaying final frame.", True)
    add("C20", "Composition/layer order", "CONFIRMED", known,
        "Original nativeGIS→NE1land/ocean→complementaryterritory→terrain-linkedfrontier→coherentroll→nationalbadges differs from ASTRA→suppliedArea/front→sourcequalifiers→nativeforegound.",
        ["ORIGINAL_ADAPTER:163-190,235-240", "CURRENT_AREA_ADAPTER:92-128"], "Use preserved original composition; no whole renderer clone or replacement.", True)
    add("C21", "Prompt parser reconstructing old Scene", "CONFIRMED", known,
        "StudioV1 input contract accepts structured JSON/frozen80s preset; original65422 was invoked directly, not generated from a Studio natural-language prompt. The original Scene is not silently equivalent to V4_ARCHIVAL_80S.",
        ["STUDIO_INPUT:79-99,152-195", "ORIGINAL_RUNTIME:126-150", "KNOWN_CURRENT_PROVENANCE:knownOutput.studioJobCreated"], "Reproduce via direct original runtime; do not invent a supported Studio prompt.", True)
    add("C22", "Actual Studio deployment caused known movie", "RULED_OUT", "Known SHA3899 only",
        "Known output's actual proof is a free source-checkout software capture with no created Studio job/candidate image execution. A later image digest in its plan is not a producing deployment receipt.",
        ["KNOWN_CURRENT_CAPTURE:softwareTraceOnly,candidateImageExecuted", "KNOWN_CURRENT_PROVENANCE:knownOutput"], "Keep source run and build-only image evidence separate.")
    add("C23", "Silent fallback to plain V4", "RULED_OUT", "Known SHA3899 only",
        "Actual per-frame trace records ASTRA,Area andV5 factories/draws; selected stage readPixels change actual pixels. Empty optional scalar/national selections are explicit, not evidence of a whole runtime fallback.",
        ["KNOWN_CURRENT_CAPTURE:frames[0].instantiatedFactories,pixelStages", "CURRENT_VISUAL_EXTENSIONS:151-159"], "Keep explicit missing-feature labels; do not report merely imported modules as active.")
    add("C24", "Wrong preview time origin/reset", "RULED_OUT", "Known SHA3899 only",
        "Known actual trace preserves source globalframes1400..1549 and full2400frame document; local outputPTSzero does not reset source Scene. Original65422 is separately authored localframes0..149.",
        ["KNOWN_CURRENT_CAPTURE:originalGlobalRange,frames[*].globalClockPreserved", "ORIGINAL_CAPTURE:frames[*].frame"], "Use original local0..149 only for exact65422; do not retime historical preview.")
    add("C25", "Original source preconditions", "CONFIRMED", exact,
        "Original runtime requires exact Scene schema, total150/fps30,visual-admission binding and unchanged savedScene except allowed frontier profile. Generic long-plan loading alone cannot satisfy this original contract.",
        ["ORIGINAL_RUNTIME:41-69", "ORIGINAL_FIXTURE"], "Restore original fixture, admissions, base native inputs and savedScene.")
    add("C26", "Original assets disappeared permanently", "RULED_OUT", exact,
        "Original report binds73source/input files;69are already byte-identical in baseline worktree,4are absent sparse materializations rather than altered assets. Git immutable source is used for capsule restoration, with exhaustive result separately recorded by capsule verifier.",
        ["ORIGINAL_CAPTURE:sourceBindings", "reports/PRIMARY_EVIDENCE.json:baselineMaterialization"], "Materialize required immutable blobs in separate capsule; do not edit/overwrite old sparse paths.")
    add("C27", "Original core/renderer overwritten", "RULED_OUT", exact,
        "The four key original runtime/runner/V4adapter/camera modules checked against2c097df are byte-identical in baseline; new work uses a verified source capsule rather than altering old shaders.",
        ["ORIGINAL_RUNTIME", "ORIGINAL_RENDER_RUNNER", "ORIGINAL_ADAPTER", "reports/PRIMARY_EVIDENCE.json:keySourceByteChecks"], "Protect old files; fix selection/restoration only.")
    add("C28", "Cache selected different original input", "UNVERIFIED", "Unidentified66461/66463 producing executions",
        "No named-file cache receipts or producing job records exist to establish cache contamination. Known historical trace source/Scene bindings are internally consistent; different input contracts already explain its divergence.",
        ["KNOWN_CURRENT_PROVENANCE:scene,knownOutput", "ORIGINAL_RENDER_RUNNER:45-108"], "New exact capture uses an empty isolated output/cache and verifies original bindings; never claim old frame reuse as new draw.")
    add("C29", "Network/external runtime resources", "RULED_OUT", exact,
        "Original runtime permits only its loopback server origin; persisted native plans,NE1/font,Three andmodule closure supply runtime data. No reference video background, remote terrain download or liveAI prompt is part of original render.",
        ["ORIGINAL_RUNTIME:73-95,119-133", "ORIGINAL_FIXTURE:nativeFiles,runtimeModuleFiles,runtimeAssetFiles", "ORIGINAL_ADAPTER:235-240"], "Use immutable local closure and deny non-loopback browser requests.")
    add("C30", "GPU versus CPU original backend", "CONFIRMED", exact,
        "Original actual renderer backend is ANGLE Vulkan SwiftShader, not attested RTX/NVIDIA; free software reproduction is therefore supported by the original path itself.",
        ["ORIGINAL_CAPTURE:runtime.backend,performance.actualBackend", "ORIGINAL_RUNTIME:117-119,152-156"], "Run same software backend; do not claim NVIDIA verification.")
    add("C31", "Original Node/Playwright/Chromium pins", "CONFIRMED", exact,
        "Original code asserts Nodev24.19.0,Playwright1.62.1,Chromium154.0.8037.57 and1080x1920/DPR1. Changes to these can alter rendering; current invocation must record actual versions.",
        ["ORIGINAL_RUNTIME:71-72,117-121"], "Use existing exact pinned runtime; abort on mismatch.")
    add("C32", "Original driver/container OS identity", "UNVERIFIED", exact,
        "SwiftShader renderer string is recorded, but complete originalOS/kernel/Mesa/NVIDIA-driver/container digest attestation is absent. Do not invent a physical driver match.",
        ["ORIGINAL_CAPTURE:runtime.backend,runtime.runtimeConfig"], "Judge actual frame and decoded-pixel equality while reporting environment provenance limits.")
    add("C33", "FFmpeg/encoding settings", "CONFIRMED", exact,
        "Original encoder arguments:30fps,start0,150frames,libx264,fast,CRF16,threads2,yuv420p,faststart,noaudio. Same dimensions/duration alone do not prove equal image content.",
        ["ORIGINAL_CAPTURE:encodeCommand,ffprobe,video", "ORIGINAL_RENDER_RUNNER:128-157"], "Reuse exact encoding parameters and compare container/decoded/raw hashes independently.")
    add("C34", "Original audio/sync mismatch", "RULED_OUT", exact,
        "Original capture audio=false,ffprobe has one H264 stream and encode command -an. Adding SFX would make exact reproduction different; there is no original sound-sync target.",
        ["ORIGINAL_CAPTURE:audio,ffprobe.streams,encodeCommand"], "Keep exact reproduction silent.")
    add("C35", "Known new audio differs", "CONFIRMED", known,
        "Known newer historical movie includes SFX, unlike original silent65422. This is a delivery difference, not the cause of missing territories/units.",
        ["KNOWN_CURRENT_PROVENANCE:knownOutput", "ORIGINAL_CAPTURE:audio", "world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/reports/MEDIA_COMPARISON.json:completeSequenceDecode"], "Preserve original audio absence in exact replay.", True)
    add("C36", "Whole-frame timing order", "CONFIRMED", exact,
        "Original full capture records ordered150frames0..149 at30fps,5s. Preserving camera/control/presentation state at every frame is mandatory; only encoderPTS may start atzero.",
        ["ORIGINAL_CAPTURE:frames,ffprobe", "ORIGINAL_RUNTIME:144-151"], "Compare all150raw/PNG/video frames and deterministic state, not only checkpoints.")
    add("C37", "Original full frame equality now", "UNVERIFIED", exact,
        "A fresh150frame capture and decoded comparison is required. This ledger never marks technical-size checks or prior known historical replay as exact65422 success.",
        ["reports/REPRODUCTION_RESULT.json (generated by fresh exact capture/comparison, if present)"], "Resolve using actual fresh capture report and full150frame comparison; retain mismatch firstframe if any.")
    add("C38", "Original quality versus reference parity", "UNVERIFIED", exact,
        "Original report itself does not claim reference quality parity,userapproval orFINAL promotion. Reproducing65422 is separate from improving quality or matching65379.",
        ["ORIGINAL_CAPTURE:qualityParityClaimed,userVideoApproved,finalPromotion"], "Do not promoteFINAL or invent visual-quality approval.")
    add("C39", "Historical native composition slot limits", "CONFIRMED", "Optional scalar integration in historical native producer only",
        "Previous focused test documents a source-valid scalar request missing historical parent native composition slots. This is a real conditional integration limit, but it is not triggered by known null-selection capture and does not affect original direct V4adapter.",
        ["CURRENT_VISUAL_EXTENSIONS:137-146,206-225", "world-simulation-shorts-engine/recovery/render-path-reconciliation-v1/reports/CONDITIONAL_NATIVE_SLOT_REPRO.md"], "Do not disable the guard; use original direct contract for exact65422 restoration.")
    add("C40", "Studio can directly call old 5s Scene", "UNVERIFIED", "Existing latest Studio interface",
        "The inspected actual old capture is a direct source runtime; no original65422 Studio prompt/job receipt exists. No claim is made that existing historical80s Studio submission supports direct MAP_ENGINE_UNIT_SCENE_V4 unchanged.",
        ["STUDIO_INPUT:152-195", "ORIGINAL_RUNTIME:41-69,126-150"], "Provide exact offline reproduction entrypoint; separate any future authenticated Studio profile work.")

    capsule_file = ROOT / "reports/SOURCE_CAPSULE_MANIFEST.json"
    capsule_verification = None
    if capsule_file.is_file():
        capsule_raw = capsule_file.read_bytes()
        capsule_verification = json.loads(capsule_raw)
        assert capsule_verification["sourceCommit"] == SOURCE
        assert capsule_verification["originalReportBindingsRestored"] == 73
        assert capsule_verification["totalFiles"] == 80
        assert capsule_verification["existingSourceChanged"] is False
        ev["RESTORED_SOURCE_CAPSULE"] = {
            "path": str(capsule_file.relative_to(REPO)), "sha256": sha(capsule_raw),
            "bytes": len(capsule_raw), "scope": "All73originalbindings plus7operational dependencies from immutableGit"}
        row = next(r for r in rows if r["id"] == "C26")
        row["finding"] += " Independent capsule now verifies/restores all73originalbindings plus7operational closure files against immutableGit; no old source changed."
        row["evidence"].append("RESTORED_SOURCE_CAPSULE")

    comparison_paths = list(ROOT.rglob("ALL_150_FRAME_COMPARISON.json"))
    if len(comparison_paths) > 1:
        raise RuntimeError("Ambiguous fresh150frame comparison; retain one source-bound canonical result")
    fresh_comparison = None
    if comparison_paths:
        comparison_file = comparison_paths[0]
        comparison_raw = comparison_file.read_bytes()
        fresh_comparison = json.loads(comparison_raw)
        assert fresh_comparison["original"]["sha256"] == original["video"]["sha256"]
        ev["FRESH_ALL_150_COMPARISON"] = {"path": str(comparison_file.relative_to(REPO)),
                                          "sha256": sha(comparison_raw), "bytes": len(comparison_raw)}
        row = next(r for r in rows if r["id"] == "C37")
        row["status"] = "CONFIRMED"
        row["evidence"] = ["FRESH_ALL_150_COMPARISON"]
        if fresh_comparison["status"] == "REPRODUCTION_PIXEL_EXACT_SOFTWARE":
            row["finding"] = ("Fresh unchanged original runtime rendered all150frames; allrawRGBA,deterministicstate anddecodedRGBframes match. "
                              f"EncodedMP4byte equality={fresh_comparison['encodedFileByteEqual']}; actualsoftware reproductionsuccess, notNVIDIAorqualityapproval.")
            row["action"] = "Submit the new source-bound movie and full150frame comparison; stop for user review."
        else:
            decoded = fresh_comparison["decodedMovie"]
            state = fresh_comparison["sourceCaptureAndStates"]
            row["finding"] = (
                f"Fresh capture: rawRGBA={state['rawRgbaMatches']}/150 and PNG={state['pngMatches']}/150 exact; "
                f"all10deterministicstatecategoriesequal={state['all150StatesEqual']}. "
                f"H264decodedpixels diverge first atframe{decoded['firstDifferingFrame']}; "
                f"whole150frameMAE={decoded['meanAbsoluteRgb8Difference']} on0..255, "
                f"maxchannelerror={decoded['maxAbsoluteChannelDifference']}. "
                "Renderer/input restoration is exact through pre-encode PNG; finalMP4 reproduction is NEEDS_REWORK, notPASS.")
            row["action"] = "Keep exact renderer/Scene/PNG unchanged; investigate only the observed encoding/color-conversion boundary."
            row = next(r for r in rows if r["id"] == "C27")
            row["finding"] += " Fresh150/150rawRGBA,PNG and10statecategories are exact to the original capture, excluding original renderer/shader corruption in this restored execution."
            row["evidence"].append("FRESH_ALL_150_COMPARISON:sourceCaptureAndStates")
            row = next(r for r in rows if r["id"] == "C36")
            row["finding"] += " Fresh full-frame comparison now confirms frame order,PTS contract and all10deterministicstatecategories; first actual difference begins after pre-encode PNG atdecodedframe0."
            row["evidence"].append("FRESH_ALL_150_COMPARISON:technicalAndPtsContractPass,sourceCaptureAndStates,decodedMovie")

    encoding_file = ROOT / "reports/ENCODING_DIFFERENCE_AND_TRIALS.json"
    if encoding_file.is_file():
        encoding_raw = encoding_file.read_bytes()
        encoding = json.loads(encoding_raw)
        assert encoding["originalFileSha256"] == original["video"]["sha256"]
        if fresh_comparison:
            assert encoding["primaryCandidateFileSha256"] == fresh_comparison["reproduction"]["sha256"]
        assert encoding["x264AdvertisedRevisionAndOptionsEqual"] is True
        ev["BOUNDED_ENCODING_TRIALS"] = {"path": str(encoding_file.relative_to(REPO)),
                                         "sha256": sha(encoding_raw), "bytes": len(encoding_raw)}
        row = next(r for r in rows if r["id"] == "C33")
        row["finding"] += (
            " Fresh encode uses originalargv; original andnewSEI both advertise x264core164r3108/31e19f9 andallidenticaloptions. "
            "Nevertheless finaldecodedpixels differ. Full original FFmpeg/libswscale/x264 binary provenance is not recorded.")
        row["evidence"].extend(["FRESH_ALL_150_COMPARISON", "BOUNDED_ENCODING_TRIALS"])
        row["action"] = "Do not infer exact binary/color-conversion identity from matching tags/SEI/options; preserve original-command candidate and report measured mismatch."
        row = next(r for r in rows if r["id"] == "C32")
        row["finding"] += " Matching x264advertisedrevision/options still does not establish originalbinarybuild,CPUfeature dispatch orlibswscale behavior; no precise encoder subcause has been proved."
        row["evidence"].append("BOUNDED_ENCODING_TRIALS:actualEncodingRootCause,originalX264Sei,primaryCandidateX264Sei")
        add("C41", "Precise encoder/color-conversion subcause", "UNVERIFIED", "Final encoded65422 reproduction only",
            "Earliest divergent stage is confirmed after150identicalpre-encodePNGs: decodedH264frame0. "
            "Two bounded no-redraw trials: -cpuflags0 changes output andworsensframe0MAE(.6346555versusbaseline.3790250); "
            "-filter_threads1 produces completebytesidenticalbaseline andtherefore doesnotexplainold-vs-newdifferenceonthishost. "
            "Exact originalCPUdispatch/binarybuild/PNGcolor-conversion cause remainsunverified. Neither trialwaspromoted; no rendererchangejustified.",
            ["FRESH_ALL_150_COMPARISON:sourceCaptureAndStates,decodedMovie,frames[0]",
             "BOUNDED_ENCODING_TRIALS:trials,confirmedEarliestDivergence,actualEncodingRootCause"],
            "Obtain originalencoderbinary/build/library/CPU provenance or an original deterministic pre-encodeYUV receipt ifavailable; do not run paidGPU or alter exact visuals to chase codec noise.")

    materialization = []
    for binding in original["sourceBindings"]:
        path = REPO / binding["path"]
        actual = sha(path.read_bytes()) if path.is_file() else None
        materialization.append({"path": binding["path"], "expectedSHA256": binding["sha256"],
                                "existsInBaselineWorktree": actual is not None,
                                "actualSHA256": actual, "matches": actual == binding["sha256"]})
    key_checks = []
    for relative in [runtime, OLD + "render_proof.mjs", renderer,
                     "world-simulation-shorts-engine/web/map_infographic_v1/reference_camera_adapter_v1.mjs"]:
        raw = subprocess.check_output(["git", "show", f"{SOURCE}:{relative}"], cwd=REPO)
        actual = (REPO / relative).read_bytes()
        assert actual == raw
        key_checks.append({"path": relative, "sourceCommit": SOURCE, "sha256": sha(raw), "baselineByteIdentical": True})
    assert sum(x["matches"] for x in materialization) == 69
    primary = {"schema": "WORLD_ENGINE_EXACT_65422_PRIMARY_EVIDENCE_V1", "evidence": ev,
               "baselineMaterialization": {"scope": "Existing sparse worktree before capsule; no old files changed",
                                           "boundFileCount": len(materialization), "byteMatches": 69,
                                           "missingMaterializations": 4, "files": materialization},
               "keySourceByteChecks": key_checks,
               "originalSummary": {"sourceCommit": SOURCE, "frameCount": 150,
                                   "scalarKnots": len(scene["controlIntent"]["longitudinal_knots"]),
                                   "scalarBoundaryKeyframes": len(scene["controlIntent"]["boundary_keyframes"]),
                                   "unitsEveryFrame": 8, "cameraKeys": len(scene["cameraKeyframes"]),
                                   "runtimeSourceSignature": original["runtimeSourceSignature"],
                                   "producingOCIImageDigest": None, "physicalNvidiaVerified": False},
               "knownCurrentSummary": {"sha256": new_provenance["knownOutput"]["sha256"],
                                       "frameCount": len(current["frames"]), "originalFrameRange": [1400, 1550],
                                       "scalarSelectedFrames": sum(f["scalarSelected"] for f in current["frames"]),
                                       "nationalSelectedFrames": sum(f["nationalUnitsSelected"] for f in current["frames"]),
                                       "physicalNvidiaVerified": False, "66461IdentityBound": False,
                                       "66463IdentityBound": False},
               "restoredSourceCapsule": {"originalBindingsRestored": 73, "operationalClosureFiles": 7,
                                         "totalFiles": 80, "existingSourceChanged": False} if capsule_verification else None}
    out = ROOT / "reports"
    out.mkdir(exist_ok=True)
    write_json(out / "PRIMARY_EVIDENCE.json", primary)
    ledger = {"schema": "WORLD_ENGINE_COMPLETE_65422_CAUSE_LEDGER_V1", "baseCommit": BASE,
              "originalSourceCommit": SOURCE, "originalProofCommit": PROOF,
              "statusDefinitions": {"CONFIRMED": "Specific fact or difference supported by cited primary input/code/execution evidence; not every confirmed fact is a defect.",
                                    "RULED_OUT": "Excluded only within the stated tested evidence scope.",
                                    "UNVERIFIED": "Missing evidence or pending fresh comparison; no inferred success."},
              "allCausesResolved": False,
              "actualReproductionDecision": fresh_comparison["status"] if fresh_comparison else "SEE_FRESH_CAPTURE_AND_150_FRAME_COMPARISON",
              "namedComparisonFileLimit": "No verified66461/66463 filename→SHA mapping; known3899 investigated separately.",
              "counts": dict(Counter(r["status"] for r in rows)), "candidates": rows}
    write_json(out / "ROOT_CAUSE_LEDGER.json", ledger)
    with (out / "ROOT_CAUSE_LEDGER.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "evidence": " | ".join(row["evidence"])})
    lines = ["# 65422 전체 원인 후보 조사", "", "원본 가상 시나리오의 재현과 역사80초 영상의 개선은 서로 다른 작업이다. 기존 자료는 새 원인으로 추측해 채우지 않았다.", "",
             "`CONFIRMED`는 지정 범위에서 증명된 사실/차이이며 모든 항목이 코드 결함이라는 뜻은 아니다. `RULED_OUT`은 지정된 실제 파일/실행 범위에 한정된다. `UNVERIFIED`는 증거 부족 또는 새 비교 대기다.", "",
             f"총 {len(rows)}건: " + ", ".join(f"{k} {v}" for k, v in ledger["counts"].items()), "",
             "66461·66463 파일명과 실제 SHA 연결은 확인되지 않았다. SHA3899d87c…의 알려진 역사 프리뷰를 해당 파일로 단정하지 않았다.", "",
             "| ID | 분류 | 상태 | 확인 내용 / 조치 |", "|---|---|---|---|"]
    for row in rows:
        lines.append(f"| {row['id']} | {row['category']} | {row['status']} | {row['finding']} **조치:** {row['action']} |")
    lines += ["", "각 항목의 코드 위치·Git source SHA·원본 실행 기록은 JSON/CSV와 `PRIMARY_EVIDENCE.json`에 기록했다. 새 영상의 실제 재현 판정은 별도150프레임 비교 결과를 따른다. 원본 셰이더/장면/카메라를 임의 수정하지 않았다.", ""]
    (out / "ROOT_CAUSE_LEDGER.md").write_text("\n".join(lines))
    print(json.dumps({"candidateCount": len(rows), "counts": ledger["counts"], "primaryAssertions": "PASS",
                      "unresolvedIdentityAndEnvironmentEvidenceRetained": True}))


if __name__ == "__main__":
    main()
