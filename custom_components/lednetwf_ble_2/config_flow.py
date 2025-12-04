"""Config flow for LEDnetWF BLE v2 integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from bleak_retry_connector import BleakNotFoundError

from .const import (
    DOMAIN,
    CONF_PRODUCT_ID,
    CONF_DISCONNECT_DELAY,
    CONF_LED_COUNT,
    CONF_LED_TYPE,
    CONF_COLOR_ORDER,
    DEFAULT_DISCONNECT_DELAY,
    DEFAULT_LED_COUNT,
    LedType,
    ColorOrder,
    is_supported_device,
    get_device_capabilities,
    needs_capability_probing,
)
from .device import LEDNetWFDevice
from . import protocol

_LOGGER = logging.getLogger(__name__)


def _is_valid_device_name(name: str) -> bool:
    """Check if device name matches supported patterns.

    Source: protocol_docs/02_ble_scanning_device_discovery.md
    Accepts: LEDnetWF*, IOTWF*, IOTB*
    """
    if not name:
        return False
    name_lower = name.lower()
    return (
        name_lower.startswith("lednetwf") or
        name_lower.startswith("iotwf") or
        name_lower.startswith("iotb")
    )


def _parse_discovery(discovery: BluetoothServiceInfoBleak) -> dict | None:
    """Parse discovery info and extract product ID."""
    name = discovery.name or ""

    # Check device name matches supported patterns
    if not _is_valid_device_name(name):
        return None

    # Parse manufacturer data
    manu_data = protocol.parse_manufacturer_data(discovery.manufacturer_data)
    if not manu_data:
        return None

    product_id = manu_data.get("product_id")
    if not is_supported_device(product_id):
        _LOGGER.debug("Device %s (product 0x%02X) not supported", name, product_id or 0)
        return None

    return {
        "address": discovery.address,
        "name": name,
        "product_id": product_id,
        "fw_version": manu_data.get("fw_version"),
        "rssi": discovery.rssi,
    }


class LEDNetWFConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow for LEDnetWF BLE v2."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: dict | None = None
        self._discovered_devices: dict[str, dict] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle Bluetooth discovery."""
        _LOGGER.debug("Bluetooth discovery: %s", discovery_info.address)

        parsed = _parse_discovery(discovery_info)
        if not parsed:
            return self.async_abort(reason="not_supported")

        address = parsed["address"]
        await self.async_set_unique_id(format_mac(address))
        self._abort_if_unique_id_configured()

        self._discovery_info = parsed
        self.context["title_placeholders"] = {"name": parsed["name"]}

        return await self.async_step_confirm()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle user-initiated setup (manual selection)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_MAC]
            if address in self._discovered_devices:
                self._discovery_info = self._discovered_devices[address]
                await self.async_set_unique_id(format_mac(address))
                self._abort_if_unique_id_configured()
                return await self.async_step_confirm()

        # Scan for devices
        self._discovered_devices = {}
        configured_addresses = {
            entry.unique_id for entry in self._async_current_entries()
        }

        for discovery in async_discovered_service_info(self.hass):
            parsed = _parse_discovery(discovery)
            if parsed and format_mac(parsed["address"]) not in configured_addresses:
                self._discovered_devices[parsed["address"]] = parsed

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        # Build device selection
        device_options = {
            addr: f"{info['name']} ({addr})"
            for addr, info in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_MAC): vol.In(device_options)}
            ),
            errors=errors,
        )

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle confirmation step with device validation."""
        errors: dict[str, str] = {}

        if self._discovery_info is None:
            return self.async_abort(reason="no_discovery_info")

        # First visit - just show the form, don't connect yet
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({
                    vol.Required("test_device", default=True): bool,
                }),
                description_placeholders={"name": self._discovery_info["name"]},
            )

        # User wants to skip testing and just add
        if not user_input.get("test_device"):
            return await self.async_step_options()

        # User wants to test - flash the device and probe if needed
        try:
            product_id = self._discovery_info.get("product_id")
            device = LEDNetWFDevice(
                self.hass,
                self._discovery_info["address"],
                self._discovery_info["name"],
                product_id,
            )

            # If device needs capability probing (unknown product ID), probe first
            if needs_capability_probing(product_id):
                _LOGGER.info(
                    "Unknown product ID 0x%02X - probing capabilities",
                    product_id or 0
                )
                probed_caps = await device.probe_capabilities()
                # Store probed capabilities for later use
                self._discovery_info["probed_capabilities"] = probed_caps
                _LOGGER.info("Probed capabilities: %s", probed_caps)

            # Flash the device 3 times to confirm it's the right one
            for _ in range(3):
                await device.turn_on()
                await asyncio.sleep(0.5)
                await device.turn_off()
                await asyncio.sleep(0.5)

            # Query LED settings if device supports it
            caps = device.capabilities  # Use device's capabilities (may be probed)
            if caps.get("has_ic_config"):
                await device.query_led_settings()
                await asyncio.sleep(0.5)

            await device.stop()

        except BleakNotFoundError:
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({vol.Required("test_device", default=True): bool}),
                errors=errors,
                description_placeholders={"name": self._discovery_info["name"]},
            )
        except Exception as ex:
            _LOGGER.exception("Validation error: %s", ex)
            errors["base"] = "unknown"
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({vol.Required("test_device", default=True): bool}),
                errors=errors,
                description_placeholders={"name": self._discovery_info["name"]},
            )

        # Device flashed successfully - proceed to options
        return await self.async_step_options()

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle LED configuration options."""
        if user_input is not None:
            return self._create_entry(user_input)

        caps = get_device_capabilities(self._discovery_info.get("product_id"))

        # Build options schema based on device capabilities
        schema_dict: dict[vol.Marker, Any] = {
            vol.Optional(
                CONF_DISCONNECT_DELAY,
                default=DEFAULT_DISCONNECT_DELAY,
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
        }

        # Only show LED config for addressable strips
        if caps.get("has_ic_config"):
            schema_dict.update({
                vol.Optional(CONF_LED_COUNT, default=DEFAULT_LED_COUNT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=1000)
                ),
                vol.Optional(CONF_LED_TYPE, default=LedType.WS2812B.name): vol.In(
                    [t.name for t in LedType]
                ),
                vol.Optional(CONF_COLOR_ORDER, default=ColorOrder.GRB.name): vol.In(
                    [o.name for o in ColorOrder]
                ),
            })

        return self.async_show_form(
            step_id="options",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={"name": self._discovery_info["name"]},
        )

    def _create_entry(self, options: dict[str, Any]) -> FlowResult:
        """Create the config entry."""
        data = {
            CONF_MAC: self._discovery_info["address"],
            CONF_NAME: self._discovery_info["name"],
            CONF_PRODUCT_ID: self._discovery_info.get("product_id"),
        }

        # Store probed capabilities if available
        if "probed_capabilities" in self._discovery_info:
            data["probed_capabilities"] = self._discovery_info["probed_capabilities"]

        # Process options
        processed_options = {
            CONF_DISCONNECT_DELAY: options.get(
                CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY
            ),
        }

        if CONF_LED_COUNT in options:
            processed_options[CONF_LED_COUNT] = options[CONF_LED_COUNT]
        if CONF_LED_TYPE in options:
            processed_options[CONF_LED_TYPE] = LedType[options[CONF_LED_TYPE]].value
        if CONF_COLOR_ORDER in options:
            processed_options[CONF_COLOR_ORDER] = ColorOrder[options[CONF_COLOR_ORDER]].value

        return self.async_create_entry(
            title=self._discovery_info["name"],
            data=data,
            options=processed_options,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options."""
        if user_input is not None:
            return self._save_options(user_input)

        product_id = self._config_entry.data.get(CONF_PRODUCT_ID)
        caps = get_device_capabilities(product_id)
        options = self._config_entry.options

        schema_dict: dict[vol.Marker, Any] = {
            vol.Optional(
                CONF_DISCONNECT_DELAY,
                default=options.get(CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
        }

        if caps.get("has_ic_config"):
            current_led_type = options.get(CONF_LED_TYPE, LedType.WS2812B.value)
            current_color_order = options.get(CONF_COLOR_ORDER, ColorOrder.GRB.value)

            # Convert values back to names for display
            led_type_name = next(
                (t.name for t in LedType if t.value == current_led_type),
                LedType.WS2812B.name,
            )
            color_order_name = next(
                (o.name for o in ColorOrder if o.value == current_color_order),
                ColorOrder.GRB.name,
            )

            schema_dict.update({
                vol.Optional(
                    CONF_LED_COUNT,
                    default=options.get(CONF_LED_COUNT, DEFAULT_LED_COUNT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
                vol.Optional(CONF_LED_TYPE, default=led_type_name): vol.In(
                    [t.name for t in LedType]
                ),
                vol.Optional(CONF_COLOR_ORDER, default=color_order_name): vol.In(
                    [o.name for o in ColorOrder]
                ),
            })

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_dict),
        )

    def _save_options(self, user_input: dict[str, Any]) -> FlowResult:
        """Save options."""
        new_options = {
            CONF_DISCONNECT_DELAY: user_input.get(
                CONF_DISCONNECT_DELAY, DEFAULT_DISCONNECT_DELAY
            ),
        }

        if CONF_LED_COUNT in user_input:
            new_options[CONF_LED_COUNT] = user_input[CONF_LED_COUNT]
        if CONF_LED_TYPE in user_input:
            new_options[CONF_LED_TYPE] = LedType[user_input[CONF_LED_TYPE]].value
        if CONF_COLOR_ORDER in user_input:
            new_options[CONF_COLOR_ORDER] = ColorOrder[user_input[CONF_COLOR_ORDER]].value

        return self.async_create_entry(title="", data=new_options)
