#!/usr/bin/env python3
"""Bounded, read-only gCube evidence; reuse the audited official CLI helpers.

This tool never changes a workload, provisions a GPU, logs in, or publishes raw
logs/environment values. Credentials exist only in the invoking Actions step.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

PRIOR = Path(__file__).resolve().parent.parent / 'studio-auth-recovery-v2'
sys.path.insert(0, str(PRIOR))
import collector
import rest_evidence

EXPECTED_ORIGIN = 'https://ae20158c.service.gcube.ai:24999'
EXPECTED_TAG = 'studio-https-v1-85aef26-39082529518-1'
EXPECTED_DIGEST = 'sha256:468deaa122ec9c687908e2142d1a5cd82331a8bc447d62154eabb5ff7c416833'
PREFIX = 'ghcr.io/dimon3898-sys/world-simulation-shorts-engine'
PROXY_CODES = frozenset({'INVALID_FORWARDED_HEADERS', 'INVALID_HOST', 'INVALID_ORIGIN',
    'STUDIO_SETUP_SAME_ORIGIN_REQUIRED', 'STUDIO_HTTPS_SETUP_REQUIRED'})


def public_gets():
    """No owner credential or setting mutation; responses are enum-only."""
    variants = [('health', '/healthz', {}), ('setup', '/setup', {}),
        ('browser_challenge', '/setup/challenge', {'Sec-Fetch-Site': 'same-origin'}),
        ('origin_challenge', '/setup/challenge', {'Sec-Fetch-Site': 'same-origin', 'Origin': EXPECTED_ORIGIN}),
        ('forwarded_challenge', '/setup/challenge', {'Sec-Fetch-Site': 'same-origin', 'Origin': EXPECTED_ORIGIN,
            'X-Forwarded-Proto': 'https', 'X-Forwarded-Host': 'ae20158c.service.gcube.ai:24999'}),
        ('standard_forwarded_challenge', '/setup/challenge', {'Sec-Fetch-Site': 'same-origin', 'Origin': EXPECTED_ORIGIN,
            'Forwarded': 'proto=https;host="ae20158c.service.gcube.ai:24999"'})]
    results = []
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(NoRedirect())
    for name, path, headers in variants:
        result = {'request_variant': name, 'method': 'GET', 'path': path,
            'raw_response_published': False, 'server_incoming_headers_observed': False}
        try:
            request = urllib.request.Request(EXPECTED_ORIGIN + path, headers=headers, method='GET')
            try:
                response = opener.open(request, timeout=8)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                data = response.read(32769)
                result['http_status'] = response.status
                result['response_over_limit'] = len(data) > 32768
                cookies = response.headers.get_all('Set-Cookie', [])
                result['cookie_count'] = len(cookies)
                result['cookies_all_secure_http_only_strict'] = bool(cookies) and all(
                    all(required in value.lower() for required in ('secure', 'httponly', 'samesite=strict')) for value in cookies)
                try:
                    payload = json.loads(data)
                except (ValueError, TypeError):
                    payload = None
                if isinstance(payload, dict):
                    code = payload.get('error', {})
                    code = code.get('code') if isinstance(code, dict) else None
                    result['error_code'] = code if code in PROXY_CODES else 'WITHHELD_UNKNOWN' if code else None
                    result['challenge_present'] = isinstance(payload.get('challenge'), str)
                    result['service_mode'] = payload.get('mode') if payload.get('mode') in ('SETUP', 'CONFIGURED') else None
                    result['render_allowed'] = payload.get('renderAllowed') is True
                if name == 'setup':
                    result['setup_html_present'] = b'<html' in data.lower() and b'setup' in data.lower()
        except Exception as error:
            result['error_category'] = type(error).__name__ if type(error).__name__ in {'URLError', 'TimeoutError', 'OSError'} else 'UNEXPECTED_ERROR'
        results.append(result)
    return {'schema': 'WORLD_ENGINE_STUDIO_PUBLIC_READONLY_PROBE_V1', 'operations': results,
        'state_changes': 0, 'paid_operations': 0,
        'limits': ['CLIENT_SENT_HEADERS_ARE_NOT_SERVER_OBSERVED_HEADERS', 'NO_AUTHENTICATION_OR_ORIGIN_REGISTRATION_ATTEMPTED']}


def current_configuration(container):
    """Reuse existing environment shape/format checks, with this image binding."""
    summary = rest_evidence.environment_summary(container)
    checks = summary.get('configuration_checks')
    if not isinstance(checks, dict):
        return summary
    checks.pop('image_digest_matches_approved', None)
    checks.pop('configured_image_matches_approved', None)
    values = {key: value for row in container['containerEnvs'] for key, value in row.items()}
    checks['image_digest_matches_https_baseline'] = values.get('WORLD_ENGINE_UNIVERSAL_IMAGE_DIGEST') == EXPECTED_DIGEST
    checks['origin_matches_user_confirmed_service'] = values.get('WORLD_ENGINE_STUDIO_PUBLIC_ORIGIN') == EXPECTED_ORIGIN
    image = container.get('containerImage')
    checks['configured_image_matches_https_baseline'] = image in {
        EXPECTED_TAG, PREFIX + ':' + EXPECTED_TAG, PREFIX.removeprefix('ghcr.io/') + ':' + EXPECTED_TAG,
        PREFIX + '@' + EXPECTED_DIGEST}
    # Only the user-confirmed public URL may leave this process. No guessed or
    # arbitrary address, private service ID, hostname, or environment value.
    service = container.get('serviceUrl')
    summary['service_url_matches_user_confirmed_origin'] = isinstance(service, str) and service.rstrip('/') == EXPECTED_ORIGIN
    return summary


def safe_proxy_errors(documents):
    """Return closed error enums only; never echo supplied header values."""
    result = []
    def visit(value, depth=0):
        if depth > 16 or len(result) >= 16:
            return
        if isinstance(value, list):
            for item in value[:1000]:
                visit(item, depth + 1)
        elif isinstance(value, dict):
            code = value.get('errorCode', value.get('error_code', value.get('code')))
            if isinstance(code, str) and code in PROXY_CODES:
                result.append({'error_code': code, 'source': 'structured_container_log'})
            for key in ('logs', 'records', 'events', 'diagnostics', 'data', 'error'):
                if key in value:
                    visit(value[key], depth + 1)
    for document in documents:
        visit(document)
    return result


def collect_rest(environ=None, *, factory=rest_evidence.official_api):
    environ = os.environ if environ is None else environ
    result = {'schema': 'WORLD_ENGINE_STUDIO_PROXY_REMOTE_EVIDENCE_V1',
        'workload': 5373, 'utc': datetime.now(timezone.utc).isoformat(),
        'status': 'BLOCKED', 'authenticated_workload_read_succeeded': False,
        'state_changes': 0, 'paid_operations': 0, 'raw_outputs_published': False,
        'credential_values_published': False, 'actual_proxy_headers_available': False,
        'actual_container_exit_code': None, 'proxy_errors': [], 'operations': []}
    token = environ.get('GCUBE_ACCESS_TOKEN')
    if not isinstance(token, str) or not token:
        result['blocking_reason'] = 'APPROVED_SECRET_CREDENTIAL_NOT_PROVIDED'
        return result
    operation = 'OFFICIAL_CLIENT_INITIALIZATION'
    with tempfile.TemporaryFile(mode='w+') as private:
        os.fchmod(private.fileno(), 0o600)
        with redirect_stdout(private), redirect_stderr(private):
            try:
                api = factory(token)
                operation = 'WORKLOAD_DESCRIBE'
                workload = api.describe('5373')
                raw = getattr(workload, 'raw', {})
                if not isinstance(raw, dict) or str(raw.get('ser')) != '5373':
                    result['blocking_reason'] = 'WORKLOAD_ID_NOT_VERIFIED'
                    return result
                result['authenticated_workload_read_succeeded'] = True
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                result['workload_state'] = collector.closed_value(raw.get('state'), rest_evidence.RAW_STATES, 'WITHHELD_UNKNOWN')
                containers = raw.get('containerArray')
                if isinstance(containers, list) and len(containers) == 1 and isinstance(containers[0], dict):
                    result['configuration'] = current_configuration(containers[0])
                operation = 'WORKLOAD_PODS'
                pods = api.pods('5373')
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                result['pod_count'] = len(pods) if isinstance(pods, list) else None
                result['pod_statuses'] = [collector.closed_value(pod.get('status'), rest_evidence.POD_STATES, 'WITHHELD_UNKNOWN')
                    for pod in pods if isinstance(pod, dict)] if isinstance(pods, list) else []
                records = collector.terminated_states({'pods': pods})
                result['terminated_container_records'] = records
                codes = {record['exit_code'] for record in records}
                if len(codes) == 1:
                    result['actual_container_exit_code'] = next(iter(codes))
                if not isinstance(pods, list) or len(pods) != 1 or not isinstance(pods[0], dict):
                    result['blocking_reason'] = 'UNAMBIGUOUS_EXISTING_POD_REQUIRED'
                    return result
                pod = pods[0].get('name')
                if not isinstance(pod, str) or not rest_evidence.POD_NAME.fullmatch(pod) or '..' in pod:
                    result['blocking_reason'] = 'AUTHORIZED_POD_NAME_NOT_VALIDATED'
                    return result
                operation = 'OFFICIAL_HTTP_POD_LOGS'
                logs = api.logs('5373', pod)
                documents, oversized = rest_evidence.log_documents(logs)
                result['operations'].append({'operation': operation, 'status': 'SUCCEEDED'})
                result['log_size_limit_exceeded'] = oversized
                result['structured_log_document_count'] = len(documents)
                result['first_actual_error'] = collector.first_error(documents)
                result['proxy_errors'] = safe_proxy_errors(documents)
                result['status'] = 'READ_ONLY_EVIDENCE_COLLECTED'
            except (Exception, SystemExit) as error:
                safe = rest_evidence.safe_exception(error)
                result['operations'].append({'operation': operation, **safe})
                result['blocking_reason'] = safe['error_category']
    result['limits'] = ['UNRECORDED_PROXY_HEADERS_NOT_INFERRED',
        'CLI_EXIT_CODE_IS_NOT_CONTAINER_EXIT_CODE', 'NO_GPU_DEPLOYMENT_OR_REMOTE_CONFIGURATION_CHANGE']
    return result


def bounded_runner(binary, args, environ, timeout_seconds):
    return collector.capture_command(binary, args, environ, min(timeout_seconds, 25))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cli', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rest-only', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.rest_only:
        result = collect_rest()
        fd = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as target:
            json.dump(result, target, indent=2, sort_keys=True)
            target.write('\n')
        return
    args.output.mkdir(parents=True, exist_ok=False)
    public = public_gets()
    # Reuse the audited exact command allowlist and private bounded capture.
    cli = collector.collect(binary=args.cli, runner=bounded_runner)
    # The official client retries bounded GETs, but its per-call timeout is
    # sixty seconds. Bound the whole optional HTTP branch in a child process
    # so evidence from the CLI/public service is always preserved.
    with tempfile.TemporaryDirectory(prefix='studio-rest-private-') as private:
        os.chmod(private, 0o700)
        report = Path(private) / 'rest.json'
        try:
            child = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
                '--cli', args.cli, '--output', str(report), '--rest-only'],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=120, check=False)
            if child.returncode != 0 or not report.is_file():
                raise RuntimeError('OPTIONAL_HTTP_COLLECTOR_FAILED')
            rest = json.loads(report.read_text())
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            rest = {'schema': 'WORLD_ENGINE_STUDIO_PROXY_REMOTE_EVIDENCE_V1',
                'status': 'BLOCKED', 'blocking_reason': 'OFFICIAL_HTTP_COLLECTOR_TIMEOUT_OR_FAILURE',
                'authenticated_workload_read_succeeded': False, 'raw_outputs_published': False,
                'actual_proxy_headers_available': False, 'state_changes': 0, 'paid_operations': 0}
    for name, value in [('CLI_RESULT.json', cli), ('REMOTE_RESULT.json', rest), ('PUBLIC_PROBE.json', public)]:
        path = args.output / name
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
    print(json.dumps({'authenticated_workload_read_succeeded': rest['authenticated_workload_read_succeeded'],
                      'status': rest['status'], 'raw_outputs_published': False}))


if __name__ == '__main__':
    main()
