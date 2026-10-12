import pytest

from google_play_billing.settings import clear_google_play_billing_settings_cache


@pytest.fixture(autouse=True)
def clear_settings_cache():
    clear_google_play_billing_settings_cache()
    yield
    clear_google_play_billing_settings_cache()
