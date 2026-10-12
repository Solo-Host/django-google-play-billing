from __future__ import annotations

import importlib
from typing import Any

from . import signals
from .client import GooglePlayAPI, build_android_publisher_service

__version__ = "0.1.0"

# Lazily exposed to avoid importing models before the Django app registry is ready.
_LAZY_EXPORTS = {
    "ingest_pubsub_envelope": ("google_play_billing.ingest", "ingest_pubsub_envelope"),
    "sync_subscription_purchase": ("google_play_billing.ingest", "sync_subscription_purchase"),
    "PlaySubscriptionPurchase": ("google_play_billing.models", "PlaySubscriptionPurchase"),
    "RealtimeNotification": ("google_play_billing.models", "RealtimeNotification"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    return getattr(importlib.import_module(module_name), attribute)


__all__ = [
    "GooglePlayAPI",
    "build_android_publisher_service",
    "ingest_pubsub_envelope",
    "sync_subscription_purchase",
    "PlaySubscriptionPurchase",
    "RealtimeNotification",
    "signals",
    "__version__",
]
