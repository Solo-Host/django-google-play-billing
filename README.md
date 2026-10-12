# django-google-play-billing

`django-google-play-billing` is a reusable Django app for **Google Play
subscription billing**. It mirrors Google Play subscription purchases into Django
models, verifies purchases through the Google Play Developer API
(`androidpublisher` v3), ingests **Real-time Developer Notifications (RTDN)**
delivered over Cloud Pub/Sub, and emits lifecycle signals that a host
application connects to in order to drive its own subscription/entitlement
state.

It is deliberately provider-generic (no product/plan/seat logic); the host
application owns the mapping from Google Play state to its own models — the same
split used by `django-paddle-mor`.

## What it includes

- installable Django app with typed package settings
- `PlaySubscriptionPurchase` mirror model (SubscriptionPurchaseV2 state)
- `RealtimeNotification` record for every RTDN envelope (idempotent + replayable)
- Google Play Developer API client (verify + acknowledge subscriptions)
- Pub/Sub push endpoint with shared-token or OIDC verification
- lifecycle signals (`subscription_synced`, `voided_purchase_received`,
  `rtdn_received`, `rtdn_processing_error`)
- management commands to sync a purchase and reprocess stored notifications
- Django admin registration

## Install

```bash
pip install django-google-play-billing
```

## Configure

Add the app to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    "google_play_billing",
]
```

Configure package settings:

```python
DJANGO_GOOGLE_PLAY_BILLING = {
    "PACKAGE_NAME": "com.example.app",
    # Provide exactly one credential source for the Play Developer API:
    "SERVICE_ACCOUNT_INFO": {...},        # service-account JSON as a dict, or
    # "SERVICE_ACCOUNT_FILE": "/path/key.json",
    "SUBSCRIBER_MODEL": "auth.User",      # optional
    "AUTO_ACKNOWLEDGE": True,
    # RTDN push verification — pick one:
    "RTDN_VERIFICATION_TOKEN": "a-shared-secret",   # ?token=... query param, or
    # "RTDN_AUDIENCE": "https://api.example.com/webhooks/google-play/",
    # "RTDN_SERVICE_ACCOUNT_EMAIL": "pubsub-push@project.iam.gserviceaccount.com",
}
```

Include the webhook URL:

```python
from django.urls import include, path

urlpatterns = [
    path("billing/", include("google_play_billing.urls")),
]
```

The RTDN push endpoint is served at `billing/webhooks/google-play/`.

## Host integration

Connect to the lifecycle signals to map Google Play state onto your own models:

```python
from django.dispatch import receiver
from google_play_billing.signals import subscription_synced, voided_purchase_received


@receiver(subscription_synced)
def on_subscription_synced(sender, purchase, notification, created, **kwargs):
    # map purchase.subscription_state / expiry_time onto your Subscription
    ...


@receiver(voided_purchase_received)
def on_voided_purchase(sender, purchase_token, notification, **kwargs):
    ...
```

To link a Play purchase submitted by a signed-in user (purchase-token hand-off
from the mobile client), verify and mirror it, then attach the subscriber:

```python
from google_play_billing.ingest import sync_subscription_purchase

purchase = sync_subscription_purchase(purchase_token)
purchase.link_subscriber(request.user)
```

## License

MIT
