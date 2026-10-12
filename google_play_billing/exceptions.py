"""Exceptions raised by django-google-play-billing."""

from __future__ import annotations


class GooglePlayBillingError(Exception):
    """Base error for all django-google-play-billing failures."""


class RtdnVerificationError(GooglePlayBillingError):
    """Raised when a Real-time Developer Notification request cannot be trusted."""


class PlayApiError(GooglePlayBillingError):
    """Raised when the Google Play Developer API call fails."""
