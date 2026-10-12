"""Typed access to the ``DJANGO_GOOGLE_PLAY_BILLING`` Django setting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured

SETTING_NAME = "DJANGO_GOOGLE_PLAY_BILLING"


@dataclass(frozen=True, slots=True)
class DjangoGooglePlayBillingSettings:
    package_name: str
    service_account_info: Mapping[str, Any] | None
    service_account_file: str | None
    subscriber_model: str | None
    subscriber_email_field: str
    auto_acknowledge: bool
    store_raw_payloads: bool
    rtdn_verification_token: str | None
    rtdn_audience: str | None
    rtdn_service_account_email: str | None
    api_timeout: float


def _require_mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ImproperlyConfigured(f"{SETTING_NAME} must be a mapping.")
    return value


def _coerce_required_string(value: object, key: str) -> str:
    if not isinstance(value, str):
        raise ImproperlyConfigured(f"{SETTING_NAME}['{key}'] must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ImproperlyConfigured(f"{SETTING_NAME}['{key}'] is required.")
    return normalized


def _coerce_optional_string(value: object, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ImproperlyConfigured(f"{SETTING_NAME}['{key}'] must be a string.")
    normalized = value.strip()
    return normalized or None


def _coerce_bool(value: object, key: str, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ImproperlyConfigured(f"{SETTING_NAME}['{key}'] must be a boolean.")
    return value


def _coerce_service_account_info(value: object, key: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ImproperlyConfigured(f"{SETTING_NAME}['{key}'] must be a mapping.")
    return dict(value)


def _coerce_timeout(value: object, key: str, *, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ImproperlyConfigured(f"{SETTING_NAME}['{key}'] must be a number.")
    if value <= 0:
        raise ImproperlyConfigured(f"{SETTING_NAME}['{key}'] must be greater than zero.")
    return float(value)


@lru_cache(maxsize=1)
def get_google_play_billing_settings() -> DjangoGooglePlayBillingSettings:
    raw = getattr(django_settings, SETTING_NAME, None)
    if raw is None:
        raise ImproperlyConfigured(f"{SETTING_NAME} is required but was not configured.")
    config = _require_mapping(raw)

    service_account_info = _coerce_service_account_info(
        config.get("SERVICE_ACCOUNT_INFO"), "SERVICE_ACCOUNT_INFO"
    )
    service_account_file = _coerce_optional_string(
        config.get("SERVICE_ACCOUNT_FILE"), "SERVICE_ACCOUNT_FILE"
    )
    if service_account_info is not None and service_account_file is not None:
        raise ImproperlyConfigured(
            f"{SETTING_NAME} accepts only one of 'SERVICE_ACCOUNT_INFO' or "
            "'SERVICE_ACCOUNT_FILE'."
        )

    return DjangoGooglePlayBillingSettings(
        package_name=_coerce_required_string(config.get("PACKAGE_NAME"), "PACKAGE_NAME"),
        service_account_info=service_account_info,
        service_account_file=service_account_file,
        subscriber_model=_coerce_optional_string(
            config.get("SUBSCRIBER_MODEL"), "SUBSCRIBER_MODEL"
        ),
        subscriber_email_field=_coerce_optional_string(
            config.get("SUBSCRIBER_EMAIL_FIELD"), "SUBSCRIBER_EMAIL_FIELD"
        )
        or "email",
        auto_acknowledge=_coerce_bool(
            config.get("AUTO_ACKNOWLEDGE"), "AUTO_ACKNOWLEDGE", default=True
        ),
        store_raw_payloads=_coerce_bool(
            config.get("STORE_RAW_PAYLOADS"), "STORE_RAW_PAYLOADS", default=True
        ),
        rtdn_verification_token=_coerce_optional_string(
            config.get("RTDN_VERIFICATION_TOKEN"), "RTDN_VERIFICATION_TOKEN"
        ),
        rtdn_audience=_coerce_optional_string(config.get("RTDN_AUDIENCE"), "RTDN_AUDIENCE"),
        rtdn_service_account_email=_coerce_optional_string(
            config.get("RTDN_SERVICE_ACCOUNT_EMAIL"), "RTDN_SERVICE_ACCOUNT_EMAIL"
        ),
        api_timeout=_coerce_timeout(config.get("API_TIMEOUT"), "API_TIMEOUT", default=30.0),
    )


def clear_google_play_billing_settings_cache() -> None:
    get_google_play_billing_settings.cache_clear()
