from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src" / "breakout" / "dashboard.py"


def test_dashboard_renders_without_uncaught_exception() -> None:
    app = AppTest.from_file(str(APP))
    app.run(timeout=60)
    assert not app.exception
