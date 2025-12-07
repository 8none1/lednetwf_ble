# Device Configuration (Color Order & LED Count)

**Last Updated**: 6 December 2025
**Status**: Research complete, ready for implementation
**Purpose**: Document how to query and set color order and LED count for simple RGB devices

---

## Overview

Some devices allow configuring hardware settings like **color order** (RGB wiring sequence) and **LED count** (number of LEDs in the strip).

| Feature | Command | Storage |
|---------|---------|---------|
| **Color Order** | 0x62 | State byte 4 upper nibble |
| **LED Count** | 0x66 | State bytes 11-12 |

**Devices that support these settings**:
- **0x33** (Ctrl_Mini_RGB)
- **0x08** (Ctrl_Mini_RGB_Mic)
- **0x06** (Ctrl_Mini_RGBW)
- **0x48** (Ctrl_Mini_RGBW_Mic)
- **0x07** (Ctrl_Mini_RGBCW)

**Note**: Symphony devices (0xA1-0xAD) have their own IC configuration system with both settings via 0x63 query (see doc 16).

---

## App UI vs Protocol Capabilities

The Android app uses firmware version checks to decide which **UI** to display:

| Product ID | Device | App shows Color Order | App shows LED Count |
|------------|--------|----------------------|---------------------|
| 0x33 (51) | Ctrl_Mini_RGB | fw 8-10 | fw >= 11 |
| 0x08 (8) | Ctrl_Mini_RGB_Mic | All versions | Never |
| 0x06 (6) | Ctrl_Mini_RGBW | fw < 4 | fw >= 4 |
| 0x48 (72) | Ctrl_Mini_RGBW_Mic | fw < 4 | fw >= 4 |
| 0x07 (7) | Ctrl_Mini_RGBCW | fw < 3 | fw >= 3 |

**Important**: These firmware checks control which **UI the app shows**, not necessarily which commands the device accepts. Both commands (0x62 and 0x66) may work regardless of firmware version - this needs testing to confirm.

---

# Query Commands by Device Type

Different device types use different query commands to retrieve current settings. This section documents which query to send to each device type.

## Summary Table

| Device Type | Query Command | Response Contains |
|-------------|--------------|-------------------|
| Simple RGB (0x33, 0x08) | 0x81 State Query | color_order (byte 4), led_count (bytes 11-12) |
| Simple RGBW (0x06, 0x48) | 0x81 State Query | color_order (byte 4), led_count (bytes 11-12) |
| Simple RGBCW (0x07) | 0x81 State Query | color_order (byte 4), led_count (bytes 11-12) |
| Ring Light (0x53) | 0x63 IC Settings | led_count, chip_type, color_order |
| Strip Light (0x56) | 0x63 IC Settings | led_count, segments, chip_type, color_order |
| Strip Light (0x5B) | 0x22 Device Query | Varies by mode |
| Symphony (0xA1-0xAD) | 0x63 IC Settings | led_count, segments, ic_type, color_order, music settings |
| IOTBT (0x80) | 0xEA 0x81 (fw>=11) or 0x81 (fw<11) | power, brightness, mode, effect_id, speed |

---

## Query Command: 0x81 (State Query)

**Used by**: Simple devices (0x33, 0x06, 0x07, 0x08, 0x48) and as a universal state query.

**Source**: `tc/b.java:l()`, `ok/a.java:b()` (surplife)

### Command Format (4 bytes)

```
[0x81] [0x8A] [0x8B] [checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x81 (129) | State query opcode |
| 1 | 0x8A (138) | Fixed |
| 2 | 0x8B (139) | Fixed |
| 3 | checksum | Sum of bytes 0-2, & 0xFF = 0x40 |

### Wrapped for BLE Transport

```
00 00 80 00 00 04 05 09 81 8A 8B 40
```

### Response Format (14 bytes)

```
[0x81] [power] [mode] [sub_mode] [color_byte] [R] [G] [B] [W] [CW] [speed] [led_hi] [led_lo] [checksum]
```

| Byte | Field | Description |
|------|-------|-------------|
| 0 | 0x81 | Response identifier |
| 1 | Power | 0x23 = ON, 0x24 = OFF |
| 2 | Mode | Current mode type |
| 3 | Sub mode | Effect ID |
| 4 | **Color byte** | Upper nibble = color order, Lower nibble = IC type |
| 5-7 | RGB | Current color values (0-255 each) |
| 8 | White/WW | Warm white (0-255) |
| 9 | CW | Cool white (0-255) |
| 10 | Speed | Effect speed |
| 11-12 | **LED count** | Big-endian uint16 |
| 13 | Checksum | Sum of bytes 0-12, & 0xFF |

---

## Query Command: 0x63 (IC Settings Query)

**Used by**: IC-enabled devices (0x53, 0x56, 0xA1-0xAD Symphony)

**Source**: `tc/b.java:f0(boolean)`

### Command Format (5 bytes)

```
[0x63] [0x12] [0x21] [terminator] [checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x63 (99) | IC settings query opcode |
| 1 | 0x12 (18) | Fixed |
| 2 | 0x21 (33) | Fixed |
| 3 | 0xF0 or 0x0F | Terminator (0xF0 for BLE, 0x0F for WiFi) |
| 4 | checksum | Sum of bytes 0-3, & 0xFF |

### Wrapped for BLE Transport (0x63)

```
00 02 80 00 00 05 06 0a 63 12 21 f0 86
```

Or with 0x0F terminator:

```
00 05 80 00 00 05 06 0a 63 12 21 0f a5
```

### Response Format - Ring Light (0x53) and FillLight (0x1D)

**10-byte response** (same structure as Symphony):

| Byte | Field | Description |
|------|-------|-------------|
| 0 | 0x63 | Response identifier |
| 1 | 0x00 | Reserved/unused |
| 2 | **LED count** | Number of LEDs (single byte, NOT 16-bit!) |
| 3 | 0x00 | Reserved/unused |
| 4 | **Segments** | Number of segments (single byte) |
| 5 | **IC Type** | Chip type (see IC Type table below) |
| 6 | **Color Order** | RGB ordering (0-5: RGB, RBG, GRB, GBR, BRG, BGR) |
| 7 | Music LED count | LED count for music mode |
| 8 | Music segments | Segments for music mode |
| 9 | Checksum | Sum of bytes 0-8, & 0xFF |

**IC Type Values** (confirmed via device testing):

| Value | IC Type | Notes |
|-------|---------|-------|
| 0 | SM16703 | |
| 1 | WS2812B | Confirmed via 0xA3 device testing |
| 2 | SM16716 | |
| 3 | SK6812 | |
| 4 | INK1003 | |
| 5 | WS2811 | |
| 6 | WS2801 | |
| 7 | WS2815 | |
| 8 | SK6812_RGBW | RGBW variant |
| 9 | TM1914 | |
| 10 | UCS1903 | |
| 11 | UCS2904B | |

**Example response** (with status prefix):
```
0x00 0x63 0x00 0x1E 0x00 0x0A 0x01 0x00 0x1E 0x0A 0xB4
 │    │    │    │    │    │    │    │    │    │    └── Checksum
 │    │    │    │    │    │    │    │    │    └─────── Music segments (10)
 │    │    │    │    │    │    │    │    └──────────── Music LED count (30)
 │    │    │    │    │    │    │    └───────────────── Color order (0 = RGB)
 │    │    │    │    │    │    └────────────────────── IC Type (1 = WS2812B)
 │    │    │    │    │    └─────────────────────────── Segments (10)
 │    │    │    │    └──────────────────────────────── Reserved (0)
 │    │    │    └───────────────────────────────────── LED count (30)
 │    │    └────────────────────────────────────────── Reserved (0)
 │    └─────────────────────────────────────────────── 0x63 header
 └──────────────────────────────────────────────────── Status prefix (strip this!)
```

**CRITICAL**: The old `model_0x53.py` code used wrong offsets:
- It parsed IC type from [3] → got 0x00 (wrong, should be [5])
- It parsed color order from [4] → got 0x0A=10 (invalid! should be [6])

### Response Format - Strip Light (0x56)

**Parsing from `model_0x56.py:476-482`**

| Byte | Field | Description |
|------|-------|-------------|
| 0 | Status | 0x00 = success (see analysis below) |
| 1 | 0x63 | Response identifier |
| 2-3 | **LED per segment** | Big-endian uint16 |
| 4 | ? | Reserved |
| 5 | **Segments** | Number of segments |
| 6 | **Chip type** | IC chip type |
| 7 | **Color order** | RGB ordering (0-5) |

**Note**: Total LED count = (bytes 2-3) * segments

### Response Identifier Position Varies

**Important**: The 0x63 identifier position differs by device type:

| Device | 0x63 Position | Byte 0 Contains |
|--------|---------------|-----------------|
| 0x53 (Ring Light) | Byte 0 | 0x63 (response ID) |
| 0x56 (Strip Light) | Byte 1 | Status byte (0x00 = success) |
| Symphony (0xA1+) | N/A | Direction (0 or 1) - no 0x63 in response |

### Response Format - Symphony (0xA1-0xAD)

**Parsing from `SymphonySettingForA3.java:132-144`**

| Byte | Field | Description |
|------|-------|-------------|
| 0 | Direction | 0 or 1 (effect direction) |
| 1 | ? | Reserved |
| 2-3 | **LED count** | Little-endian uint16 |
| 4-5 | **Segments** | Little-endian uint16 |
| 6 | **IC type** | IC configuration type (0-9+) |
| 7 | **Color order** | RGB ordering (0-5) |
| 8 | Music point | Music mode LED point |
| 9 | Music part | Music mode part setting |

---

## Query Command: 0x22 (Device Query)

**Used by**: Some strip lights (0x5B)

**Source**: Old integration `model_0x5b.py`

### Wrapped Command

```
00 05 80 00 00 02 03 07 22 22
```

**Note**: This appears to be a simpler device query. Response format varies.

---

## Query Command: 0xEA (IOTBT State Query)

**Used by**: IOTBT devices (0x80)

**Source**: `ok/a.java`, `zk/f.java`, `DeviceState2.java` (surplife)

### IOTBT Protocol Overview

IOTBT devices use a different protocol based on **Telink BLE Mesh** opcodes. The Android app distinguishes between older firmware (< 11) which uses the legacy 0x81 query, and newer firmware (>= 11) which uses the 0xEA query wrapped in a special transport layer.

### Transport Layer (zk/f.java)

IOTBT devices use a different transport wrapper than other LEDnetWF devices:

**Header**: `{0xB0, 0xB1, 0xB2, 0xB3, 0x00, type}`

| Byte | Value | Description |
|------|-------|-------------|
| 0-3 | B0 B1 B2 B3 | Magic header |
| 4 | 0x00 | Reserved |
| 5 | type | 0x01 or 0x02 (transport type) |
| 6 | sequence | Incrementing sequence number |
| 7 | 0x?? | Unknown |
| 8-9 | length | Payload length (big-endian) |
| 10+ | payload | Raw command bytes |
| last | checksum | Sum of bytes 0-(n-1) & 0xFF |

### Raw Query Command (ok/a.java)

**Legacy (firmware < 11)** - `ok.a.b()`:

```
[0x81] [0x8A] [0x8B] [checksum=0x40]
```

**IOTBT (firmware >= 11)** - `ok.a.c()`:

```
[0xEA] [0x81] [0x8A] [0x8B]
```

Note: The IOTBT query `0xEA 0x81 0x8A 0x8B` has no internal checksum - it's wrapped with the transport layer which provides the checksum.

### Response Formats - 0xEA 0x81 vs 0x81

**CRITICAL**: IOTBT devices can return **two different response formats** depending on the query used. Do NOT simply strip 0xEA - it's part of a different response format!

#### Detecting Response Type

```python
def detect_iotbt_response_type(data: bytes) -> str:
    """Detect IOTBT response format from magic header."""
    if len(data) >= 2 and data[0] == 0xEA and data[1] == 0x81:
        return "DeviceState2"  # New format (fw >= 11)
    elif len(data) >= 1 and data[0] == 0x81:
        return "DeviceState"   # Legacy format (fw < 11)
    else:
        return "unknown"
```

#### DeviceState2 Format (0xEA 0x81 response)

**Source**: `com/zengge/wifi/Device/DeviceState2.java`

| Byte | Field | Description |
|------|-------|-------------|
| 0 | **0xEA** | Magic byte 1 (Telink "user all" opcode) |
| 1 | **0x81** | Magic byte 2 (state query marker) |
| 2 | ? | Reserved/unknown |
| 3-4 | Address | Device mesh address (big-endian, & 0x7FFF) |
| 5 | Mode | Current mode/brightness |
| 6 | Power | 0x23 = ON, others = OFF |

#### DeviceState Format (0x81 response)

**Source**: `tc/b.java:c()` (standard response parser)

| Byte | Field | Description |
|------|-------|-------------|
| 0 | **0x81** | Response identifier |
| 1 | Power | 0x23 = ON, 0x24 = OFF |
| 2 | Mode | Current mode type |
| ... | ... | (see standard 0x81 response format above) |

**Key Points**:
1. **Do NOT strip 0xEA** - it identifies the response format
2. **Byte offsets differ** between DeviceState and DeviceState2
3. Use firmware version to choose query format (>=11 uses 0xEA 0x81)
4. Check magic header to determine parsing strategy

---

## IOTBT Command Reference

### Power Command (0x71)

```
00 00 80 00 00 02 03 0a 71 23  (ON)
00 00 80 00 00 02 03 0a 71 24  (OFF)
```

### Color Command (0xE2)

```
00 00 80 00 00 04 05 0a e2 0b cc bb
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0xE2 | Color opcode |
| 1 | 0x0B | Sub-command |
| 2 | cc | Quantized hue (1-240, 0=white) |
| 3 | bb | Brightness (0xE0 OR level, level=0-31) |

### Effect Command (0xE0 0x02)

```
00 00 80 00 00 06 07 0a e0 02 ff ss bb
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0xE0 | Effect opcode |
| 1 | 0x02 | Sub-command (effect mode) |
| 2 | ff | Effect ID (1-12) |
| 3 | ss | Speed (1-100) |
| 4 | bb | Brightness percent (1-100) |

---

## Telink BLE Mesh Opcode Reference

From `com/telink/bluetooth/light/Opcode.java`:

| Opcode | Byte | Description |
|--------|------|-------------|
| E0 | 0xE0 | Set device address |
| E1 | 0xE1 | Notify device address info |
| E2 | 0xE2 | Configure RGB value |
| E3 | 0xE3 | Kick out / reset factory |
| E4 | 0xE4 | Set device time |
| EA | 0xEA | User all (generic query) |
| EB | 0xEB | User all notify |

---

# Part 1: Color Order Settings

## Color Order Values by Device Type

### RGB Devices (0x33, 0x08)

| Value | Order | Description |
|-------|-------|-------------|
| 1 | RGB | Red, Green, Blue (standard) |
| 2 | GRB | Green, Red, Blue (common for WS2812B) |
| 3 | BRG | Blue, Red, Green |

### RGBW Devices (0x06, 0x48)

| Value | Order | Description |
|-------|-------|-------------|
| 1 | RGBW | Red, Green, Blue, White |
| 2 | GRBW | Green, Red, Blue, White |
| 3 | BRGW | Blue, Red, Green, White |

### RGBCW Devices (0x07)

| Value | Order | Value | Order |
|-------|-------|-------|-------|
| 1 | RGBCW | 9 | WBRGC |
| 2 | GRBCW | 10 | CRGBW |
| 3 | BRGCW | 11 | CGRBW |
| 4 | RGBWC | 12 | CBRGW |
| 5 | GRBWC | 13 | WCRGB |
| 6 | BRGWC | 14 | WCGRB |
| 7 | WRGBC | 15 | WCBRG |
| 8 | WGRBC | | |

---

## Set Color Order

### Command: 0x62 (Wiring Setting)

**Source**: `n.java:243-248`

```
[0x62] [ic_type] [color_order] [0x0F] [checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x62 | Wiring setting opcode |
| 1 | ic_type | IC type (0 or 1 for simple devices) |
| 2 | color_order | 1=RGB, 2=GRB, 3=BRG (or 1-15 for RGBCW) |
| 3 | 0x0F | Terminator |
| 4 | checksum | Sum of bytes 0-3, masked with 0xFF |

---

# Part 2: LED Count Settings

## Set LED Count

### Command: 0x66 (LED/Bead Count)

**Source**: `tc/b.java:Y(int i10)`

```
[0x66] [count_high] [count_low]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x66 | LED count opcode |
| 1 | count_high | High byte of count (big-endian) |
| 2 | count_low | Low byte of count |

**Note**: This command has NO checksum (only 3 bytes).

### Query LED Count

LED count is returned in the 0x81 state response at bytes 11-12 (big-endian).

---

## Source Files Reference

| File | Purpose |
|------|---------|
| `tc/b.java:l()` | State query command builder (0x81) |
| `tc/b.java:Y(int)` | LED count command builder (0x66) |
| `tc/b.java:c()` | State response parser |
| `n.java:243-248` | Color order command builder (0x62) |
| `Ctrl_Mini_RGB_0x33.java` | Device-specific feature checks |

---

## Related Documentation

- **BLE Advertisement Parsing**: See [02_manufacturer_data.md](02_manufacturer_data.md) for all advertisement formats (ZengGe, Telink, Service Data)
- **Sound Reactive / Built-in Mic**: See [18_sound_reactive_music_mode.md](18_sound_reactive_music_mode.md) for device mic detection and commands
- **Query Formats (Symphony)**: See [16_query_formats_0x63_vs_0x44.md](16_query_formats_0x63_vs_0x44.md) for 0x63/0x44 Symphony queries
