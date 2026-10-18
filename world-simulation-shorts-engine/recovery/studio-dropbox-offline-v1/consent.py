#!/usr/bin/env python3
"""One-time offline consent: hidden input and a private Secret file, no GPU.

This tool never prints an authorization code, app secret, refresh/access token,
or HTTP response. Authorization URLs contain the public app key and scopes only.
The resulting private file must be retained in an approved Secret store.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import sys
import urllib.parse

from offline_frozen import HERE, modules
from renewal import REQUIRED_SCOPES, token_request


def fail(code):
    raise modules().stores.BackupError(code)


def credential(value, *, identifier=False, minimum=8, maximum=4096):
    if (not isinstance(value, str) or not minimum <= len(value) <= maximum
            or any(not 33 <= ord(c) <= 126 for c in value)
            or identifier and not re.fullmatch('[A-Za-z0-9_-]+', value)):
        fail('DURABILITY_OAUTH_ENROLL_INPUT_INVALID')
    return value


def read_input(path, prompt, *, identifier=False, minimum=8, maximum=4096):
    if path is not None:
        try:
            value = modules().stores.read_private_file(path, limit=maximum + 2).decode('ascii').strip()
        except modules().stores.BackupError:
            raise
        except Exception:
            fail('DURABILITY_OAUTH_ENROLL_INPUT_INVALID')
    else:
        if not sys.stdin.isatty():
            fail('DURABILITY_OAUTH_PRIVATE_INPUT_REQUIRED')
        value = getpass.getpass(prompt).strip()
    return credential(value, identifier=identifier, minimum=minimum, maximum=maximum)


def authorize_url(app_key):
    credential(app_key, identifier=True, maximum=256)
    # Official NoRedirect authorization-code flow. A code is shown by Dropbox;
    # it is entered privately into this process, never returned in our URL.
    return 'https://www.dropbox.com/oauth2/authorize?' + urllib.parse.urlencode({
        'client_id': app_key, 'response_type': 'code', 'token_access_type': 'offline',
        'scope': ' '.join(sorted(REQUIRED_SCOPES)),
    })


def output_path(path):
    destination = Path(path)
    source_root = HERE if HERE.is_relative_to('/opt') else HERE.parents[2]
    if (not destination.is_absolute() or '..' in destination.parts
            or destination.is_relative_to('/world-storage')
            or destination.is_relative_to(source_root)
            or any(p.is_symlink() for p in (destination, *destination.parents))):
        fail('DURABILITY_OAUTH_PRIVATE_SECRET_OUTPUT_REQUIRED')
    return destination


def write_refresh_secret(path, value):
    credential(value, minimum=16)
    destination = output_path(path)
    cache = modules().checkpoint.modules()['cache']
    # Existing strict directory policy: current contract is UID/GID 1000,
    # owned 0700 parent, no links. No existing credential is replaced.
    with cache.PrivateTree(destination.parent) as directory:
        fd = os.open(destination.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory.fd)
        try:
            data = (value + '\n').encode('ascii')
            while data:
                count = os.write(fd, data)
                if count <= 0:
                    fail('DURABILITY_OAUTH_SECRET_WRITE_FAILED')
                data = data[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(directory.fd)
    return str(destination)


def exchange(app_key, app_secret, code, output_file, *, opener=None):
    result = token_request({'grant_type': 'authorization_code',
        'client_id': credential(app_key, identifier=True, maximum=256),
        'client_secret': credential(app_secret, maximum=256),
        'code': credential(code)}, opener=opener)
    scopes = result.get('scope')
    refresh = result.get('refresh_token')
    if (not isinstance(scopes, str) or not REQUIRED_SCOPES.issubset(scopes.split())
            or not isinstance(result.get('token_type'), str)
            or result['token_type'].lower() != 'bearer'
            or type(result.get('expires_in')) is not int or result['expires_in'] <= 0):
        fail('DURABILITY_OAUTH_ENROLL_SCOPE_OR_RESPONSE_INVALID')
    credential(result.get('access_token'), minimum=16)
    credential(refresh, minimum=16)
    written = write_refresh_secret(output_file, refresh)
    return {'status': 'PASS', 'refreshSecretFile': written,
            'refreshTokenPrinted': False, 'requiredScopesGranted': True,
            'accessTokenPersisted': False, 'gpuExecuted': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-key-file', type=Path)
    parser.add_argument('--app-secret-file', type=Path)
    parser.add_argument('--authorization-code-file', type=Path)
    parser.add_argument('--refresh-secret-file', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if os.geteuid() != 1000 or os.getegid() != 1000:
            fail('DURABILITY_UID_GID_1000_REQUIRED')
        # Validate output parent before asking the user to approve anything.
        target = output_path(args.refresh_secret_file)
        with modules().checkpoint.modules()['cache'].PrivateTree(target.parent):
            pass
        if args.refresh_secret_file.exists() or args.refresh_secret_file.is_symlink():
            fail('DURABILITY_OAUTH_EXISTING_SECRET_PRESERVED')
        app_key = read_input(args.app_key_file, 'Dropbox App key (hidden): ', identifier=True, maximum=256)
        app_secret = read_input(args.app_secret_file, 'Dropbox App secret (hidden): ', maximum=256)
        print('Open this official Dropbox URL, sign in, then choose Allow:', flush=True)
        print(authorize_url(app_key), flush=True)
        code = read_input(args.authorization_code_file, 'Dropbox authorization code (hidden): ')
        print(json.dumps(exchange(app_key, app_secret, code, args.refresh_secret_file), sort_keys=True))
        return 0
    except Exception as error:
        code = getattr(error, 'code', str(error))
        if not isinstance(code, str) or not re.fullmatch('[A-Z][A-Z0-9_]{0,95}', code):
            code = 'DURABILITY_OAUTH_ENROLL_FAILED'
        print(json.dumps({'status': 'BLOCKED', 'errorCode': code, 'gpuExecuted': False}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
