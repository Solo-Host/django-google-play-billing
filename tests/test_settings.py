from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from google_play_billing.settings import (
    clear_google_play_billing_settings_cache,
    get_google_play_billing_settings,
)


def test_defaults_are_applied():
    settings = get_google_play_billing_settings()
    assert settings.package_name == "com.example.app"
    assert settings.auto_acknowledge is True
    assert settings.store_raw_payloads is True
    assert settings.subscriber_email_field == "email"
    assert settings.api_timeout == 30.0


@override_settings(DJANGO_GOOGLE_PLAY_BILLING=None)
def test_missing_setting_raises():
    clear_google_play_billing_settings_cache()
    with pytest.raises(ImproperlyConfigured):
        get_google_play_billing_settings()


@override_settings(DJANGO_GOOGLE_PLAY_BILLING={"PACKAGE_NAME": "  "})
def test_blank_package_name_raises():
    clear_google_play_billing_settings_cache()
    with pytest.raises(ImproperlyConfigured):
        get_google_play_billing_settings()


@override_settings(
    DJANGO_GOOGLE_PLAY_BILLING={
        "PACKAGE_NAME": "com.example.app",
        "SERVICE_ACCOUNT_INFO": {"type": "service_account"},
        "SERVICE_ACCOUNT_FILE": "/tmp/key.json",  # noqa: S108
    }
)
def test_conflicting_credentials_raise():
    clear_google_play_billing_settings_cache()
    with pytest.raises(ImproperlyConfigured):
        get_google_play_billing_settings()
