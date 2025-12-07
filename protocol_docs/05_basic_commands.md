# Basic Control Commands

All commands include a checksum byte as the last byte: `checksum = sum(data) & 0xFF`

---

## RGB Color Command (0x31)

### Standard 9-Byte Format

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x31 |
| 1-3 | R, G, B | 0-255 each |
| 4-5 | WW, CW | 0-255 each |
| 6 | Mode | 0x5A=RGBCW, 0xF0=RGB, 0x0F=White |
| 7 | Persist | 0xF0=save, 0x0F=temp |
| 8 | Checksum | Sum of bytes 0-7 |

```python
def set_rgbcw(r, g, b, ww=0, cw=0, persist=False):
    cmd = bytearray([0x31, r&0xFF, g&0xFF, b&0xFF, ww&0xFF, cw&0xFF,
                     0x5A, 0xF0 if persist else 0x0F])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

### Format Variants by Product ID

| Product IDs | Method | Format |
|-------------|--------|--------|
| 37, R0() devices | tc.b.t() | 9-byte: `[0x31, R,G,B, WW,CW, 0xF0, persist, chk]` |
| 51, 8, 4, 161 | tc.b.v() | 8-byte: `[0x31, R,G,B, W, 0x00, persist, chk]` |
| 68, 84, 6, 72 | tc.b.x() | 8-byte: `[0x31, R,G,B, W, mode, persist, chk]` |
| BLE v5+ | tc.d.a() | Use 0x3B command (see below) |

### Mode Byte Values

| Value | Mode | Description |
|-------|------|-------------|
| 0x5A | RGBCW | All channels active |
| 0xF0 | RGB only | RGB mode, whites ignored |
| 0x0F | White only | White mode, RGB ignored |

---

## CCT Temperature Command (0x35)

For CCT-only devices using color temperature control.

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x35 |
| 1 | Sub-command | 0xB1 |
| 2 | Temperature % | 0-100 (0=warm, 100=cool) |
| 3 | Brightness % | 0-100 |
| 4-5 | Reserved | 0x00, 0x00 |
| 6-7 | Duration | Big-endian, value × 10 = deciseconds |
| 8 | Checksum | Sum of bytes 0-7 |

```python
def set_cct(temp_pct: int, bright_pct: int, duration_sec: float = 0.3) -> bytes:
    duration = int(duration_sec * 10)
    cmd = bytearray([0x35, 0xB1, temp_pct & 0xFF, bright_pct & 0xFF,
                     0x00, 0x00, (duration >> 8) & 0xFF, duration & 0xFF])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

---

## Brightness Command (0x47) - Legacy

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x47 |
| 1 | Brightness | 0-255 |
| 2 | Checksum | Sum of bytes 0-1 |

---

## Brightness Command (0x3B Mode 0x01) - Firmware v9+

Standalone brightness control for modern devices. Adjusts brightness independent of current mode.

**Source**: `wifi_dp_cmd.json`, `ble_dp_cmd.json` - function `bright_value_v2`

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x3B |
| 1 | Mode | 0x01 |
| 2-3 | Reserved | 0x00, 0x00 |
| 4 | Brightness | 0-100 (percent) |
| 5 | Reserved | 0x00 |
| 6 | Brightness | 0-100 (repeated) |
| 7-9 | Delay | Big-endian 24-bit (ms) |
| 10-11 | Gradient | Big-endian 16-bit |
| 12 | Checksum | Sum of bytes 0-11 |

```python
def build_brightness_v2(brightness: int, delay: int = 0, gradient: int = 0) -> bytes:
    """Build standalone brightness command for firmware v9+ devices."""
    brightness = max(0, min(100, brightness))
    cmd = bytearray([
        0x3B, 0x01, 0x00, 0x00,
        brightness & 0xFF, 0x00, brightness & 0xFF,
        (delay >> 16) & 0xFF, (delay >> 8) & 0xFF, delay & 0xFF,
        (gradient >> 8) & 0xFF, gradient & 0xFF
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

---

## Power Commands

### Modern Power (0x3B) - BLE v5+

**Recommended for most devices.**

PowerType values:
- `0x23` = Power ON
- `0x24` = Power OFF
- `0x25` = Toggle

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x3B |
| 1 | PowerType | 0x23/0x24/0x25 |
| 2-6 | Zeros | 0x00 × 5 |
| 7-9 | Duration | 0x00, 0x00, 0x32 (50ms) |
| 10-11 | Zeros | 0x00 × 2 |
| 12 | Checksum | Sum of bytes 0-11 |

### Legacy Power (0x71) - BLE v1-4

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x71 |
| 1 | State | 0x23=ON, 0x24=OFF |
| 2 | Persist | 0xF0=save, 0x0F=temp |
| 3 | Checksum | Sum of bytes 0-2 |

Examples:
- Power ON: `[0x71, 0x23, 0x0F, 0xA3]`
- Power OFF: `[0x71, 0x24, 0x0F, 0xA4]`

### Very Old Power (0x11)

| Byte | Field | Value |
|------|-------|-------|
| 0-2 | Header | 0x11, 0x1A, 0x1B |
| 3 | State | 0xF0=ON, 0x0F=OFF |
| 4 | Checksum | Sum of bytes 0-3 |

---

## HSV/Symphony Color Command (0x3B)

For BLE v5+ / Symphony devices. Uses HSV color space.

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x3B |
| 1 | Mode | 0xA1=color, 0xB1=CCT, 0x23/0x24=power |
| 2-3 | Hue+Sat packed | `(hue << 7) \| sat` as big-endian |
| 4 | Brightness | 0-100 |
| 5-6 | Params | Mode-specific |
| 7-9 | RGB | Redundant RGB values |
| 10-11 | Time | Duration (use 0x00, 0x00 for instant!) |
| 12 | Checksum | Sum of bytes 0-11 |

### HSV Encoding

```python
# Encode
packed = (hue << 7) | saturation  # hue: 0-360, sat: 0-100
byte_hi = (packed >> 8) & 0xFF
byte_lo = packed & 0xFF

# Decode
packed = (byte_hi << 8) | byte_lo
hue = packed >> 7
saturation = packed & 0x7F
```

### Mode Values

| Mode | Purpose |
|------|---------|
| 0x23 | Power ON |
| 0x24 | Power OFF |
| 0xA1 | Solid Color (HSV) |
| 0xB1 | CCT Temperature |

### Time Field (CRITICAL!)

**Use `0x00, 0x00` for instant response!**

Non-zero values cause delays (interpreted as seconds):
- `0x00, 0x1E` = ~30 second delay
- `0x00, 0x32` = ~50 second delay

---

## CCT via 0x3B (Mode 0xB1)

Alternative CCT command for Symphony/Ring Light devices.

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0x3B |
| 1 | Mode | 0xB1 |
| 2-4 | Zeros | 0x00 × 3 |
| 5 | Temperature % | 0-100 |
| 6 | Brightness % | 0-100 |
| 7-9 | Zeros | 0x00 × 3 |
| 10-11 | Time | 0x00, 0x00 for instant |
| 12 | Checksum | Sum of bytes 0-11 |

```python
def build_cct_0x3B(temp_pct: int, bright_pct: int) -> bytes:
    cmd = bytearray([0x3B, 0xB1, 0x00, 0x00, 0x00,
                     temp_pct & 0xFF, bright_pct & 0xFF,
                     0x00, 0x00, 0x00, 0x00, 0x00])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

---

## Segment Color Command (0xA0)

For setting individual segment colors on addressable LED strips.

| Byte | Field | Value |
|------|-------|-------|
| 0 | Command | 0xA0 |
| 1 | Reserved | 0x00 |
| 2 | Segment count | N |
| 3+ | Segment data | 8 bytes per segment |
| last | Checksum | Sum of all previous |

Per-segment data (8 bytes):
```
[0x00, segment_num, R, G, B, 0x00, 0x00, 0xFF]
```

---

**For effect commands, see [06_effect_commands.md](06_effect_commands.md)**
