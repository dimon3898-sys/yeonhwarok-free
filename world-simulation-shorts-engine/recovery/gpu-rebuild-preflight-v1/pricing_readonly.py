#!/usr/bin/env python3
"""One official GET; emit only public RTX4080SUPER catalogue price fields.

No workload, SSH, deployment, billing-ledger or storage request is made.
Endpoint/price semantics reuse verified official gcube-cli0.4.2 source.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

ENDPOINT = 'https://api.gcube.ai/api/gpu/available/pricing/list'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 10**9


def safe_label(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9 ._+()/\-]{1,80}', value) else None


def sanitize_rows(rows):
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('PRICE_ARRAY_INVALID')
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name, ext = safe_label(row.get('gpuName')), safe_label(row.get('gpuExt'))
        combined = re.sub('[^A-Z0-9]', '', ((name or '') + (ext or '')).upper())
        if '4080' not in combined or 'SUPER' not in combined:
            continue
        currency = row.get('currencyUnit')
        price, surcharge = row.get('price'), row.get('usagePrice')
        valid = currency in ('KRW', 'USD') and finite_number(price) and finite_number(surcharge)
        item = {'gpuName': name, 'gpuExt': ext,
                'productName': safe_label(row.get('productName')),
                'currency': currency if currency in ('KRW', 'USD') else None,
                'priceFieldsComplete': valid,
                'nodesCount': len(row['nodes']) if isinstance(row.get('nodes'), list) else None,
                'actualSelectedNodeQuote': False}
        for key in ('gpu', 'vram', 'cpu', 'memory', 'disk'):
            item[key] = row.get(key) if finite_number(row.get(key)) else None
        if valid:
            item.update(hourlyCatalogueMin=price, hourlyCatalogueMax=round(price + surcharge, 8),
                        threeHourCatalogueMin=round(3 * price, 8),
                        threeHourCatalogueMax=round(3 * (price + surcharge), 8))
        result.append(item)
    return result


def collect():
    out = {'schema': 'WORLD_ENGINE_GPU_REBUILD_READONLY_PRICING_V1',
           'observedUTC': datetime.now(timezone.utc).isoformat(),
           'endpoint': ENDPOINT, 'method': 'GET', 'requestLimit': 1,
           'status': 'BLOCKED', 'workloadMutations': 0, 'sshAttempts': 0,
           'paidOperations': 0, 'rendererInvoked': False, 'credentialsPublished': False,
           'actualSelectedNodeQuote': False,
           'priceSemantics': 'Official CLI catalogue hourly price..price+usagePrice; not a selected-node invoice.',
           'exclusions': 'Provider tax, rounding, storage, network, deployment preparation and idle time not quoted.'}
    token = os.environ.get('GCUBE_ACCESS_TOKEN')
    if not token:
        return {**out, 'reason': 'APPROVED_REPOSITORY_SECRET_UNAVAILABLE'}
    try:
        opener = urllib.request.build_opener(NoRedirect())
        request = urllib.request.Request(ENDPOINT, method='GET', headers={
            'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
        with opener.open(request, timeout=35) as response:
            out['httpStatus'] = response.status
            body = response.read(4 * 1024**2 + 1)
        if len(body) > 4 * 1024**2:
            return {**out, 'reason': 'RESPONSE_SIZE_LIMIT'}
        document = json.loads(body)
        if not isinstance(document, dict) or document.get('status') != 200:
            return {**out, 'reason': 'API_STATUS_NOT_200'}
        rows = sanitize_rows(document.get('pricings', document.get('data')))
        out.update(rows=rows, matchedRows=len(rows), status='CATALOGUE_OBSERVED' if rows else 'NO_MATCHING_CATALOGUE_ROWS')
    except urllib.error.HTTPError as error:
        out.update(httpStatus=error.code, reason='HTTP_REQUEST_FAILED')
    except Exception as error:
        out.update(reason='READ_ONLY_QUERY_FAILED', errorType=type(error).__name__)
    return out


def main():
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    # The raw response and credential are never written, printed or published.
    value = collect()
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': value['status'], 'method': 'GET', 'paidOperations': 0}))


if __name__ == '__main__':
    main()
