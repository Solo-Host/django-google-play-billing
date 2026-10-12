"""Ingest Google Play RTDN envelopes and mirror subscription purchases."""

from __future__ import annotations

import base64
import binascii
import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from django.utils.dateparse import parse_datetime

from . import constants, signals
from .client import GooglePlayAPI
from .exceptions import GooglePlayBillingError
from .models import PlaySubscriptionPurchase, RealtimeNotification
from .settings import get_google_play_billing_settings

logger = logging.getLogger("google_play_billing")

_FRACTIONAL_SECONDS = re.compile(r"(\.\d{6})\d+")


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    # Google timestamps may include nanosecond precision; trim to microseconds.
    normalized = _FRACTIONAL_SECONDS.sub(r"\1", value.strip())
    parsed = parse_datetime(normalized)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _parse_epoch_millis(value: object) -> datetime | None:
    if not isinstance(value, (str, int)) or value == "":
        return None
    try:
        millis = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(millis / 1000, tz=UTC)


def decode_developer_notification(message: Mapping[str, Any]) -> dict[str, Any]:
    """Decode the base64 ``data`` field of a Pub/Sub message into a dict."""
    data = message.get("data")
    if not isinstance(data, str) or not data:
        raise GooglePlayBillingError("Pub/Sub message is missing base64 'data'.")
    try:
        decoded = base64.b64decode(data)
    except (binascii.Error, ValueError) as exc:
        raise GooglePlayBillingError(f"Pub/Sub 'data' is not valid base64: {exc}") from exc
    try:
        payload = json.loads(decoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GooglePlayBillingError(f"Developer notification is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise GooglePlayBillingError("Developer notification must be a JSON object.")
    return payload


def _categorize(notification: Mapping[str, Any]) -> str:
    if "subscriptionNotification" in notification:
        return constants.NotificationCategory.SUBSCRIPTION
    if "voidedPurchaseNotification" in notification:
        return constants.NotificationCategory.VOIDED_PURCHASE
    if "oneTimeProductNotification" in notification:
        return constants.NotificationCategory.ONE_TIME_PRODUCT
    if "testNotification" in notification:
        return constants.NotificationCategory.TEST
    return constants.NotificationCategory.UNKNOWN


def extract_v2_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten a SubscriptionPurchaseV2 payload into model-ready fields."""
    line_items = payload.get("lineItems")
    product_id = ""
    base_plan_id = ""
    offer_id = ""
    expiry_time: datetime | None = None
    auto_renewing = False
    if isinstance(line_items, list) and line_items:
        first = line_items[0] if isinstance(line_items[0], Mapping) else {}
        product_id = str(first.get("productId") or "")
        offer_details = first.get("offerDetails")
        if isinstance(offer_details, Mapping):
            base_plan_id = str(offer_details.get("basePlanId") or "")
            offer_id = str(offer_details.get("offerId") or "")
        auto_renewing_plan = first.get("autoRenewingPlan")
        if isinstance(auto_renewing_plan, Mapping):
            auto_renewing = bool(auto_renewing_plan.get("autoRenewEnabled"))
        for item in line_items:
            if not isinstance(item, Mapping):
                continue
            candidate = _parse_timestamp(item.get("expiryTime"))
            if candidate is not None and (expiry_time is None or candidate > expiry_time):
                expiry_time = candidate

    return {
        "product_id": product_id,
        "base_plan_id": base_plan_id,
        "offer_id": offer_id,
        "subscription_state": str(payload.get("subscriptionState") or ""),
        "latest_order_id": str(payload.get("latestOrderId") or ""),
        "start_time": _parse_timestamp(payload.get("startTime")),
        "expiry_time": expiry_time,
        "auto_renewing": auto_renewing,
        "acknowledgement_state": str(payload.get("acknowledgementState") or ""),
        "linked_purchase_token": str(payload.get("linkedPurchaseToken") or ""),
        "test_purchase": "testPurchase" in payload,
    }


def sync_subscription_purchase(
    purchase_token: str,
    *,
    api: GooglePlayAPI | None = None,
    notification: RealtimeNotification | None = None,
    emit_signal: bool = True,
) -> PlaySubscriptionPurchase:
    """Fetch the current purchase state from Google Play and mirror it locally."""
    package_settings = get_google_play_billing_settings()
    client = api or GooglePlayAPI()
    payload = client.get_subscription_v2(purchase_token)
    fields = extract_v2_fields(payload)

    should_acknowledge = (
        package_settings.auto_acknowledge
        and fields["acknowledgement_state"] == constants.ACK_STATE_PENDING
        and bool(fields["product_id"])
    )
    if should_acknowledge:
        client.acknowledge_subscription(purchase_token, fields["product_id"])
        fields["acknowledgement_state"] = constants.ACK_STATE_ACKNOWLEDGED
        logger.info(
            "Acknowledged Google Play subscription purchase for product %s", fields["product_id"]
        )

    defaults: dict[str, Any] = {
        "package_name": client.package_name,
        **fields,
    }
    if package_settings.store_raw_payloads:
        defaults["raw"] = payload

    purchase, created = PlaySubscriptionPurchase.objects.update_or_create(
        purchase_token=purchase_token,
        defaults=defaults,
    )
    logger.info(
        "Synced Google Play subscription purchase token=%s state=%s created=%s",
        purchase_token[:12],
        fields["subscription_state"],
        created,
    )
    if emit_signal:
        signals.subscription_synced.send_robust(
            sender=PlaySubscriptionPurchase,
            purchase=purchase,
            notification=notification,
            created=created,
        )
    return purchase


def _handle_voided_purchase(
    developer_notification: Mapping[str, Any],
    notification: RealtimeNotification,
) -> None:
    voided = developer_notification.get("voidedPurchaseNotification")
    purchase_token = ""
    if isinstance(voided, Mapping):
        purchase_token = str(voided.get("purchaseToken") or "")
    if purchase_token:
        PlaySubscriptionPurchase.objects.filter(purchase_token=purchase_token).update(
            revoked=True
        )
    signals.voided_purchase_received.send_robust(
        sender=PlaySubscriptionPurchase,
        purchase_token=purchase_token,
        notification=notification,
    )


def _process_notification(
    notification: RealtimeNotification,
    developer_notification: Mapping[str, Any],
    *,
    api: GooglePlayAPI | None,
) -> None:
    if notification.category == constants.NotificationCategory.SUBSCRIPTION:
        if notification.purchase_token:
            sync_subscription_purchase(
                notification.purchase_token, api=api, notification=notification
            )
        notification.processing_state = constants.ProcessingState.PROCESSED
    elif notification.category == constants.NotificationCategory.VOIDED_PURCHASE:
        _handle_voided_purchase(developer_notification, notification)
        notification.processing_state = constants.ProcessingState.PROCESSED
    else:
        notification.processing_state = constants.ProcessingState.IGNORED


def reprocess_notification(
    notification: RealtimeNotification,
    *,
    api: GooglePlayAPI | None = None,
) -> RealtimeNotification:
    """Re-run processing for a stored notification using its saved raw payload."""
    developer_notification = notification.raw if isinstance(notification.raw, dict) else {}
    notification.processing_attempts = notification.processing_attempts + 1
    try:
        _process_notification(notification, developer_notification, api=api)
        notification.last_error = ""
    except Exception as exc:
        notification.processing_state = constants.ProcessingState.FAILED
        notification.last_error = str(exc)
        notification.save(
            update_fields=[
                "processing_state",
                "processing_attempts",
                "last_error",
                "updated_at",
            ]
        )
        logger.exception("Failed to reprocess RTDN message_id=%s", notification.message_id)
        signals.rtdn_processing_error.send_robust(
            sender=RealtimeNotification, notification=notification, error=exc
        )
        raise
    notification.save(
        update_fields=["processing_state", "processing_attempts", "last_error", "updated_at"]
    )
    return notification


def ingest_pubsub_envelope(
    envelope: Mapping[str, Any],
    *,
    api: GooglePlayAPI | None = None,
) -> RealtimeNotification:
    """Record and process a Pub/Sub push envelope carrying an RTDN."""
    message = envelope.get("message")
    if not isinstance(message, Mapping):
        raise GooglePlayBillingError("Pub/Sub envelope is missing 'message'.")

    message_id = str(message.get("messageId") or message.get("message_id") or "").strip()
    if not message_id:
        raise GooglePlayBillingError("Pub/Sub message is missing 'messageId'.")

    developer_notification = decode_developer_notification(message)
    category = _categorize(developer_notification)

    subscription = developer_notification.get("subscriptionNotification")
    voided = developer_notification.get("voidedPurchaseNotification")
    purchase_token = ""
    product_id = ""
    notification_type: int | None = None
    if isinstance(subscription, Mapping):
        purchase_token = str(subscription.get("purchaseToken") or "")
        product_id = str(subscription.get("subscriptionId") or "")
        raw_type = subscription.get("notificationType")
        notification_type = int(raw_type) if isinstance(raw_type, int) else None
    elif isinstance(voided, Mapping):
        purchase_token = str(voided.get("purchaseToken") or "")

    package_settings = get_google_play_billing_settings()
    notification, created = RealtimeNotification.objects.get_or_create(
        message_id=message_id,
        defaults={
            "publish_time": _parse_timestamp(message.get("publishTime")),
            "event_time": _parse_epoch_millis(developer_notification.get("eventTimeMillis")),
            "package_name": str(developer_notification.get("packageName") or ""),
            "category": category,
            "notification_type": notification_type,
            "purchase_token": purchase_token,
            "product_id": product_id,
            "raw": developer_notification if package_settings.store_raw_payloads else {},
        },
    )

    if not created and notification.processing_state == constants.ProcessingState.PROCESSED:
        logger.info("Skipping already-processed RTDN message_id=%s", message_id)
        return notification

    signals.rtdn_received.send_robust(sender=RealtimeNotification, notification=notification)

    notification.processing_attempts = notification.processing_attempts + 1
    try:
        _process_notification(notification, developer_notification, api=api)
        notification.last_error = ""
        notification.save(
            update_fields=[
                "processing_state",
                "processing_attempts",
                "last_error",
                "updated_at",
            ]
        )
    except Exception as exc:
        notification.processing_state = constants.ProcessingState.FAILED
        notification.last_error = str(exc)
        notification.save(
            update_fields=[
                "processing_state",
                "processing_attempts",
                "last_error",
                "updated_at",
            ]
        )
        logger.exception("Failed to process RTDN message_id=%s", message_id)
        signals.rtdn_processing_error.send_robust(
            sender=RealtimeNotification, notification=notification, error=exc
        )
        raise

    return notification
