"""Device class for LEDnetWF BLE devices.

Handles BLE connection, state management, and command sending.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection, BleakClientWithServiceCache

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, callback

from .const import (
    WRITE_CHARACTERISTIC_UUID,
    NOTIFY_CHARACTERISTIC_UUID,
    DEFAULT_DISCONNECT_DELAY,
    DEFAULT_EFFECT_SPEED,
    MIN_KELVIN,
    MAX_KELVIN,
    EffectType,
    get_device_capabilities,
    needs_capability_probing,
    get_effect_list,
    get_effect_id,
)
from . import protocol

_LOGGER = logging.getLogger(__name__)


class LEDNetWFDevice:
    """Represents a LEDnetWF BLE device."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        product_id: int | None = None,
        disconnect_delay: int = DEFAULT_DISCONNECT_DELAY,
    ) -> None:
        """Initialize the device.

        Args:
            hass: Home Assistant instance
            address: BLE MAC address
            name: Device name
            product_id: Product ID from manufacturer data
            disconnect_delay: Seconds to wait before disconnecting
        """
        self._hass = hass
        self._address = address
        self._name = name
        self._product_id = product_id
        self._disconnect_delay = disconnect_delay

        # Connection state
        self._client: BleakClient | None = None
        self._ble_device: BLEDevice | None = None
        self._disconnect_timer: asyncio.TimerHandle | None = None
        self._seq: int = 0
        self._connect_lock = asyncio.Lock()

        # Device state
        self._is_on: bool | None = None
        self._brightness: int = 255  # 0-255
        self._rgb: tuple[int, int, int] | None = None
        self._color_temp_kelvin: int | None = None
        self._effect: str | None = None
        self._effect_speed: int = DEFAULT_EFFECT_SPEED  # 0-100

        # LED settings (for addressable strips)
        self._led_count: int | None = None
        self._led_type: int | None = None
        self._color_order: int | None = None

        # Firmware info
        self._fw_version: str | None = None

        # Callbacks for state updates
        self._callbacks: list[Callable[[], None]] = []

        # Cache capabilities
        self._capabilities = get_device_capabilities(product_id)

        # Log initial device setup
        _LOGGER.debug(
            "Device initialized: %s (%s), product_id=0x%02X, "
            "capabilities: has_rgb=%s, has_ww=%s, has_cw=%s, effect_type=%s, needs_probing=%s",
            self._name, self._address,
            product_id or 0,
            self._capabilities.get("has_rgb"),
            self._capabilities.get("has_ww"),
            self._capabilities.get("has_cw"),
            self._capabilities.get("effect_type"),
            self._capabilities.get("needs_probing"),
        )

        # Response waiting mechanism for probing
        self._pending_state_response: asyncio.Event | None = None
        self._last_state_response: dict | None = None

    @property
    def address(self) -> str:
        """Return the BLE address."""
        return self._address

    @property
    def name(self) -> str:
        """Return the device name."""
        return self._name

    @property
    def product_id(self) -> int | None:
        """Return the product ID."""
        return self._product_id

    @property
    def capabilities(self) -> dict:
        """Return device capabilities."""
        return self._capabilities

    @property
    def is_on(self) -> bool | None:
        """Return power state."""
        return self._is_on

    @property
    def brightness(self) -> int:
        """Return brightness (0-255)."""
        return self._brightness

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return RGB color."""
        return self._rgb

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return color temperature in Kelvin."""
        return self._color_temp_kelvin

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return minimum color temperature."""
        return MIN_KELVIN

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return maximum color temperature."""
        return MAX_KELVIN

    @property
    def effect(self) -> str | None:
        """Return current effect name."""
        return self._effect

    @property
    def effect_speed(self) -> int:
        """Return effect speed (0-100)."""
        return self._effect_speed

    @property
    def effect_list(self) -> list[str]:
        """Return list of available effects."""
        effect_type = self._capabilities.get("effect_type", EffectType.NONE)
        return get_effect_list(effect_type)

    @property
    def has_rgb(self) -> bool:
        """Return True if device supports RGB."""
        return bool(self._capabilities.get("has_rgb"))

    @property
    def has_color_temp(self) -> bool:
        """Return True if device supports color temperature."""
        return bool(self._capabilities.get("has_ww") or self._capabilities.get("has_cw"))

    @property
    def has_effects(self) -> bool:
        """Return True if device supports effects."""
        effect_type = self._capabilities.get("effect_type", EffectType.NONE)
        return effect_type != EffectType.NONE

    @property
    def needs_probing(self) -> bool:
        """Return True if device needs capability probing."""
        return self._capabilities.get("needs_probing", False)

    @property
    def fw_version(self) -> str | None:
        """Return firmware version."""
        return self._fw_version

    @property
    def led_count(self) -> int | None:
        """Return LED count for addressable strips."""
        return self._led_count

    def register_callback(self, callback_fn: Callable[[], None]) -> None:
        """Register a callback for state updates."""
        self._callbacks.append(callback_fn)

    def unregister_callback(self, callback_fn: Callable[[], None]) -> None:
        """Unregister a callback."""
        if callback_fn in self._callbacks:
            self._callbacks.remove(callback_fn)

    def _notify_callbacks(self) -> None:
        """Notify all registered callbacks."""
        for callback_fn in self._callbacks:
            try:
                callback_fn()
            except Exception as ex:
                _LOGGER.exception("Error in callback: %s", ex)

    async def _ensure_connected(self) -> BleakClient:
        """Ensure we have an active BLE connection."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None

        if self._client and self._client.is_connected:
            self._schedule_disconnect()
            return self._client

        async with self._connect_lock:
            # Check again after acquiring lock
            if self._client and self._client.is_connected:
                self._schedule_disconnect()
                return self._client

            _LOGGER.debug("Connecting to %s (%s)", self._name, self._address)

            try:
                # Get BLEDevice from address
                ble_device: BLEDevice | None = bluetooth.async_ble_device_from_address(
                    self._hass, self._address
                )
                if not ble_device:
                    raise BleakError(f"Device {self._address} not found")

                # Store for ble_device_callback
                self._ble_device = ble_device

                self._client = await establish_connection(
                    BleakClientWithServiceCache,
                    ble_device,
                    self._name,
                    disconnected_callback=self._on_disconnected,
                    use_services_cache=True,
                    ble_device_callback=lambda: self._ble_device,
                )

                # Start notifications
                await self._client.start_notify(
                    NOTIFY_CHARACTERISTIC_UUID,
                    self._on_notification,
                )

                # Give BLE stack a moment to register the notification handler
                await asyncio.sleep(0.1)
                _LOGGER.debug("Connected and notifications started for %s", self._name)

            except BleakError as ex:
                _LOGGER.error("Failed to connect to %s: %s", self._name, ex)
                self._client = None
                raise

        self._schedule_disconnect()
        return self._client

    def _schedule_disconnect(self) -> None:
        """Schedule a disconnection after the delay."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()

        self._disconnect_timer = self._hass.loop.call_later(
            self._disconnect_delay,
            lambda: asyncio.create_task(self._disconnect()),
        )

    async def _disconnect(self) -> None:
        """Disconnect from the device."""
        if self._client and self._client.is_connected:
            _LOGGER.debug("Disconnecting from %s", self._name)
            try:
                await self._client.stop_notify(NOTIFY_CHARACTERISTIC_UUID)
            except BleakError:
                pass
            try:
                await self._client.disconnect()
            except BleakError:
                pass
        self._client = None

    @callback
    def _on_disconnected(self, client: BleakClient) -> None:
        """Handle disconnection."""
        _LOGGER.debug("Disconnected from %s", self._name)
        self._client = None

    def _on_notification(self, sender: int, data: bytearray) -> None:
        """Handle incoming notifications."""
        # Format as 0xNN for readability
        raw_hex = ' '.join(f'0x{b:02X}' for b in data)
        _LOGGER.debug("Notification from %s (raw %d bytes): %s",
                      self._name, len(data), raw_hex)

        # Unwrap transport layer
        payload = protocol.unwrap_response(bytes(data))
        if not payload:
            _LOGGER.debug("Could not unwrap notification (data too short?)")
            return

        # Format payload as 0xNN
        payload_hex = ' '.join(f'0x{b:02X}' for b in payload)
        _LOGGER.debug("Notification payload (%d bytes): %s", len(payload), payload_hex)

        # Parse based on first byte
        if payload[0] == 0x81:
            self._parse_state_response(payload)
        elif payload[0] == 0x63:
            self._parse_led_settings_response(payload)
        else:
            _LOGGER.debug("Unknown notification type: 0x%02X", payload[0])

    def _parse_state_response(self, data: bytes) -> None:
        """Parse 0x81 state response."""
        result = protocol.parse_state_response(data)
        if not result:
            return

        # Store for probing
        self._last_state_response = result

        # Signal waiting coroutine if any
        if self._pending_state_response:
            self._pending_state_response.set()

        self._is_on = result["is_on"]
        self._rgb = (result["r"], result["g"], result["b"])

        # Use brightness from response if available
        if result.get("brightness", 0) > 0:
            self._brightness = result["brightness"]

        # Check if in effect mode
        if result.get("is_effect_mode") and result.get("effect_id"):
            self._effect = self._effect_id_to_name(result["effect_id"])
            # Update effect speed from response
            if result.get("speed", 0) > 0:
                # Convert 0-255 to 0-100
                self._effect_speed = int(result["speed"] * 100 / 255)
        else:
            # Not in effect mode - check for color temp vs RGB mode
            self._effect = None
            if result["ww"] > 0 or result["cw"] > 0:
                # White/CCT mode - estimate color temp from WW/CW ratio
                total = result["ww"] + result["cw"]
                if total > 0:
                    cw_ratio = result["cw"] / total
                    self._color_temp_kelvin = int(MIN_KELVIN + cw_ratio * (MAX_KELVIN - MIN_KELVIN))
                    self._brightness = min(255, total)
                    self._rgb = None  # Clear RGB when in CCT mode
            elif result["r"] > 0 or result["g"] > 0 or result["b"] > 0:
                # RGB mode
                self._color_temp_kelvin = None

        _LOGGER.debug("Parsed state: on=%s, rgb=%s, cct=%s, effect=%s, brightness=%s",
                      self._is_on, self._rgb, self._color_temp_kelvin, self._effect, self._brightness)

        self._notify_callbacks()

    def _parse_led_settings_response(self, data: bytes) -> None:
        """Parse 0x63 LED settings response."""
        result = protocol.parse_led_settings_response(data)
        if not result:
            return

        self._led_count = result["led_count"]
        self._led_type = result["ic_type"]
        self._color_order = result["color_order"]

        _LOGGER.debug("Parsed LED settings: count=%s, type=%s, order=%s",
                      self._led_count, self._led_type, self._color_order)

    def _effect_id_to_name(self, effect_id: int) -> str | None:
        """Convert effect ID to name."""
        effect_type = self._capabilities.get("effect_type", EffectType.NONE)

        if effect_type == EffectType.SIMPLE:
            from .const import SIMPLE_EFFECTS
            return SIMPLE_EFFECTS.get(effect_id)
        elif effect_type == EffectType.SYMPHONY:
            from .const import SYMPHONY_SCENE_EFFECTS
            if effect_id <= 44:
                return SYMPHONY_SCENE_EFFECTS.get(effect_id)
            elif effect_id >= 100:
                return f"Build Effect {effect_id - 99}"
        return None

    async def _send_command(self, packet: bytearray, with_response: bool = False) -> bool:
        """Send a command packet to the device.

        Args:
            packet: Command packet to send
            with_response: If True, wait for BLE acknowledgement (slower).
                          Default False for faster writes like the old integration.
        """
        try:
            client = await self._ensure_connected()

            # Update sequence number in packet
            self._seq = (self._seq + 1) % 256
            packet[1] = self._seq

            # Format as 0xNN for debugging
            pkt_hex = ' '.join(f'0x{b:02X}' for b in packet)
            _LOGGER.debug("Sending to %s: %s", self._name, pkt_hex)

            await client.write_gatt_char(
                WRITE_CHARACTERISTIC_UUID,
                packet,
                response=with_response,
            )
            return True

        except BleakError as ex:
            _LOGGER.error("Failed to send command to %s: %s", self._name, ex)
            return False

    # ----- Public command methods -----

    async def turn_on(self) -> bool:
        """Turn on the device."""
        packet = protocol.build_power_command_0x3B(turn_on=True)
        if await self._send_command(packet):
            self._is_on = True
            self._notify_callbacks()
            return True
        return False

    async def turn_off(self) -> bool:
        """Turn off the device."""
        packet = protocol.build_power_command_0x3B(turn_on=False)
        if await self._send_command(packet):
            self._is_on = False
            self._notify_callbacks()
            return True
        return False

    async def set_rgb_color(self, rgb: tuple[int, int, int], brightness: int = 255) -> bool:
        """Set RGB color.

        Args:
            rgb: Tuple of (R, G, B) values 0-255
            brightness: Brightness 0-255
        """
        if not self.has_rgb:
            _LOGGER.warning("Device %s does not support RGB", self._name)
            return False

        # Convert brightness to 0-100 for protocol
        brightness_pct = int(brightness * 100 / 255)

        packet = protocol.build_color_command_0x3B(
            rgb[0], rgb[1], rgb[2], brightness_pct
        )

        if await self._send_command(packet):
            self._rgb = rgb
            self._brightness = brightness
            self._effect = None  # Clear effect when setting color
            self._color_temp_kelvin = None
            self._notify_callbacks()
            return True
        return False

    async def set_color_temp(self, kelvin: int, brightness: int = 255) -> bool:
        """Set color temperature.

        Args:
            kelvin: Color temperature in Kelvin (2700-6500)
            brightness: Brightness 0-255
        """
        if not self.has_color_temp:
            _LOGGER.warning("Device %s does not support color temperature", self._name)
            return False

        # Use the 0x3B B1 command format (temperature percentage + brightness percentage)
        # This format is used by Ring Lights (model_0x53) and Symphony devices.
        # Per protocol docs: 0% = cool/6500K, 100% = warm/2700K
        kelvin = max(MIN_KELVIN, min(MAX_KELVIN, kelvin))
        temp_pct = int((MAX_KELVIN - kelvin) * 100 / (MAX_KELVIN - MIN_KELVIN))
        brightness_pct = int(brightness * 100 / 255)

        packet = protocol.build_cct_command_0x3B(temp_pct, brightness_pct)
        _LOGGER.debug("Setting CCT: kelvin=%d, temp_pct=%d%% (0=cool, 100=warm), brightness_pct=%d%%",
                      kelvin, temp_pct, brightness_pct)

        if await self._send_command(packet):
            self._color_temp_kelvin = kelvin
            self._brightness = brightness
            self._effect = None
            self._rgb = None
            self._notify_callbacks()
            return True
        return False

    async def set_effect(self, effect_name: str, speed: int | None = None) -> bool:
        """Set an effect by name.

        Args:
            effect_name: Effect name from effect_list
            speed: Effect speed 0-100 (or None to use current)
        """
        if not self.has_effects:
            _LOGGER.warning("Device %s does not support effects", self._name)
            return False

        effect_type = self._capabilities.get("effect_type", EffectType.NONE)
        effect_id = get_effect_id(effect_name, effect_type)

        if effect_id is None:
            _LOGGER.warning("Unknown effect: %s", effect_name)
            return False

        if speed is None:
            speed = self._effect_speed

        # Convert speed to 0-255 for protocol
        speed_byte = int(speed * 255 / 100)

        packet = protocol.build_effect_command(effect_type, effect_id, speed_byte)
        if packet is None:
            return False

        if await self._send_command(packet):
            self._effect = effect_name
            self._effect_speed = speed
            self._notify_callbacks()
            return True
        return False

    async def set_effect_speed(self, speed: int) -> bool:
        """Set effect speed (0-100).

        If an effect is active, re-sends the effect with new speed.
        """
        self._effect_speed = max(0, min(100, speed))

        # If an effect is currently active, update it with new speed
        if self._effect:
            return await self.set_effect(self._effect, self._effect_speed)

        return True

    async def query_state(self) -> bool:
        """Query current device state."""
        packet = protocol.build_state_query()
        return await self._send_command(packet)

    async def query_led_settings(self) -> bool:
        """Query LED settings (for addressable strips)."""
        packet = protocol.build_led_settings_query()
        return await self._send_command(packet)

    async def set_led_settings(
        self,
        led_count: int,
        led_type: int,
        color_order: int,
    ) -> bool:
        """Set LED settings for addressable strips."""
        packet = protocol.build_led_settings_command(led_count, led_type, color_order)

        if await self._send_command(packet):
            self._led_count = led_count
            self._led_type = led_type
            self._color_order = color_order
            return True
        return False

    def update_from_advertisement(self, manu_data: dict[int, bytes]) -> bool:
        """Update state from manufacturer advertisement data.

        Parses state_data bytes (14-24) which include:
        - Power state (byte 14)
        - Color mode (byte 15-16): RGB, CCT, or Effect
        - RGB color (bytes 18-20 when in RGB mode)
        - Brightness/CCT (bytes 17, 21 when in CCT mode)
        - Effect ID/speed (bytes 16, 18-19 when in effect mode)

        Returns True if state was updated.
        """
        result = protocol.parse_manufacturer_data(manu_data)
        if not result:
            return False

        changed = False

        # Power state
        if result.get("power_state") is not None:
            if self._is_on != result["power_state"]:
                self._is_on = result["power_state"]
                changed = True

        # Firmware version
        if result.get("fw_version"):
            self._fw_version = result["fw_version"]

        # Color mode and associated values
        color_mode = result.get("color_mode")

        if color_mode == "rgb":
            # RGB mode - update RGB color
            rgb = result.get("rgb")
            if rgb and rgb != self._rgb:
                self._rgb = rgb
                # Derive brightness from RGB (max component)
                max_val = max(rgb)
                if max_val > 0:
                    self._brightness = max_val
                self._color_temp_kelvin = None  # Clear CCT when in RGB mode
                self._effect = None  # Clear effect when in RGB mode
                changed = True
                _LOGGER.debug("Advertisement updated RGB: %s, brightness: %d",
                              self._rgb, self._brightness)

        elif color_mode == "cct":
            # CCT/White mode - update color temperature
            temp_pct = result.get("color_temp_percent")
            bright_pct = result.get("brightness_percent")

            if temp_pct is not None:
                # Convert percent to Kelvin
                # Per protocol docs: 0% = cool/6500K, 100% = warm/2700K
                # Same direction as command format (0x3B 0xB1)
                new_kelvin = int(MAX_KELVIN - temp_pct * (MAX_KELVIN - MIN_KELVIN) / 100)
                if self._color_temp_kelvin != new_kelvin:
                    self._color_temp_kelvin = new_kelvin
                    changed = True

            if bright_pct is not None:
                # Convert percent (0-100) to 0-255
                new_brightness = int(bright_pct * 255 / 100)
                if self._brightness != new_brightness:
                    self._brightness = new_brightness
                    changed = True

            if changed:
                self._rgb = None  # Clear RGB when in CCT mode
                self._effect = None  # Clear effect when in CCT mode
                _LOGGER.debug("Advertisement updated CCT: %dK, brightness: %d",
                              self._color_temp_kelvin, self._brightness)

        elif color_mode == "effect":
            # Effect mode - update effect and speed
            effect_id = result.get("effect_id")
            effect_speed = result.get("effect_speed")
            bright_pct = result.get("brightness_percent")

            if effect_id is not None:
                effect_name = self._effect_id_to_name(effect_id)
                if effect_name and self._effect != effect_name:
                    self._effect = effect_name
                    changed = True

            if effect_speed is not None and self._effect_speed != effect_speed:
                self._effect_speed = effect_speed
                changed = True

            if bright_pct is not None:
                new_brightness = int(bright_pct * 255 / 100)
                if self._brightness != new_brightness:
                    self._brightness = new_brightness
                    changed = True

            if changed:
                _LOGGER.debug("Advertisement updated effect: %s, speed: %d, brightness: %d",
                              self._effect, self._effect_speed, self._brightness)

        if changed:
            self._notify_callbacks()

        return changed

    async def _query_state_and_wait(self, timeout: float = 3.0) -> dict | None:
        """Send state query and wait for response.

        Args:
            timeout: Maximum seconds to wait for response

        Returns:
            Parsed state response dict, or None if timeout/error
        """
        self._pending_state_response = asyncio.Event()
        self._last_state_response = None

        try:
            packet = protocol.build_state_query()
            if not await self._send_command(packet):
                return None

            # Wait for response
            try:
                await asyncio.wait_for(
                    self._pending_state_response.wait(),
                    timeout=timeout
                )
                return self._last_state_response
            except asyncio.TimeoutError:
                _LOGGER.debug("State query timeout for %s", self._name)
                return None
        finally:
            self._pending_state_response = None

    async def probe_capabilities(self) -> dict:
        """Probe device capabilities by testing each channel.

        For unknown devices or stub classes, actively probe to detect
        which channels (RGB, WW, CW) are supported.

        Source: protocol_docs/04_device_identification_capabilities.md
        "State-Based Capability Detection" section

        Returns:
            Dict with detected capabilities (has_rgb, has_ww, has_cw)
        """
        _LOGGER.info("Probing capabilities for %s (product_id=0x%02X)",
                     self._name, self._product_id or 0)

        # Start with unknown capabilities
        detected = {
            "has_rgb": False,
            "has_ww": False,
            "has_cw": False,
            "effect_type": EffectType.SYMPHONY,  # Assume modern device
        }

        try:
            # Step 1: Query initial state to get baseline
            initial_state = await self._query_state_and_wait()
            if not initial_state:
                _LOGGER.warning("No state response during probe - device may not support state queries")
                # Fall back to defaults for unknown device
                detected["has_rgb"] = True
                detected["has_ww"] = True
                detected["has_cw"] = True
                self._capabilities.update(detected)
                return detected

            # Save original values to restore
            original_r = initial_state.get("r", 0)
            original_g = initial_state.get("g", 0)
            original_b = initial_state.get("b", 0)
            original_ww = initial_state.get("ww", 0)
            original_cw = initial_state.get("cw", 0)

            # Step 2: Test RGB by setting red to 0x32 (50)
            _LOGGER.debug("Testing RGB capability...")
            test_cmd = protocol.build_color_command_0x31(0x32, 0, 0, 0, 0)
            if await self._send_command(test_cmd):
                await asyncio.sleep(0.3)  # Give device time to apply
                state = await self._query_state_and_wait()
                if state and state.get("r", 0) >= 0x30:  # Allow some tolerance
                    detected["has_rgb"] = True
                    _LOGGER.debug("RGB capability detected")

            # Step 3: Test WW by setting to 0x32
            _LOGGER.debug("Testing WW capability...")
            test_cmd = protocol.build_color_command_0x31(0, 0, 0, 0x32, 0)
            if await self._send_command(test_cmd):
                await asyncio.sleep(0.3)
                state = await self._query_state_and_wait()
                if state and state.get("ww", 0) >= 0x30:
                    detected["has_ww"] = True
                    _LOGGER.debug("WW capability detected")

            # Step 4: Test CW by setting to 0x32
            _LOGGER.debug("Testing CW capability...")
            test_cmd = protocol.build_color_command_0x31(0, 0, 0, 0, 0x32)
            if await self._send_command(test_cmd):
                await asyncio.sleep(0.3)
                state = await self._query_state_and_wait()
                if state and state.get("cw", 0) >= 0x30:
                    detected["has_cw"] = True
                    _LOGGER.debug("CW capability detected")

            # Step 5: Restore original state
            _LOGGER.debug("Restoring original state...")
            if detected["has_rgb"] and (original_r or original_g or original_b):
                restore_cmd = protocol.build_color_command_0x3B(
                    original_r, original_g, original_b, 100
                )
                await self._send_command(restore_cmd)
            elif detected["has_ww"] or detected["has_cw"]:
                restore_cmd = protocol.build_white_command(original_ww, original_cw)
                await self._send_command(restore_cmd)

            _LOGGER.info("Probing complete for %s: RGB=%s, WW=%s, CW=%s",
                         self._name, detected["has_rgb"], detected["has_ww"], detected["has_cw"])

        except Exception as ex:
            _LOGGER.error("Error during capability probing: %s", ex)
            # Fall back to defaults
            detected["has_rgb"] = True
            detected["has_ww"] = True
            detected["has_cw"] = True

        # Update cached capabilities
        self._capabilities.update(detected)
        self._capabilities["needs_probing"] = False
        self._capabilities["probed"] = True

        # Log final capabilities summary
        _LOGGER.info(
            "Final capabilities for %s: has_rgb=%s, has_ww=%s, has_cw=%s, "
            "effect_type=%s, probed=%s",
            self._name,
            self._capabilities.get("has_rgb"),
            self._capabilities.get("has_ww"),
            self._capabilities.get("has_cw"),
            self._capabilities.get("effect_type"),
            self._capabilities.get("probed"),
        )

        return detected

    async def stop(self) -> None:
        """Stop the device and clean up."""
        if self._disconnect_timer:
            self._disconnect_timer.cancel()
            self._disconnect_timer = None

        await self._disconnect()
        self._callbacks.clear()
