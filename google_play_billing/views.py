"""HTTP endpoint for Google Play Pub/Sub push notifications (RTDN)."""

from __future__ import annotations

import hmac
import json
import logging
from typing import Any

from django.http import HttpRequest, HttpResponseNotAllowed, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .exceptions import GooglePlayBillingError, RtdnVerificationError
from .ingest import ingest_pubsub_envelope
from .settings import get_google_play_billing_settings

logger = logging.getLogger("google_play_billing")


def _verify_oidc_token(request: HttpRequest, *, audience: str, expected_email: str | None) -> None:
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        raise RtdnVerificationError("Missing OIDC bearer token.")
    token = header[len("Bearer ") :].strip()

    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    try:
        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), audience
        )
    except Exception as exc:  # noqa: BLE001 - any verification failure is a rejection
        raise RtdnVerificationError(f"Invalid OIDC token: {exc}") from exc

    if expected_email and claims.get("email") != expected_email:
        raise RtdnVerificationError("OIDC token email does not match expected service account.")
    if expected_email and not claims.get("email_verified", False):
        raise RtdnVerificationError("OIDC token email is not verified.")


def _authorize(request: HttpRequest) -> None:
    package_settings = get_google_play_billing_settings()
    if package_settings.rtdn_verification_token:
        provided = request.GET.get("token", "")
        if not hmac.compare_digest(provided, package_settings.rtdn_verification_token):
            raise RtdnVerificationError("Invalid RTDN verification token.")
        return
    if package_settings.rtdn_audience:
        _verify_oidc_token(
            request,
            audience=package_settings.rtdn_audience,
            expected_email=package_settings.rtdn_service_account_email,
        )
        return
    logger.warning(
        "Google Play RTDN endpoint received a request with no verification configured; "
        "set RTDN_VERIFICATION_TOKEN or RTDN_AUDIENCE."
    )


@csrf_exempt
def rtdn_push(request: HttpRequest) -> JsonResponse | HttpResponseNotAllowed:
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    try:
        _authorize(request)
    except RtdnVerificationError as exc:
        return JsonResponse({"detail": str(exc)}, status=403)

    try:
        envelope: Any = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)
    if not isinstance(envelope, dict):
        return JsonResponse({"detail": "Pub/Sub envelope must be a JSON object."}, status=400)

    try:
        notification = ingest_pubsub_envelope(envelope)
    except GooglePlayBillingError as exc:
        # Malformed/undecodable payloads should be acknowledged, not retried forever.
        logger.warning("Rejecting malformed RTDN payload: %s", exc)
        return JsonResponse({"detail": str(exc)}, status=400)
    except Exception as exc:  # noqa: BLE001 - transient processing failure; ask for redelivery
        logger.exception("Transient failure processing RTDN payload")
        return JsonResponse({"detail": str(exc)}, status=500)

    return JsonResponse(
        {
            "message_id": notification.message_id,
            "category": notification.category,
            "notification_type": notification.notification_type,
            "processing_state": notification.processing_state,
        },
        status=200,
    )
