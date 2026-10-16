"""Synthetic transport tests; no official document or real network is asserted."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
import urllib.error
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from source_acquisition import acquire, checked_url, ApprovedRedirects, SourceError


URL = 'https://source.example.invalid/document.pdf'
HOSTS = ['source.example.invalid']
PDF = b'%PDF-1.4\nSYNTHETIC_TRANSPORT_BYTES_NOT_A_HISTORICAL_MAP\n%%EOF\n'


class Response(io.BytesIO):
    status = 200
    def __init__(self, body, *, length=None, url=URL):
        super().__init__(body)
        self.headers = {'Content-Type': 'application/pdf', 'Content-Length': str(len(body)) if length is None else str(length)}
        self.url = url
    def geturl(self):
        return self.url


class Opener:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, 0
    def open(self, request, timeout):
        self.calls += 1
        if self.error:
            raise self.error
        return self.response


class SourceAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / 'source.pdf'
    def tearDown(self):
        self.directory.cleanup()
    def fetch(self, opener, **kwargs):
        return acquire(URL, self.path, allowed_hosts=HOSTS, opener=opener, **kwargs)
    def test_complete_bytes_hash_but_no_historical_or_license_claim(self):
        row = self.fetch(Opener(Response(PDF)))
        self.assertEqual(row['originalSHA256'], hashlib.sha256(PDF).hexdigest())
        self.assertEqual(self.path.read_bytes(), PDF)
        self.assertFalse(row['historicalFrontVerified'])
        self.assertFalse(row['licenseVerified'])
        self.assertEqual(row['status'], 'RAW_SOURCE_ACQUIRED_REVIEW_REQUIRED')
    def test_error_html_not_original_map(self):
        error = urllib.error.HTTPError(URL, 403, 'Forbidden', {}, io.BytesIO(b'<html>Access Denied</html>'))
        row = self.fetch(Opener(error=error))
        self.assertEqual(row['status'], 'HTTP_FAILURE')
        self.assertIsNone(row['originalSHA256'])
        self.assertFalse(self.path.exists())
    def test_http200_html_is_not_pdf(self):
        row = self.fetch(Opener(Response(b'<html>error</html>')))
        self.assertEqual(row['status'], 'INVALID_OR_INCOMPLETE_SOURCE')
        self.assertFalse(self.path.exists())
    def test_truncated_pdf_is_rejected(self):
        row = self.fetch(Opener(Response(PDF, length=len(PDF)+10)))
        self.assertFalse(row['sourceBodyRetrieved'])
        self.assertFalse(self.path.exists())
    def test_incomplete_pdf_eof_is_rejected(self):
        row = self.fetch(Opener(Response(PDF[:-7])))
        self.assertFalse(row['sourceBodyRetrieved'])
    def test_size_bound_is_enforced(self):
        row = self.fetch(Opener(Response(PDF)), max_bytes=8)
        self.assertFalse(row['sourceBodyRetrieved'])
        self.assertFalse(self.path.exists())
    def test_no_overwrite_or_network_for_existing_source(self):
        self.path.write_bytes(b'existing')
        opener = Opener(Response(PDF))
        with self.assertRaisesRegex(SourceError, 'OVERWRITE'):
            self.fetch(opener)
        self.assertEqual(opener.calls, 0)
        self.assertEqual(self.path.read_bytes(), b'existing')
    def test_proxy_denial_is_not_retried(self):
        opener = Opener(error=urllib.error.URLError('Tunnel connection failed: 403 Forbidden'))
        row = self.fetch(opener)
        self.assertEqual(row['reasonCode'], 'PROXY_CONNECT_403')
        self.assertEqual(opener.calls, 1)
        self.assertFalse(row['sourceBodyRetrieved'])
    def test_cross_host_final_response_is_rejected(self):
        with self.assertRaisesRegex(SourceError, 'APPROVED_HTTPS'):
            ApprovedRedirects(HOSTS).redirect_request(None, None, 302, '', {}, 'https://other.invalid/source.pdf')
        row = self.fetch(Opener(Response(PDF, url='https://other.invalid/map.pdf')))
        self.assertFalse(row['sourceBodyRetrieved'])
    def test_https_tls_and_secret_url_boundary(self):
        for url in ['http://source.example.invalid/a', 'https://u:p@source.example.invalid/a', URL+'?token=sensitive']:
            with self.assertRaises(SourceError):
                checked_url(url, HOSTS)
    def test_html_discovery_cannot_be_map_evidence(self):
        row = self.fetch(Opener(Response(b'<html>official index</html>')), kind='HTML')
        self.assertEqual(row['sourceRole'], 'DISCOVERY_PAGE_ONLY')
        self.assertFalse(row['mapLegendVerified'])


if __name__ == '__main__':
    unittest.main()
