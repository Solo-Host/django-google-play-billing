from __future__ import annotations

from django.contrib import admin

from .models import PlaySubscriptionPurchase, RealtimeNotification


@admin.register(PlaySubscriptionPurchase)
class PlaySubscriptionPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "product_id",
        "base_plan_id",
        "subscription_state",
        "auto_renewing",
        "expiry_time",
        "revoked",
        "updated_at",
    )
    list_filter = ("subscription_state", "auto_renewing", "revoked", "test_purchase")
    search_fields = ("purchase_token", "product_id", "latest_order_id", "subscriber_object_id")
    readonly_fields = ("created_at", "updated_at", "raw")


@admin.register(RealtimeNotification)
class RealtimeNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "message_id",
        "category",
        "notification_type",
        "processing_state",
        "processing_attempts",
        "created_at",
    )
    list_filter = ("category", "processing_state")
    search_fields = ("message_id", "purchase_token", "product_id")
    readonly_fields = ("created_at", "updated_at", "raw", "last_error")
