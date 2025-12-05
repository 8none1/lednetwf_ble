# Effect Commands by Device Type

**Last Updated**: 5 December 2025  
**Status**: Consolidated from multiple investigation documents  
**Purpose**: Authoritative guide for effect command implementation

---

## Overview

Effect commands vary significantly by device type. Using the wrong format will cause devices to turn off, show incorrect brightness, or behave unpredictably.

**Critical Rules:**
1. **Use Product ID (bytes 8-9) for device detection** - NOT sta_byte (sta_byte is device status)
2. **Different devices use different command formats** - 4-byte vs 5-byte, with/without checksum
3. **Speed encoding varies** - Some devices use direct values, others invert them
4. **Brightness=0 powers OFF the device** - Always use minimum of 1, not 0

---

## Quick Reference Table

| Product ID | Device Type | Command | Format | Bytes | Checksum | Speed Range | Speed Encoding |
|------------|-------------|---------|--------|-------|----------|-------------|----------------|
| **0x1D (29)** | **FillLight/Ring Light** | **0x38** | `[0x38, effect, speed, bright]` | **4** | **NO** | 0-100 | Direct |
| 0x54, 0x55, 0x62 | Addressable Strip | 0x38 | `[0x38, effect, speed, bright, chk]` | 5 | YES | 0-100 | Direct |
| 0x56, 0x80 | Music Strip | 0x42 | `[0x42, effect, speed, bright, chk]` | 5 | YES | 0-100 | Direct |
| 0x5B | Strip Controller | 0x38 | `[0x38, effect, speed, bright, chk]` | 5 | YES | 0-100 | Direct |
| **0xA1-0xA9** | **Symphony Devices** | **0x38** | `[0x38, effect, speed, bright, chk]` | **5** | **YES** | **1-31** | **INVERTED** |
| **0xAA, 0xAB** | **Symphony Strip** | **0x38** | `[0x38, effect, speed, bright, chk]` | **5** | **YES** | **1-31** | **INVERTED** |
| **0xAC, 0xAD (172, 173)** | **LED Curtain Light** | **0x38** | `[0x38, effect, speed, bright, chk]` | **5** | **YES** | **1-31** | **INVERTED** |
| **0x33, 0x06, 0x04** | **Legacy RGB** | **0x61** | `[0x61, effect, speed, persist, chk]` | **5** | **YES** | **1-31** | **INVERTED** |

---

## Device Type Detection

### Step 1: Extract Product ID from Advertisement

```python
def get_device_info(advertisement_data):
    """Extract device info from BLE manufacturer data."""
    mfr_data = advertisement_data.manufacturer_data
    
    # Find LEDnetWF company ID (0x5A** range: 23040-23295)
    for company_id, payload in mfr_data.items():
        if 23040 <= company_id <= 23295 and len(payload) == 27:
            # Format B (bleak) - company ID is dict key, not in payload
            product_id = (payload[8] << 8) | payload[9]  # Big-endian, bytes 8-9
            ble_version = payload[1]
            sta_byte = payload[0]  # Status byte, NOT device type!
            
            return {
                'product_id': product_id,
                'ble_version': ble_version,
                'sta_byte': sta_byte,
                'mac': ':'.join(f'{b:02X}' for b in payload[2:8]),
                'fw_version': payload[10],
                'led_version': payload[11],
            }
    return None
```

### Step 2: Map Product ID to Effect Command Type

```python
def get_effect_command_type(product_id: int) -> str:
    """
    Determine effect command format from product_id.
    
    Returns:
        'filllight_4byte': FillLight devices (no checksum)
        'symphony_5byte': Symphony devices (inverted speed, 1-31 range)
        'standard_5byte': Standard addressable strips (direct speed, 0-100)
        'legacy_rgb': Non-addressable RGB controllers
    """
    # FillLight - 4-byte format, NO checksum
    if product_id == 0x1D:  # 29 decimal
        return 'filllight_4byte'
    
    # Symphony - 5-byte format WITH checksum, INVERTED speed (1-31)
    if product_id in [0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xA7, 0xA9]:  # 161-169
        return 'symphony_5byte'
    
    # Standard addressable - 5-byte format WITH checksum, DIRECT speed (0-100)
    if product_id in [0x54, 0x55, 0x62, 0x5B]:
        return 'standard_5byte'
    
    # Music-reactive strips - Different opcode but similar format
    if product_id in [0x56, 0x80]:
        return 'music_5byte'  # Uses 0x42 instead of 0x38
    
    # Legacy RGB controllers
    if product_id in [0x33, 0x06, 0x04, 0x44]:
        return 'legacy_rgb'
    
    return 'unknown'
```

---

## Format A: FillLight / Ring Light (Product ID 0x1D)

### Device Characteristics

- **Product ID**: 0x1D (29 decimal)
- **Device Class**: FillLight0x1D (extends BaseDeviceInfo)
- **Common Names**: LED Ring Light, Fill Light
- **Effects**: 93 custom effects (IDs 1-93) + 0xFF for "cycle all modes"

### Effect Command Format (0x38) - 4 bytes, NO checksum

```
Raw command: [0x38, effect_id, speed, brightness]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command opcode | 0x38 | Fixed value |
| 1 | Effect ID | 1-93, 0xFF | 0xFF = cycle through all effects |
| 2 | Speed | 0-100 | **DIRECT**: 0=slowest, 100=fastest |
| 3 | Brightness | 0-100 | **Percent scale**: 0=OFF (avoid!), use 1-100 |

**CRITICAL**: This is the ONLY device type that uses 4 bytes with NO checksum!

### Python Implementation

```python
def build_effect_filllight(effect_id: int, speed: int, brightness: int) -> bytes:
    """
    Build FillLight effect command (4 bytes, NO checksum).
    
    Args:
        effect_id: 1-93 or 0xFF for cycle all
        speed: 0-100 (0=slowest, 100=fastest - DIRECT encoding)
        brightness: 1-100 (NEVER use 0, it powers OFF!)
    
    Returns:
        4-byte command (no transport wrapper)
    """
    # Validate and clamp
    if effect_id != 0xFF:
        effect_id = max(1, min(93, effect_id))
    speed = max(0, min(100, speed))
    brightness = max(1, min(100, brightness))  # Min 1, not 0!
    
    # 4 bytes, NO checksum
    return bytes([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF
    ])
```

### Example Commands

**Effect 1, speed 50, brightness 100%:**
```
Unwrapped: 38 01 32 64
Wrapped:   00 01 80 00 00 04 05 0b 38 01 32 64
```

**Effect 5, speed 80, brightness 50%:**
```
Unwrapped: 38 05 50 32
Wrapped:   00 02 80 00 00 04 05 0b 38 05 50 32
```

**Cycle all effects, speed 100, brightness 75%:**
```
Unwrapped: 38 ff 64 4b
Wrapped:   00 03 80 00 00 04 05 0b 38 ff 64 4b
```

### State Response Parsing

When device is in effect mode, state query (0x81) returns:

```
State response (14 bytes):
Byte 0:  0x81 (response header)
Byte 1:  mode
Byte 2:  0x23=ON, 0x24=OFF
Byte 3:  0x25 (effect mode indicator)
Byte 4:  effect_id (1-93 or 0xFF)
Byte 5:  unknown/reserved
Byte 6:  brightness (0-100) ← In R position!
Byte 7:  speed (0-100 direct) ← In G position!
Byte 8:  unknown
...
```

**Key difference from Symphony**: Brightness is in byte 6 (R position), speed in byte 7 (G position).

```python
def parse_filllight_effect_state(response: bytes) -> dict:
    """Parse effect state from FillLight device."""
    if len(response) < 14 or response[0] != 0x81:
        return None
    
    if response[3] != 0x25:  # Not in effect mode
        return None
    
    return {
        'power_on': response[2] == 0x23,
        'mode': 'effect',
        'effect_id': response[4],
        'brightness': response[6],  # R position
        'speed': response[7],        # G position
    }
```

### Android Source Evidence

From `com/zengge/wifi/Device/a.java` (device class mapping):
```java
case 29:  // 0x1D
    return new FillLight0x1D(deviceInfo);
```

From `com/zengge/wifi/Device/Type/FillLight0x1D.java`:
```java
public class FillLight0x1D extends BaseDeviceInfo {
    // Stub class - uses BaseDeviceInfo defaults
    // No special effect command overrides
    // Uses the 4-byte format
}
```

---

## Format B: Symphony Devices (Product IDs 0xA1-0xA9)

### Device Characteristics

- **Product IDs**: 0xA1-0xA9 (161-169 decimal)
- **Device Classes**: 
  - Ctrl_Mini_RGB_Symphony_0xa1 (0xA1/161)
  - Ctrl_Mini_RGB_Symphony_new_0xa2 through 0xa9 (162-169)
- **Common Names**: Symphony LED Strip Controllers, Addressable LED Controllers
- **Effects**: 44 Symphony Scene effects + 300 Build effects

### Effect Command Format (0x38) - 5 bytes WITH checksum

```
Raw command: [0x38, effect_id, speed, brightness, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command opcode | 0x38 | Fixed value |
| 1 | Effect ID | 1-44 | Symphony Scene effects (or 1-300 Build) |
| 2 | Speed | 1-31 | **INVERTED**: 1=fastest, 31=slowest |
| 3 | Brightness | 1-100 | **Percent scale**: NEVER use 0 (powers OFF!) |
| 4 | Checksum | calculated | Sum of bytes 0-3, masked with 0xFF |

**CRITICAL Differences from FillLight:**
1. **Has checksum** (5 bytes total)
2. **Speed is INVERTED**: lower values = faster
3. **Speed range 1-31**: NOT 0-100!
4. **Different state response format**

### Speed Encoding (INVERTED!)

The Symphony devices use an inverted speed scale mapped to 1-31 range:

```python
def map_speed_to_symphony(ui_speed: int) -> int:
    """
    Map UI speed (0-100, where 0=slow, 100=fast) to Symphony protocol (1-31, inverted).
    
    Args:
        ui_speed: 0-100 (0=slowest, 100=fastest)
    
    Returns:
        1-31 (1=fastest, 31=slowest) - INVERTED!
    """
    # Clamp to valid range
    ui_speed = max(0, min(100, ui_speed))
    
    # Map 0-100 to 31-1 (inverted)
    # Formula: 31 - (speed * 30 / 100)
    protocol_speed = 31 - int(ui_speed * 30 / 100)
    
    # Ensure in valid range 1-31
    return max(1, min(31, protocol_speed))

# Examples:
# UI speed 0   (slowest) → 31 (slowest)
# UI speed 50  (medium)  → 16 (medium)
# UI speed 100 (fastest) → 1  (fastest)
```

**Why is it inverted?** The Android app code in `tc/d.java` uses this formula:
```java
// From FragmentUniteControl.java lines 1185-1189
int speed = Math.round(g2.d.f(100.0f, 0.0f, 31.0f, 1.0f, seekBarValue));
// This maps 0-100 → 31-1 (reversed range)
```

### Brightness Rules

**NEVER set brightness to 0!** This is treated as a power-off command:

```python
def safe_brightness(brightness: int) -> int:
    """
    Ensure brightness is in safe range 1-100.
    Brightness=0 powers OFF Symphony devices!
    """
    brightness = max(1, min(100, brightness))  # Clamp to 1-100, not 0-100
    return brightness
```

### Python Implementation

```python
def build_effect_symphony(effect_id: int, speed: int, brightness: int) -> bytes:
    """
    Build Symphony effect command (5 bytes WITH checksum).
    
    Args:
        effect_id: 1-44 for Scene effects, 1-300 for Build effects
        speed: 0-100 UI scale (will be mapped to 1-31 inverted)
        brightness: 1-100 (NEVER 0!)
    
    Returns:
        5-byte command with checksum (no transport wrapper)
    """
    # Validate effect ID
    effect_id = max(1, min(300, effect_id))
    
    # Map UI speed (0-100) to protocol speed (1-31 inverted)
    protocol_speed = 31 - int(speed * 30 / 100)
    protocol_speed = max(1, min(31, protocol_speed))
    
    # Ensure brightness is never 0
    brightness = max(1, min(100, brightness))
    
    # Build command
    cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        protocol_speed & 0xFF,
        brightness & 0xFF
    ])
    
    # Add checksum
    cmd.append(sum(cmd) & 0xFF)
    
    return bytes(cmd)
```

### Example Commands

**Effect 1 (Scene), UI speed 50 (medium), brightness 100%:**
```
UI values: effect=1, speed=50, bright=100
Protocol:  effect=1, speed=16 (inverted), bright=100
Unwrapped: 38 01 10 64 ad
Wrapped:   00 01 80 00 00 05 06 0b 38 01 10 64 ad
```

**Effect 10 (Scene), UI speed 100 (fast), brightness 50%:**
```
UI values: effect=10, speed=100, bright=50
Protocol:  effect=10, speed=1 (fastest), bright=50
Unwrapped: 38 0a 01 32 75
Wrapped:   00 02 80 00 00 05 06 0b 38 0a 01 32 75
```

**Effect 5, UI speed 0 (slow), brightness 75%:**
```
UI values: effect=5, speed=0, bright=75
Protocol:  effect=5, speed=31 (slowest), bright=75
Unwrapped: 38 05 1f 4b b1
Wrapped:   00 03 80 00 00 05 06 0b 38 05 1f 4b b1
```

### State Response Parsing

When Symphony device is in effect mode:

```
State response (14 bytes):
Byte 0:  0x81 (response header)
Byte 1:  mode
Byte 2:  0x23=ON, 0x24=OFF
Byte 3:  0x25 (effect mode indicator)
Byte 4:  effect_id
Byte 5:  brightness (1-100) ← Different position than FillLight!
Byte 6:  unknown/reserved (often 0)
Byte 7:  speed (1-31 inverted protocol value)
...
```

**Key difference**: Brightness is in byte 5 (NOT byte 6 like FillLight).

```python
def parse_symphony_effect_state(response: bytes) -> dict:
    """Parse effect state from Symphony device."""
    if len(response) < 14 or response[0] != 0x81:
        return None
    
    if response[3] != 0x25:  # Not in effect mode
        return None
    
    protocol_speed = response[7]  # 1-31 inverted
    # Convert back to UI speed (0-100)
    ui_speed = int((31 - protocol_speed) * 100 / 30)
    
    return {
        'power_on': response[2] == 0x23,
        'mode': 'effect',
        'effect_id': response[4],
        'brightness': response[5],  # Byte 5, not 6!
        'speed': ui_speed,           # Converted to UI scale
        'speed_raw': protocol_speed, # Raw protocol value
    }
```

### Android Source Evidence

From `tc/d.java` (Symphony command builder):
```java
// Method d() - lines 43-50
public static byte[] d(int i10, int i11, int i12) {
    byte[] bArr = new byte[5];
    bArr[0] = 56;           // 0x38
    bArr[1] = (byte) i10;   // effect_id
    bArr[2] = (byte) i11;   // speed (already inverted when passed in)
    bArr[3] = (byte) i12;   // brightness
    bArr[4] = b.b(bArr, 4); // checksum
    return bArr;
}
```

From `FragmentUniteControl.java` (speed inversion call):
```java
// Lines 1185-1189
int speed = Math.round(g2.d.f(100.0f, 0.0f, 31.0f, 1.0f, seekBarValue));
// g2.d.f() maps input range to output range with reversal
// Maps 0-100 → 31-1
```

### Symphony Effect Lists

**Scene Effects (IDs 1-44)**: See `12_symphony_effect_names.md` for complete list
- Effect 1: "Change gradually"
- Effect 5: "Running, 1point from start to end"
- Effect 29: "7 colors run alternately, 1 point from start to end"
- ...44 total scene effects

**Build Effects (IDs 1-300)**: Also in `12_symphony_effect_names.md`
- Displayed as IDs 100-399 in UI (internal ID + 99)
- Effect 1: "Circulate all modes"
- Effect 2: "7 colors change gradually"
- ...300 total build effects

---

## Format C: Standard Addressable Strips (5-byte, Direct Speed)

### Device Characteristics

- **Product IDs**: 0x54, 0x55, 0x62, 0x5B
- **Common Names**: LED Strip Controllers (non-Symphony)
- **Speed Encoding**: Direct (0-100), NOT inverted

### Effect Command Format (0x38) - 5 bytes WITH checksum

```
Raw command: [0x38, effect_id, speed, brightness, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command opcode | 0x38 | Fixed value |
| 1 | Effect ID | varies | Device-specific |
| 2 | Speed | 0-100 | **DIRECT**: 0=slowest, 100=fastest |
| 3 | Brightness | 1-100 | **Percent scale**: Avoid 0 |
| 4 | Checksum | calculated | Sum of bytes 0-3, masked with 0xFF |

### Python Implementation

```python
def build_effect_standard(effect_id: int, speed: int, brightness: int) -> bytes:
    """
    Build standard addressable strip effect command.
    
    Args:
        effect_id: Device-specific effect ID
        speed: 0-100 (0=slowest, 100=fastest - DIRECT, no inversion)
        brightness: 1-100
    
    Returns:
        5-byte command with checksum
    """
    # Validate
    effect_id = max(1, min(255, effect_id))
    speed = max(0, min(100, speed))
    brightness = max(1, min(100, brightness))
    
    # Build command
    cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF
    ])
    
    # Add checksum
    cmd.append(sum(cmd) & 0xFF)
    
    return bytes(cmd)
```

### Special Commands for 0x54/0x5B Devices

**Candle Mode (0x39)**:
```python
def build_candle_mode(on: bool, r: int, g: int, b: int, speed: int, brightness: int) -> bytes:
    """Build candle flicker effect command."""
    cmd = bytearray([
        0x39,
        0x01 if on else 0x00,
        r & 0xFF,
        g & 0xFF,
        b & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,
        0x00  # Reserved
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

---

## Format D: Music-Reactive Strips (Product IDs 0x56, 0x80)

### Device Characteristics

- **Product IDs**: 0x56, 0x80
- **Special Feature**: Music-reactive modes
- **Main Command**: 0x42 (different opcode!)

### Effect Command Format (0x42) - 5 bytes WITH checksum

```
Raw command: [0x42, effect_id, speed, brightness, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command opcode | 0x42 | **Different from 0x38!** |
| 1 | Effect ID | varies | Device-specific |
| 2 | Speed | 0-100 | DIRECT |
| 3 | Brightness | 1-100 | Percent scale |
| 4 | Checksum | calculated | Sum of bytes 0-3 |

### Python Implementation

```python
def build_effect_music(effect_id: int, speed: int, brightness: int) -> bytes:
    """Build music-reactive strip effect command."""
    effect_id = max(1, min(255, effect_id))
    speed = max(0, min(100, speed))
    brightness = max(1, min(100, brightness))
    
    cmd = bytearray([
        0x42,  # Different opcode!
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

### Additional Commands for 0x56 Devices

**Static Effect with FG/BG Colors (0x41)**:
```python
def build_static_fg_bg(effect_id: int, fg_rgb: tuple, bg_rgb: tuple, 
                       speed: int, direction: int) -> bytes:
    """
    Build static effect with foreground and background colors.
    
    Args:
        effect_id: Effect mode
        fg_rgb: (R, G, B) foreground color
        bg_rgb: (R, G, B) background color
        speed: 0-255
        direction: 0=forward, 1=reverse
    """
    cmd = bytearray([
        0x41,
        effect_id & 0xFF,
        fg_rgb[0] & 0xFF,  # Foreground R
        fg_rgb[1] & 0xFF,  # Foreground G
        fg_rgb[2] & 0xFF,  # Foreground B
        bg_rgb[0] & 0xFF,  # Background R
        bg_rgb[1] & 0xFF,  # Background G
        bg_rgb[2] & 0xFF,  # Background B
        speed & 0xFF,
        direction & 0xFF,
        0x00,  # Reserved
        0xF0,  # Persist flag
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

**Music Mode (0x73)**:
```python
def build_music_mode(on: bool, effect_id: int, fg_rgb: tuple, bg_rgb: tuple,
                     speed: int, brightness: int) -> bytes:
    """Build music-reactive mode command."""
    cmd = bytearray([
        0x73,
        0x01 if on else 0x00,
        0x00,  # Unknown
        effect_id & 0xFF,
        fg_rgb[0] & 0xFF,
        fg_rgb[1] & 0xFF,
        fg_rgb[2] & 0xFF,
        bg_rgb[0] & 0xFF,
        bg_rgb[1] & 0xFF,
        bg_rgb[2] & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

---

## Format E: Legacy RGB Controllers (Non-Addressable)

### Device Characteristics

- **Product IDs**: 0x33, 0x06, 0x04, 0x44, and other non-addressable RGB devices
- **Effects**: Simple effects (IDs 37-56)
- **No addressable LED support**

### Product ID 0x33 (Ctrl_Mini_RGB) Effect Support

**Product ID 0x33 DOES support effects!** The effects are the simple 0x61 effects (IDs 37-56),
NOT the addressable Symphony effects.

**Note**: The `s0()` method returns empty for 0x33 because it only returns *addressable/Symphony*
effects. The simple effects (37-56) are provided by `dd.g.k()` and are available via the
Dynamic Mode UI in the Android app.

**Effect Command Path (from Java source):**
1. `ActivityCMDBase.x0()` calls `Protocol.n` constructor
2. `Protocol.n` checks device type and calls `tc.b.c()` for non-Symphony devices
3. `tc.b.c()` builds the 5-byte 0x61 command with speed 1-31 (inverted)

### Effect Command Format (0x61) - 5 bytes WITH checksum

```
Raw command: [0x61, effect_id, speed, persist, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command opcode | 0x61 | Fixed value |
| 1 | Effect ID | 37-56 | 20 simple effects |
| 2 | Speed | **1-31** | **INVERTED: 1=fastest, 31=slowest** |
| 3 | Persist | 0xF0/0x0F | 0xF0=save, 0x0F=temporary |
| 4 | Checksum | calculated | Sum of bytes 0-3 |

### Speed Encoding (CRITICAL - From Java Source!)

**From `COMM/Protocol/n.java` line 23:**
```java
tc.b.c(i10, ad.e.a(f10, 1, 31), false)
```

**From `ad/e.java` line 32-34:**
```java
public static byte a(float f10, int i10, int i11) {
    return (byte) (i10 + ((i11 - i10) * (1.0f - f10)));
}
```

This means:
- **Speed range is 1-31 (NOT 0-255!)**
- **Speed is INVERTED: lower values = faster**
- UI 100% (fastest) → protocol value 1
- UI 50% (medium) → protocol value 16
- UI 0% (slowest) → protocol value 31

```python
def map_ui_speed_to_legacy_protocol(ui_speed: int) -> int:
    """
    Convert UI speed (0-100, 0=slow, 100=fast) to protocol speed (1-31, inverted).

    From ad/e.java: result = min + ((max-min) * (1.0 - normalized_speed))
    With min=1, max=31: result = 1 + (30 * (1.0 - speed/100))
    """
    ui_speed = max(0, min(100, ui_speed))
    normalized = ui_speed / 100.0
    protocol_speed = 1 + int(30 * (1.0 - normalized))
    return max(1, min(31, protocol_speed))

# Examples:
# UI 100% (fast)  → 1 + (30 * 0.0)  = 1  (fastest)
# UI 50% (medium) → 1 + (30 * 0.5)  = 16 (medium)
# UI 0% (slow)    → 1 + (30 * 1.0)  = 31 (slowest)
```

### NO Brightness Byte!

**Important**: The 0x61 command does NOT have a brightness byte!
Brightness for legacy RGB controllers is controlled separately via the 0x31
static color command or is inherent to the effect.

### Python Implementation

```python
def build_effect_legacy(effect_id: int, ui_speed: int, persist: bool = False) -> bytes:
    """
    Build legacy RGB effect command.

    Args:
        effect_id: 37-56 (simple effects)
        ui_speed: 0-100 (0=slowest, 100=fastest - will be inverted internally)
        persist: Save to flash memory

    Note: NO brightness parameter - brightness controlled separately via 0x31
    """
    effect_id = max(37, min(56, effect_id))

    # Convert UI speed (0-100) to protocol speed (1-31, inverted)
    normalized = max(0, min(100, ui_speed)) / 100.0
    protocol_speed = 1 + int(30 * (1.0 - normalized))
    protocol_speed = max(1, min(31, protocol_speed))

    cmd = bytearray([
        0x61,
        effect_id & 0xFF,
        protocol_speed & 0xFF,
        0xF0 if persist else 0x0F
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

### Common Mistake: Wrong Speed Range

**BAD (what user sent):**
```
61 29 BA 0F 53
      ^^
      Speed=186 (0xBA) - WRONG! Outside valid range 1-31!
```

This causes undefined behavior because the device expects 1-31, not 0-255.

**CORRECT (same effect at ~73% UI speed):**
```python
# Effect 41 (Yellow gradual change), 73% speed, temporary
# UI speed 73% → protocol speed: 1 + (30 * 0.27) = 9
cmd = [0x61, 0x29, 0x09, 0x0F]
checksum = (0x61 + 0x29 + 0x09 + 0x0F) & 0xFF  # = 0xA2
final = [0x61, 0x29, 0x09, 0x0F, 0xA2]
```

### Simple Effect List (IDs 37-56)

From `dd/g.java`:
- 37: Seven color cross fade
- 38: Red gradual change
- 39: Green gradual change
- 40: Blue gradual change
- 41: Yellow gradual change
- 42: Cyan gradual change
- 43: Purple gradual change
- 44: White gradual change
- 45: Red/green cross fade
- 46: Red/blue cross fade
- 47: Green/blue cross fade
- 48: Seven color strobe flash
- 49: Red strobe flash
- 50: Green strobe flash
- 51: Blue strobe flash
- 52: Yellow strobe flash
- 53: Cyan strobe flash
- 54: Purple strobe flash
- 55: White strobe flash
- 56: Seven color jumping change

---

## Troubleshooting Common Issues

### Issue 1: Device Turns Off When Setting Effect

**Symptom**: Sending effect command causes device to power off instead of showing effect.

**Causes**:
1. **Brightness set to 0** - This is treated as power-off command
2. **Wrong command format** - Using 5-byte format on 4-byte device (or vice versa)
3. **Missing checksum** - Sending 4 bytes to device that expects 5
4. **Wrong opcode** - Using 0x38 on 0x42 device

**Solutions**:
```python
# Always use minimum brightness of 1, never 0
brightness = max(1, min(100, brightness))

# Detect device type from product_id, not sta_byte
cmd_type = get_effect_command_type(product_id)

# Use correct builder for device type
if cmd_type == 'filllight_4byte':
    cmd = build_effect_filllight(effect, speed, brightness)
elif cmd_type == 'symphony_5byte':
    cmd = build_effect_symphony(effect, speed, brightness)
# etc.
```

### Issue 2: Effect Speed Behaves Backwards (Symphony Devices)

**Symptom**: Increasing speed makes effect slower, or vice versa.

**Cause**: Symphony devices use inverted speed encoding (1=fast, 31=slow).

**Solution**:
```python
# Map UI speed (0=slow, 100=fast) to protocol speed (31=slow, 1=fast)
protocol_speed = 31 - int(ui_speed * 30 / 100)
protocol_speed = max(1, min(31, protocol_speed))
```

### Issue 3: Brightness Not Updating

**Symptom**: Effect brightness doesn't change when sending new values.

**Causes**:
1. **Reading wrong byte in state response**
   - FillLight: brightness in byte 6
   - Symphony: brightness in byte 5
2. **Not waiting for device to update**
3. **Brightness value out of range**

**Solution**:
```python
# Check device type for correct byte position
if cmd_type == 'filllight_4byte':
    current_brightness = state_response[6]  # Byte 6
elif cmd_type == 'symphony_5byte':
    current_brightness = state_response[5]  # Byte 5

# Always clamp brightness
brightness = max(1, min(100, brightness))
```

### Issue 4: Effect ID Not Working

**Symptom**: Device doesn't recognize effect ID or shows wrong effect.

**Causes**:
1. **Effect ID out of range for device type**
   - FillLight: 1-93
   - Symphony Scene: 1-44
   - Symphony Build: 1-300
   - Legacy RGB: 37-56
2. **Using internal ID instead of UI ID** (Symphony Build effects)

**Solution**:
```python
# Symphony Build effects: UI displays 100-399, but protocol uses 1-300
if effect_id >= 100:
    internal_id = effect_id - 99  # Convert UI ID to internal
else:
    internal_id = effect_id

# Validate against device capabilities
if product_id == 0x1D:  # FillLight
    internal_id = max(1, min(93, internal_id))
elif product_id in [0xA1, 0xA2, 0xA3]:  # Symphony
    internal_id = max(1, min(300, internal_id))
```

### Issue 5: Checksum Errors

**Symptom**: Commands ignored, device doesn't respond, or behaves erratically.

**Cause**: Incorrect checksum calculation.

**Solution**:
```python
def calculate_checksum(data: bytes) -> int:
    """Calculate checksum for command bytes."""
    return sum(data) & 0xFF

# Example
cmd = bytearray([0x38, 0x01, 0x10, 0x64])
checksum = calculate_checksum(cmd)  # Sum all bytes, mask with 0xFF
cmd.append(checksum)
```

**Remember**: FillLight (0x1D) is the ONLY device with NO checksum!

---

## Implementation Checklist

When implementing effect commands:

- [ ] Extract product_id from manufacturer data (bytes 8-9, big-endian)
- [ ] Map product_id to effect command type (not sta_byte!)
- [ ] Use correct command format (4-byte vs 5-byte)
- [ ] Add checksum if required (all except FillLight)
- [ ] Handle speed encoding (direct vs inverted)
- [ ] Clamp brightness to 1-100 (never 0!)
- [ ] Validate effect_id range for device type
- [ ] Parse state response from correct byte positions
- [ ] Wrap command in transport layer before sending
- [ ] Test with actual device (essential!)

---

## Android Source Code References

Key files for effect command implementation:

| File | Purpose | Key Methods |
|------|---------|-------------|
| `tc/d.java` | Symphony command builder | `d()` - Effect command |
| `tc/b.java` | Legacy command builders | `c()` - RGB effect (0x61) |
| `Protocol/n.java` | Effect protocol handler | Wraps tc/d.java calls |
| `FragmentUniteControl.java` | UI controller | Speed inversion logic |
| `Device/a.java` | Device mapping | `k()` - Product ID → Class |
| `Device/Type/FillLight0x1D.java` | FillLight class | Device-specific behavior |
| `Device/Type/Ctrl_Mini_RGB_Symphony_*.java` | Symphony classes | Symphony-specific behavior |

---

## Summary Table

| Aspect | FillLight (0x1D) | Symphony (0xA1-0xA9) | Standard (0x54, 0x5B) | Music (0x56, 0x80) | Legacy RGB |
|--------|------------------|----------------------|-----------------------|--------------------|------------|
| **Bytes** | 4 | 5 | 5 | 5 | 5 |
| **Checksum** | NO | YES | YES | YES | YES |
| **Opcode** | 0x38 | 0x38 | 0x38 | 0x42 | 0x61 |
| **Speed Range** | 0-100 | 1-31 | 0-100 | 0-100 | 0-255 |
| **Speed Encoding** | Direct | Inverted | Direct | Direct | Varies |
| **Brightness** | 0-100 (avoid 0) | 1-100 (never 0!) | 1-100 | 1-100 | N/A |
| **State Byte 5** | Unknown | Brightness | Brightness | Brightness | N/A |
| **State Byte 6** | Brightness | Reserved | Unknown | Unknown | N/A |
| **State Byte 7** | Speed | Speed (inverted) | Speed | Speed | N/A |
| **Effect Count** | 93 | 44+300 | Varies | Varies | 20 |

---

**End of Effect Commands Guide**
