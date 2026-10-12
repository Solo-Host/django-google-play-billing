SECRET_KEY = "tests-only-secret-key"  # noqa: S105
USE_TZ = True
TIME_ZONE = "UTC"
ROOT_URLCONF = "tests.urls"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "google_play_billing",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DJANGO_GOOGLE_PLAY_BILLING = {
    "PACKAGE_NAME": "com.example.app",
    "RTDN_VERIFICATION_TOKEN": "rtdn-secret",
    "AUTO_ACKNOWLEDGE": True,
}
