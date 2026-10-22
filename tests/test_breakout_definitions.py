from breakout.definitions import defs


def test_definitions_expose_assets_and_schedule() -> None:
    graph = defs.resolve_asset_graph()
    keys = {key.to_user_string() for key in graph.get_all_asset_keys()}
    assert {"ingest", "dbt_models", "pipeline_health"} <= keys
    assert len(defs.schedules) == 1
    schedule = defs.schedules[0]
    assert schedule.cron_schedule == "0 6 * * *"
