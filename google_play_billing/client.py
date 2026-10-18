"""Thin wrapper around the Google Play Developer API (androidpublisher v3)."""

from __future__ import annotations

from typing import Any

from .exceptions import PlayApiError
from .settings import get_google_play_billing_settings

ANDROID_PUBLISHER_SCOPE = "https://www.googleapis.com/auth/androidpublisher"


def _build_credentials() -> Any:
    from google.oauth2 import service_account  # local import; optional at import time

    package_settings = get_google_play_billing_settings()
    if package_settings.service_account_info is not None:
        return service_account.Credentials.from_service_account_info(
            dict(package_settings.service_account_info),
            scopes=[ANDROID_PUBLISHER_SCOPE],
        )
    if package_settings.service_account_file is not None:
        return service_account.Credentials.from_service_account_file(
            package_settings.service_account_file,
            scopes=[ANDROID_PUBLISHER_SCOPE],
        )
    raise PlayApiError(
        "Google Play credentials are not configured; set DJANGO_GOOGLE_PLAY_BILLING"
        "['SERVICE_ACCOUNT_INFO'] or ['SERVICE_ACCOUNT_FILE']."
    )


def build_android_publisher_service() -> Any:
    from googleapiclient.discovery import build  # local import; optional at import time

    return build(
        "androidpublisher",
        "v3",
        credentials=_build_credentials(),
        cache_discovery=False,
    )


class GooglePlayAPI:
    """Minimal androidpublisher client for subscription verification/acknowledge."""

    def __init__(self, service: Any | None = None, package_name: str | None = None) -> None:
        self._service = service
        self._package_name = package_name or get_google_play_billing_settings().package_name

    @property
    def service(self) -> Any:
        if self._service is None:
            self._service = build_android_publisher_service()
        return self._service

    @property
    def package_name(self) -> str:
        return self._package_name

    def get_subscription_v2(self, purchase_token: str) -> dict[str, Any]:
        """Fetch the current SubscriptionPurchaseV2 for a purchase token."""
        try:
            request = (
                self.service.purchases()
                .subscriptionsv2()
                .get(packageName=self._package_name, token=purchase_token)
            )
            result = request.execute()
        except Exception as exc:  # noqa: BLE001 - surface any API failure uniformly
            raise PlayApiError(f"Failed to fetch subscription purchase: {exc}") from exc
        if not isinstance(result, dict):
            raise PlayApiError("Unexpected subscription purchase response payload.")
        return result

    def get_monetization_subscription(self, product_id: str) -> dict[str, Any]:
        """Fetch the monetization Subscription (base plans + regional prices).

        Returns the ``monetization.subscriptions.get`` resource, which exposes
        each base plan's per-region list price. Used for cross-provider price
        comparisons; it does not require a purchase token.
        """
        try:
            request = (
                self.service.monetization()
                .subscriptions()
                .get(packageName=self._package_name, productId=product_id)
            )
            result = request.execute()
        except Exception as exc:  # noqa: BLE001 - surface any API failure uniformly
            raise PlayApiError(
                f"Failed to fetch monetization subscription {product_id}: {exc}"
            ) from exc
        if not isinstance(result, dict):
            raise PlayApiError("Unexpected monetization subscription response payload.")
        return result

    def acknowledge_subscription(self, purchase_token: str, product_id: str) -> None:
        """Acknowledge a subscription purchase (v1 acknowledge endpoint)."""
        try:
            (
                self.service.purchases()
                .subscriptions()
                .acknowledge(
                    packageName=self._package_name,
                    subscriptionId=product_id,
                    token=purchase_token,
                    body={},
                )
                .execute()
            )
        except Exception as exc:  # noqa: BLE001 - surface any API failure uniformly
            raise PlayApiError(f"Failed to acknowledge subscription purchase: {exc}") from exc
