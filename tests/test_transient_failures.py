"""A failure on Entur's side (5xx, timeout, connection error) must not blank the sensors.

On 19.11.2026 about a third of the polls between 21:31 and 00:45 came back 500. Each one
raised UpdateFailed, so every sensor went unavailable until the next poll two minutes
later, and each failure was logged three times at ERROR.
"""
import asyncio
import logging
import sys
import types
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

try:  # pragma: no cover - a real HA install wins
    import homeassistant.helpers.update_coordinator  # noqa: F401
except ImportError:
    class _Coordinator:
        def __init__(self, hass, logger, name=None, update_interval=None):
            self.hass = hass
            self.update_interval = update_interval

        def __class_getitem__(cls, item):
            return cls

    class UpdateFailed(Exception):
        pass

    for name in (
        "homeassistant", "homeassistant.core", "homeassistant.helpers",
        "homeassistant.helpers.aiohttp_client",
        "homeassistant.helpers.update_coordinator",
    ):
        sys.modules.setdefault(name, types.ModuleType(name))
    sys.modules["homeassistant.core"].HomeAssistant = object
    sys.modules["homeassistant.helpers.aiohttp_client"].async_get_clientsession = MagicMock()
    sys.modules["homeassistant.helpers"].instance_id = MagicMock()
    uc = sys.modules["homeassistant.helpers.update_coordinator"]
    uc.DataUpdateCoordinator = _Coordinator
    uc.UpdateFailed = UpdateFailed

    # The integration's __init__ pulls in half of Home Assistant; these tests only need
    # the coordinator, so load the package without running it.
    from pathlib import Path
    _root = Path(__file__).resolve().parent.parent / "custom_components"
    for name, path in (("custom_components", _root), ("custom_components.entur_sx", _root / "entur_sx")):
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(path)]
        sys.modules[name] = pkg

from homeassistant.helpers.update_coordinator import UpdateFailed  # noqa: E402

from custom_components.entur_sx.const import (  # noqa: E402
    BACKOFF_MAX,
    STALE_DATA_MAX_AGE,
    TRANSIENT_BACKOFF_AFTER,
    UPDATE_INTERVAL,
)
from custom_components.entur_sx.coordinator import EnturSXDataUpdateCoordinator  # noqa: E402

DATA = {"SKY:Line:1": [{"status": "open", "summary": "Test"}]}


def _http_error(status, headers=None):
    return aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=status,
        message="Internal Server Error", headers=headers,
    )


@pytest.fixture
def coordinator():
    api = MagicMock()
    api._operator = None
    api.set_session = MagicMock()
    with patch("custom_components.entur_sx.coordinator.async_get_clientsession"):
        coord = EnturSXDataUpdateCoordinator(MagicMock(), api)
    coord.hass.config_entries.async_entries.return_value = []
    return coord


async def _prime(coord):
    coord.api.async_get_deviations = AsyncMock(return_value=DATA)
    assert await coord._async_update_data() == DATA


@pytest.mark.asyncio
@pytest.mark.parametrize("err", [
    _http_error(500), _http_error(502), _http_error(503),
    asyncio.TimeoutError(), aiohttp.ClientConnectionError("reset"),
])
async def test_transient_failure_keeps_last_data(coordinator, err):
    await _prime(coordinator)
    coordinator.api.async_get_deviations = AsyncMock(side_effect=err)
    assert await coordinator._async_update_data() == DATA


@pytest.mark.asyncio
async def test_logs_once_per_run_of_failures(coordinator, caplog):
    await _prime(coordinator)
    coordinator.api.async_get_deviations = AsyncMock(side_effect=_http_error(500))
    with caplog.at_level(logging.INFO):
        for _ in range(4):
            await coordinator._async_update_data()
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


@pytest.mark.asyncio
async def test_recovery_is_logged_and_resets_interval(coordinator, caplog):
    await _prime(coordinator)
    coordinator.api.async_get_deviations = AsyncMock(side_effect=_http_error(500))
    for _ in range(TRANSIENT_BACKOFF_AFTER + 1):
        await coordinator._async_update_data()
    assert coordinator.update_interval.total_seconds() > UPDATE_INTERVAL

    coordinator.api.async_get_deviations = AsyncMock(return_value=DATA)
    with caplog.at_level(logging.INFO):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL)
    assert any("recovered after 4" in r.getMessage() for r in caplog.records)
    assert coordinator._failure_count == 0


@pytest.mark.asyncio
async def test_backoff_only_after_repeated_failures_and_is_capped(coordinator):
    await _prime(coordinator)
    coordinator.api.async_get_deviations = AsyncMock(side_effect=_http_error(500))
    for n in range(1, TRANSIENT_BACKOFF_AFTER):
        await coordinator._async_update_data()
        assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL), n
    for _ in range(10):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=BACKOFF_MAX)


@pytest.mark.asyncio
async def test_retry_after_is_honoured_up_to_the_cap(coordinator):
    await _prime(coordinator)
    err = _http_error(503, headers={"Retry-After": "400"})
    coordinator.api.async_get_deviations = AsyncMock(side_effect=err)
    for _ in range(TRANSIENT_BACKOFF_AFTER):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=400)


@pytest.mark.asyncio
async def test_data_goes_unavailable_once_too_old(coordinator):
    await _prime(coordinator)
    coordinator._last_success_time = datetime.now() - timedelta(seconds=STALE_DATA_MAX_AGE + 60)
    coordinator.api.async_get_deviations = AsyncMock(side_effect=_http_error(500))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_no_cache_means_unavailable(coordinator):
    coordinator.api.async_get_deviations = AsyncMock(side_effect=_http_error(500))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_client_errors_still_fail_loudly(coordinator, status):
    await _prime(coordinator)
    coordinator.api.async_get_deviations = AsyncMock(side_effect=_http_error(status))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
