"""Sensor platform for HA Config Git Sync."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, STATUS_CLEAN, STATUS_ERROR, STATUS_PENDING, STATUS_PUSHING
from .coordinator import GitSyncCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors."""
    coordinator: GitSyncCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        GitSyncStatusSensor(coordinator, entry),
        GitSyncLastActivitySensor(coordinator, entry),
    ])


class GitSyncStatusSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing git sync status and changed files."""

    _attr_has_entity_name = True
    _attr_name = "Status"

    def __init__(self, coordinator: GitSyncCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "HA Config Git Sync",
            "model": "Git Sync",
        }

    @property
    def native_value(self) -> str | None:
        """Return the current sync status."""
        if self.coordinator.data:
            return self.coordinator.data.get("status", STATUS_CLEAN)
        return STATUS_CLEAN

    @property
    def icon(self) -> str:
        """Return icon based on status."""
        status = self.native_value
        icons = {
            STATUS_CLEAN: "mdi:check-circle",
            STATUS_PENDING: "mdi:source-branch-sync",
            STATUS_PUSHING: "mdi:progress-upload",
            STATUS_ERROR: "mdi:alert-circle",
        }
        return icons.get(status, "mdi:git")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        if not self.coordinator.data:
            return {}
        data = self.coordinator.data
        return {
            "changed_files": data.get("changed_files", []),
            "changed_count": data.get("changed_count", 0),
            "last_push": data.get("last_push"),
            "last_push_commit": data.get("last_push_commit"),
            "last_check": data.get("last_check"),
            "last_error": data.get("last_error"),
        }


class GitSyncLastActivitySensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the last activity performed by the integration."""

    _attr_has_entity_name = True
    _attr_name = "Last Activity"

    def __init__(self, coordinator: GitSyncCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_activity"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "HA Config Git Sync",
            "model": "Git Sync",
        }

    @property
    def native_value(self) -> str | None:
        """Return the last activity description."""
        if self.coordinator.data:
            return self.coordinator.data.get("last_activity")
        return None

    @property
    def icon(self) -> str:
        """Return icon."""
        return "mdi:history"
