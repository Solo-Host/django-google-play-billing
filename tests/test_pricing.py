"""Tests for the Google Play price helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from google_play_billing.pricing import find_base_plan_price, money_to_decimal
from tests.support import monetization_subscription


@pytest.mark.parametrize(
    ("money", "expected"),
    [
        ({"units": "1", "nanos": 990000000}, Decimal("1.99")),
        ({"units": "4", "nanos": 0}, Decimal("4")),
        ({"units": "0", "nanos": 500000000}, Decimal("0.5")),
        ({}, Decimal("0")),
    ],
)
def test_money_to_decimal(money: dict[str, object], expected: Decimal) -> None:
    assert money_to_decimal(money) == expected


def test_find_base_plan_price_matches_currency() -> None:
    subscription = monetization_subscription(
        base_plan_id="monthly", currency_code="USD", units="4", nanos=990000000
    )
    assert find_base_plan_price(subscription, "monthly", "usd") == Decimal("4.99")


def test_find_base_plan_price_missing_currency_returns_none() -> None:
    subscription = monetization_subscription(currency_code="USD")
    assert find_base_plan_price(subscription, "monthly", "CAD") is None


def test_find_base_plan_price_missing_base_plan_returns_none() -> None:
    subscription = monetization_subscription(base_plan_id="monthly")
    assert find_base_plan_price(subscription, "annual", "USD") is None


def test_find_base_plan_price_tolerates_malformed_payload() -> None:
    assert find_base_plan_price({"basePlans": "nope"}, "monthly", "USD") is None
    assert find_base_plan_price({}, "monthly", "USD") is None
