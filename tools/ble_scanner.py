#!/usr/bin/env python3
"""
LEDnetWF BLE Device Scanner

Scans for BLE devices matching LEDnetWF manufacturer IDs and decodes
their manufacturer data advertisements.

This tool is used to:
1. Discover compatible devices
2. Validate protocol documentation against real hardware
3. Understand device capabilities before connecting
4. Actively probe devices to detect RGB/WW/CW capabilities

Data parsed from advertisements (no connection required):
- Device identification (name, MAC, manufacturer ID)
- Product ID → device capabilities mapping
- Firmware version (basic or extended for BLE v6+)
- BLE/protocol version
- Power state, color mode (from embedded state data)
- RGB, brightness, WW/CW values (format may vary by device)

Capability Detection (see protocol_docs/08_state_query_response_parsing.md):
- Passive detection: Infer capabilities from state query response
- Active probing: Send test commands to definitively detect RGB/WW/CW
- Capabilities are cached by MAC address (~/.lednetwf_capabilities.json)

Protocol documentation: ../protocol_docs/

Limitations:
- Advertisement state data format varies by device - values shown may not
  be accurate until validated against specific hardware
- BLE v7+ devices have extended 24-byte state; scanner shows partial subset
- Stub devices (e.g., FillLight_0x1D) require connection and state query
  to determine actual capabilities (RGB/WW/CW support)

Usage:
    python ble_scanner.py [--duration SECONDS] [--continuous]
    python ble_scanner.py --interactive        # Scan then connect interactively
    python ble_scanner.py --connect AA:BB:CC:DD:EE:FF  # Connect directly by MAC
    python ble_scanner.py --connect AA:BB:CC:DD:EE:FF --probe  # Connect and probe capabilities
    python ble_scanner.py --clear-cache        # Clear cached capabilities
"""

import asyncio
import argparse
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Tuple
from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


# =============================================================================
# BLE VERSION DETECTION
# Source: protocol_docs/04_device_identification_capabilities.md
# The BLE version is extracted from the device name suffix (e.g., "LEDnetWF07" → 7)
# This determines which power command format to use:
#   < 5:  Use 0x71 command (legacy)
#   >= 5: Use 0x3B command (modern)
# =============================================================================

# Pattern to extract version number from device name
# Matches: LEDnetWF07, LEDnetWF_07, iotwf10, IOTBT_11, etc.
BLE_VERSION_PATTERN = re.compile(r'(?:lednetwf|iotwf|iotbt)[_]?(\d+)', re.IGNORECASE)


def extract_ble_version_from_name(device_name: Optional[str]) -> Optional[int]:
    """
    Extract BLE protocol version from device name suffix.

    Examples:
        "LEDnetWF07" → 7
        "LEDnetWF_10" → 10
        "iotwf05" → 5
        "IOTBT_11" → 11
        "Unknown" → None

    Source: protocol_docs/04_device_identification_capabilities.md
    The app extracts version from BaseModuleType.f23897c field.
    """
    if not device_name:
        return None

    match = BLE_VERSION_PATTERN.search(device_name)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass
    return None


def get_recommended_power_command(ble_version: Optional[int]) -> str:
    """
    Get the recommended power command type based on BLE version.

    From protocol_docs/04_device_identification_capabilities.md:
        Version < 5:  Use 0x71 (legacy)
        Version >= 5: Use 0x3B (modern)

    Returns:
        "0x3B" for modern devices (BLE v5+)
        "0x71" for legacy devices (BLE v1-4)
        "0x3B" as default if version unknown (most devices are modern)
    """
    if ble_version is None:
        return "0x3B"  # Default to modern, most common

    if ble_version >= 5:
        return "0x3B"
    else:
        return "0x71"


# Manufacturer ID ranges from protocol doc (Section 9.1)
# Primary range: 23120-23122 (0x5A50-0x5A52)
# Extended ranges: various in 0x5A00-0x5AFF
VALID_MANUFACTURER_ID_MIN = 0x5A00  # 23040
VALID_MANUFACTURER_ID_MAX = 0x5AFF  # 23295

# Specific valid ranges from Java code
EXACT_MATCH_IDS = set(range(23123, 23134))  # 23123-23133
VALID_RANGES = [
    (23120, 23122),   # Primary: 0x5A50-0x5A52
    (23072, 23087),   # Range 1: 0x5A20-0x5A2F
    (23136, 23151),   # Range 2: 0x5A60-0x5A6F
    (23152, 23167),   # Range 3: 0x5A70-0x5A7F
    (23168, 23183),   # Range 4: 0x5A80-0x5A8F
]

# Device name patterns to look for (checked case-insensitively)
NAME_PATTERNS = ["lednetwf", "iotwf", "iotbt"]

# BLE Characteristic UUIDs for device communication
WRITE_CHARACTERISTIC_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_CHARACTERISTIC_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

# Command packets from protocol doc
# State query command: [0x81, 0x8A, 0x8B, 0x40] where 0x40 is checksum
STATE_QUERY_RAW = bytearray([0x81, 0x8A, 0x8B, 0x40])

# State query wrapped in transport layer (what the HA integration uses)
# Format: [seq, flags, cmdId, len_hi, len_lo, ...payload...]
STATE_QUERY_WRAPPED = bytearray.fromhex("00 01 80 00 00 04 05 0a 81 8a 8b 96")

# GET_LED_SETTINGS packet (queries LED strip configuration)
GET_LED_SETTINGS_PACKET = bytearray.fromhex("00 02 80 00 00 05 06 0a 63 12 21 f0 86")

# Capability detection probe commands (from protocol doc section 10.5.8)
# These are used when device is OFF or in effect mode (all channels may be 0)
# Each probe sets a specific channel to test if the device supports it

# RGB Probe: Set R=50, G=0, B=0 in static RGB mode
# Format from protocol_docs/07_control_commands.md:
# [0x31, R, G, B, WW, CW, Mode(0x5A), Persist, Checksum] - 9 bytes
RGB_PROBE_RAW = bytearray([0x31, 0x32, 0x00, 0x00, 0x00, 0x00, 0x5A, 0x0F])
RGB_PROBE_RAW.append(sum(RGB_PROBE_RAW) & 0xFF)  # Checksum of bytes 0-7

# WW Probe: Set warm white to 50 in static white mode
# Format: [0x31, R, G, B, WW, CW, Mode(0x0F=white), Persist, Checksum]
WW_PROBE_RAW = bytearray([0x31, 0x00, 0x00, 0x00, 0x32, 0x00, 0x0F, 0x0F])
WW_PROBE_RAW.append(sum(WW_PROBE_RAW) & 0xFF)  # Checksum of bytes 0-7

# CW Probe: Set cool white to 50 in static white mode
# Format: [0x31, R, G, B, WW, CW, Mode(0x0F=white), Persist, Checksum]
CW_PROBE_RAW = bytearray([0x31, 0x00, 0x00, 0x00, 0x00, 0x32, 0x0F, 0x0F])
CW_PROBE_RAW.append(sum(CW_PROBE_RAW) & 0xFF)  # Checksum of bytes 0-7

# =============================================================================
# POWER COMMANDS - Multiple versions depending on device BLE protocol version
# Source: com/zengge/wifi/COMM/Protocol/q.java
#
# Version selection logic (from BaseDeviceInfo.E()):
#   BLE version >= 5: Use 0x3B command with PowerType mode byte
#   BLE version < 5:  Use 0x71 command
#   Very old devices: Use 0x11 command (legacy, often doesn't work)
#
# PowerType enum (from CommandPackagePowerOverDuraion.java):
#   PowerType_PowerON  = 0x23 (35)
#   PowerType_PowerOFF = 0x24 (36)
#   PowerType_PowerSwitch = 0x25 (37) - toggle
# =============================================================================

# Modern power command (0x3B) - BLE v5+ - RECOMMENDED for most devices
# Source: tc/d.java method c() + CommandPackagePowerOverDuraion.java
# Format: [0x3B, PowerType, HSV(0,0), params(0,0,0), duration(0,0,50), time(0,0), checksum]
# These are PRE-WRAPPED with transport layer header - send directly, no wrapping needed!
POWER_ON_0x3B_WRAPPED = bytearray.fromhex("00 01 80 00 00 0d 0e 0b 3b 23 00 00 00 00 00 00 00 32 00 00 90")
POWER_OFF_0x3B_WRAPPED = bytearray.fromhex("00 01 80 00 00 0d 0e 0b 3b 24 00 00 00 00 00 00 00 32 00 00 91")

# Legacy power command (0x71) - BLE v1-4
# Source: tc/b.java method M() lines 759-772
# Format: [0x71, state(0x23/0x24), persist(0x0F), checksum]
POWER_ON_0x71_RAW = bytearray([0x71, 0x23, 0x0F])
POWER_ON_0x71_RAW.append(sum(POWER_ON_0x71_RAW) & 0xFF)  # = 0xA3

POWER_OFF_0x71_RAW = bytearray([0x71, 0x24, 0x0F])
POWER_OFF_0x71_RAW.append(sum(POWER_OFF_0x71_RAW) & 0xFF)  # = 0xA4

# Very old power command (0x11) - legacy, often doesn't work on modern devices
# Source: tc/b.java method m() lines 1648-1657
# Format: [0x11, 0x1A, 0x1B, state, checksum]
POWER_ON_0x11_RAW = bytearray([0x11, 0x1A, 0x1B, 0xF0])
POWER_ON_0x11_RAW.append(sum(POWER_ON_0x11_RAW) & 0xFF)  # = 0xE6

POWER_OFF_0x11_RAW = bytearray([0x11, 0x1A, 0x1B, 0x0F])
POWER_OFF_0x11_RAW.append(sum(POWER_OFF_0x11_RAW) & 0xFF)  # = 0x55

# Aliases for backward compatibility (HA integration uses these names)
HA_POWER_ON_WRAPPED = POWER_ON_0x3B_WRAPPED
HA_POWER_OFF_WRAPPED = POWER_OFF_0x3B_WRAPPED
POWER_ON_RAW = POWER_ON_0x11_RAW   # Legacy alias (often doesn't work)
POWER_OFF_RAW = POWER_OFF_0x11_RAW  # Legacy alias (often doesn't work)

# Capability cache file location
CAPABILITY_CACHE_FILE = os.path.expanduser("~/.lednetwf_capabilities.json")

# Product ID to capability mapping from protocol_docs/04_device_identification_capabilities.md
# Source: com/zengge/wifi/Device/a.java method k()
# Capabilities: has_rgb, has_ww (warm white), has_cw (cool white), has_dim (dimmer only)
# BaseType indicates the class hierarchy from the app
PRODUCT_ID_CAPABILITIES = {
    # Controllers with RGB + White (RGBWBoth / RGBCWBoth BaseType)
    4:   {"name": "Ctrl_RGBW_UFO_0x04", "has_rgb": True, "has_ww": True, "has_cw": False, "base_type": "RGBW"},
    6:   {"name": "Ctrl_Mini_RGBW_0x06", "has_rgb": True, "has_ww": True, "has_cw": False, "base_type": "RGBWBoth"},
    7:   {"name": "Ctrl_Mini_RGBCW_0x07", "has_rgb": True, "has_ww": True, "has_cw": True, "base_type": "RGBCWBoth"},
    32:  {"name": "Ctrl_Mini_RGBW_0x20", "has_rgb": True, "has_ww": True, "has_cw": False, "base_type": "RGBWBoth"},
    37:  {"name": "Ctrl_RGBCW_Both_0x25", "has_rgb": True, "has_ww": True, "has_cw": True, "base_type": "RGBCWBoth"},
    38:  {"name": "Ctrl_Mini_RGBW_0x26", "has_rgb": True, "has_ww": True, "has_cw": False, "base_type": "RGBWBoth"},
    39:  {"name": "Ctrl_Mini_RGBW_0x27", "has_rgb": True, "has_ww": True, "has_cw": False, "base_type": "RGBWBoth"},
    72:  {"name": "Ctrl_Mini_RGBW_Mic_0x48", "has_rgb": True, "has_ww": True, "has_cw": False, "base_type": "RGBWBoth"},

    # Controllers with RGB only (RGB / RGBSymphony BaseType)
    8:   {"name": "Ctrl_Mini_RGB_Mic_0x08", "has_rgb": True, "has_ww": False, "has_cw": False, "base_type": "RGBSymphony"},
    16:  {"name": "ChristmasLight_0x10", "has_rgb": True, "has_ww": False, "has_cw": False, "base_type": "RGB"},
    51:  {"name": "Ctrl_Mini_RGB_0x33", "has_rgb": True, "has_ww": False, "has_cw": False, "base_type": "RGB"},

    # CCT only - no RGB (CCT BaseType)
    9:   {"name": "Ctrl_Ceiling_light_CCT_0x09", "has_rgb": False, "has_ww": True, "has_cw": True, "base_type": "CCT"},
    22:  {"name": "Magnetic_CCT_0x16", "has_rgb": False, "has_ww": True, "has_cw": True, "base_type": "CCT"},
    28:  {"name": "TableLamp_CCT_0x1C", "has_rgb": False, "has_ww": True, "has_cw": True, "base_type": "CCT"},
    82:  {"name": "Bulb_CCT_0x52", "has_rgb": False, "has_ww": True, "has_cw": True, "base_type": "CCT"},
    98:  {"name": "Ctrl_CCT_0x62", "has_rgb": False, "has_ww": True, "has_cw": True, "base_type": "CCT"},

    # Dimmer only (Brightness BaseType)
    23:  {"name": "Magnetic_Dim_0x17", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "base_type": "Brightness"},
    33:  {"name": "Bulb_Dim_0x21", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "base_type": "Brightness"},
    65:  {"name": "Ctrl_Dim_0x41", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "base_type": "Brightness"},

    # Bulbs with RGBCW (RGBCWBulb / RGBWBulb BaseType)
    14:  {"name": "FloorLamp_RGBCW_0x0E", "has_rgb": True, "has_ww": True, "has_cw": True, "base_type": "RGBCWBoth"},
    30:  {"name": "CeilingLight_RGBCW_0x1E", "has_rgb": True, "has_ww": True, "has_cw": True, "base_type": "RGBCWBoth"},
    53:  {"name": "Bulb_RGBCW_R120_0x35", "has_rgb": True, "has_ww": True, "has_cw": True, "base_type": "RGBCWBulb"},
    59:  {"name": "Bulb_RGBCW_0x3B", "has_rgb": True, "has_ww": True, "has_cw": True, "base_type": "RGBCWBulb"},
    68:  {"name": "Bulb_RGBW_0x44", "has_rgb": True, "has_ww": True, "has_cw": False, "base_type": "RGBWBulb"},
    84:  {"name": "Downlight_RGBW_0X54", "has_rgb": True, "has_ww": True, "has_cw": False, "base_type": "RGBWBoth"},

    # Switches and Sockets (Switch BaseType) - on/off only, no dimming
    11:  {"name": "Switch_1c_0x0b", "has_rgb": False, "has_ww": False, "has_cw": False, "is_switch": True, "base_type": "Switch"},
    147: {"name": "Switch_1C_0x93", "has_rgb": False, "has_ww": False, "has_cw": False, "is_switch": True, "base_type": "Switch"},
    148: {"name": "Switch_1c_Watt_0x94", "has_rgb": False, "has_ww": False, "has_cw": False, "is_switch": True, "has_power_monitoring": True, "base_type": "Switch"},
    149: {"name": "Switch_2c_0x95", "has_rgb": False, "has_ww": False, "has_cw": False, "is_switch": True, "channels": 2, "base_type": "Switch"},
    150: {"name": "Switch_4c_0x96", "has_rgb": False, "has_ww": False, "has_cw": False, "is_switch": True, "channels": 4, "base_type": "Switch"},
    151: {"name": "Socket_1c_0x97", "has_rgb": False, "has_ww": False, "has_cw": False, "is_socket": True, "base_type": "Switch"},

    # Special/misc devices
    24:  {"name": "PlantLight_0x18", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "base_type": "Special"},
    25:  {"name": "Socket_2Usb_0x19", "has_rgb": False, "has_ww": False, "has_cw": False, "is_socket": True, "base_type": "Switch"},
    26:  {"name": "ChristmasLight_0x1A", "has_rgb": True, "has_ww": False, "has_cw": False, "base_type": "RGB"},
    27:  {"name": "SprayLight_0x1B", "has_rgb": True, "has_ww": False, "has_cw": False, "base_type": "Special"},
    29:  {"name": "FillLight_0x1D", "has_rgb": None, "has_ww": None, "has_cw": None, "is_stub": True, "base_type": "Special"},
    41:  {"name": "MirrorLight_0x29", "has_rgb": True, "has_ww": True, "has_cw": True, "base_type": "Special"},
    45:  {"name": "GAON_PlantLight_0x2D", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "base_type": "Special"},
    209: {"name": "Digital_Light_0xd1", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "base_type": "Special"},

    # Ceiling lights (Ceiling BaseType)
    225: {"name": "Ctrl_Ceiling_light_0xe1", "has_rgb": False, "has_ww": True, "has_cw": True, "base_type": "Ceiling"},
    226: {"name": "Ctrl_Ceiling_light_Assist_0xe2", "has_rgb": False, "has_ww": True, "has_cw": True, "base_type": "Ceiling"},

    # Symphony controllers - addressable RGB with effects (RGBSymphony / RGBNewSymphony BaseType)
    161: {"name": "Ctrl_Mini_RGB_Symphony_0xa1", "has_rgb": True, "has_ww": False, "has_cw": False, "effects": 100, "base_type": "RGBSymphony"},
    162: {"name": "Ctrl_Mini_RGB_Symphony_new_0xa2", "has_rgb": True, "has_ww": False, "has_cw": False, "effects": 100, "base_type": "RGBNewSymphony"},
    163: {"name": "Ctrl_Mini_RGB_Symphony_new_0xA3", "has_rgb": True, "has_ww": False, "has_cw": False, "effects": 100, "base_type": "RGBNewSymphony"},
    164: {"name": "Ctrl_Mini_RGB_Symphony_new_0xA4", "has_rgb": True, "has_ww": False, "has_cw": False, "effects": 100, "base_type": "RGBNewSymphony"},
    166: {"name": "Ctrl_Mini_RGB_Symphony_new_0xA6", "has_rgb": True, "has_ww": False, "has_cw": False, "effects": 100, "base_type": "RGBNewSymphony"},
    167: {"name": "Ctrl_Mini_RGB_Symphony_new_0xA7", "has_rgb": True, "has_ww": False, "has_cw": False, "effects": 100, "base_type": "RGBNewSymphony"},
    169: {"name": "Ctrl_Mini_RGB_Symphony_new_0xA9", "has_rgb": True, "has_ww": False, "has_cw": False, "effects": 100, "base_type": "RGBNewSymphony"},

    # Unknown/None
    0:   {"name": "TypeNone", "has_rgb": None, "has_ww": None, "has_cw": None, "is_stub": True, "base_type": "None"},
}


@dataclass
class DeviceCapabilities:
    """
    Detected device capabilities from protocol doc section 10.5.8.

    These are determined by:
    1. Product ID lookup (initial guess from PRODUCT_ID_CAPABILITIES)
    2. State query response (check which channels have non-zero values)
    3. Active probing (definitively test each channel if needed)
    """
    has_rgb: bool = False
    has_ww: bool = False  # Warm white
    has_cw: bool = False  # Cool white
    is_dimmable: bool = True  # Most devices support brightness

    # Detection metadata
    detection_method: str = "unknown"  # "product_id", "state_query", "active_probe"
    detected_at: Optional[str] = None
    product_id: Optional[int] = None
    mac_address: Optional[str] = None

    # Confidence flags - True means we're certain about this capability
    rgb_confirmed: bool = False
    ww_confirmed: bool = False
    cw_confirmed: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceCapabilities":
        """Create from dictionary (for JSON deserialization)."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @property
    def color_mode_str(self) -> str:
        """Determine Home Assistant color mode from capabilities."""
        if self.has_rgb and (self.has_ww or self.has_cw):
            return "RGBWW" if self.has_ww and self.has_cw else "RGBW"
        elif self.has_rgb:
            return "RGB"
        elif self.has_ww and self.has_cw:
            return "COLOR_TEMP"
        elif self.has_ww or self.has_cw:
            return "WHITE"
        elif self.is_dimmable:
            return "BRIGHTNESS"
        else:
            return "ONOFF"


def load_capability_cache() -> dict:
    """Load cached capabilities from file."""
    if os.path.exists(CAPABILITY_CACHE_FILE):
        try:
            with open(CAPABILITY_CACHE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_capability_cache(cache: dict):
    """Save capabilities cache to file."""
    try:
        with open(CAPABILITY_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except IOError as e:
        print(f"  Warning: Could not save capability cache: {e}")


def get_cached_capabilities(mac_address: str) -> Optional[DeviceCapabilities]:
    """Get cached capabilities for a device by MAC address."""
    cache = load_capability_cache()
    key = f"caps_{mac_address.replace(':', '_')}"
    if key in cache:
        return DeviceCapabilities.from_dict(cache[key])
    return None


def cache_capabilities(mac_address: str, caps: DeviceCapabilities):
    """Cache capabilities for a device by MAC address."""
    cache = load_capability_cache()
    key = f"caps_{mac_address.replace(':', '_')}"
    caps.mac_address = mac_address
    caps.detected_at = datetime.now().isoformat()
    cache[key] = caps.to_dict()
    save_capability_cache(cache)


def wrap_command(raw_payload: bytes, cmd_family: int = 0x0b, seq: int = 0) -> bytearray:
    """
    Wrap a raw command payload in the transport layer format.

    Based on protocol_docs/06_transport_layer_protocol.md:

    Header format (8 bytes):
      - Byte 0: Header flags (0x00 for version 0, not segmented)
      - Byte 1: Sequence number (0-255)
      - Bytes 2-3: Frag Control (0x80, 0x00 = single complete segment)
      - Bytes 4-5: Total payload length (big-endian)
      - Byte 6: Payload length + 1 (for cmdId)
      - Byte 7: cmdId (0x0a = expects response, 0x0b = no response)

    NOTE: raw_payload should already include checksum if the command requires one.
          This function does NOT add a checksum - that's part of the command itself.

    Args:
        raw_payload: Raw command bytes (including checksum if needed)
        cmd_family: 0x0a for queries expecting response, 0x0b for commands
        seq: Sequence number (0-255)

    Returns:
        Complete wrapped packet ready to send
    """
    payload_len = len(raw_payload)

    # Build header per protocol_docs/06_transport_layer_protocol.md
    packet = bytearray(8 + payload_len)
    packet[0] = 0x00                      # Header: version 0, not segmented
    packet[1] = seq & 0xFF                # Sequence number (single byte)
    packet[2] = 0x80                      # Frag control high byte
    packet[3] = 0x00                      # Frag control low byte
    packet[4] = (payload_len >> 8) & 0xFF # Total length high byte
    packet[5] = payload_len & 0xFF        # Total length low byte
    packet[6] = (payload_len + 1) & 0xFF  # Payload length + 1
    packet[7] = cmd_family                # cmdId

    # Add payload (already includes checksum if needed)
    packet[8:] = raw_payload

    return packet


def build_rgb_probe_packet(brightness: int = 100, format_type: str = "9byte") -> bytearray:
    """
    Build a packet to set RGB color (for probing RGB capability).

    Different devices may require different command formats:
    - "9byte": [0x31, R, G, B, WW, CW, Mode(0xF0), Persist(0x0F), CS] - RGBCW devices
    - "8byte_v": [0x31, R, G, B, W, 0x00, Persist(0x0F), CS] - tc.b.v() format
    - "8byte_x": [0x31, R, G, B, W, Mode, Persist(0x0F), CS] - tc.b.x() format
    - "symphony": 0x3B HSV command for BLE v5+ devices

    Source: tc/b.java methods t(), v(), x() and tc/d.java method a()
    """
    r_value = brightness & 0xFF

    if format_type == "9byte":
        # tc.b.t() format - 9 bytes: [0x31, R, G, B, 0, 0, 0xF0, 0x0F, CS]
        raw_cmd = bytearray([0x31, r_value, 0x00, 0x00, 0x00, 0x00, 0xF0, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    elif format_type == "8byte_v":
        # tc.b.v() format - 8 bytes: [0x31, R, G, B, W, 0x00, 0x0F, CS]
        raw_cmd = bytearray([0x31, r_value, 0x00, 0x00, 0x00, 0x00, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    elif format_type == "8byte_x":
        # tc.b.x() format - 8 bytes: [0x31, R, G, B, W, mode(0xF0), 0x0F, CS]
        raw_cmd = bytearray([0x31, r_value, 0x00, 0x00, 0x00, 0xF0, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    elif format_type == "symphony":
        # tc.d.a() format - 0x3B HSV command for BLE v5+ devices
        # Mode 0xA1 (161) for color, HSV=0/100/brightness, time=30
        # [0x3B, mode, HSV_hi, HSV_lo, brightness, 0, 0, time_hi, time_mid, time_lo, 0, 0, CS]
        # For red: Hue=0, Sat=100, Val=brightness
        hue = 0
        sat = 100
        val = min(brightness, 100)  # 0-100 for brightness
        packed_hs = (hue << 7) | sat
        hs_hi = (packed_hs >> 8) & 0xFF
        hs_lo = packed_hs & 0xFF
        time_val = 30
        raw_cmd = bytearray([0x3B, 0xA1, hs_hi, hs_lo, val, 0x00, 0x00, 0x00, 0x00, time_val, 0x00, 0x00])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    else:
        raise ValueError(f"Unknown format_type: {format_type}")

    # Wrap in transport layer
    return wrap_command(raw_cmd, cmd_family=0x0b, seq=0)


def build_ww_probe_packet(brightness: int = 50, format_type: str = "9byte") -> bytearray:
    """
    Build a packet to set warm white (for probing WW capability).

    Different devices may require different command formats.
    Source: tc/b.java methods t(), v(), x()
    """
    ww_value = brightness & 0xFF

    if format_type == "9byte":
        # [0x31, R, G, B, WW, CW, 0x0F, 0x0F, CS]
        raw_cmd = bytearray([0x31, 0x00, 0x00, 0x00, ww_value, 0x00, 0x0F, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    elif format_type == "8byte_v":
        # tc.b.v() format - put WW in byte[4]
        raw_cmd = bytearray([0x31, 0x00, 0x00, 0x00, ww_value, 0x00, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    elif format_type == "8byte_x":
        # tc.b.x() format - put WW in byte[4], mode based on W>0
        raw_cmd = bytearray([0x31, 0x00, 0x00, 0x00, ww_value, 0x0F, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    else:
        raise ValueError(f"Unknown format_type: {format_type}")

    return wrap_command(raw_cmd, cmd_family=0x0b, seq=0)


def build_cw_probe_packet(brightness: int = 50, format_type: str = "9byte") -> bytearray:
    """
    Build a packet to set cool white (for probing CW capability).

    Different devices may require different command formats.
    Source: tc/b.java methods t(), v(), x()
    """
    cw_value = brightness & 0xFF

    if format_type == "9byte":
        # [0x31, R, G, B, WW, CW, 0x0F, 0x0F, CS]
        raw_cmd = bytearray([0x31, 0x00, 0x00, 0x00, 0x00, cw_value, 0x0F, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    elif format_type == "8byte_v":
        # tc.b.v() format - CW would need different handling
        # Most 8-byte devices don't have separate CW channel
        raw_cmd = bytearray([0x31, 0x00, 0x00, 0x00, cw_value, 0x00, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    elif format_type == "8byte_x":
        # tc.b.x() format
        raw_cmd = bytearray([0x31, 0x00, 0x00, 0x00, cw_value, 0x0F, 0x0F])
        raw_cmd.append(sum(raw_cmd) & 0xFF)
    else:
        raise ValueError(f"Unknown format_type: {format_type}")

    return wrap_command(raw_cmd, cmd_family=0x0b, seq=0)


def build_power_on_packet() -> bytearray:
    """
    Build a packet to turn the device ON.

    Uses the 0x11 power command from protocol_docs/07_control_commands.md.
    Format: [0x11, 0x1A, 0x1B, 0xF0, checksum]
    """
    return wrap_command(POWER_ON_RAW, cmd_family=0x0b, seq=0)


def build_power_off_packet() -> bytearray:
    """
    Build a packet to turn the device OFF.

    Uses the 0x11 power command from protocol_docs/07_control_commands.md.
    Format: [0x11, 0x1A, 0x1B, 0x0F, checksum]
    """
    return wrap_command(POWER_OFF_RAW, cmd_family=0x0b, seq=0)


async def send_power_command(device: BLEDevice, turn_on: bool) -> bool:
    """
    Connect to device and send power on/off command (legacy 0x11 version).

    Uses the 0x11 command format from tc/b.java method m() lines 1648-1657.
    NOTE: This is a very old command that DOESN'T WORK on most modern devices.
    Use send_power_command_ha() for BLE v5+ devices (recommended).
    Use send_power_command_0x71() for BLE v1-4 devices.

    Args:
        device: BLEDevice to control
        turn_on: True to turn on, False to turn off

    Returns:
        True if command was sent successfully
    """
    action = "ON" if turn_on else "OFF"
    print(f"\n  Sending POWER {action} (legacy 0x11 - often doesn't work) to {device.name or device.address}...")

    try:
        async with BleakClient(device.address, timeout=10.0) as client:
            # Find write characteristic
            write_char = None
            for service in client.services:
                for char in service.characteristics:
                    if char.uuid.lower() == WRITE_CHARACTERISTIC_UUID.lower():
                        write_char = char
                        break

            if not write_char:
                print(f"  Error: Write characteristic not found")
                return False

            # Determine write method
            use_response = "write" in write_char.properties and "write-without-response" not in write_char.properties

            # Build and send command
            packet = build_power_on_packet() if turn_on else build_power_off_packet()
            print(f"  Sending: {format_bytes_hex(packet)}")

            await client.write_gatt_char(write_char.uuid, packet, response=use_response)
            print(f"  ✓ Power {action} command sent!")
            return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def send_power_command_ha(device: BLEDevice, turn_on: bool) -> bool:
    """
    Connect to device and send power on/off command (modern 0x3B version).

    Uses the pre-wrapped 0x3B command format with PowerType mode byte.
    This is the RECOMMENDED power command for BLE v5+ devices (most modern devices).

    Source: CommandPackagePowerOverDuraion.java, tc/d.java method c()
    PowerType: 0x23 = ON, 0x24 = OFF

    Args:
        device: BLEDevice to control
        turn_on: True to turn on, False to turn off

    Returns:
        True if command was sent successfully
    """
    action = "ON" if turn_on else "OFF"
    print(f"\n  Sending POWER {action} (modern 0x3B - BLE v5+) to {device.name or device.address}...")

    try:
        async with BleakClient(device.address, timeout=10.0) as client:
            # Find write characteristic
            write_char = None
            for service in client.services:
                for char in service.characteristics:
                    if char.uuid.lower() == WRITE_CHARACTERISTIC_UUID.lower():
                        write_char = char
                        break

            if not write_char:
                print(f"  Error: Write characteristic not found")
                return False

            # Determine write method
            use_response = "write" in write_char.properties and "write-without-response" not in write_char.properties

            # Use pre-wrapped 0x3B power commands (no need to call wrap_command)
            packet = POWER_ON_0x3B_WRAPPED if turn_on else POWER_OFF_0x3B_WRAPPED
            print(f"  Sending: {format_bytes_hex(packet)}")

            await client.write_gatt_char(write_char.uuid, packet, response=use_response)
            print(f"  ✓ Power {action} command sent!")
            return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def send_power_command_0x71(device: BLEDevice, turn_on: bool) -> bool:
    """
    Connect to device and send power on/off command (legacy 0x71 version).

    Uses the 0x71 command format for BLE v1-4 devices.
    Source: tc/b.java method M() lines 759-772
    State: 0x23 = ON, 0x24 = OFF

    Args:
        device: BLEDevice to control
        turn_on: True to turn on, False to turn off

    Returns:
        True if command was sent successfully
    """
    action = "ON" if turn_on else "OFF"
    print(f"\n  Sending POWER {action} (legacy 0x71 - BLE v1-4) to {device.name or device.address}...")

    try:
        async with BleakClient(device.address, timeout=10.0) as client:
            # Find write characteristic
            write_char = None
            for service in client.services:
                for char in service.characteristics:
                    if char.uuid.lower() == WRITE_CHARACTERISTIC_UUID.lower():
                        write_char = char
                        break

            if not write_char:
                print(f"  Error: Write characteristic not found")
                return False

            # Determine write method
            use_response = "write" in write_char.properties and "write-without-response" not in write_char.properties

            # Wrap 0x71 command in transport layer
            raw_packet = POWER_ON_0x71_RAW if turn_on else POWER_OFF_0x71_RAW
            packet = wrap_command(raw_packet, cmd_family=0x0b, seq=0)
            print(f"  Sending: {format_bytes_hex(packet)}")

            await client.write_gatt_char(write_char.uuid, packet, response=use_response)
            print(f"  ✓ Power {action} command sent!")
            return True

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def send_power_command_auto(device: BLEDevice, turn_on: bool) -> bool:
    """
    Connect to device and send power on/off command with AUTO-DETECTION.

    Automatically selects the appropriate power command based on BLE version
    extracted from the device name:
        - BLE v5+: Uses modern 0x3B command
        - BLE v1-4: Uses legacy 0x71 command
        - Unknown: Defaults to 0x3B (most devices are modern)

    Source: protocol_docs/04_device_identification_capabilities.md

    Args:
        device: BLEDevice to control
        turn_on: True to turn on, False to turn off

    Returns:
        True if command was sent successfully
    """
    # Extract BLE version from device name
    ble_version = extract_ble_version_from_name(device.name)
    recommended_cmd = get_recommended_power_command(ble_version)

    action = "ON" if turn_on else "OFF"
    version_str = f"v{ble_version}" if ble_version else "unknown"
    print(f"\n  AUTO-DETECTING power command for {device.name or device.address}...")
    print(f"  BLE version: {version_str} → using {recommended_cmd} command")

    if recommended_cmd == "0x3B":
        return await send_power_command_ha(device, turn_on)
    else:
        return await send_power_command_0x71(device, turn_on)


async def detect_capabilities_via_probe(
    client: BleakClient,
    write_char_uuid: str,
    notify_char_uuid: str,
    use_response: bool = False,
    ble_version: int = 0
) -> DeviceCapabilities:
    """
    Actively probe device to detect capabilities (from protocol doc section 10.5.8).

    This function:
    1. Queries current state to save it
    2. Tries multiple command formats to find one that works
    3. Sends RGB probe command, queries state, checks if RGB channels changed
    4. Sends WW probe command, queries state, checks if WW channel changed
    5. Sends CW probe command, queries state, checks if CW channel changed
    6. Returns detected capabilities

    NOTE: This WILL change the device's current color/state temporarily.
    The caller should restore the original state afterward if needed.

    Args:
        client: Connected BleakClient
        write_char_uuid: UUID of write characteristic
        notify_char_uuid: UUID of notify characteristic
        use_response: Whether to use write-with-response
        ble_version: BLE version from manufacturer data (determines format order)

    Returns:
        DeviceCapabilities with detected flags
    """
    caps = DeviceCapabilities(detection_method="active_probe")

    # Store received notifications
    received_data = []
    notification_event = asyncio.Event()

    def notification_handler(sender, data: bytearray):
        received_data.append(bytes(data))
        notification_event.set()

    async def query_state() -> Optional['StateResponse']:
        """Send state query and wait for response."""
        received_data.clear()
        notification_event.clear()
        await client.write_gatt_char(write_char_uuid, STATE_QUERY_WRAPPED, response=use_response)
        try:
            await asyncio.wait_for(notification_event.wait(), timeout=2.0)
            await asyncio.sleep(0.1)  # Allow any additional data
            for data in received_data:
                state = parse_state_response(data)
                if state:
                    return state
        except asyncio.TimeoutError:
            pass
        return None

    async def send_probe(packet: bytearray) -> bool:
        """Send a probe packet. Returns True if sent successfully."""
        try:
            await client.write_gatt_char(write_char_uuid, packet, response=use_response)
            await asyncio.sleep(0.3)  # Give device time to process
            return True
        except Exception:
            return False

    # Determine format order based on BLE version
    # BLE v5+ prefers symphony (0x3B) commands, older versions use 0x31
    # From Protocol/r.java analysis:
    # - BLE v5+: Try symphony first, then 8byte_x
    # - BLE v1-4: Try 8byte_x first, then 9byte
    # - Unknown (0): Try all formats
    if ble_version >= 5:
        format_order = ["symphony", "8byte_x", "8byte_v", "9byte"]
    elif ble_version >= 1:
        format_order = ["8byte_x", "8byte_v", "9byte", "symphony"]
    else:
        format_order = ["9byte", "8byte_x", "8byte_v", "symphony"]

    # Enable notifications
    await client.start_notify(notify_char_uuid, notification_handler)
    await asyncio.sleep(0.2)

    working_format = None

    try:
        # Step 1: Get initial state
        print("    Probing: Querying initial state...")
        initial_state = await query_state()
        if not initial_state:
            print("    Probing: Could not get initial state, aborting probe")
            caps.detection_method = "probe_failed"
            return caps

        print(f"    Probing: Initial state - RGB({initial_state.red},{initial_state.green},{initial_state.blue}) "
              f"WW={initial_state.warm_white} CW={initial_state.cool_white}")
        print(f"    Probing: BLE version={ble_version}, format order={format_order}")

        # Step 2: Probe RGB capability - try different formats until one works
        print("    Probing: Testing RGB capability...")
        for format_type in format_order:
            print(f"      Trying format: {format_type}")
            try:
                rgb_packet = build_rgb_probe_packet(brightness=50, format_type=format_type)
            except ValueError:
                continue  # Skip unsupported formats

            if await send_probe(rgb_packet):
                state = await query_state()
                if state:
                    # Check if any RGB channel responded
                    if state.red > 0 or state.green > 0 or state.blue > 0:
                        caps.has_rgb = True
                        caps.rgb_confirmed = True
                        working_format = format_type
                        print(f"    Probing: RGB DETECTED with format={format_type} - R={state.red} G={state.green} B={state.blue}")
                        break
                    else:
                        print(f"      Format {format_type}: RGB channels unchanged, trying next...")
                else:
                    print(f"      Format {format_type}: No state response")
            else:
                print(f"      Format {format_type}: Failed to send")

        if not caps.has_rgb:
            print("    Probing: RGB not detected with any format")

        # Use the working format for WW/CW if we found one, otherwise try all
        ww_cw_formats = [working_format] if working_format else format_order

        # Step 3: Probe WW capability
        print("    Probing: Testing Warm White capability...")
        for format_type in ww_cw_formats:
            if format_type == "symphony":
                continue  # Symphony doesn't have a WW-only mode
            print(f"      Trying format: {format_type}")
            try:
                ww_packet = build_ww_probe_packet(brightness=50, format_type=format_type)
            except ValueError:
                continue

            if await send_probe(ww_packet):
                state = await query_state()
                if state and state.warm_white > 0:
                    caps.has_ww = True
                    caps.ww_confirmed = True
                    print(f"    Probing: WW DETECTED with format={format_type} - value={state.warm_white}")
                    break
        if not caps.has_ww:
            print("    Probing: WW not detected")

        # Step 4: Probe CW capability
        print("    Probing: Testing Cool White capability...")
        for format_type in ww_cw_formats:
            if format_type == "symphony":
                continue  # Symphony doesn't have a CW-only mode
            print(f"      Trying format: {format_type}")
            try:
                cw_packet = build_cw_probe_packet(brightness=50, format_type=format_type)
            except ValueError:
                continue

            if await send_probe(cw_packet):
                state = await query_state()
                if state and state.cool_white > 0:
                    caps.has_cw = True
                    caps.cw_confirmed = True
                    print(f"    Probing: CW DETECTED with format={format_type} - value={state.cool_white}")
                    break
        if not caps.has_cw:
            print("    Probing: CW not detected")

        # Check dimmability from any state we got
        if initial_state.brightness > 0:
            caps.is_dimmable = True

        print(f"\n    Probing complete: RGB={caps.has_rgb}, WW={caps.has_ww}, CW={caps.has_cw}")
        print(f"    Working format: {working_format or 'none found'}")
        print(f"    Suggested color mode: {caps.color_mode_str}")

    finally:
        await client.stop_notify(notify_char_uuid)

    return caps


def detect_capabilities_from_state(state: 'StateResponse', product_id: Optional[int] = None) -> DeviceCapabilities:
    """
    Detect capabilities from a state query response (passive detection).

    This is a heuristic based on which channels have non-zero values.
    If the device is OFF or in effect mode, all channels may be 0 even
    if they're supported. Use detect_capabilities_via_probe() for
    definitive detection.

    From protocol doc section 10.5.8:
    - If R/G/B > 0: has_rgb = True
    - If WW > 0: has_ww = True
    - If CW > 0: has_cw = True
    """
    caps = DeviceCapabilities(
        detection_method="state_query",
        product_id=product_id
    )

    # Check channel values
    if state.red > 0 or state.green > 0 or state.blue > 0:
        caps.has_rgb = True
    if state.warm_white > 0:
        caps.has_ww = True
    if state.cool_white > 0:
        caps.has_cw = True
    if state.brightness > 0:
        caps.is_dimmable = True

    # If product_id is known and not a stub, use it to fill in gaps
    if product_id and product_id in PRODUCT_ID_CAPABILITIES:
        known_caps = PRODUCT_ID_CAPABILITIES[product_id]
        if not known_caps.get('is_stub'):
            # Trust the product ID for capabilities we couldn't detect
            if not caps.has_rgb and known_caps.get('has_rgb'):
                caps.has_rgb = True  # Product ID says it has RGB
            if not caps.has_ww and known_caps.get('has_ww'):
                caps.has_ww = True
            if not caps.has_cw and known_caps.get('has_cw'):
                caps.has_cw = True

    return caps


@dataclass
class ManufacturerData:
    """Parsed manufacturer data from BLE advertisement (Format B - 27 bytes)."""
    raw_bytes: bytes
    company_id: int

    # Byte 0: sta (status/type flags)
    sta: int

    # Byte 1: BLE version - determines protocol version
    ble_version: int

    # Bytes 2-7: MAC address
    mac_address: str

    # Bytes 8-9: Product ID (big-endian)
    product_id: int

    # Byte 10: Firmware version (low byte)
    # For bleVersion >= 6, high byte is in byte 12 bits 2-7
    firmware_ver_low: int

    # Byte 11: LED version (determines feature availability)
    led_version: int

    # Byte 12: Packed byte containing:
    #   - Bits 0-1: check_key_flag (2 bits, values 0-3)
    #   - Bits 2-7: firmware_ver high byte (6 bits, only if ble_version >= 6)
    check_key_flag: int
    firmware_ver_high: int  # Only valid if ble_version >= 6

    # Byte 13: firmware_flag (bits 0-4 only, 5 bits, values 0-31)
    firmware_flag: int

    # Bytes 14-24: State data (if ble_version >= 5)
    state_data: Optional[bytes]

    # Bytes 25-26: RFU (reserved for future use)
    rfu: Optional[bytes]

    @property
    def protocol_version(self) -> int:
        """Determine write protocol version from BLE version."""
        return 1 if self.ble_version >= 8 else 0

    @property
    def max_mtu(self) -> int:
        """Maximum MTU based on protocol version."""
        return 512 if self.protocol_version == 1 else 255

    @property
    def firmware_version(self) -> int:
        """
        Get full firmware version.
        For ble_version >= 6: combines low byte (byte 10) with high bits (byte 12 bits 2-7)
        For ble_version < 6: just the low byte
        """
        if self.ble_version >= 6:
            return self.firmware_ver_low | (self.firmware_ver_high << 8)
        return self.firmware_ver_low

    @property
    def firmware_version_str(self) -> str:
        """Human-readable firmware version string."""
        if self.ble_version >= 6 and self.firmware_ver_high > 0:
            return f"{self.firmware_ver_high}.{self.firmware_ver_low}"
        return f"0.{self.firmware_ver_low}"

    @property
    def capabilities(self) -> dict:
        """Get device capabilities from product ID."""
        if self.product_id in PRODUCT_ID_CAPABILITIES:
            return PRODUCT_ID_CAPABILITIES[self.product_id]
        return {"name": f"Unknown_0x{self.product_id:02X}", "has_rgb": True, "has_ww": False, "has_cw": False}

    @property
    def power_state(self) -> Optional[str]:
        """Parse power state from state_data if available."""
        if self.state_data and len(self.state_data) > 0:
            # Byte 14 (first byte of state_data) contains power state
            power_byte = self.state_data[0]
            if power_byte == 0x23:
                return "ON"
            elif power_byte == 0x24:
                return "OFF"
        return None

    @property
    def color_mode(self) -> Optional[str]:
        """Parse color mode from state_data if available."""
        if self.state_data and len(self.state_data) > 2:
            mode_byte = self.state_data[1]  # Byte 15
            sub_mode = self.state_data[2]   # Byte 16
            if mode_byte == 0x61:
                if sub_mode == 0xF0:
                    return "RGB"
                elif sub_mode == 0x0F:
                    return "White/CCT"
                elif sub_mode == 0x01:
                    return "RGB (alt)"
                elif sub_mode == 0x0B:
                    return "Music"
            elif mode_byte == 0x25:
                return f"Effect #{sub_mode}"
        return None

    @property
    def effect_speed(self) -> Optional[int]:
        """Parse effect speed from state_data if available (byte 17 / state_data[3])."""
        if self.state_data and len(self.state_data) > 3:
            return self.state_data[3]
        return None

    @property
    def state_rgb(self) -> Optional[tuple]:
        """
        Parse RGB values from state_data if available.
        Based on protocol doc, RGB is at bytes 6-8 of state_data (bytes 20-22 overall).
        NOTE: This is the advertisement format, which may differ from state query response.
        """
        if self.state_data and len(self.state_data) > 8:
            r = self.state_data[6]
            g = self.state_data[7]
            b = self.state_data[8]
            return (r, g, b)
        return None

    @property
    def state_brightness(self) -> Optional[int]:
        """
        Parse brightness from state_data if available.
        Based on protocol doc worked example, brightness appears to be at byte 5 (state_data[5]).
        NOTE: Format may vary by device - this needs validation against real hardware.
        """
        if self.state_data and len(self.state_data) > 5:
            return self.state_data[5]
        return None

    @property
    def state_ww(self) -> Optional[int]:
        """Parse warm white value from state_data if available (state_data[9])."""
        if self.state_data and len(self.state_data) > 9:
            return self.state_data[9]
        return None

    @property
    def state_cw(self) -> Optional[int]:
        """Parse cool white value from state_data if available (state_data[10])."""
        if self.state_data and len(self.state_data) > 10:
            return self.state_data[10]
        return None

    @property
    def has_extended_state(self) -> bool:
        """
        Check if device has extended 24-byte state format (BLE version >= 7).
        For v7+ devices, state is stored differently: 24 bytes from byte 3 onwards.
        The scanner only captures bytes 14-24, which is a subset of the full state.
        """
        return self.ble_version >= 7


@dataclass
class StateResponse:
    """
    Parsed state response from device (14 bytes).

    This is the response to a state query command [0x81, 0x8A, 0x8B, 0x40].
    Format documented in protocol doc section 10.8.
    """
    raw_bytes: bytes
    valid: bool

    # Byte 0: Header (should be 0x81)
    header: int

    # Byte 1: Current mode (0-255)
    mode: int

    # Byte 2: Power state (0x23 = ON, other = OFF)
    power_on: bool

    # Byte 3: Mode type (97/98/99 = static solid, other = effect/dynamic)
    mode_type: int

    # Byte 4: Effect speed (0-255)
    speed: int

    # Byte 5: Device-specific value
    value1: int

    # Bytes 6-8: RGB values
    red: int
    green: int
    blue: int

    # Byte 9: Warm white (0-255)
    warm_white: int

    # Byte 10: Brightness (0-255)
    brightness: int

    # Byte 11: Cool white (0-255)
    cool_white: int

    # Byte 12: Reserved
    reserved: int

    # Byte 13: Checksum
    checksum: int
    checksum_valid: bool

    @property
    def is_static_mode(self) -> bool:
        """Check if device is in static (non-effect) mode."""
        return self.mode_type in [97, 98, 99]  # 0x61, 0x62, 0x63

    @property
    def mode_type_str(self) -> str:
        """Human-readable mode type."""
        if self.mode_type == 97:
            return "Static RGB (0x61)"
        elif self.mode_type == 98:
            return "Static WW (0x62)"
        elif self.mode_type == 99:
            return "Static CW (0x63)"
        else:
            return f"Effect/Dynamic (0x{self.mode_type:02X})"

    @property
    def detected_capabilities(self) -> dict:
        """
        Infer device capabilities from current state values.
        NOTE: This is heuristic - channels with 0 values may still be supported.
        """
        return {
            'has_rgb': self.red > 0 or self.green > 0 or self.blue > 0,
            'has_ww': self.warm_white > 0,
            'has_cw': self.cool_white > 0,
            'is_dimmable': self.brightness > 0,
            'rgb_active': self.red > 0 or self.green > 0 or self.blue > 0,
            'ww_active': self.warm_white > 0,
            'cw_active': self.cool_white > 0,
        }


def extract_hex_payload_from_notification(data: bytes) -> Optional[bytes]:
    """
    Extract hex payload from JSON-wrapped notification.

    The device sends notifications as JSON-like text with hex payload:
      {"cmd":"result","data":"8123...hexdata..."}

    This extracts the hex string between quotes and converts to bytes.
    """
    try:
        # Decode as UTF-8 text
        text = data.decode("utf-8", errors="ignore")
        # Find hex payload between quotes
        last_quote = text.rfind('"')
        if last_quote > 0:
            first_quote = text.rfind('"', 0, last_quote)
            if first_quote > 0:
                hex_payload = text[first_quote + 1:last_quote]
                # Verify it's valid hex
                if all(c in "0123456789abcdefABCDEF" for c in hex_payload):
                    return bytes.fromhex(hex_payload)
    except Exception:
        pass
    return None


def parse_state_response(data: bytes) -> Optional[StateResponse]:
    """
    Parse a state response from the device.

    The device may send:
    1. Raw 14-byte binary state response (header 0x81)
    2. JSON-wrapped hex payload containing the state

    Returns StateResponse if valid, None if data is invalid.
    """
    # First, try to extract from JSON wrapper (most common)
    payload = extract_hex_payload_from_notification(data)
    if payload is None:
        # Fall back to raw binary
        payload = data

    if len(payload) < 14:
        return None

    header = payload[0]
    if header != 0x81:
        # Not a state response
        return None

    # Use payload instead of data from here
    data = payload

    # Calculate expected checksum
    expected_checksum = sum(data[:13]) & 0xFF
    actual_checksum = data[13]
    checksum_valid = expected_checksum == actual_checksum

    return StateResponse(
        raw_bytes=data[:14],
        valid=checksum_valid,
        header=header,
        mode=data[1],
        power_on=(data[2] == 0x23),
        mode_type=data[3],
        speed=data[4],
        value1=data[5],
        red=data[6],
        green=data[7],
        blue=data[8],
        warm_white=data[9],
        brightness=data[10],
        cool_white=data[11],
        reserved=data[12],
        checksum=actual_checksum,
        checksum_valid=checksum_valid,
    )


def print_state_response(state: StateResponse):
    """Print formatted state response information."""
    print("\n" + "=" * 70)
    print("STATE RESPONSE FROM DEVICE")
    print("=" * 70)

    print(f"  Raw Data ({len(state.raw_bytes)} bytes):")
    print(f"    {format_bytes_hex(state.raw_bytes)}")

    if not state.checksum_valid:
        print(f"\n  ⚠️  CHECKSUM INVALID: expected 0x{sum(state.raw_bytes[:13]) & 0xFF:02X}, got 0x{state.checksum:02X}")
    else:
        print(f"\n  ✓ Checksum valid (0x{state.checksum:02X})")

    print(f"\n  PARSED FIELDS:")
    print(f"    Header:         0x{state.header:02X} (state response)")
    print(f"    Power:          {'ON' if state.power_on else 'OFF'} (byte 2 = 0x{0x23 if state.power_on else state.raw_bytes[2]:02X})")
    print(f"    Mode:           {state.mode} (0x{state.mode:02X})")
    print(f"    Mode Type:      {state.mode_type_str}")
    print(f"    Speed:          {state.speed}")
    print(f"    Value1:         {state.value1} (device-specific)")

    print("\n  COLOR CHANNELS:")
    print(f"    Red:            {state.red:3d} (0x{state.red:02X})")
    print(f"    Green:          {state.green:3d} (0x{state.green:02X})")
    print(f"    Blue:           {state.blue:3d} (0x{state.blue:02X})")
    print(f"    Warm White:     {state.warm_white:3d} (0x{state.warm_white:02X})")
    print(f"    Cool White:     {state.cool_white:3d} (0x{state.cool_white:02X})")
    print(f"    Brightness:     {state.brightness:3d} (0x{state.brightness:02X})")

    # Show detected capabilities
    caps = state.detected_capabilities
    print("\n  DETECTED CAPABILITIES (from current state):")
    print(f"    RGB active:     {'Yes' if caps['rgb_active'] else 'No (values are 0)'}")
    print(f"    WW active:      {'Yes' if caps['ww_active'] else 'No (value is 0)'}")
    print(f"    CW active:      {'Yes' if caps['cw_active'] else 'No (value is 0)'}")
    print(f"    Dimmable:       {'Yes' if caps['is_dimmable'] else 'No (brightness is 0)'}")

    print("\n  NOTE: Channels showing 0 may still be supported - try setting them!")
    print()


async def connect_and_query_device(
    device: BLEDevice,
    manu_data: Optional[ManufacturerData] = None,
    probe_capabilities: bool = False
):
    """
    Connect to a device, enable notifications, and send state query.

    Args:
        device: BLEDevice to connect to
        manu_data: Optional ManufacturerData for protocol version detection
        probe_capabilities: If True, run active capability probing (will change device state!)
    """
    print(f"\n{'='*70}")
    print(f"CONNECTING TO: {device.name or 'Unknown'} ({device.address})")
    print("="*70)

    # Check for cached capabilities
    cached_caps = get_cached_capabilities(device.address)
    if cached_caps:
        print(f"\n  📋 CACHED CAPABILITIES (from {cached_caps.detected_at}):")
        print(f"     RGB: {cached_caps.has_rgb}, WW: {cached_caps.has_ww}, CW: {cached_caps.has_cw}")
        print(f"     Color mode: {cached_caps.color_mode_str}")

    # Store received notifications
    received_data = []
    notification_event = asyncio.Event()

    def notification_handler(sender, data: bytearray):
        """Handle incoming notifications from device."""
        print(f"\n  📥 NOTIFICATION received ({len(data)} bytes):")
        print(f"     {format_bytes_hex(data)}")
        received_data.append(bytes(data))
        notification_event.set()

    try:
        async with BleakClient(device.address, timeout=20.0) as client:
            print("  ✓ Connected!")

            # List services and characteristics
            print("\n  SERVICES AND CHARACTERISTICS:")
            for service in client.services:
                print(f"    Service: {service.uuid}")
                for char in service.characteristics:
                    props = ", ".join(char.properties)
                    print(f"      Char: {char.uuid} [{props}]")

            # Find our characteristics
            write_char = None
            notify_char = None

            for service in client.services:
                for char in service.characteristics:
                    if char.uuid.lower() == WRITE_CHARACTERISTIC_UUID.lower():
                        write_char = char
                    if char.uuid.lower() == NOTIFY_CHARACTERISTIC_UUID.lower():
                        notify_char = char

            if not write_char:
                print(f"\n  ❌ Write characteristic not found: {WRITE_CHARACTERISTIC_UUID}")
                return
            if not notify_char:
                print(f"\n  ❌ Notify characteristic not found: {NOTIFY_CHARACTERISTIC_UUID}")
                return

            print(f"\n  ✓ Found write characteristic: {write_char.uuid}")
            print(f"  ✓ Found notify characteristic: {notify_char.uuid}")

            # Enable notifications
            print("\n  Enabling notifications...")
            await client.start_notify(notify_char.uuid, notification_handler)
            print("  ✓ Notifications enabled")

            # Give BLE stack time to register notification handler (critical!)
            await asyncio.sleep(0.2)

            # Check write characteristic properties
            write_props = write_char.properties
            print(f"\n  Write char properties: {write_props}")
            use_response = "write" in write_props and "write-without-response" not in write_props

            # Send state query (wrapped version)
            print("\n  Sending STATE QUERY (wrapped):")
            print(f"    {format_bytes_hex(STATE_QUERY_WRAPPED)}")
            print(f"    Using write {'with' if use_response else 'without'} response")
            await client.write_gatt_char(write_char.uuid, STATE_QUERY_WRAPPED, response=use_response)
            print("  ✓ Command sent")

            # Wait for response
            print("\n  Waiting for response (3 seconds)...")
            try:
                await asyncio.wait_for(notification_event.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                print("  ⚠️  No response received within timeout")

            # Give time for any additional notifications
            await asyncio.sleep(0.5)

            # Parse and display any state responses
            for data in received_data:
                state = parse_state_response(data)
                if state:
                    print_state_response(state)
                else:
                    print("\n  Response is not a standard state response (header != 0x81)")
                    print("  This may be a different response type or protocol variant")

            # Optionally send GET_LED_SETTINGS
            print("\n  " + "=" * 60)
            print("  Sending GET_LED_SETTINGS query:")
            print(f"    {format_bytes_hex(GET_LED_SETTINGS_PACKET)}")

            notification_event.clear()
            received_data.clear()

            await client.write_gatt_char(write_char.uuid, GET_LED_SETTINGS_PACKET, response=use_response)
            print("  ✓ Command sent")

            print("\n  Waiting for response (3 seconds)...")
            try:
                await asyncio.wait_for(notification_event.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                print("  ⚠️  No response received within timeout")

            await asyncio.sleep(0.5)

            for data in received_data:
                print(f"\n  LED_SETTINGS response ({len(data)} bytes):")
                print(f"    Raw: {format_bytes_hex(data)}")

                # Try to extract hex payload from JSON wrapper
                payload = extract_hex_payload_from_notification(data)
                if payload:
                    print(f"    Extracted payload: {format_bytes_hex(payload)}")
                    if len(payload) >= 5 and payload[0] == 0x63:
                        print(f"    LED Count:    {payload[2]}")
                        print(f"    Chip Type:    0x{payload[3]:02X}")
                        print(f"    Color Order:  0x{payload[4]:02X}")
                else:
                    print("    (Could not extract JSON-wrapped hex payload)")

            # Capability Detection
            print("\n  " + "=" * 60)
            print("  CAPABILITY DETECTION")

            # Get product_id from manu_data if available
            product_id = manu_data.product_id if manu_data else None
            detected_caps = None

            # Re-query state specifically for capability detection
            notification_event.clear()
            received_data.clear()
            await client.write_gatt_char(write_char.uuid, STATE_QUERY_WRAPPED, response=use_response)
            try:
                await asyncio.wait_for(notification_event.wait(), timeout=2.0)
                await asyncio.sleep(0.2)
            except asyncio.TimeoutError:
                pass

            state_for_caps = None
            for data in received_data:
                state_for_caps = parse_state_response(data)
                if state_for_caps:
                    break

            if state_for_caps:
                detected_caps = detect_capabilities_from_state(state_for_caps, product_id)
                print("\n  Passive detection (from state query):")
                print(f"    RGB: {detected_caps.has_rgb}, WW: {detected_caps.has_ww}, CW: {detected_caps.has_cw}")
                print(f"    Suggested color mode: {detected_caps.color_mode_str}")

                # Check if this is a stub device that needs probing
                is_stub = False
                if product_id and product_id in PRODUCT_ID_CAPABILITIES:
                    is_stub = PRODUCT_ID_CAPABILITIES[product_id].get('is_stub', False)

                if is_stub:
                    print("\n  ⚠️  This is a STUB device - capabilities may vary by hardware variant")
                    print("     Active probing recommended for accurate detection")

            # Active probing if requested
            if probe_capabilities:
                print("\n  " + "-" * 50)
                print("  ACTIVE CAPABILITY PROBING")
                print("  (This will temporarily change the device's color!)")
                print("  " + "-" * 50)

                # Stop current notifications first (detect_capabilities_via_probe will start its own)
                await client.stop_notify(notify_char.uuid)

                # Pass BLE version to help determine which command format to try first
                ble_ver = manu_data.ble_version if manu_data else 0
                probed_caps = await detect_capabilities_via_probe(
                    client, write_char.uuid, notify_char.uuid, use_response, ble_version=ble_ver
                )

                if probed_caps.detection_method != "probe_failed":
                    detected_caps = probed_caps
                    # Cache the probed capabilities
                    cache_capabilities(device.address, detected_caps)
                    print(f"\n  ✓ Capabilities cached for {device.address}")
                else:
                    print("\n  ⚠️  Active probing failed - using passive detection results")

                # Re-enable notifications for cleanup
                await client.start_notify(notify_char.uuid, notification_handler)

            elif detected_caps and not cached_caps:
                # Cache passive detection results if we don't have cached data
                cache_capabilities(device.address, detected_caps)
                print(f"\n  ✓ Passive capabilities cached for {device.address}")

            # Stop notifications before disconnecting
            await client.stop_notify(notify_char.uuid)
            print("\n  ✓ Notifications stopped")

    except Exception as e:
        print(f"\n  ❌ Error: {e}")

    print("\n  Connection closed.")


def matches_name_pattern(name: Optional[str]) -> bool:
    """Check if device name matches known patterns (case-insensitive)."""
    if not name:
        return False
    name_lower = name.lower()
    return any(pattern in name_lower for pattern in NAME_PATTERNS)


def get_manufacturer_id_status(manu_id: int) -> str:
    """
    Check manufacturer ID against known ranges and return a status string.

    Returns:
        "known" - ID is in the documented valid ranges
        "extended" - ID is in the broader 0x5A00-0x5AFF range (likely valid)
        "unknown" - ID is outside all expected ranges
    """
    # Check exact matches first
    if manu_id in EXACT_MATCH_IDS:
        return "known"

    # Check specific documented ranges
    for range_min, range_max in VALID_RANGES:
        if range_min <= manu_id <= range_max:
            return "known"

    # Check broader 0x5A00-0x5AFF range
    if VALID_MANUFACTURER_ID_MIN <= manu_id <= VALID_MANUFACTURER_ID_MAX:
        return "extended"

    return "unknown"


def parse_manufacturer_data(company_id: int, data: bytes) -> Optional[ManufacturerData]:
    """
    Parse manufacturer data from BLE advertisement.

    There are two formats documented:

    Format A (29 bytes) - Raw AD Type 255 payload:
        - Used by Android scanRecord.getBytes() or iOS raw data
        - Company ID embedded in bytes 0-1
        - We DON'T use this format

    Format B (27 bytes) - What bleak/Python provides:
        - Company ID extracted as dictionary key (not in payload)
        - This is what we receive from bleak's manufacturer_data dict
        - All offsets below are for Format B

    Format B byte layout:
    - Byte 0: sta (status/type flags)
    - Byte 1: ble_version (determines protocol: <8=legacy, >=8=modern)
    - Bytes 2-7: MAC address (display order, no reversal needed)
    - Bytes 8-9: product_id (big-endian) - maps to device capabilities
    - Byte 10: firmware_ver_low (low 8 bits of firmware version)
    - Byte 11: led_version (determines feature availability)
    - Byte 12: BIT-PACKED:
        - Bits 0-1: check_key_flag (2 bits, values 0-3)
        - Bits 2-7: firmware_ver_high (6 bits, only if ble_version >= 6)
    - Byte 13: BIT-PACKED:
        - Bits 0-4: firmware_flag (5 bits, values 0-31)
        - Bits 5-7: unused/reserved
    - Bytes 14-24: state_data (power, mode, colors - if ble_version >= 5)
    - Bytes 25-26: rfu (reserved for future use)

    Extended firmware version (ble_version >= 6):
        full_firmware_ver = firmware_ver_low | (firmware_ver_high << 8)

    NOTE: The existing HA integration uses byte 0 as 'fw_major' but the
    protocol doc calls it 'sta'. We need to validate with real devices!
    """
    if len(data) < 14:
        return None  # Minimum required bytes

    sta = data[0]
    ble_version = data[1]

    # MAC address - bytes 2-7
    mac_bytes = data[2:8]
    mac_address = ":".join(f"{b:02X}" for b in mac_bytes)

    # Product ID - bytes 8-9 (big-endian)
    product_id = (data[8] << 8) | data[9]

    # Firmware version low byte - byte 10
    firmware_ver_low = data[10] if len(data) > 10 else 0

    # LED version - byte 11
    led_version = data[11] if len(data) > 11 else 0

    # Byte 12: Bit-packed field
    #   - Bits 0-1: check_key_flag (2 bits)
    #   - Bits 2-7: firmware_ver high byte (6 bits, only valid if ble_version >= 6)
    byte_12 = data[12] if len(data) > 12 else 0
    check_key_flag = byte_12 & 0x03  # Extract bits 0-1
    firmware_ver_high = (byte_12 >> 2) & 0x3F  # Extract bits 2-7 (6 bits)

    # Byte 13: firmware_flag (only bits 0-4 are valid, 5 bits)
    byte_13 = data[13] if len(data) > 13 else 0
    firmware_flag = byte_13 & 0x1F  # Extract bits 0-4

    # State data - bytes 14-24 (if ble_version >= 5 and data available)
    state_data = None
    if len(data) > 14 and ble_version >= 5:
        state_data = data[14:min(25, len(data))]

    # RFU - bytes 25-26
    rfu = None
    if len(data) >= 27:
        rfu = data[25:27]

    return ManufacturerData(
        raw_bytes=data,
        company_id=company_id,
        sta=sta,
        ble_version=ble_version,
        mac_address=mac_address,
        product_id=product_id,
        firmware_ver_low=firmware_ver_low,
        led_version=led_version,
        check_key_flag=check_key_flag,
        firmware_ver_high=firmware_ver_high,
        firmware_flag=firmware_flag,
        state_data=state_data,
        rfu=rfu
    )


def format_bytes_hex(data: bytes) -> str:
    """Format bytes as hex string with spaces."""
    return " ".join(f"{b:02X}" for b in data)


def print_device_info(device: BLEDevice, adv_data: AdvertisementData, manu_data: ManufacturerData, matched_by: str = "name"):
    """Print formatted device information."""
    print("\n" + "=" * 70)
    print(f"DEVICE: {device.name or 'Unknown'}")
    print("=" * 70)

    # Basic BLE info
    print(f"  Address:        {device.address}")
    print(f"  RSSI:           {adv_data.rssi} dBm")
    print(f"  Matched by:     {matched_by}")

    # Manufacturer data header with validation status
    id_status = get_manufacturer_id_status(manu_data.company_id)
    status_msg = {
        "known": "(in documented range)",
        "extended": "(in extended 0x5Axx range - probably valid)",
        "unknown": "(OUTSIDE expected ranges - may still work)"
    }[id_status]

    print(f"\n  Manufacturer ID: 0x{manu_data.company_id:04X} ({manu_data.company_id}) {status_msg}")
    print(f"  Raw Data ({len(manu_data.raw_bytes)} bytes):")
    print(f"    {format_bytes_hex(manu_data.raw_bytes)}")

    # Parsed fields
    print(f"\n  PARSED FIELDS:")
    print(f"    sta (byte 0):           0x{manu_data.sta:02X}")
    print(f"    BLE Version (byte 1):   {manu_data.ble_version}")
    print(f"    Protocol Version:       {manu_data.protocol_version} ({'modern' if manu_data.protocol_version == 1 else 'legacy'})")
    print(f"    Max MTU:                {manu_data.max_mtu} bytes")
    print(f"    MAC Address (2-7):      {manu_data.mac_address}")
    print(f"    Product ID (8-9):       0x{manu_data.product_id:04X} ({manu_data.product_id})")

    # Firmware version with extended format for ble_version >= 6
    if manu_data.ble_version >= 6:
        print(f"    Firmware Ver:           {manu_data.firmware_version_str} (extended: low=0x{manu_data.firmware_ver_low:02X}, high=0x{manu_data.firmware_ver_high:02X})")
    else:
        print(f"    Firmware Ver (byte 10): 0x{manu_data.firmware_ver_low:02X} ({manu_data.firmware_ver_low})")

    print(f"    LED Version (byte 11):  0x{manu_data.led_version:02X} ({manu_data.led_version})")

    # Bit-packed fields from byte 12
    print(f"    Check Key Flag (12[0:1]): {manu_data.check_key_flag} (2 bits)")
    if manu_data.ble_version >= 6:
        print(f"    FW Ver High (12[2:7]):  0x{manu_data.firmware_ver_high:02X} (6 bits)")

    # Bit-packed field from byte 13
    print(f"    Firmware Flag (13[0:4]): {manu_data.firmware_flag} (5 bits)")

    # Capabilities
    caps = manu_data.capabilities
    print(f"\n  CAPABILITIES (from Product ID):")
    print(f"    Device Type:    {caps['name']}")

    # Handle stub devices where capabilities are unknown
    if caps.get('is_stub'):
        print("    *** STUB DEVICE - capabilities must be detected dynamically ***")
        print("    Has RGB:        Unknown (needs state query)")
        print("    Has Warm White: Unknown (needs state query)")
        print("    Has Cool White: Unknown (needs state query)")
    else:
        print(f"    Has RGB:        {'Yes' if caps.get('has_rgb') else 'No'}")
        print(f"    Has Warm White: {'Yes' if caps.get('has_ww') else 'No'}")
        print(f"    Has Cool White: {'Yes' if caps.get('has_cw') else 'No'}")

    if caps.get('has_dim'):
        print("    Dimmer Only:    Yes")
    if caps.get('is_socket'):
        print("    Socket/Plug:    Yes")
    if caps.get('effects'):
        print(f"    Effects:        {caps['effects']}")

    # State data
    if manu_data.state_data:
        print(f"\n  STATE DATA (bytes 14-24):")
        if manu_data.has_extended_state:
            print(f"    NOTE: BLE v{manu_data.ble_version} uses extended 24-byte state (bytes 3-26)")
            print(f"          Scanner shows subset (bytes 14-24). Full state needs connect+query.")
        print(f"    Raw: {format_bytes_hex(manu_data.state_data)}")
        if manu_data.power_state:
            print(f"    Power State:    {manu_data.power_state}")
        if manu_data.color_mode:
            print(f"    Color Mode:     {manu_data.color_mode}")
        if manu_data.effect_speed is not None:
            print(f"    Effect Speed:   {manu_data.effect_speed}")
        if manu_data.state_brightness is not None:
            print(f"    Brightness:     {manu_data.state_brightness} (byte 5 - may vary by device)")
        if manu_data.state_rgb:
            r, g, b = manu_data.state_rgb
            print(f"    RGB:            ({r}, {g}, {b}) (bytes 6-8 - may vary by device)")
        if manu_data.state_ww is not None:
            print(f"    Warm White:     {manu_data.state_ww} (byte 9 - may vary by device)")
        if manu_data.state_cw is not None:
            print(f"    Cool White:     {manu_data.state_cw} (byte 10 - may vary by device)")

    # RFU
    if manu_data.rfu:
        print(f"\n  RFU (bytes 25-26): {format_bytes_hex(manu_data.rfu)}")

    print()


class DeviceTracker:
    """Track discovered devices to avoid duplicate output."""

    def __init__(self):
        self.seen_devices: dict[str, ManufacturerData] = {}

    def is_new_or_changed(self, address: str, manu_data: ManufacturerData) -> bool:
        """Check if this is a new device or if its data has changed."""
        if address not in self.seen_devices:
            self.seen_devices[address] = manu_data
            return True

        # Check if data changed (especially state data)
        old_data = self.seen_devices[address]
        if old_data.raw_bytes != manu_data.raw_bytes:
            self.seen_devices[address] = manu_data
            return True

        return False


async def scan_once(duration: float = 10.0, show_all_matching: bool = False):
    """Perform a single scan for devices."""
    print(f"\nScanning for LEDnetWF devices for {duration} seconds...")
    print("Primary match: device name containing 'lednetwf', 'iotwf', or 'iotbt'")
    print("Secondary validation: manufacturer ID in 0x5A00-0x5AFF range")
    print("-" * 70)

    # Store tuples of (device, adv_data, manu_data, matched_by)
    found_devices = []

    def detection_callback(device: BLEDevice, adv_data: AdvertisementData):
        # Check if device has manufacturer data
        if not adv_data.manufacturer_data:
            return

        # PRIMARY: Match by device name first
        name_matches = matches_name_pattern(device.name)

        if name_matches:
            # Device name matches - grab any manufacturer data it has
            for company_id, data in adv_data.manufacturer_data.items():
                manu_data = parse_manufacturer_data(company_id, data)
                if manu_data:
                    id_status = get_manufacturer_id_status(company_id)
                    if id_status == "known":
                        matched_by = "name + manufacturer ID (confirmed)"
                    elif id_status == "extended":
                        matched_by = "name + manufacturer ID (extended range)"
                    else:
                        matched_by = f"name only (ID 0x{company_id:04X} outside expected ranges)"
                    found_devices.append((device, adv_data, manu_data, matched_by))
                    return

        # SECONDARY: If no name match, check manufacturer ID alone
        # (catches devices that might have been renamed)
        if not name_matches:
            for company_id, data in adv_data.manufacturer_data.items():
                id_status = get_manufacturer_id_status(company_id)
                if id_status in ("known", "extended"):
                    manu_data = parse_manufacturer_data(company_id, data)
                    if manu_data:
                        matched_by = f"manufacturer ID only (name: {device.name or 'None'})"
                        found_devices.append((device, adv_data, manu_data, matched_by))
                        return

    scanner = BleakScanner(detection_callback)
    await scanner.start()
    await asyncio.sleep(duration)
    await scanner.stop()

    # Deduplicate by address, keeping the last (freshest) entry
    devices_by_address = {}
    for device, adv_data, manu_data, matched_by in found_devices:
        devices_by_address[device.address] = (device, adv_data, manu_data, matched_by)

    if not devices_by_address:
        print("\nNo LEDnetWF devices found.")
        print("\nTroubleshooting tips:")
        print("  1. Make sure your device is powered on")
        print("  2. Try moving closer to the device")
        print("  3. Some devices stop advertising after pairing")
        print("  4. Try power cycling the LED controller")
    else:
        print(f"\nFound {len(devices_by_address)} device(s):")
        for device, adv_data, manu_data, matched_by in devices_by_address.values():
            print_device_info(device, adv_data, manu_data, matched_by)

    return list(devices_by_address.values())


async def scan_continuous():
    """Continuously scan and report device changes."""
    print("\nContinuous scanning mode - press Ctrl+C to stop")
    print("Primary match: device name containing 'lednetwf', 'iotwf', or 'iotbt'")
    print("Secondary validation: manufacturer ID in 0x5A00-0x5AFF range")
    print("-" * 70)

    tracker = DeviceTracker()

    def detection_callback(device: BLEDevice, adv_data: AdvertisementData):
        if not adv_data.manufacturer_data:
            return

        name_matches = matches_name_pattern(device.name)

        for company_id, data in adv_data.manufacturer_data.items():
            id_status = get_manufacturer_id_status(company_id)

            # Match by name (primary) or by manufacturer ID (secondary)
            if name_matches:
                manu_data = parse_manufacturer_data(company_id, data)
                if manu_data and tracker.is_new_or_changed(device.address, manu_data):
                    if id_status == "known":
                        matched_by = "name + manufacturer ID (confirmed)"
                    elif id_status == "extended":
                        matched_by = "name + manufacturer ID (extended range)"
                    else:
                        matched_by = f"name only (ID 0x{company_id:04X} outside expected ranges)"
                    print_device_info(device, adv_data, manu_data, matched_by)
                return
            elif id_status in ("known", "extended"):
                manu_data = parse_manufacturer_data(company_id, data)
                if manu_data and tracker.is_new_or_changed(device.address, manu_data):
                    matched_by = f"manufacturer ID only (name: {device.name or 'None'})"
                    print_device_info(device, adv_data, manu_data, matched_by)
                return

    scanner = BleakScanner(detection_callback)

    try:
        await scanner.start()
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        await scanner.stop()


async def interactive_mode(duration: float = 10.0):
    """
    Interactive mode: scan for devices, then offer to connect and query them.
    """
    # First, scan for devices
    found_devices = await scan_once(duration)

    if not found_devices:
        return

    selected_device_idx = None  # Track currently selected device

    # Interactive menu
    while True:
        print("\n" + "=" * 70)
        print("INTERACTIVE MENU")
        print("=" * 70)
        print("\nDiscovered devices:")
        for i, (device, _adv_data, manu_data, _matched_by) in enumerate(found_devices, 1):
            name = device.name or "Unknown"
            caps = manu_data.capabilities
            cached = get_cached_capabilities(device.address)
            cache_indicator = " [cached]" if cached else ""
            marker = " <--" if selected_device_idx == i - 1 else ""
            # Show BLE version from device name
            ble_ver = extract_ble_version_from_name(device.name)
            ver_str = f" [BLE v{ble_ver}]" if ble_ver else ""
            print(f"  {i}. {name} ({device.address}) - {caps['name']}{ver_str}{cache_indicator}{marker}")

        print("\nPower commands:")
        print("  [pow N]   Turn device N ON/OFF (AUTO-SELECT based on BLE version)")
        print("  [on N]    Turn device N ON  (legacy 0x11 - often doesn't work)")
        print("  [off N]   Turn device N OFF (legacy 0x11 - often doesn't work)")
        print("  [on2 N]   Turn device N ON  (modern 0x3B - BLE v5+)")
        print("  [off2 N]  Turn device N OFF (modern 0x3B - BLE v5+)")
        print("  [on3 N]   Turn device N ON  (legacy 0x71 - BLE v1-4)")
        print("  [off3 N]  Turn device N OFF (legacy 0x71 - BLE v1-4)")
        print("\nOther options:")
        print("  [1-N]     Connect to device and query state")
        print("  [p N]     Probe device N for capabilities (will change device color!)")
        print("  [c N]     Clear cached capabilities for device N")
        print("  [r]       Rescan for devices")
        print("  [q]       Quit")

        try:
            choice = input("\nEnter choice: ").strip().lower()
        except EOFError:
            break

        if choice == 'q':
            print("Goodbye!")
            break
        elif choice == 'r':
            print("\nRescanning...")
            found_devices = await scan_once(duration)
            if not found_devices:
                print("No devices found. Try again or quit.")
        elif choice.startswith('pow '):
            # Toggle power with AUTO-SELECT command based on BLE version
            parts = choice.split()
            if len(parts) >= 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, _, _ = found_devices[idx]
                    selected_device_idx = idx
                    # Determine on/off from optional third argument, default to ON
                    if len(parts) >= 3 and parts[2] in ('off', '0', 'false'):
                        await send_power_command_auto(device, turn_on=False)
                    else:
                        await send_power_command_auto(device, turn_on=True)
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: pow N [on|off] (where N is the device number)")
        elif choice.startswith('on ') and not choice.startswith('on2') and not choice.startswith('on3'):
            # Turn device ON (protocol doc version)
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, _, _ = found_devices[idx]
                    selected_device_idx = idx
                    await send_power_command(device, turn_on=True)
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: on N (where N is the device number)")
        elif choice.startswith('off ') and not choice.startswith('off2') and not choice.startswith('off3'):
            # Turn device OFF (legacy 0x11 version)
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, _, _ = found_devices[idx]
                    selected_device_idx = idx
                    await send_power_command(device, turn_on=False)
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: off N (where N is the device number)")
        elif choice.startswith('on2 '):
            # Turn device ON (modern 0x3B - BLE v5+, recommended)
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, _, _ = found_devices[idx]
                    selected_device_idx = idx
                    await send_power_command_ha(device, turn_on=True)
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: on2 N (where N is the device number)")
        elif choice.startswith('off2 '):
            # Turn device OFF (modern 0x3B - BLE v5+, recommended)
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, _, _ = found_devices[idx]
                    selected_device_idx = idx
                    await send_power_command_ha(device, turn_on=False)
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: off2 N (where N is the device number)")
        elif choice.startswith('on3 '):
            # Turn device ON (legacy 0x71 - BLE v1-4)
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, _, _ = found_devices[idx]
                    selected_device_idx = idx
                    await send_power_command_0x71(device, turn_on=True)
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: on3 N (where N is the device number)")
        elif choice.startswith('off3 '):
            # Turn device OFF (legacy 0x71 - BLE v1-4)
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, _, _ = found_devices[idx]
                    selected_device_idx = idx
                    await send_power_command_0x71(device, turn_on=False)
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: off3 N (where N is the device number)")
        elif choice.startswith('p ') or choice.startswith('p'):
            # Probe capabilities
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, manu_data, _ = found_devices[idx]
                    selected_device_idx = idx
                    print("\n  Active probing will temporarily change the device's color!")
                    confirm = input("Continue? [y/N]: ").strip().lower()
                    if confirm == 'y':
                        await connect_and_query_device(device, manu_data, probe_capabilities=True)
                    else:
                        print("Probe cancelled.")
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: p N (where N is the device number)")
        elif choice.startswith('c ') or choice.startswith('c'):
            # Clear cached capabilities
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(found_devices):
                    device, _, _, _ = found_devices[idx]
                    cache = load_capability_cache()
                    key = f"caps_{device.address.replace(':', '_')}"
                    if key in cache:
                        del cache[key]
                        save_capability_cache(cache)
                        print(f"✓ Cleared cached capabilities for {device.address}")
                    else:
                        print(f"No cached capabilities for {device.address}")
                else:
                    print(f"Invalid device number. Enter 1-{len(found_devices)}")
            else:
                print("Usage: c N (where N is the device number)")
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(found_devices):
                device, _, manu_data, _ = found_devices[idx]
                selected_device_idx = idx
                await connect_and_query_device(device, manu_data)
            else:
                print(f"Invalid choice. Enter 1-{len(found_devices)}")
        else:
            print("Invalid choice. Enter 'pow N', 'on/on2/on3 N', 'off/off2/off3 N', 'p N', 'c N', 'r', or 'q'.")


def main():
    parser = argparse.ArgumentParser(
        description="Scan for LEDnetWF BLE devices and decode manufacturer data"
    )
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=10.0,
        help="Scan duration in seconds (default: 10)"
    )
    parser.add_argument(
        "--continuous", "-c",
        action="store_true",
        help="Continuously scan and report changes"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive mode: scan then connect to query devices"
    )
    parser.add_argument(
        "--connect", "-C",
        type=str,
        metavar="ADDRESS",
        help="Connect directly to device by MAC address (e.g., AA:BB:CC:DD:EE:FF)"
    )
    parser.add_argument(
        "--probe", "-p",
        action="store_true",
        help="Run active capability probing when connecting (will change device color!)"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear all cached capabilities"
    )

    args = parser.parse_args()

    try:
        if args.clear_cache:
            # Clear capability cache
            if os.path.exists(CAPABILITY_CACHE_FILE):
                os.remove(CAPABILITY_CACHE_FILE)
                print(f"Cleared capability cache: {CAPABILITY_CACHE_FILE}")
            else:
                print("No capability cache file found.")
            return
        elif args.connect:
            # Direct connection mode - create a minimal BLEDevice
            device = BLEDevice(args.connect, args.connect, {}, 0)
            asyncio.run(connect_and_query_device(device, probe_capabilities=args.probe))
        elif args.interactive:
            asyncio.run(interactive_mode(args.duration))
        elif args.continuous:
            asyncio.run(scan_continuous())
        else:
            asyncio.run(scan_once(args.duration))
    except KeyboardInterrupt:
        print("\nScan stopped by user")


if __name__ == "__main__":
    main()
