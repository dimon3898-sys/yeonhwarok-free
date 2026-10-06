"""Single-writer durable control records, separate from engine project state."""
from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import inspect
import json
from pathlib import Path
import re
import time

from deployment.one_url.budget import BudgetError
from deployment.security import private_json


def fingerprint(budget):
    def encode(value):
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        raise TypeError()
    return hashlib.sha256(json.dumps(asdict(budget), default=encode, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


class ControlState:
    """The hosting backend must enforce one writer across containers too.

    Modal candidate uses max_containers=1 and a named single compute backend.
    This lock serializes concurrent front requests; it is not distributed.
    All callbacks finish before files are reopened. No engine Volume is reloaded.
    """
    def __init__(self, root, *, reload=None, commit=None, clock=time.time):
        self.root = Path(root)
        if self.root.is_symlink():
            raise ValueError('UNSAFE_CONTROL_ROOT')
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.reload, self.commit, self.clock = reload, commit, clock
        self.lock = asyncio.Lock()

    @staticmethod
    async def _call(callback):
        if callback is not None:
            result = callback()
            if inspect.isawaitable(result):
                await result

    def _read(self, name):
        p = self.root / name
        if p.is_symlink():
            raise ValueError('UNSAFE_CONTROL_RECORD')
        if not p.exists():
            return None
        if not p.is_file() or p.stat().st_size > 1024 * 1024:
            raise ValueError('UNSAFE_CONTROL_RECORD')
        value = json.loads(p.read_text())
        if not isinstance(value, dict):
            raise ValueError('INVALID_CONTROL_RECORD')
        return value

    async def reserve(self, budget):
        async with self.lock:
            await self._call(self.reload)
            name = f'reservations-{budget.verified_month}.json'
            stamp = fingerprint(budget)
            raw = self._read(name)
            if raw is None:
                raw = {'month': budget.verified_month, 'budget_fingerprint': stamp,
                       'reserved_sessions': 0, 'reserved_usd': '0'}
            if raw.get('month') != budget.verified_month or raw.get('budget_fingerprint') != stamp:
                raise BudgetError()
            used = raw.get('reserved_sessions')
            amount = budget.require_available_session(used, now=datetime.fromtimestamp(self.clock(), timezone.utc))
            try:
                prior = Decimal(raw['reserved_usd'])
            except Exception:
                raise BudgetError() from None
            if (not prior.is_finite() or prior < 0 or
                    prior != budget.session_reservation_usd * used or
                    prior + amount + budget.portal_storage_safety_reserve_usd > budget.monthly_free_credit_usd):
                raise BudgetError()
            raw['reserved_sessions'], raw['reserved_usd'] = used + 1, str(prior + amount)
            private_json(self.root / name, raw)
            await self._call(self.commit)
            return raw

    def _revocations(self):
        raw = self._read('session-revocations.json')
        if raw is None:
            return {}
        if raw.get('format') != 'world-portal-revocations-v1' or not isinstance(raw.get('sessions'), dict):
            raise ValueError('INVALID_REVOCATION_RECORD')
        for sid, expires in raw['sessions'].items():
            if (not re.fullmatch(r'[a-f0-9]{40}', sid) or type(expires) is not int):
                raise ValueError('INVALID_REVOCATION_RECORD')
        return raw['sessions']

    async def contains(self, sid):
        async with self.lock:
            await self._call(self.reload)
            return self._revocations().get(sid, 0) > self.clock()

    async def revoke(self, sid, expires):
        if (not isinstance(sid, str) or not re.fullmatch(r'[a-f0-9]{40}', sid)
                or type(expires) is not int or not self.clock() < expires <= self.clock() + 43200):
            raise ValueError('INVALID_REVOCATION')
        async with self.lock:
            await self._call(self.reload)
            sessions = {s: exp for s, exp in self._revocations().items() if exp > self.clock()}
            if len(sessions) >= 4096 and sid not in sessions:
                raise ValueError('REVOCATION_CAPACITY_EXCEEDED')
            sessions[sid] = expires
            private_json(self.root / 'session-revocations.json',
                         {'format': 'world-portal-revocations-v1', 'sessions': sessions})
            await self._call(self.commit)
