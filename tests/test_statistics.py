from datetime import date

from autody.history import TaskRunRecord, dashboard_statistics


def run(day: str, status="completed", retries=0):
    return TaskRunRecord(
        run_id=day,
        date=day,
        task_type="daily_send",
        trigger_source="scheduled",
        start_time=f"{day}T07:30:00",
        end_time=f"{day}T07:31:00",
        duration=60,
        total_targets=2,
        success_count=2 if status == "completed" else 1,
        failed_count=0 if status == "completed" else 1,
        retry_count=retries,
        final_status=status,
    )


def test_dashboard_statistics_use_structured_history():
    records = [run("2026-07-11"), run("2026-07-12"), run("2026-07-13", retries=2)]

    stats = dashboard_statistics(records, date(2026, 7, 13))

    assert stats["consecutive_successful_days"] == 3
    assert stats["success_rate_7d"] == 100.0
    assert stats["retries_7d"] == 2
