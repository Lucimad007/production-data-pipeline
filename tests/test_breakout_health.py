from breakout.health import evaluate_slos, failing_checks


def test_health_checks_include_core_slos(settings) -> None:
    checks = evaluate_slos(settings)
    names = {check.name for check in checks}

    assert {
        "bronze_videos_present",
        "snapshots_present",
        "comments_present",
        "freshness_hours",
        "quota_used",
        "quarantine_empty",
        "mart_checks_available",
    } <= names
    assert all(isinstance(check.passed, bool) for check in checks)
    assert isinstance(failing_checks(checks), list)
