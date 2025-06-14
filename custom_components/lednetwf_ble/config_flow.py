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
import homeassistant.helpers.config_validation as cv
from bluetooth_data_tools import human_readable_name

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_DELAY,
    CONF_LEDCOUNT,
    CONF_LEDTYPE,
    CONF_COLORORDER,
    CONF_MODEL,
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


class DeviceData:
    def __init__(self, discovery: BluetoothServiceInfoBleak):
        self._discovery = discovery
        self.address = discovery.address
        self.logical_name = discovery.name
        self.rssi = discovery.rssi
        manu_data = next(iter(discovery.manufacturer_data.values()), None)
        self.fw_major = manu_data[0] if isinstance(manu_data, (bytes, bytearray)) and len(manu_data) > 0 else None

    def is_supported(self) -> bool:
        return (
            self.logical_name.lower().startswith("lednetwf")
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
        self._devices: dict[str, DeviceData] = {}
        self._selected: DeviceData | None = None
        self._instance: LEDNETWFInstance | None = None
        self._initial_discovery: BluetoothServiceInfoBleak | None = None

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        _LOGGER.debug("[BT] Received Bluetooth discovery for %s", discovery_info.address)
        self._initial_discovery = discovery_info
        device = DeviceData(discovery_info)
        self.context["title_placeholders"] = {"name": "LEDnetWF Device"}
        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        _LOGGER.debug("[USER] Entered async_step_user with input: %s", user_input)

        configured_ids = self._get_configured_ids()
        _LOGGER.debug("[USER] Already configured device IDs: %s", configured_ids)

        self._devices.clear()

        for discovery in async_discovered_service_info(self.hass):
            if discovery.address in configured_ids:
                _LOGGER.debug("[USER] Skipping configured address: %s", discovery.address)
                continue

            if discovery.address in self._devices:
                _LOGGER.debug("[USER] Skipping duplicate address already seen: %s", discovery.address)
                continue

            try:
                device = DeviceData(discovery)
                if device.is_supported():
                    self._devices[discovery.address] = device
                    _LOGGER.debug("[USER] Added device: %s (%s)", device.display_name(), device.fw_major)
            except Exception as e:
                _LOGGER.warning("[USER] Failed to parse discovery %s: %s", discovery.address, e)

        if user_input:
            mac = user_input[CONF_MAC]
            self._selected = self._devices.get(mac)
            if self._selected:
                _LOGGER.debug("[USER] Selected device: %s", self._selected.display_name())
                return await self.async_step_validate()
            else:
                _LOGGER.warning("[USER] Selected MAC not in device list: %s", mac)
                return self.async_abort(reason="device_disappeared")

        if not self._devices:
            _LOGGER.warning("[USER] No supported unconfigured devices found")
            return self.async_abort(reason="no_devices_found")

        mac_dict = {
            addr: dev.display_name()
            for addr, dev in sorted(self._devices.items(), key=lambda item: item[1].rssi or -999, reverse=True)
        }

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

        if not self._instance:
            _LOGGER.debug("[VALIDATE] Instantiating device before prompt")
            data = {
                CONF_MAC: self._selected.address,
                CONF_NAME: self._selected.human_name(),
                CONF_DELAY: 120,
                CONF_MODEL: self._selected.fw_major,
            }
            self._instance = LEDNETWFInstance(self._selected.address, self.hass, data)
            await self._instance.update()
            await self._instance.send_initial_packets()
            await self._instance._write(self._instance._model_interface.GET_LED_SETTINGS_PACKET)

        if user_input:
            if user_input.get("flicker"):
                await self.async_set_unique_id(self._selected.address)
                self._abort_if_unique_id_configured()
                return self._create_entry()

        try:
            for _ in range(3):
                await self._instance.turn_on()
                await asyncio.sleep(1)
                await self._instance.turn_off()
                await asyncio.sleep(1)
        except Exception as e:
            _LOGGER.error("[TOGGLE] Toggle failed: %s", e, exc_info=True)
            return self.async_show_form(
                step_id="validate",
                data_schema=vol.Schema({vol.Required("retry"): bool}),
                errors={"base": "connect"},
            )

        return self.async_show_form(
            step_id="validate",
            data_schema=vol.Schema({vol.Required("flicker"): bool}),
            description_placeholders={"device": self._selected.display_name()},
        )

    def _create_entry(self) -> FlowResult:
        led_count = getattr(self._instance._model_interface, 'led_count', 64)
        chip_type = getattr(self._instance._model_interface, 'chip_type', "WS2812B")
        color_order = getattr(self._instance._model_interface, 'color_order', "GRB")

        _LOGGER.debug("[CREATE] LED Count: %s, Chip Type: %s, Color Order: %s", led_count, chip_type, color_order)

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
        led_types = LedTypes_StripLight if model == 0x56 else LedTypes_RingLight
        led_types_list = list(led_types)

        if not led_types_list:
            _LOGGER.error("[OPTIONS] No LED types defined for model: %s", model)
            return self.async_abort(reason="unsupported_model")

        _LOGGER.debug("[OPTIONS] Current model: %s", model)
        _LOGGER.debug("[OPTIONS] Options before update: %s", self._options)

        if user_input:
            """new_led_type    = user_input.get(CONF_LEDTYPE)
            new_led_type    = LedTypes_StripLight[new_led_type].value if model == 0x56 else LedTypes_RingLight[new_led_type].value
            """
            chip = led_types[user_input[CONF_LEDTYPE]]# .value
            order = ColorOrdering[user_input[CONF_COLORORDER]]# .value
            self._options.update({
                CONF_DELAY: user_input.get(CONF_DELAY, 120),
                CONF_LEDCOUNT: user_input[CONF_LEDCOUNT],
                CONF_LEDTYPE: chip,
                CONF_COLORORDER: order,
            })
            _LOGGER.debug("[OPTIONS] Updated options: %s", self._options)
            return self.async_create_entry(title=self._data[CONF_NAME], data=self._options)

        chip_default = self._options.get(CONF_LEDTYPE)
        chip_default_name = next(
            (t.name for t in led_types if t.value == chip_default),
            led_types_list[0].name
        )
        order_default = self._options.get(CONF_COLORORDER, ColorOrdering.GRB.value)
        order_default_name = next((o.name for o in ColorOrdering if o.value == order_default), ColorOrdering.GRB.name)

        _LOGGER.debug("[OPTIONS] Resolved chip_default: %s, order_default: %s", chip_default_name, order_default_name)

        schema = vol.Schema({
            vol.Optional(CONF_DELAY, default=self._options.get(CONF_DELAY, 120)): int,
            vol.Optional(CONF_LEDCOUNT, default=self._options.get(CONF_LEDCOUNT, 64)): cv.positive_int,
            vol.Optional(CONF_LEDTYPE, default=chip_default_name): vol.In([t.name for t in led_types]),
            vol.Optional(CONF_COLORORDER, default=order_default_name): vol.In([o.name for o in ColorOrdering]),
        })
        return self.async_show_form(step_id="user", data_schema=schema)
