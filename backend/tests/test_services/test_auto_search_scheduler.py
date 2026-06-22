from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.auto_search_scheduler import reschedule, shutdown_scheduler, start_scheduler


def test_start_and_shutdown_scheduler():
    """Scheduler starts and shuts down without errors."""
    start_scheduler(interval_hours=999)  # very long interval to avoid firing
    shutdown_scheduler()


def test_reschedule_changes_interval():
    start_scheduler(interval_hours=999)
    try:
        # Should not raise — just updates the trigger
        reschedule(new_interval_hours=888)
    finally:
        shutdown_scheduler()


def test_trigger_now_runs_in_thread():
    """trigger_now should fire _run in a background thread, not block."""
    import threading
    import time

    ran = threading.Event()

    def fake_run():
        ran.set()

    with (
        patch("app.services.auto_search_scheduler._run", side_effect=fake_run),
        patch("app.services.auto_search_store.update_run_times"),
        patch("app.services.job_store.create_job"),
        patch("app.services.job_store.update_job"),
    ):
        from app.services.auto_search_scheduler import trigger_now
        trigger_now(job_id="test-job-id")
        ran.wait(timeout=3.0)
        assert ran.is_set(), "_run was not called within 3 seconds"
