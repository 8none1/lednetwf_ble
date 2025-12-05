# Brightness and Speed Value Ranges - Device-Specific Handling

## Overview

LEDnetWF devices report brightness and speed values in **different ranges** depending on the device type and context. This document explains how to determine which range a device uses and how to handle the conversions.

## TL;DR - Quick Reference

| Context | Range | Notes |
|---------|-------|-------|
| **Commands: Effect brightness** | 0-100 | Percentage for addressable LEDs |
| **Commands: RGB/White brightness** | 0-255 | Most direct control commands |
| **Manufacturer data: White mode** | 0-100 | Byte 17 (state offset 3) |
| **Manufacturer data: RGB values** | 0-255 | Bytes 18-20 (R,G,B) |
| **State response: White mode** | 0-100 | Byte 5 (Value1) |
| **State response: RGB values** | 0-255 | Bytes 6-8 (R,G,B) |
| **Effect speed (addressable)** | 0-100 | Direct, no conversion |
| **Effect speed (Symphony)** | 1-31 inverted | Lower=faster |
| **Effect speed (Legacy RGB 0x33, 0x06, 0x04)** | 1-31 inverted | Lower=faster (same as Symphony) |

## The Problem

A SIMPLE device (product_id 0x33, Ctrl_Mini_RGB) reports `brightness_percent=255` and `effect_speed=255` in advertisement data, which causes overflow when the integration assumes a 0-100 range.

**Root cause**: The device is advertising **raw RGB values** (0-255) in bytes that other device types use for percentage values (0-100).

## How Devices Indicate Value Ranges

### Method 1: Context-Based (Primary Method)

The value range depends on **what data field you're reading**, not a device capability flag:

```python
# Manufacturer data parsing (Format B)
if mfr_data[15] == 0x61:  # Static mode
    if mfr_data[16] == 0xF0:  # RGB mode
        # RGB values are 0-255
        r, g, b = mfr_data[18], mfr_data[19], mfr_data[20]
        # Derive brightness from HSV
        brightness_255 = hsv_from_rgb(r, g, b)[2] * 255
        
    elif mfr_data[16] == 0x0F:  # White mode
        # Brightness is 0-100 PERCENT
        brightness_percent = mfr_data[17]
        # Convert to 0-255 for HA
        brightness_255 = int(brightness_percent * 255 / 100)

elif mfr_data[15] == 0x25:  # Effect mode
    # Effect speed is device-specific
    # Some devices: 0-100 direct
    # Some devices: 1-31 inverted
    effect_speed_raw = mfr_data[17]
```

### Method 2: Device Type Classification

Different device types use different formats:

#### Type 1: Addressable LED Devices (FillLight, etc.)

**Product IDs**: 0x1D (29), 0x53, 0x54, 0x56
**Command format**: 0x38 (4-byte, no checksum)

```python
# Manufacturer data for 0x53 devices:
if manu_data[15] == 0x25:  # Effect mode
    effect_id = manu_data[16]
    brightness_percent = manu_data[18]  # 0-100
    effect_speed = manu_data[19]  # 0-100 direct
    
    # Convert brightness for HA (0-255)
    self.brightness = int(brightness_percent * 255 / 100)
```

#### Type 2: Symphony Devices

**Product IDs**: 0xA1-0xA9 (161-169)
**Command format**: 0x38 (5-byte, WITH checksum)

```python
# Symphony devices use inverted speed
if manu_data[15] == 0x25:  # Effect mode
    speed_raw = manu_data[17]  # 1-31 (lower=faster)
    # Convert to percentage (0-100)
    effect_speed_percent = round((0x1f - speed_raw) * 99 / 30 + 1)
```

#### Type 3: Simple/Legacy RGB Devices

**Product IDs**: 0x33, 0x04, 0x06, 0x44, etc.
**Characteristics**: No addressable LED support, uses 0x61 effect command
**Effect command**: 0x61 (NOT 0x38!)
**Speed format**: 1-31 inverted (same as Symphony!)

```python
# These devices may report RGB in "percent" fields
if manu_data[15] == 0x61:  # Static mode
    if manu_data[16] == 0xF0:  # RGB mode
        # These are 0-255 RGB values, not percents!
        r = manu_data[18]  # Could be 255
        g = manu_data[19]
        b = manu_data[20]

# Effect speed for 0x61 command uses INVERTED 1-31 range (like Symphony)
def legacy_rgb_percent_to_speed(percent: int) -> int:
    """Convert percent (0-100) to legacy RGB speed (1-31 inverted)."""
    # Formula from ad/e.java: 1 + (30 * (1.0 - speed/100))
    percent = max(0, min(100, percent))
    return 1 + int(30 * (1.0 - percent / 100.0))

# Examples:
# 100% (fast)  → 1 + (30 * 0.0)  = 1  (fastest)
# 50% (medium) → 1 + (30 * 0.5)  = 16 (medium)
# 0% (slow)    → 1 + (30 * 1.0)  = 31 (slowest)
```

**CRITICAL**: Legacy RGB devices use the **same inverted 1-31 speed format** as Symphony devices!
Do NOT use 0-255 or 0-100 - sending speed values outside 1-31 causes undefined behavior.

## Old Integration Implementation

### Model 0x53 (FillLight) - Correct Handling

File: `custom_components/lednetwf_ble/models/model_0x53.py`

```python
# Lines 189-207: Parsing manufacturer data

if self.manu_data[16] == 0x0f:
    # White mode - brightness is in PERCENT (0-100)
    self.brightness = int(self.manu_data[17] * 255 // 100)
    
elif self.manu_data[15] == 0x25:
    # Effect mode
    self.effect_speed = self.manu_data[19]  # 0-100 direct
    self.brightness = int(self.manu_data[18] * 255 // 100)  # Convert percent

# Lines 344-367: Parsing state response (0x81)

if payload[3] == 0x61:  # Static mode
    if payload[4] == 0xF0:  # RGB mode
        # Derive brightness from RGB using HSV
        self.brightness = int(hsv_color[2])  # Already 0-255
        
    elif payload[4] == 0x0F:  # White mode
        # Brightness is in PERCENT (0-100)
        self.brightness = int(payload[5] * 255 // 100)
        
elif payload[3] == 0x25:  # Effect mode
    # Brightness in PERCENT (0-100)
    self.brightness = int(payload[6] * 255 // 100)
```

### Model 0x5b (Symphony) - Inverted Speed

File: `custom_components/lednetwf_ble/models/model_0x5b.py`

```python
# Lines 101-102: Speed conversion for Symphony devices

# Convert from device speed (0x1f = 1%, 0x01 = 100%) to percentage (0-100)
speed = self.manu_data[17]
self.effect_speed = round((0x1f - speed) * (100 - 1) / (0x1f - 0x01) + 1)

# Lines 185-189: Converting back for commands
# Convert speed from percentage (0-100) to device format (0x1f to 0x01)
# 0x01 = 100% and 0x1f = 1%
speed_byte = round(0x1f - (self.effect_speed - 1) * (0x1f - 0x01) / (100 - 1))
```

## Protocol Documentation Evidence

### Manufacturer Data State Fields

From `03_manufacturer_data_parsing.md`:

| Field | Byte | Range | Notes |
|-------|------|-------|-------|
| Value1 (white brightness) | 17 | 0-100 | Percentage in white mode |
| R, G, B | 18-20 | 0-255 | RGB color values |
| Warm White | 21 | 0-255 | WW value |
| Cool White | 23 | 0-255 | CW value |

### State Response Fields

From `08_state_query_response_parsing.md`:

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 5 | Value1 | 0-100 | White brightness in white mode |
| 6-8 | R, G, B | 0-255 | RGB values |
| 9 | Warm White | 0-255 | WW value |
| 11 | Cool White | 0-255 | CW value |

**Key insight**: Byte 10 is LED version, **NOT brightness**!

### Effect Command Brightness

From `BUG_REPORT_EFFECT_COMMANDS.md`:

```python
# For addressable LED effects (0x38 command)
def build_effect_command_0x38(effect_id: int, speed: int, brightness: int):
    """
    Args:
        effect_id: 1-255
        speed: 0-100 (FillLight) or 1-31 (Symphony)
        brightness: 0-100 PERCENT - NOT 0-255!
    """
    return bytes([0x38, effect_id, speed, brightness])
```

## Implementation Recommendations

### For New Integration (lednetwf_ble_2)

```python
class DeviceState:
    def __init__(self):
        # Always store brightness internally as 0-255 for HA
        self._brightness_255 = 255
        self._effect_speed_percent = 50  # 0-100 for UI
    
    def parse_manufacturer_data(self, mfr_data: bytes):
        """Parse manufacturer data with context-aware range handling."""
        
        mode = mfr_data[15]
        sub_mode = mfr_data[16]
        
        if mode == 0x61:  # Static mode
            if sub_mode == 0xF0:  # RGB mode
                # RGB values are 0-255
                r, g, b = mfr_data[18], mfr_data[19], mfr_data[20]
                # Derive brightness from RGB
                _, _, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                self._brightness_255 = int(v * 255)
                
            elif sub_mode == 0x0F:  # White mode
                # Value1 is brightness in PERCENT (0-100)
                brightness_percent = mfr_data[17]
                self._brightness_255 = int(brightness_percent * 255 / 100)
                
        elif mode == 0x25:  # Effect mode
            # Check device type for speed format
            if self._is_symphony_device():
                # Symphony: 1-31 inverted
                speed_raw = mfr_data[17]
                self._effect_speed_percent = self._symphony_speed_to_percent(speed_raw)
            else:
                # FillLight/etc: 0-100 direct
                self._effect_speed_percent = mfr_data[17]
            
            # Brightness is in PERCENT (0-100)
            brightness_percent = mfr_data[18]
            self._brightness_255 = int(brightness_percent * 255 / 100)
    
    def parse_state_response(self, response: bytes):
        """Parse 0x81 state response."""
        
        mode_type = response[3]
        sub_mode = response[4]
        
        if mode_type == 0x61:  # Static mode
            if sub_mode in [0xF0, 0x01, 0x0B]:  # RGB mode
                # Derive brightness from RGB
                r, g, b = response[6], response[7], response[8]
                _, _, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
                self._brightness_255 = int(v * 255)
                
            elif sub_mode == 0x0F:  # White mode
                # Value1 (byte 5) is brightness in PERCENT
                brightness_percent = response[5]
                self._brightness_255 = int(brightness_percent * 255 / 100)
                
        elif mode_type == 0x25:  # Effect mode
            # Brightness is in PERCENT (byte 6)
            brightness_percent = response[6]
            self._brightness_255 = int(brightness_percent * 255 / 100)
    
    def _is_symphony_device(self) -> bool:
        """Check if device uses Symphony speed format."""
        # Symphony devices: product_id 0xA1-0xA9 (161-169)
        return 0xA1 <= self.product_id <= 0xA9
    
    def _symphony_speed_to_percent(self, speed_raw: int) -> int:
        """Convert Symphony speed (1-31 inverted) to percent (0-100)."""
        # 0x01 = fastest (100%), 0x1F = slowest (1%)
        if speed_raw < 1:
            speed_raw = 1
        elif speed_raw > 0x1F:
            speed_raw = 0x1F
        return round((0x1F - speed_raw) * 99 / 30 + 1)
    
    def _percent_to_symphony_speed(self, percent: int) -> int:
        """Convert percent (0-100) to Symphony speed (1-31 inverted)."""
        percent = max(1, min(100, percent))
        return round(0x1F - (percent - 1) * 30 / 99)
    
    @property
    def brightness_percent(self) -> int:
        """Get brightness for commands that need percent (0-100)."""
        return int(self._brightness_255 * 100 / 255)
    
    @property
    def brightness_255(self) -> int:
        """Get brightness for Home Assistant (0-255)."""
        return self._brightness_255
```

### Detecting Device Type

```python
def detect_speed_format(product_id: int, sta_byte: int) -> str:
    """
    Determine which speed format the device uses.

    Returns:
        "direct": 0-100 direct (FillLight, etc.)
        "inverted": 1-31 inverted (Symphony, Legacy RGB)
    """
    # Symphony devices: product_id 0xA1-0xA9
    if 0xA1 <= product_id <= 0xA9:
        return "inverted"

    # Legacy RGB devices: product_id 0x33, 0x06, 0x04, 0x44
    # These use 0x61 command with 1-31 inverted speed!
    legacy_rgb_product_ids = [0x33, 0x06, 0x04, 0x44]
    if product_id in legacy_rgb_product_ids:
        return "inverted"

    # Fallback based on sta byte if product_id unreliable
    symphony_sta_bytes = [0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xA7, 0xA9, 0x08]
    if sta_byte in symphony_sta_bytes:
        return "inverted"

    # Default to direct for most devices (FillLight, etc.)
    return "direct"
```

## Common Pitfalls

### Pitfall 1: Treating RGB as Brightness

```python
# WRONG - treating RGB value as brightness percent
brightness = mfr_data[18]  # Could be 255, not a percent!

# CORRECT - recognize RGB context
if sub_mode == 0xF0:  # RGB mode
    r, g, b = mfr_data[18], mfr_data[19], mfr_data[20]
    _, _, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    brightness = int(v * 255)
```

### Pitfall 2: Wrong Byte for Brightness

```python
# WRONG - byte 22 (offset 8 in state data) is LED version!
brightness = mfr_data[22]  # This is NOT brightness

# CORRECT - brightness depends on mode
if mode == 0x61 and sub_mode == 0x0F:  # White mode
    brightness_percent = mfr_data[17]  # This is brightness
    brightness = int(brightness_percent * 255 / 100)
```

### Pitfall 3: Not Converting Percent Values

```python
# WRONG - passing percent (0-100) directly to HA (expects 0-255)
self.brightness = mfr_data[18]  # If this is percent, it's too low!

# CORRECT - convert percent to 0-255
brightness_percent = mfr_data[18]
self.brightness = int(brightness_percent * 255 / 100)
```

### Pitfall 4: Assuming Universal Speed Format

```python
# WRONG - assuming all devices use same speed format
effect_speed = mfr_data[17]  # Could be inverted on Symphony!

# CORRECT - check device type
if is_symphony_device:
    effect_speed = symphony_speed_to_percent(mfr_data[17])
else:
    effect_speed = mfr_data[17]  # Direct 0-100
```

### Pitfall 5: Using Wrong Speed Range for Legacy RGB (0x61 cmd)

```python
# WRONG - sending 0-100 or 0-255 speed to legacy RGB devices
# This causes flashing, erratic behavior, or device turning off!
effect_packet = [0x61, effect_id, 186, 0x0F]  # speed=186 is INVALID!

# CORRECT - legacy RGB uses 1-31 inverted (same as Symphony)
def build_legacy_effect(effect_id: int, ui_speed_percent: int) -> bytes:
    # Convert UI speed (0-100) to protocol (1-31 inverted)
    protocol_speed = 1 + int(30 * (1.0 - ui_speed_percent / 100.0))
    protocol_speed = max(1, min(31, protocol_speed))  # Clamp to valid range!

    cmd = bytearray([0x61, effect_id, protocol_speed, 0x0F])
    cmd.append(sum(cmd) & 0xFF)  # checksum
    return bytes(cmd)
```

## Summary

**Value ranges are context-dependent, not device-capability-based:**

1. **RGB values**: Always 0-255 (bytes 18-20 in mfr_data, bytes 6-8 in state)
2. **White brightness**: Always 0-100 percent (byte 17 in mfr_data, byte 5 in state) → Convert to 0-255 for HA
3. **Effect brightness**: Always 0-100 percent → Convert to 0-255 for HA
4. **Effect speed**: Device-specific:
   - FillLight/addressable (0x38 cmd): 0-100 direct
   - Symphony (0x38 cmd): 1-31 inverted
   - Legacy RGB (0x61 cmd): 1-31 inverted
5. **Byte 22/Byte 10**: LED version, NOT brightness!

**The integration must:**
- Parse based on **mode and sub-mode context**, not device capability flags
- Always store brightness as 0-255 internally for Home Assistant
- Convert percent values (0-100) to 0-255 when reading from device
- Convert 0-255 to percent (0-100) when sending commands to device
- Handle device-specific speed formats (Symphony inversion)
