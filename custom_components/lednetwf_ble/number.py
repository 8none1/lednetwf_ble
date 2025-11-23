from __future__ import annotations
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
)
from .lednetwf import LEDNETWFInstance
from .const import DOMAIN
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers import device_registry
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    instance = hass.data[DOMAIN][config_entry.entry_id]
    await instance.update()
    async_add_entities([LEDNETWFSpeedSlider(instance, "Effect speed", config_entry.entry_id)])

class LEDNETWFSpeedSlider(NumberEntity):
    """LEDNETWF Slider for effect speed."""

    def __init__(self, lednetfInstance: LEDNETWFInstance, attr_name: str, entry_id: str) -> None:
        self._instance             = lednetfInstance
        self._attr_has_entity_name = True
        #self._attr_translation_key = attr_name # Can't get this to work
        self._attr_name            = attr_name
        self._attr_unique_id       = self._instance.mac
        
        # Register for state updates
        if not hasattr(self._instance, '_callbacks'):
            self._instance._callbacks = []
        self._instance._callbacks.append(self.speed_local_callback)

    @property
    def available(self):
        return self._instance.is_on is not None

    @property
    def name(self) -> str:
        return self._attr_name

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return self._attr_unique_id

    @property
    def native_value(self) -> int | None:
        # Always read from model to get latest state
        return self._instance._model_interface.effect_speed
    
    @callback
    def speed_local_callback(self) -> None:
        """Handle state updates from device."""
        _LOGGER.debug("Speed callback triggered, effect_speed=%s", 
                     self._instance._model_interface.effect_speed)
        self.schedule_update_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._instance.mac)},
            connections={(device_registry.CONNECTION_NETWORK_MAC,
                          self._instance.mac)},
        )

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self._instance.set_effect_speed(int(value))
