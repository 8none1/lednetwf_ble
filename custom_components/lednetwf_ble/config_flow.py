import logging
import asyncio
import importlib
import pkgutil
import voluptuous as vol

from typing import Any

from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_MAC
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac
import homeassistant.helpers.config_validation as cv
from bluetooth_data_tools import human_readable_name
from bleak_retry_connector import BleakNotFoundError, BleakOutOfConnectionSlotsError
from asyncio import TimeoutError
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_DELAY,
    CONF_LEDCOUNT,
    CONF_LEDTYPE,
    CONF_COLORORDER,
    CONF_MODEL,
    CONF_SEGMENTS,
    CONF_IGNORE_NOTIFICATIONS,
    LedTypes_StripLight,
    LedTypes_RingLight,
    ColorOrdering,
)
from .lednetwf import LEDNETWFInstance

_LOGGER = logging.getLogger(__name__)

# Dynamically load supported models
SUPPORTED_MODELS = []
package = __package__
models_path = __file__.replace(__file__.split("/")[-1], "models")

for _, module_name, _ in pkgutil.iter_modules([models_path]):
    if module_name.startswith("model_0x"):
        module = importlib.import_module(f"{package}.models.{module_name}")
        if hasattr(module, "SUPPORTED_MODELS"):
            SUPPORTED_MODELS.extend(module.SUPPORTED_MODELS)


# Device name prefixes that indicate potentially supported devices
SUPPORTED_NAME_PREFIXES = ["lednetwf", "iotb"]


def _has_supported_name(device_name: str) -> bool:
    """Check if device name matches any supported prefix."""
    name_lower = device_name.lower()
    return any(name_lower.startswith(prefix) for prefix in SUPPORTED_NAME_PREFIXES)


class DeviceData:
    def __init__(self, discovery: BluetoothServiceInfoBleak):
        self._discovery = discovery
        self.address = discovery.address
        self.unique_id = format_mac(self.address)
        self.logical_name = discovery.name
        self.rssi = discovery.rssi

        # Log service data for debugging - only for our devices
        if _has_supported_name(self.logical_name):
            if discovery.service_data:
                _LOGGER.debug(f"[{self.logical_name}] Service data found:")
                for uuid, data in discovery.service_data.items():
                    data_hex = ' '.join(f'{byte:02X}' for byte in data) if isinstance(data, (bytes, bytearray)) else str(data)
                    _LOGGER.debug(f"  UUID: {uuid}, Data: {data_hex}")
            else:
                _LOGGER.debug(f"[{self.logical_name}] No service data available")

        manu_data = next(iter(discovery.manufacturer_data.values()), None)
        self.fw_major = manu_data[0] if isinstance(manu_data, (bytes, bytearray)) and len(manu_data) > 0 else None

    def is_supported(self) -> bool:
        return (
            _has_supported_name(self.logical_name)
            and self.fw_major is not None
            and self.fw_major in SUPPORTED_MODELS
        )

    def human_name(self) -> str:
        return human_readable_name(None, self.logical_name, self.address)

    def display_name(self) -> str:
        return f"{self.human_name()} ({self.address})"


@config_entries.HANDLERS.register(DOMAIN)
class LEDNETWFFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._discovered_devices: dict[str, DeviceData] = {}
        self._selected: DeviceData | None = None
        self._instance: LEDNETWFInstance | None = None
        self._initial_discovery: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        _LOGGER.debug("[BT] Received Bluetooth discovery for %s", discovery_info.address)
        # await self.async_set_unique_id(discovery_info.address.lower())
        # self._abort_if_unique_id_configured()
        self._initial_discovery = discovery_info
        device = DeviceData(discovery_info)
        await self.async_set_unique_id(device.unique_id)
        self.context["title_placeholders"] = {"name": device.human_name()}

        if device.is_supported():
            if device.unique_id not in self._discovered_devices:
                self._discovered_devices[device.unique_id] = device
                _LOGGER.debug("[BT] Added to discovered cache: %s", device.unique_id)

        return await self.async_step_user()


    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        _LOGGER.debug("[USER] Entered async_step_user with input: %s", user_input)

        configured_ids = self._get_configured_ids()
        _LOGGER.debug("[USER] Already configured device IDs: %s", configured_ids)

        # Refresh discovery cache
        for discovery in async_discovered_service_info(self.hass):
            mac = format_mac(discovery.address)

            if mac in configured_ids or mac in self._discovered_devices:
                continue

            try:
                device = DeviceData(discovery)
                if device.is_supported():
                    self._discovered_devices[mac] = device
                    _LOGGER.debug("[USER] Added device: %s (%s)", device.display_name(), f"0x{device.fw_major:02X}")
            except Exception as e:
                _LOGGER.warning("[USER] Failed to parse discovery %s: %s", mac, e)

        # Limit UI to only the device that triggered the flow
        if self._initial_discovery:
            selected_mac = format_mac(self._initial_discovery.address)
            selected_device = self._discovered_devices.get(selected_mac)

            if not selected_device or selected_mac in configured_ids:
                _LOGGER.warning("[USER] Initial discovery device missing or already configured: %s", selected_mac)
                return self.async_abort(reason="device_disappeared")

            mac_dict = {selected_mac: selected_device.display_name()}
        else:
            # Fallback: show all devices if not launched via bluetooth
            mac_dict = {
                addr: dev.display_name()
                for addr, dev in sorted(self._discovered_devices.items(), key=lambda item: item[1].rssi or -999, reverse=True)
                if addr not in configured_ids
            }

        if not mac_dict:
            _LOGGER.warning("[USER] No supported unconfigured devices found")
            return self.async_abort(reason="no_devices_found")

        if user_input:
            mac = user_input[CONF_MAC]
            self._selected = self._discovered_devices.get(mac)
            if self._selected:
                _LOGGER.debug("[USER] Selected device: %s", self._selected.display_name())
                return await self.async_step_validate()
            else:
                _LOGGER.warning("[USER] Selected MAC not in device list: %s", mac)
                return self.async_abort(reason="device_disappeared")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_MAC): vol.In(mac_dict)}),
        )

    def _get_configured_ids(self) -> set[str]:
        return {entry.unique_id for entry in self.hass.config_entries.async_entries(DOMAIN)}

    async def async_step_validate(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        _LOGGER.debug("[VALIDATE] Entered async_step_validate with input: %s", user_input)

        if self._selected is None:
            _LOGGER.error("[VALIDATE] No device selected at validation step")
            return self.async_abort(reason="no_selection")

        try:
            if not self._instance:
                _LOGGER.debug("[VALIDATE] Instantiating device before prompt")
                data = {
                    CONF_MAC:   self._selected.address,
                    CONF_NAME:  self._selected.human_name(),
                    CONF_DELAY: 120,
                    CONF_MODEL: self._selected.fw_major,
                }
                self._instance = LEDNETWFInstance(self._selected.address, self.hass, data)
                await self._instance.update()
                await self._instance.send_initial_packets()
                await self._instance._write(self._instance._model_interface.GET_LED_SETTINGS_PACKET)
                _LOGGER.debug("[VALIDATE] Device instantiated and initial packets sent")
                _LOGGER.debug("[VALIDATE] Device model interface: %s", self._instance._model_interface)
                _LOGGER.debug("[VALIDATE] LED Count: %s, Chip Type: %s, Color Order: %s, Segments: %s",
                              getattr(self._instance._model_interface, 'led_count', 'Unknown'),
                              getattr(self._instance._model_interface, 'chip_type', 'Unknown'),
                              getattr(self._instance._model_interface, 'color_order', 'Unknown'),
                              getattr(self._instance._model_interface, 'segments', 'Unknown'))

            if user_input:
                if user_input.get("flicker"):
                    self._abort_if_unique_id_configured()
                    return self._create_entry()

            for _ in range(3):
                await self._instance.turn_on()
                await asyncio.sleep(1)
                await self._instance.turn_off()
                await asyncio.sleep(1)
            
            _LOGGER.debug("[VALIDATE AFTER FLASH] LED Count: %s, Chip Type: %s, Color Order: %s, Segments: %s",
                getattr(self._instance._model_interface, 'led_count', 'Unknown'),
                getattr(self._instance._model_interface, 'chip_type', 'Unknown'),
                getattr(self._instance._model_interface, 'color_order', 'Unknown'),
                getattr(self._instance._model_interface, 'segments', 'Unknown'))

        except BleakOutOfConnectionSlotsError as e:
            _LOGGER.error("[VALIDATE] Device unreachable or out of connection slots: %s", e, exc_info=True)
            return self.async_show_form(
                step_id="validate",
                data_schema=vol.Schema({vol.Required("retry"): bool}),
                errors={"base": "device_unreachable"},
            )

        except (TimeoutError, BleakNotFoundError) as e:
            _LOGGER.error("[VALIDATE] Connection failed: %s", e, exc_info=True)
            return self.async_show_form(
                step_id="validate",
                data_schema=vol.Schema({vol.Required("retry"): bool}),
                errors={"base": "cannot_connect"},
            )

        except ConfigEntryNotReady as e:
            _LOGGER.error("[VALIDATE] Device not ready: %s", e, exc_info=True)
            return self.async_show_form(
                step_id="validate",
                data_schema=vol.Schema({vol.Required("retry"): bool}),
                errors={"base": "device_not_ready"},
            )

        except Exception as e:
            _LOGGER.error("[VALIDATE] Unexpected error: %s", e, exc_info=True)
            return self.async_show_form(
                step_id="validate",
                data_schema=vol.Schema({vol.Required("retry"): bool}),
                errors={"base": "unknown"},
            )

        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema({vol.Required("flicker"): bool}),
            description_placeholders={"device": self._selected.display_name()},
        )


    def _create_entry(self) -> FlowResult:
        # Let's see if those stored values are available
        led_count = getattr(self._instance._model_interface, 'led_count', 64)
        if getattr(self._instance, "_model", None) in (0x56, 0x80):
            chip_type = LedTypes_RingLight.WS2812B
        else:
            chip_type = LedTypes_StripLight.WS2812B
        color_order   = getattr(self._instance._model_interface, 'color_order', ColorOrdering.GRB) #"GRB")
        segments      = getattr(self._instance._model_interface, 'segments', 1)

        _LOGGER.debug("[CREATE] LED Count: %s, Chip Type: %s, Color Order: %s, Segments: %s", led_count, chip_type, color_order, segments)

        data = {
            CONF_MAC: self._selected.address,
            CONF_NAME: self._selected.human_name(),
            CONF_DELAY: 120,
            CONF_MODEL: self._selected.fw_major,
        }
        options = {
            CONF_LEDCOUNT: led_count,
            CONF_LEDTYPE: chip_type,
            CONF_COLORORDER: color_order,
            CONF_SEGMENTS: segments,
        }

        _LOGGER.debug("[CREATE] Creating config entry with data: %s and options: %s", data, options)

        return self.async_create_entry(title=self._selected.human_name(), data=data, options=options)

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry):
        return OptionsFlowHandler(entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._data = config_entry.data
        self._options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        model = self._data.get(CONF_MODEL)
        # TODO: Look up the strip light models more dynamically, not hard coded
        led_types = LedTypes_StripLight if model in (0x56, 0x80) else LedTypes_RingLight
        # led_types_list = list(led_types)

        # if not led_types_list:
        #     _LOGGER.error("[OPTIONS] No LED types defined for model: %s", model)
        #     return self.async_abort(reason="unsupported_model")

        _LOGGER.debug(f"[OPTIONS] Current model: 0x{model:02X}")
        _LOGGER.debug("[OPTIONS] Options before update: %s", self._options)

        if user_input:
            _LOGGER.debug("[OPTIONS] Received user input: %s", user_input)
            chip = led_types[user_input[CONF_LEDTYPE]]
            order = ColorOrdering[user_input[CONF_COLORORDER]]
            _LOGGER.debug("[OPTIONS] Resolved chip: %s, order: %s", chip, order)
            # self._options.update({
            #     CONF_DELAY: user_input.get(CONF_DELAY, 120),
            #     CONF_LEDCOUNT: user_input[CONF_LEDCOUNT],
            #     CONF_LEDTYPE: chip,
            #     CONF_COLORORDER: order,
            #     CONF_SEGMENTS: user_input.get(CONF_SEGMENTS, 1),
            #     CONF_IGNORE_NOTIFICATIONS: user_input.get(CONF_IGNORE_NOTIFICATIONS, False),
            # })
            self._options.update({
                CONF_DELAY: user_input.get(CONF_DELAY, 120),
                CONF_LEDCOUNT: user_input[CONF_LEDCOUNT],
                # CONF_LEDTYPE: user_input[CONF_LEDTYPE],
                CONF_LEDTYPE: chip,
                # CONF_COLORORDER: user_input[CONF_COLORORDER],
                CONF_COLORORDER: order,
                CONF_SEGMENTS: user_input.get(CONF_SEGMENTS, 1),
                CONF_IGNORE_NOTIFICATIONS: user_input.get(CONF_IGNORE_NOTIFICATIONS, False),
            })
            _LOGGER.debug("[OPTIONS] Updated options: %s", self._options)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._options)

        
        # chip_default_name = next(
        #     (t.name for t in led_types if t.value == chip_default),
        #     led_types_list[0].name
        # )
        # chip_default = self._options.get(CONF_LEDTYPE, 1)
        # order_default = self._options.get(CONF_COLORORDER, ColorOrdering.GRB.value)
        # order_default = self._options.get(CONF_COLORORDER, 2)
        # order_default_name = next((o.name for o in ColorOrdering if o.value == order_default), ColorOrdering.GRB.name)
        current_chip = self._options.get(CONF_LEDTYPE)
        current_order = self._options.get(CONF_COLORORDER)
        chip_default_name = current_chip.name if hasattr(current_chip, 'name') else list(led_types)[0].name
        order_default_name = current_order.name if hasattr(current_order, 'name') else ColorOrdering.GRB.name
        _LOGGER.debug("[OPTIONS] Resolved chip_default: %s, order_default: %s", chip_default_name, order_default_name)

        schema = vol.Schema({
            vol.Optional(CONF_DELAY, default=self._options.get(CONF_DELAY, 120)): int,
            vol.Optional(CONF_LEDCOUNT, default=self._options.get(CONF_LEDCOUNT, 64)): cv.positive_int,
            vol.Optional(CONF_LEDTYPE, default=chip_default_name): vol.In([t.name for t in led_types]),
            vol.Optional(CONF_COLORORDER, default=order_default_name): vol.In([o.name for o in ColorOrdering]),
            vol.Optional(CONF_SEGMENTS, default=self._options.get(CONF_SEGMENTS, 1)): cv.positive_int,
            vol.Optional(CONF_IGNORE_NOTIFICATIONS, default=self._options.get(CONF_IGNORE_NOTIFICATIONS, False)): bool,
        })
        return self.async_show_form(step_id="user", data_schema=schema)
