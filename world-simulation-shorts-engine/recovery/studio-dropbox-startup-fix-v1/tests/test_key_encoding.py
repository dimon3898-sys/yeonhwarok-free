"""Key representation compatibility without credentials, rotation or network.

These fixed byte strings are synthetic fixtures, never backup Secret values.
The unchanged consumer's canonical URL-safe check is reproduced with stdlib.
"""
from __future__ import annotations

import base64
import binascii
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from key_encoding import canonical_key


def frozen_parser_accepts(value):
    """The exact representation predicates in frozen vault.read_key_file()."""
    try:
        text = value.encode('ascii').decode('ascii').strip()
        raw = base64.b64decode(text.encode('ascii'), altchars=b'-_', validate=True)
    except (UnicodeError, ValueError, binascii.Error):
        return False
    return len(raw) == 32 and base64.urlsafe_b64encode(raw).decode('ascii') == text


class KeyEncodingTests(unittest.TestCase):
    # Both special alphabet symbols are present, so standard and URL-safe forms
    # differ and an alphabet-mixed input can be tested deterministically.
    RAW = b'\xfb\xff\xff' * 10 + b'\xfb\xff'

    def assert_rejected(self, value):
        with self.assertRaises(RuntimeError) as raised:
            canonical_key(value)
        message = str(raised.exception)
        self.assertRegex(message, r'^[A-Z][A-Z0-9_]{2,95}$')
        if isinstance(value, str) and len(value) > 3:
            self.assertNotIn(value, message)
        self.assertNotIn('SENSITIVE_INPUT_MARKER', message)

    def test_standard_special_symbols_fail_before_then_preserve_key_bytes(self):
        standard = base64.b64encode(self.RAW).decode('ascii')
        self.assertEqual(len(self.RAW), 32)
        self.assertIn('+', standard)
        self.assertIn('/', standard)
        self.assertFalse(frozen_parser_accepts(standard))
        normalized = canonical_key(standard)
        self.assertTrue(frozen_parser_accepts(normalized))
        self.assertEqual(normalized, base64.urlsafe_b64encode(self.RAW).decode('ascii'))
        self.assertEqual(base64.urlsafe_b64decode(normalized), self.RAW)
        self.assertEqual(len(normalized), 44)
        self.assertTrue(normalized.endswith('='))

    def test_already_urlsafe_encoding_is_unchanged_and_idempotent(self):
        existing = base64.urlsafe_b64encode(self.RAW).decode('ascii')
        self.assertIn('-', existing)
        self.assertIn('_', existing)
        self.assertEqual(canonical_key(existing), existing)
        self.assertEqual(canonical_key(canonical_key(existing)), existing)

    def test_standard_encoding_without_special_symbols_is_unchanged(self):
        raw = b'x' * 32
        existing = base64.b64encode(raw).decode('ascii')
        self.assertNotIn('+', existing)
        self.assertNotIn('/', existing)
        self.assertTrue(frozen_parser_accepts(existing))
        self.assertEqual(canonical_key(existing), existing)
        self.assertEqual(base64.urlsafe_b64decode(canonical_key(existing)), raw)

    def test_outer_ascii_whitespace_matches_existing_consumer_strip(self):
        standard = base64.b64encode(self.RAW).decode('ascii')
        expected = base64.urlsafe_b64encode(self.RAW).decode('ascii')
        self.assertEqual(canonical_key(' \t\r\n' + standard + '\n\t '), expected)

    def test_repeated_normalization_never_rotates_key(self):
        for index in (0, 1, 127, 255):
            with self.subTest(fixture=index):
                raw = bytes([index]) * 32
                standard = base64.b64encode(raw).decode('ascii')
                first, second = canonical_key(standard), canonical_key(standard)
                self.assertEqual(first, second)
                self.assertEqual(base64.urlsafe_b64decode(first), raw)

    def test_decoded_sizes_other_than_32_are_rejected(self):
        for size in (0, 1, 16, 24, 31, 33, 48, 64):
            for encoder in (base64.b64encode, base64.urlsafe_b64encode):
                with self.subTest(decoded_bytes=size, encoder=encoder.__name__):
                    self.assert_rejected(encoder(b'x' * size).decode('ascii'))

    def test_raw_text_and_hex_are_not_guessed_as_key_formats(self):
        for value in ('x' * 32, self.RAW.hex(), 'SENSITIVE_INPUT_MARKER_RAW_KEY'):
            with self.subTest(input_length=len(value)):
                self.assert_rejected(value)

    def test_unpadded_and_extra_padding_are_rejected(self):
        for encoder in (base64.b64encode, base64.urlsafe_b64encode):
            encoded = encoder(self.RAW).decode('ascii')
            for invalid in (encoded.rstrip('='), encoded + '=', encoded + '=='):
                with self.subTest(encoder=encoder.__name__, length=len(invalid)):
                    self.assert_rejected(invalid)

    def test_mixed_alphabets_are_rejected(self):
        standard = base64.b64encode(self.RAW).decode('ascii')
        # Strict b64decode(altchars=...) would accept these mixed forms; they
        # are neither canonical source encoding and must not be guessed.
        for mixed in (standard.replace('+', '-'), standard.replace('/', '_')):
            self.assertEqual(base64.b64decode(mixed, altchars=b'-_', validate=True), self.RAW)
            self.assert_rejected(mixed)

    def test_noncanonical_padding_bits_are_rejected(self):
        canonical = base64.b64encode(b'x' * 32).decode('ascii')
        alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
        offset = alphabet.index(canonical[-2])
        self.assertEqual(offset % 4, 0)
        noncanonical = canonical[:-2] + alphabet[offset + 1] + '='
        self.assertEqual(base64.b64decode(noncanonical, validate=True), b'x' * 32)
        self.assert_rejected(noncanonical)

    def test_non_ascii_and_internal_whitespace_are_rejected(self):
        canonical = base64.urlsafe_b64encode(self.RAW).decode('ascii')
        for invalid in ('\N{NO-BREAK SPACE}' + canonical, canonical + '\N{NO-BREAK SPACE}',
                        canonical[:12] + '\n' + canonical[12:],
                        canonical[:12] + ' ' + canonical[12:], '\N{SNOWMAN}'):
            with self.subTest(input_length=len(invalid)):
                self.assert_rejected(invalid)

    def test_invalid_types_and_failures_do_not_echo_input(self):
        for invalid in (None, True, 32, b'x' * 32, bytearray(b'x' * 32),
                        ['SENSITIVE_INPUT_MARKER'], {'value': 'SENSITIVE_INPUT_MARKER'}):
            with self.subTest(input_type=type(invalid).__name__):
                self.assert_rejected(invalid)
        self.assert_rejected('SENSITIVE_INPUT_MARKER+NOT-A-VALID-KEY')


if __name__ == '__main__':
    unittest.main()
