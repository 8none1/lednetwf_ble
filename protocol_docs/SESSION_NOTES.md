# Session Notes - AI Assistant Role & Mission

## Project Context
This project is developing a new Home Assistant custom integration to control LEDnetWF/Zengge Bluetooth Low Energy LED lights. The integration is being reverse-engineered from the official Android application.

## My Role & Responsibilities

### 1. Primary Mission
Help develop the new Home Assistant integration by analyzing and documenting the Android app's BLE protocol implementation.

### 2. Source Code Locations

#### **Android App (Source of Truth)**
- **Location 1**: `/home/will/source/reverse_engineering/zengee/`
- **Location 2**: `/home/will/source/jadx/projects/zengee/`
- **Purpose**: These contain the decompiled Android application code. This is the authoritative source for understanding the BLE protocol.
- **Action**: Analyze both directories to understand how the app communicates with the LED devices.

#### **Old Python Integration (Reference Only - READ ONLY)**
- **Location**: `/home/will/source/lednetwf_ble/custom_components/lednetwf_ble/`
- **Purpose**: Working Python implementation from a previous version.
- **Action**: Read to understand patterns and help interpret Android code. DO NOT fix bugs or modify this code.
- **Note**: We're replacing this implementation, not maintaining it.

#### **New Python Integration (Analysis Only)**
- **Location**: `/home/will/source/lednetwf_ble/custom_components/lednetwf_ble_2/`
- **Purpose**: New implementation being written by another AI assistant.
- **Action**: Can analyze and report bugs/issues, but DO NOT fix them. Provide detailed findings so the other AI can make corrections.

#### **Protocol Documentation**
- **Location**: `/home/will/source/lednetwf_ble/protocol_docs/`
- **Purpose**: Documented findings from Android app analysis.
- **Action**: 
  - Always check documentation first when answering questions
  - Document new discoveries as you explore the Android code
  - Update/correct documentation if Android code reveals errors
  - Assume documentation might be incomplete or incorrect - verify against Android source

## Workflow

1. **When asked a question**: Check `protocol_docs/` first
2. **When exploring**: Analyze Android app code from both `zengee` directories
3. **When documenting**: Write findings to `protocol_docs/`
4. **When verifying**: Cross-reference with old Python code if needed
5. **When reviewing new code**: Analyze and report, don't fix

## Key Principles

- Android app code is the source of truth
- Documentation should reflect what the Android code actually does
- Old Python code is for reference and understanding only
- New Python code review is informational only
- Keep documentation accurate and up-to-date based on discoveries - LEDnetWF BLE Protocol Reverse Engineering

**Date**: 3 December 2025
**Branch**: 8none1/version_2

## Current Investigation Status

### Device Under Test
- **Name**: LEDnetWF02001D0CDA81
- **sta byte**: 0x53 (handled by model_0x53.py)
- **Product ID**: 0x001D (29 decimal) = FillLight0x1D
- **BLE Version**: 5
- **Protocol Version**: 0 (legacy)

### Current Issue - Effect Commands Turning Off Device

**Problem**: Setting effects on 0x53 devices often turns device OFF and sets wrong brightness

**Root Cause Analysis** (4 Dec 2025):

1. **Incorrect 0x38 Command Format for Addressable LED Devices**
   - **Current (WRONG)**: `[0x38, effect_id, speed, param, checksum]` - 5 bytes total
   - **Correct (from working old code)**: `[0x38, effect_id, speed, brightness]` - 4 bytes, NO checksum
   - The raw command payload is only 4 bytes before transport wrapping
   - Checksum is NOT added to unwrapped payload for this command

2. **Missing Brightness Parameter**
   - New integration file: `protocol.py::build_effect_command_0x38()` 
   - Uses generic `param` instead of brightness
   - `device.py::set_effect()` doesn't pass current brightness value
   - Old working code: `effect_packet[11] = self.get_brightness_percent()`

3. **Device Classification Error**
   - 0x53/0x54/0x56 devices are addressable LED strip controllers
   - They use 0x38 command but with DIFFERENT format than Symphony devices
   - They have 93+ custom effects (IDs 1-93+), not Symphony effects
   - NOT the same as "Simple Effects" (37-56) or "Symphony Effects" (1-44)

**Working Packet Example** (from old code):
```text
00 00 80 00 00 04 05 0b 38 01 32 64
└──────transport────┘ └─payload──┘
                      ^  ^  ^  ^
                      |  |  |  └─ brightness (0x64 = 100%)
                      |  |  └──── speed (0x32 = 50)
                      |  └─────── effect_id (0x01 = effect 1)
                      └────────── command (0x38)
```

**CRITICAL RESEARCH FINDINGS** (4 Dec 2025):

Analysis of all old Python models revealed **FIVE DIFFERENT effect command formats**:

1. **0x53** (UNIQUE): `0x38` with 4 bytes, NO checksum - `[0x38, effect, speed, bright]`
2. **0x54/0x55/0x62**: `0x38` with 5 bytes + checksum, `0x39` for candle (9 bytes)
3. **0x56/0x80**: `0x42` (5 bytes), `0x41` (13 bytes, FG/BG colors), `0x73` (13 bytes, music)
4. **0x5B**: `0x38` with 5 bytes + checksum, `0x39` for candle (9 bytes)
5. **Symphony (0xA1-0xA9)**: `0x38` with 5 bytes + checksum (param instead of brightness)

**Key Discovery**: Only 0x53 omits the checksum! All others include it.

**Documentation**: 
- `BUG_REPORT_EFFECT_COMMANDS.md` - Complete bug analysis with fixes
- `EFFECT_COMMAND_REFERENCE.md` - Comprehensive reference for all device types

**Previous Issue** (RESOLVED):
Linux machine not receiving BLE notifications from device, but:
- Device DOES send notifications (confirmed via LightBlue on phone)
- This is a Linux BLE stack issue, NOT a device protocol issue
- Scanner `mon N` command added to help debug this

---

## Java Source Code Location
Decompiled APK at: `/tmp/zengee/app/src/main/java/`

### Key Java Files Analyzed

#### Device Type Classes
- `com/zengge/wifi/Device/Type/FillLight0x1D.java` - **STUB class** (all methods return null/0/false)
- `com/zengge/wifi/Device/BaseDeviceInfo.java` - Base device class with common functionality
- `com/zengge/wifi/Device/DeviceState.java` - State container (power, RGB, mode, etc.)

#### Protocol Implementation
- `tc/b.java` - Main protocol class with command builders:
  - `l()` at line 1637: Builds state query `[0x81, 0x8A, 0x8B, checksum]`
  - `c()` at line 46: Parses 0x81 state response (14 bytes)
  - `M()` at line 759: Legacy power command 0x71
  - `t()`, `v()`, `x()`: Different color command formats (8-byte and 9-byte)
  
- `tc/d.java` - Symphony (0x3B) commands for BLE v5+ devices:
  - `c()`: Power command with PowerType mode byte
  - `a()`: HSV color command

- `com/zengge/wifi/COMM/Protocol/q.java` - Power command protocol selection

#### Module/Version Detection
- `com/zengge/wifi/Device/ModuleType/ModuleType_ZG_2_0.java`:
  - `f23897c` field = protocol version (parsed from position 11+ of module string)
  - Version thresholds: >=5 for modern commands, >=8 for protocol v1, etc.

- `com/zengge/wifi/Device/ModuleType/BaseModuleType.java`:
  - `f23896b` = sub-type string
  - `f23897c` = version number

#### Product ID Mapping
- `com/zengge/wifi/Device/a.java` method `k()` - Maps product IDs to device types

#### Symphony/Addressable LED Support
- `dd/i.java` - IC chip type definitions:
  ```
  1=UCS1903, 2=SM16703, 3=WS2811, 4=WS2812B, 5=SK6812, 6=INK1003,
  7=WS2801, 8=WS2815, 9=APA102, 10=TM1914, 11=UCS2904B, 12=JY1903,
  13=WS2812E, 14=CF1903B
  ```

- Symphony Product IDs (0xA1-0xA9 / 161-169): Support addressable LEDs with segments

#### BLE Communication
- `com/zengge/hagallbjarkan/gatt/impl/HBConnectionImpl.java` - BLE GATT handling
- `UpperTransportLayer` - Wraps/unwraps BLE packets

---

## Protocol Formats Discovered

### State Query
```
Command:  [0x81, 0x8A, 0x8B, 0x40]  (0x40 = checksum)
Wrapped:  00 01 80 00 00 04 05 0a 81 8a 8b 96
Response: 14 bytes starting with 0x81
```

### State Response (0x81) - 14 bytes
| Byte | Field | Notes |
|------|-------|-------|
| 0 | Header | 0x81 |
| 1 | Mode | Current mode |
| 2 | Power | 0x23=ON, 0x24=OFF |
| 3 | Mode Type | 97/98/99=static, other=effect |
| 4 | Speed | Effect speed |
| 5 | Value1 | Device-specific |
| 6-8 | R, G, B | Color values 0-255 |
| 9 | Warm White | 0-255 |
| 10 | Brightness | 0-255 |
| 11 | Cool White | 0-255 |
| 12 | Reserved | |
| 13 | Checksum | sum(bytes 0-12) & 0xFF |

### LED Settings Query/Response (0x62/0x63)
```
Query:    00 02 80 00 00 05 06 0a 63 12 21 f0 86
Response: 12 bytes starting with 0x63
```

### Power Commands

**Modern (0x3B) - BLE v5+:**
```
ON:  00 01 80 00 00 0d 0e 0b 3b 23 00 00 00 00 00 00 00 32 00 00 90
OFF: 00 01 80 00 00 0d 0e 0b 3b 24 00 00 00 00 00 00 00 32 00 00 91
PowerType: 0x23=ON, 0x24=OFF, 0x25=Toggle
```

**Legacy (0x71) - BLE v1-4:**
```
ON:  [0x71, 0x23, 0x0F, checksum]
OFF: [0x71, 0x24, 0x0F, checksum]
```

### Color Commands

**0x3B HSV (BLE v5+):**
```
[0x3B, mode(0xA1), HSV_hi, HSV_lo, brightness, 0, 0, R, G, B, time_hi, time_lo, checksum]
HSV encoding: packed = (hue << 7) | saturation
  - hue: 0-360
  - saturation: 0-100 (NOT scaled to 127!)
  - brightness: 0-100
```

**0x31 RGB (Legacy):**
- 9-byte: `[0x31, R, G, B, WW, CW, Mode(0xF0), Persist(0x0F), checksum]`
- 8-byte v: `[0x31, R, G, B, W, 0x00, Persist(0x0F), checksum]`
- 8-byte x: `[0x31, R, G, B, W, Mode(0xF0), Persist(0x0F), checksum]`

### Transport Layer Wrapper
```
[flags, seq, 0x80, 0x00, len_hi, len_lo, payload_len+1, cmdId, ...payload...]
cmdId: 0x0a = expects response, 0x0b = no response expected
```

---

## Manufacturer Data Format (27 bytes)

| Byte | Field | Notes |
|------|-------|-------|
| 0 | sta | Device type (0x53, 0x54, 0x56, etc.) |
| 1 | BLE Version | Determines protocol selection |
| 2-7 | MAC | 6 bytes |
| 8-9 | Product ID | Big-endian (maps to device capabilities) |
| 10 | FW Ver Low | |
| 11 | LED Version | |
| 12 | Packed byte | check_key_flag (bits 0-1), fw_ver_high (bits 2-7 if BLE>=6) |
| 13 | Firmware Flag | |
| 14-24 | State Data | Power, mode, RGB, brightness, etc. (if BLE>=5) |
| 25-26 | RFU | Reserved |

### State Data in Manufacturer Data (bytes 14-24)
For model 0x53:
| Offset | Field |
|--------|-------|
| 14 (state[0]) | Power: 0x23=ON, 0x24=OFF |
| 15 (state[1]) | Mode: 0x61=color/white, 0x25=effect |
| 16 (state[2]) | Sub-mode: 0xF0=RGB, 0x0F=white, effect# |
| 17 (state[3]) | Brightness (white mode, 0-100) |
| 18-20 (state[4-6]) | R, G, B (0-255) |
| 21 (state[7]) | Color Temp (0-100) |

---

## Scanner Tool Updates Made

### New Commands Added
- `mon N` - Monitor notifications from device (Ctrl+C to stop)
- `rgb N color` - Set color (supports: red, #ff0000, 255,0,0, rgb(255,0,0))

### New Functions
- `parse_rgb_input()` - Parse multiple RGB input formats
- `rgb_to_hsv()` - Convert RGB to HSV for 0x3B commands
- `build_color_command_0x3B()` - Build HSV color command
- `build_color_command_0x31()` - Build legacy RGB command
- `set_color()` - Auto-select protocol based on BLE version
- `monitor_notifications()` - Connect and decode all notifications
- `detect_capabilities_from_manu_data()` - Fallback capability detection

### Improved Probe Failure Handling
- Better error messages when state query gets no response
- Falls back to manufacturer data capability detection
- Explains that some devices broadcast state in advertisements

---

## Files Modified This Session

1. `/home/will/source/lednetwf_ble/tools/ble_scanner.py`
   - Added color commands, notification monitoring
   - Improved probe failure handling
   - Fixed state_rgb parsing (indices 4,5,6 not 6,7,8)

2. `/home/will/source/lednetwf_ble/protocol_docs/08_state_query_response_parsing.md`
   - Added section on state in manufacturer data
   - Removed incorrect claim about devices not responding
   - Added detection strategy for unknown devices

---

## Key Insights

1. **Model 0x53 (Ring Light)** reads state from manufacturer data advertisements, not just query responses

2. **FillLight0x1D** in Java is a stub - the app doesn't fully support this device, but commands still work via BaseDeviceInfo

3. **Protocol version** (f23897c) is different from **BLE version** - both affect command selection

4. **BLE v5+** uses 0x3B Symphony commands (HSV-based), older uses 0x31 (RGB-based)

5. **Notifications should work** - the issue is Linux BLE stack, not device protocol

---

## Effect Commands Deep Dive (Java Source)

### tc/d.java - Symphony Commands (0x3B, 0x38)

**Method `a(int color, int time)`** - Solid color mode:
- Converts Android Color int to HSV
- Calls `c()` with mode 0xA1 (161)

**Method `b(int mode, int color, int time)`** - Variable mode:
- Same as `a()` but allows specifying mode byte

**Method `c(mode, hue, sat, brightness, param1, param2, rgbColor, time)`** - Core builder:
- Builds 13-byte 0x3B command
- HSV encoding: `(hue << 7) | saturation`

**Method `d(effectId, speed, param)`** - Simple effect (0x38):
- 5-byte command: `[0x38, effect, speed, param, checksum]`

### tc/a.java - Custom Color Array Commands

**Method `a(CustomPickerParams)`** - 0xA3 command:
- Variable length based on color array sizes
- Supports up to 7 foreground + 7 background colors
- Speed mapped from 0-100 to 1-31

**Method `b(long[] colors)`** - 0xA0 segment command:
- 8 bytes per segment: `[0, segNum, R, G, B, 0, 0, 0xFF]`

### tc/b.java - Legacy Commands

**Method `c(effectId, speed, persist)`** - 0x61 effect:
- 5-byte format for built-in modes

**Method `w/y/z(r, g, b, w, persist)`** - 0x41 RGB variants:
- Non-Symphony devices use 0x41 as RGB command

### Protocol/l.java - FG/BG Effect Command (0x41)

**Constructor `l(devices, mode, fgColor, bgColor, speed, direction)`**:
- 13-byte 0x41 command for Symphony devices (types 0xA2, 0xA3)
- Bytes 2-4: Foreground RGB
- Bytes 5-7: Background RGB
- Byte 8: Speed
- Byte 9: Direction (0=forward, 1=reverse)

### Mode Values for 0x3B (from CipherSuite constants)

| Mode | Hex  | Purpose                   |
|------|------|---------------------------|
| 35   | 0x23 | Power ON                  |
| 36   | 0x24 | Power OFF                 |
| 37   | 0x25 | Power Toggle              |
| 161  | 0xA1 | Solid Color (main mode)   |
| 162  | 0xA2 | Mic-reactive              |
| 163  | 0xA3 | Music strip               |
| 164  | 0xA4 | Scene mode                |
| 165  | 0xA5 | Multi-color/gradient      |
| 166  | 0xA6 | Animation                 |
| 167  | 0xA7 | Animation 2               |
| 170  | 0xAA | Effect mode               |
| 177  | 0xB1 | Special effect            |
| 180  | 0xB4 | Brightness mode           |
| 193  | 0xC1 | Custom color mode         |
| 194  | 0xC2 | Multi-param mode          |

---

## JSON-Wrapped Notification Responses

**Document Created**: `JSON_WRAPPED_NOTIFICATION_RESPONSES.md`

### Discovery Summary

Some devices wrap BLE notification responses in JSON format instead of sending raw binary. The format is determined by **message type bits (2-3)** in the transport layer header byte 0.

### Message Types

| Type | Value | Format | Usage |
|------|-------|--------|-------|
| JSON | 0 | `{"code":0,"payload":"hex"}` | Some devices, WiFi provisioning |
| HEX  | 1 | Raw binary | Most LED state responses |
| ACK  | 2 | Acknowledgment | Filtered out by handlers |

### Type Detection

```python
type_bits = (header_byte[0] & 0x0C) >> 2
```

### Key Findings

1. **Type is per-notification, not per-device**
   - Same device may use different types for different responses
   - Cannot predict from product_id or ble_version alone

2. **Android Implementation**
   - `ZGHBReceiveCallback`: Handles binary (type=1) for most devices
   - `z2.f`: Handles JSON (type=0) for WiFi provisioning and some device setup
   - Type=2 (ACK) always filtered out

3. **Python Implementation (Old Code)**
   - model_0x53 (FillLight): Always JSON with quote extraction
   - model_0x54: Checks for `{` prefix, JSON detection
   - model_0x56: Pure binary, no JSON

4. **Simplified Approach**
   - Old Python code doesn't check type bits explicitly
   - Instead: try UTF-8 decode + JSON parse, fallback to quote extraction
   - This approach works for all known devices

### Example JSON Response

Raw (59 bytes):
```
00 00 80 00 00 2F 30 0A 7B 22 63 6F 64 65 22 3A 30 2C 22 70 61 79 6C 6F 61 64 22 3A 22 38 31 33 33 32 34 32 42 32 33 31 44 45 44 30 30 45 44 30 30 30 41 30 30 30 46 33 36 22 7D
```

Decoded payload:
```json
{"code":0,"payload":"8133242B231DED00ED000A000F36"}
```

State bytes:
```
81 33 24 2B 23 1D ED 00 ED 00 0A 00 0F 36
```

### Android Code References

- `UpperTransportLayer.java`: Defines type constants (JSON=0, HEX=1, ACK=2)
- `LowerTransportLayerDecoder.java`: Extracts type from bits 2-3 of header
- `ZGHBReceiveCallback.java`: Binary notification handler (filters type=2)
- `z2/f.java`: JSON notification handler (uses Gson to parse)
- `Result.java`: JSON structure with `code` and `payload` fields

---

## Transport Header Type Bits - Critical Correction

**Document Created**: `TRANSPORT_HEADER_TYPE_BITS_ANALYSIS.md`

### The Problem

Observed header byte `0x04`:
- Bits 2-3 = 01 → Type 1 (HEX/binary according to spec)
- But actual payload starts with `0x7B` (`{`) → JSON!

### Investigation Results

**CRITICAL FINDING: Type bits (2-3) DO NOT indicate JSON vs binary format!**

#### Android Code Analysis

1. **Two different LowerTransportLayerDecoder implementations:**
   - `com.zengge.hagallbjarkan`: Extracts type bits
   - `com.example.blelibrary`: Does NOT extract type bits

2. **Type bits ONLY used to filter ACK packets:**
   ```java
   if (transport.getType() == 2) return;  // Filter ACKs
   ```

3. **NEVER checks type == 0 vs type == 1** for JSON detection
   - z2.f: Always parses as JSON (no type check)
   - ZGHBReceiveCallback: Passes raw payload (no type check)

4. **Old Python code completely ignores transport header:**
   - Decodes FULL notification (including header) as UTF-8
   - Uses `rfind('"')` to extract hex between quotes
   - Works by accident but is robust!

### Why Type Bits Don't Match

Possible reasons:
1. Type bits may indicate **command format**, not response format
2. Type bits may be unreliable/unused in practice
3. Different firmware versions inconsistent
4. Android app doesn't trust them, uses payload inspection instead

### Correct Implementation

**DO:**
- Filter ACK packets: `if (type & 0x0C) >> 2 == 2: skip`
- Detect JSON by payload: Check for `{` or try UTF-8 decode
- Use old Python approach: Decode full notification, extract from quotes

**DON'T:**
- Trust type bits for JSON vs binary detection
- Use type bits to decide parsing strategy

### Impact

Previous `JSON_WRAPPED_NOTIFICATION_RESPONSES.md` document was **INCORRECT**:
- Stated type bits determine JSON vs binary → WRONG
- Type bits only reliable for ACK filtering
- JSON detection must be payload-based

---

## Next Steps

1. Debug why Linux isn't receiving BLE notifications (use `mon N` command)
2. Compare notification behavior between Linux and phone
3. Check if BlueZ version or adapter settings affect this
4. May need to try different BLE adapters or BlueZ configurations
5. Implement effect commands in scanner for testing
6. Document remaining tc/e.java timer/schedule commands
