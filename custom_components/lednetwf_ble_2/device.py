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
    convert_brightness_from_adv,
    convert_speed_from_adv,
    SYMPHONY_SCENE_EFFECTS,
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

        # Background color state (for devices that support it - 0x56, 0x80)
        self._bg_rgb: tuple[int, int, int] | None = None
        self._bg_brightness: int = 255  # 0-255

        # LED settings (for addressable strips)
        self._led_count: int | None = None
        self._led_type: int | None = None
        self._color_order: int | None = None
        self._segments: int | None = None
        self._direction: int | None = None  # 0 = forward, 1 = reverse
        self._pending_led_settings_response: asyncio.Event | None = None

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
    def effect_type(self) -> EffectType:
        """Return the effect type as proper enum (handles int conversion)."""
        val = self._capabilities.get("effect_type", EffectType.NONE)
        return EffectType(val) if isinstance(val, int) else val

    @property
    def effect_list(self) -> list[str]:
        """Return list of available effects."""
        return get_effect_list(self.effect_type, self.has_bg_color, self.has_ic_config)

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
        return self.effect_type != EffectType.NONE

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
        """Return LED count per segment for addressable strips."""
        return self._led_count

    @property
    def segments(self) -> int | None:
        """Return number of segments for addressable strips."""
        return self._segments

    @property
    def total_leds(self) -> int | None:
        """Return total LED count (led_count × segments)."""
        if self._led_count is not None and self._segments is not None:
            return self._led_count * self._segments
        return self._led_count

    @property
    def has_bg_color(self) -> bool:
        """Return True if device supports background color.

        Background color is supported on 0x56 and 0x80 devices for static effects.
        These devices use the 0x41 command format which includes both foreground
        and background RGB colors.
        """
        return bool(self._capabilities.get("has_bg_color"))

    @property
    def has_ic_config(self) -> bool:
        """Return True if device supports IC configuration.

        True Symphony devices (0xA1-0xAD) have IC configuration capability.
        This distinguishes them from 0x56/0x80 devices which also use Symphony
        effect type but have different effect sets.
        """
        return bool(self._capabilities.get("has_ic_config"))

    @property
    def has_color_order(self) -> bool:
        """Return True if device supports color order configuration.

        SIMPLE devices like 0x33 (Ctrl_Mini_RGB) support color order via 0x62 command.
        Color order is stored in byte 4 upper nibble of state response.
        """
        return bool(self._capabilities.get("has_color_order"))

    @property
    def color_order(self) -> int | None:
        """Return current color order (1=RGB, 2=GRB, 3=BRG)."""
        return self._color_order

    @property
    def bg_rgb_color(self) -> tuple[int, int, int] | None:
        """Return background RGB color."""
        return self._bg_rgb

    @property
    def bg_brightness(self) -> int:
        """Return background brightness (0-255)."""
        return self._bg_brightness

    @property
    def bg_effect_list(self) -> list[str]:
        """Return list of effects that support background color.

        For 0x56/0x80 devices: Static Effects 2-10
        For Symphony devices (has_ic_config): Settled Mode effects 2-10
        """
        if not self.has_bg_color:
            return []

        if self.effect_type == EffectType.SYMPHONY and self.has_ic_config:
            # True Symphony devices: Settled Mode effects 2-10 support FG+BG colors
            # Effect 1 ("Solid Color") does NOT support background color
            from .const import SYMPHONY_SETTLED_EFFECTS, SYMPHONY_SETTLED_BG_EFFECTS
            return [SYMPHONY_SETTLED_EFFECTS[i] for i in SYMPHONY_SETTLED_BG_EFFECTS
                    if i in SYMPHONY_SETTLED_EFFECTS]
        elif self.has_bg_color:
            # 0x56/0x80 devices: Static Effects 2-10
            return [f"Static Effect {i}" for i in range(2, 11)]
        return []

    def is_bg_color_available(self) -> bool:
        """Return True if background color can be set for current effect.

        For 0x56/0x80 devices: Static Effects 2-10
        For Symphony devices (has_ic_config): Settled Mode effects 2-10
        Not available for: solid color mode, other effects, or sound reactive.
        """
        if not self.has_bg_color:
            return False
        if self._effect is None:
            return False

        if self.effect_type == EffectType.SYMPHONY:
            # Symphony devices: check if current effect is in bg_color supported list
            return self._effect in self.bg_effect_list
        else:
            # 0x56/0x80 devices: check for Static Effect prefix
            return self._effect.startswith("Static Effect")

    def is_in_settled_effect(self) -> bool:
        """Return True if device is currently in a Settled Mode effect.

        Settled Mode effects (1-10) use 0x41 command with FG+BG colors.
        When in Settled Mode, color changes should update FG/BG via 0x41
        rather than exiting to solid color mode.

        Returns True for Symphony devices (has_ic_config) running:
        - "Solid Color" (effect 1)
        - "Static Effect 2-10" (effects 2-10)
        """
        if not self.has_ic_config:
            return False
        if self._effect is None:
            return False
        if self.effect_type != EffectType.SYMPHONY:
            return False

        from .const import SYMPHONY_SETTLED_EFFECTS
        return self._effect in SYMPHONY_SETTLED_EFFECTS.values()

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

        # Check for JSON-wrapped response (starts with '{' = 0x7B)
        # Some devices wrap state responses in JSON: {"code":0,"payload":"hex_string"}
        if payload[0] == 0x7B:  # '{'
            payload = self._unwrap_json_payload(payload)
            if not payload:
                return

        # Format payload as 0xNN
        payload_hex = ' '.join(f'0x{b:02X}' for b in payload)
        _LOGGER.debug("Notification payload (%d bytes): %s", len(payload), payload_hex)

        # Parse based on first byte (or first two bytes for status+type responses)
        if payload[0] == 0x81:
            self._parse_state_response(payload)
        elif payload[0] == 0x63:
            self._parse_led_settings_response(payload)
        elif len(payload) >= 2 and payload[0] == 0x00 and payload[1] == 0x63:
            # LED settings response with leading status byte (0x00 = success)
            # Format: [0x00 status] [0x63 type] [data...]
            # Pass from byte 1 onwards so parser sees 0x63 as first byte
            _LOGGER.debug("LED settings response with status byte prefix")
            self._parse_led_settings_response(payload[1:])
        else:
            _LOGGER.debug("Unknown notification type: 0x%02X", payload[0])

    def _unwrap_json_payload(self, payload: bytes) -> bytes | None:
        """Extract hex payload from JSON-wrapped notification.

        Some devices (especially older ones or during setup) wrap responses in JSON:
        {"code":0,"payload":"8133242B231DED00ED000A000F36"}

        The payload field contains the actual state response as a hex string.

        Source: Android UpperTransportLayer.java, Result.java
        """
        try:
            # Decode as UTF-8 and parse JSON
            json_str = payload.decode("utf-8", errors="ignore")
            _LOGGER.debug("JSON-wrapped notification: %s", json_str)

            import json
            data = json.loads(json_str)

            # Check for error code
            code = data.get("code", 0)
            if code != 0:
                _LOGGER.warning("JSON notification error code: %d", code)

            # Extract hex payload string
            hex_payload = data.get("payload", "")
            if not hex_payload:
                _LOGGER.debug("JSON notification has no payload")
                return None

            # Convert hex string to bytes
            return bytes.fromhex(hex_payload)

        except (json.JSONDecodeError, ValueError) as ex:
            # Fallback: try old format where payload is just quoted hex
            # e.g., some responses are just "8133242B..."
            _LOGGER.debug("JSON parse failed (%s), trying quoted hex extraction", ex)
            return self._extract_quoted_hex(payload)

    def _extract_quoted_hex(self, payload: bytes) -> bytes | None:
        """Extract hex from quoted string (old format fallback).

        Old devices might send: "8133242B231DED00ED000A000F36"
        This extracts the content between the last pair of quotes.

        Source: model_0x53.py notification_handler()
        """
        try:
            text = payload.decode("utf-8", errors="ignore")
            last_quote = text.rfind('"')
            if last_quote > 0:
                first_quote = text.rfind('"', 0, last_quote)
                if first_quote >= 0:
                    hex_str = text[first_quote + 1:last_quote]
                    # Validate it's all hex characters
                    if all(c in "0123456789abcdefABCDEF" for c in hex_str):
                        _LOGGER.debug("Extracted quoted hex: %s", hex_str)
                        return bytes.fromhex(hex_str)
            _LOGGER.debug("Could not extract quoted hex from: %s", text[:100])
            return None
        except (UnicodeDecodeError, ValueError) as ex:
            _LOGGER.debug("Quoted hex extraction failed: %s", ex)
            return None

    def _parse_state_response(self, data: bytes) -> None:
        """Parse 0x81 state response.

        Brightness handling per mode (from model_0x53.py):
        - RGB mode: derive from RGB via HSV conversion (V component)
        - White mode: from value1 (byte 5), scaled 0-100 → 0-255
        - Effect mode: from byte 6 (R position), scaled 0-100 → 0-255
        """
        result = protocol.parse_state_response(data)
        if not result:
            return

        # Store for probing
        self._last_state_response = result

        # Signal waiting coroutine if any
        if self._pending_state_response:
            self._pending_state_response.set()

        self._is_on = result["is_on"]

        # Debug: trace which condition will match
        _LOGGER.debug(
            "State parse conditions: is_effect=%s, is_white=%s, is_rgb=%s, "
            "has_ic_config=%s, effect_type=%s (SIMPLE=%s), mode_type=0x%02X",
            result.get("is_effect_mode"), result.get("is_white_mode"), result.get("is_rgb_mode"),
            self.has_ic_config, self.effect_type, self.effect_type == EffectType.SIMPLE,
            result["mode_type"]
        )

        # Handle different modes
        if result.get("is_effect_mode"):
            # Effect mode (mode_type=0x25) - this is Function Mode for Symphony devices
            # For has_ic_config devices, effect_id 1-100 are Function Mode effects
            # NOT Settled Mode effects (which report mode_type=0x61)
            if self.has_ic_config:
                # Function Mode effects: use SYMPHONY_EFFECTS directly (bypass _effect_id_to_name)
                from .const import SYMPHONY_EFFECTS
                self._effect = SYMPHONY_EFFECTS.get(result["effect_id"])
            else:
                self._effect = self._effect_id_to_name(result["effect_id"])
            self._color_temp_kelvin = None

            if self.effect_type == EffectType.SYMPHONY and self.has_ic_config:
                # True Symphony devices (0xA1-0xAD) effect mode:
                # - Brightness in byte 6 (R position), 1-100 scale
                # - Speed in byte 5 (value1), stored as speed_byte × 3
                # - speed_byte is 1-31 (1=slow, 31=fast)
                brightness_pct = result["r"] if result["r"] > 0 else 100
                self._brightness = int(brightness_pct * 255 / 100)
                # Convert speed: value1 = speed_byte × 3, speed_byte is 1-31 (1=slow, 31=fast)
                raw_value1 = result["value1"]
                if raw_value1 > 0:
                    speed_byte = raw_value1 // 3
                    # Clamp to valid range 1-31
                    speed_byte = max(1, min(31, speed_byte))
                    self._effect_speed = int((speed_byte - 1) * 100 / 30)
                else:
                    self._effect_speed = 50
            else:
                # ADDRESSABLE_0x53 and others:
                # - Brightness from byte 6 (R position), 0-100 scale
                # - Speed from byte 7 (G position), 0-100 scale
                self._brightness = int(result["r"] * 255 / 100) if result["r"] <= 100 else result["r"]
                self._effect_speed = result["g"] if result["g"] <= 100 else int(result["g"] * 100 / 255)

            _LOGGER.debug("Effect mode: effect_id=%s, brightness=%d, speed=%d (value1=%d, r=%d, g=%d)",
                          result["effect_id"], self._brightness, self._effect_speed,
                          result["value1"], result["r"], result["g"])

        elif result.get("is_white_mode"):
            # White/CCT mode - brightness from value1 (byte 5), scaled 0-100 → 0-255
            self._effect = None
            self._rgb = None
            self._brightness = int(result["value1"] * 255 / 100)
            # Color temp from byte 9 (ww position), 0-100%
            # Per protocol: 0% = 2700K (warm), 100% = 6500K (cool)
            temp_pct = result["ww"]
            self._color_temp_kelvin = int(MIN_KELVIN + temp_pct * (MAX_KELVIN - MIN_KELVIN) / 100)
            _LOGGER.debug("White mode: brightness=%d (value1=%d), color_temp=%dK (pct=%d)",
                          self._brightness, result["value1"], self._color_temp_kelvin, temp_pct)

        elif (self.effect_type == EffectType.SIMPLE and
              result["mode_type"] == 0x61):
            # SIMPLE devices: mode_type=0x61 is RGB mode regardless of sub_mode
            # sub_mode often echoes power state (0x23=ON, 0x24=OFF) rather than mode info
            # Must check BEFORE is_rgb_mode since SIMPLE sub_modes don't match standard RGB sub_modes
            self._color_temp_kelvin = None
            # Don't clear effect for SIMPLE devices - they report 0x61 even when running effects

            # Extract color order from upper nibble if device supports it
            if self.has_color_order and "color_order_nibble" in result:
                color_order = result["color_order_nibble"]
                if 1 <= color_order <= 3:  # Valid range: 1=RGB, 2=GRB, 3=BRG
                    self._color_order = color_order

            r, g, b = result["r"], result["g"], result["b"]
            h, s, v = protocol.rgb_to_hsv(r, g, b)
            brightness_raw = round(v * 255 / 100)
            if brightness_raw == 0 and (r > 0 or g > 0 or b > 0):
                brightness_raw = 1
            self._brightness = brightness_raw

            if v > 0 or (r > 0 or g > 0 or b > 0):
                max_rgb = max(r, g, b)
                if max_rgb > 0:
                    scale = 255 / max_rgb
                    pure_r = min(255, int(round(r * scale)))
                    pure_g = min(255, int(round(g * scale)))
                    pure_b = min(255, int(round(b * scale)))
                    self._rgb = (pure_r, pure_g, pure_b)
                else:
                    self._rgb = (r, g, b)
            else:
                self._rgb = (r, g, b)

            _LOGGER.debug("SIMPLE RGB mode (0x61/0x%02X): device_rgb=(%d,%d,%d), pure_rgb=%s, brightness=%d, color_order=%s",
                          result["sub_mode"], r, g, b, self._rgb, self._brightness, self._color_order)

        elif result.get("is_rgb_mode"):
            # RGB mode - brightness derived from RGB via HSV conversion
            self._effect = None
            self._color_temp_kelvin = None
            r, g, b = result["r"], result["g"], result["b"]
            # Device returns RGB pre-scaled by brightness. Extract H, S, V
            # then reconstruct "pure" color at full brightness for the color picker.
            h, s, v = protocol.rgb_to_hsv(r, g, b)
            # v is 0-100, convert to 0-255 for brightness
            # Use round() and ensure non-zero RGB gives at least brightness 1
            # to prevent 0% brightness issues when device is at very low brightness
            brightness_raw = round(v * 255 / 100)
            if brightness_raw == 0 and (r > 0 or g > 0 or b > 0):
                brightness_raw = 1  # Ensure non-zero RGB has at least brightness 1
            self._brightness = brightness_raw
            # Reconstruct pure RGB at V=100 (full brightness) for color picker
            if v > 0 or (r > 0 or g > 0 or b > 0):
                # Even if v rounds to 0, we can compute pure color from raw RGB
                max_rgb = max(r, g, b)
                if max_rgb > 0:
                    scale = 255 / max_rgb
                    pure_r = min(255, int(round(r * scale)))
                    pure_g = min(255, int(round(g * scale)))
                    pure_b = min(255, int(round(b * scale)))
                    self._rgb = (pure_r, pure_g, pure_b)
                else:
                    self._rgb = (r, g, b)
            else:
                # If all RGB are 0, keep as-is
                self._rgb = (r, g, b)
            _LOGGER.debug("RGB mode: device_rgb=(%d,%d,%d), pure_rgb=%s, brightness=%d (from HSV h=%d, s=%d, v=%d)",
                          r, g, b, self._rgb, self._brightness, h, s, v)

        elif (self.has_ic_config and
              result["mode_type"] == 0x61 and
              1 <= result["sub_mode"] <= 10):
            # Settled Mode effect for Symphony devices (has_ic_config)
            # mode_type=0x61 with sub_mode=1-10 indicates Settled effect
            # RGB contains the foreground color
            from .const import SYMPHONY_SETTLED_EFFECTS
            effect_id = result["sub_mode"]
            self._effect = SYMPHONY_SETTLED_EFFECTS.get(effect_id)
            self._color_temp_kelvin = None

            r, g, b = result["r"], result["g"], result["b"]
            # Derive brightness from RGB via HSV
            h, s, v = protocol.rgb_to_hsv(r, g, b)
            brightness_raw = round(v * 255 / 100)
            if brightness_raw == 0 and (r > 0 or g > 0 or b > 0):
                brightness_raw = 1
            self._brightness = brightness_raw

            # Reconstruct pure RGB for color picker
            if v > 0 or (r > 0 or g > 0 or b > 0):
                max_rgb = max(r, g, b)
                if max_rgb > 0:
                    scale = 255 / max_rgb
                    pure_r = min(255, int(round(r * scale)))
                    pure_g = min(255, int(round(g * scale)))
                    pure_b = min(255, int(round(b * scale)))
                    self._rgb = (pure_r, pure_g, pure_b)
                else:
                    self._rgb = (r, g, b)
            else:
                self._rgb = (r, g, b)

            # Speed from value1 (if available)
            if result["value1"] > 0:
                self._effect_speed = min(100, result["value1"])

            _LOGGER.debug("Settled effect mode: effect=%s (id=%d), fg_rgb=%s, pure_rgb=%s, brightness=%d, speed=%d",
                          self._effect, effect_id, (r, g, b), self._rgb, self._brightness, self._effect_speed)

        else:
            # Unknown mode - use raw values with same HSV reconstruction
            # For SIMPLE devices, DON'T clear effect state from unknown mode responses.
            # SIMPLE devices report mode_type=0x61 even when running effects, so we
            # can't reliably detect effect mode from state response. Keep the commanded
            # effect state instead of clearing it.
            if self.effect_type != EffectType.SIMPLE:
                self._effect = None

            r, g, b = result["r"], result["g"], result["b"]
            # Device returns RGB pre-scaled by brightness. Extract H, S, V
            h, s, v = protocol.rgb_to_hsv(r, g, b)

            # For SIMPLE devices, DON'T update brightness from state response.
            # SIMPLE devices report scaled RGB values (RGB * brightness), so deriving
            # brightness from HSV creates a feedback loop where brightness gradually
            # decreases due to small variations in device-reported values.
            # Keep the user's commanded brightness instead.
            if self.effect_type != EffectType.SIMPLE:
                self._brightness = int(v * 255 / 100) if v > 0 else 255

            # Reconstruct pure RGB at V=100 for color picker
            if v > 0:
                pure_r, pure_g, pure_b = protocol.hsv_to_rgb(h, s, 100)
                self._rgb = (pure_r, pure_g, pure_b)
            else:
                self._rgb = (r, g, b)
            _LOGGER.debug("Unknown mode (0x%02X/0x%02X): device_rgb=(%d,%d,%d), pure_rgb=%s, brightness=%d (SIMPLE=%s, effect=%s)",
                          result["mode_type"], result["sub_mode"], r, g, b, self._rgb, self._brightness,
                          self.effect_type == EffectType.SIMPLE, self._effect)

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
        self._segments = result.get("segments")
        self._direction = result.get("direction")

        _LOGGER.debug(
            "Parsed LED settings: count=%s, segments=%s, type=%s, order=%s, direction=%s",
            self._led_count, self._segments, self._led_type, self._color_order, self._direction
        )

        # Signal waiting coroutine if any
        if self._pending_led_settings_response:
            self._pending_led_settings_response.set()

    def _effect_id_to_name(self, effect_id: int) -> str | None:
        """Convert effect ID to name.

        Must be consistent with get_effect_list() and get_effect_id() in const.py.
        """
        eff_type = self.effect_type

        if eff_type == EffectType.SIMPLE:
            from .const import SIMPLE_EFFECTS
            return SIMPLE_EFFECTS.get(effect_id)
        elif eff_type == EffectType.SYMPHONY:
            if self.has_ic_config:
                # True Symphony devices (0xA1-0xAD):
                # - Settled Mode effects (1-10) via 0x41 command
                # - Function Mode effects (1-100) via 0x42 command
                # For IDs 1-10, check Settled effects first, then Function Mode
                from .const import SYMPHONY_SETTLED_EFFECTS, SYMPHONY_EFFECTS
                if effect_id <= 10:
                    name = SYMPHONY_SETTLED_EFFECTS.get(effect_id)
                    if name:
                        return name
                # Fall through to Function Mode for IDs 1-100
                return SYMPHONY_EFFECTS.get(effect_id)
            elif self.has_bg_color:
                # 0x56/0x80 devices: Static effects, strip effects, or sound reactive
                from .const import STATIC_EFFECTS_WITH_BG, STRIP_EFFECTS, SOUND_REACTIVE_EFFECTS
                if effect_id <= 10:
                    return STATIC_EFFECTS_WITH_BG.get(effect_id)
                elif effect_id <= 99:
                    return STRIP_EFFECTS.get(effect_id)
                elif effect_id == 255:
                    return "Cycle Modes"
                # Sound reactive would be decoded differently, but we store raw ID
                return f"Effect {effect_id}"
            else:
                # Fallback: use Scene Effects (named effects 1-44)
                from .const import SYMPHONY_SCENE_EFFECTS
                if effect_id <= 44:
                    return SYMPHONY_SCENE_EFFECTS.get(effect_id)
                elif effect_id >= 100:
                    return f"Build Effect {effect_id - 99}"
        elif eff_type == EffectType.ADDRESSABLE_0x53:
            from .const import ADDRESSABLE_0x53_EFFECTS
            return ADDRESSABLE_0x53_EFFECTS.get(effect_id)
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

        For devices in Settled Mode effects (Symphony has_ic_config), changing color
        updates the foreground color via 0x41 command while staying in the effect.
        To exit effect mode, select a non-Settled effect from the effects list.
        """
        if not self.has_rgb:
            _LOGGER.warning("Device %s does not support RGB", self._name)
            return False

        # Check if we're in a Settled Mode effect
        # If so, update FG color via 0x41 command with the current effect_id
        if self.is_in_settled_effect():
            # Get the actual effect_id from the current effect name
            from .const import SYMPHONY_SETTLED_EFFECTS
            effect_id = None
            for eid, name in SYMPHONY_SETTLED_EFFECTS.items():
                if name == self._effect:
                    effect_id = eid
                    break

            if effect_id is None:
                effect_id = 1  # Fallback to Solid Color

            # Scale FG color by brightness
            scale = brightness / 255.0
            fg_rgb = (
                int(rgb[0] * scale),
                int(rgb[1] * scale),
                int(rgb[2] * scale),
            )

            # Get current BG color (scaled by bg_brightness)
            if self._bg_rgb:
                bg_scale = self._bg_brightness / 255.0
                bg_rgb = (
                    int(self._bg_rgb[0] * bg_scale),
                    int(self._bg_rgb[1] * bg_scale),
                    int(self._bg_rgb[2] * bg_scale),
                )
            else:
                bg_rgb = (0, 0, 0)

            packet = protocol.build_static_effect_command_0x41(
                effect_id, fg_rgb, bg_rgb, self._effect_speed
            )

            _LOGGER.debug(
                "Updating FG color in Settled effect %s (id=%d): fg=%s, bg=%s, speed=%d",
                self._effect, effect_id, fg_rgb, bg_rgb, self._effect_speed
            )

            if await self._send_command(packet):
                self._rgb = rgb
                self._brightness = brightness
                # Keep self._effect - stay in current effect mode
                self._color_temp_kelvin = None
                self._notify_callbacks()
                return True
            return False

        # Standard color command (exits effect mode)
        eff_type = self.effect_type
        if eff_type == EffectType.SIMPLE:
            # SIMPLE devices use 0x31 command format (9-byte RGB)
            # Brightness is applied directly to RGB values (no separate brightness field)
            # Scale RGB by brightness factor
            scale = brightness / 255.0
            scaled_r = int(rgb[0] * scale)
            scaled_g = int(rgb[1] * scale)
            scaled_b = int(rgb[2] * scale)

            _LOGGER.debug(
                "SIMPLE device: RGB=(%d,%d,%d), brightness=%d -> scaled RGB=(%d,%d,%d)",
                rgb[0], rgb[1], rgb[2], brightness, scaled_r, scaled_g, scaled_b
            )

            packet = protocol.build_color_command_0x31(scaled_r, scaled_g, scaled_b)
        else:
            # Symphony and Addressable devices use 0x3B command format (HSV-based)
            # Convert brightness to 0-100 for protocol
            # Use max(1, ...) to prevent 0% brightness from turning off the light
            # when user has very low but non-zero brightness (e.g., 2 out of 255)
            brightness_pct = max(1, round(brightness * 100 / 255)) if brightness > 0 else 0

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

        eff_type = self.effect_type
        kelvin = max(MIN_KELVIN, min(MAX_KELVIN, kelvin))

        if eff_type == EffectType.SIMPLE:
            # SIMPLE devices use 0x31 command format with WW/CW channels
            # Convert kelvin to WW/CW values (brightness is applied to channel values)
            ww, cw = protocol.kelvin_to_ww_cw(kelvin, brightness)
            _LOGGER.debug(
                "SIMPLE device CCT: kelvin=%d, brightness=%d -> WW=%d, CW=%d",
                kelvin, brightness, ww, cw
            )
            packet = protocol.build_color_command_0x31(0, 0, 0, ww, cw)
        else:
            # Symphony and Addressable devices use 0x3B B1 command format
            # (temperature percentage + brightness percentage)
            # Per working old code: 0% = warm/2700K, 100% = cool/6500K
            temp_pct = int((kelvin - MIN_KELVIN) * 100 / (MAX_KELVIN - MIN_KELVIN))
            # Use max(1, ...) to prevent 0% brightness from turning off the light
            brightness_pct = max(1, round(brightness * 100 / 255)) if brightness > 0 else 0

            packet = protocol.build_cct_command_0x3B(temp_pct, brightness_pct)
            _LOGGER.debug("Setting CCT: kelvin=%d, temp_pct=%d%% (0=warm, 100=cool), brightness_pct=%d%%",
                          kelvin, temp_pct, brightness_pct)

        if await self._send_command(packet):
            self._color_temp_kelvin = kelvin
            self._brightness = brightness
            self._effect = None
            self._rgb = None
            self._notify_callbacks()
            return True
        return False

    async def set_effect(
        self, effect_name: str, speed: int | None = None, brightness: int | None = None
    ) -> bool:
        """Set an effect by name.

        Args:
            effect_name: Effect name from effect_list
            speed: Effect speed 0-100 (or None to use current)
            brightness: Brightness 0-255 (or None to use current)
        """
        if not self.has_effects:
            _LOGGER.warning("Device %s does not support effects", self._name)
            return False

        eff_type = self.effect_type
        effect_id = get_effect_id(effect_name, eff_type, self.has_bg_color, self.has_ic_config)

        if effect_id is None:
            _LOGGER.warning("Unknown effect: %s", effect_name)
            return False

        if speed is None:
            speed = self._effect_speed if self._effect_speed > 0 else 50

        if brightness is None:
            brightness = self._brightness

        # Ensure we have a valid brightness (0 = power off for some devices!)
        if brightness <= 0:
            brightness = 255  # Default to full brightness

        # Convert brightness from 0-255 to 0-100 for protocol
        brightness_pct = max(1, round(brightness * 100 / 255))

        # Get FG and BG colors for static effects
        fg_rgb = None
        bg_rgb = None
        if self.has_bg_color:
            # Get foreground color (scaled by brightness)
            if self._rgb:
                scale = brightness / 255.0
                fg_rgb = (
                    int(self._rgb[0] * scale),
                    int(self._rgb[1] * scale),
                    int(self._rgb[2] * scale),
                )
            else:
                fg_rgb = (255, 255, 255)  # Default white

            # Get background color (scaled by bg_brightness)
            if self._bg_rgb:
                scale = self._bg_brightness / 255.0
                bg_rgb = (
                    int(self._bg_rgb[0] * scale),
                    int(self._bg_rgb[1] * scale),
                    int(self._bg_rgb[2] * scale),
                )
            else:
                # No background color set yet - default to black
                # Sync bg_brightness with foreground so when user first picks
                # a BG color, it will match the foreground brightness
                self._bg_brightness = brightness
                bg_rgb = (0, 0, 0)

        # Note: speed is already 0-100, protocol expects 0-100 for most devices
        packet = protocol.build_effect_command(
            eff_type, effect_id, speed, brightness_pct,
            has_bg_color=self.has_bg_color,
            has_ic_config=self.has_ic_config,
            fg_rgb=fg_rgb,
            bg_rgb=bg_rgb,
        )
        if packet is None:
            return False

        _LOGGER.debug(
            "Setting effect: %s (id=%d), speed=%d, brightness=%d%% (effect_type=%s)",
            effect_name, effect_id, speed, brightness_pct, eff_type.name
        )

        if await self._send_command(packet):
            self._effect = effect_name
            self._effect_speed = speed
            self._brightness = brightness
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

    async def set_bg_color(
        self, rgb: tuple[int, int, int], brightness: int = 255
    ) -> bool:
        """Set background color for static effects.

        Only works on devices that support background color (0x56, 0x80, Symphony)
        and only when running a static effect (2-10).

        Args:
            rgb: Background RGB color tuple (0-255)
            brightness: Background brightness (0-255)
        """
        if not self.has_bg_color:
            _LOGGER.warning("Device %s does not support background color", self._name)
            return False

        if not self.is_bg_color_available():
            _LOGGER.warning(
                "Background color only available for static effects. Current: %s",
                self._effect,
            )
            return False

        # Get the actual effect_id from the current effect name
        effect_id = None
        if self.is_in_settled_effect():
            from .const import SYMPHONY_SETTLED_EFFECTS
            for eid, name in SYMPHONY_SETTLED_EFFECTS.items():
                if name == self._effect:
                    effect_id = eid
                    break
        if effect_id is None:
            # Fallback: try to extract from effect name like "Static Effect 3"
            if self._effect and self._effect.startswith("Static Effect "):
                try:
                    effect_id = int(self._effect.split()[-1])
                except ValueError:
                    effect_id = 2  # Default to Static Effect 2
            else:
                effect_id = 2  # Default

        # Scale BG RGB by brightness
        scale = brightness / 255.0
        scaled_r = int(rgb[0] * scale)
        scaled_g = int(rgb[1] * scale)
        scaled_b = int(rgb[2] * scale)
        bg_rgb = (scaled_r, scaled_g, scaled_b)

        # Get current foreground color (also scaled)
        fg_scale = self._brightness / 255.0 if self._brightness else 1.0
        if self._rgb:
            fg_rgb = (
                int(self._rgb[0] * fg_scale),
                int(self._rgb[1] * fg_scale),
                int(self._rgb[2] * fg_scale),
            )
        else:
            fg_rgb = (255, 255, 255)  # Default white

        packet = protocol.build_static_effect_command_0x41(
            effect_id, fg_rgb, bg_rgb, self._effect_speed
        )

        _LOGGER.debug(
            "Setting background color in effect %s (id=%d): BG=(%d,%d,%d), "
            "brightness=%d, scaled=(%d,%d,%d), fg=(%d,%d,%d)",
            self._effect, effect_id,
            rgb[0], rgb[1], rgb[2], brightness,
            scaled_r, scaled_g, scaled_b,
            fg_rgb[0], fg_rgb[1], fg_rgb[2],
        )

        if await self._send_command(packet):
            self._bg_rgb = rgb
            self._bg_brightness = brightness
            self._notify_callbacks()
            return True
        return False

    async def query_state(self) -> bool:
        """Query current device state."""
        packet = protocol.build_state_query()
        return await self._send_command(packet)

    async def query_state_and_wait(self, timeout: float = 3.0) -> dict | None:
        """Query device state and wait for response.

        This sends a state query and waits for the response. The notification
        handler will update all internal state (is_on, brightness, rgb, effect,
        color_order, etc.) when the response is received.

        Args:
            timeout: Maximum seconds to wait for response

        Returns:
            Parsed state response dict, or None if timeout/error
        """
        return await self._query_state_and_wait(timeout)

    async def query_led_settings(self) -> bool:
        """Query LED settings (for addressable strips)."""
        packet = protocol.build_led_settings_query()
        return await self._send_command(packet)

    async def query_led_settings_and_wait(self, timeout: float = 3.0) -> dict | None:
        """Query LED settings and wait for response.

        Args:
            timeout: Maximum seconds to wait for response

        Returns:
            Dict with led_count, ic_type, color_order, segments, direction
            or None if timeout/error
        """
        self._pending_led_settings_response = asyncio.Event()

        try:
            if not await self.query_led_settings():
                return None

            try:
                await asyncio.wait_for(
                    self._pending_led_settings_response.wait(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout waiting for LED settings response")
                return None

            # Return the captured settings
            if self._led_count is not None:
                return {
                    "led_count": self._led_count,
                    "ic_type": self._led_type,
                    "color_order": self._color_order,
                    "segments": self._segments,
                    "direction": self._direction,
                }
            return None
        finally:
            self._pending_led_settings_response = None

    async def set_led_settings(
        self,
        led_count: int,
        led_type: int,
        color_order: int,
        segments: int = 1,
    ) -> bool:
        """Set LED settings for addressable strips.

        Args:
            led_count: LEDs per segment
            led_type: IC type (see LedType enum)
            color_order: RGB ordering (see ColorOrder enum)
            segments: Number of segments (for IC config devices)

        For devices with has_ic_config (Symphony A3+), uses the A3 format
        which includes segment support. Other devices use the original format.
        """
        if self.has_ic_config:
            # A3+ format with segment support
            packet = protocol.build_led_settings_command_a3(
                led_count, segments, led_type, color_order
            )
        else:
            # Original format without segments
            packet = protocol.build_led_settings_command(led_count, led_type, color_order)

        if await self._send_command(packet):
            self._led_count = led_count
            self._led_type = led_type
            self._color_order = color_order
            self._segments = segments
            return True
        return False

    async def set_color_order(self, color_order: int) -> bool:
        """Set color order for SIMPLE devices (0x33, etc.).

        Args:
            color_order: 1=RGB, 2=GRB, 3=BRG

        Returns:
            True if command was sent successfully
        """
        if not self.has_color_order:
            _LOGGER.warning("Device %s does not support color order configuration", self._name)
            return False

        packet = protocol.build_color_order_command_simple(color_order)

        if await self._send_command(packet):
            self._color_order = color_order
            _LOGGER.debug("Set color order to %d for %s", color_order, self._name)
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
        result = protocol.parse_manufacturer_data(manu_data, self._name)
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
            if rgb:
                # Device returns RGB pre-scaled by brightness. Extract H, S, V
                # then reconstruct "pure" color at full brightness for the color picker.
                r, g, b = rgb
                h, s, v = protocol.rgb_to_hsv(r, g, b)
                # v is 0-100, convert to 0-255 for brightness
                new_brightness = int(v * 255 / 100)
                # Reconstruct pure RGB at V=100 (full brightness) for color picker
                if v > 0:
                    pure_r, pure_g, pure_b = protocol.hsv_to_rgb(h, s, 100)
                    pure_rgb = (pure_r, pure_g, pure_b)
                else:
                    pure_rgb = rgb

                if pure_rgb != self._rgb or new_brightness != self._brightness:
                    self._rgb = pure_rgb
                    self._brightness = new_brightness
                    self._color_temp_kelvin = None  # Clear CCT when in RGB mode
                    self._effect = None  # Clear effect when in RGB mode
                    changed = True
                    _LOGGER.debug("Advertisement updated RGB: device_rgb=(%d,%d,%d), pure_rgb=%s, brightness=%d (HSV v=%d)",
                                  r, g, b, self._rgb, self._brightness, v)

        elif color_mode == "cct":
            # CCT/White mode - update color temperature
            temp_pct = result.get("color_temp_percent")
            bright_pct = result.get("brightness_percent")

            if temp_pct is not None:
                # Convert percent to Kelvin
                # Per working old code: 0% = warm/2700K, 100% = cool/6500K
                new_kelvin = int(MIN_KELVIN + temp_pct * (MAX_KELVIN - MIN_KELVIN) / 100)
                if self._color_temp_kelvin != new_kelvin:
                    self._color_temp_kelvin = new_kelvin
                    changed = True

            if bright_pct is not None:
                # Use product_id-based conversion for proper value scaling
                new_brightness = convert_brightness_from_adv(bright_pct, self._product_id)
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
                elif effect_name is None:
                    # Unknown effect ID - log but don't clear effect state
                    _LOGGER.debug("Unknown effect ID %d for effect_type %s",
                                  effect_id, self.effect_type.name)

            if effect_speed is not None:
                # Use product_id-based conversion for proper value scaling
                # This handles inverted speed for 0x54/0x55/0x62/0x5B devices
                new_speed = convert_speed_from_adv(effect_speed, self._product_id)
                if self._effect_speed != new_speed:
                    self._effect_speed = new_speed
                    changed = True

            if bright_pct is not None:
                # Use product_id-based conversion for proper value scaling
                new_brightness = convert_brightness_from_adv(bright_pct, self._product_id)
                if self._brightness != new_brightness:
                    self._brightness = new_brightness
                    changed = True

            if changed:
                _LOGGER.debug("Advertisement updated effect: %s, speed: %d, brightness: %d",
                              self._effect, self._effect_speed, self._brightness)

        elif color_mode == "settled":
            # Settled Mode effect (Symphony devices has_ic_config)
            # This is mode_type=0x61 with sub_mode=1-10
            effect_id = result.get("effect_id")
            effect_speed = result.get("effect_speed")
            rgb = result.get("rgb")

            if effect_id is not None:
                from .const import SYMPHONY_SETTLED_EFFECTS
                effect_name = SYMPHONY_SETTLED_EFFECTS.get(effect_id)
                if effect_name and self._effect != effect_name:
                    self._effect = effect_name
                    changed = True

            if effect_speed is not None:
                new_speed = convert_speed_from_adv(effect_speed, self._product_id)
                if self._effect_speed != new_speed:
                    self._effect_speed = new_speed
                    changed = True

            if rgb:
                # Extract RGB and brightness via HSV
                r, g, b = rgb
                h, s, v = protocol.rgb_to_hsv(r, g, b)
                brightness = round(v * 255 / 100)
                if brightness == 0 and (r > 0 or g > 0 or b > 0):
                    brightness = 1

                # Reconstruct pure RGB at full brightness
                max_rgb = max(r, g, b)
                if max_rgb > 0:
                    scale = 255 / max_rgb
                    pure_r = min(255, int(round(r * scale)))
                    pure_g = min(255, int(round(g * scale)))
                    pure_b = min(255, int(round(b * scale)))
                    pure_rgb = (pure_r, pure_g, pure_b)
                else:
                    pure_rgb = (r, g, b)

                if self._rgb != pure_rgb:
                    self._rgb = pure_rgb
                    changed = True
                if self._brightness != brightness:
                    self._brightness = brightness
                    changed = True

            if changed:
                _LOGGER.debug(
                    "Advertisement updated Settled effect: %s, rgb=%s, speed=%d, brightness=%d",
                    self._effect, self._rgb, self._effect_speed, self._brightness
                )

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

        # Start with unknown capabilities, but PRESERVE effect_type if already known
        # from product_id lookup (don't overwrite ADDRESSABLE_0x53 with SYMPHONY!)
        # By NOT including effect_type in detected, the update() won't overwrite it.
        detected = {
            "has_rgb": False,
            "has_ww": False,
            "has_cw": False,
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
