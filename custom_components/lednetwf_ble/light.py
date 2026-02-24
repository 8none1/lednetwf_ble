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

    entities: list[LightEntity] = [LEDNetWFLight(device, entry)]

    # Add background light entity for devices that support it (0x56, 0x80)
    if device.has_bg_color:
        _LOGGER.info(
            "Adding background light entity for %s (product_id=0x%02X)",
            device.name,
            device.product_id or 0,
        )
        entities.append(LEDNetWFBackgroundLight(device, entry))

    async_add_entities(entities)


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
        # Model string: capability name from product ID mapping
        cap_name = self._device.capabilities.get("name", "Unknown")
        model_str = cap_name

        # Software version: app-style firmware string
        # Format: "{product_id:02X}.{firmware_ver:04d}.{ble_version:02d},V{led_version}"
        # Example: "62.0008.05,V3" matching the LEDnetWF Android app display
        sw_version = self._device.app_firmware_version

        return DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
            name=self._device.name,
            manufacturer="LEDnetWF",
            model=model_str,
            sw_version=sw_version,
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
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes for diagnostics."""
        attrs: dict[str, Any] = {}

        # Product ID (hex format for easy lookup in docs)
        if self._device.product_id is not None:
            attrs["product_id"] = f"0x{self._device.product_id:02X}"

        # Effect type (command format used by device)
        attrs["effect_type"] = self._device.effect_type.name

        # Effect speed (when effect is active)
        if self._device.effect:
            attrs["effect_speed"] = self._device.effect_speed

        # LED configuration (for addressable strips)
        if self._device.led_count:
            attrs["led_count"] = self._device.led_count
        if self._device.segments:
            attrs["segments"] = self._device.segments
        if self._device.total_leds:
            attrs["total_leds"] = self._device.total_leds

        # Capabilities (useful for debugging)
        attrs["has_rgb"] = self._device.has_rgb
        attrs["has_color_temp"] = self._device.has_color_temp
        if self._device.has_builtin_mic:
            attrs["has_builtin_mic"] = True

        # Device info from service data (protocol_docs/17_device_configuration.md)
        if self._device.ble_version is not None:
            attrs["ble_version"] = self._device.ble_version
        if self._device.led_version is not None:
            attrs["led_version"] = self._device.led_version
        if self._device.firmware_ver is not None:
            attrs["firmware_ver"] = self._device.firmware_ver
        if self._device.firmware_flag is not None:
            attrs["firmware_flag"] = f"0x{self._device.firmware_flag:02X}"

        # Data-driven capabilities (from JSON database)
        json_caps = self._device.json_capabilities
        if json_caps:
            attrs["json_device_version"] = self._device.device_version
            attrs["json_state_protocol"] = json_caps.get_state_protocol(
                self._device.device_version
            )
            # Show which effect functions are supported
            attrs["supports_scene_data_v2"] = self._device.supports_datadriven_function(
                "scene_data_v2"
            )

        return attrs

    @property
    def color_mode(self) -> ColorMode:
        """Return current color mode."""
        if self._device.effect:
            # For Settled Mode effects, allow RGB color changes
            # so user can adjust foreground color while staying in the effect
            if self._device.is_in_settled_effect():
                return ColorMode.RGB
            # For other effects, report brightness mode (no color picker)
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
            elif self._device.has_dim:
                await self._device.set_brightness(brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self._device.turn_off()


class LEDNetWFBackgroundLight(LightEntity):
    """Background light entity for devices that support background color (0x56, 0x80).

    This entity allows setting the background color for static effects (2-10).
    The background color is only visible when running a compatible static effect.
    """

    _attr_has_entity_name = True
    _attr_name = "Background"
    _attr_icon = "mdi:layers-triple"

    def __init__(self, device: LEDNetWFDevice, entry: ConfigEntry) -> None:
        """Initialize the background light entity."""
        self._device = device
        self._entry = entry

        # Set up unique ID
        self._attr_unique_id = f"{device.address}_background"

        # Background light only supports RGB
        self._attr_supported_color_modes = {ColorMode.RGB}
        self._attr_color_mode = ColorMode.RGB

        # No effects for background light
        self._attr_supported_features = LightEntityFeature(0)

        # Track independent on/off state (brightness 0 = off)
        self._is_on = True

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
        """Return device info - links to same device as main light."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.address)},
            # Don't set name here - it will link to existing device with same identifiers
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available.

        Background light is only available when running a static effect (2-10).
        Not available for: color mode, solid color, dynamic effects, or sound reactive.
        """
        if self._device.is_on is None:
            return False

        # Must be running a static effect
        return self._device.is_bg_color_available()

    @property
    def is_on(self) -> bool | None:
        """Return True if background light is on.

        Background light has its own on/off state, independent of brightness value.
        """
        return self._device.is_on and self._is_on

    @property
    def brightness(self) -> int | None:
        """Return the background brightness."""
        return self._device.bg_brightness

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return background RGB color."""
        return self._device.bg_rgb_color

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the background light on."""
        _LOGGER.debug("Background light turn_on called with kwargs: %s", kwargs)

        # Ensure main light is on
        if not self._device.is_on:
            await self._device.turn_on()

        # Mark as on
        self._is_on = True

        # Determine brightness
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness is None:
            # Preserve current brightness if reasonable
            if self._device.bg_brightness >= 10:
                brightness = self._device.bg_brightness
            else:
                # Default to foreground brightness (user expectation: BG matches FG)
                brightness = self._device.brightness or 255

        # Handle RGB color
        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
        else:
            # Use current background color or default to white
            rgb = self._device.bg_rgb_color or (255, 255, 255)

        await self._device.set_bg_color(rgb, brightness)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the background light off.

        Sets brightness to 0 to hide the background color.
        """
        _LOGGER.debug("Background light turn_off called")

        # Mark as off
        self._is_on = False

        # Set background to black (brightness 0)
        rgb = self._device.bg_rgb_color or (255, 255, 255)
        await self._device.set_bg_color(rgb, 0)
