# Effect Command Implementation Guide - Quick Reference

**Date**: 5 December 2025  
**Purpose**: Summary for implementation in lednetwf_ble_2 integration  
**Status**: Ready for implementation

---

## Critical Findings - Must Read First

### 1. Device Type Detection
- **Use product_id (bytes 8-9) as PRIMARY identifier**, not sta_byte
- Product ID 29 (0x1D) = FillLight → uses 4-byte format
- Product IDs 161-169 (0xA1-0xA9) = Symphony → uses 5-byte format
- Sta_byte is DEVICE STATUS, not device type (use as fallback only)

### 2. Effect Command Formats
There are **TWO completely different formats**:

#### Format A: FillLight/Ring Light (Product ID 29)
```
[0x38, effect_id, speed, brightness]  // 4 bytes, NO checksum
```
- Speed: 0-100 DIRECT (no inversion)
- Brightness: 0-100 (0=OFF, use 1-100)
- Effect IDs: 1-93 or 0xFF for cycle all

#### Format B: Symphony Devices (Product IDs 161-169)
```
[0x38, effect_id, speed, brightness, checksum]  // 5 bytes WITH checksum
```
- Speed: 1-31 INVERTED (lower=faster)
- Brightness: 1-100 (NEVER 0, it powers OFF)
- Effect IDs: 1-44 Symphony effects

### 3. State Response Parsing
Different byte positions for different devices:

#### FillLight (4-byte format devices)
```
State response (14 bytes, 0x81 header):
Byte 3: 0x25 (effect mode)
Byte 4: effect_id
Byte 6: brightness (0-100)  ← R position
Byte 7: speed (0-100 direct) ← G position
```

#### Symphony (5-byte format devices)
```
State response (14 bytes, 0x81 header):
Byte 3: 0x25 (effect mode)
Byte 4: effect_id
Byte 5: brightness (1-100)  ← NOT byte 6!
Byte 6: unknown/reserved (often 0)
Byte 7: speed (1-31 inverted)
```

---

## Implementation Code

### Device Detection

```python
def get_effect_command_type(product_id: int) -> str:
    """Determine effect command format from product_id."""
    
    # FillLight - 4-byte format, NO checksum
    if product_id == 29:  # 0x1D
        return 'filllight_4byte'
    
    # Symphony - 5-byte format WITH checksum
    if product_id in [161, 162, 163, 164, 166, 167, 169]:  # 0xA1-0xA9
        return 'symphony_5byte'
    
    # Add other device types as needed
    return 'unknown'
```

### FillLight Effect Command (4-byte)

```python
def build_effect_filllight(effect_id: int, speed: int, brightness: int) -> bytes:
    """
    Build FillLight effect command (4 bytes, NO checksum).
    
    Args:
        effect_id: 1-93 or 0xFF
        speed: 0-100 (0=slowest, 100=fastest - DIRECT, no scaling!)
        brightness: 0-100 (0=OFF, recommend 1-100)
    """
    # Clamp values
    effect_id = max(1, min(93, effect_id)) if effect_id != 0xFF else 0xFF
    speed = max(0, min(100, speed))
    brightness = max(0, min(100, brightness))
    
    # 4 bytes, NO checksum
    command = bytes([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,
    ])
    
    return command
```

### Symphony Effect Command (5-byte)

```python
def build_effect_symphony(effect_id: int, speed_percent: int, brightness: int) -> bytes:
    """
    Build Symphony effect command (5 bytes WITH checksum).
    
    Args:
        effect_id: 1-44
        speed_percent: 0-100 (will be inverted to 1-31)
        brightness: 1-100 (NEVER 0!)
    """
    # Validate and clamp
    effect_id = max(1, min(44, effect_id))
    speed_percent = max(0, min(100, speed_percent))
    brightness = max(1, min(100, brightness))  # Force minimum 1
    
    # Invert speed to 1-31 range (lower=faster)
    speed_byte = 31 - round(speed_percent * 30 / 100)
    speed_byte = max(1, min(31, speed_byte))
    
    # Build payload
    payload = bytes([
        0x38,
        effect_id & 0xFF,
        speed_byte & 0xFF,
        brightness & 0xFF,
    ])
    
    # Add checksum
    checksum = sum(payload) & 0xFF
    command = payload + bytes([checksum])
    
    return command
```

### State Response Parser

```python
def parse_effect_state(response: bytes, device_type: str) -> dict:
    """
    Parse effect state from device response.
    
    Args:
        response: 14-byte state response starting with 0x81
        device_type: 'filllight_4byte' or 'symphony_5byte'
    """
    if len(response) < 14 or response[0] != 0x81:
        return None
    
    # Verify checksum
    if sum(response[:13]) & 0xFF != response[13]:
        return None
    
    mode_type = response[3]
    
    if mode_type != 0x25:  # Not effect mode
        return None
    
    if device_type == 'filllight_4byte':
        # FillLight: brightness=byte6, speed=byte7 (direct)
        return {
            'effect_id': response[4],
            'brightness': response[6],  # 0-100
            'speed': response[7],       # 0-100 direct
            'device_type': 'filllight',
        }
    
    elif device_type == 'symphony_5byte':
        # Symphony: brightness=byte5, speed=byte7 (inverted)
        speed_byte = response[7]
        
        # Convert inverted speed (1-31) back to percentage (0-100)
        speed_percent = round((31 - speed_byte) * 100 / 30)
        speed_percent = max(0, min(100, speed_percent))
        
        return {
            'effect_id': response[4],
            'brightness': response[5],   # 1-100
            'speed_percent': speed_percent,
            'speed_byte': speed_byte,    # 1-31 inverted
            'device_type': 'symphony',
        }
    
    return None
```

---

## Common Mistakes to Avoid

### ❌ WRONG: Using 5-byte format for FillLight
```python
# This BREAKS FillLight devices!
command = bytes([0x38, effect_id, speed, brightness, checksum])
```

### ✅ CORRECT: Use 4-byte format for FillLight
```python
command = bytes([0x38, effect_id, speed, brightness])  # NO checksum
```

### ❌ WRONG: Inverting speed for FillLight
```python
# This makes speed slider not work on FillLight!
speed_byte = 31 - round(speed_percent * 30 / 100)
```

### ✅ CORRECT: Direct speed for FillLight
```python
speed_byte = speed_percent  # 0-100 direct
```

### ❌ WRONG: Using brightness=0 for Symphony
```python
# This turns the device OFF!
build_effect_symphony(effect_id, speed, 0)
```

### ✅ CORRECT: Minimum brightness=1 for Symphony
```python
brightness = max(1, min(100, brightness))  # Force 1-100
```

### ❌ WRONG: Using sta_byte for device type
```python
# Sta_byte is DEVICE STATUS, not type!
if sta_byte == 0x53:
    device_type = 'filllight'
```

### ✅ CORRECT: Use product_id for device type
```python
if product_id == 29:  # 0x1D
    device_type = 'filllight'
```

---

## Quick Decision Tree

```
Is this an effect command?
├─ YES → Check product_id
│   ├─ product_id == 29 (0x1D)?
│   │   └─ Use 4-byte format, direct speed
│   ├─ product_id in 161-169 (0xA1-0xA9)?
│   │   └─ Use 5-byte format, inverted speed
│   └─ Unknown?
│       └─ Check old model_0x53.py, model_0x54.py, etc.
└─ NO → Use appropriate color/power command
```

---

## Testing Checklist

- [ ] FillLight (product_id=29): Speed slider changes effect speed
- [ ] FillLight: Brightness slider changes effect brightness
- [ ] FillLight: Device stays ON when setting effect
- [ ] Symphony (product_id=161-169): Speed slider changes effect speed
- [ ] Symphony: Brightness=1 shows dim effect (not OFF)
- [ ] Symphony: Brightness=0 turns device OFF (expected)
- [ ] State query returns correct speed and brightness values
- [ ] Speed direction correct: higher slider value = faster effect

---

## Reference Documents

- `FILLLIGHT_0x1D_EFFECT_FORMAT.md` - Complete FillLight details
- `SYMPHONY_EFFECT_BRIGHTNESS_ISSUE.md` - Complete Symphony details
- `SYMPHONY_EFFECT_SPEED_ENCODING.md` - Speed encoding explained
- `DEVICE_IDENTIFICATION_GUIDE.md` - Product ID mapping
- `BUG_REPORT_EFFECT_COMMANDS.md` - Original bug analysis
- `EFFECT_COMMAND_REFERENCE.md` - All device types reference

---

## Key Facts Summary

| Aspect | FillLight (29) | Symphony (161-169) |
|--------|----------------|-------------------|
| **Command length** | 4 bytes | 5 bytes |
| **Checksum** | NO | YES |
| **Speed range** | 0-100 | 1-31 |
| **Speed encoding** | Direct | Inverted |
| **Brightness min** | 0 (=OFF) | 1 (0=OFF) |
| **Effect IDs** | 1-93, 0xFF | 1-44 |
| **State byte 5** | Unknown | Brightness |
| **State byte 6** | Brightness | Unknown |
| **State byte 7** | Speed (direct) | Speed (inverted) |

---

## Implementation Priority

1. ✅ Detect device type from product_id (bytes 8-9 in manufacturer data)
2. ✅ Build correct command format based on device type
3. ✅ Handle speed encoding correctly (direct vs inverted)
4. ✅ Enforce brightness limits (0-100 vs 1-100)
5. ✅ Parse state response from correct byte positions
6. ✅ Test with real devices

---

## Final Notes

- **Old Python code (model_0x53.py) is CORRECT for FillLight**
- **Android source (tc/d.java) is CORRECT for Symphony**
- **These are TWO DIFFERENT protocols, not variants of the same**
- **Product ID is the authoritative device identifier**
- **Sta_byte is unreliable (it's current status, not type)**
- **Never mix the two formats - always check device type first**
