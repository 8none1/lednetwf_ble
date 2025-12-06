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
