"""Budget admission tests use invented rates, never provider pricing claims."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from deployment.one_url.budget import (BudgetError, SESSION_STARTUP_MARGIN_SECONDS,
                                      load_verified_budget, validate_budget_config)

NOW = datetime(2026, 10, 6, 8, 0, tzinfo=timezone.utc)


def fixture():
    return {
        "verified_month": "2026-10", "verified_at": "2026-10-06T07:00:00Z",
        "monthly_free_credit_usd": "10", "cpu_price_per_core_second": "0.00001",
        "memory_price_per_gib_second": "0.000001",
        "portal_storage_safety_reserve_usd": "1", "max_monthly_sessions": 10,
        "max_session_seconds": 14400, "cpu": 4, "memory_mib": 8192,
        "paid_overage_disabled": True, "card_required": False,
        "terms_and_account_verified": True,
        "evidence_urls": ["https://modal.com/docs/guide/billing"],
        "provider_rates_evidence_urls": ["https://modal.com/pricing"],
    }


class VerifiedBudget(unittest.TestCase):
    def test_full_lifetime_reservation_uses_supplied_rates_and_all_monthly_sessions(self):
        budget = validate_budget_config(fixture(), now=NOW)
        self.assertEqual(budget.session_reservation_usd, Decimal("0.6912"))
        self.assertEqual(budget.monthly_reservation_usd, Decimal("7.912"))
        self.assertEqual(budget.require_available_session(9, now=NOW), Decimal("0.6912"))
        with self.assertRaises(FrozenInstanceError):
            budget.cpu = 1

    def test_no_unverified_field_or_free_credit_default(self):
        for field in fixture():
            raw = fixture()
            del raw[field]
            with self.subTest(field=field), self.assertRaisesRegex(BudgetError, "BUDGET_UNVERIFIED"):
                validate_budget_config(raw, now=NOW)
        for field, value in (("paid_overage_disabled", False), ("card_required", True),
                             ("terms_and_account_verified", False), ("paid_overage_disabled", 1)):
            raw = fixture()
            raw[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(BudgetError):
                validate_budget_config(raw, now=NOW)

    def test_credit_must_cover_all_reserved_sessions_and_portal_storage(self):
        raw = fixture()
        raw["monthly_free_credit_usd"] = "7.91199999"
        with self.assertRaises(BudgetError):
            validate_budget_config(raw, now=NOW)
        raw["monthly_free_credit_usd"] = "7.912"
        validate_budget_config(raw, now=NOW)

    def test_unsafe_numbers_and_resources_fail_closed(self):
        for field, value in (("cpu_price_per_core_second", "NaN"),
                             ("memory_price_per_gib_second", "Infinity"),
                             ("monthly_free_credit_usd", -1),
                             ("portal_storage_safety_reserve_usd", 0),
                             ("cpu_price_per_core_second", True),
                             ("cpu_price_per_core_second", "1e999999999"),
                             ("max_monthly_sessions", True), ("max_session_seconds", 14401),
                             ("cpu", 5), ("memory_mib", 8193)):
            raw = fixture()
            raw[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(BudgetError):
                validate_budget_config(raw, now=NOW)

    def test_stale_month_future_verification_and_unverifiable_urls_rejected(self):
        for field, value in (("verified_month", "2026-09"),
                             ("verified_at", "2026-10-06T09:00:00Z"),
                             ("verified_at", "2026-10-06T07:00:00"),
                             ("evidence_urls", []),
                             ("evidence_urls", ["http://modal.com/pricing"]),
                             ("evidence_urls", ["https://token@modal.com/pricing"]),
                             ("provider_rates_evidence_urls", ["https://modal.com:444/pricing"])):
            raw = fixture()
            raw[field] = value
            with self.subTest(field=field), self.assertRaises(BudgetError):
                validate_budget_config(raw, now=NOW)

    def test_ledger_missing_exhausted_or_old_month_cannot_admit(self):
        budget = validate_budget_config(fixture(), now=NOW)
        for count in (None, False, -1, "0"):
            with self.subTest(count=count), self.assertRaises(BudgetError):
                budget.require_available_session(count, now=NOW)
        with self.assertRaisesRegex(BudgetError, "BUDGET_EXHAUSTED"):
            budget.require_available_session(10, now=NOW)
        with self.assertRaisesRegex(BudgetError, "BUDGET_UNVERIFIED"):
            budget.require_available_session(0, now=datetime(2026, 11, 1, tzinfo=timezone.utc))

    def test_full_lifetime_and_startup_margin_stay_inside_verified_month(self):
        budget = validate_budget_config(fixture(), now=NOW)
        boundary = datetime(2026, 11, 1, tzinfo=timezone.utc)
        last_allowed = boundary - timedelta(
            seconds=budget.max_session_seconds + SESSION_STARTUP_MARGIN_SECONDS + 1)
        self.assertEqual(budget.require_available_session(0, now=last_allowed),
                         budget.session_reservation_usd)
        # The renderer lifetime alone fits, but startup headroom reaches midnight.
        with self.assertRaisesRegex(BudgetError, "BUDGET_MONTH_BOUNDARY"):
            budget.require_available_session(0, now=last_allowed + timedelta(seconds=1))
        with self.assertRaisesRegex(BudgetError, "BUDGET_MONTH_BOUNDARY"):
            budget.require_available_session(0, now=boundary - timedelta(minutes=1))

    def test_utc_month_guard_handles_year_rollover_and_other_timezones(self):
        raw = fixture()
        raw.update(verified_month="2026-12", verified_at="2026-12-01T00:00:00Z",
                   max_session_seconds=300)
        boundary = datetime(2027, 1, 1, tzinfo=timezone.utc)
        current = datetime(2026, 12, 31, tzinfo=timezone.utc)
        budget = validate_budget_config(raw, now=current)
        last_allowed = boundary - timedelta(
            seconds=budget.max_session_seconds + SESSION_STARTUP_MARGIN_SECONDS + 1)
        # Local calendar time is already January, but billing admission uses UTC.
        local = last_allowed.astimezone(timezone(timedelta(hours=5)))
        self.assertEqual(local.month, 1)
        self.assertEqual(budget.require_available_session(0, now=local),
                         budget.session_reservation_usd)
        with self.assertRaisesRegex(BudgetError, "BUDGET_MONTH_BOUNDARY"):
            budget.require_available_session(0, now=local + timedelta(seconds=1))
        with self.assertRaisesRegex(BudgetError, "BUDGET_UNVERIFIED"):
            budget.require_available_session(0, now=boundary)

    def test_file_missing_malformed_duplicates_symlink_and_large_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            good = root / "verified.json"
            good.write_text(json.dumps(fixture()))
            self.assertEqual(load_verified_budget(good, now=NOW).cpu, 4)
            candidates = [root / "missing.json", root / "bad.json", root / "duplicate.json",
                          root / "linked.json", root / "large.json"]
            candidates[1].write_text("{")
            candidates[2].write_text('{"cpu":4,"cpu":4}')
            candidates[3].symlink_to(good)
            candidates[4].write_bytes(b" " * 65537)
            for path in candidates:
                with self.subTest(path=path.name), self.assertRaisesRegex(BudgetError, "BUDGET_UNVERIFIED"):
                    load_verified_budget(path, now=NOW)


if __name__ == "__main__":
    unittest.main()
