"""The Entur Situation Exchange integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import EnturSXApiClient
from .const import DOMAIN, normalize_language
from .coordinator import EnturSXDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Entur Situation Exchange from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Create API client - merge data and options for backward compatibility
    config_data = {**entry.data, **entry.options}
    
    # Use HA's language setting
    lang = normalize_language(hass.config.language)
    
    api = EnturSXApiClient(
        operator=config_data.get("operator"),
        lines=config_data.get("lines_to_check", []),
        lang=lang,
    )

    # Create coordinator
    coordinator = EnturSXDataUpdateCoordinator(hass, api)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady("Failed to fetch initial data from Entur API")

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options flow
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
