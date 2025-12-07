# Query Formats: 0x63 vs 0x44

**Last Updated**: 6 December 2025
**Status**: Research complete
**Purpose**: Document the two query command formats for Symphony devices

---

## Overview

Symphony devices (0xA1-0xAD) use two different query commands:

| Query | Format | Purpose | Used By |
|-------|--------|---------|---------|
| **0x63** | IC Settings Query | LED count, segments, IC type, color order | Symphony Settings UI |
| **0x44** | Settled Mode Query | Current effect, FG/BG colors, speed, direction | Settled Mode Fragment |

**Important**: Non-IC devices (0x1D, 0x53, 0x56, 0x80, etc.) do NOT use these queries.

---

## Query Command Formats

### 0x63 Query (IC Settings)

**Source**: `tc/b.java:f0()`

```
[0x63] [0x12] [0x21] [terminator] [checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x63 (99) | Command opcode |
| 1 | 0x12 (18) | Fixed |
| 2 | 0x21 (33) | Fixed |
| 3 | 0xF0 or 0x0F | Terminator (0xF0 for BLE, 0x0F for WiFi) |
| 4 | checksum | Sum of bytes 0-3, masked with 0xFF |

**Used in**:
- `SymphonySettingForA3.java:215` - For 0xA3+ devices
- `NewSymphonyActivity.java:217` - For 0xA2 devices

### 0x44 Query (Settled Mode State)

**Source**: `tc/b.java:d0()`

```
[0x44] [0x4A] [0x4B] [terminator] [checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x44 (68) | Command opcode |
| 1 | 0x4A (74) | Fixed |
| 2 | 0x4B (75) | Fixed |
| 3 | 0xF0 or 0x0F | Terminator (0xF0 for BLE, 0x0F for WiFi) |
| 4 | checksum | Sum of bytes 0-3, masked with 0xFF |

**Used in**:
- `SettledModeFragment.java:334` - For querying current settled mode state
- `tc/e.java:1268` - Generic query method for local connections

---

## Response Formats

### 0x63 Response (IC Settings)

**Source**: `SymphonySettingForA3.java:132-144`

**Response structure** (10 bytes):

| Byte | Field | Description |
|------|-------|-------------|
| 0 | Direction | 0 or 1 (forward/reverse default) |
| 1 | (unused) | Reserved/ignored |
| 2-3 | LED Count | Little-endian uint16 (byte order: [3][2]) |
| 4-5 | Segments | Little-endian uint16 (byte order: [5][4]) |
| 6 | IC Type | IC configuration type (0-9+) |
| 7 | Color Order | RGB order setting (0-5 for RGB variants) |
| 8 | Music Point | Music mode LED point setting |
| 9 | Music Part | Music mode part setting |

**Python parsing**:
```python
def parse_ic_settings_response(data: bytes) -> dict:
    """Parse 0x63 IC settings response."""
    return {
        "direction": data[0] == 1,  # True = forward
        "led_count": data[3] << 8 | data[2],  # Little-endian
        "segments": data[5] << 8 | data[4],  # Little-endian
        "ic_type": data[6],
        "color_order": data[7],
        "music_point": data[8],
        "music_part": data[9],
    }
```

### 0x44 Response (Settled Mode State)

**Source**: `SettledModeFragment.java:500-530`

**Response structure** (12+ bytes):

| Byte | Field | Description |
|------|-------|-------------|
| 2 | Effect ID | 1-10 (Settled Mode effect) |
| 3 | FG Red | Foreground color red (0-255) |
| 4 | FG Green | Foreground color green (0-255) |
| 5 | FG Blue | Foreground color blue (0-255) |
| 6 | BG Red | Background color red (0-255) |
| 7 | BG Green | Background color green (0-255) |
| 8 | BG Blue | Background color blue (0-255) |
| 9 | Speed | Effect speed (0-100) |
| 10 | Direction | 0 = forward, 1 = reverse |
| 11 | Bulb | Bulb/brightness setting |

**Note**: Bytes 0-1 are likely transport layer or reserved.

**Python parsing**:
```python
def parse_settled_mode_response(data: bytes) -> dict:
    """Parse 0x44 settled mode response."""
    return {
        "effect_id": data[2],  # 1-10
        "fg_rgb": (data[3], data[4], data[5]),
        "bg_rgb": (data[6], data[7], data[8]),
        "speed": data[9],
        "direction": data[10] == 0,  # True = forward
        "bulb": data[11],
    }
```

---

## Which Devices Use Which Query

### 0x63 Query Users (IC Settings)

**All Symphony devices (0xA1-0xAD)** when opening Symphony settings UI:

| Product ID | Class | Query Used |
|------------|-------|------------|
| 0xA1 (161) | Ctrl_Mini_RGB_Symphony_0xa1 | 0x63 |
| 0xA2 (162) | Ctrl_Mini_RGB_Symphony_new_0xa2 | 0x63 |
| 0xA3 (163) | Ctrl_Mini_RGB_Symphony_new_0xA3 | 0x63 |
| 0xA4 (164) | Ctrl_Mini_RGB_Symphony_new_0xA4 | 0x63 |
| 0xA6 (166) | Ctrl_Mini_RGB_Symphony_new_0xA6 | 0x63 |
| 0xA7 (167) | Ctrl_Mini_RGB_Symphony_new_0xA7 | 0x63 |
| 0xA9 (169) | Ctrl_Mini_RGB_Symphony_new_0xA9 | 0x63 |
| 0xAA-0xAD | Symphony_Line, Symphony_Curtain | 0x63 |

### 0x44 Query Users (Settled Mode)

Same Symphony devices when viewing Settled Mode UI:
- Query is sent when `SettledModeFragment` becomes visible
- Both 0xA2 and 0xA3+ devices use this query for settled mode state

### Non-IC Devices (NO queries needed)

These devices do NOT use 0x63 or 0x44 queries:

| Product ID | Device Type | Notes |
|------------|-------------|-------|
| 0x1D (29) | FillLight/Ring Light | Uses 0x38 effects, no IC config |
| 0x53 (83) | Ring Light | Uses 0x38 effects, no IC config |
| 0x56 (86) | Strip Lights | Has static effects but no IC settings |
| 0x80 (128) | Strip Lights | Has static effects but no IC settings |

---

## Timing and Sequence

### When Queries Are Sent

The queries are **NOT** sent automatically on BLE connection. They are triggered by UI events:

1. **0x63 Query** - Sent when Symphony Settings activity opens:
   - `NewSymphonyActivity.java:217` (for 0xA2)
   - `SymphonySettingForA3.java:215` (for 0xA3+)
   - Happens in activity initialization, not on connection

2. **0x44 Query** - Sent when Settled Mode fragment becomes visible:
   - `SettledModeFragment.d2()` method
   - Triggered by `C1(boolean visible)` callback
   - Only queries if fragment is visible AND ready

### Connection vs Query Timing

```
BLE Connection Established
        ↓
User opens device control UI
        ↓
[If Symphony Settings] → Send 0x63 query → Parse IC settings
        ↓
[If Settled Mode tab] → Send 0x44 query → Parse settled mode state
```

### For Home Assistant Integration

Since HA doesn't have the same UI-driven flow, you have options:

1. **Query on connection** - Send queries after BLE connect + authentication
2. **Query on demand** - Send queries when specific data is needed
3. **Skip queries** - Use stored/default values if queries aren't critical

**Recommendation**: Query IC settings (0x63) once on connection for Symphony devices to get LED count and IC type. The settled mode query (0x44) can be sent on-demand when the user requests effect state.

---

## Python Implementation

### Building Query Commands

```python
def build_ic_settings_query(is_ble: bool = True) -> bytearray:
    """Build 0x63 IC settings query command."""
    raw_cmd = bytearray([
        0x63,                        # Command opcode
        0x12,                        # Fixed
        0x21,                        # Fixed
        0xF0 if is_ble else 0x0F,    # Terminator
    ])
    checksum = sum(raw_cmd) & 0xFF
    raw_cmd.append(checksum)
    return raw_cmd


def build_settled_mode_query(is_ble: bool = True) -> bytearray:
    """Build 0x44 settled mode state query command."""
    raw_cmd = bytearray([
        0x44,                        # Command opcode
        0x4A,                        # Fixed
        0x4B,                        # Fixed
        0xF0 if is_ble else 0x0F,    # Terminator
    ])
    checksum = sum(raw_cmd) & 0xFF
    raw_cmd.append(checksum)
    return raw_cmd
```

### Full Query with Transport Layer

```python
def wrap_query(raw_cmd: bytearray, cmd_family: int = 0x09) -> bytearray:
    """Wrap query command in transport layer."""
    length = len(raw_cmd)
    packet = bytearray([
        0x00,                    # Byte 0: Always 0
        0x00,                    # Byte 1: Sequence (can be 0)
        0x80,                    # Byte 2: Always 0x80
        0x00,                    # Byte 3: Always 0
        0x00,                    # Byte 4: Always 0
        length & 0xFF,           # Byte 5: Payload length (low)
        (length + 1) & 0xFF,     # Byte 6: Payload length + 1
        cmd_family & 0xFF,       # Byte 7: Command family (0x09 for queries)
    ])
    packet.extend(raw_cmd)
    return packet
```

---

## Response Detection

### Identifying Response Type

When receiving notifications, check the response opcode:

```python
def identify_response(data: bytes) -> str:
    """Identify response type from notification data."""
    # Skip transport header if present
    payload = data[8:] if len(data) > 8 else data

    if len(payload) >= 10 and payload[0] in (0x63, 0x00):
        # Could be IC settings response
        return "ic_settings"

    if len(payload) >= 12:
        # Could be settled mode response
        # Check if byte 2 is in valid effect range (1-10)
        if 1 <= payload[2] <= 10:
            return "settled_mode"

    return "unknown"
```

**Note**: The actual response identification may need refinement based on real device testing, as the response format details may vary.

---

## Summary

| Aspect | 0x63 Query | 0x44 Query |
|--------|-----------|-----------|
| Purpose | IC settings | Settled mode state |
| Command | `[0x63, 0x12, 0x21, term, chk]` | `[0x44, 0x4A, 0x4B, term, chk]` |
| Response size | 10 bytes | 12+ bytes |
| Used by | All Symphony (0xA1-0xAD) | Symphony w/ SettledMode |
| Timing | On settings UI open | On settled mode tab |
| Non-IC devices | Not used | Not used |

---

## Source Files Reference

| File | Purpose |
|------|---------|
| `tc/b.java` | Query command builders (d0, f0) |
| `tc/e.java` | Query execution for local connections |
| `SymphonySettingForA3.java` | A3+ IC settings handler |
| `NewSymphonyActivity.java` | 0xA2 Symphony settings handler |
| `SettledModeFragment.java` | Settled mode UI and state query |
