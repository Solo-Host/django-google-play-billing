from django.urls import include, path

urlpatterns = [
    path("", include("google_play_billing.urls")),
]
