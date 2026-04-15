"""
pytest configuration — registers custom markers so pytest doesn't warn about unknown markers.
"""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end tests requiring a real paper TWS running on port 7497",
    )


def pytest_collection_modifyitems(config, items):
    """Skip e2e tests unless -m e2e is explicitly passed."""
    if not config.option.markexpr or "e2e" not in config.option.markexpr:
        skip_e2e = pytest.mark.skip(reason="E2E tests skipped — run with: pytest -m e2e")
        for item in items:
            if "e2e" in item.keywords:
                item.add_marker(skip_e2e)
