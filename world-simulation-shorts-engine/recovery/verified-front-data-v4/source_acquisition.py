#!/usr/bin/env python3
"""Bounded official-source retrieval; a download never certifies a historical front.

Uses the configured proxy/CA, follows only approved HTTPS redirects, never
retries implicitly and never overwrites an existing source. No network on import.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import ssl
import tempfile
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request


class SourceError(ValueError):
    pass


def checked_url(value, allowed_hosts):
    url = urllib.parse.urlsplit(value)
    if (url.scheme != 'https' or url.hostname not in allowed_hosts or
            url.username is not None or url.password is not None or
            url.port not in (None, 443) or url.fragment):
        raise SourceError('APPROVED_HTTPS_SOURCE_REQUIRED')
    if any(k.lower() in {'token', 'access_token', 'password', 'api_key', 'key'}
           for k, _ in urllib.parse.parse_qsl(url.query)):
        raise SourceError('CREDENTIAL_QUERY_FORBIDDEN')
    return value


class ApprovedRedirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_hosts):
        self.allowed_hosts = frozenset(allowed_hosts)

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_url(newurl, self.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def acquire(url, destination, *, allowed_hosts, kind='PDF', max_bytes=128 * 1024**2,
            timeout=25, opener=None):
    """Return a receipt; only complete PDFs/pages are source bytes, never error bodies.

    RAW_SOURCE_ACQUIRED still requires document/page/legend/license/georeference
    inspection. HTML pages are discovery material and never map/coordinate proof.
    """
    checked_url(url, allowed_hosts)
    if kind not in {'PDF', 'HTML'} or type(max_bytes) is not int or not 1 <= max_bytes <= 128 * 1024**2:
        raise SourceError('BOUNDED_SOURCE_KIND_REQUIRED')
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
        raise SourceError('BOUNDED_TIMEOUT_REQUIRED')
    destination = Path(destination).absolute()
    for part in [destination, *destination.parents]:
        if part.is_symlink():
            raise SourceError('SOURCE_SYMLINK_FORBIDDEN')
    if destination.exists():
        raise SourceError('SOURCE_OVERWRITE_FORBIDDEN')
    destination.parent.mkdir(parents=True, exist_ok=True)
    result = {'schema': 'WORLD_ENGINE_OFFICIAL_SOURCE_RECEIPT_V4', 'url': url,
              'retrievedAt': datetime.now(timezone.utc).isoformat(),
              'status': 'NOT_ACQUIRED', 'sourceBodyRetrieved': False,
              'originalSHA256': None, 'bytes': 0, 'licenseVerified': False,
              'mapLegendVerified': False, 'historicalFrontVerified': False,
              'tlsVerification': True, 'proxyPreserved': True, 'automaticRetries': 0}
    if opener is None:
        opener = urllib.request.build_opener(ApprovedRedirects(allowed_hosts),
                                            urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    temporary = None
    try:
        request = urllib.request.Request(url, headers={'User-Agent': 'WORLD-ENGINE-Research/4.0'})
        with opener.open(request, timeout=timeout) as response:
            checked_url(response.geturl(), allowed_hosts)
            result.update(httpStatus=response.status, finalURL=response.geturl(),
                          contentType=response.headers.get('Content-Type'))
            if response.status != 200:
                raise SourceError('HTTP_200_REQUIRED')
            declared = response.headers.get('Content-Length')
            if declared is not None and (not declared.isdigit() or int(declared) > max_bytes):
                raise SourceError('SOURCE_CONTENT_LENGTH_REJECTED')
            descriptor, temporary = tempfile.mkstemp(prefix='.acquiring-', dir=destination.parent)
            digest = hashlib.sha256()
            size, prefix, tail = 0, b'', b''
            with os.fdopen(descriptor, 'wb') as target:
                while block := response.read(min(1024 * 1024, max_bytes + 1 - size)):
                    size += len(block)
                    if size > max_bytes:
                        raise SourceError('SOURCE_SIZE_LIMIT')
                    prefix = (prefix + block)[:1024]
                    tail = (tail + block)[-4096:]
                    target.write(block)
                    digest.update(block)
                target.flush()
                os.fsync(target.fileno())
            if size == 0 or declared is not None and size != int(declared):
                raise SourceError('SOURCE_TRUNCATED_OR_EMPTY')
            if kind == 'PDF' and (not prefix.startswith(b'%PDF-') or b'%%EOF' not in tail):
                raise SourceError('PDF_BYTES_REQUIRED_NOT_HTML_OR_TRUNCATED')
            if kind == 'HTML' and not any(mark in prefix.lower() for mark in (b'<html', b'<!doctype html')):
                raise SourceError('HTML_BYTES_REQUIRED')
            # link is exclusive even if another process creates destination mid-fetch.
            os.link(temporary, destination, follow_symlinks=False)
            result.update(status='RAW_SOURCE_ACQUIRED_REVIEW_REQUIRED', sourceBodyRetrieved=True,
                          originalSHA256=digest.hexdigest(), bytes=size,
                          sourceRole='DOCUMENT_CANDIDATE' if kind == 'PDF' else 'DISCOVERY_PAGE_ONLY')
    except urllib.error.HTTPError as error:
        body = error.read(8192)
        result.update(status='HTTP_FAILURE', httpStatus=error.code,
                      errorBodySHA256=hashlib.sha256(body).hexdigest(),
                      errorBodyIsOriginalSource=False)
    except urllib.error.URLError as error:
        reason = str(error.reason)
        code = ('PROXY_CONNECT_403' if 'Tunnel connection failed: 403' in reason else
                'TLS_OR_TRANSPORT_FAILURE')
        result.update(status='ACCESS_FAILED', reasonCode=code)
    except (OSError, SourceError) as error:
        result.update(status='INVALID_OR_INCOMPLETE_SOURCE',
                      reasonCode=str(error) if isinstance(error, SourceError) else type(error).__name__)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)  # only this call's incomplete temporary file
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--allowed-host', action='append', required=True)
    parser.add_argument('--kind', choices=['PDF', 'HTML'], default='PDF')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = acquire(args.url, args.output, allowed_hosts=args.allowed_host, kind=args.kind)
        print(json.dumps(result))
        return 0 if result['sourceBodyRetrieved'] else 2
    except SourceError as error:
        print(json.dumps({'status': 'REJECTED', 'reasonCode': str(error)}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
