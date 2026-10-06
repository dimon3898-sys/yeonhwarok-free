import asyncio
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from deployment.one_url.budget import BudgetError, validate_budget_config
from deployment.one_url.control_state import ControlState
from deployment.one_url.test_budget import NOW, fixture


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.budget = validate_budget_config(fixture(), now=NOW)
        self.commits = 0
        async def commit():
            self.commits += 1
        self.state = ControlState(self.root, commit=commit, clock=NOW.timestamp)

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_concurrent_reservations_accumulate_full_cost(self):
        records = await asyncio.gather(*(self.state.reserve(self.budget) for _ in range(3)))
        last = json.loads((self.root / 'reservations-2026-10.json').read_text())
        self.assertEqual(last['reserved_sessions'], 3)
        self.assertEqual(Decimal(last['reserved_usd']), self.budget.session_reservation_usd * 3)
        self.assertEqual(self.commits, 3)
        self.assertEqual((self.root / 'reservations-2026-10.json').stat().st_mode & 0o777, 0o600)

    async def test_same_month_configuration_change_never_resets_prior_reservations(self):
        await self.state.reserve(self.budget)
        original = (self.root / 'reservations-2026-10.json').read_bytes()
        raw = fixture()
        raw['max_session_seconds'] = 7200
        cheaper = validate_budget_config(raw, now=NOW)
        with self.assertRaises(BudgetError):
            await self.state.reserve(cheaper)
        self.assertEqual((self.root / 'reservations-2026-10.json').read_bytes(), original)

    async def test_corrupted_ledger_not_treated_as_zero(self):
        p = self.root / 'reservations-2026-10.json'
        p.write_text('[]')
        with self.assertRaises(ValueError):
            await self.state.reserve(self.budget)
        self.assertEqual(p.read_text(), '[]')

    async def test_exhausted_budget_blocks_new_allocation(self):
        raw = fixture()
        raw['max_monthly_sessions'] = 1
        budget = validate_budget_config(raw, now=NOW)
        await self.state.reserve(budget)
        with self.assertRaisesRegex(BudgetError, 'BUDGET_EXHAUSTED'):
            await self.state.reserve(budget)

    async def test_logout_survives_control_object_restart(self):
        sid = 'a' * 40
        expiry = int(NOW.timestamp()) + 43200
        await self.state.revoke(sid, expiry)
        restarted = ControlState(self.root, clock=NOW.timestamp)
        self.assertTrue(await restarted.contains(sid))
        self.assertFalse(await restarted.contains('b' * 40))
        self.assertEqual(self.commits, 1)

    async def test_failed_persistence_does_not_report_revoke_success(self):
        async def failed():
            raise OSError('controlled failure')
        state = ControlState(self.root, commit=failed, clock=NOW.timestamp)
        with self.assertRaises(OSError):
            await state.revoke('a' * 40, int(NOW.timestamp()) + 100)


if __name__ == '__main__':
    unittest.main()
