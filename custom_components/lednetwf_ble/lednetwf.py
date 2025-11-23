import asyncio
import importlib
import pkgutil
from homeassistant.components import bluetooth
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components.light import EFFECT_OFF
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTCharacteristic, BleakGATTServiceCollection
from bleak.exc import BleakDBusError
from bleak_retry_connector import BLEAK_RETRY_EXCEPTIONS as BLEAK_EXCEPTIONS
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    BleakNotFoundError,
    establish_connection,
    retry_bluetooth_connection_error,
)
from typing import Any, TypeVar, cast, Tuple
from collections.abc import Callable
import traceback
import logging

from .const import (
    CONF_DELAY,
    CONF_MODEL,
    CONF_LEDTYPE,
    CONF_COLORORDER,
    CONF_SEGMENTS,
    CONF_IGNORE_NOTIFICATIONS
)

LOGGER                        = logging.getLogger(__name__)
WRITE_CHARACTERISTIC_UUIDS    = ["0000ff01-0000-1000-8000-00805f9b34fb"]
NOTIFY_CHARACTERISTIC_UUIDS   = ["0000ff02-0000-1000-8000-00805f9b34fb"]
INITIAL_PACKET                = bytearray.fromhex("00 01 80 00 00 04 05 0a 81 8a 8b 96")
GET_LED_SETTINGS_PACKET       = bytearray.fromhex("00 02 80 00 00 05 06 0a 63 12 21 f0 86")
DEFAULT_ATTEMPTS              = 3
BLEAK_BACKOFF_TIME            = 0.25
RETRY_BACKOFF_EXCEPTIONS      = (BleakDBusError)
SUPPORTED_MODELS              = {}

WrapFuncType = TypeVar("WrapFuncType", bound=Callable[..., Any])

# Iterate through all modules in the current package
package = __package__
filename = __file__
LOGGER.debug(f"File: {__file__}")
my_name = filename[filename.rfind('/')+1:]
models_path = f"{filename.replace(my_name, 'models')}"
LOGGER.debug(f"Models path: {models_path}")

for _, module_name, _ in pkgutil.iter_modules([models_path]):
    LOGGER.debug(f"Module name: {module_name}")
    if module_name.startswith('model_0x'):
        m = importlib.import_module(f'{package}.models.{module_name}')
        class_name = f'Model{module_name.split("_")[1]}'
        if hasattr(m, class_name):
            globals()[class_name] = getattr(m, class_name)
        if hasattr(m, "SUPPORTED_MODELS"):
            supported_models_hex = [f"0x{model:02X}" for model in getattr(m, 'SUPPORTED_MODELS')]
            LOGGER.debug(f"Supported models: {supported_models_hex}")
            SUPPORTED_MODELS[class_name] = getattr(m, "SUPPORTED_MODELS")

all_models_hex = {class_name: [f"0x{model:02X}" for model in models] for class_name, models in SUPPORTED_MODELS.items()}
LOGGER.debug(f"All supported modules: {all_models_hex}")

def find_model_for_value(value):
    for model_name, models in SUPPORTED_MODELS.items():
        if value in models:
            return model_name
    return None

def retry_bluetooth_connection_error(func: WrapFuncType) -> WrapFuncType:
    async def _async_wrap_retry_bluetooth_connection_error(
        self: "LEDNETWFInstance", *args: Any, **kwargs: Any
    ) -> Any:
        attempts = DEFAULT_ATTEMPTS
        max_attempts = attempts - 1

        for attempt in range(attempts):
            try:
                return await func(self, *args, **kwargs)
            except BleakNotFoundError:
                # The lock cannot be found so there is no
                # point in retrying.
                raise
            except RETRY_BACKOFF_EXCEPTIONS as err:
                if attempt >= max_attempts:
                    LOGGER.debug(
                        "%s: %s error calling %s, reach max attempts (%s/%s)",
                        self.bluetooth_device_name,
                        type(err),
                        func,
                        attempt,
                        max_attempts,
                        exc_info=True,
                    )
                    raise
                LOGGER.debug(
                    "%s: %s error calling %s, backing off %ss, retrying (%s/%s)...",
                    self.bluetooth_device_name,
                    type(err),
                    func,
                    BLEAK_BACKOFF_TIME,
                    attempt,
                    max_attempts,
                    exc_info=True,
                )
                await asyncio.sleep(BLEAK_BACKOFF_TIME)
            except BLEAK_EXCEPTIONS as err:
                if attempt >= max_attempts:
                    LOGGER.debug(
                        "%s: %s error calling %s, reach max attempts (%s/%s): %s",
                        self.bluetooth_device_name,
                        type(err),
                        func,
                        attempt,
                        max_attempts,
                        err,
                        exc_info=True,
                    )
                    raise
                LOGGER.debug(
                    "%s: %s error calling %s, retrying  (%s/%s)...: %s",
                    self.bluetooth_device_name,
                    type(err),
                    func,
                    attempt,
                    max_attempts,
                    err,
                    exc_info=True,
                )

    return cast(WrapFuncType, _async_wrap_retry_bluetooth_connection_error)


class LEDNETWFInstance:
    def __init__(self, mac, hass, data={}, options={}) -> None:
        self._data    = data
        LOGGER.debug(f"Data: {data}")
        self._name    = self._data.get('name')
        self._model   = self._data.get(CONF_MODEL)
        self._ignore_notifications = self._data.get(CONF_IGNORE_NOTIFICATIONS, options.get(CONF_IGNORE_NOTIFICATIONS, False))
        LOGGER.debug(f"Ignore notifications: {self._ignore_notifications}")
        self._segments = self._data.get(CONF_SEGMENTS, options.get(CONF_SEGMENTS, 1))
        LOGGER.debug(f"Segments: {self._segments}")
        self._options = options
        self._hass    = hass
        self._mac     = mac
        self._delay   = self._options.get(CONF_DELAY, self._data.get(CONF_DELAY, 120)) # Try and read from options first, data second so that if this is changed via config then new values are picked up
        self.loop     = asyncio.get_running_loop()
        self._bluetooth_device:   BLEDevice | None = None
        self._bluetooth_device  = bluetooth.async_ble_device_from_address(self._hass, self._mac)
        if not self._bluetooth_device:
            raise ConfigEntryNotReady(
                f"You need to add bluetooth integration (https://www.home-assistant.io/integrations/bluetooth) or couldn't find a nearby device with address: {self._mac}"
            )
        service_info  = bluetooth.async_last_service_info(self._hass, self._mac).as_dict()
        if service_info is not None and 'address' in service_info:
            if service_info['address'] != self._mac:
                LOGGER.error(f"Service info address {service_info['address']} does not match expected MAC {self._mac}. This shouldn't happen, but it does. Try again later.")
                return False
        model_class_name = find_model_for_value(self._model)
        LOGGER.debug(f"Model class name: {model_class_name}")
        if model_class_name is None:
            if self._model is None:
                LOGGER.error(f"Device model is None. Manufacturer data may not be available yet. MAC: {self._mac}")
                raise ConfigEntryNotReady(
                    f"Unable to determine device model for {self._mac}. Manufacturer data not available. Please ensure the device is advertising and try again."
                )
            else:
                LOGGER.error(f"No model class found for model value: 0x{self._model:02X}. Device may not be supported yet.")
                raise ConfigEntryNotReady(
                    f"Device model 0x{self._model:02X} is not supported. Please check the integration documentation."
                )
        model_class = globals()[model_class_name]
        LOGGER.debug(f"Model class via lookup: {model_class}")
        self._model_interface = model_class(service_info['manufacturer_data'])
        self._model_interface._parent_instance = self
        self._connect_lock: asyncio.Lock = asyncio.Lock()
        self._client: BleakClientWithServiceCache | None = None
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._cached_services: BleakGATTServiceCollection | None = None
        self._expected_disconnect   = False
        self._packet_counter        = 0
        self._read_uuid             = None
        self._model_interface.chip_type = self._options.get(CONF_LEDTYPE)
        self._model_interface.color_order = self._options.get(CONF_COLORORDER)
        LOGGER.debug(f"Chip type: {self._model_interface.chip_type}")
        LOGGER.debug(f"Color order: {self._model_interface.color_order}")
    
    async def _write(self, data: bytearray):
        """Send command to device and read response."""
        if data is None:
            return
        await self._ensure_connected()
        if self._packet_counter > 65535:
            self._packet_counter = 0
        data[0] = (0xFF00 & self._packet_counter) >> 8
        data[1] = 0x00FF & self._packet_counter
        self._packet_counter += 1
        await self._write_while_connected(data)

    async def _write_while_connected(self, data: bytearray):
        LOGGER.debug(f"Writing data to {self._name}: {' '.join([f'{byte:02X}' for byte in data])}")
        await self._client.write_gatt_char(self._write_uuid, data, False)
    
    def _notification_handler(self, _sender: BleakGATTCharacteristic, data: bytearray) -> None:
        LOGGER.debug(f"Notification handler {self.bluetooth_device_name}: {' '.join([f'{byte:02X}' for byte in data])}")
        if self._ignore_notifications:
            LOGGER.debug("Ignoring notification as per configuration")
            return
        self._model_interface.notification_handler(data)
        self.local_callback()
    
    async def send_initial_packets(self):
        # Send initial packets to device to see if it sends notifications
        LOGGER.debug("Send initial packets")
        await self._write(self._model_interface.INITIAL_PACKET)
        if not self._model_interface.chip_type:
            # We should only need to get this once, since config is immutable.
            # All future changes of this data will come via the config flow.
            LOGGER.debug(f"Sending GET_LED_SETTINGS_PACKET to {self.bluetooth_device_name}")
            await self._write(self._model_interface.GET_LED_SETTINGS_PACKET)
        # Query device status including background color for models that support it
        if hasattr(self._model_interface, 'GET_STATUS_PACKET'):
            LOGGER.debug(f"Sending GET_STATUS_PACKET to {self.bluetooth_device_name}")
            await self._write(self._model_interface.GET_STATUS_PACKET)
    
    @property
    def mac(self):
        return self._bluetooth_device.address

    @property
    def bluetooth_device_name(self):
        return self._bluetooth_device.name

    @property
    def rssi(self):
        return self._bluetooth_device.rssi

    @property
    def is_on(self):
        return self._model_interface.is_on

    @property
    def brightness(self):
        return self._model_interface.brightness

    @property
    def min_color_temp_kelvin(self):
        return self._model_interface.min_color_temp

    @property
    def max_color_temp_kelvin(self):
        return self._model_interface.max_color_temp

    @property
    def color_temp_kelvin(self):
        return self._model_interface.color_temperature_kelvin

    @property
    def hs_color(self):
        return self._model_interface.get_hs_color()

    @property
    def rgb_color(self):
        return self._model_interface.get_rgb_color()
    
    @property
    def bg_hs_color(self):
        return self._model_interface.get_bg_hs_color()
    
    @property
    def bg_rgb_color(self):
        return self._model_interface.get_bg_rgb_color()
    
    @property
    def bg_brightness(self):
        return self._model_interface.bg_brightness
    
    @property
    def effect_list(self) -> list[str]:
        return self._model_interface.effect_list

    @property
    def effect(self):
        return self._model_interface.effect
    
    @property
    def color_mode(self):
        return self._model_interface.color_mode
    
    @property
    def model_number(self):
        return self._model_interface.fw_major
    
    @property
    def firmware_version(self):
        return f"{self._model_interface.fw_major:02X}.{self._model_interface.fw_minor}"
    
    @retry_bluetooth_connection_error
    async def set_color_temp_kelvin(self, value: int, new_brightness: int):
        byte_pattern = self._model_interface.set_color_temp_kelvin(value, new_brightness)
        await self._write(byte_pattern)
    
    @retry_bluetooth_connection_error
    async def set_hs_color(self, hs: Tuple[int, int], new_brightness: int):
        byte_pattern = self._model_interface.set_color(hs, new_brightness)
        await self._write(byte_pattern)
    
    @retry_bluetooth_connection_error
    async def set_bg_hs_color(self, hs: Tuple[int, int], new_brightness: int):
        # Only set background color if the model supports it
        if hasattr(self._model_interface, 'set_bg_color'):
            byte_pattern = self._model_interface.set_bg_color(hs, new_brightness)
            await self._write(byte_pattern)
        else:
            LOGGER.warning(f"Model {self.model_number:02x} does not support background color")
    
    @retry_bluetooth_connection_error
    async def set_effect(self, effect: str, new_brightness: int):
        byte_pattern = self._model_interface.set_effect(effect, new_brightness)
        await self._write(byte_pattern)
    
    @retry_bluetooth_connection_error
    async def set_effect_speed(self, speed):
        speed = max(0, min(100, speed)) # Should be zero for stationary effects?
        self._model_interface.effect_speed = speed
        if self._model_interface.effect == EFFECT_OFF:
            return
        await self.set_effect(self.effect, self.brightness)
    
    @retry_bluetooth_connection_error
    async def turn_on(self):
        await self._write(self._model_interface.turn_on())
    
    @retry_bluetooth_connection_error
    async def turn_off(self):
        await self._write(self._model_interface.turn_off())

    @retry_bluetooth_connection_error
    async def set_led_settings(self, options: dict):
        led_settings_packet = self._model_interface.set_led_settings(options)
        if led_settings_packet is None:
            LOGGER.error("LED settings packet is None")
            return
        LOGGER.debug(f"LED settings packet: {' '.join([f'{byte:02X}' for byte in led_settings_packet])}")
        await self.turn_off()
        await self._write(led_settings_packet)
        await self._write(self._model_interface.GET_LED_SETTINGS_PACKET)
        await self.turn_off()
        await self.stop()

    @retry_bluetooth_connection_error
    async def update(self):
        # Called when HA starts up and wants the devices to initialise themselves
        LOGGER.debug(f"{self._name}: Update in lednetwf called")
        try:
            await self._ensure_connected()
            # Query the device to get the actual current state
            await self.send_initial_packets()
        except Exception as error:
            LOGGER.debug(f"Error getting status: {error}")
            track = traceback.format_exc()
            LOGGER.error(track)

    async def _ensure_connected(self) -> None:
        """Ensure connection to device is established."""
        LOGGER.debug(f"{self._name}: Ensure connected")
        if self._connect_lock.locked():
            LOGGER.debug(f"ES {self._name}: Connection already in progress, waiting for it to complete")
        
        if self._client and self._client.is_connected:
            self._reset_disconnect_timer()
            return

        async with self._connect_lock:
            # Check again while holding the lock
            if self._client and self._client.is_connected:
                self._reset_disconnect_timer()
                return
            
            LOGGER.debug(f"{self._name}: Not connected yet, connecting now...")
            client = await establish_connection(
                BleakClientWithServiceCache,
                self._bluetooth_device,
                self.bluetooth_device_name,
                self._disconnected,
                use_services_cache=True,
                ble_device_callback=lambda: self._bluetooth_device,
            )
            
            LOGGER.debug(f"{self._name}: Connected")
            resolved = self._resolve_characteristics(client.services)
            if not resolved:
                # Try to handle services failing to load
                resolved = self._resolve_characteristics(await client.get_services())
            
            self._client = client
            self._reset_disconnect_timer()
            LOGGER.debug(f"Trying to start notifications for {self._name}")
            await self._client.start_notify(self._read_uuid, self._notification_handler)
            # Give the BLE stack a moment to register the notification handler
            await asyncio.sleep(0.1)
            
    def _resolve_characteristics(self, services: BleakGATTServiceCollection) -> bool:
        """Resolve characteristics."""
        for characteristic in self._model_interface.NOTIFY_CHARACTERISTIC_UUIDS:
            if char := services.get_characteristic(characteristic):
                LOGGER.debug(f"Found notify characteristic: {char}")
                self._read_uuid = char
                break
        for characteristic in self._model_interface.WRITE_CHARACTERISTIC_UUIDS:
            if char := services.get_characteristic(characteristic):
                LOGGER.debug(f"Found write characteristic: {char}")
                self._write_uuid = char
                break
        return bool(self._read_uuid and self._write_uuid)

    def _reset_disconnect_timer(self) -> None:
        """Reset disconnect timer."""
        if self._disconnect_timer:
            LOGGER.debug(f"{self._name}: Cancelling existing disconnect timer (delay was {self._delay}s)")
            self._disconnect_timer.cancel()
        self._expected_disconnect = False
        if self._delay is not None and self._delay != 0:
            LOGGER.debug(f"{self._name}: Creating new disconnect timer with delay {self._delay}s")
            self._disconnect_timer = self.loop.call_later(self._delay, self._disconnect)

    def _disconnected(self, client: BleakClientWithServiceCache) -> None:
        """Disconnected callback."""
        if self._expected_disconnect:
            LOGGER.debug("Disconnected from device")
            return
        LOGGER.warning("Device unexpectedly disconnected")

    def _disconnect(self) -> None:
        """Disconnect from device."""
        self._disconnect_timer = None
        asyncio.create_task(self._execute_timed_disconnect())

    async def stop(self) -> None:
        """Stop the LEDNET WF device."""
        LOGGER.debug("%s: Stop", self._name)
        await self._execute_disconnect()

    async def _execute_timed_disconnect(self) -> None:
        """Execute timed disconnection."""
        LOGGER.debug(f"Disconnecting after timeout of {self._delay}")
        await self._execute_disconnect()

    async def _execute_disconnect(self) -> None:
        """Execute disconnection."""
        async with self._connect_lock:
            read_char = self._read_uuid
            client = self._client
            self._expected_disconnect = True
            self._client = None
            self._write_uuid = None
            self._read_uuid = None
            if client and client.is_connected:
                await client.stop_notify(read_char)
                await client.disconnect()
            LOGGER.debug("Disconnected")
    
    def register_callback(self, callback):
        """Register a callback to be called when device state changes."""
        if not hasattr(self, '_callbacks'):
            self._callbacks = []
        self._callbacks.append(callback)
        LOGGER.debug(f"Registered callback for {self._mac}, total callbacks: {len(self._callbacks)}")
    
    def local_callback(self):
        # Notify all registered entities (main light and background light)
        LOGGER.debug(f"local_callback triggered for {self._mac}")
        if hasattr(self, '_callbacks'):
            LOGGER.debug(f"Found {len(self._callbacks)} registered callbacks")
            for callback in self._callbacks:
                callback()
        else:
            LOGGER.debug("No callbacks registered!")
        return

