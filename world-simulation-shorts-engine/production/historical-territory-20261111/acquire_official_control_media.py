#!/usr/bin/env python3
"""One-shot public source acquisition only. No renderer, image build or GPU."""
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

SOURCE = 'https://anzacportal.dva.gov.au/wars-and-missions/korean-war/strategic-map'
OUTPUT = Path('territory-source-evidence')
PAGE_LIMIT = 8 * 1024 * 1024
MEDIA_LIMIT = 160 * 1024 * 1024
HOSTS = {'anzacportal.dva.gov.au', 'www.dva.gov.au', 'dva.gov.au',
         'player.vimeo.com', 'vimeo.com', 'www.youtube.com', 'www.youtube-nocookie.com'}
MEDIA_SUFFIXES = ('.mp4', '.webm', '.swf')


def allowed(url):
    p = urllib.parse.urlsplit(url)
    return p.scheme == 'https' and p.hostname in HOSTS and not p.username and not p.password and p.port in (None, 443)


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('REDIRECT_HOST_NOT_ADMITTED: ' + urllib.parse.urlsplit(newurl).netloc)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Links(HTMLParser):
    def __init__(self, base):
        super().__init__()
        self.base = base
        self.media = set()
        self.frames = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for key in ('src', 'href', 'data', 'data-src'):
            value = attrs.get(key)
            if not value:
                continue
            url = urllib.parse.urljoin(self.base, html.unescape(value))
            if tag == 'iframe' and key in ('src', 'data-src') and 'googletagmanager' not in url:
                self.frames.add(url)
            if urllib.parse.urlsplit(url).path.lower().endswith(MEDIA_SUFFIXES):
                self.media.add(url)


def retrieve(url, filename, limit):
    if not allowed(url):
        raise ValueError('SOURCE_HOST_NOT_ADMITTED: ' + urllib.parse.urlsplit(url).netloc)
    request = urllib.request.Request(url, headers={'User-Agent': 'WORLD-ENGINE-public-source-review/1.0'})
    opener = urllib.request.build_opener(SafeRedirect())
    with opener.open(request, timeout=30) as response:
        size = response.headers.get('Content-Length')
        if size and int(size) > limit:
            raise ValueError('SOURCE_SIZE_LIMIT')
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('SOURCE_SIZE_LIMIT')
        record = {'requestedURL': url, 'finalURL': response.url, 'httpStatus': response.status,
                  'contentType': response.headers.get('Content-Type', ''), 'bytes': len(raw),
                  'sha256': hashlib.sha256(raw).hexdigest(), 'file': filename}
    (OUTPUT / filename).write_bytes(raw)
    return raw, record


def extract(text, base):
    parser = Links(base)
    parser.feed(text)
    normalized = html.unescape(text).replace('\\/', '/')
    for url in re.findall(r'https://[^\s"<>]+?\.(?:mp4|webm|swf)(?:\?[^\s"<>]*)?', normalized):
        parser.media.add(url)
    return parser


def main():
    OUTPUT.mkdir(exist_ok=False)
    report = {'schema': 'WORLD_ENGINE_PUBLIC_CONTROL_SOURCE_ACQUISITION_V1',
              'status': 'STARTED', 'sourceURL': SOURCE, 'attemptsPerURL': 1,
              'sourceFiles': [], 'mediaCandidates': [], 'embeddedPages': [], 'errors': [],
              'gpuRuns': 0, 'renders': 0, 'imageBuilds': 0, 'oldPASSReruns': 0,
              'historicalControlGeometryAdmitted': False,
              'scope': 'PUBLIC_SOURCE_BYTES_ONLY_NOT_HISTORICAL_OR_RENDER_QUALIFICATION'}
    media = set()
    try:
        raw, record = retrieve(SOURCE, 'official-page.html', PAGE_LIMIT)
        report['sourceFiles'].append(record)
        parser = extract(raw.decode('utf-8', errors='replace'), record['finalURL'])
        media.update(parser.media)
        report['embeddedPages'] = sorted(parser.frames)
        for index, url in enumerate(sorted(parser.frames)[:4]):
            if not allowed(url):
                report['errors'].append({'url': url, 'error': 'EMBEDDED_HOST_NOT_ADMITTED'})
                continue
            try:
                data, rec = retrieve(url, f'embedded-page-{index}.html', PAGE_LIMIT)
                report['sourceFiles'].append(rec)
                media.update(extract(data.decode('utf-8', errors='replace'), rec['finalURL']).media)
            except Exception as exc:
                report['errors'].append({'url': url, 'error': str(exc)})
        report['mediaCandidates'] = sorted(media)
        for index, url in enumerate(sorted(media)[:4]):
            if not allowed(url):
                report['errors'].append({'url': url, 'error': 'MEDIA_HOST_NOT_ADMITTED'})
                continue
            try:
                suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
                _, rec = retrieve(url, f'official-media-{index}{suffix}', MEDIA_LIMIT)
                report['sourceFiles'].append(rec)
            except Exception as exc:
                report['errors'].append({'url': url, 'error': str(exc)})
        got_media = any(row['file'].startswith('official-media-') for row in report['sourceFiles'])
        report['status'] = 'SOURCE_MEDIA_RETRIEVED_PENDING_REVIEW' if got_media else 'BLOCKED_MEDIA_SOURCE_NOT_RETRIEVED'
    except Exception as exc:
        report['errors'].append({'url': SOURCE, 'error': str(exc)})
        report['status'] = 'BLOCKED_SOURCE_PAGE_RETRIEVAL'
    (OUTPUT / 'SOURCE_ACQUISITION_RESULT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'files': len(report['sourceFiles']),
                      'mediaCandidates': len(report['mediaCandidates']), 'errors': report['errors']}))
    # A successful execution means the evidence was captured; report.status is the source gate.
    # No retry or alternate renderer follows a BLOCKED result.


if __name__ == '__main__':
    main()
