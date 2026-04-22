"""Switch platform for HA Config Git Sync."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GitSyncCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switches."""
    coordinator: GitSyncCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GitSyncAutoPushSwitch(coordinator, entry),
    ])


class GitSyncAutoPushSwitch(CoordinatorEntity, RestoreEntity, SwitchEntity):
    """Switch to enable/disable automatic push of local changes."""

    _attr_has_entity_name = True
    _attr_name = "Auto-sync Local Changes"
    _attr_icon = "mdi:source-branch-sync"

    def __init__(self, coordinator: GitSyncCoordinator, entry: ConfigEntry) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_auto_push"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "HA Config Git Sync",
            "manufacturer": "ongas",
            "model": "Git Sync",
        }

    async def async_added_to_hass(self) -> None:
        """Restore previous state on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self.coordinator._auto_push_enabled = last_state.state == "on"

    @property
    def is_on(self) -> bool:
        """Return True if auto-push is enabled."""
        return self.coordinator._auto_push_enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable auto-push."""
        self.coordinator._auto_push_enabled = True
        self.coordinator.async_set_updated_data(self.coordinator._build_data())

    async def async_turn_off(self, **kwargs) -> None:
        """Disable auto-push."""
        self.coordinator._auto_push_enabled = False
        self.coordinator.async_set_updated_data(self.coordinator._build_data())
