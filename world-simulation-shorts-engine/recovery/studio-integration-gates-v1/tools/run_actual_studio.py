"""Single free G1 job through real mobile browser HTTP; no legacy output reuse."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gates_actual_service", HERE / "studio_service.py")
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def run(private_root):
    private_root.mkdir(mode=0o700, exist_ok=False)
    state_root = private_root / "state"
    state_root.mkdir(mode=0o700)
    owner = private_root / "owner-code"
    owner.write_text(secrets.token_urlsafe(32))
    owner.chmod(0o600)
    request = private_root / "REQUEST.json"
    request.write_text(json.dumps(service.controller_module.contract.REQUEST))
    request.chmod(0o600)
    exports = HERE / "captures"
    exports.mkdir(mode=0o700, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    # Actual prior image metadata only. New code is source checkout; no new OCI
    # image is built/deployed by this free source regression.
    image = "sha256:3add2c567190dae3618427befe90d15f0c183bd221c87d16736842bcc6ebb4c5"
    app = service.local_application(state_root=state_root, owner_file=owner, export_root=exports,
        port=port, image_digest=image, allow_software_reference=True)
    http = service.server.ThreadingHTTPServer(("127.0.0.1", port), service.server.make_handler(app))
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        subprocess.run(["node", str(HERE / "tools/mobile_client.mjs"), f"http://127.0.0.1:{port}",
                        str(private_root), str(request)], check=True, timeout=90)
        mobile = json.loads((private_root / "MOBILE_HTTP_START.json").read_bytes())
        job_id = mobile["jobId"]
        # Closing the whole HTTP server as well as the browser does not own or
        # kill the worker. Reconstructing the controller must not relaunch it.
        http.shutdown()
        http.server_close()
        app2 = service.local_application(state_root=state_root, owner_file=owner, export_root=exports,
            port=port, image_digest=image, allow_software_reference=True)
        state = app2.controller.start(mobile["submissionId"], "g1-reconnect-new-key-20261022", consent=True)
        if state["jobId"] != job_id:
            raise RuntimeError("RECONNECT_DUPLICATE_JOB")
        last = None
        for _ in range(190):
            state = app2.controller.status(job_id)
            current = (state["state"], state.get("processedFrames", 0))
            if current != last:
                print(json.dumps({"jobId": job_id, **state}), flush=True)
                last = current
            if state["state"] in {"COMPLETED", "FAILED", "INTERRUPTED"}:
                break
            time.sleep(5)
        else:
            raise RuntimeError("REFERENCE_SUPERVISION_LIMIT_REACHED")
        report = {**mobile, "httpServerStoppedDuringRender": True,
            "controllerRestartDuplicateJobId": state["jobId"], "finalState": state,
            "newImageBuilt": False, "deploymentPerformed": False, "paidGpuExecuted": False,
            "gpuRenderingVerified": False, "visualQualityApproved": False}
        (HERE / "reports/STUDIO_HTTP_EXECUTION.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        if state["state"] != "COMPLETED":
            raise RuntimeError("REFERENCE_JOB_NOT_COMPLETED")
    finally:
        http.shutdown()
        http.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    run(parser.parse_args().private_root)
