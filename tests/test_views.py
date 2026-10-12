from __future__ import annotations

import pytest

from google_play_billing import constants
from google_play_billing.models import PlaySubscriptionPurchase, RealtimeNotification
from tests.support import (
    FakeGooglePlayAPI,
    make_envelope,
    make_test_notification,
    subscription_notification,
    subscription_v2,
)

pytestmark = pytest.mark.django_db

RTDN_URL = "/webhooks/google-play/?token=rtdn-secret"


def test_get_not_allowed(client):
    response = client.get(RTDN_URL)
    assert response.status_code == 405


def test_missing_token_is_rejected(client):
    envelope = make_envelope(make_test_notification(), message_id="t-1")
    response = client.post(
        "/webhooks/google-play/", data=envelope, content_type="application/json"
    )
    assert response.status_code == 403


def test_wrong_token_is_rejected(client):
    envelope = make_envelope(make_test_notification(), message_id="t-2")
    response = client.post(
        "/webhooks/google-play/?token=nope", data=envelope, content_type="application/json"
    )
    assert response.status_code == 403


def test_test_notification_returns_200(client):
    envelope = make_envelope(make_test_notification(), message_id="t-3")
    response = client.post(RTDN_URL, data=envelope, content_type="application/json")
    assert response.status_code == 200
    body = response.json()
    assert body["processing_state"] == constants.ProcessingState.IGNORED
    assert RealtimeNotification.objects.filter(message_id="t-3").exists()


def test_subscription_notification_processed(client, monkeypatch):
    api = FakeGooglePlayAPI(subscription_v2())
    monkeypatch.setattr("google_play_billing.ingest.GooglePlayAPI", lambda *a, **k: api)

    envelope = make_envelope(
        subscription_notification(constants.SUBSCRIPTION_PURCHASED), message_id="s-1"
    )
    response = client.post(RTDN_URL, data=envelope, content_type="application/json")

    assert response.status_code == 200
    assert response.json()["processing_state"] == constants.ProcessingState.PROCESSED
    assert PlaySubscriptionPurchase.objects.filter(purchase_token="token-1").exists()


def test_malformed_payload_returns_400(client):
    response = client.post(
        RTDN_URL, data="not-json", content_type="application/json"
    )
    assert response.status_code == 400


def test_envelope_without_message_returns_400(client):
    response = client.post(
        RTDN_URL, data={"subscription": "x"}, content_type="application/json"
    )
    assert response.status_code == 400
