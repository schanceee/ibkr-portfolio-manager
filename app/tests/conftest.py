"""
pytest configuration — registers custom markers so pytest doesn't warn about unknown markers.
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end tests requiring a real paper TWS running on port 7497",
    )
    config.addinivalue_line(
        "markers",
        "ui: Playwright browser tests — require app server running and E2E_BASE_URL set",
    )


def pytest_collection_modifyitems(config, items):
    """Skip e2e and ui tests unless explicitly requested via -m."""
    markexpr = config.option.markexpr or ""
    for item in items:
        if "e2e" in item.keywords and "e2e" not in markexpr:
            item.add_marker(pytest.mark.skip(reason="E2E tests skipped — run with: pytest -m e2e"))
        if "ui" in item.keywords and "ui" not in markexpr:
            item.add_marker(pytest.mark.skip(reason="UI tests skipped — run with: ./run_ui_tests.sh"))
