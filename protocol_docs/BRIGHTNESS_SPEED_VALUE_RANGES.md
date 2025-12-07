# Effect Brightness & Speed: Firmware Version Differences

**Last Updated**: 7 December 2025
**Status**: New discovery - updates understanding of 06_effect_commands.md

---

## Overview

The ability to set brightness during effects is **firmware version dependent**. Different firmware versions use different command formats with different capabilities.

**Key Discovery**: The `0x61` command (Legacy RGB effects) has NO brightness parameter, but newer firmware uses `0x38` which DOES include brightness. The minimum firmware version varies by product - some support it from v1+, others from v8+.

---

## Command Formats by Firmware Version

### scene_data (Firmware 0-8) - NO Brightness

**Command**: `0x61`
**Function code**: `scene_data`
**Parameters**: `[model, speed]`

```
Format: 61 {model} {speed} {persist} [checksum]

Byte 0: 0x61 - Command opcode
Byte 1: model (37-56) - Effect ID
Byte 2: speed (1-31, INVERTED: 1=fast, 31=slow)
Byte 3: persist (0xF0=save, 0x0F=temp)
Byte 4: checksum
```

**No brightness control** - effect brightness is inherent to the effect or must be controlled separately.

---

### scene_data_v2 (Varies by Product) - HAS Brightness

**Command**: `0x38`
**Function code**: `scene_data_v2`
**Parameters**: `[model, speed, bright]`
**Source**: `wifi_dp_cmd.json`

**Minimum firmware varies by product:**

- Products 0x08, 0x3C: minVer=1 (very early support)
- Products 0x06, 0x07, 0x48: minVer=2
- Products 0x33, 0x35, etc.: minVer=8-9

```
Format: 38 {model} {speed} {bright} [checksum]

Byte 0: 0x38 - Command opcode
Byte 1: model (37-56) - Effect ID
Byte 2: speed (1-31)
Byte 3: bright (1-100) - Brightness percentage
Byte 4: checksum
```

**Python implementation:**
```python
def build_effect_v2(effect_id: int, speed: int, brightness: int) -> bytes:
    """
    Build effect command for firmware v9+ devices.

    Args:
        effect_id: 37-56 (simple effects)
        speed: 1-31 (1=fast, 31=slow)
        brightness: 1-100 (percent, never 0!)

    Returns:
        5-byte command with checksum
    """
    effect_id = max(37, min(56, effect_id))
    speed = max(1, min(31, speed))
    brightness = max(1, min(100, brightness))

    cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

**Example - Effect 41, medium speed, 75% brightness:**
```
model=41 (0x29), speed=16, bright=75 (0x4B)
Command: 38 29 10 4B [checksum]
         38 + 29 + 10 + 4B = BC
Final:   38 29 10 4B BC
```

---

### scene_data_v3 (Firmware 11+) - HAS Brightness + Preview

**Command**: `0xE0 0x02`
**Function code**: `scene_data_v3`
**Parameters**: `[preview, model, speed, bright]`
**Source**: `wifi_dp_cmd.json`

```
Format: e0 02 {preview} {model} {speed} {bright}

Byte 0: 0xE0 - Command opcode
Byte 1: 0x02 - Sub-command
Byte 2: preview (0-255) - Preview mode flag
Byte 3: model (37-56) - Effect ID
Byte 4: speed (0-100, DIRECT: 0=slow, 100=fast)
Byte 5: bright (0-100) - Brightness percentage
NO CHECKSUM
```

**Note**: Speed encoding changed from INVERTED (1-31) to DIRECT (0-100) in v3!

**Python implementation:**
```python
def build_effect_v3(effect_id: int, speed: int, brightness: int,
                    preview: int = 0) -> bytes:
    """
    Build effect command for firmware v11+ devices.

    Args:
        effect_id: 37-56 (simple effects)
        speed: 0-100 (DIRECT: 0=slow, 100=fast)
        brightness: 0-100 (percent)
        preview: 0-255 (preview mode)

    Returns:
        6-byte command, NO checksum
    """
    preview = max(0, min(255, preview))
    effect_id = max(37, min(56, effect_id))
    speed = max(0, min(100, speed))
    brightness = max(0, min(100, brightness))

    return bytes([
        0xE0,
        0x02,
        preview & 0xFF,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF
    ])
```

**Example - Effect 41, 50% speed, 75% brightness, no preview:**
```
preview=0, model=41 (0x29), speed=50 (0x32), bright=75 (0x4B)
Command: E0 02 00 29 32 4B
```

---

## Separate Brightness Control (bright_value_v2)

Firmware v9+ devices also have a separate brightness command that can adjust brightness independently of the current mode.

**Command**: `0x3B`
**Function code**: `bright_value_v2`
**Source**: `wifi_dp_cmd.json`, `ble_dp_cmd.json`

```
Format: 3b 01 00 00 {value} 00 {value} {delay_h} {delay_m} {delay_l} {grad_h} {grad_l} [checksum]

Byte 0:  0x3B - Command opcode
Byte 1:  0x01 - Sub-command
Byte 2:  0x00 - Reserved
Byte 3:  0x00 - Reserved
Byte 4:  value (0-100) - Brightness percentage
Byte 5:  0x00 - Reserved
Byte 6:  value (0-100) - Brightness (repeated)
Byte 7:  delay high byte
Byte 8:  delay mid byte
Byte 9:  delay low byte
Byte 10: gradient high byte
Byte 11: gradient low byte
Byte 12: checksum
```

**Parameter ranges:**
- `value`: 0-100 (brightness percentage)
- `delay`: 0-65535 (transition delay, 3 bytes)
- `gradient`: 0-16777215 (fade gradient, 2 bytes shown but can be 3)

**Python implementation:**
```python
def build_brightness_v2(brightness: int, delay: int = 0,
                        gradient: int = 0) -> bytes:
    """
    Build standalone brightness command for firmware v9+ devices.

    Args:
        brightness: 0-100 (percent)
        delay: 0-65535 (transition delay ms)
        gradient: 0-65535 (fade gradient)

    Returns:
        13-byte command with checksum
    """
    brightness = max(0, min(100, brightness))
    delay = max(0, min(65535, delay))
    gradient = max(0, min(65535, gradient))

    cmd = bytearray([
        0x3B,
        0x01,
        0x00,
        0x00,
        brightness & 0xFF,
        0x00,
        brightness & 0xFF,
        (delay >> 16) & 0xFF,
        (delay >> 8) & 0xFF,
        delay & 0xFF,
        (gradient >> 8) & 0xFF,
        gradient & 0xFF
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

---

## Speed Encoding Summary

| Firmware | Command | Speed Range | Encoding |
|----------|---------|-------------|----------|
| v0-8 | `scene_data` (0x61) | 1-31 | **INVERTED**: 1=fast, 31=slow |
| v9-10 | `scene_data_v2` (0x38) | 1-31 | 1-31 (needs verification) |
| v11+ | `scene_data_v3` (0xE0 02) | 0-100 | **DIRECT**: 0=slow, 100=fast |

**Converting UI speed (0-100, 0=slow) to protocol:**

```python
def ui_to_protocol_speed(ui_speed: int, firmware_version: int) -> int:
    """Convert UI speed to protocol speed based on firmware."""
    if firmware_version >= 11:
        # v11+: Direct 0-100
        return max(0, min(100, ui_speed))
    else:
        # v0-10: Inverted 1-31
        normalized = max(0, min(100, ui_speed)) / 100.0
        return 1 + int(30 * (1.0 - normalized))
```

---

## Brightness Range Summary

| Firmware | Command | Brightness Range | Notes |
|----------|---------|------------------|-------|
| v0-8 | `scene_data` (0x61) | N/A | No brightness in command |
| v9-10 | `scene_data_v2` (0x38) | 1-100 | Never use 0! |
| v11+ | `scene_data_v3` (0xE0 02) | 0-100 | 0 may power off |

---

## Detecting Firmware Version

The firmware version is available in the BLE advertisement data:

```python
def get_firmware_version(advertisement_data) -> int:
    """Extract firmware version from BLE advertisement."""
    mfr_data = advertisement_data.manufacturer_data

    for company_id, payload in mfr_data.items():
        if 23040 <= company_id <= 23295 and len(payload) >= 11:
            return payload[10]  # Byte 10 is firmware version

    return 0  # Default to legacy
```

---

## Implementation Strategy

For a Home Assistant integration supporting all firmware versions:

```python
def build_effect_command(effect_id: int, speed_pct: int, brightness: int,
                        firmware_version: int) -> bytes:
    """
    Build effect command appropriate for device firmware.

    Args:
        effect_id: 37-56 (simple effects)
        speed_pct: 0-100 (UI speed, 0=slow, 100=fast)
        brightness: 1-100 (percent)
        firmware_version: Device firmware version

    Returns:
        Command bytes appropriate for firmware
    """
    if firmware_version >= 11:
        # v11+: Use scene_data_v3 (0xE0 02)
        return build_effect_v3(effect_id, speed_pct, brightness)
    elif firmware_version >= 9:
        # v9-10: Use scene_data_v2 (0x38)
        protocol_speed = 1 + int(30 * (1.0 - speed_pct/100.0))
        return build_effect_v2(effect_id, protocol_speed, brightness)
    else:
        # v0-8: Use scene_data (0x61) - no brightness!
        protocol_speed = 1 + int(30 * (1.0 - speed_pct/100.0))
        return build_effect_legacy(effect_id, protocol_speed)
```

---

## Products Using These Commands

Based on `ble_devices.json`, scene command support varies significantly by product:

### Products with EARLY scene_data_v2 Support (minVer 0-2)

These support brightness in effects from very early firmware:

| Product | Hex | v2 minVer | v3 minVer | Description |
|---------|-----|-----------|-----------|-------------|
| 6 | 0x06 | 2 | 4 | Ctrl_Mini_RGBW |
| 7 | 0x07 | 2 | 3 | Ctrl_Mini_RGBCW |
| **8** | **0x08** | **1** | N/A | **Ctrl_Mini_RGB_Mic** |
| 16 | 0x10 | 0 | N/A | Unknown |
| 26 | 0x1A | 0 | N/A | Unknown |
| **60** | **0x3C** | **1** | N/A | **Ctrl_Mini_RGB_Mic** |
| 72 | 0x48 | 2 | 4 | Ctrl_Mini_RGBW_Mic |

### Products with LATER scene_data_v2 Support (minVer 8-9)

These require newer firmware for brightness support:

| Product | Hex | v2 minVer | v3 minVer | Description |
|---------|-----|-----------|-----------|-------------|
| 14 | 0x0E | 8 | 10 | FloorLamp_RGBCW |
| 30 | 0x1E | 8 | 10 | CeilingLight_RGBCW |
| 41 | 0x29 | 8 | 10 | Unknown |
| 51 | 0x33 | 9 | 11 | Ctrl_Mini_RGB |
| 53 | 0x35 | 8 | 10 | Bulb_RGBCW |
| 62 | 0x3E | 8 | 10 | Unknown |
| 77 | 0x4D | 8 | 10 | Unknown |
| 85 | 0x55 | 8 | 10 | Unknown |

### Products with ONLY Legacy scene_data (No Brightness)

These do NOT support brightness in effects:

| Product | Hex | Description |
|---------|-----|-------------|
| 68 | 0x44 | Bulb_RGBW |
| 84 | 0x54 | Downlight_RGBW |

**Note**: The old integration code uses 0x38 for product 0x54, suggesting the device may accept the command even though not officially documented.

---

## Related Documentation

- [06_effect_commands.md](06_effect_commands.md) - Main effect command reference (needs update for v2/v3)
- [03_device_identification.md](03_device_identification.md) - Product ID reference

---

**End of Document**
