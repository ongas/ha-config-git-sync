"""Binary sensor platform for HA Config Git Sync."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_PENDING
from .coordinator import GitSyncCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up binary sensors."""
    coordinator: GitSyncCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([GitSyncPendingChangesSensor(coordinator, entry)])


class GitSyncPendingChangesSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor that is ON when there are uncommitted config changes."""

    _attr_has_entity_name = True
    _attr_name = "Pending Changes"
    _attr_device_class = BinarySensorDeviceClass.UPDATE

    def __init__(self, coordinator: GitSyncCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_pending"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "HA Config Git Sync",
            "manufacturer": "Custom",
            "model": "Git Sync",
        }

    @property
    def is_on(self) -> bool:
        """Return True if there are pending changes."""
        if self.coordinator.data:
            return self.coordinator.data.get("status") == STATUS_PENDING
        return False

    @property
    def icon(self) -> str:
        """Return icon based on state."""
        return "mdi:source-branch-check" if self.is_on else "mdi:check-circle"

    @property
    def extra_state_attributes(self) -> dict:
        """Return changed file count."""
        if not self.coordinator.data:
            return {}
        return {
            "changed_count": self.coordinator.data.get("changed_count", 0),
        }
