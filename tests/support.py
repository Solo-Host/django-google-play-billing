"""Shared helpers for the django-google-play-billing test suite."""

from __future__ import annotations

import base64
import json
from typing import Any


def subscription_v2(
    *,
    state: str = "SUBSCRIPTION_STATE_ACTIVE",
    product_id: str = "personal_monthly",
    base_plan_id: str = "monthly",
    offer_id: str = "freetrial",
    acknowledgement_state: str = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED",
    expiry_time: str = "2030-01-01T00:00:00Z",
    start_time: str = "2024-01-01T00:00:00Z",
    auto_renewing: bool = True,
    test_purchase: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "subscriptionState": state,
        "latestOrderId": "GPA.1111-2222-3333-44444",
        "startTime": start_time,
        "acknowledgementState": acknowledgement_state,
        "lineItems": [
            {
                "productId": product_id,
                "expiryTime": expiry_time,
                "autoRenewingPlan": {"autoRenewEnabled": auto_renewing},
                "offerDetails": {"basePlanId": base_plan_id, "offerId": offer_id},
            }
        ],
    }
    if test_purchase:
        payload["testPurchase"] = {}
    return payload


def subscription_notification(
    notification_type: int,
    *,
    purchase_token: str = "token-1",
    subscription_id: str = "personal_monthly",
    package_name: str = "com.example.app",
) -> dict[str, Any]:
    return {
        "version": "1.0",
        "packageName": package_name,
        "eventTimeMillis": "1700000000000",
        "subscriptionNotification": {
            "version": "1.0",
            "notificationType": notification_type,
            "purchaseToken": purchase_token,
            "subscriptionId": subscription_id,
        },
    }


def voided_notification(
    *,
    purchase_token: str = "token-1",
    package_name: str = "com.example.app",
) -> dict[str, Any]:
    return {
        "version": "1.0",
        "packageName": package_name,
        "eventTimeMillis": "1700000000000",
        "voidedPurchaseNotification": {
            "purchaseToken": purchase_token,
            "orderId": "GPA.1111",
            "productType": 1,
            "refundType": 1,
        },
    }


def make_test_notification(*, package_name: str = "com.example.app") -> dict[str, Any]:
    return {
        "version": "1.0",
        "packageName": package_name,
        "eventTimeMillis": "1700000000000",
        "testNotification": {"version": "1.0"},
    }


def monetization_subscription(
    *,
    product_id: str = "personal_monthly",
    base_plan_id: str = "monthly",
    currency_code: str = "USD",
    units: str = "4",
    nanos: int = 990000000,
) -> dict[str, Any]:
    """Build a ``monetization.subscriptions.get`` style payload for tests."""
    return {
        "productId": product_id,
        "basePlans": [
            {
                "basePlanId": base_plan_id,
                "regionalConfigs": [
                    {
                        "regionCode": "US",
                        "price": {
                            "currencyCode": currency_code,
                            "units": units,
                            "nanos": nanos,
                        },
                    }
                ],
            }
        ],
    }


def make_envelope(
    developer_notification: dict[str, Any],
    *,
    message_id: str = "m-1",
    publish_time: str = "2024-01-01T00:00:00Z",
) -> dict[str, Any]:
    encoded = base64.b64encode(json.dumps(developer_notification).encode("utf-8")).decode("ascii")
    return {
        "message": {
            "data": encoded,
            "messageId": message_id,
            "publishTime": publish_time,
        },
        "subscription": "projects/example/subscriptions/rtdn",
    }


class FakeGooglePlayAPI:
    """Stand-in for ``GooglePlayAPI`` that returns a fixed v2 payload."""

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        *,
        package_name: str = "com.example.app",
        monetization_payload: dict[str, Any] | None = None,
    ) -> None:
        self._payload = payload if payload is not None else subscription_v2()
        self._monetization_payload = monetization_payload
        self.package_name = package_name
        self.acknowledged: list[tuple[str, str]] = []

    def get_subscription_v2(self, purchase_token: str) -> dict[str, Any]:
        return self._payload

    def get_monetization_subscription(self, product_id: str) -> dict[str, Any]:
        if self._monetization_payload is None:
            return monetization_subscription(product_id=product_id)
        return self._monetization_payload

    def acknowledge_subscription(self, purchase_token: str, product_id: str) -> None:
        self.acknowledged.append((purchase_token, product_id))
