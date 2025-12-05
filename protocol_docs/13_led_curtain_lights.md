# LED Curtain Light Protocol

This document covers LED curtain light devices (Product IDs 172, 173) found in the surplife app.
These are matrix/panel LED devices that display effects in a 2D grid pattern.

**Source**: Surplife Android app (`com.magichome.surplife.apk`) - decompiled Flutter assets.

## Device Identification

### Product IDs

| Product ID | Type | Category | Protocol |
|------------|------|----------|----------|
| 172 | symphony_curtain | hc3 | curtainLightE2 |
| 173 | symphony_curtain | hc3 | curtainLightE2 |

### Supported Matrix Sizes

The devices come in various resolutions:

| Dimensions | Total LEDs |
|------------|------------|
| 13 x 10 | 130 |
| 15 x 17 | 255 |
| 15 x 19 | 285 |
| 15 x 24 | 360 |
| 18 x 12 | 216 |
| 20 x 13 | 260 |
| 20 x 20 | 400 |
| 20 x 28 | 560 |
| 24 x 22 | 528 |
| 30 x 15 | 450 |
| 30 x 30 | 900 |

### BLE Advertisement Detection

These devices advertise with the standard LEDnetWF format. Product ID is in the manufacturer data.

```python
def is_curtain_light(product_id: int) -> bool:
    """Check if device is an LED curtain light."""
    return product_id in [172, 173]
```

---

## Protocol Overview

LED curtain lights use the **same command protocol as Symphony devices** (hc3 category).
The basic control commands are identical - the only difference is in advanced features
(text display, image gallery) which are curtain-specific and not covered here.

### Protocol Stack

```
┌─────────────────────────────────────┐
│  Application Commands               │
│  (0x3B, 0x38, 0x71, etc.)          │
├─────────────────────────────────────┤
│  Upper Transport Layer              │
│  (seq, cmd_id, payload)             │
├─────────────────────────────────────┤
│  Lower Transport Layer (v0)         │
│  (header, frag control, length)     │
├─────────────────────────────────────┤
│  BLE GATT Write Characteristic      │
└─────────────────────────────────────┘
```

All commands must be wrapped in the transport layer. See `06_transport_layer_protocol.md`.

---

## On/Off Control

### Modern Command (0x3B) - Recommended

Same format as Symphony devices. This is the preferred method for BLE v5+ devices.

**PowerType values:**
- `0x23` (35) = Power ON
- `0x24` (36) = Power OFF
- `0x25` (37) = Toggle

**Format (13 bytes before transport wrapper):**

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x3B (59) |
| 1 | PowerType | 0x23=ON, 0x24=OFF |
| 2-3 | Zeros | 0x00, 0x00 |
| 4-6 | Zeros | 0x00, 0x00, 0x00 |
| 7-9 | Duration | 0x00, 0x00, 0x32 (50ms) |
| 10-11 | Zeros | 0x00, 0x00 |
| 12 | Checksum | Sum of bytes 0-11 |

**Python Implementation:**

```python
def build_power_command(turn_on: bool) -> bytes:
    """
    Build power on/off command for curtain lights.

    Args:
        turn_on: True for ON, False for OFF
    """
    power_type = 0x23 if turn_on else 0x24

    cmd = bytearray([
        0x3B,           # Command
        power_type,     # 0x23=ON, 0x24=OFF
        0x00, 0x00,     # HSV zeros
        0x00, 0x00, 0x00,  # Params
        0x00, 0x00, 0x32,  # Duration (50ms)
        0x00, 0x00,     # Zeros
    ])
    cmd.append(sum(cmd) & 0xFF)  # Checksum
    return bytes(cmd)

# Examples:
power_on = build_power_command(True)   # Turn on
power_off = build_power_command(False)  # Turn off
```

### Legacy Command (0x71) - Fallback

For older BLE protocol versions (v1-4):

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x71 (113) |
| 1 | State | 0x23=ON, 0x24=OFF |
| 2 | Persist | 0xF0=save, 0x0F=temporary |
| 3 | Checksum | Sum of bytes 0-2 |

```python
def build_power_legacy(turn_on: bool, persist: bool = False) -> bytes:
    """Legacy power command for older devices."""
    state = 0x23 if turn_on else 0x24
    persist_byte = 0xF0 if persist else 0x0F

    cmd = bytearray([0x71, state, persist_byte])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

---

## RGB Color Control

### Solid Color via 0x3B (HSV) - Recommended

For Symphony-class devices (including curtain lights), use the 0x3B command with mode 0xA1.

**Format (13 bytes before transport wrapper):**

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x3B (59) |
| 1 | Mode | 0xA1 (solid color) |
| 2 | Hue (high) | H >> 8 |
| 3 | Hue (low) | H & 0xFF |
| 4 | Saturation | 0-100 |
| 5 | Value/Brightness | 0-100 |
| 6 | Reserved | 0x00 |
| 7-9 | Duration | 0x00, 0x00, 0x32 |
| 10-11 | Reserved | 0x00, 0x00 |
| 12 | Checksum | Sum of bytes 0-11 |

**Python Implementation:**

```python
import colorsys

def rgb_to_hsv_protocol(r: int, g: int, b: int, brightness: int = 100) -> tuple:
    """
    Convert RGB to HSV for protocol.

    Args:
        r, g, b: RGB values 0-255
        brightness: Brightness percentage 0-100

    Returns:
        (hue, saturation, value) for protocol
        hue: 0-360 (will be split into high/low bytes)
        saturation: 0-100
        value: 0-100 (brightness)
    """
    h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
    hue = int(h * 360)
    saturation = int(s * 100)
    # Use brightness parameter, not calculated V
    return (hue, saturation, brightness)

def build_color_command_3b(r: int, g: int, b: int, brightness: int = 100) -> bytes:
    """
    Build solid color command for curtain lights.

    Args:
        r, g, b: RGB values 0-255
        brightness: 0-100 percent
    """
    hue, sat, val = rgb_to_hsv_protocol(r, g, b, brightness)

    cmd = bytearray([
        0x3B,
        0xA1,           # Mode: solid color
        (hue >> 8) & 0xFF,
        hue & 0xFF,
        sat & 0xFF,
        val & 0xFF,
        0x00,
        0x00, 0x00, 0x32,  # Duration
        0x00, 0x00,
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)

# Example: Set to red at 80% brightness
red_cmd = build_color_command_3b(255, 0, 0, brightness=80)
```

### Direct RGB via 0x31 - Alternative

Some devices respond better to direct RGB commands:

**9-byte format:**

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x31 |
| 1 | Red | 0-255 |
| 2 | Green | 0-255 |
| 3 | Blue | 0-255 |
| 4 | Warm White | 0-255 (usually 0) |
| 5 | Cool White | 0-255 (usually 0) |
| 6 | Mode | 0xF0 (RGB mode) |
| 7 | Persist | 0xF0=save, 0x0F=temp |
| 8 | Checksum | Sum of bytes 0-7 |

```python
def build_color_command_31(r: int, g: int, b: int, persist: bool = False) -> bytes:
    """Build direct RGB command."""
    cmd = bytearray([
        0x31,
        r & 0xFF,
        g & 0xFF,
        b & 0xFF,
        0x00,  # WW
        0x00,  # CW
        0xF0,  # RGB mode
        0xF0 if persist else 0x0F,
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

---

## Brightness Control

### Standalone Brightness (0x3B)

Set brightness without changing color:

```python
def build_brightness_command(brightness: int) -> bytes:
    """
    Set brightness level.

    Args:
        brightness: 0-100 percent
    """
    brightness = max(1, min(100, brightness))  # Clamp, avoid 0

    cmd = bytearray([
        0x3B,
        0xA1,           # Mode
        0x00, 0x00,     # Keep current hue
        0x00,           # Keep current saturation
        brightness & 0xFF,
        0x00,
        0x00, 0x00, 0x32,
        0x00, 0x00,
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

**Note:** Some devices require setting the full color (H, S, V) to change brightness.
If standalone brightness doesn't work, use `build_color_command_3b()` with the
current color and new brightness.

---

## Effect Control

Curtain lights support Symphony effects. They use the same effect IDs as Symphony
strip lights, but the effects are rendered on a 2D matrix instead of a linear strip.

### Effect Command (0x38) - Symphony Format

**Format (5 bytes):**

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x38 | Fixed |
| 1 | Effect ID | 1-300 | Scene (1-44) or Build (1-300) |
| 2 | Speed | 1-31 | **INVERTED**: 1=fastest, 31=slowest |
| 3 | Brightness | 1-100 | Percent, avoid 0 |
| 4 | Checksum | calculated | Sum of bytes 0-3 |

### Speed Encoding (CRITICAL!)

**Speed is INVERTED**: Lower values = faster animation!

```python
def ui_speed_to_protocol(ui_speed: int) -> int:
    """
    Convert UI speed (0-100, 100=fast) to protocol (1-31, 1=fast).

    Uses the same formula as Symphony devices.
    """
    ui_speed = max(0, min(100, ui_speed))
    # Formula: 1 + (30 * (1.0 - speed/100))
    protocol_speed = 1 + int(30 * (1.0 - ui_speed / 100.0))
    return max(1, min(31, protocol_speed))

# Examples:
# UI 100% (fastest) → 1
# UI 50% (medium)   → 16
# UI 0% (slowest)   → 31
```

### Python Implementation

```python
def build_effect_command(effect_id: int, ui_speed: int = 50, brightness: int = 100) -> bytes:
    """
    Build effect command for curtain lights.

    Args:
        effect_id: 1-44 (scene) or 1-300 (build)
        ui_speed: 0-100 (0=slow, 100=fast) - converted to protocol internally
        brightness: 1-100 percent

    Returns:
        5-byte command with checksum
    """
    # Validate
    effect_id = max(1, min(300, effect_id))
    brightness = max(1, min(100, brightness))

    # Convert speed to protocol format (inverted 1-31)
    protocol_speed = ui_speed_to_protocol(ui_speed)

    cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        protocol_speed & 0xFF,
        brightness & 0xFF,
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)

# Examples:
rainbow = build_effect_command(effect_id=2, ui_speed=75, brightness=100)
strobe = build_effect_command(effect_id=4, ui_speed=90, brightness=80)
```

### Available Effects

Curtain lights support all Symphony effects. See `12_symphony_effect_names.md` for the full list.

**Scene Effects (IDs 1-44):**
- Basic animations with color customization options
- Examples: gradual change, strobe, running patterns

**Build Effects (IDs 1-300):**
- Complex pre-defined animations
- 7-color patterns, circular runs, overlays, fades
- Example: ID 1 = "Circulate all modes" (cycles through effects)

### Recommended Effects for Curtain Lights

Some effects look particularly good on 2D matrix displays:

| Effect ID | Name | Description |
|-----------|------|-------------|
| 1 | Change gradually | Smooth color transitions |
| 2 | Bright up and Fade gradually | Pulse effect |
| 3 | Change quickly | Quick color changes |
| 4 | Strobe-flash | Flash effect |
| 29-44 | 7-color patterns | Pre-set rainbow animations |
| 100 | Circulate all modes | Demo mode |
| 101 | 7 colors change gradually | Rainbow fade |

---

## State Query

Query device state using the standard 0x81 state query command.

```python
def build_state_query() -> bytes:
    """Build state query command."""
    return bytes([0x81, 0x8A, 0x8B, 0x96])  # Standard query
```

### State Response Format

Curtain lights use the `wifibleSymphonyCurtainLight` state protocol, which is
similar to standard Symphony state responses.

**Key state bytes:**

| Offset | Field | Notes |
|--------|-------|-------|
| 0 | Header | 0x81 |
| 1 | Product ID | 0xAC (172) or 0xAD (173) |
| 2 | Power | 0x23=ON, 0x24=OFF |
| 3 | Mode | Current mode |
| 4 | Unknown | |
| 5 | Brightness | 0-100 (if applicable) |
| 6 | R or Effect ID | Depends on mode |
| 7 | G or Speed | Depends on mode |
| 8 | B or Param | Depends on mode |

---

## Implementation Notes

### Compatibility with Existing Code

Since curtain lights use the same commands as Symphony devices:

1. **Add product IDs to Symphony detection:**
   ```python
   SYMPHONY_PRODUCT_IDS = [0xA1, 0xA2, 0xA3, ..., 172, 173]
   ```

2. **Use Symphony command builders:**
   - Power: `build_power_command()` (0x3B)
   - Color: `build_color_command_3b()` (0x3B with 0xA1)
   - Effects: `build_effect_command()` (0x38)

3. **Speed encoding is the same:**
   - 1-31 inverted (lower = faster)
   - Same conversion formula as Symphony

### What NOT to Support (Initially)

These curtain-specific features require significant additional code:

- **Text display** (`text_setting_data`, `text_execute_data`)
- **Image gallery** (`image_data`)
- **DIY animations** (`diy_preview_data`, `diy_save_*`)
- **Multi-panel splicing** (`multiple_screen_data`)
- **Horizontal flip** (`flip_data`)

These can be added later if needed.

---

## Quick Reference

### Commands Summary

| Feature | Command | Format |
|---------|---------|--------|
| Power ON | 0x3B | `[0x3B, 0x23, 0,0, 0,0,0, 0,0,0x32, 0,0, chk]` |
| Power OFF | 0x3B | `[0x3B, 0x24, 0,0, 0,0,0, 0,0,0x32, 0,0, chk]` |
| Solid Color | 0x3B | `[0x3B, 0xA1, H_hi, H_lo, S, V, 0, 0,0,0x32, 0,0, chk]` |
| Effect | 0x38 | `[0x38, effect_id, speed(1-31), brightness, chk]` |
| State Query | 0x81 | `[0x81, 0x8A, 0x8B, 0x96]` |

### Speed Conversion

| UI Speed | Protocol Speed | Result |
|----------|----------------|--------|
| 100% | 1 | Fastest |
| 75% | 8 | Fast |
| 50% | 16 | Medium |
| 25% | 23 | Slow |
| 0% | 31 | Slowest |

### Effect ID Ranges

| Range | Type | Example |
|-------|------|---------|
| 1-44 | Scene Effects | Basic animations |
| 1-300 | Build Effects | Complex patterns |

---

**End of LED Curtain Light Protocol Guide**
