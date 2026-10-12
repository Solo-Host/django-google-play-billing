from __future__ import annotations

import pytest

from google_play_billing import constants, signals
from google_play_billing.ingest import (
    extract_v2_fields,
    ingest_pubsub_envelope,
    sync_subscription_purchase,
)
from google_play_billing.models import PlaySubscriptionPurchase, RealtimeNotification
from tests.support import (
    FakeGooglePlayAPI,
    make_envelope,
    make_test_notification,
    subscription_notification,
    subscription_v2,
    voided_notification,
)

pytestmark = pytest.mark.django_db


def test_extract_v2_fields_maps_line_item():
    fields = extract_v2_fields(subscription_v2())
    assert fields["product_id"] == "personal_monthly"
    assert fields["base_plan_id"] == "monthly"
    assert fields["offer_id"] == "freetrial"
    assert fields["auto_renewing"] is True
    assert fields["subscription_state"] == constants.STATE_ACTIVE
    assert fields["expiry_time"] is not None


def test_sync_creates_purchase_and_emits_signal():
    received: list[dict] = []

    def handler(sender, **kwargs):
        received.append(kwargs)

    signals.subscription_synced.connect(handler, weak=False)
    try:
        api = FakeGooglePlayAPI(subscription_v2())
        purchase = sync_subscription_purchase("token-1", api=api)
    finally:
        signals.subscription_synced.disconnect(handler)

    assert purchase.product_id == "personal_monthly"
    assert purchase.subscription_state == constants.STATE_ACTIVE
    assert PlaySubscriptionPurchase.objects.count() == 1
    assert len(received) == 1
    assert received[0]["created"] is True


def test_sync_acknowledges_pending_purchase():
    api = FakeGooglePlayAPI(
        subscription_v2(acknowledgement_state=constants.ACK_STATE_PENDING)
    )
    purchase = sync_subscription_purchase("token-ack", api=api)
    assert api.acknowledged == [("token-ack", "personal_monthly")]
    assert purchase.acknowledgement_state == constants.ACK_STATE_ACKNOWLEDGED


def test_sync_updates_existing_purchase():
    api_active = FakeGooglePlayAPI(subscription_v2(state=constants.STATE_ACTIVE))
    sync_subscription_purchase("token-1", api=api_active)
    api_grace = FakeGooglePlayAPI(subscription_v2(state=constants.STATE_IN_GRACE_PERIOD))
    purchase = sync_subscription_purchase("token-1", api=api_grace)
    assert PlaySubscriptionPurchase.objects.count() == 1
    assert purchase.subscription_state == constants.STATE_IN_GRACE_PERIOD


def test_ingest_subscription_envelope(monkeypatch):
    api = FakeGooglePlayAPI(subscription_v2())
    monkeypatch.setattr("google_play_billing.ingest.GooglePlayAPI", lambda *a, **k: api)

    envelope = make_envelope(
        subscription_notification(constants.SUBSCRIPTION_PURCHASED), message_id="msg-1"
    )
    notification = ingest_pubsub_envelope(envelope)

    assert notification.category == constants.NotificationCategory.SUBSCRIPTION
    assert notification.notification_type == constants.SUBSCRIPTION_PURCHASED
    assert notification.processing_state == constants.ProcessingState.PROCESSED
    assert PlaySubscriptionPurchase.objects.filter(purchase_token="token-1").exists()


def test_ingest_is_idempotent(monkeypatch):
    api = FakeGooglePlayAPI(subscription_v2())
    monkeypatch.setattr("google_play_billing.ingest.GooglePlayAPI", lambda *a, **k: api)

    envelope = make_envelope(
        subscription_notification(constants.SUBSCRIPTION_RENEWED), message_id="dup"
    )
    ingest_pubsub_envelope(envelope)
    ingest_pubsub_envelope(envelope)

    assert RealtimeNotification.objects.filter(message_id="dup").count() == 1
    notification = RealtimeNotification.objects.get(message_id="dup")
    assert notification.processing_attempts == 1


def test_ingest_voided_marks_revoked_and_emits():
    api = FakeGooglePlayAPI(subscription_v2())
    sync_subscription_purchase("token-1", api=api)

    received: list[dict] = []

    def handler(sender, **kwargs):
        received.append(kwargs)

    signals.voided_purchase_received.connect(handler, weak=False)
    try:
        envelope = make_envelope(voided_notification(purchase_token="token-1"), message_id="void-1")
        notification = ingest_pubsub_envelope(envelope)
    finally:
        signals.voided_purchase_received.disconnect(handler)

    assert notification.category == constants.NotificationCategory.VOIDED_PURCHASE
    assert notification.processing_state == constants.ProcessingState.PROCESSED
    assert PlaySubscriptionPurchase.objects.get(purchase_token="token-1").revoked is True
    assert received and received[0]["purchase_token"] == "token-1"


def test_ingest_test_notification_is_ignored():
    envelope = make_envelope(make_test_notification(), message_id="test-1")
    notification = ingest_pubsub_envelope(envelope)
    assert notification.category == constants.NotificationCategory.TEST
    assert notification.processing_state == constants.ProcessingState.IGNORED
