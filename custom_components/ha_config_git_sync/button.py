"""Button platform for HA Config Git Sync."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GitSyncCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up buttons."""
    coordinator: GitSyncCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GitSyncPushButton(coordinator, entry)])


class GitSyncPushButton(CoordinatorEntity, ButtonEntity):
    """Button to manually push config changes to git."""

    _attr_has_entity_name = True
    _attr_name = "Push to Git"
    _attr_icon = "mdi:source-branch-plus"

    def __init__(self, coordinator: GitSyncCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_push"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "HA Config Git Sync",
            "manufacturer": "Custom",
            "model": "Git Sync",
        }

    async def async_press(self) -> None:
        """Handle button press — push changes to git."""
        await self.coordinator.async_push()
