"""Number platform for LEDnetWF BLE v2 integration."""
from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_EFFECT_SPEED
from .device import LEDNetWFDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    device: LEDNetWFDevice = hass.data[DOMAIN][entry.entry_id]

    entities: list[NumberEntity] = []

    # Only add effect speed if device supports effects
    if device.has_effects:
        entities.append(LEDNetWFEffectSpeed(device))

    if entities:
        async_add_entities(entities)


class LEDNetWFEffectSpeed(NumberEntity):
    """Effect speed control for LEDnetWF devices.

    This can serve as "speed" for effects or "sensitivity" for sound-reactive modes.
    """

    _attr_has_entity_name = True
    _attr_name = "Effect Speed"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:speedometer"

    def __init__(self, device: LEDNetWFDevice) -> None:
        """Initialize the number entity."""
        self._device = device
        self._attr_unique_id = f"{device.address}_effect_speed"

        # Register callback for state updates
        device.register_callback(self._handle_state_update)

    async def async_will_remove_from_hass(self) -> None:
        """Handle entity removal."""
        self._device.unregister_callback(self._handle_state_update)

    @callback
    def _handle_state_update(self) -> None:
        """Handle state updates from the device."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.is_on is not None

    @property
    def native_value(self) -> float:
        """Return the current effect speed."""
        return self._device.effect_speed

    async def async_set_native_value(self, value: float) -> None:
        """Set the effect speed."""
        await self._device.set_effect_speed(int(value))
