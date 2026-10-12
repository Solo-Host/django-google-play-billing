"""Django models mirroring Google Play subscription purchases and RTDN events."""

from __future__ import annotations

from typing import Any

from django.apps import apps as django_apps
from django.db import models

from .constants import NotificationCategory, ProcessingState


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PlaySubscriptionPurchase(TimestampedModel):
    """Mirror of a Google Play subscription purchase (SubscriptionPurchaseV2)."""

    package_name = models.CharField(max_length=255)
    purchase_token = models.CharField(max_length=1024, unique=True)
    product_id = models.CharField(max_length=255, blank=True)
    base_plan_id = models.CharField(max_length=255, blank=True)
    offer_id = models.CharField(max_length=255, blank=True)
    subscription_state = models.CharField(max_length=64, blank=True)
    latest_order_id = models.CharField(max_length=255, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    expiry_time = models.DateTimeField(null=True, blank=True)
    auto_renewing = models.BooleanField(default=False)
    acknowledgement_state = models.CharField(max_length=64, blank=True)
    linked_purchase_token = models.CharField(max_length=1024, blank=True)
    test_purchase = models.BooleanField(default=False)
    revoked = models.BooleanField(default=False)
    subscriber_model_label = models.CharField(max_length=255, blank=True)
    subscriber_object_id = models.CharField(max_length=64, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "google_play_subscription_purchase"
        ordering = ["-updated_at", "-id"]
        indexes = [
            models.Index(fields=["product_id", "subscription_state"]),
            models.Index(fields=["subscriber_model_label", "subscriber_object_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.product_id or 'subscription'} ({self.subscription_state or 'unknown'})"

    @property
    def subscriber(self) -> Any | None:
        if not self.subscriber_model_label or not self.subscriber_object_id:
            return None
        try:
            subscriber_model = django_apps.get_model(self.subscriber_model_label)
        except (LookupError, ValueError):
            return None
        return subscriber_model._default_manager.filter(pk=self.subscriber_object_id).first()

    def link_subscriber(self, subscriber: Any) -> None:
        self.subscriber_model_label = subscriber._meta.label
        self.subscriber_object_id = str(subscriber.pk)
        self.save(
            update_fields=["subscriber_model_label", "subscriber_object_id", "updated_at"]
        )


class RealtimeNotification(TimestampedModel):
    """A received Google Play Real-time Developer Notification envelope."""

    message_id = models.CharField(max_length=255, unique=True)
    publish_time = models.DateTimeField(null=True, blank=True)
    event_time = models.DateTimeField(null=True, blank=True)
    package_name = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=32, default=NotificationCategory.UNKNOWN)
    notification_type = models.IntegerField(null=True, blank=True)
    purchase_token = models.CharField(max_length=1024, blank=True)
    product_id = models.CharField(max_length=255, blank=True)
    processing_state = models.CharField(max_length=16, default=ProcessingState.PENDING)
    processing_attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "google_play_realtime_notification"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["category", "processing_state"]),
            models.Index(fields=["purchase_token"]),
        ]

    def __str__(self) -> str:
        return f"{self.category}:{self.notification_type} ({self.processing_state})"
