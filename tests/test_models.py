from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from google_play_billing.models import PlaySubscriptionPurchase

pytestmark = pytest.mark.django_db


def test_link_subscriber_resolves_back():
    user = get_user_model().objects.create_user(username="alice", password="pw")  # noqa: S106
    purchase = PlaySubscriptionPurchase.objects.create(
        package_name="com.example.app",
        purchase_token="token-xyz",
        product_id="personal_monthly",
    )
    purchase.link_subscriber(user)

    purchase.refresh_from_db()
    assert purchase.subscriber_model_label == "auth.User"
    assert purchase.subscriber == user


def test_subscriber_is_none_when_unlinked():
    purchase = PlaySubscriptionPurchase.objects.create(
        package_name="com.example.app",
        purchase_token="token-unlinked",
    )
    assert purchase.subscriber is None
