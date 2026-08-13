"""Tests for disruption change tracking and its log levels.

Standalone: the rest of tests/ is a collection of ad-hoc investigation scripts that
do not collect under pytest, so run this file directly:

    python -m pytest tests/test_disruption_tracking.py -v

Stubs Home Assistant rather than importing it, so no HA install is needed.
"""
from __future__ import annotations

import logging
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Stub Home Assistant, and register the package without running its __init__ ──
# Importing custom_components.entur_sx normally executes __init__.py, which pulls in a
# large amount of Home Assistant. Registering the package as a module object with a
# __path__ lets `from .api import ...` resolve while that file is never executed.
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))


def _pkg(name: str, path: Path | None = None) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__path__ = [str(path)] if path else []
    sys.modules[name] = mod
    return mod


_ha = _pkg("homeassistant")
for sub in ("core", "config_entries", "const", "exceptions", "helpers",
            "helpers.aiohttp_client", "helpers.update_coordinator",
            "helpers.entity", "helpers.entity_platform", "util", "util.dt",
            "components", "components.sensor"):
    full = f"homeassistant.{sub}"
    m = MagicMock()
    m.__path__ = []
    sys.modules[full] = m
    parts = sub.split(".")
    setattr(sys.modules["homeassistant" if len(parts) == 1 else
                        f"homeassistant.{'.'.join(parts[:-1])}"], parts[-1], m)


class _DataUpdateCoordinator:
    """Minimal stand-in: the real base class only needs to be constructible."""

    def __init__(self, *args, **kwargs):
        self.hass = kwargs.get("hass") or (args[0] if args else None)

    def __class_getitem__(cls, _item):
        return cls


class _UpdateFailed(Exception):
    pass


_uc = sys.modules["homeassistant.helpers.update_coordinator"]
_uc.DataUpdateCoordinator = _DataUpdateCoordinator
_uc.UpdateFailed = _UpdateFailed

# Third-party modules api.py imports at module scope but this test never exercises.
for _third_party in ("async_timeout", "aiohttp", "voluptuous"):
    sys.modules.setdefault(_third_party, MagicMock())

_pkg("custom_components", _ROOT / "custom_components")
_pkg("custom_components.entur_sx", _ROOT / "custom_components" / "entur_sx")

from custom_components.entur_sx.coordinator import (  # noqa: E402
    EnturSXDataUpdateCoordinator,
)

_LOGGER_NAME = "custom_components.entur_sx.coordinator.disruptions"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _coord(monitored=("SKY:Line:1",)):
    c = EnturSXDataUpdateCoordinator.__new__(EnturSXDataUpdateCoordinator)
    c._previous_disruptions = {}
    c._first_disruption_check = False        # startup quiet is tested separately
    entry = MagicMock()
    entry.data = {"lines_to_check": list(monitored)}
    entry.options = {}
    c.hass = MagicMock()
    c.hass.config_entries.async_entries.return_value = [entry]
    return c


def _dev(summary="Trafikkmelding", status="open", valid_from="2026-08-13T09:00:00+02:00",
         situation_number="SKY:SituationNumber:1"):
    return {
        "summary": summary,
        "status": status,
        "valid_from": valid_from,
        "situation_number": situation_number,
    }


def _capture(coord, data, level):
    """Run tracking and return the messages logged at exactly `level`."""
    records: list[logging.LogRecord] = []

    class _Handler(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger(_LOGGER_NAME)
    handler = _Handler()
    prev_level, prev_prop = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    try:
        coord._track_disruption_changes(data)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(prev_level)
        logger.propagate = prev_prop
    return [r.getMessage() for r in records if r.levelno == level]


# ═════════════════════════════════════════════════════════════════════════════
# Log level: only lines with a sensor are worth INFO
# ═════════════════════════════════════════════════════════════════════════════

class TestOnlyMonitoredLinesReachInfo:
    """The feed covers the whole dataset; most of it concerns lines nobody asked for.

    That was nearly all of the log volume and none of it actionable.
    """

    def test_a_monitored_line_logs_at_info(self):
        c = _coord(monitored=["SKY:Line:1"])
        assert _capture(c, {"SKY:Line:1": [_dev()]}, logging.INFO)

    def test_an_unmonitored_line_stays_at_debug(self):
        c = _coord(monitored=["SKY:Line:1"])
        data = {"SKY:Line:1026": [_dev(summary="Jondal-Tørvikbygd innstilt")]}
        assert _capture(c, data, logging.INFO) == []
        c = _coord(monitored=["SKY:Line:1"])
        assert _capture(c, data, logging.DEBUG), "should still be available at debug"

    def test_lines_from_options_count_as_monitored(self):
        """Reconfiguring writes to options, not data."""
        c = _coord()
        entry = MagicMock()
        entry.data = {"lines_to_check": []}
        entry.options = {"lines_to_check": ["SKY:Line:7"]}
        c.hass.config_entries.async_entries.return_value = [entry]
        assert _capture(c, {"SKY:Line:7": [_dev()]}, logging.INFO)

    def test_lines_across_several_entries_are_all_monitored(self):
        """One coordinator serves every entry, so the union is what matters."""
        c = _coord()
        e1, e2 = MagicMock(), MagicMock()
        e1.data, e1.options = {"lines_to_check": ["SKY:Line:1"]}, {}
        e2.data, e2.options = {"lines_to_check": ["SKY:Line:2"]}, {}
        c.hass.config_entries.async_entries.return_value = [e1, e2]
        assert _capture(c, {"SKY:Line:2": [_dev()]}, logging.INFO)

    def test_startup_is_quiet_even_for_monitored_lines(self):
        c = _coord(monitored=["SKY:Line:1"])
        c._first_disruption_check = True
        assert _capture(c, {"SKY:Line:1": [_dev()]}, logging.INFO) == []


# ═════════════════════════════════════════════════════════════════════════════
# Identity: a status change is one event, not a removal plus an addition
# ═════════════════════════════════════════════════════════════════════════════

class TestStatusChangeIsOneEvent:
    """The key used to include the status, so any transition read as NEW + REMOVED.

    Observed 2026-08-13: `NEW … (status: expired)` immediately followed by
    `REMOVED … (was: open)` for one disruption on SKY:Line:1038, and the same pattern
    for planned → open on lines 850 and 800.
    """

    def test_a_status_transition_logs_once_as_changed(self):
        c = _coord(monitored=["SKY:Line:1"])
        _capture(c, {"SKY:Line:1": [_dev(status="planned")]}, logging.INFO)
        msgs = _capture(c, {"SKY:Line:1": [_dev(status="open")]}, logging.INFO)
        assert len(msgs) == 1, f"expected one line, got {msgs}"
        assert "CHANGED" in msgs[0]
        assert "planned" in msgs[0] and "open" in msgs[0]

    def test_a_status_transition_is_not_reported_as_new_or_removed(self):
        c = _coord(monitored=["SKY:Line:1"])
        _capture(c, {"SKY:Line:1": [_dev(status="open")]}, logging.INFO)
        msgs = _capture(c, {"SKY:Line:1": [_dev(status="expired")]}, logging.INFO)
        assert not any("NEW" in m or "REMOVED" in m for m in msgs), msgs

    def test_an_unchanged_disruption_logs_nothing(self):
        c = _coord(monitored=["SKY:Line:1"])
        _capture(c, {"SKY:Line:1": [_dev()]}, logging.INFO)
        assert _capture(c, {"SKY:Line:1": [_dev()]}, logging.INFO) == []

    def test_a_genuinely_new_disruption_still_reports_new(self):
        c = _coord(monitored=["SKY:Line:1"])
        _capture(c, {"SKY:Line:1": [_dev(situation_number="A")]}, logging.INFO)
        msgs = _capture(
            c,
            {"SKY:Line:1": [_dev(situation_number="A"),
                            _dev(situation_number="B", summary="Vegarbeid")]},
            logging.INFO,
        )
        assert len(msgs) == 1 and "NEW" in msgs[0], msgs

    def test_a_disappearing_disruption_still_reports_removed(self):
        c = _coord(monitored=["SKY:Line:1"])
        _capture(c, {"SKY:Line:1": [_dev()]}, logging.INFO)
        msgs = _capture(c, {"SKY:Line:1": []}, logging.INFO)
        assert len(msgs) == 1 and "REMOVED" in msgs[0], msgs

    def test_identity_falls_back_when_there_is_no_situation_number(self):
        """Older payloads lack one; summary plus validity survives a status change."""
        c = _coord(monitored=["SKY:Line:1"])
        bare = {"summary": "Trafikkmelding", "status": "open",
                "valid_from": "2026-08-13T09:00:00+02:00"}
        _capture(c, {"SKY:Line:1": [bare]}, logging.INFO)
        msgs = _capture(c, {"SKY:Line:1": [{**bare, "status": "expired"}]}, logging.INFO)
        assert len(msgs) == 1 and "CHANGED" in msgs[0], msgs

    def test_the_key_ignores_status_directly(self):
        a = EnturSXDataUpdateCoordinator._disruption_key(_dev(status="open"))
        b = EnturSXDataUpdateCoordinator._disruption_key(_dev(status="expired"))
        assert a == b


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
