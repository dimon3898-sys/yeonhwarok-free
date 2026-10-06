"""Operator-verified, conservative admission limits; no provider API claims.

This file deliberately contains no prices or free-credit defaults. A verified
configuration is evidence supplied by the operator, not verification performed
by this module. Reservations cover the full permitted backend lifetime, including
idle time. Admission also leaves five minutes for bounded provider startup so
the full session stays in its verified UTC billing month. The caller must
serialize and persist its monthly session ledger and recheck before creation.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit


# Covers bounded allocation, tunnel configuration and readiness overhead.
# This is extra time headroom, not a deduction from the reserved compute life.
SESSION_STARTUP_MARGIN_SECONDS = 300


class BudgetError(ValueError):
    def __init__(self, code="BUDGET_UNVERIFIED"):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Budget:
    verified_month: str
    verified_at: datetime
    monthly_free_credit_usd: Decimal
    cpu_price_per_core_second: Decimal
    memory_price_per_gib_second: Decimal
    portal_storage_safety_reserve_usd: Decimal
    max_monthly_sessions: int
    max_session_seconds: int
    cpu: int
    memory_mib: int
    paid_overage_disabled: bool
    card_required: bool
    terms_and_account_verified: bool
    evidence_urls: tuple[str, ...]
    provider_rates_evidence_urls: tuple[str, ...]

    @property
    def session_reservation_usd(self):
        rate = (Decimal(self.cpu) * self.cpu_price_per_core_second +
                Decimal(self.memory_mib) / Decimal(1024) * self.memory_price_per_gib_second)
        return rate * Decimal(self.max_session_seconds)

    @property
    def monthly_reservation_usd(self):
        return (self.session_reservation_usd * self.max_monthly_sessions +
                self.portal_storage_safety_reserve_usd)

    def require_available_session(self, sessions_reserved, *, now=None):
        """Read an authoritative monthly ledger; never infer a missing count as zero."""
        current = _now(now)
        if current.strftime("%Y-%m") != self.verified_month:
            raise BudgetError()
        try:
            latest_completion = current + timedelta(
                seconds=self.max_session_seconds + SESSION_STARTUP_MARGIN_SECONDS)
        except OverflowError:
            raise BudgetError() from None
        if latest_completion.strftime("%Y-%m") != self.verified_month:
            raise BudgetError("BUDGET_MONTH_BOUNDARY")
        if type(sessions_reserved) is not int or sessions_reserved < 0:
            raise BudgetError()
        if sessions_reserved >= self.max_monthly_sessions:
            raise BudgetError("BUDGET_EXHAUSTED")
        return self.session_reservation_usd


def _now(value):
    value = datetime.now(timezone.utc) if value is None else value
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise BudgetError()
    return value.astimezone(timezone.utc)


def _money(value, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise BudgetError()
    if isinstance(value, str) and (not value or len(value) > 64 or value != value.strip()):
        raise BudgetError()
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise BudgetError() from None
    if not amount.is_finite() or amount < 0 or (positive and amount <= 0):
        raise BudgetError()
    # Reject pathological exponents before arithmetic can consume large memory.
    if amount != 0 and not Decimal("1e-18") <= amount <= Decimal("1e9"):
        raise BudgetError()
    return amount


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise BudgetError()
    return value


def _urls(value):
    if not isinstance(value, list) or not 1 <= len(value) <= 12:
        raise BudgetError()
    result = []
    for url in value:
        if (not isinstance(url, str) or not 1 <= len(url) <= 2048 or
                re.search(r"[\s\\]", url)):
            raise BudgetError()
        try:
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            raise BudgetError() from None
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or
                parsed.password is not None or port not in (None, 443) or parsed.fragment):
            raise BudgetError()
        result.append(url)
    return tuple(result)


def validate_budget_config(raw, *, now=None):
    """Fail closed unless all required account, price, month and reserve evidence exists."""
    current = _now(now)
    if not isinstance(raw, dict):
        raise BudgetError()
    required = set(Budget.__dataclass_fields__)
    if set(raw) != required:
        raise BudgetError()
    if (raw["paid_overage_disabled"] is not True or raw["card_required"] is not False or
            raw["terms_and_account_verified"] is not True):
        raise BudgetError()
    month = raw["verified_month"]
    if (not isinstance(month, str) or not re.fullmatch(r"\d{4}-\d{2}", month) or
            month != current.strftime("%Y-%m")):
        raise BudgetError()
    stamp = raw["verified_at"]
    if not isinstance(stamp, str) or len(stamp) > 40:
        raise BudgetError()
    try:
        verified = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        raise BudgetError() from None
    if (verified.tzinfo is None or verified.utcoffset() is None or
            verified.utcoffset().total_seconds() != 0 or verified > current or
            verified.strftime("%Y-%m") != month):
        raise BudgetError()
    cpu = _integer(raw["cpu"], 4, 4)
    memory = _integer(raw["memory_mib"], 8192, 8192)
    budget = Budget(
        verified_month=month, verified_at=verified,
        monthly_free_credit_usd=_money(raw["monthly_free_credit_usd"], positive=True),
        cpu_price_per_core_second=_money(raw["cpu_price_per_core_second"], positive=True),
        memory_price_per_gib_second=_money(raw["memory_price_per_gib_second"], positive=True),
        portal_storage_safety_reserve_usd=_money(raw["portal_storage_safety_reserve_usd"], positive=True),
        max_monthly_sessions=_integer(raw["max_monthly_sessions"], 1, 10000),
        max_session_seconds=_integer(raw["max_session_seconds"], 1, 14400),
        cpu=cpu, memory_mib=memory,
        paid_overage_disabled=True, card_required=False, terms_and_account_verified=True,
        evidence_urls=_urls(raw["evidence_urls"]),
        provider_rates_evidence_urls=_urls(raw["provider_rates_evidence_urls"]),
    )
    if budget.monthly_reservation_usd > budget.monthly_free_credit_usd:
        raise BudgetError()
    return budget


def _unique_json(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BudgetError()
        result[key] = value
    return result


def load_verified_budget(path, *, now=None):
    """Read a small ordinary config file, preserving every failure as unverified."""
    if path is None:
        raise BudgetError()
    file_path = Path(path)
    descriptor = None
    try:
        if file_path.is_symlink():
            raise BudgetError()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        descriptor = os.open(file_path, flags)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
            raise BudgetError()
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            data = stream.read(65537)
        if len(data) > 65536:
            raise BudgetError()
        raw = json.loads(data, object_pairs_hook=_unique_json, parse_float=Decimal)
        return validate_budget_config(raw, now=now)
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError, ArithmeticError):
        raise BudgetError() from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
