"""Lifecycle signals for django-google-play-billing.

Host applications connect to these signals to map mirrored Google Play state
onto their own subscription/entitlement models.
"""

from __future__ import annotations

from django.dispatch import Signal

# Sent after an RTDN envelope is received and recorded (before processing).
rtdn_received = Signal()

# Sent after a subscription purchase is fetched from the Play Developer API and
# mirrored into ``PlaySubscriptionPurchase``. Provides ``purchase`` and
# ``notification`` (may be ``None`` when triggered by a direct purchase link).
subscription_synced = Signal()

# Sent when a voided purchase (refund/chargeback/revoke) notification is
# ingested. Provides ``purchase_token`` and ``notification``.
voided_purchase_received = Signal()

# Sent when processing an RTDN envelope raises. Provides ``notification`` and
# ``error``.
rtdn_processing_error = Signal()
