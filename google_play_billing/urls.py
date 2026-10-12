from django.urls import path

from .views import rtdn_push

app_name = "google_play_billing"

urlpatterns = [
    path("webhooks/google-play/", rtdn_push, name="rtdn_push"),
]
