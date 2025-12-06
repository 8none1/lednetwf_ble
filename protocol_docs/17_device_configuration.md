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

**Analysis from code**:

1. **0x81 responses are consistent** - Both 0x53 and 0x56 check `payload[0] == 0x81` for state query responses
2. **0x63 responses differ** - Only the IC settings query shows this prefix difference
3. **Transport layer evidence** - The Android app's transport layer (`LowerTransportLayerDecoder.java`) extracts cmdId separately from payload, suggesting the response structure varies by command type

**For 0x56 devices**, byte 0 is a **status/result code**:

- **0x00** = Success (IC settings returned)
- Other values may indicate errors (no error codes observed in sources)

This pattern matches the transport layer design where result codes precede payload data. The Java source `tc/b.java:g()` checks `bArr[0] == 0x63` because it receives pre-processed data from devices that don't include the status prefix, while 0x56 devices include it in their JSON-wrapped responses.

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

### Captured Packet Examples (from old integration)

**State query (0x44 format)**:

```
00 14 80 00 00 05 06 0a 44 4a 4b 0f e8
```

Command bytes: `[0x44] [0x4A] [0x4B] [0x0F] [checksum=0xE8]`

**LED settings query (0xEA format)**:

```
00 04 80 00 00 02 03 0a ea 81
```

Command bytes: `[0xEA] [0x81]`

**Device settings query (0xE0 format)**:

```
00 08 80 00 00 03 04 0a e0 0e 01
```

Command bytes: `[0xE0] [0x0E] [0x01]`

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

This format is returned when you send the `0xEA 0x81 0x8A 0x8B` query (firmware >= 11):

| Byte | Field | Description |
|------|-------|-------------|
| 0 | **0xEA** | Magic byte 1 (Telink "user all" opcode) |
| 1 | **0x81** | Magic byte 2 (state query marker) |
| 2 | ? | Reserved/unknown |
| 3-4 | Address | Device mesh address (big-endian, & 0x7FFF) |
| 5 | Mode | Current mode/brightness |
| 6 | Power | 0x23 = ON, others = OFF |

**Parsing code from DeviceState2.java**:
```java
// Magic header check
public static final byte[] MAGIC = {(byte)0xEA, (byte)0x81};
public static boolean isDeviceState2(byte[] data) {
    return Arrays.equals(MAGIC, new byte[]{data[0], data[1]});
}

// Constructor parses at DIFFERENT offsets than DeviceState
public DeviceState2(byte[] bArr) {
    // Address at bytes 3-4 (big-endian, masked)
    setAddress(((bArr[3] << 8) & 0xFF00) | (bArr[4] & 0xFF)) & 0x7FFF);

    // Power at byte 6 (NOT byte 1 like in standard 0x81)
    setPowerOn(bArr[6] == 0x23);

    // Mode at byte 5
    setMode(bArr[5] & 0xFF);
}
```

#### DeviceState Format (0x81 response)

**Source**: `tc/b.java:c()` (standard response parser)

This format is returned when you send the legacy `0x81 0x8A 0x8B [checksum]` query:

| Byte | Field | Description |
|------|-------|-------------|
| 0 | **0x81** | Response identifier |
| 1 | Power | 0x23 = ON, 0x24 = OFF |
| 2 | Mode | Current mode type |
| ... | ... | (see standard 0x81 response format above) |

#### Implementation Recommendation

```python
def parse_iotbt_state_response(data: bytes) -> dict:
    """Parse IOTBT state response, handling both formats."""
    if len(data) < 2:
        return None

    # Check for DeviceState2 format (0xEA 0x81 magic header)
    if data[0] == 0xEA and data[1] == 0x81:
        # DeviceState2 format - different byte positions!
        if len(data) < 7:
            return None
        return {
            "format": "DeviceState2",
            "address": ((data[3] << 8) | data[4]) & 0x7FFF,
            "mode": data[5] & 0xFF,
            "power_on": data[6] == 0x23,
        }

    # Standard 0x81 format
    elif data[0] == 0x81:
        return {
            "format": "DeviceState",
            "power_on": data[1] == 0x23,
            "mode": data[2] if len(data) > 2 else 0,
            # ... parse remaining fields as standard
        }

    return None
```

**Key Points**:
1. **Do NOT strip 0xEA** - it identifies the response format
2. **Byte offsets differ** between DeviceState and DeviceState2
3. Use firmware version to choose query format (>=11 uses 0xEA 0x81)
4. Check magic header to determine parsing strategy

### Status Response (from notification_handler)

Status notifications have `data[0] == 0x04`:

| Byte | Field | Description |
|------|-------|-------------|
| 0 | 0x04 | Status response marker |
| ... | | (padding) |
| 14 | Power | 0x23 = ON, 0x24 = OFF |
| 15 | Mode | Mode type (see below) |
| 16 | Effect ID | Effect number |
| 17 | Speed | Effect speed |

**Mode Types (byte 15)**:

| Value | Mode | Notes |
|-------|------|-------|
| 0x62 | Music reactive | effect_id = byte[16] << 8 |
| 0x66 | Static color | No effect active |
| 0x67 | Effect mode | effect_id = byte[16] |

---

## IOTBT Command Reference

### Power Command (0x71)

**Wrapped packet**:

```
00 00 80 00 00 02 03 0a 71 23  (ON)
00 00 80 00 00 02 03 0a 71 24  (OFF)
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x71 | Power opcode |
| 1 | 0x23/0x24 | 0x23 = ON, 0x24 = OFF |

### Color Command (0xE2)

**Wrapped packet**:

```
00 00 80 00 00 04 05 0a e2 0b cc bb
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0xE2 | Color opcode |
| 1 | 0x0B | Sub-command |
| 2 | cc | Quantized hue (1-240, 0=white) |
| 3 | bb | Brightness (0xE0 OR level, level=0-31) |

**Hue Quantization**:

- Hue is mapped to 240 values (1-240)
- Value 0 is reserved for white
- Red maps to ~1, proceeding through the color wheel

**Brightness Encoding**:

- 5-bit value (0-31) with gamma correction
- Upper bits set to 0xE0 (0b11100000 OR level)

### Effect Command (0xE0 0x02)

**Wrapped packet**:

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

### Music Mode Command (0xE1 0x05)

**Wrapped packet** (54 bytes total):

```
00 e2 80 00 00 36 37 0a e1 05 01 64 08 00 00 64 ...
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0xE1 | Music mode opcode |
| 1 | 0x05 | Sub-command |
| 2 | 0x01 | Enable |
| 3 | brightness | Brightness percent |
| 4 | effect_id | Music effect (1-13, excluding 5,6,9,10,11) |
| 7 | sensitivity | Mic sensitivity (1-100) |
| ... | | Color palette data |

---

## Telink BLE Mesh Opcode Reference

From `com/telink/bluetooth/light/Opcode.java`:

| Opcode | Byte | Description |
|--------|------|-------------|
| E0 | 0xE0 (-32) | Set device address |
| E1 | 0xE1 (-31) | Notify device address info |
| E2 | 0xE2 (-30) | Configure RGB value |
| E3 | 0xE3 (-29) | Kick out / reset factory |
| E4 | 0xE4 (-28) | Set device time |
| EA | 0xEA (-22) | User all (generic query) |
| EB | 0xEB (-21) | User all notify |

These opcodes are part of the Telink BLE Mesh protocol used by IOTBT devices.

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

**Legend**: R=Red, G=Green, B=Blue, W=Warm White, C=Cool White

---

## Query Current Color Order

### Command: State Query (0x81)

**Source**: `tc/b.java:l()`

```
[0x81] [0x8A] [0x8B] [checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x81 | State query opcode |
| 1 | 0x8A | Fixed |
| 2 | 0x8B | Fixed |
| 3 | checksum | Sum of bytes 0-2, masked with 0xFF |

### Response Format (0x81)

**Source**: `tc/b.java:c()` (lines 46-68)

```
[0x81] [power] [mode] [sub_mode] [color_byte] [R] [G] [B] [W] [CW] [speed] [led_hi] [led_lo] [checksum]
```

| Byte | Field | Description |
|------|-------|-------------|
| 0 | Response ID | 0x81 |
| 1 | Power state | 0x23 (35) = ON, 0x24 (36) = OFF |
| 2 | Mode type | Current mode |
| 3 | Sub mode | Effect ID or mode variant |
| 4 | **Color byte** | Contains color order + IC type |
| 5 | Red | 0-255 |
| 6 | Green | 0-255 |
| 7 | Blue | 0-255 |
| 8 | White | 0-255 (for RGBW devices) |
| 9 | Cool White | 0-255 (for RGBCW devices) |
| 10 | Speed | Effect speed |
| 11 | **LED count high** | High byte of LED count (big-endian) |
| 12 | **LED count low** | Low byte of LED count |
| 13 | Checksum | Sum of bytes 0-12, masked with 0xFF |

### Extracting Color Order from Byte 4

For **0x33, 0x06, 0x07, 0x48** devices, the color byte encodes:
- **Upper nibble (bits 4-7)**: Color order (1-3 or 1-15)
- **Lower nibble (bits 0-3)**: IC type (for some devices)

```python
def extract_color_order(color_byte: int) -> int:
    """Extract color order from state response byte 4."""
    return (color_byte & 0xF0) >> 4  # Upper nibble

def extract_ic_type(color_byte: int) -> int:
    """Extract IC type from state response byte 4."""
    return color_byte & 0x0F  # Lower nibble

# Example:
# color_byte = 0x21 -> color_order = 2 (GRB), ic_type = 1
# color_byte = 0x10 -> color_order = 1 (RGB), ic_type = 0
```

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

LED count is returned in the 0x81 state response at bytes 11-12 (big-endian):

```python
def extract_led_count(state_response: bytes) -> int:
    """Extract LED count from 0x81 state response."""
    if len(state_response) < 13:
        return 0
    return (state_response[11] << 8) | state_response[12]
```

### Valid Range

- **Minimum**: 1 LED
- **Maximum**: 65535 LEDs (16-bit value)
- **UI limit**: App typically limits to 150 LEDs in the slider

---

# Part 3: Python Implementation

```python
# Color order options by device type
COLOR_ORDERS = {
    # RGB devices (0x33, 0x08)
    0x33: {1: "RGB", 2: "GRB", 3: "BRG"},
    0x08: {1: "RGB", 2: "GRB", 3: "BRG"},

    # RGBW devices (0x06, 0x48)
    0x06: {1: "RGBW", 2: "GRBW", 3: "BRGW"},
    0x48: {1: "RGBW", 2: "GRBW", 3: "BRGW"},

    # RGBCW devices (0x07)
    0x07: {
        1: "RGBCW", 2: "GRBCW", 3: "BRGCW",
        4: "RGBWC", 5: "GRBWC", 6: "BRGWC",
        7: "WRGBC", 8: "WGRBC", 9: "WBRGC",
        10: "CRGBW", 11: "CGRBW", 12: "CBRGW",
        13: "WCRGB", 14: "WCGRB", 15: "WCBRG",
    },
}


def build_color_order_command(color_order: int, ic_type: int = 0) -> bytearray:
    """
    Build command to set color order.

    Args:
        color_order: Color order value (1-3 for RGB/RGBW, 1-15 for RGBCW)
        ic_type: IC type (0 for simple RGB devices)

    Returns:
        5-byte command (needs transport wrapper)
    """
    raw_cmd = bytearray([
        0x62,                      # Command opcode
        ic_type & 0xFF,            # IC type
        color_order & 0xFF,        # Color order
        0x0F,                      # Terminator
    ])
    checksum = sum(raw_cmd) & 0xFF
    raw_cmd.append(checksum)
    return raw_cmd


def build_led_count_command(led_count: int) -> bytearray:
    """
    Build command to set LED count.

    Args:
        led_count: Number of LEDs (1-65535)

    Returns:
        3-byte command (needs transport wrapper), NO checksum
    """
    led_count = max(1, min(65535, led_count))  # Clamp to valid range
    return bytearray([
        0x66,                          # Command opcode
        (led_count >> 8) & 0xFF,       # High byte (big-endian)
        led_count & 0xFF,              # Low byte
    ])


def build_state_query() -> bytearray:
    """Build state query command (0x81 format)."""
    raw_cmd = bytearray([
        0x81,  # State query opcode
        0x8A,  # Fixed
        0x8B,  # Fixed
    ])
    checksum = sum(raw_cmd) & 0xFF
    raw_cmd.append(checksum)
    return raw_cmd


def wrap_command(raw_cmd: bytearray, cmd_family: int = 0x0b) -> bytearray:
    """Wrap raw command in transport layer."""
    length = len(raw_cmd)
    packet = bytearray([
        0x00, 0x00, 0x80, 0x00, 0x00,
        length & 0xFF,
        (length + 1) & 0xFF,
        cmd_family & 0xFF,
    ])
    packet.extend(raw_cmd)
    return packet


def parse_state_response(data: bytes) -> dict:
    """Parse 0x81 state response."""
    if len(data) < 14 or data[0] != 0x81:
        return None

    color_byte = data[4]
    return {
        "power_on": data[1] == 0x23,
        "mode": data[2],
        "sub_mode": data[3],
        "color_order": (color_byte & 0xF0) >> 4,
        "ic_type": color_byte & 0x0F,
        "rgb": (data[5], data[6], data[7]),
        "white": data[8],
        "cool_white": data[9],
        "speed": data[10],
        "led_count": (data[11] << 8) | data[12],
    }


def app_shows_color_order_ui(product_id: int, firmware_version: int) -> bool:
    """Check if the Android app shows color order UI for this device/firmware.

    Note: The actual 0x62 command may work regardless of firmware.
    These checks mirror the Android app's UI logic.
    """
    if product_id == 0x33:  # Ctrl_Mini_RGB
        return 8 <= firmware_version <= 10
    elif product_id == 0x08:  # Ctrl_Mini_RGB_Mic
        return True  # Always shows color order UI
    elif product_id in (0x06, 0x48):  # RGBW devices
        return firmware_version < 4
    elif product_id == 0x07:  # RGBCW
        return firmware_version < 3
    return False


def app_shows_led_count_ui(product_id: int, firmware_version: int) -> bool:
    """Check if the Android app shows LED count UI for this device/firmware.

    Note: The actual 0x66 command may work regardless of firmware.
    These checks mirror the Android app's UI logic.
    """
    if product_id == 0x33:  # Ctrl_Mini_RGB
        return firmware_version >= 11
    elif product_id == 0x08:  # Ctrl_Mini_RGB_Mic
        return False  # Never shows LED count UI
    elif product_id in (0x06, 0x48):  # RGBW devices
        return firmware_version >= 4
    elif product_id == 0x07:  # RGBCW
        return firmware_version >= 3
    return False


def supports_color_order(product_id: int) -> bool:
    """Check if device type supports color order command (0x62).

    For actual support, try the command - this just indicates the device
    type has color order capability.
    """
    return product_id in (0x33, 0x08, 0x06, 0x48, 0x07)


def supports_led_count(product_id: int) -> bool:
    """Check if device type supports LED count command (0x66).

    For actual support, try the command - this just indicates the device
    type has LED count capability. Note: 0x08 may not support this.
    """
    return product_id in (0x33, 0x06, 0x48, 0x07)  # 0x08 excluded


def get_color_order_options(product_id: int) -> dict:
    """Get available color order options for a device."""
    return COLOR_ORDERS.get(product_id, {})


# Example usage:

# Set color order to GRB for older firmware device
raw_cmd = build_color_order_command(color_order=2, ic_type=0)
packet = wrap_command(raw_cmd)
# Send packet via BLE write

# Set LED count to 60 for newer firmware device
raw_cmd = build_led_count_command(led_count=60)
packet = wrap_command(raw_cmd)
# Send packet via BLE write
```

---

## Device-Specific Notes

### 0x33 (Ctrl_Mini_RGB) - Product ID 51

- **Color Orders**: RGB (1), GRB (2), BRG (3)
- **App shows color order UI**: Firmware 8-10
- **App shows LED count UI**: Firmware >= 11
- **State Byte Encoding**: Upper nibble of byte 4
- **Your device**: Firmware 29.0A - app would show LED count UI, but color order command (0x62) may still work

### 0x08 (Ctrl_Mini_RGB_Mic) - Product ID 8

- **Color Orders**: RGB (1), GRB (2), BRG (3)
- **App shows color order UI**: All firmware versions
- **App shows LED count UI**: Never
- **State Byte Encoding**: Upper nibble of byte 4
- Lower nibble may store microphone sensitivity

### 0x06 (Ctrl_Mini_RGBW) - Product ID 6

- **Color Orders**: RGBW (1), GRBW (2), BRGW (3)
- **App shows color order UI**: Firmware < 4
- **App shows LED count UI**: Firmware >= 4
- **State Byte Encoding**: Upper nibble = color order, lower nibble = IC type

### 0x48 (Ctrl_Mini_RGBW_Mic) - Product ID 72

- **Color Orders**: RGBW (1), GRBW (2), BRGW (3)
- **App shows color order UI**: Firmware < 4
- **App shows LED count UI**: Firmware >= 4
- **State Byte Encoding**: Upper nibble = color order, lower nibble = mic mode

### 0x07 (Ctrl_Mini_RGBCW) - Product ID 7

- **Color Orders**: 15 options (see table above)
- **App shows color order UI**: Firmware < 3
- **App shows LED count UI**: Firmware >= 3
- **State Byte Encoding**: Full byte stores color order (values 1-15)
- Most flexible color order options due to 5-channel output

---

## Integration Notes for Home Assistant

### Determining Feature Support

On device connection:
1. Get product ID from manufacturer data
2. Use `supports_color_order()` and `supports_led_count()` to check device type capability
3. Optionally use firmware version to match Android app behavior

### Recommended Approach

For simplicity, you can expose BOTH settings for devices that support them (0x33, 0x06, 0x07, 0x48), regardless of firmware version. Let the user configure what they need.

Alternatively, mirror the Android app behavior using `app_shows_color_order_ui()` and `app_shows_led_count_ui()` to show only the "expected" setting based on firmware.

### Exposing Settings

**Color Order**:
1. Expose as select entity with options: RGB, GRB, BRG (etc.)
2. Parse current value from byte 4 upper nibble of state response
3. Send 0x62 command on selection change

**LED Count**:
1. Expose as number entity with min=1, max=150 (or 65535)
2. Parse current value from bytes 11-12 of state response
3. Send 0x66 command on value change

### State Storage

Both settings persist across power cycles. Query once on connection and update only when changed.

---

## Source Files Reference

| File | Purpose |
|------|---------|
| `tc/b.java:l()` | State query command builder (0x81) |
| `tc/b.java:Y(int)` | LED count command builder (0x66) |
| `tc/b.java:c()` | State response parser |
| `n.java:243-248` | Color order command builder (0x62) |
| `Ctrl_Mini_RGB_0x33.java:c()` | LED count feature check |
| `Ctrl_Mini_RGB_0x33.java:l()` | Color order feature check |
| `Ctrl_Mini_RGB_0x33.java:j0()` | Get color order from state |
| `Ctrl_Mini_RGB_0x33.java:X0()` | Set color order in state |
| `Ctrl_Mini_RGB_0x33.java:p()` | Color order options |
| `ActivityTabForRGB.java:56-62` | LED count UI handler |
| `kd/z0.java` | LED count picker popup |
| `ucPopupWiringSetting.java` | Color order picker popup |

---

## BLE Advertisement Data Formats

Different device families encode state information in BLE advertisements differently. Understanding these formats is essential for detecting power state without connecting.

### Standard ZengGe Format (Company ID 0x5A**)

**Company ID Range**: 23040-23295 (0x5A00-0x5AFF)

**Used by**: Most LEDnetWF devices

**Source**: `com/zengge/hagallbjarkan/device/ZGHBDevice.java`

#### Manufacturer Data (27 bytes)

| Byte | Field | Description |
|------|-------|-------------|
| 0 | sta | Status byte (NOT for device identification) |
| 1 | ble_version | BLE protocol version |
| 2-7 | mac_address | Device MAC address |
| 8-9 | product_id | Product ID (big-endian) |
| 10 | firmware_ver | Firmware version (low byte) |
| 11 | led_version | LED version |
| 12 | check_key_flag | Check key (bits 0-1), firmware high (bits 2-7 for v6+) |
| 13 | firmware_flag | Firmware flag (bits 0-4) |
| **14** | **power** | **Power state: 0x23=ON, 0x24=OFF** |
| 15 | mode_type | Mode type (0x61=color/white, 0x25=effect) |
| 16 | sub_mode | Sub-mode or effect ID |
| 17-24 | state_data | Color/brightness/speed data |
| 25-26 | rfu | Reserved |

#### With Service Data (BLE v7+)

For BLE version >= 7, when both Type 22 (service data) AND Type 255 (manufacturer data) are present:

- **Service Data (16 bytes)**: Product ID, BLE version, MAC (same format as mfr data bytes 0-15)
- **Manufacturer Data**: State data at bytes 3-27 (25 bytes, different offset!)

```python
# BLE v7+ with service data
if ble_version >= 7 and has_service_data:
    state_data = mfr_data[3:28]  # 25 bytes starting at offset 3
    power_state = state_data[11]  # Power at different offset!
```

### Telink Private Mesh Format (Company ID 0x1102)

**Company ID**: 4354 (0x1102)

**Used by**: IOTBT devices, Telink BLE mesh devices

**Source**: `com/telink/bluetooth/light/c.java`

#### Manufacturer Data (~13+ bytes)

Telink devices use a completely different format in manufacturer data:

| Offset | Field | Description |
|--------|-------|-------------|
| 0-1 | manufacturer_id | 4354 (0x1102) for Telink |
| 2-3 | mesh_uuid | Mesh network ID (little-endian) |
| 4-7 | reserved | MAC or reserved bytes |
| 8-9 | product_uuid | Product UUID (little-endian) |
| **10** | **status** | **Power/brightness: non-zero = ON** |
| 11-12 | mesh_address | Device mesh address (little-endian) |

#### Parsing Telink Advertisement

```python
def parse_telink_advertisement(mfr_data: bytes) -> dict | None:
    """Parse Telink BLE Mesh advertisement format.

    Returns None if not a Telink device.
    """
    if len(mfr_data) < 13:
        return None

    # Company ID is first 2 bytes (big-endian in Android parsing)
    company_id = (mfr_data[0] << 8) | mfr_data[1]
    if company_id != 4354:  # 0x1102 - Telink
        return None

    # Parse Telink format
    mesh_uuid = (mfr_data[3] << 8) | mfr_data[2]  # Little-endian
    product_uuid = (mfr_data[9] << 8) | mfr_data[8]  # Little-endian
    status = mfr_data[10] & 0xFF  # Status byte
    mesh_address = (mfr_data[12] << 8) | mfr_data[11]  # Little-endian

    # In Telink format: non-zero status = device is ON
    # Status may also encode brightness level
    power_on = status > 0

    return {
        "format": "telink",
        "mesh_uuid": mesh_uuid,
        "product_uuid": product_uuid,
        "status": status,
        "power_on": power_on,
        "mesh_address": mesh_address,
    }
```

### Service Data Format (BLE v5+)

Service data provides device identification and version information. For BLE v7+ devices, state data is in manufacturer data at a different offset.

**Service UUID**: `0000FFFF-0000-1000-8000-00805f9b34fb` (short: 0xFFFF)

**Source**: `ZGHBDevice.java` lines 134-167, `Service.java` line 7

#### Service Data Layout (16 or 29 bytes)

**Important**: Service data can be **16 bytes** (device ID + version info) OR **29 bytes** (full format with state).

**Source**: `ZGHBDevice.java` line 139: `if (bArr6.length != 16 && bArr6.length != 29)`

##### 16-byte Service Data (Device Identification)

| Byte | Field | Description |
|------|-------|-------------|
| 0 | sta | Status byte (255 = OTA mode) |
| 1 | mfr_hi | Manufacturer prefix (0x5A or 0x5B) |
| 2 | mfr_lo | Manufacturer low byte |
| 3 | ble_version | BLE protocol version (e.g., 5, 6, 7) |
| 4-9 | mac_address | Device MAC address (6 bytes) |
| 10-11 | product_id | Product ID (big-endian) |
| 12 | firmware_ver_lo | Firmware version low byte |
| 13 | led_version | LED/hardware version |
| 14 | check_key + fw_hi | Bits 0-1: check_key_flag, Bits 2-7: firmware_ver high (BLE v6+) |
| 15 | firmware_flag | Firmware feature flags (bits 0-4) |

##### Field Details

**sta (byte 0)**: Device status byte

- `0xFF` (255) = Device is in OTA firmware update mode
- Other values: Normal operation

**ble_version (byte 3)**: BLE protocol version

- Determines which features and command formats the device supports
- v5+: Service data with device ID
- v6+: Extended firmware version (high bits in byte 14)
- v7+: State data at offset 3 in manufacturer data

**firmware_ver (bytes 12 + 14)**: Full firmware version calculation

```python
# For BLE v6+, firmware version spans two bytes:
if ble_version >= 6:
    firmware_ver = byte12 | ((byte14 >> 2) << 8)
else:
    firmware_ver = byte12
# Example: byte12=0x23, byte14=0x08 → fw = 0x23 | (0x02 << 8) = 0x0223 = 547
```

**led_version (byte 13)**: LED/hardware version

- Indicates hardware revision or LED controller type
- Used in combination with product_id for device capability detection

**check_key_flag (byte 14, bits 0-1)**: Key validation flag

- Used during device binding/authentication
- Values: 0-3

**firmware_flag (byte 15, bits 0-4)**: Firmware feature flags

- Bit field indicating supported features
- Device-specific interpretation

##### 29-byte Service Data (Full format with state)

When service data is 29 bytes, it follows the same format as manufacturer data:

| Byte | Field | Description |
|------|-------|-------------|
| 0-15 | Device ID | Same as 16-byte format above |
| **16** | **power** | **Power state: 0x23=ON, 0x24=OFF** |
| 17 | mode_type | Mode type (0x61=color/white, 0x25=effect) |
| 18 | sub_mode | Sub-mode or effect ID |
| 19 | brightness | Brightness % (white mode) |
| 20-22 | rgb | R, G, B values |
| 23 | color_temp | Color temp % (white mode) |
| 24-25 | speed/ww/cw | Effect speed or warm/cool white |
| 26 | ? | Additional state |
| 27-28 | rfu | Reserved |

**Note**: The Android app ALWAYS reads state from manufacturer data, even when 29-byte service data is present. However, for devices that ONLY have service data (no manufacturer data), the 29-byte format likely contains valid state/color info.

#### When Service Data Present (v7+)

When both service data AND manufacturer data are present:

1. **Device identification**: Parsed from service data
2. **State data**: Parsed from manufacturer data at **offset 3** (25 bytes)
3. **The app ignores state in service data** even if it's 29 bytes

```python
def parse_service_data(service_data: bytes) -> dict | None:
    """Parse LEDnetWF service data (16 or 29 bytes).

    Returns device identification and version information.
    """
    if len(service_data) < 16:
        return None

    # Check manufacturer prefix
    mfr_hi = service_data[1] & 0xFF
    if mfr_hi not in (0x5A, 0x5B):
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

    return {
        "sta": sta,
        "is_ota_mode": sta == 0xFF,
        "manufacturer": manufacturer,
        "ble_version": ble_version,
        "mac_address": ":".join(f"{b:02X}" for b in mac_bytes),
        "product_id": product_id,
        "firmware_ver": firmware_ver,
        "led_version": led_version,
        "check_key_flag": check_key_flag,
        "firmware_flag": firmware_flag,
    }


def parse_v7_with_service_data(service_data: bytes, mfr_data: bytes) -> dict:
    """Parse BLE v7+ advertisement with service data.

    Args:
        service_data: 16 bytes from service data AD type
        mfr_data: 27+ bytes from manufacturer data AD type
    """
    # Device ID and version from service data
    device_info = parse_service_data(service_data)
    if device_info is None:
        return None

    ble_version = device_info["ble_version"]

    # State from manufacturer data at OFFSET 3 (not 14!)
    if ble_version >= 7 and len(mfr_data) >= 28:
        state_data = mfr_data[3:28]  # 25 bytes starting at offset 3

        # Power state in state_data
        # For v7+ with service data, power is at state_data[11] (= mfr_data[14])
        power_byte = state_data[11]
        power_on = power_byte == 0x23

        device_info["power_on"] = power_on
        device_info["state_data"] = state_data

    return device_info
```

### Service Data UUIDs

| UUID | Short | Name | Used By |
|------|-------|------|---------|
| `0000FFFF-0000-1000-8000-00805f9b34fb` | 0xFFFF | LEDnetWF Service | Standard LEDnetWF (v7+) |
| `00001827-0000-1000-8000-00805f9b34fb` | 0x1827 | MESH_PROVISIONING | SIG Mesh unprovisioned |
| `00001828-0000-1000-8000-00805f9b34fb` | 0x1828 | MESH_PROXY | SIG Mesh provisioned |

**Source**: `Service.java`, `xj/b.java`, `ZGSigMeshApi.java`

### Home Assistant Service Data Access

In bleak/Home Assistant, service data is keyed by UUID string:

```python
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

def _parse_discovery(discovery: BluetoothServiceInfoBleak) -> dict | None:
    # Manufacturer data: dict[company_id: int, data: bytes]
    manu_data = discovery.manufacturer_data

    # Service data: dict[uuid_string: str, data: bytes]
    service_data = discovery.service_data

    # Check for service data (BLE v7+)
    # UUID may be full string or short form
    lednetwf_service_data = None
    for uuid_str, data in service_data.items():
        if "ffff" in uuid_str.lower():
            lednetwf_service_data = data
            break

    # Parse based on what's available
    if lednetwf_service_data is not None:
        # BLE v7+ format with service data
        return parse_v7_advertisement(lednetwf_service_data, manu_data)

    # Fall back to manufacturer data only
    for company_id, data in manu_data.items():
        if 23040 <= company_id <= 23295:  # 0x5A** ZengGe
            return parse_zengge_advertisement(data)
        if company_id == 4354:  # 0x1102 Telink
            return parse_telink_advertisement(data)

    return None
```

### Complete Parsing Example

```python
def parse_lednetwf_advertisement(
    manu_data: dict[int, bytes],
    service_data: dict[str, bytes]
) -> dict | None:
    """Parse LEDnetWF BLE advertisement data.

    Handles:
    - Standard ZengGe format (company ID 0x5A**)
    - BLE v7+ with service data + manufacturer data
    - Service data ONLY (29-byte format with state)
    - Telink/IOTBT format (company ID 0x1102)
    """
    # 1. Check for service data (BLE v7+)
    sd = None
    for uuid_str, data in service_data.items():
        if "ffff" in uuid_str.lower() and len(data) >= 16:
            sd = data
            break

    # 2. Find manufacturer data
    md = None
    for cid, data in manu_data.items():
        if 23040 <= cid <= 23295:  # ZengGe
            md = data
            break
        if cid == 4354:  # Telink
            return _parse_telink(data)

    # 3. Parse based on what's available
    power_on = None
    rgb = None
    mode_type = None
    sub_mode = None

    if sd is not None and md is not None:
        # Case A: Both service data AND manufacturer data (BLE v7+)
        ble_version = sd[3]
        product_id = (sd[10] << 8) | sd[11]

        if ble_version >= 7 and len(md) >= 28:
            # State at offset 3 in manufacturer data
            state = md[3:28]  # 25 bytes
            power_byte = state[11]  # = md[14]
            mode_type = state[12]   # = md[15]
            sub_mode = state[13]    # = md[16]
            rgb = (state[15], state[16], state[17])  # = md[18:21]
        else:
            power_byte = md[14] if len(md) > 14 else None

    elif sd is not None and len(sd) >= 29:
        # Case B: Service data ONLY (29-byte format with state)
        # Some surplife devices may only advertise service data
        ble_version = sd[3]
        product_id = (sd[10] << 8) | sd[11]

        # State in service data bytes 16-26
        power_byte = sd[16]
        mode_type = sd[17]
        sub_mode = sd[18]
        rgb = (sd[20], sd[21], sd[22])

    elif sd is not None:
        # Case C: Service data only (16-byte, ID only - no state)
        ble_version = sd[3]
        product_id = (sd[10] << 8) | sd[11]
        power_byte = None

    elif md is not None and len(md) >= 27:
        # Case D: Manufacturer data only (standard format)
        ble_version = md[1]
        product_id = (md[8] << 8) | md[9]

        if ble_version >= 5 and len(md) > 14:
            power_byte = md[14]
            mode_type = md[15]
            sub_mode = md[16]
            rgb = (md[18], md[19], md[20])
        else:
            power_byte = None

    else:
        return None

    # Parse power state
    if power_byte is not None:
        if power_byte == 0x23:
            power_on = True
        elif power_byte == 0x24:
            power_on = False

    return {
        "product_id": product_id,
        "ble_version": ble_version,
        "power_on": power_on,
        "mode_type": mode_type,
        "sub_mode": sub_mode,
        "rgb": rgb,
        "has_service_data": sd is not None,
        "has_manufacturer_data": md is not None,
    }


def _parse_telink(data: bytes) -> dict | None:
    """Parse Telink BLE Mesh format."""
    if len(data) < 13:
        return None

    status = data[10] & 0xFF
    return {
        "product_id": 0x80,  # IOTBT
        "ble_version": 0,
        "power_on": status > 0,
        "format": "telink",
        "mesh_address": (data[12] << 8) | data[11],
    }
```

### Implementation Notes for lednetwf_ble_2

The current `parse_manufacturer_data()` in `protocol.py` only handles ZengGe format (0x5A** company IDs). To fully support all device types:

1. **Add service data parsing**: Check for UUID containing "ffff" in `discovery.service_data`
2. **Add Telink format detection**: Check for company ID 4354 (0x1102)
3. **Handle BLE v7+ format**: When service data present, parse state from mfr_data offset 3
4. **Parse Telink status byte at offset 10**: This contains power/brightness

**Key differences for product_id=0x00 devices**:

- If you see product_id=0x00 with ZengGe format, the device may be using Telink format
- Check if manufacturer data has company ID 4354 instead of 0x5A**
- Parse power from offset 10, not offset 14
