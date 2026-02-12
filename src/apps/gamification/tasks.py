from __future__ import annotations

from celery import shared_task

from gamification.services import ProgressionService


@shared_task(name="gamification.tasks.run_weekly_level_evaluation")
def run_weekly_level_evaluation() -> dict[str, int | str]:
    return ProgressionService.run_weekly_level_evaluation()
