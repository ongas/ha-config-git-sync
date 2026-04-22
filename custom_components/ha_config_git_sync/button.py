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
    async_add_entities([
        GitSyncPushButton(coordinator, entry),
        GitSyncPullButton(coordinator, entry),
        GitSyncUndoButton(coordinator, entry),
    ])


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
            "manufacturer": "ongas",
            "model": "Git Sync",
        }

    async def async_press(self) -> None:
        """Handle button press — push changes to git."""
        await self.coordinator.async_push()


class GitSyncPullButton(CoordinatorEntity, ButtonEntity):
    """Button to manually pull latest config from git."""

    _attr_has_entity_name = True
    _attr_name = "Pull from Git"
    _attr_icon = "mdi:source-branch-pull"

    def __init__(self, coordinator: GitSyncCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_pull"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "HA Config Git Sync",
            "manufacturer": "ongas",
            "model": "Git Sync",
        }

    async def async_press(self) -> None:
        """Handle button press — pull changes from git."""
        await self.coordinator.async_pull()


class GitSyncUndoButton(CoordinatorEntity, ButtonEntity):
    """Button to undo/redo the most recent git commit."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GitSyncCoordinator, entry: ConfigEntry) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_undo"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "HA Config Git Sync",
            "manufacturer": "ongas",
            "model": "Git Sync",
        }

    @property
    def _is_redo(self) -> bool:
        """Return True when the last action was an undo (so next press is redo)."""
        return bool(
            self.coordinator.data and self.coordinator.data.get("is_revert_head")
        )

    @property
    def name(self) -> str:
        """Return dynamic name based on undo/redo state."""
        return "Redo Last Change" if self._is_redo else "Undo Last Change"

    @property
    def icon(self) -> str:
        """Return dynamic icon based on undo/redo state."""
        return "mdi:redo" if self._is_redo else "mdi:undo"

    async def async_press(self) -> None:
        """Handle button press — revert the most recent commit."""
        await self.coordinator.async_undo()
