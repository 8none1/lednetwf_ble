"""Light platform for LEDnetWF BLE v2 integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .device import LEDNetWFDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light platform."""
    device: LEDNetWFDevice = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([LEDNetWFLight(device, entry)])


class LEDNetWFLight(LightEntity):
    """Representation of a LEDnetWF light."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name

    def __init__(self, device: LEDNetWFDevice, entry: ConfigEntry) -> None:
        """Initialize the light."""
        self._device = device
        self._entry = entry

        # Set up unique ID
        self._attr_unique_id = device.address

        # Determine supported color modes
        color_modes: set[ColorMode] = set()

        if device.has_rgb:
            color_modes.add(ColorMode.RGB)
        if device.has_color_temp:
            color_modes.add(ColorMode.COLOR_TEMP)

        # If no color modes, at least support brightness
        if not color_modes:
            color_modes.add(ColorMode.BRIGHTNESS)

        self._attr_supported_color_modes = color_modes

        # Set up features
        features = LightEntityFeature(0)
        if device.has_effects:
            features |= LightEntityFeature.EFFECT
        self._attr_supported_features = features

        # Color temp range
        if device.has_color_temp:
            self._attr_min_color_temp_kelvin = device.min_color_temp_kelvin
            self._attr_max_color_temp_kelvin = device.max_color_temp_kelvin

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
        # Build model string with effect type for easier debugging
        # e.g., "FillLight (ADDRESSABLE_0x53)" or "Ctrl_RGB_Symphony_new (SYMPHONY)"
        cap_name = self._device.capabilities.get("name", "Unknown")
        effect_type = self._device.effect_type
        model_str = f"{cap_name} ({effect_type.name})"

        # Product ID as hex for hardware version, e.g., "0x1D (29)"
        product_id = self._device.product_id
        if product_id is not None:
            hw_version = f"0x{product_id:02X} ({product_id})"
        else:
            hw_version = "Unknown"

        return DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
            name=self._device.name,
            manufacturer="LEDnetWF",
            model=model_str,
            sw_version=self._device.fw_version,
            hw_version=hw_version,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.is_on is not None

    @property
    def is_on(self) -> bool | None:
        """Return True if light is on."""
        return self._device.is_on

    @property
    def brightness(self) -> int | None:
        """Return the brightness."""
        return self._device.brightness

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return RGB color."""
        return self._device.rgb_color

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return color temperature in Kelvin."""
        return self._device.color_temp_kelvin

    @property
    def effect_list(self) -> list[str] | None:
        """Return list of effects."""
        effects = self._device.effect_list
        return effects if effects else None

    @property
    def effect(self) -> str | None:
        """Return current effect."""
        return self._device.effect

    @property
    def color_mode(self) -> ColorMode:
        """Return current color mode."""
        if self._device.effect:
            # When running an effect, report brightness mode
            return ColorMode.BRIGHTNESS
        if self._device.color_temp_kelvin and self._device.has_color_temp:
            return ColorMode.COLOR_TEMP
        if self._device.rgb_color and self._device.has_rgb:
            return ColorMode.RGB
        if ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
            return ColorMode.BRIGHTNESS
        # Fallback
        return next(iter(self._attr_supported_color_modes))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        _LOGGER.debug("turn_on called with kwargs: %s", kwargs)

        # Ensure light is on
        if not self._device.is_on:
            await self._device.turn_on()

        # Determine brightness
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            brightness = self._device.brightness or 255

        # Handle effect
        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            if effect:
                await self._device.set_effect(effect)
                return

        # Handle color temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            await self._device.set_color_temp(kwargs[ATTR_COLOR_TEMP_KELVIN], brightness)
            return

        # Handle RGB color
        if ATTR_RGB_COLOR in kwargs:
            await self._device.set_rgb_color(kwargs[ATTR_RGB_COLOR], brightness)
            return

        # Just brightness change - resend current color/mode
        # IMPORTANT: Check effect FIRST since it takes priority over stored color values
        if ATTR_BRIGHTNESS in kwargs:
            if self._device.effect:
                # Re-send effect with new brightness
                await self._device.set_effect(
                    self._device.effect,
                    speed=self._device.effect_speed,
                    brightness=brightness
                )
            elif self._device.color_temp_kelvin and self._device.has_color_temp:
                await self._device.set_color_temp(
                    self._device.color_temp_kelvin, brightness
                )
            elif self._device.rgb_color and self._device.has_rgb:
                await self._device.set_rgb_color(self._device.rgb_color, brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._device.turn_off()
