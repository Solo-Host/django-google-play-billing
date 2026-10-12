from __future__ import annotations

from typing import Any

from django.apps import AppConfig
from django.test.signals import setting_changed

from .settings import SETTING_NAME, clear_google_play_billing_settings_cache


def _handle_setting_changed(*, setting: str, **kwargs: Any) -> None:
    if setting == SETTING_NAME:
        clear_google_play_billing_settings_cache()


class GooglePlayBillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "google_play_billing"
    verbose_name = "Django Google Play Billing"

    def ready(self) -> None:
        setting_changed.connect(
            _handle_setting_changed,
            dispatch_uid="google_play_billing.handle_setting_changed",
        )
