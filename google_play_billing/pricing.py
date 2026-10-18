"""Helpers for reading Google Play subscription base-plan list prices.

These helpers operate on the ``monetization.subscriptions.get`` response of the
Google Play Developer API (androidpublisher v3). They are intentionally free of
Django and Google client dependencies so they can be unit-tested in isolation
and reused by host applications that compare Play prices against another source.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import Any

NANOS_PER_UNIT = Decimal(1_000_000_000)


def money_to_decimal(money: Mapping[str, Any]) -> Decimal:
    """Convert a Google Play ``Money`` object to a major-unit :class:`Decimal`.

    ``Money`` stores whole ``units`` (an int64 serialised as a string) plus
    ``nanos`` (billionths of a unit). For example ``{"units": "1", "nanos":
    990000000}`` represents ``1.99``.
    """
    units = Decimal(str(money.get("units", "0") or "0"))
    nanos = Decimal(int(money.get("nanos", 0) or 0))
    return units + nanos / NANOS_PER_UNIT


def _base_plans(subscription: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    base_plans = subscription.get("basePlans")
    if not isinstance(base_plans, (list, tuple)):
        return []
    return [plan for plan in base_plans if isinstance(plan, Mapping)]


def find_base_plan_price(
    subscription: Mapping[str, Any],
    base_plan_id: str,
    currency_code: str,
) -> Decimal | None:
    """Return the regional list price for ``base_plan_id`` in ``currency_code``.

    The returned value is the tax-exclusive list price in major currency units
    (a :class:`Decimal`), or ``None`` when the base plan or currency is not
    offered in the subscription's regional configuration.
    """
    currency = currency_code.upper()
    for base_plan in _base_plans(subscription):
        if str(base_plan.get("basePlanId") or "") != base_plan_id:
            continue
        regional_configs = base_plan.get("regionalConfigs")
        if not isinstance(regional_configs, (list, tuple)):
            continue
        for config in regional_configs:
            if not isinstance(config, Mapping):
                continue
            price = config.get("price")
            if not isinstance(price, Mapping):
                continue
            if str(price.get("currencyCode") or "").upper() == currency:
                return money_to_decimal(price)
    return None
