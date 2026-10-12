from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from google_play_billing.constants import ProcessingState
from google_play_billing.ingest import reprocess_notification
from google_play_billing.models import RealtimeNotification


class Command(BaseCommand):
    help = "Reprocess failed or pending Google Play RTDN notifications from stored payloads."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--state",
            default=ProcessingState.FAILED,
            choices=[ProcessingState.FAILED, ProcessingState.PENDING],
            help="Which processing state to reprocess (default: failed).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of notifications to reprocess.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        del args
        queryset = RealtimeNotification.objects.filter(
            processing_state=options["state"]
        ).order_by("created_at")[: options["limit"]]
        processed = 0
        failed = 0
        for notification in list(queryset):
            try:
                reprocess_notification(notification)
                processed += 1
            except Exception:  # noqa: BLE001 - reported in aggregate
                failed += 1
        self.stdout.write(
            self.style.SUCCESS(f"Reprocessed {processed} notification(s); {failed} failed.")
        )
