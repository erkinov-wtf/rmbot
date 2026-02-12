from django.core.management import BaseCommand, CommandError

from gamification.services import ProgressionService


class Command(BaseCommand):
    help = "Run weekly level evaluation and issue coupon events for level-ups."

    def add_arguments(self, parser):
        parser.add_argument(
            "--week-start",
            type=str,
            required=False,
            help="Monday date token in YYYY-MM-DD format. Defaults to previous week.",
        )
        parser.add_argument(
            "--actor-user-id",
            type=int,
            required=False,
            help="Optional actor user id for audit attribution.",
        )

    def handle(self, *args, **options):
        week_start_token = options.get("week_start")
        actor_user_id = options.get("actor_user_id")

        try:
            week_start = None
            if week_start_token:
                week_start = ProgressionService.parse_week_start_token(week_start_token)

            summary = ProgressionService.run_weekly_level_evaluation(
                week_start=week_start,
                actor_user_id=actor_user_id,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Completed weekly level evaluation: "
                f"week={summary['week_start']}..{summary['week_end']} "
                f"created={summary['evaluations_created']} "
                f"skipped={summary['evaluations_skipped']} "
                f"level_ups={summary['level_ups']} "
                f"coupon_events={summary['coupon_events_created']}"
            )
        )
