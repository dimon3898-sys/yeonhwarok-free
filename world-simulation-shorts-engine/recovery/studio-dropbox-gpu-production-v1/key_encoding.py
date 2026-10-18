"""Represent the SAME recovery key in the frozen reader's canonical format."""
from __future__ import annotations

import base64
import binascii


def canonical_key(value):
    try:
        if not isinstance(value, str):
            raise ValueError()
        text = value.encode('ascii').decode('ascii').strip()
        if len(text) != 44:
            raise ValueError()
        decoded = base64.b64decode(text.encode('ascii'), altchars=b'-_', validate=True)
        standard = base64.b64encode(decoded).decode('ascii')
        canonical = base64.urlsafe_b64encode(decoded).decode('ascii')
        if len(decoded) != 32 or text not in {standard, canonical}:
            raise ValueError()
        if base64.urlsafe_b64decode(canonical) != decoded:
            raise ValueError()
        return canonical
    except (UnicodeError, ValueError, TypeError, binascii.Error):
        raise RuntimeError('STARTUP_BACKUP_KEY_ENCODING_INVALID') from None
