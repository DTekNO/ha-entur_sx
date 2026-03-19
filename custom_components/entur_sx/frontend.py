"""Frontend resource management for Entur Alert Card."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from homeassistant.components.lovelace.const import (
    CONF_RESOURCE_TYPE_WS,
    CONF_URL,
)
from homeassistant.const import CONF_ID, CONF_TYPE, EVENT_COMPONENT_LOADED
from homeassistant.core import Event, HomeAssistant, callback

from .const import (
    CARD_FILENAME,
    CARD_LEGACY_BASE_URL,
    CARD_WWW_DIR,
    FRONTEND_DATA_COMPONENT_LISTENER,
    FRONTEND_DATA_KEY,
)

_LOGGER = logging.getLogger(__name__)


def _card_file_path() -> Path:
    """Return absolute path to bundled card file."""
    return Path(__file__).resolve().parent / CARD_WWW_DIR / CARD_FILENAME


def _local_www_card_path(hass: HomeAssistant) -> Path:
    """Return target path for /local card file."""
    return Path(hass.config.path("www")) / CARD_FILENAME


def _read_manifest_version() -> str:
    """Read integration version from manifest.json."""
    manifest_path = Path(__file__).resolve().parent / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "0.0.0"
    return str(manifest.get("version", "0.0.0"))


def _card_mtime() -> int:
    """Read card modification time for cache busting."""
    card_path = _card_file_path()
    try:
        return int(card_path.stat().st_mtime)
    except OSError:
        return 0


def _read_file_bytes(path: Path) -> bytes:
    """Read file bytes."""
    return path.read_bytes()


def _write_file_bytes(path: Path, content: bytes) -> None:
    """Write file bytes atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.replace(path)


async def _async_sync_card_to_local_www(hass: HomeAssistant) -> None:
    """Sync bundled card file into /config/www for /local serving."""
    source = _card_file_path()
    target = _local_www_card_path(hass)

    if not source.exists():
        _LOGGER.warning("Missing bundled card file: %s", source)
        return

    source_bytes = await hass.async_add_executor_job(_read_file_bytes, source)

    # Only write if file doesn't exist or content is different
    if target.exists():
        target_bytes = await hass.async_add_executor_job(_read_file_bytes, target)
        if target_bytes == source_bytes:
            _LOGGER.debug("Card file in /local is up to date")
            return

    _LOGGER.info("Syncing Entur alert card to %s", target)
    await hass.async_add_executor_job(_write_file_bytes, target, source_bytes)


async def _cache_key_for_dev(hass: HomeAssistant) -> str:
    """Build cache key from manifest version and card mtime."""
    version_task = hass.async_add_executor_job(_read_manifest_version)
    mtime_task = hass.async_add_executor_job(_card_mtime)
    version, mtime = await asyncio.gather(version_task, mtime_task)
    return f"{version}-{mtime}"


def _url_base(url: str) -> str:
    """Return URL without query/fragment to allow stable comparisons."""
    split = urlsplit(url)
    return urlunsplit((split.scheme, split.netloc, split.path, "", ""))


def _url_with_version(base_url: str, cache_key: str) -> str:
    """Set/update the `v` query parameter for cache-busting."""
    split = urlsplit(base_url)
    query = dict(parse_qsl(split.query, keep_blank_values=True))
    query["v"] = cache_key
    return urlunsplit(
        (
            split.scheme,
            split.netloc,
            split.path,
            urlencode(query, doseq=True),
            split.fragment,
        )
    )


async def _async_get_lovelace_resources(hass: HomeAssistant):
    """Return Lovelace resource collection or None if unavailable."""
    lovelace_data = hass.data.get("lovelace")
    if lovelace_data is None:
        return None

    resources = getattr(lovelace_data, "resources", None)
    if resources is None:
        return None

    # Ensure resources are loaded
    if hasattr(resources, "loaded") and not resources.loaded and hasattr(
        resources, "async_load"
    ):
        await resources.async_load()
        resources.loaded = True

    return resources


async def _async_ensure_card_resource(hass: HomeAssistant) -> bool:
    """Create/update Lovelace module resource for the card."""
    cache_key = await _cache_key_for_dev(hass)
    desired_url = _url_with_version(CARD_LEGACY_BASE_URL, cache_key)

    try:
        resources = await _async_get_lovelace_resources(hass)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Unable to load Lovelace resources: %s", err)
        resources = None

    if resources is None:
        _LOGGER.debug(
            "Lovelace resources API unavailable, card must be added manually: %s",
            desired_url,
        )
        return False

    try:
        items: list[dict[str, Any]] = list(resources.async_items() or [])
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Unable to list Lovelace resources: %s", err)
        return False

    # Find existing resource for our card
    existing_resource = None
    for item in items:
        url = item.get(CONF_URL)
        if not isinstance(url, str):
            continue
        base = _url_base(url)
        if base == CARD_LEGACY_BASE_URL:
            existing_resource = item
            break

    # Update existing resource if needed
    if existing_resource is not None:
        if (
            existing_resource.get(CONF_URL) == desired_url
            and existing_resource.get(CONF_TYPE) == "module"
        ):
            _LOGGER.debug("Card resource is up to date: %s", desired_url)
            return True

        try:
            await resources.async_update_item(
                existing_resource[CONF_ID],
                {CONF_URL: desired_url, CONF_RESOURCE_TYPE_WS: "module"},
            )
            _LOGGER.info("Updated Lovelace resource: %s", desired_url)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Unable to update Lovelace resource: %s", err)
            return False
        return True

    # Create new resource
    try:
        await resources.async_create_item(
            {CONF_URL: desired_url, CONF_RESOURCE_TYPE_WS: "module"}
        )
        _LOGGER.info("Created Lovelace resource: %s", desired_url)
    except Exception as err:  # noqa: BLE001
        _LOGGER.debug("Unable to create Lovelace resource: %s", err)
        return False

    return True


def _async_component_loaded_listener(hass: HomeAssistant) -> Callable[[], None]:
    """Create component-loaded listener for late Lovelace startup."""

    @callback
    def _handle_component_loaded(event: Event) -> None:
        if event.data.get("component") not in ("lovelace", "frontend"):
            return
        _LOGGER.debug("Lovelace/frontend loaded, ensuring card resource")
        hass.async_create_task(_async_ensure_card_resource(hass))

    return hass.bus.async_listen(EVENT_COMPONENT_LOADED, _handle_component_loaded)


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Set up static card path and Lovelace resource.
    
    This function:
    1. Copies the bundled card to /config/www/
    2. Registers it as a Lovelace resource automatically
    3. Sets up listeners for late Lovelace startup
    """
    state: dict[str, Any] = hass.data.setdefault(FRONTEND_DATA_KEY, {})
    if state.get("setup_done"):
        _LOGGER.debug("Frontend already setup, skipping")
        return

    # Copy card to www folder
    await _async_sync_card_to_local_www(hass)
    
    # Register as Lovelace resource
    await _async_ensure_card_resource(hass)

    # Listen for late Lovelace startup
    if FRONTEND_DATA_COMPONENT_LISTENER not in hass.data:
        hass.data[FRONTEND_DATA_COMPONENT_LISTENER] = _async_component_loaded_listener(
            hass
        )

    state["setup_done"] = True
    _LOGGER.info("Entur alert card frontend setup complete")
