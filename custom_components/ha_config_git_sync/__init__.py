"""HA Config Git Sync integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant

from .const import ACTION_DISMISS, ACTION_PUSH, DOMAIN, PLATFORMS
from .coordinator import GitSyncCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Config Git Sync from a config entry."""
    coordinator = GitSyncCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Listen for actionable notification responses
    async def handle_notification_action(event: Event) -> None:
        """Handle mobile_app notification action."""
        action = event.data.get("action")
        if action in (ACTION_PUSH, ACTION_DISMISS):
            await coordinator.async_handle_action(action)

    entry.async_on_unload(
        hass.bus.async_listen(
            "mobile_app_notification_action", handle_notification_action
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Handle options updates
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
