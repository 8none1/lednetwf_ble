"""LEDnetWF BLE v2 integration for Home Assistant."""
from __future__ import annotations

import logging

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME, Platform
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    CONF_PRODUCT_ID,
    CONF_DISCONNECT_DELAY,
    CONF_LED_COUNT,
    CONF_SEGMENTS,
    CONF_LED_TYPE,
    CONF_COLOR_ORDER,
    DEFAULT_DISCONNECT_DELAY,
    DEFAULT_LED_COUNT,
    DEFAULT_SEGMENTS,
    LedType,
    ColorOrder,
    get_device_capabilities,
)
from .device import LEDNetWFDevice
from . import protocol

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LEDnetWF BLE v2 from a config entry."""
    address = entry.data[CONF_MAC]
    name = entry.data.get(CONF_NAME, address)
    product_id = entry.data.get(CONF_PRODUCT_ID)
    disconnect_delay = entry.options.get(CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY)

    _LOGGER.debug(
        "Setting up LEDnetWF device: %s (%s), product_id=0x%02X",
        name,
        address,
        product_id or 0,
    )

    # Create the device instance
    device = LEDNetWFDevice(
        hass,
        address,
        name,
        product_id,
        disconnect_delay,
    )

    # Apply probed capabilities if available (from config flow probing)
    probed_caps = entry.data.get("probed_capabilities")
    if probed_caps:
        _LOGGER.debug("Applying probed capabilities: %s", probed_caps)
        device._capabilities.update(probed_caps)
        device._capabilities["needs_probing"] = False

    # Store LED settings from options in device state
    # These will be sent to the device when needed
    caps = get_device_capabilities(product_id)
    if caps.get("has_ic_config"):
        device._led_count = entry.options.get(CONF_LED_COUNT, DEFAULT_LED_COUNT)
        device._segments = entry.options.get(CONF_SEGMENTS, DEFAULT_SEGMENTS)
        device._led_type = entry.options.get(CONF_LED_TYPE, LedType.WS2812B.value)
        device._color_order = entry.options.get(CONF_COLOR_ORDER, ColorOrder.GRB.value)
        _LOGGER.debug(
            "Initialized LED settings: count=%d, segments=%d, type=%d, order=%d",
            device._led_count, device._segments, device._led_type, device._color_order
        )

    # For devices that don't report power state in advertisements (like IOTBT),
    # query state on startup to ensure proper availability
    # Source: protocol_docs/17_device_configuration.md - IOTBT uses DeviceState2 format
    if device.is_on is None and product_id == 0x00:
        _LOGGER.info(
            "Device %s (product_id=0x00) has no power state from advertisement, "
            "querying device state...", name
        )
        try:
            await device.query_state_and_wait(timeout=5.0)
            _LOGGER.debug("Initial state query result: is_on=%s", device.is_on)
        except Exception as ex:
            _LOGGER.warning("Failed to query initial state for %s: %s", name, ex)
            # Device will show as unavailable until first command or advertisement update

    # Store device instance
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = device

    # Register Bluetooth callback for advertisement updates
    @callback
    def _async_update_ble(
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle Bluetooth advertisement updates."""
        if service_info.manufacturer_data or service_info.service_data:
            device.update_from_advertisement(
                service_info.manufacturer_data,
                service_info.service_data,
            )

    entry.async_on_unload(
        async_register_callback(
            hass,
            _async_update_ble,
            BluetoothCallbackMatcher(address=address),
            BluetoothChange.ADVERTISEMENT,
        )
    )

    # Handle options updates
    entry.async_on_unload(entry.add_update_listener(async_options_updated))

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        device: LEDNetWFDevice = hass.data[DOMAIN].pop(entry.entry_id)
        await device.stop()

    return unload_ok


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    _LOGGER.debug("Options update triggered for entry %s", entry.entry_id)

    device: LEDNetWFDevice = hass.data[DOMAIN].get(entry.entry_id)
    if device is None:
        _LOGGER.warning("Device not found for options update")
        await hass.config_entries.async_reload(entry.entry_id)
        return

    # Update disconnect delay
    new_delay = entry.options.get(CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY)
    device._disconnect_delay = new_delay

    # Check if LED settings need to be applied
    product_id = entry.data.get(CONF_PRODUCT_ID)
    caps = get_device_capabilities(product_id)

    if caps.get("has_ic_config"):
        new_led_count = entry.options.get(CONF_LED_COUNT, DEFAULT_LED_COUNT)
        new_segments = entry.options.get(CONF_SEGMENTS, DEFAULT_SEGMENTS)
        new_led_type = entry.options.get(CONF_LED_TYPE, LedType.WS2812B.value)
        new_color_order = entry.options.get(CONF_COLOR_ORDER, ColorOrder.GRB.value)

        _LOGGER.debug(
            "LED settings comparison - Current: count=%s, segments=%s, type=%s, order=%s; "
            "New: count=%s, segments=%s, type=%s, order=%s",
            device._led_count, device._segments, device._led_type, device._color_order,
            new_led_count, new_segments, new_led_type, new_color_order
        )

        # Check if settings changed
        if (device._led_count != new_led_count or
            device._segments != new_segments or
            device._led_type != new_led_type or
            device._color_order != new_color_order):

            _LOGGER.info(
                "LED settings changed, applying: count=%d, segments=%d, type=%d, order=%d",
                new_led_count, new_segments, new_led_type, new_color_order
            )

            # Apply new settings to device
            success = await device.set_led_settings(
                new_led_count, new_led_type, new_color_order, new_segments
            )
            if success:
                # Update device's internal state to match new values
                device._led_count = new_led_count
                device._segments = new_segments
                device._led_type = new_led_type
                device._color_order = new_color_order
                _LOGGER.debug("LED settings applied and device state updated")
            else:
                _LOGGER.warning("Failed to apply LED settings to device")
        else:
            _LOGGER.debug("LED settings unchanged, no update needed")
