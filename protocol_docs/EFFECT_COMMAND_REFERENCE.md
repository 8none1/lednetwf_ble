# Effect Command Reference by Device Type

**Last Updated**: 4 December 2025  
**Source**: Android app source code analysis + working Python implementation

This document maps each device type (sta byte) to its specific effect command formats.

---

## Command Summary Table

| Sta Byte | Product IDs | Main Command | Format | Bytes | Checksum | Special Commands |
|----------|-------------|--------------|--------|-------|----------|------------------|
| **0x53** | 0x001D | **0x38** | `[0x38, effect, speed, bright]` | **4** | **NO** | None |
| 0x54 | 0x54, 0x55, 0x62 | 0x38 | `[0x38, effect, speed, bright, chk]` | 5 | YES | 0x39 (candle) |
| 0x56 | 0x56, 0x80 | 0x42 | `[0x42, effect, speed, bright, chk]` | 5 | YES | 0x41 (static), 0x73 (music) |
| 0x5B | 0x5B | 0x38 | `[0x38, effect, speed, bright, chk]` | 5 | YES | 0x39 (candle), 0x63 (RGB jump) |
| 0xA1-0xA9 | Symphony | 0x38 | `[0x38, effect, speed, param, chk]` | 5 | YES | None (different param meaning) |
| Others | RGB bulbs | 0x61 | `[0x61, effect, speed, persist, chk]` | 5 | YES | Effects 37-56 |

---

## 0x53 Devices - UNIQUE FORMAT

**Product ID**: 0x001D (FillLight0x1D)  
**Device Type**: Addressable LED Ring Light  
**Effects**: 93+ custom effects (IDs 1-93, plus 0xFF for "All modes")

### Effect Command (0x38) - 4 bytes, NO checksum

```python
# Raw payload (before transport wrapping)
[0x38, effect_id, speed, brightness]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x38 | Fixed |
| 1 | Effect ID | 1-93, 0xFF | 0xFF = cycle all modes |
| 2 | Speed | 0-255 | Higher = faster |
| 3 | Brightness | 0-100 | **Percent, not 0-255!** |

**CRITICAL**: NO checksum byte! Total payload is only 4 bytes.

### Example Packet

Effect 1, speed 50 (0x32), brightness 100%:

```
Unwrapped: 38 01 32 64
Wrapped:   00 00 80 00 00 04 05 0b 38 01 32 64
           └──────transport────┘ └─payload──┘
```

### Python Implementation

```python
def build_effect_0x53(effect_id: int, speed: int, brightness: int) -> bytearray:
    """Build 0x53 effect command - NO CHECKSUM!"""
    raw_cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,  # 0-100 percent!
    ])
    return wrap_command(raw_cmd, cmd_family=0x0b)
```

### Android Source

**NOT FOUND** - The 4-byte variant without checksum is not explicitly in `tc/b.java` or `tc/d.java`. This suggests:
1. It's constructed inline in device-specific code
2. It's an older protocol variant not in current Android app
3. The old Python code discovered this through reverse engineering

The working Python implementation is the authoritative source for 0x53.

---

## 0x54 Devices (also 0x55, 0x62)

**Device Type**: Addressable LED strips with candle mode  
**Effects**: 
- Standard effects: IDs 37-56 (21 effects)
- Candle mode: ID 100
- Sound reactive: ID 200 (not fully implemented)

### Command 1: Standard Effects (0x38) - 5 bytes with checksum

```python
[0x38, effect_id, speed_inverted, brightness, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x38 | Fixed |
| 1 | Effect ID | 37-56 | Standard effect range |
| 2 | Speed | 0x01-0x1F | **INVERTED**: `0x1F - ((speed-1) * (0x1F-0x01) / 99)` |
| 3 | Brightness | 0-100 | Percent |
| 4 | Checksum | - | Sum of bytes 0-3 (after transport unwrapping) |

**Note**: Speed calculation inverts the range so 0x01 = 100% speed, 0x1F = 1% speed.

### Command 2: Candle Mode (0x39) - 9 bytes with checksum

```python
[0x39, 0xD1, R, G, B, speed_inverted, brightness, 0x03, checksum]
```

| Byte | Field | Value | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x39 | Fixed |
| 1 | Mode | 0xD1 | Fixed (on) |
| 2-4 | RGB | 0-255 each | Flame color |
| 5 | Speed | 0x01-0x1F | Inverted (same formula as 0x38) |
| 6 | Brightness | 0-100 | Percent |
| 7 | Parameter | 0x03 | Fixed |
| 8 | Checksum | - | Sum of bytes 0-7 |

### Python Implementation

```python
def build_effect_0x54(effect_id: int, speed: int, brightness: int) -> bytearray:
    """Standard effects for 0x54."""
    # Invert speed: 100% -> 0x01, 1% -> 0x1F
    speed_inv = round(0x1F - (speed - 1) * (0x1F - 0x01) / 99)
    
    raw_cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed_inv & 0xFF,
        brightness & 0xFF,
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)

def build_candle_0x39(rgb: tuple, speed: int, brightness: int) -> bytearray:
    """Candle mode for 0x54."""
    speed_inv = round(0x1F - (speed - 1) * (0x1F - 0x01) / 99)
    
    raw_cmd = bytearray([
        0x39,
        0xD1,  # On
        rgb[0], rgb[1], rgb[2],
        speed_inv & 0xFF,
        brightness & 0xFF,
        0x03,  # Fixed parameter
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)
```

### Android Source

- **0x39 command**: tc/b.java method `a()` at line 1226
  ```java
  public static byte[] a(boolean z10, int i10, int i11, int i12, int i13, int i14, int i15) {
      byte[] bArr = new byte[9];
      bArr[0] = 57;  // 0x39
      bArr[1] = (byte) (z10 ? 209 : CipherSuite.TLS_PSK_WITH_NULL_SHA384);  // 0xD1 or other
      bArr[2] = (byte) i10;  // R
      bArr[3] = (byte) i11;  // G
      // ... etc
  ```

---

## 0x56 Devices (also 0x80)

**Device Type**: Advanced addressable LED strips with FG/BG colors  
**Effects**: 
- Standard effects: IDs 1-99
- Static effects with colors: IDs 1-10 (encoded as `effect_id << 8`)
- Sound reactive: IDs 1-15 (encoded as `(id+0x32) << 8`)
- Cycle all: ID 255

### Command 1: Standard Effects (0x42) - 5 bytes with checksum

```python
[0x42, effect_id, speed, brightness, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x42 | Fixed |
| 1 | Effect ID | 1-99, 255 | 255 = cycle all |
| 2 | Speed | 0-255 | Normal speed range |
| 3 | Brightness | 0-100 | Percent |
| 4 | Checksum | - | Sum of bytes 0-3 |

### Command 2: Static Effects with FG/BG (0x41) - 13 bytes with checksum

Used for "Static Effect 1" (solid color) and "Static Effect 2-10" (animations with colors).

```python
[0x41, effect_id, R_fg, G_fg, B_fg, R_bg, G_bg, B_bg, speed, direction, 0x00, 0xF0, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x41 | Fixed |
| 1 | Effect ID | 1-10 | Original ID (before shifting) |
| 2-4 | FG RGB | 0-255 each | Foreground color |
| 5-7 | BG RGB | 0-255 each | Background color |
| 8 | Speed | 0-255 | Normal speed |
| 9 | Direction | 0 or 1 | 0=forward, 1=reverse |
| 10 | Reserved | 0x00 | Fixed |
| 11 | Persist | 0xF0 | Save to device |
| 12 | Checksum | - | Sum of bytes 0-11 |

**Effect ID encoding**: Python code uses `effect_id << 8` (e.g., `0x0100` for effect 1) as a marker, then shifts back with `effect_id >> 8` before building the command.

### Command 3: Music Reactive (0x73) - 13 bytes with checksum

```python
[0x73, 0x00, 0x26, effect_id, R_fg, G_fg, B_fg, R_bg, G_bg, B_bg, speed, brightness, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x73 | Fixed |
| 1 | On/Off | 0x00 or 0x01 | 0x01 = on |
| 2 | Subcommand | 0x26 | Fixed |
| 3 | Effect ID | 1-15 | Internal ID (after shifting) |
| 4-6 | FG RGB | 0-255 each | Foreground color |
| 7-9 | BG RGB | 0-255 each | Background color |
| 10 | Speed | 0-255 | Actually sensitivity |
| 11 | Brightness | 0-100 | Percent |
| 12 | Checksum | - | Sum of bytes 0-11 |

**Effect ID encoding**: Python code uses `(effect_id + 0x32) << 8` for music effects (e.g., `0x3300` for effect 1), then decodes with `(effect_id >> 8) - 0x32`.

### Python Implementation

```python
def build_effect_0x56_standard(effect_id: int, speed: int, brightness: int) -> bytearray:
    """Standard effects for 0x56."""
    raw_cmd = bytearray([
        0x42,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)

def build_effect_0x56_static(effect_id: int, fg_rgb: tuple, bg_rgb: tuple, speed: int) -> bytearray:
    """Static effects with FG/BG colors for 0x56."""
    # effect_id should be 1-10 (original, before << 8 encoding)
    raw_cmd = bytearray([
        0x41,
        effect_id & 0xFF,
        fg_rgb[0], fg_rgb[1], fg_rgb[2],
        bg_rgb[0], bg_rgb[1], bg_rgb[2],
        speed & 0xFF,
        0x00,  # direction (0=forward)
        0x00,  # reserved
        0xF0,  # persist
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)

def build_effect_0x56_music(effect_id: int, fg_rgb: tuple, bg_rgb: tuple, speed: int, brightness: int) -> bytearray:
    """Music reactive effects for 0x56."""
    # effect_id should be 1-15 (internal, after decoding from (id+0x32)<<8)
    raw_cmd = bytearray([
        0x73,
        0x01,  # on
        0x26,  # fixed subcommand
        effect_id & 0xFF,
        fg_rgb[0], fg_rgb[1], fg_rgb[2],
        bg_rgb[0], bg_rgb[1], bg_rgb[2],
        speed & 0xFF,
        brightness & 0xFF,
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)
```

### Android Source

- **0x41 command**: com/zengge/wifi/COMM/Protocol/l.java (Symphony static effects)
- **0x73 command**: Not yet found in Android source (device-specific)
- **0x42 command**: Not yet found as a distinct method (may be inline)

---

## 0x5B Devices

**Device Type**: CCT strips & Sunrise lamps  
**Effects**:
- Standard effects: IDs 37-56 (21 effects)
- RGB Jump: ID 0x63 (99)
- Candle mode: ID 100

### Command 1: Standard Effects (0x38) - 5 bytes with checksum

Same format as 0x54:

```python
[0x38, effect_id, speed_inverted, brightness, checksum]
```

Speed is inverted using same formula as 0x54.

### Command 2: Candle Mode (0x39) - 9 bytes with checksum

Same format as 0x54 candle mode.

### Python Implementation

Same as 0x54 (see above).

---

## Symphony Devices (0xA1-0xA9, 0x08)

**Device Type**: Symphony LED controllers  
**Effects**:
- Scene effects: IDs 1-44
- Build effects: IDs 100-399 (internal: 1-300)

### Effect Command (0x38) - 5 bytes with checksum

```python
[0x38, effect_id, speed, param, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x38 | Fixed |
| 1 | Effect ID | 1-44 or 1-300 | Build effects: subtract 99 from UI ID |
| 2 | Speed | 0-255 | Normal speed range |
| 3 | Parameter | varies | Effect-specific (often 0) |
| 4 | Checksum | - | Sum of bytes 0-3 |

**Key Difference**: The 4th byte is a generic "parameter", NOT brightness like in addressable LED devices.

### Android Source

- tc/d.java method `d()` at line 37:
  ```java
  public static byte[] d(int i10, int i11, int i12) {
      byte[] bArr = new byte[5];
      bArr[0] = 56;           // 0x38
      bArr[1] = (byte) i10;   // effect ID
      bArr[2] = (byte) i11;   // speed
      bArr[3] = (byte) i12;   // parameter
      bArr[4] = b.b(bArr, 4); // checksum
      return bArr;
  }
  ```

---

## Simple RGB Devices (0x61 command)

**Device Type**: Basic RGB bulbs without addressable LEDs  
**Effects**: 20 standard effects (IDs 37-56)

### Effect Command (0x61) - 5 bytes with checksum

```python
[0x61, effect_id, speed, persist, checksum]
```

| Byte | Field | Range | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x61 | Fixed |
| 1 | Effect ID | 37-56 | 20 effects |
| 2 | Speed | 0-255 | Normal speed (signed byte in Java) |
| 3 | Persist | 0xF0 or 0x0F | 0xF0=save, 0x0F=don't save |
| 4 | Checksum | - | Sum of bytes 0-3 |

### Android Source

- tc/b.java method `c()` at line 1283:
  ```java
  public static byte[] c(int i10, byte b10, boolean z10) {
      byte[] bArr = new byte[5];
      bArr[0] = 97;           // 0x61
      bArr[1] = (byte) i10;   // effect ID
      bArr[2] = b10;          // speed
      bArr[3] = z10 ? -16 : 15;  // 0xF0 or 0x0F persist
      bArr[4] = b(bArr, 4);   // checksum
      return bArr;
  }
  ```

---

## Implementation Notes

### Checksum Calculation

For commands that include checksums:

```python
def calculate_checksum(data: bytes) -> int:
    """Calculate checksum - sum of all bytes & 0xFF."""
    return sum(data) & 0xFF
```

The checksum is calculated on the **unwrapped payload** (after removing transport header, before wrapping).

### Speed Inversion (0x54, 0x5B)

Some devices use inverted speed where lower values = faster:

```python
def invert_speed(speed_percent: int) -> int:
    """
    Convert speed percentage (1-100) to inverted byte (0x1F to 0x01).
    100% speed -> 0x01 (fastest)
    1% speed -> 0x1F (slowest)
    """
    return round(0x1F - (speed_percent - 1) * (0x1F - 0x01) / 99)
```

### Effect ID Encoding (0x56)

The 0x56 device uses bit-shifted IDs to distinguish effect types:

```python
# Standard effect 5
effect_id = 5

# Static effect 2 (with colors)
effect_id = 2 << 8  # = 0x0200 = 512

# Music effect 3
effect_id = (3 + 0x32) << 8  # = 0x3500 = 13568

# Before building command, extract original ID:
if effect_id & 0xFF00:  # Shifted ID
    original_id = effect_id >> 8
    if original_id >= 0x33:  # Music effect
        music_id = original_id - 0x32
```

---

## Testing Each Device Type

When testing, verify:

1. **Packet length** matches expected format
2. **Checksum presence/absence** matches device type
3. **Brightness stays at current level** when setting effect
4. **Speed changes** affect animation speed
5. **Device doesn't turn off** unexpectedly

Use packet capture to verify raw bytes sent to device match format above.
