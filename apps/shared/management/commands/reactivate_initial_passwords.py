import logging
from django.core.management.base import BaseCommand
from apps.shared.models import User, UserInitialPassword

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Reactivate or create UserInitialPassword records so first-login flows trigger again."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records would be updated without touching the database.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional limit for number of users to process (useful for smoke tests).",
        )

    def handle(self, *_args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        inactive_qs = UserInitialPassword.objects.filter(is_active=False)
        missing_qs = User.objects.filter(initial_password__isnull=True)

        if limit:
            inactive_qs = inactive_qs[:limit]
            missing_qs = missing_qs[:max(limit - inactive_qs.count(), 0)]

        reactivated = inactive_qs.count()
        created = missing_qs.count()

        self.stdout.write(
            self.style.NOTICE(
                f"Found {reactivated} inactive records and {created} users with no initial password."
            )
        )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run complete - no changes applied."))
            return

        # Reactivate inactive records
        updated = inactive_qs.update(is_active=True)

        # Warn about users missing initial passwords (we cannot recreate plaintext)
        if created:
            for user in missing_qs.iterator():
                logger.warning(
                    "User %s (%s) has no initial password record; manual follow-up required.",
                    user.acc_username,
                    user.user_id,
                )

        self.stdout.write(
            self.style.SUCCESS(f"Reactivated {updated} initial password record(s).")
        )


