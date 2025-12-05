"""Protocol layer for LEDnetWF BLE devices.

This module handles:
- Transport layer wrapping (header + payload)
- Command building (power, color, effects, settings)
- Response parsing

Based on protocol documentation in protocol_docs/
"""
from __future__ import annotations

import colorsys
import logging
from typing import Tuple

from .const import EffectType, MIN_KELVIN, MAX_KELVIN, SYMPHONY_BG_COLOR_EFFECTS

_LOGGER = logging.getLogger(__name__)


# =============================================================================
# CHECKSUM
# =============================================================================

def calculate_checksum(data: bytes) -> int:
    """Calculate checksum (sum of all bytes & 0xFF)."""
    return sum(data) & 0xFF


# =============================================================================
# TRANSPORT LAYER
# =============================================================================

def wrap_command(raw_payload: bytes, cmd_family: int = 0x0b, seq: int = 0) -> bytearray:
    """
    Wrap a raw command payload in the transport layer format.

    Header format (8 bytes):
      - Byte 0: Header flags (0x00 for version 0, not segmented)
      - Byte 1: Sequence number (0-255, will be updated by caller)
      - Bytes 2-3: Frag Control (0x80, 0x00 = single complete segment)
      - Bytes 4-5: Total payload length (big-endian)
      - Byte 6: Payload length + 1 (for cmdId)
      - Byte 7: cmdId (0x0a = expects response, 0x0b = no response)

    Args:
        raw_payload: Raw command bytes (including checksum)
        cmd_family: 0x0a for queries, 0x0b for commands
        seq: Sequence number (will be overwritten by device class)

    Returns:
        Complete wrapped packet ready to send
    """
    payload_len = len(raw_payload)

    packet = bytearray(8 + payload_len)
    packet[0] = 0x00                       # Header: version 0, not segmented
    packet[1] = seq & 0xFF                 # Sequence number
    packet[2] = 0x80                       # Frag control high byte
    packet[3] = 0x00                       # Frag control low byte
    packet[4] = (payload_len >> 8) & 0xFF  # Total length high byte
    packet[5] = payload_len & 0xFF         # Total length low byte
    packet[6] = (payload_len + 1) & 0xFF   # Payload length + 1
    packet[7] = cmd_family                 # cmdId

    packet[8:] = raw_payload
    return packet


def unwrap_response(data: bytes) -> bytes | None:
    """
    Extract payload from transport layer response.

    Returns the raw payload without the 8-byte header, or None if invalid.
    """
    if len(data) < 8:
        return None
    # Payload starts at byte 8
    return data[8:]


# =============================================================================
# COLOR CONVERSION
# =============================================================================

def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[int, int, int]:
    """
    Convert RGB (0-255) to HSV (hue 0-360, sat 0-100, val 0-100).
    """
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
    return (int(h * 360), int(s * 100), int(v * 100))


def hsv_to_rgb(h: int, s: int, v: int) -> Tuple[int, int, int]:
    """
    Convert HSV (hue 0-360, sat 0-100, val 0-100) to RGB (0-255).
    """
    r, g, b = colorsys.hsv_to_rgb(h / 360.0, s / 100.0, v / 100.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def kelvin_to_ww_cw(kelvin: int, brightness: int = 255) -> Tuple[int, int]:
    """
    Convert Kelvin color temperature to WW/CW channel values.

    Args:
        kelvin: Color temperature (2700-6500K)
        brightness: Overall brightness (0-255)

    Returns:
        Tuple of (warm_white, cool_white) values (0-255)
    """
    kelvin = max(MIN_KELVIN, min(MAX_KELVIN, kelvin))
    cool_ratio = (kelvin - MIN_KELVIN) / (MAX_KELVIN - MIN_KELVIN)
    warm_ratio = 1.0 - cool_ratio

    ww = int(warm_ratio * brightness)
    cw = int(cool_ratio * brightness)
    return (ww, cw)


# =============================================================================
# POWER COMMANDS
# =============================================================================

def build_power_command_0x3B(turn_on: bool) -> bytearray:
    """
    Build power command using 0x3B format (BLE v5+).

    Format: [0x3B, mode, 0, 0, 0, 0, 0, 0, 0, time_lo, 0, 0, checksum]
    Mode: 0x23 = ON, 0x24 = OFF
    """
    mode = 0x23 if turn_on else 0x24
    raw_cmd = bytearray([
        0x3B, mode,
        0x00, 0x00, 0x00,  # HSV placeholder
        0x00, 0x00,        # Params
        0x00, 0x00, 0x32,  # RGB + time (50ms)
        0x00, 0x00
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_power_command_0x71(turn_on: bool) -> bytearray:
    """
    Build power command using 0x71 format (legacy BLE v1-4).

    Format: [0x71, state, 0x0F, checksum]
    State: 0x23 = ON, 0x24 = OFF
    """
    state = 0x23 if turn_on else 0x24
    raw_cmd = bytearray([0x71, state, 0x0F])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


# =============================================================================
# COLOR COMMANDS
# =============================================================================

def build_color_command_0x3B(r: int, g: int, b: int, brightness: int = 100) -> bytearray:
    """
    Build color command using 0x3B format (BLE v5+, Symphony).

    Uses HSV internally with RGB fallback in bytes 7-9.
    Brightness is 0-100 (percentage).
    """
    h, s, v = rgb_to_hsv(r, g, b)
    # Use provided brightness, capped to 100
    brightness = min(brightness, 100)

    # Pack hue (0-360) and saturation (0-100) into two bytes
    packed = (h << 7) | s
    hs_hi = (packed >> 8) & 0xFF
    hs_lo = packed & 0xFF

    raw_cmd = bytearray([
        0x3B,                  # Command opcode
        0xA1,                  # Mode: solid color
        hs_hi, hs_lo,          # Packed hue + saturation
        brightness & 0xFF,     # Brightness (0-100)
        0x00, 0x00,            # Params
        r & 0xFF, g & 0xFF, b & 0xFF,  # RGB values
        0x00, 0x00,            # Time (0 = instant, matches working old code)
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_color_command_0x31(r: int, g: int, b: int, ww: int = 0, cw: int = 0) -> bytearray:
    """
    Build color command using 0x31 format (9-byte format with WW+CW).

    Source: protocol_docs/07_control_commands.md

    Format (9 bytes): [0x31, R, G, B, WW, CW, mode, persist, checksum]

    Mode byte values:
    - 0xF0 = RGB only mode (whites ignored) - tc.b.t()
    - 0x0F = White only mode (RGB ignored) - tc.b.f()
    - 0x5A = RGBCW mode (all channels) - tc.b.s()

    This function selects the appropriate mode based on channel values.
    """
    # Determine mode based on which channels are active
    has_rgb = (r > 0 or g > 0 or b > 0)
    has_white = (ww > 0 or cw > 0)

    if has_rgb and has_white:
        mode = 0x5A  # RGBCW mode - all channels active
    elif has_white:
        mode = 0x0F  # White only mode
    else:
        mode = 0xF0  # RGB only mode (default)

    raw_cmd = bytearray([
        0x31,
        r & 0xFF, g & 0xFF, b & 0xFF,
        ww & 0xFF, cw & 0xFF,
        mode,
        0x0F,      # Don't persist
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_white_command(ww: int, cw: int) -> bytearray:
    """
    Build white temperature command using 0x31 format (9-byte format).

    Source: protocol_docs/07_control_commands.md - "9-Byte White/CCT Format - tc.b.f()"

    Format: [0x31, 0x00, 0x00, 0x00, WW, CW, 0x0F, persist, checksum]

    Mode byte 0x0F = White only mode (RGB ignored).
    """
    raw_cmd = bytearray([
        0x31,
        0x00, 0x00, 0x00,      # RGB = 0
        ww & 0xFF, cw & 0xFF,  # WW/CW values
        0x0F,                   # Mode: 0x0F = White only mode
        0x0F,                   # Don't persist
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_cct_command_0x3B(temp_percent: int, brightness_percent: int,
                          duration: int = 0) -> bytearray:
    """
    Build CCT temperature command using 0x3B format with mode 0xB1.

    Source: protocol_docs/07_control_commands.md - "CCT Temperature Mode (0xB1)"

    This format is used by Ring Lights (model_0x53) and Symphony devices.
    Alternative to the 0x35 CCT command used by some ceiling lights.

    Format (13 bytes):
    [0x3B, 0xB1, 0x00, 0x00, 0x00, temp%, bright%, 0x00, 0x00, 0x00, time_hi, time_lo, checksum]

    Args:
        temp_percent: 0-100 (0=cool/6500K, 100=warm/2700K)
        brightness_percent: 0-100
        duration: Transition time (default 0 = instant, matches working old code)

    Returns:
        13-byte command packet wrapped in transport layer
    """
    temp_percent = max(0, min(100, temp_percent))
    brightness_percent = max(0, min(100, brightness_percent))

    raw_cmd = bytearray([
        0x3B,                      # Command opcode
        0xB1,                      # Mode: CCT temperature
        0x00, 0x00,                # Hue/Sat (unused)
        0x00,                      # Brightness param (unused for CCT)
        temp_percent & 0xFF,       # Temperature %
        brightness_percent & 0xFF, # Brightness %
        0x00, 0x00, 0x00,          # RGB (unused)
        (duration >> 8) & 0xFF,    # Time high byte
        duration & 0xFF,           # Time low byte
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_cct_command_0x35(temp_percent: int, brightness_percent: int, duration_ms: int = 300) -> bytearray:
    """
    Build CCT temperature command using 0x35 format.

    Source: protocol_docs/07_control_commands.md - "CCT Temperature Command (0x35)"

    Format (9 bytes): [0x35, 0xB1, temp%, brightness%, 0x00, 0x00, duration_hi, duration_lo, checksum]

    Args:
        temp_percent: 0-100 (0=cool/6500K, 100=warm/2700K)
        brightness_percent: 0-100
        duration_ms: Transition duration in milliseconds (default 300ms)

    Note: Used by CCT-only devices (ceiling lights, etc.)
    """
    temp_percent = max(0, min(100, temp_percent))
    brightness_percent = max(0, min(100, brightness_percent))
    duration = duration_ms // 100  # Convert to tenths of seconds

    raw_cmd = bytearray([
        0x35,                          # Command opcode
        0xB1,                          # Sub-command
        temp_percent & 0xFF,           # Temperature percentage
        brightness_percent & 0xFF,     # Brightness percentage
        0x00, 0x00,                    # Reserved
        (duration >> 8) & 0xFF,        # Duration high byte
        duration & 0xFF,               # Duration low byte
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


# =============================================================================
# STATIC EFFECT COMMANDS (with background color support)
# =============================================================================

def build_static_effect_command_0x41(
    effect_id: int,
    fg_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int],
    speed: int = 50,
) -> bytearray:
    """
    Build static effect command with foreground and background colors.

    Used for 0x56 and 0x80 devices that support background color.
    This command format includes both foreground and background RGB colors.

    Source: model_0x56.py set_color() and set_effect() methods

    Format (13 bytes + checksum):
    [0x41, effect_id, FG_R, FG_G, FG_B, BG_R, BG_G, BG_B, speed, 0x00, 0x00, 0xF0, checksum]

    Static Effect IDs:
    - 0 = No change to current effect (useful for just changing colors)
    - 1 = Solid Color (foreground only, no background)
    - 2-10 = Static Effects with foreground + background

    Args:
        effect_id: Static effect ID (0-10)
        fg_rgb: Foreground RGB color tuple (0-255)
        bg_rgb: Background RGB color tuple (0-255)
        speed: Effect speed (0-100)

    Returns:
        Complete command packet wrapped in transport layer
    """
    fg_r, fg_g, fg_b = fg_rgb
    bg_r, bg_g, bg_b = bg_rgb
    speed = max(0, min(100, speed))

    raw_cmd = bytearray([
        0x41,                      # Command opcode
        effect_id & 0xFF,          # Static effect ID (0-10)
        fg_r & 0xFF,               # Foreground R
        fg_g & 0xFF,               # Foreground G
        fg_b & 0xFF,               # Foreground B
        bg_r & 0xFF,               # Background R
        bg_g & 0xFF,               # Background G
        bg_b & 0xFF,               # Background B
        speed & 0xFF,              # Effect speed
        0x00, 0x00,                # Reserved/unknown
        0xF0,                      # Mode flag
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_bg_color_command_0x41(
    fg_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int],
    speed: int = 50,
) -> bytearray:
    """
    Build background color command (0x41 with effect_id=0).

    This sets the background color without changing the current static effect.
    Effect ID 0 means "keep current effect, just update colors".

    Args:
        fg_rgb: Foreground RGB color tuple (0-255)
        bg_rgb: Background RGB color tuple (0-255)
        speed: Effect speed (0-100)

    Returns:
        Complete command packet wrapped in transport layer
    """
    return build_static_effect_command_0x41(0, fg_rgb, bg_rgb, speed)


# =============================================================================
# EFFECT COMMANDS
# =============================================================================

def build_effect_command_0x53(effect_id: int, speed: int = 50, brightness: int = 100) -> bytearray:
    """
    Build addressable effect command for 0x53 devices (Ring Lights, FillLight).

    IMPORTANT: This format uses NO CHECKSUM - only 4 bytes!
    Source: model_0x53.py set_effect() method
    Source: protocol_docs/07_control_commands.md - Variant 2

    Format: [0x38, effect_id, speed, brightness] - NO checksum!
    - effect_id: 1-113 (or 0xFF for cycle all)
    - speed: 0-100 (direct, no conversion - matches old working code)
    - brightness: 0-100 (percentage)

    Product IDs using this format: 0, 29 (FillLight), 83 (per protocol docs)
    """
    # Speed and brightness both 0-100, sent directly (no conversion)
    speed = max(0, min(100, speed))
    brightness = max(0, min(100, brightness))

    raw_cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,  # Brightness 0-100, NOT a checksum!
    ])
    # NO checksum for 0x53 devices!
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_effect_command_0x38(effect_id: int, speed: int = 50, brightness: int = 100) -> bytearray:
    """
    Build Symphony effect command (0x38) WITH checksum.

    Used for Symphony devices (product IDs 0xA1-0xA9, 0x08).
    Scene effects: IDs 1-44

    Format: [0x38, effect_id, speed_byte, brightness, checksum]

    IMPORTANT:
    - brightness must be 1-100 (0 = power off!)
    - speed uses 1-31 scale where 1=slowest, 31=fastest (NOT inverted)
    """
    # Validate effect ID (Scene effects are 1-44)
    effect_id = max(1, min(44, effect_id))

    # Convert speed from 0-100 to 1-31 scale (1=slowest, 31=fastest)
    # Formula: speed_byte = 1 + round(speed_percent * 30 / 100)
    speed_byte = 1 + round(speed * 30 / 100)
    speed_byte = max(1, min(31, speed_byte))

    # Ensure brightness is at least 1 (0 = power off!)
    brightness = max(1, min(100, brightness))

    raw_cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed_byte & 0xFF,
        brightness & 0xFF,
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_effect_command_0x61(effect_id: int, speed: int = 16, persist: bool = False) -> bytearray:
    """
    Build legacy effect command (0x61).

    Used for non-Symphony RGB devices (e.g., product_id 0x33).
    Effect IDs: 37-56 (20 effects)

    Format: [0x61, effect_id, speed, persist, checksum]

    Args:
        effect_id: Effect ID (37-56)
        speed: Protocol speed value 1-31 (INVERTED: 1=fastest, 31=slowest)
               Convert from UI percentage: speed = 1 + int(30 * (1.0 - ui_pct/100))
        persist: If True, save to flash (0xF0), else temporary (0x0F)

    Note: There is NO brightness byte in this command format.
          Brightness must be controlled separately via color commands.
    """
    raw_cmd = bytearray([
        0x61,
        effect_id & 0xFF,
        speed & 0xFF,
        0xF0 if persist else 0x0F,
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_effect_command_0x42(effect_id: int, speed: int = 50, brightness: int = 100) -> bytearray:
    """
    Build strip effect command (0x42) for 0x56/0x80 devices.

    Used for regular (dynamic) effects on strip controllers.
    Effect IDs: 1-99, or 255 for cycle modes

    Format (5 bytes + checksum): [0x42, effect_id, speed, brightness, checksum]

    Args:
        effect_id: Effect ID (1-99 or 255)
        speed: Effect speed (0-100)
        brightness: Effect brightness (0-100)
    """
    speed = max(0, min(100, speed))
    brightness = max(1, min(100, brightness))

    raw_cmd = bytearray([
        0x42,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_effect_command(
    effect_type: EffectType,
    effect_id: int,
    speed: int = 50,
    brightness: int = 100,
    has_bg_color: bool = False,
    has_ic_config: bool = False,
    fg_rgb: tuple[int, int, int] | None = None,
    bg_rgb: tuple[int, int, int] | None = None,
) -> bytearray | None:
    """
    Build effect command based on device effect type.

    Args:
        effect_type: SIMPLE, SYMPHONY, or ADDRESSABLE_0x53
        effect_id: Effect ID (can be encoded for special effect types)
        speed: Effect speed (0-100)
        brightness: Effect brightness (0-100)
        has_bg_color: If True, device supports background colors
        has_ic_config: If True, device is a true Symphony controller (0xA1-0xAD)
        fg_rgb: Foreground RGB for static effects (optional)
        bg_rgb: Background RGB for static effects (optional)

    Returns:
        Command packet or None if effect type is NONE

    Effect ID encoding for 0x56/0x80 devices (has_bg_color but not has_ic_config):
        - Static effects: (effect_id >> 8) where result is 2-10
        - Sound reactive: (effect_id >> 8) where result is 0x33-0x41
        - Regular effects: effect_id directly (1-99, 255)
    """
    if effect_type == EffectType.ADDRESSABLE_0x53:
        # 4 bytes, NO checksum - brightness is critical!
        return build_effect_command_0x53(effect_id, speed, brightness)
    elif effect_type == EffectType.SYMPHONY:
        # True Symphony devices (0xA1-0xAD) with has_ic_config=True
        if has_ic_config:
            if has_bg_color and effect_id in SYMPHONY_BG_COLOR_EFFECTS:
                # Symphony effects 5-18 support FG+BG colors via 0x41 command
                # Source: protocol_docs/14_symphony_background_colors.md
                if fg_rgb is None:
                    fg_rgb = (255, 255, 255)  # Default white
                if bg_rgb is None:
                    bg_rgb = (0, 0, 0)  # Default black
                _LOGGER.debug(
                    "Using 0x41 command for Symphony effect %d with FG=%s, BG=%s",
                    effect_id, fg_rgb, bg_rgb
                )
                return build_static_effect_command_0x41(
                    effect_id, fg_rgb, bg_rgb, speed
                )
            else:
                # Standard Symphony effect (1-44) - use 0x38 command
                return build_effect_command_0x38(effect_id, speed, brightness)
        # 0x56/0x80 devices (has_bg_color but not has_ic_config)
        elif has_bg_color and effect_id >= 0x100:
            # Encoded effect ID for 0x56/0x80 devices (static effects use ID << 8)
            decoded_id = effect_id >> 8
            if decoded_id <= 10:
                # Static effect (2-10) - use 0x41 command
                # These effects need FG and BG colors
                if fg_rgb is None:
                    fg_rgb = (255, 255, 255)  # Default white
                if bg_rgb is None:
                    bg_rgb = (0, 0, 0)  # Default black
                return build_static_effect_command_0x41(
                    decoded_id, fg_rgb, bg_rgb, speed
                )
            elif decoded_id >= 0x33:
                # Sound reactive effect - would need 0x73 command
                # For now, just log and return None (not yet implemented)
                _LOGGER.warning(
                    "Sound reactive effects not yet implemented (id=%d)",
                    effect_id
                )
                return None
        elif has_bg_color:
            # Regular strip effect (1-99 or 255) for 0x56/0x80 - use 0x42 command
            return build_effect_command_0x42(effect_id, speed, brightness)
        else:
            # Fallback for unknown Symphony devices - use 0x38 command
            return build_effect_command_0x38(effect_id, speed, brightness)
    elif effect_type == EffectType.SIMPLE:
        # 0x61 command - speed uses INVERTED 1-31 range
        # Formula from ad/e.java: protocol_speed = 1 + (30 * (1.0 - ui_speed/100))
        # 100% UI speed (fast) → 1 (fastest protocol value)
        # 0% UI speed (slow) → 31 (slowest protocol value)
        speed_byte = 1 + int(30 * (1.0 - speed / 100))
        speed_byte = max(1, min(31, speed_byte))  # Clamp to valid range
        return build_effect_command_0x61(effect_id, speed_byte)
    return None


# =============================================================================
# QUERY COMMANDS
# =============================================================================

def build_state_query() -> bytearray:
    """
    Build state query command.

    Returns device state including power, color, effect, etc.
    Response is 0x81 format.
    """
    raw_cmd = bytearray([0x81, 0x8A, 0x8B])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0a)


def build_led_settings_query() -> bytearray:
    """
    Build LED settings query command.

    Returns LED count, IC type, color order for addressable strips.
    Response is 0x63 format.
    """
    raw_cmd = bytearray([0x63, 0x12, 0x21, 0xF0])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0a)


# =============================================================================
# LED SETTINGS COMMANDS
# =============================================================================

def build_led_settings_command(
    led_count: int,
    led_type: int,
    color_order: int,
    param_d: int = 0,
    param_e: int = 0,
    param_f: int = 0,
) -> bytearray:
    """
    Build LED configuration command (0x62 - Original format).

    Sets LED count, IC type, and color order for addressable strips.

    Format: [0x62, count_lo, count_hi, ic_type, color_order, d, e, f, freq_lo, freq_hi, 0, persist, checksum]
    Source: tc/b.java method B() lines 518-531
    """
    raw_cmd = bytearray([
        0x62,
        led_count & 0xFF,          # LED count low byte
        (led_count >> 8) & 0xFF,   # LED count high byte
        led_type & 0xFF,
        color_order & 0xFF,
        param_d & 0xFF,
        param_e & 0xFF,
        param_f & 0xFF,
        0x00, 0x00,                # Frequency (0 = default)
        0x00,                       # Reserved
        0xF0,                       # Persist
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_led_settings_command_a3(
    led_count: int,
    segments: int,
    led_type: int,
    color_order: int,
    music_led_count: int = 30,
    music_segments: int = 10,
) -> bytearray:
    """
    Build LED configuration command (0x62 - A3+ format).

    For newer A3+ Symphony devices with segment support.

    Format: [0x62, count_lo, count_hi, seg_lo, seg_hi, ic_type, color_order, music_count, music_seg, persist, checksum]
    Source: tc/b.java method C() lines 533-547
    """
    raw_cmd = bytearray([
        0x62,
        led_count & 0xFF,          # LED count low byte
        (led_count >> 8) & 0xFF,   # LED count high byte
        segments & 0xFF,           # Segments low byte
        (segments >> 8) & 0xFF,    # Segments high byte
        led_type & 0xFF,
        color_order & 0xFF,
        music_led_count & 0xFF,
        music_segments & 0xFF,
        0xF0,                      # Persist
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_led_settings_query_a3() -> bytearray:
    """
    Build LED settings query command for A3+ devices.

    Response is 0x44 format with segment and music settings.
    Source: tc/b.java method d0() lines 1336-1343
    """
    raw_cmd = bytearray([0x44, 0x4A, 0x4B, 0xF0])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0a)


# =============================================================================
# RESPONSE PARSING
# =============================================================================

def parse_state_response(data: bytes) -> dict | None:
    """
    Parse state query response (0x81 format).

    Source: tc/b.java method c() lines 47-62, DeviceState.java
    Source: protocol_docs/08_state_query_response_parsing.md

    Response format (14 bytes):
        Byte 0: Header (0x81)
        Byte 1: Mode (f23859c)
        Byte 2: Power State (0x23 = ON) (f23858b)
        Byte 3: Mode Type (0x61=static, 0x25=effect) (f23862f)
        Byte 4: Sub-mode (0xF0/0x0B=RGB, 0x0F=white, or effect ID) (f23863g)
        Byte 5: Value1 (brightness 0-100 for white mode) (f23864h)
        Byte 6-8: RGB (f23865j, f23866k, f23867l)
        Byte 9: Warm White / Color Temp (f23868m)
        Byte 10: LED Version - NOT brightness! (f23860d via i())
        Byte 11: Cool White (f23869n)
        Byte 12: Reserved (f23870p)
        Byte 13: Checksum

    Brightness derivation (mode-dependent per Java source):
        - RGB mode: derive from RGB via HSV (V component)
        - White mode: from value1 (byte 5), scaled 0-100 → 0-255
        - Effect mode: from byte 6 (R position), scaled 0-100 → 0-255

    Returns dict with:
        - is_on: bool
        - mode_type: int (0x61=static, 0x25=effect)
        - sub_mode: int (0xF0/0x0B=RGB, 0x0F=white, or effect ID)
        - value1: int (byte 5 - brightness for white mode, 0-100)
        - r, g, b: int (0-255)
        - ww, cw: int (0-255)
        - led_version: int (byte 10 - firmware version, NOT brightness)
        - effect_id: int | None (if in effect mode)
        - is_effect_mode: bool
        - is_rgb_mode: bool
        - is_white_mode: bool
    """
    if len(data) < 14 or data[0] != 0x81:
        return None

    # Byte 2: Power state (0x23 = on)
    is_on = data[2] == 0x23

    # Byte 3: Mode type
    # 0x61 (97) = static color/white mode
    # 0x25 (37) = effect mode
    mode_type = data[3]
    is_effect_mode = mode_type == 0x25

    # Byte 4: Sub-mode
    # In static mode: 0xF0/0x01/0x0B = RGB, 0x0F = white
    # In effect mode: effect ID
    sub_mode = data[4]

    # Determine color mode from sub_mode (when in static mode)
    is_rgb_mode = False
    is_white_mode = False
    if mode_type == 0x61:  # Static mode
        if sub_mode in (0xF0, 0x01, 0x0B):
            is_rgb_mode = True
        elif sub_mode == 0x0F:
            is_white_mode = True

    # Byte 5: Value1 (brightness 0-100 for white mode, other uses for RGB)
    value1 = data[5]

    # Bytes 6-8: RGB (or brightness/speed in effect mode)
    r, g, b = data[6], data[7], data[8]

    # Byte 9: WW / Color Temp, Byte 10: LED Version (NOT brightness!), Byte 11: CW
    ww = data[9]
    led_version = data[10]  # This is LED/firmware version, NOT brightness
    cw = data[11]

    # Effect ID is sub_mode when in effect mode
    effect_id = sub_mode if is_effect_mode else None

    return {
        "is_on": is_on,
        "mode_type": mode_type,
        "sub_mode": sub_mode,
        "value1": value1,
        "r": r,
        "g": g,
        "b": b,
        "ww": ww,
        "cw": cw,
        "led_version": led_version,  # NOT brightness - it's firmware version
        "effect_id": effect_id,
        "is_effect_mode": is_effect_mode,
        "is_rgb_mode": is_rgb_mode,
        "is_white_mode": is_white_mode,
    }


def parse_led_settings_response(data: bytes) -> dict | None:
    """
    Parse LED settings response (0x63 format - Original).

    Source: tc/b.java inner class a, method g() lines 180-195
    Source: protocol_docs/09_effects_addressable_led_support.md

    Response format (12 bytes):
        Byte 0: Header (0x63)
        Byte 1: LED count low byte
        Byte 2: LED count high byte
        Byte 3: IC Type
        Byte 4: Color Order
        Byte 5-7: Timing params D, E, F
        Byte 8: Frequency low byte
        Byte 9: Frequency high byte
        Byte 10: Reserved
        Byte 11: Checksum

    Returns dict with:
        - led_count: int
        - ic_type: int
        - color_order: int
        - frequency: int (Hz)
    """
    if len(data) < 12 or data[0] != 0x63:
        return None

    # LED count: byte 1 is low, byte 2 is high
    led_count = (data[2] << 8) | data[1]
    ic_type = data[3]
    color_order = data[4]
    # Frequency: byte 8 is low, byte 9 is high
    frequency = (data[9] << 8) | data[8]

    return {
        "led_count": led_count,
        "ic_type": ic_type,
        "color_order": color_order,
        "frequency": frequency,
    }


def parse_led_settings_response_a3(data: bytes) -> dict | None:
    """
    Parse LED settings response (A3+ format - 0x44 response).

    Source: SymphonySettingForA3.java inner class a, method c() lines 130-148
    Source: protocol_docs/09_effects_addressable_led_support.md

    Response format (10 bytes payload):
        Byte 0: Has 4th channel (1 = RGBW, 0 = RGB)
        Byte 1: LED count high byte (note: swapped in Java)
        Byte 2: LED count low byte
        Byte 3: Segments high byte (note: swapped)
        Byte 4: Segments low byte
        Byte 5: IC Type
        Byte 6: Color Order
        Byte 7: Music LED count
        Byte 8: Music segments

    Returns dict with:
        - has_rgbw: bool
        - led_count: int
        - segments: int
        - ic_type: int
        - color_order: int
        - music_led_count: int
        - music_segments: int
    """
    if len(data) < 9:
        return None

    has_rgbw = data[0] == 1
    # LED count: byte 2 is low, byte 1 is high (Java swaps them)
    # Actually: Java does g2.c.a(new byte[]{bArr[3], bArr[2]}) for led count
    # which means bArr[3] is treated as first byte (high), bArr[2] as second (low)
    # But indices in Java start after response header, so adjust
    led_count = (data[2] << 8) | data[3]
    segments = (data[4] << 8) | data[5]
    ic_type = data[6] & 0xFF
    color_order = data[7] & 0xFF
    music_led_count = data[8] & 0xFF if len(data) > 8 else 30
    music_segments = data[9] & 0xFF if len(data) > 9 else 10

    return {
        "has_rgbw": has_rgbw,
        "led_count": led_count,
        "segments": segments,
        "ic_type": ic_type,
        "color_order": color_order,
        "music_led_count": music_led_count,
        "music_segments": music_segments,
    }


def parse_manufacturer_data(
    manu_data: dict[int, bytes],
    device_name: str | None = None
) -> dict | None:
    """
    Parse manufacturer data from BLE advertisement (Format B - bleak).

    Source: protocol_docs/03_manufacturer_data_parsing.md

    Format B layout (27 bytes, company ID is dict key):
        Byte 0: sta (status byte)
        Byte 1: ble_version
        Bytes 2-7: mac_address
        Bytes 8-9: product_id (big-endian)
        Byte 10: firmware_ver
        Byte 11: led_version
        Byte 12: check_key_flag
        Byte 13: firmware_flag
        Bytes 14-24: state_data (if ble_version >= 5)
        Bytes 25-26: rfu

    Args:
        manu_data: Manufacturer data dict from BLE advertisement
        device_name: Optional device name for log message context

    Returns dict with:
        - product_id: int
        - power_state: bool | None
        - ble_version: int
        - fw_version: str
        - manu_id: int (company ID)
    """
    # Log prefix for device identification
    log_prefix = f"[{device_name}] " if device_name else ""
    if not manu_data:
        return None

    # Find valid company ID in 0x5A** range (23040-23295)
    # Source: protocol_docs/03_manufacturer_data_parsing.md
    VALID_COMPANY_ID_MIN = 23040  # 0x5A00
    VALID_COMPANY_ID_MAX = 23295  # 0x5AFF

    for manu_id, data in manu_data.items():
        if not (VALID_COMPANY_ID_MIN <= manu_id <= VALID_COMPANY_ID_MAX):
            continue

        if len(data) != 27:
            _LOGGER.debug(
                "Manufacturer data wrong length: %d bytes (expected 27), company_id=0x%04X",
                len(data), manu_id
            )
            continue

        # Parse Format B fields
        sta = data[0]
        ble_version = data[1]

        # Product ID is bytes 8-9 (big-endian)
        product_id = (data[8] << 8) | data[9]

        # Firmware version from byte 10
        firmware_ver = data[10]
        led_version = data[11]
        fw_version = f"{firmware_ver:02X}.{led_version:02X}"

        # Power state is byte 14 of state_data (0x23 = on, 0x24 = off)
        # Only available if ble_version >= 5
        power_state = None
        if ble_version >= 5 and len(data) > 14:
            if data[14] == 0x23:
                power_state = True
            elif data[14] == 0x24:
                power_state = False

        # Parse state_data (bytes 14-24) for color/mode/brightness
        # Source: model_0x53.py model_specific_manu_data()
        # Byte 15 = mode type (0x61=color/white, 0x25=effect)
        # Byte 16 = sub-mode (0xF0/0x01/0x0B=RGB, 0x0F=white) or effect ID
        # Byte 17 = brightness % (white mode)
        # Bytes 18-20 = RGB or brightness+speed (effect mode)
        # Byte 21 = color temp % (white mode)
        color_mode = None  # 'rgb', 'cct', 'effect'
        rgb = None
        color_temp_percent = None
        brightness_percent = None
        effect_id = None
        effect_speed = None

        if ble_version >= 5 and len(data) >= 22:
            mode_type = data[15]  # 0x61=color/white, 0x25=effect
            sub_mode = data[16]

            if mode_type == 0x61:
                # Color or white mode
                if sub_mode in (0xF0, 0x01, 0x0B):
                    # RGB mode (0xF0=RGB, 0x01/0x0B may be effects/music mode but show as RGB)
                    color_mode = 'rgb'
                    rgb = (data[18], data[19], data[20])
                    _LOGGER.debug("%sManu data RGB mode: rgb=%s", log_prefix, rgb)
                elif sub_mode == 0x0F:
                    # White/CCT mode
                    color_mode = 'cct'
                    brightness_percent = data[17]  # 0-100
                    color_temp_percent = data[21]  # 0-100 (0=2700K, 100=6500K)
                    _LOGGER.debug("%sManu data CCT mode: temp_pct=%d, bright_pct=%d",
                                  log_prefix, color_temp_percent, brightness_percent)
                elif sub_mode == 0x23:
                    # Power ON state - device on but no specific color mode
                    # 0x23 (35) = PowerType_PowerON per protocol docs
                    color_mode = 'standby'
                    _LOGGER.debug("%sManu data standby mode (0x23 power on)", log_prefix)
                elif sub_mode == 0x24:
                    # Power OFF state
                    # 0x24 (36) = PowerType_PowerOFF per protocol docs
                    color_mode = 'off'
                    _LOGGER.debug("%sManu data power off mode (0x24)", log_prefix)
                else:
                    # Log full state bytes for debugging unknown sub-modes
                    state_bytes = ' '.join(f'{b:02X}' for b in data[14:min(25, len(data))])
                    _LOGGER.debug(
                        "%sManu data unknown sub-mode: 0x%02X (mode_type=0x61), "
                        "state_bytes[14:24]: %s",
                        log_prefix, sub_mode, state_bytes
                    )
            elif mode_type == 0x25:
                # Effect mode (Symphony/Addressable devices)
                # Effect ID is in sub_mode byte
                color_mode = 'effect'
                effect_id = sub_mode  # Effect ID in sub_mode byte
                brightness_percent = data[18]  # 0-100
                effect_speed = data[19]  # 0-100
                _LOGGER.debug("%sManu data effect mode (0x25): id=%d, bright_pct=%d, speed=%d",
                              log_prefix, effect_id, brightness_percent, effect_speed)
            elif 37 <= mode_type <= 56:
                # SIMPLE effect mode - mode_type IS the effect ID (37-56)
                # For SIMPLE devices (0x33, etc.), when running effects like
                # "Yellow gradual change" (41), the mode_type contains the effect ID directly
                color_mode = 'effect'
                effect_id = mode_type  # Effect ID is in mode_type, not sub_mode
                # sub_mode may contain speed or other param (0x23 observed)
                # Bytes 17-20 interpretation for SIMPLE effects may differ
                # For now, try to extract brightness from common positions
                brightness_percent = data[17] if data[17] <= 100 else None
                effect_speed = sub_mode if sub_mode <= 100 else None
                _LOGGER.debug("%sManu data SIMPLE effect mode: id=%d (0x%02X), "
                              "sub_mode=0x%02X, bright_pct=%s",
                              log_prefix, effect_id, mode_type, sub_mode, brightness_percent)
            else:
                # Log full state bytes for debugging unknown modes
                state_bytes = ' '.join(f'{b:02X}' for b in data[14:min(25, len(data))])
                _LOGGER.debug(
                    "%sManu data unknown mode_type: 0x%02X, sub_mode: 0x%02X, "
                    "state_bytes[14:24]: %s",
                    log_prefix, mode_type, sub_mode, state_bytes
                )

        result = {
            "product_id": product_id,
            "power_state": power_state,
            "ble_version": ble_version,
            "fw_version": fw_version,
            "manu_id": manu_id,
            "sta": sta,
            # State fields from bytes 15-21
            "color_mode": color_mode,
            "rgb": rgb,
            "color_temp_percent": color_temp_percent,
            "brightness_percent": brightness_percent,
            "effect_id": effect_id,
            "effect_speed": effect_speed,
        }

        # Log comprehensive summary of parsed manufacturer data
        _LOGGER.debug(
            "%sParsed manu data: product_id=0x%02X (%d), ble_version=%d, "
            "fw=%s, power=%s, mode=%s",
            log_prefix, product_id, product_id, ble_version, fw_version,
            "ON" if power_state else ("OFF" if power_state is False else "unknown"),
            color_mode or "unknown",
        )
        if color_mode == "rgb":
            _LOGGER.debug("%s  RGB state: rgb=%s", log_prefix, rgb)
        elif color_mode == "cct":
            _LOGGER.debug("%s  CCT state: temp_pct=%s%%, bright_pct=%s%%",
                          log_prefix, color_temp_percent, brightness_percent)
        elif color_mode == "effect":
            _LOGGER.debug("%s  Effect state: id=%s, speed=%s, bright_pct=%s%%",
                          log_prefix, effect_id, effect_speed, brightness_percent)

        return result

    # No valid manufacturer data found
    _LOGGER.debug("%sNo valid LEDnetWF manufacturer data found in: %s",
                  log_prefix, {hex(k): len(v) for k, v in manu_data.items()})
    return None
