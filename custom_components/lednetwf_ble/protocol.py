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
# IOTBT COMMANDS (product_id=0x00, Telink BLE Mesh based)
# =============================================================================

def build_iotbt_power_command(turn_on: bool) -> bytearray:
    """
    Build IOTBT power command (0x71 format, no checksum).

    Source: protocol_docs/17_device_configuration.md - IOTBT Command Reference

    Format: [0x71, state] - NO checksum, NO 0x0F terminator
    State: 0x23 = ON, 0x24 = OFF
    Uses cmd_family=0x0a (expects response)
    """
    state = 0x23 if turn_on else 0x24
    raw_cmd = bytearray([0x71, state])
    return wrap_command(raw_cmd, cmd_family=0x0a)


def rgb_to_iotbt_hue(r: int, g: int, b: int) -> int:
    """
    Convert RGB (0-255) to IOTBT quantized hue (1-240, 0=white).

    Source: model_iotbt_0x80.py - hue_to_cc_240() function

    IOTBT uses a 240-step hue wheel with 24-bin QUANTIZATION to avoid
    washed-out colors. Colors are snapped to 24 discrete hue bins.

    - 0 = white (special case for low saturation)
    - 1-240 = quantized hue values

    The quantization helps produce more vivid, saturated colors on the device.
    """
    if r == g == b:
        # Pure grayscale (white/gray/black) - return white mode
        return 0

    # Convert RGB to HSV
    h, s, v = rgb_to_hsv(r, g, b)

    # If saturation is too low (< 5%), treat as white
    # This threshold matches the old integration: sat < 0.05
    if s < 5:
        return 0

    # Quantize to 24 hue bins then map to 240-step ring
    # Source: model_iotbt_0x80.py hue_to_cc_240()
    N_HUES = 24
    bin_idx = int(round((h % 360) / 360 * N_HUES)) % N_HUES
    step = 240 / N_HUES  # = 10
    ring_pos = int(round(bin_idx * step)) % 240
    cc = ring_pos + 1  # 1..240

    # Ensure we never return 0 for colored values
    return max(1, min(240, cc))


def iotbt_hue_to_rgb(hue: int, brightness: int = 100) -> Tuple[int, int, int]:
    """
    Convert IOTBT hue (1-240, 0=white) to RGB (0-255).

    Args:
        hue: IOTBT hue value (0=white, 1-240=colors)
        brightness: Brightness percentage (0-100)

    Returns:
        RGB tuple (0-255)
    """
    if hue == 0:
        # White mode
        level = int(brightness * 255 / 100)
        return (level, level, level)

    # Map IOTBT hue (1-240) back to standard hue (0-360)
    std_hue = int((hue - 1) * 360 / 239)
    std_hue = max(0, min(360, std_hue))

    # Convert HSV to RGB
    return hsv_to_rgb(std_hue, 100, brightness)


def iotbt_brightness_to_level(brightness_0_255: int, gamma: float = 2.2, max_level: int = 31) -> int:
    """
    Convert brightness (0-255) to IOTBT level (0-31) with gamma correction.

    Source: model_iotbt_0x80.py - brightness_to_level() function

    Gamma correction makes brightness perception more linear on the device.
    """
    x = max(0.0, min(1.0, brightness_0_255 / 255.0))
    x_gamma = x ** gamma
    return int(round(x_gamma * max_level))


def build_iotbt_color_command(r: int, g: int, b: int, brightness: int = 100) -> bytearray:
    """
    Build IOTBT color command (0xE2 format).

    Source: protocol_docs/17_device_configuration.md - Color Command (0xE2)
    Source: model_iotbt_0x80.py - set_color() method

    Format: [0xE2, 0x0B, hue, brightness_byte]
    - hue: Quantized hue (1-240, 0=white) using 24-bin quantization
    - brightness_byte: 0xE0 | level (level = 0-31, gamma corrected)

    Uses cmd_family=0x0a (expects response)
    """
    # Convert RGB to IOTBT quantized hue
    hue = rgb_to_iotbt_hue(r, g, b)

    # Convert brightness from 0-100 to 0-255 for gamma calculation
    brightness_255 = int(brightness * 255 / 100)

    # Apply gamma correction (2.2) for proper brightness perception
    level = iotbt_brightness_to_level(brightness_255)
    level = max(0, min(31, level))
    brightness_byte = 0xE0 | level

    raw_cmd = bytearray([0xE2, 0x0B, hue & 0xFF, brightness_byte])
    return wrap_command(raw_cmd, cmd_family=0x0a)


def build_iotbt_white_command(brightness: int = 100) -> bytearray:
    """
    Build IOTBT white color command (0xE2 with hue=0).

    Args:
        brightness: Brightness percentage (0-100)

    Returns:
        Command packet for white mode
    """
    # Hue 0 = white mode
    # Convert brightness to 0-255 for gamma calculation
    brightness_255 = int(brightness * 255 / 100)
    level = iotbt_brightness_to_level(brightness_255)
    level = max(0, min(31, level))
    brightness_byte = 0xE0 | level

    raw_cmd = bytearray([0xE2, 0x0B, 0x00, brightness_byte])
    return wrap_command(raw_cmd, cmd_family=0x0a)


def build_iotbt_effect_command(effect_id: int, speed: int = 50, brightness: int = 100) -> bytearray:
    """
    Build IOTBT effect command (0xE0 0x02 format).

    Source: protocol_docs/17_device_configuration.md - Effect Command (0xE0 0x02)
    Source: model_iotbt_0x80.py - set_effect() method

    Format: [0xE0, 0x02, 0x00, effect_id, speed, brightness] - 6 bytes!
    - 0x00: Constant byte (required!)
    - effect_id: 1-12 (IOTBT has 12 effects)
    - speed: 1-100
    - brightness: 1-100 (percentage)

    Uses cmd_family=0x0a (expects response)
    """
    effect_id = max(1, min(12, effect_id))
    speed = max(1, min(100, speed))
    brightness = max(1, min(100, brightness))

    # Note: The 0x00 byte after 0x02 is REQUIRED - old integration shows 6-byte payload
    raw_cmd = bytearray([0xE0, 0x02, 0x00, effect_id & 0xFF, speed & 0xFF, brightness & 0xFF])
    return wrap_command(raw_cmd, cmd_family=0x0a)


def build_iotbt_music_command(effect_id: int, brightness: int = 100, sensitivity: int = 100) -> bytearray:
    """
    Build IOTBT music reactive command (0xE1 0x05 format).

    Source: protocol_docs/17_device_configuration.md - Music Mode Command (0xE1 0x05)
    Source: model_iotbt_0x80.py - set_effect() method for music mode

    This is a 54-byte packet that enables music reactive mode with a specific effect.

    Args:
        effect_id: Music effect ID (1, 2, 3, 4, 7, 8, 12, 13 - other IDs don't exist)
        brightness: Brightness percentage (0-100)
        sensitivity: Mic sensitivity percentage (0-100)

    Packet structure (raw payload, 46 bytes):
        Byte 0: 0xE1 - Music mode opcode
        Byte 1: 0x05 - Sub-command
        Byte 2: 0x01 - Enable
        Byte 3: brightness (0-100)
        Byte 4: effect_id (1-13)
        Byte 5-6: 0x00 0x00
        Byte 7: sensitivity (0-100)
        Bytes 8-45: Color palette data (fixed pattern)

    Uses cmd_family=0x0a (expects response)
    """
    # Valid music effects: 1, 2, 3, 4, 7, 8, 12, 13 (5, 6, 9, 10, 11 don't exist)
    effect_id = max(1, min(13, effect_id))
    brightness = max(1, min(100, brightness))
    sensitivity = max(1, min(100, sensitivity))

    # Base packet from old integration (46 bytes raw payload)
    # The full wrapped packet is 54 bytes (8-byte header + 46-byte payload)
    raw_cmd = bytearray.fromhex(
        "e1 05 01 64 08 00 00 64 "
        "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
        "a1 00 00 00 06 a1 00 64 64 a1 96 64 64 a1 78 64 64 "
        "a1 5a 64 64 a1 3c 64 64 a1 1e 64 64"
    )

    # Set the variable bytes
    raw_cmd[3] = brightness & 0xFF    # Brightness at offset 3
    raw_cmd[4] = effect_id & 0xFF     # Effect ID at offset 4
    raw_cmd[7] = sensitivity & 0xFF   # Sensitivity at offset 7

    return wrap_command(raw_cmd, cmd_family=0x0a)


def build_iotbt_state_query() -> bytearray:
    """
    Build IOTBT state query command (0xEA format for firmware >= 11).

    Source: protocol_docs/17_device_configuration.md - Query Command: 0xEA

    Format: [0xEA, 0x81, 0x8A, 0x8B] - NO checksum
    Response will be DeviceState2 format (0xEA 0x81 magic header)

    Uses cmd_family=0x0a (expects response)
    """
    raw_cmd = bytearray([0xEA, 0x81, 0x8A, 0x8B])
    return wrap_command(raw_cmd, cmd_family=0x0a)


# =============================================================================
# IOTBT SEGMENT-BASED COMMANDS (IOTBT devices with addressable segments)
# These devices use 0xE1 0x03 for color (not 0xE2) and 0x3B for power (not 0x71)
# =============================================================================

def build_iotbt_segment_color_command(
    r: int, g: int, b: int, brightness: int = 100, segment_count: int = 20
) -> bytearray:
    """
    Build IOTBT segment-based color command (0xE1 0x03 format).

    Source: User protocol capture (Dec 2025) - IOTBT devices with addressable segments.

    Format: [0xE1, 0x03, 0x00, segment_count, 0x00, 0x00, segment_count, ...segment_data...]

    Each segment (4 bytes): [0xA1, hue, saturation, brightness]
    - 0xA1: Segment marker
    - hue: 0-255 (0=red, 85=green, 170=blue, wrapping)
    - saturation: 0-100 (0=white, 100=full color)
    - brightness: 0-100 (0=off, 100=full)

    This sets all segments to the same color. For individual segment control,
    the segment_data would contain different values per segment.

    Args:
        r, g, b: RGB color values (0-255)
        brightness: Overall brightness percentage (0-100)
        segment_count: Number of segments (default 20)

    Returns:
        Wrapped command packet
    """
    # Convert RGB to HSV
    h, s, v = rgb_to_hsv(r, g, b)

    # This devices accepts angles 0-180 for hue
    # 0=red, ~60=green, ~120=blue
    # CHANGE THIS TO THE FOLLOIWNG
    hue_180 = int(h / 2) & 0xFF

    # Saturation stays 0-100
    sat = max(0, min(100, s))

    # Combine brightness from both sources
    # RGB value gives us "color intensity", brightness param is overall
    combined_bright = max(1, min(100, int(brightness * v / 100)))

    # Build header: E1 03 00 {segment_count} 00 00 {segment_count}
    raw_cmd = bytearray([
        0xE1, 0x03,
        0x00,                       # Unknown/reserved
        segment_count & 0xFF,       # Segment count (first occurrence)
        0x00, 0x00,                 # Reserved
        segment_count & 0xFF,       # Segment count (repeated)
    ])

    # Add segment data - all segments get same color
    for _ in range(segment_count):
        raw_cmd.extend([
            0xA1,                    # Segment marker
            hue_180 & 0xFF,          # Hue (0-180 deg)
            sat & 0xFF,              # Saturation (0-100)
            combined_bright & 0xFF   # Brightness (0-100)
        ])

    # No checksum for this command format
    return wrap_command(raw_cmd, cmd_family=0x0a)

    
def build_iotbt_segment_effect_command(effect_id: int, speed: int = 50, brightness: int = 100, segment_count: int = 100) -> bytearray:
    """
    Build IOTBT segment effect command (0xE1 0x01 format), based on sniffed BLE data.

    speed: 1-100 (maps directly to bytes in little endian)
    brightness: 0-255
    segment_count: number of segments (often 0x64 = 100)
    """
    effect_id = max(1, min(12, effect_id))
    speed = max(1, min(100, speed))
    brightness = max(0, min(255, brightness))
    segment_count = max(1, min(255, segment_count))

    # Base payload (matches your sniffed data structure)
    payload = bytearray([
        0xE1, 0x01, 0x00,
        0x64,                   # Some brightness or smth
        effect_id,              # effect ID
        0x00,                   # unknown/reserved
        0x01,                   # unknown/fixed
        0x64,                  # speed low byte
        speed & 0xFF,    # speed high byte
        0xA1, 0x00, 0x00, 0x00,  # fixed pattern per scene
        (effect_id + 4),              # effect ID
        0xA1, 0x58, 0xDE, 0x61,
        0xA1, 0x3C, 0x64, 0x64,
        0xA1, 0x68, 0xE4, 0x64,
        0xA1, 0x96, 0x64, 0x64
    ])

    return wrap_command(payload, cmd_family=0x0A)


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


def build_candle_command(
    r: int, g: int, b: int, speed: int = 50, brightness: int = 100
) -> bytearray:
    """
    Build candle flicker effect command (0x39).

    Used for product IDs 0x54 and 0x5B devices.

    Source: protocol_docs/06_effect_commands.md, model_0x54.py

    Format (9 bytes): [0x39, enable, R, G, B, speed, brightness, reserved, checksum]

    Args:
        r, g, b: Candle color (0-255)
        speed: Flicker speed 0-100 (converted to inverted 1-31 range)
        brightness: Brightness 0-100

    Note: Speed is inverted like SIMPLE effects: 1=fastest, 31=slowest
    """
    # Convert UI speed (0-100, 100=fast) to protocol speed (1-31, 1=fast)
    # Formula: 1 + (30 * (1.0 - speed/100))
    speed_byte = 1 + int(30 * (1.0 - max(0, min(100, speed)) / 100))
    speed_byte = max(1, min(31, speed_byte))

    brightness = max(1, min(100, brightness))

    raw_cmd = bytearray([
        0x39,
        0x01,  # Enable candle mode
        r & 0xFF,
        g & 0xFF,
        b & 0xFF,
        speed_byte & 0xFF,
        brightness & 0xFF,
        0x00,  # Reserved
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_effect_command_0x42(effect_id: int, speed: int = 50, brightness: int = 100) -> bytearray:
    """
    Build effect command (0x42) for Symphony and strip devices.

    Used for:
    - Symphony Function Mode effects (0xA1-0xAD): IDs 1-100 (numbered only, no names)
    - 0x56/0x80 strip effects: IDs 1-99, or 255 for cycle modes

    Source: FunctionModeFragment.java - Protocol.m class

    Format (5 bytes): [0x42, effect_id, speed, brightness, checksum]

    Args:
        effect_id: Effect ID (1-100 for Symphony, 1-99 or 255 for strips)
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


def build_effect_command_0x38(
    effect_id: int, speed: int = 50, brightness: int = 100
) -> bytearray:
    """
    Build effect command (0x38) for addressable strip devices (0x54, 0x5B, etc.).

    Used for devices that support SIMPLE effects (IDs 37-56) but use the 0x38
    command format WITH brightness, unlike the 0x61 format.

    Source: User's working implementation for 0x54 devices

    Format (5 bytes): [0x38, effect_id, speed, brightness, checksum]

    Args:
        effect_id: Effect ID (37-56 for SIMPLE effects)
        speed: Effect speed 0-100 (converted to inverted 1-31 range)
        brightness: Effect brightness (0-100)

    Note: Speed is inverted like 0x61: 1=fastest, 31=slowest
    """
    # Convert UI speed (0-100, 100=fast) to protocol speed (1-31, 1=fast)
    speed_byte = 1 + int(30 * (1.0 - max(0, min(100, speed)) / 100))
    speed_byte = max(1, min(31, speed_byte))

    brightness = max(1, min(100, brightness))

    raw_cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed_byte & 0xFF,
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
    uses_0x38_effects: bool = False,
    fg_rgb: tuple[int, int, int] | None = None,
    bg_rgb: tuple[int, int, int] | None = None,
) -> bytearray | None:
    """
    Build effect command based on device effect type.

    Args:
        effect_type: SIMPLE, SYMPHONY, ADDRESSABLE_0x53, or IOTBT
        effect_id: Effect ID (can be encoded for special effect types)
        speed: Effect speed (0-100)
        uses_0x38_effects: If True, use 0x38 command for SIMPLE effects (0x54, 0x5B devices)
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

    IOTBT devices (product_id=0x00):
        - Regular effects (1-12): 0xE0 0x02 command format
        - Music effects (encoded as effect_num << 8): 0xE1 0x05 command format
          Speed parameter is used as mic sensitivity for music mode
    """
    if effect_type == EffectType.IOTBT_SEGMENT:
        # Standard IOTBT devices use different commands for regular effects vs music effects
        if effect_id >= 0x100:
            # Music reactive effect (encoded as effect_num << 8)
            # Decode the effect ID and use music command
            music_effect_id = effect_id >> 8
            # Speed is used as sensitivity for music mode
            return build_iotbt_music_command(music_effect_id, brightness, speed)
        else:
            # Regular effect (1-100) via 0xE0 0x02 command
            return build_iotbt_segment_effect_command(effect_id, speed, brightness)
    elif effect_type == EffectType.IOTBT:
        # Standard IOTBT devices use different commands for regular effects vs music effects
        if effect_id >= 0x100:
            # Music reactive effect (encoded as effect_num << 8)
            # Decode the effect ID and use music command
            music_effect_id = effect_id >> 8
            # Speed is used as sensitivity for music mode
            return build_iotbt_music_command(music_effect_id, brightness, speed)
        else:
            # Regular effect (1-12) via 0xE0 0x02 command
            return build_iotbt_effect_command(effect_id, speed, brightness)
    elif effect_type == EffectType.ADDRESSABLE_0x53:
        # 4 bytes, NO checksum - brightness is critical!
        return build_effect_command_0x53(effect_id, speed, brightness)
    elif effect_type == EffectType.SYMPHONY:
        # True Symphony devices (0xA1-0xAD) with has_ic_config=True
        if has_ic_config:
            if effect_id >= 0x100:
                # Settled Mode effect (encoded with << 8 to distinguish from Function Mode)
                # Decode and route to 0x41 command with FG+BG colors
                decoded_id = effect_id >> 8
                if fg_rgb is None:
                    fg_rgb = (255, 255, 255)  # Default white
                if bg_rgb is None:
                    bg_rgb = (0, 0, 0)  # Default black
                return build_static_effect_command_0x41(
                    decoded_id, fg_rgb, bg_rgb, speed
                )
            else:
                # Symphony Function Mode effects (1-100) use 0x42 command
                # Source: FunctionModeFragment.java - effects are numbered 1-100
                # Format: [0x42, effect_id, speed, brightness, checksum]
                return build_effect_command_0x42(effect_id, speed, brightness)
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
        if uses_0x38_effects:
            # 0x38 command for devices like 0x54, 0x5B that support brightness in effects
            # Speed is still inverted 1-31 range, but brightness is included
            return build_effect_command_0x38(effect_id, speed, brightness)
        else:
            # 0x61 command - speed uses INVERTED 1-31 range, NO brightness
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

    Format: [0x62, count_hi, count_lo, ic_type, color_order, d, e, f, freq_hi, freq_lo, param, persist, checksum]
    Source: tc/b.java method B() lines 519-536

    Note: Java uses g2.c.c() which returns [lo, hi], then reverses order:
      bArr[1] = bArrC[1]  (high byte)
      bArr[2] = bArrC[0]  (low byte)
    So the wire format is big-endian (high byte first).
    """
    raw_cmd = bytearray([
        0x62,
        (led_count >> 8) & 0xFF,   # LED count high byte
        led_count & 0xFF,          # LED count low byte
        led_type & 0xFF,
        color_order & 0xFF,
        param_d & 0xFF,
        param_e & 0xFF,
        param_f & 0xFF,
        0x00, 0x00,                # Frequency (0 = default, big-endian)
        0x00,                       # Reserved param
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

    Format: [0x62, count_hi, count_lo, seg_hi, seg_lo, ic_type, color_order, music_count, music_seg, persist, checksum]
    Source: tc/b.java method C() lines 539-555

    Note: Java uses g2.c.c() which returns [lo, hi], then reverses order:
      bArr[1] = bArrC[1]  (high byte)
      bArr[2] = bArrC[0]  (low byte)
    So the wire format is big-endian (high byte first).
    """
    raw_cmd = bytearray([
        0x62,
        (led_count >> 8) & 0xFF,   # LED count high byte
        led_count & 0xFF,          # LED count low byte
        (segments >> 8) & 0xFF,    # Segments high byte
        segments & 0xFF,           # Segments low byte
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


def build_color_order_command_simple(color_order: int) -> bytearray:
    """
    Build color order command for SIMPLE devices (0x33, etc.).

    This is a simplified 0x62 command that only sets color order.
    For SIMPLE devices, ic_type should be 0.

    Source: protocol_docs/17_color_order_settings.md

    Args:
        color_order: 1=RGB, 2=GRB, 3=BRG

    Format: [0x62, ic_type, color_order, 0x0F, checksum]
    """
    raw_cmd = bytearray([
        0x62,
        0x00,                      # IC type (0 for SIMPLE devices)
        color_order & 0xFF,
        0x0F,                      # Terminator
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_sound_reactive_simple(enable: bool, sensitivity: int = 50) -> bytearray:
    """
    Build simple 5-byte sound reactive command for 0x08, 0x48 devices.

    Only for devices with built-in microphones using the simple command format.
    When enabled, the device listens to ambient sound via its built-in mic
    and adjusts LED colors/patterns autonomously.

    Source: Packet capture analysis (micmode.csv)
    Source: protocol_docs/18_sound_reactive_music_mode.md

    Args:
        enable: True to enable sound reactive mode, False to disable
        sensitivity: Microphone sensitivity 1-100 (default 50)

    Format: [0x73, enable, sensitivity, 0x0F, checksum]
        - 0x73: Command ID
        - enable: 0x01 = on, 0x00 = off
        - sensitivity: 1-100 (mic gain level)
        - 0x0F: Fixed byte
        - checksum: Sum of bytes 0-3 & 0xFF

    Examples from packet capture:
        73 01 21 0f a4  - enable with sensitivity 33
        73 01 64 0f e7  - enable with sensitivity 100 (max)
        73 01 01 0f 84  - enable with sensitivity 1 (min)
    """
    sensitivity = max(1, min(100, sensitivity))
    raw_cmd = bytearray([
        0x73,                      # Command ID
        0x01 if enable else 0x00,  # Enable/disable
        sensitivity,               # Sensitivity 1-100
        0x0F,                      # Fixed byte
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)  # 0x0b for commands


def build_sound_reactive_symphony(
    enable: bool,
    effect_id: int = 1,
    fg_rgb: tuple[int, int, int] = (255, 0, 0),
    bg_rgb: tuple[int, int, int] = (0, 0, 255),
    sensitivity: int = 50,
    brightness: int = 100,
) -> bytearray:
    """
    Build 13-byte sound reactive command for Symphony devices (0xA2, 0xA3, etc).

    For Symphony devices with built-in microphones. These devices support
    effect selection, colors, and sensitivity parameters.

    Source: com/zengge/wifi/COMM/Protocol/z.java
    Source: MusicModeFragment.java method K2()
    Source: protocol_docs/18_sound_reactive_music_mode.md

    Args:
        enable: True to enable device mic, False to disable
        effect_id: Effect number (1-255, 255 = all colors mode)
        fg_rgb: Foreground color tuple (0-255)
        bg_rgb: Background color tuple (0-255)
        sensitivity: Microphone sensitivity 0-100
        brightness: Brightness percentage 0-100

    Format: [0x73, enable, mode, effect_id, FG_R, FG_G, FG_B, BG_R, BG_G, BG_B, sensitivity, brightness, checksum]
        - Byte 0: 0x73 (Command ID)
        - Byte 1: 0x01 = enable, 0x00 = disable
        - Byte 2: 0x27 = device mic mode, 0x26 = app mic mode (we use device mic)
        - Byte 3: effect_id (1-255)
        - Bytes 4-6: Foreground RGB
        - Bytes 7-9: Background RGB
        - Byte 10: Sensitivity (0-100)
        - Byte 11: Brightness (0-100)
        - Byte 12: Checksum
    """
    sensitivity = max(0, min(100, sensitivity))
    brightness = max(0, min(100, brightness))
    effect_id = max(1, min(255, effect_id))

    raw_cmd = bytearray([
        0x73,                           # Command ID
        0x01 if enable else 0x00,       # Enable/disable
        0x27,                           # Device mic mode (0x27)
        effect_id & 0xFF,               # Effect ID
        fg_rgb[0] & 0xFF,               # FG Red
        fg_rgb[1] & 0xFF,               # FG Green
        fg_rgb[2] & 0xFF,               # FG Blue
        bg_rgb[0] & 0xFF,               # BG Red
        bg_rgb[1] & 0xFF,               # BG Green
        bg_rgb[2] & 0xFF,               # BG Blue
        sensitivity & 0xFF,             # Sensitivity
        brightness & 0xFF,              # Brightness
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)  # 0x0b for commands


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
    # For SIMPLE devices with has_color_order: upper nibble contains color order
    sub_mode = data[4]

    # Extract color order from upper nibble (for SIMPLE devices like 0x33)
    # Source: protocol_docs/17_color_order_settings.md
    # Values: 1=RGB, 2=GRB, 3=BRG
    color_order_nibble = (data[4] & 0xF0) >> 4

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
        "color_order_nibble": color_order_nibble,  # For SIMPLE devices with has_color_order
    }


def parse_led_settings_response(data: bytes) -> dict | None:
    """
    Parse LED settings response (0x63 format - IC Settings).

    Source: protocol_docs/16_query_formats_0x63_vs_0x44.md
    Used by Symphony devices (0xA1-0xAD) only.

    Response format (10 bytes):
        Byte 0: Header (0x63)
        Byte 1: Direction (0 = forward, 1 = reverse)
        Byte 2-3: LED count per segment (little-endian uint16)
        Byte 4: Segments (single byte)
        Byte 5: IC Type (WS2812B=1, etc.)
        Byte 6: Color Order (RGB=0, RBG=1, GRB=2, etc.)
        Byte 7: Music Point
        Byte 8: Music Part
        Byte 9: Checksum (if present)

    Note: Total LED count = led_count × segments

    Returns dict with:
        - led_count: int
        - segments: int
        - ic_type: int
        - color_order: int
        - direction: int (0 = forward, 1 = reverse)
        - music_point: int
    """
    if len(data) < 10:
        _LOGGER.debug("LED settings response too short: %d bytes (need 10)", len(data))
        return None
    if data[0] != 0x63:
        _LOGGER.debug("LED settings response wrong header: 0x%02X (expected 0x63)", data[0])
        return None

    # Log raw bytes for debugging format issues
    # Different devices may have different formats - see protocol_docs/16_query_formats_0x63_vs_0x44.md
    raw_hex = ' '.join(f'0x{b:02X}' for b in data[:10])
    _LOGGER.debug("LED settings raw bytes: %s", raw_hex)

    direction = data[1]
    # LED count: bytes 2-3 little-endian (LEDs per segment, not total)
    led_count = data[2] | (data[3] << 8)
    # Segments: byte 4 only (single byte, NOT 16-bit!)
    # Total LEDs = led_count × segments
    segments = data[4]
    # IC Type: byte 5
    ic_type = data[5]
    # Color Order: byte 6
    color_order = data[6]
    # Music point/part: bytes 7-8
    music_point = data[7]
    music_part = data[8] if len(data) > 8 else 0

    # Log parsed values for verification
    _LOGGER.debug(
        "LED settings parsed: dir=%d, count=%d, seg=%d, ic=%d, order=%d, music=%d/%d",
        direction, led_count, segments, ic_type, color_order, music_point, music_part
    )

    # Sanity check: color_order should be 0-5 for addressable, 1-3 for SIMPLE
    if color_order > 5:
        _LOGGER.warning(
            "LED settings color_order=%d is outside expected range (0-5). "
            "Response format may differ from expected - check raw bytes above.",
            color_order
        )

    return {
        "led_count": led_count,
        "segments": segments,
        "ic_type": ic_type,
        "color_order": color_order,
        "direction": direction,
        "music_point": music_point,
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

    # IOTBT name-based detection (highest priority)
    # Device names starting with "IOTBT" are definitely IOTBT devices regardless of
    # manufacturer data format. This handles cases where the advertisement data
    # doesn't match expected IOTBT patterns (e.g., service data UUID 0x5A00 with
    # non-standard format that causes product_id misdetection).
    if device_name and device_name.upper().startswith("IOTBT"):
        _LOGGER.debug(
            "%sIOTBT device detected by name prefix, forcing product_id=0x00",
            log_prefix
        )
        # Try to extract power state from manufacturer data if available
        power_state = None
        for manu_id, data in manu_data.items():
            if len(data) >= 2:
                byte1 = data[1] & 0xFF
                if byte1 == 0x23:
                    power_state = True
                    break
                elif byte1 == 0x24:
                    power_state = False
                    break

        return {
            "product_id": 0x00,  # IOTBT device
            "power_state": power_state,
            "format": "iotbt_name",  # Detected by device name prefix
            "manu_id": list(manu_data.keys())[0] if manu_data else None,
            "ble_version": None,
            "fw_version": None,
            "sta": None,
            "color_mode": None,
            "rgb": None,
            "color_temp_percent": None,
            "brightness_percent": None,
            "effect_id": None,
            "effect_speed": None,
        }

    # Check for Telink BLE Mesh format (Company ID 4354)
    # Source: protocol_docs/17_device_configuration.md
    # Used by IOTBT devices (product_id=0x00/0x80)
    TELINK_COMPANY_ID = 4354  # 0x1102

    if TELINK_COMPANY_ID in manu_data:
        data = manu_data[TELINK_COMPANY_ID]

        # IOTBT devices use a CUSTOM format (NOT standard Telink BLE Mesh)
        # Source: old integration model_iotbt_0x80.py _parse_state_from_manu_data()
        # Format (bleak - company ID is dict key, not in data):
        #   Byte 0: unknown (sta or mesh prefix)
        #   Byte 1: power state (0x23=ON, 0x24=OFF)
        #   Byte 2: mode (0x66=solid color, 0x67=effect, 0x69=music)
        #   Byte 3: effect_id (when in effect/music mode)

        if len(data) >= 4:
            # Detect IOTBT custom format by checking byte 1 for power markers
            byte1 = data[1] & 0xFF
            if byte1 in (0x23, 0x24):
                # IOTBT custom format detected
                power_on = (byte1 == 0x23)
                mode = data[2] & 0xFF
                effect_id = data[3] & 0xFF if len(data) > 3 else None

                # Determine color mode from mode byte
                color_mode = None
                if mode == 0x66:
                    color_mode = 'rgb'  # Solid color mode
                elif mode == 0x67:
                    color_mode = 'effect'  # Regular effect mode
                elif mode == 0x69:
                    color_mode = 'music'  # Music reactive mode
                    # For music mode, effect_id is shifted
                    if effect_id is not None:
                        effect_id = effect_id << 8

                _LOGGER.debug(
                    "%sParsed IOTBT manu data: power=%s, mode=0x%02X (%s), effect_id=%s",
                    log_prefix, "ON" if power_on else "OFF", mode,
                    color_mode or "unknown", effect_id
                )

                return {
                    "product_id": 0x00,  # IOTBT device - use 0x00 (const.py defines IOTBT at product_id=0)
                    "power_state": power_on,
                    "format": "iotbt",
                    "manu_id": TELINK_COMPANY_ID,
                    "ble_version": None,  # IOTBT doesn't use BLE version in advertisement
                    "fw_version": None,   # Firmware version not in advertisement
                    "sta": data[0] & 0xFF,
                    "color_mode": color_mode,
                    "rgb": None,  # IOTBT doesn't include RGB in advertisement
                    "color_temp_percent": None,
                    "brightness_percent": None,
                    "effect_id": effect_id,
                    "effect_speed": None,
                }
            else:
                # Standard Telink BLE Mesh format (fallback)
                # Raw offsets: mesh_uuid@2-3, product_uuid@8-9, status@10, mesh_addr@11-12
                # Bleak offsets (subtract 2): mesh_uuid@0-1, product_uuid@6-7, status@8
                if len(data) >= 11:
                    status = data[8] & 0xFF
                    power_on = status > 0
                    mesh_address = (data[10] << 8) | data[9]

                    _LOGGER.debug(
                        "%sParsed Telink mesh manu data: status=%d, power=%s, mesh_addr=0x%04X",
                        log_prefix, status, "ON" if power_on else "OFF", mesh_address
                    )

                    return {
                        "product_id": 0x00,  # IOTBT device - use 0x00 (const.py defines IOTBT at product_id=0)
                        "power_state": power_on,
                        "format": "telink_mesh",
                        "manu_id": TELINK_COMPANY_ID,
                        "mesh_address": mesh_address,
                        "status": status,
                        "ble_version": None,
                        "fw_version": None,
                        "sta": None,
                        "color_mode": None,
                        "rgb": None,
                        "color_temp_percent": None,
                        "brightness_percent": None,
                        "effect_id": None,
                        "effect_speed": None,
                    }
        else:
            _LOGGER.debug(
                "%sTelink data too short: %d bytes (expected 4+)",
                log_prefix, len(data)
            )

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

        # Check for IOTBT device advertising with 0x5Axx company ID
        # Source: old integration model_iotbt_0x80.py
        # IOTBT format has power marker (0x23/0x24) at byte 1 and product_id=0x00
        byte1 = data[1] & 0xFF
        bytes8_9_product = (data[8] << 8) | data[9]

        if bytes8_9_product == 0x00 and byte1 in (0x23, 0x24):
            # IOTBT device using 0x5Axx company ID with IOTBT data format
            # Byte 1 = power state (0x23=ON, 0x24=OFF)
            # Byte 2 = mode (0x66=solid, 0x67=effect, 0x69=music)
            # Byte 3 = effect_id
            power_on = (byte1 == 0x23)
            mode = data[2] & 0xFF if len(data) > 2 else 0
            iotbt_effect_id = data[3] & 0xFF if len(data) > 3 else None

            color_mode = None
            if mode == 0x66:
                color_mode = 'rgb'
            elif mode == 0x67:
                color_mode = 'effect'
            elif mode == 0x69:
                color_mode = 'music'
                if iotbt_effect_id is not None:
                    iotbt_effect_id = iotbt_effect_id << 8

            _LOGGER.debug(
                "%sDetected IOTBT device (0x5Axx company ID): power=%s, mode=0x%02X (%s), effect=%s",
                log_prefix, "ON" if power_on else "OFF", mode, color_mode or "unknown", iotbt_effect_id
            )

            return {
                "product_id": 0x00,  # IOTBT device
                "power_state": power_on,
                "format": "iotbt_5axx",  # IOTBT format with 0x5Axx company ID
                "manu_id": manu_id,
                "ble_version": None,  # IOTBT doesn't use standard BLE version
                "fw_version": None,   # Firmware version not in advertisement
                "sta": data[0] & 0xFF,
                "color_mode": color_mode,
                "rgb": None,
                "color_temp_percent": None,
                "brightness_percent": None,
                "effect_id": iotbt_effect_id,
                "effect_speed": None,
            }

        # Parse Format B fields (standard ZengGe format)
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
                elif 1 <= sub_mode <= 10:
                    # Settled Mode effect (Symphony devices has_ic_config)
                    # mode_type=0x61 with sub_mode=1-10 indicates Settled effect
                    # RGB is in bytes 18-20 (foreground color)
                    # Speed is in byte 17
                    color_mode = 'settled'
                    effect_id = sub_mode  # Settled effect 1-10
                    rgb = (data[18], data[19], data[20])
                    effect_speed = data[17]  # Speed for settled effects
                    _LOGGER.debug(
                        "%sManu data Settled Mode effect: id=%d, rgb=%s, speed=%d",
                        log_prefix, effect_id, rgb, effect_speed
                    )
                else:
                    # Log full state bytes for debugging unknown sub-modes
                    state_bytes = ' '.join(f'{b:02X}' for b in data[14:min(25, len(data))])
                    _LOGGER.debug(
                        "%sManu data unknown sub-mode: 0x%02X (mode_type=0x61), "
                        "state_bytes[14:24]: %s",
                        log_prefix, sub_mode, state_bytes
                    )
            elif mode_type == 0x25:
                # Effect mode - interpretation depends on device type
                # For Symphony/Addressable: sub_mode is the effect ID directly
                # For SIMPLE devices: sub_mode may be offset by 20 from actual effect ID (37-56)
                color_mode = 'effect'
                effect_id = sub_mode  # Effect ID in sub_mode byte

                # Check if this might be a SIMPLE effect (offset by 20)
                # SIMPLE effects are 37-56, so sub_mode 17-36 → effect_id 37-56
                if 17 <= sub_mode <= 36:
                    # Could be SIMPLE effect with 20 offset
                    possible_simple_id = sub_mode + 20
                    _LOGGER.debug("%sManu data effect mode (0x25): sub_mode=%d, "
                                  "possible_simple_id=%d, bright_pct=%d, speed=%d",
                                  log_prefix, sub_mode, possible_simple_id, data[18], data[19])
                    effect_id = possible_simple_id
                else:
                    _LOGGER.debug("%sManu data effect mode (0x25): id=%d, bright_pct=%d, speed=%d",
                                  log_prefix, effect_id, data[18], data[19])

                brightness_percent = data[18]  # 0-100
                effect_speed = data[19]  # 0-100
            elif 37 <= mode_type <= 56:
                # SIMPLE effect mode (0x61 command) - mode_type IS the effect ID (37-56)
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
            elif mode_type in (0x5D, 0x62):
                # Sound reactive mode (built-in microphone)
                # 0x5D (93) - SIMPLE devices with mic (e.g., product 0x08 Ctrl_Mini_RGB_Mic)
                # 0x62 (98) - Symphony devices with mic
                color_mode = 'sound_reactive'
                effect_id = 0x100  # Special ID for Sound Reactive (same as IOTBT_MUSIC_EFFECTS)
                # Byte 17: SENSITIVITY - command uses 1-100, adv may use different scale
                # Brightness is NOT available in sound reactive advertisement data
                sensitivity_raw = data[17] if len(data) > 17 else 0
                # Map sensitivity to effect_speed (0-100) for UI
                # If value is 1-100, use directly; if 1-31 (IR remote scale), map to 0-100
                if sensitivity_raw <= 0:
                    effect_speed = 50  # Default if invalid
                elif sensitivity_raw <= 31:
                    # IR remote uses 1-31 scale, map to 1-100
                    effect_speed = max(1, int(sensitivity_raw * 100 / 31))
                elif sensitivity_raw <= 100:
                    # App/BLE uses 1-100 scale directly
                    effect_speed = sensitivity_raw
                else:
                    effect_speed = 100  # Cap at 100
                # Bytes 18-20: real-time RGB color (changes with sound) - often 0,0,0 when idle
                if len(data) > 20:
                    rgb = (data[18], data[19], data[20])
                state_bytes = ' '.join(f'{b:02X}' for b in data[14:min(25, len(data))])
                _LOGGER.debug("%sManu data sound reactive mode: mode_type=0x%02X, sensitivity_raw=%d, speed=%d%%, rgb=%s, state_bytes[14:24]: %s",
                              log_prefix, mode_type, sensitivity_raw, effect_speed, rgb, state_bytes)
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
        elif color_mode == "sound_reactive":
            _LOGGER.debug("%s  Sound reactive state: sensitivity/speed=%s%%, rgb=%s",
                          log_prefix, effect_speed, rgb)

        return result

    # No valid manufacturer data found
    _LOGGER.debug("%sNo valid LEDnetWF manufacturer data found in: %s",
                  log_prefix, {hex(k): len(v) for k, v in manu_data.items()})
    return None


# =============================================================================
# SERVICE DATA PARSING (BLE v5+)
# =============================================================================

# Service UUID for LEDnetWF devices
SERVICE_UUID_FFFF = "0000ffff-0000-1000-8000-00805f9b34fb"
SERVICE_UUID_SHORT = 0xFFFF


def parse_service_data(service_data: bytes) -> dict | None:
    """
    Parse LEDnetWF service data (16 or 29 bytes).

    Source: protocol_docs/17_device_configuration.md - Service Data Format

    Service data provides device identification and version information.
    For BLE v5+ devices, service data contains firmware version, LED version,
    and other device-specific information.

    Args:
        service_data: Raw service data bytes (16 or 29 bytes)

    Returns:
        Dict with device identification and version info, or None if invalid

    Format (16-byte minimum):
        Byte 0: sta - Status byte (255 = OTA mode)
        Byte 1: mfr_hi - Manufacturer prefix (0x5A or 0x5B)
        Byte 2: mfr_lo - Manufacturer low byte
        Byte 3: ble_version - BLE protocol version
        Byte 4-9: mac_address - Device MAC (6 bytes)
        Byte 10-11: product_id - Product ID (big-endian)
        Byte 12: firmware_ver_lo - Firmware version low byte
        Byte 13: led_version - LED/hardware version
        Byte 14: check_key + fw_hi - Bits 0-1: check_key, Bits 2-7: firmware high (BLE v6+)
        Byte 15: firmware_flag - Feature flags (bits 0-4)
    """
    # Handle IOTBT 14-byte format (Telink BLE Mesh)
    # Format: [status][ble_ver][MAC 6 bytes][mesh_addr 2 bytes][led_ver][mode][flags][flags2]
    # Status byte can be 0x80 (standard) or 0x56 (variant seen on some IOTBT devices)
    # or other values. The 14-byte length with UUID 0x5A00 is the distinctive marker.
    if len(service_data) == 14:
        sta = service_data[0] & 0xFF
        ble_version = service_data[1] & 0xFF
        mac_bytes = service_data[2:8]
        mesh_addr = (service_data[8] << 8) | service_data[9]
        led_version = service_data[10] & 0xFF
        mode = service_data[11] & 0xFF
        flags = service_data[12] & 0xFF
        flags2 = service_data[13] & 0xFF

        mac_address = ":".join(f"{b:02X}" for b in mac_bytes)

        _LOGGER.debug(
            "Parsed IOTBT service data (14-byte format): sta=0x%02X, ble_v=%d, mac=%s, "
            "mesh_addr=0x%04X, led_ver=%d, mode=0x%02X, flags=0x%02X",
            sta, ble_version, mac_address, mesh_addr, led_version, mode, flags
        )

        return {
            "sta": sta,
            "is_ota_mode": False,
            "is_iotbt": True,
            "ble_version": ble_version,
            "mac_address": mac_address,
            "mesh_address": mesh_addr,
            "led_version": led_version,
            "firmware_ver": led_version,  # Use led_version as firmware indicator
            "firmware_ver_str": str(led_version),
            "firmware_flag": flags,
            "product_id": 0,  # IOTBT always product_id=0
        }

    if len(service_data) < 16:
        _LOGGER.debug("Service data too short: %d bytes (need 16)", len(service_data))
        return None

    # Check manufacturer prefix (0x5A or 0x5B) for standard ZengGe format
    mfr_hi = service_data[1] & 0xFF
    if mfr_hi not in (0x5A, 0x5B):
        _LOGGER.debug("Service data invalid manufacturer prefix: 0x%02X", mfr_hi)
        return None

    sta = service_data[0] & 0xFF
    manufacturer = (mfr_hi << 8) | (service_data[2] & 0xFF)
    ble_version = service_data[3] & 0xFF
    mac_bytes = service_data[4:10]
    product_id = (service_data[10] << 8) | service_data[11]
    firmware_ver_lo = service_data[12] & 0xFF
    led_version = service_data[13] & 0xFF

    # Extended firmware version for BLE v6+
    firmware_ver = firmware_ver_lo
    check_key_flag = 0
    firmware_flag = 0

    if ble_version >= 6 and len(service_data) >= 16:
        byte14 = service_data[14] & 0xFF
        byte15 = service_data[15] & 0xFF
        check_key_flag = byte14 & 0x03        # bits 0-1
        firmware_ver_hi = (byte14 >> 2) & 0x3F  # bits 2-7
        firmware_ver = firmware_ver_lo | (firmware_ver_hi << 8)
        firmware_flag = byte15 & 0x1F         # bits 0-4

    # Format MAC address for display
    mac_address = ":".join(f"{b:02X}" for b in mac_bytes)

    # Format firmware version string
    fw_version_str = f"{firmware_ver}"
    if ble_version >= 6 and firmware_ver > 255:
        fw_version_str = f"{firmware_ver >> 8}.{firmware_ver & 0xFF}"

    _LOGGER.debug(
        "Parsed service data: sta=%d, mfr=0x%04X, ble_v=%d, mac=%s, "
        "product_id=0x%02X (%d), fw=%s, led_ver=%d",
        sta, manufacturer, ble_version, mac_address,
        product_id, product_id, fw_version_str, led_version
    )

    return {
        "sta": sta,
        "is_ota_mode": sta == 0xFF,
        "manufacturer": manufacturer,
        "ble_version": ble_version,
        "mac_address": mac_address,
        "product_id": product_id,
        "firmware_ver": firmware_ver,
        "firmware_ver_str": fw_version_str,
        "led_version": led_version,
        "check_key_flag": check_key_flag,
        "firmware_flag": firmware_flag,
    }


def parse_service_data_with_state(service_data: bytes) -> dict | None:
    """
    Parse 29-byte service data that includes power state.

    Source: protocol_docs/17_device_configuration.md - 29-byte Service Data

    When service data is 29 bytes, byte 16 contains power state:
        Byte 16: power - 0x23 = ON, 0x24 = OFF

    Args:
        service_data: Raw service data (29 bytes)

    Returns:
        Dict with device info and power state, or None if invalid
    """
    if len(service_data) < 29:
        return parse_service_data(service_data)

    result = parse_service_data(service_data)
    if result is None:
        return None

    # Extract power state from byte 16
    power_byte = service_data[16] & 0xFF
    if power_byte == 0x23:
        result["power_on"] = True
    elif power_byte == 0x24:
        result["power_on"] = False
    else:
        result["power_on"] = None

    _LOGGER.debug(
        "Service data (29-byte): power=%s (byte16=0x%02X)",
        "ON" if result.get("power_on") else "OFF" if result.get("power_on") is False else "unknown",
        power_byte
    )

    return result


def parse_v7_with_service_data(
    service_data: bytes,
    mfr_data: bytes,
    device_name: str | None = None
) -> dict | None:
    """
    Parse BLE v7+ advertisement with service data.

    Source: protocol_docs/17_device_configuration.md - BLE v7+ with Service Data

    For BLE v7+ devices that have both service data AND manufacturer data:
    - Device identification comes from service data
    - State data comes from manufacturer data at OFFSET 3 (not 14!)

    Args:
        service_data: 16 bytes from service data AD type (UUID 0xFFFF)
        mfr_data: 27+ bytes from manufacturer data AD type

    Returns:
        Dict with device info and state, or None if invalid
    """
    log_prefix = f"[{device_name}] " if device_name else ""

    # Device ID and version from service data
    device_info = parse_service_data(service_data)
    if device_info is None:
        _LOGGER.debug("%sService data parsing failed", log_prefix)
        return None

    ble_version = device_info["ble_version"]

    # For v7+, state is in manufacturer data at offset 3
    if ble_version >= 7 and len(mfr_data) >= 28:
        state_data = mfr_data[3:28]  # 25 bytes starting at offset 3

        # Power state is at state_data[11] (= mfr_data[14])
        power_byte = state_data[11] & 0xFF
        if power_byte == 0x23:
            device_info["power_on"] = True
        elif power_byte == 0x24:
            device_info["power_on"] = False
        else:
            device_info["power_on"] = None

        # Mode type at state_data[12] (= mfr_data[15])
        mode_type = state_data[12] & 0xFF
        sub_mode = state_data[13] & 0xFF

        device_info["state_data"] = state_data
        device_info["mode_type"] = mode_type
        device_info["sub_mode"] = sub_mode

        _LOGGER.debug(
            "%sBLE v7+ parsed: power=%s, mode=0x%02X, sub_mode=0x%02X",
            log_prefix,
            "ON" if device_info.get("power_on") else "OFF",
            mode_type, sub_mode
        )

    return device_info


def get_service_data_from_advertisement(
    service_data_dict: dict[str, bytes]
) -> bytes | None:
    """
    Extract LEDnetWF service data from advertisement service data dict.

    Home Assistant's BluetoothServiceInfoBleak provides service_data as a dict
    mapping UUID strings to bytes.

    LEDnetWF devices may use different service UUIDs:
    - 0xFFFF: Standard service UUID
    - 0x5A00: ZengGe manufacturer-specific (seen on IOTBT devices)
    - 0x5B00: ZengGe manufacturer-specific variant

    Args:
        service_data_dict: Dict from BluetoothServiceInfoBleak.service_data

    Returns:
        Service data bytes if found, or None
    """
    # Try full UUID (0xFFFF)
    if SERVICE_UUID_FFFF in service_data_dict:
        return service_data_dict[SERVICE_UUID_FFFF]

    # Try short UUID as string (some platforms use this format)
    short_uuid_str = f"0000{SERVICE_UUID_SHORT:04x}-0000-1000-8000-00805f9b34fb"
    if short_uuid_str in service_data_dict:
        return service_data_dict[short_uuid_str]

    # Try ZengGe manufacturer-specific UUIDs (0x5A00, 0x5B00)
    # These are used by IOTBT and possibly other devices
    for prefix in ("5a00", "5b00"):
        uuid_str = f"0000{prefix}-0000-1000-8000-00805f9b34fb"
        if uuid_str in service_data_dict:
            return service_data_dict[uuid_str]

    # Try just "ffff" or "FFFF" as fallback
    for key in service_data_dict:
        if "ffff" in key.lower():
            return service_data_dict[key]

    return None


def is_iotbt_segment_variant(service_data_dict: dict[str, bytes]) -> bool:
    """
    Check if device is an IOTBT segment-based variant.

    Segment-based IOTBT devices are identified by:
    - Service UUID 0x5A00 (ZengGe manufacturer-specific)
    - Status byte (byte 0) is 0x56

    Standard IOTBT devices (status byte 0x80) use Telink mesh protocol.
    Unknown status bytes default to standard Telink protocol for safety.

    Segment-based variants (status 0x56) use different commands:
    - Power: 0x3B (standard LEDnetWF, not 0x71 Telink)
    - Color: 0xE1 0x03 (segment-based HSB, not 0xE2 hue)
    - Effects: 0xE1 0x01 (palette-based, not 0xE0 0x02)

    Args:
        service_data_dict: Dict from BluetoothServiceInfoBleak.service_data

    Returns:
        True if segment-based IOTBT variant (status 0x56), False otherwise
    """
    uuid_5a00 = "00005a00-0000-1000-8000-00805f9b34fb"
    if uuid_5a00 not in service_data_dict:
        return False

    data = service_data_dict[uuid_5a00]
    if len(data) < 1:
        return False

    # Status byte 0x80 = standard IOTBT (Telink mesh protocol) - DEFAULT
    # Status byte 0x56 = segment-based variant
    # Unknown values default to standard Telink for safety
    status_byte = data[0] & 0xFF
    return status_byte == 0x56
