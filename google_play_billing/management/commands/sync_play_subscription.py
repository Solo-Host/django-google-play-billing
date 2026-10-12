from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from google_play_billing.ingest import sync_subscription_purchase


class Command(BaseCommand):
    help = "Fetch a Google Play subscription purchase by token and mirror it locally."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("purchase_token", help="The Google Play purchase token to sync.")

    def handle(self, *args: Any, **options: Any) -> None:
        del args
        purchase = sync_subscription_purchase(options["purchase_token"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Synced {purchase.product_id} state={purchase.subscription_state} "
                f"expiry={purchase.expiry_time}"
            )
        )
