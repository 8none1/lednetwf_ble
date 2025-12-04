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
    DEFAULT_DISCONNECT_DELAY,
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
        if service_info.manufacturer_data:
            device.update_from_advertisement(service_info.manufacturer_data)

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
    # Reload the entry to apply new options
    await hass.config_entries.async_reload(entry.entry_id)
