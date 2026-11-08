"""Private Dropbox transfer using the existing Studio backup credentials.

Never log provider responses, credentials, remote paths, or file contents.
Only an exact basename and expected SHA256 select an input.
"""
import hashlib
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request


def token():
    prefix = "WORLD_ENGINE_STUDIO_BACKUP_DROPBOX_"
    fields = {"grant_type": "refresh_token", "refresh_token": os.environ[prefix + "REFRESH_TOKEN"],
              "client_id": os.environ[prefix + "APP_KEY"], "client_secret": os.environ[prefix + "APP_SECRET"]}
    request = urllib.request.Request("https://api.dropboxapi.com/oauth2/token", data=urllib.parse.urlencode(fields).encode())
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)["access_token"]


def rpc(access, endpoint, payload):
    request = urllib.request.Request("https://api.dropboxapi.com/2/" + endpoint,
        data=json.dumps(payload).encode(), headers={"Authorization": "Bearer " + access, "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def download_exact(access, basename, digest, destination):
    result = rpc(access, "files/search_v2", {"query": basename, "options": {"filename_only": True, "max_results": 100}})
    matches = [m["metadata"]["metadata"] for m in result.get("matches", [])
               if m.get("metadata", {}).get("metadata", {}).get("name") == basename]
    if result.get("has_more") or len(matches) != 1 or matches[0].get(".tag") != "file":
        raise RuntimeError(json.dumps({"code": "PRIVATE_INPUT_SELECTION_FAILED",
            "exactMatches": len(matches), "hasMore": bool(result.get("has_more")),
            "returnedMatches": len(result.get("matches", [])),
            "metadataTags": [m.get(".tag") for m in matches]}))
    request = urllib.request.Request("https://content.dropboxapi.com/2/files/download", data=b"",
        headers={"Authorization": "Bearer " + access, "Dropbox-API-Arg": json.dumps({"path": matches[0]["id"]})})
    checksum = hashlib.sha256()
    destination = pathlib.Path(destination)
    with urllib.request.urlopen(request, timeout=180) as response, destination.open("xb") as target:
        while block := response.read(4 * 1024 * 1024):
            target.write(block)
            checksum.update(block)
    if checksum.hexdigest() != digest:
        raise RuntimeError("PRIVATE_INPUT_HASH_MISMATCH")
    return {"status": "PRIVATE_TRANSFER_PASS", "sha256": digest, "bytes": destination.stat().st_size}


if __name__ == "__main__":
    try:
        print(json.dumps(download_exact(token(), *sys.argv[1:])))
    except Exception as error:
        print(json.dumps({"status": "PRIVATE_TRANSFER_BLOCKED", "errorType": type(error).__name__,
            "detail": str(error) if isinstance(error, RuntimeError) else "PROVIDER_ERROR_REDACTED"}), flush=True)
        sys.exit(1)
