"""Common fixtures for the NATS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with (
        patch(
            "custom_components.nats_io.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch(
            "custom_components.nats_io.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock_setup_entry
