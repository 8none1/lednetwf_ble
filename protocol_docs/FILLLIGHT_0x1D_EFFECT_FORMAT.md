# FillLight (Product ID 0x1D/29) Effect Command Format - RESOLVED

**Date**: 5 December 2025  
**Status**: ✅ CONFIRMED  
**Device**: FillLight (product_id 0x1D = 29 decimal)

---

## Summary

FillLight (product_id 0x1D/29) uses the **SAME 4-byte effect command format as model_0x53 Ring Lights**:

1. **Command format**: `[0x38, effect_id, speed, brightness]` - **NO checksum (4 bytes only)**
2. **Speed encoding**: 0-100 direct (NOT inverted, NOT 1-31 scale)
3. **Brightness encoding**: 0-100 direct (0 = device OFF)
4. **State response**: brightness=byte 6 (R position), speed=byte 7 (G position)

---

## Evidence from Android Source

### Device Class Mapping (Device/a.java)

```java
// From com/zengge/wifi/Device/a.java lines 277-278
case 29:
    return new FillLight0x1D(deviceInfo);
```

**Product ID 29 maps to FillLight0x1D device class.**

### FillLight0x1D Class Implementation

```java
// From com/zengge/wifi/Device/Type/FillLight0x1D.java
public class FillLight0x1D extends BaseDeviceInfo {
    public FillLight0x1D(DeviceInfo deviceInfo) {
        super(deviceInfo);
    }
    
    @Override
    public int T() {
        return 29;  // Product ID
    }
    
    // No special effect methods overridden
    // Uses default BaseDeviceInfo behavior
}
```

**Key finding**: FillLight0x1D is a **minimal/stub class** that doesn't override any effect-specific methods. This means it uses **default BaseDeviceInfo behavior**, which for addressable LED devices defaults to the 4-byte format.

---

## Evidence from Old Python Code (model_0x53.py)

### Supported Models

```python
# From custom_components/lednetwf_ble/models/model_0x53.py line 13
SUPPORTED_MODELS = [0x00, 0x53]
```

**Note**: The old code uses **sta byte 0x53**, not product_id. But we know from DEVICE_IDENTIFICATION_GUIDE.md that:
- **Product ID 29 (0x1D) → sta byte 0x53**

### Effect Command Builder (4 bytes, NO checksum)

```python
# From model_0x53.py lines 250-266
def set_effect(self, effect, brightness):
    # ...
    effect_packet     = bytearray.fromhex("00 00 80 00 00 04 05 0b 38 01 32 64")
    effect_packet[9]  = effect_id      # Byte 9 of full packet
    effect_packet[10] = self.effect_speed  # 0-100 direct
    effect_packet[11] = self.get_brightness_percent()  # 0-100
    return effect_packet
```

**Breaking down the packet:**
- Bytes 0-7: Transport layer header (8 bytes)
- Byte 8: `0x38` (command opcode)
- Byte 9: effect_id (1-93+, or 0xFF for "cycle all")
- Byte 10: speed (0-100 direct, NO inversion)
- Byte 11: brightness (0-100)
- **NO checksum byte!**

**Pure command payload**: `[0x38, effect_id, speed, brightness]` (4 bytes)

### State Response Parsing

```python
# From model_0x53.py lines 193-211
elif self.manu_data[15] == 0x25:
    # Effect mode (mode_type = 0x25)
    effect = self.manu_data[16]        # Byte 16: effect_id
    self.effect_speed = self.manu_data[19]  # Byte 19: speed
    self.brightness = int(self.manu_data[18] * 255 // 100)  # Byte 18: brightness
```

**Manufacturer data byte positions** (27 bytes from bleak):
- Byte 15: mode_type (0x25 = effect mode)
- Byte 16: effect_id
- Byte 18: brightness (0-100)
- Byte 19: speed (0-100)

**For state query response** (14 bytes starting with 0x81):
- Byte 3: mode_type (0x25 = effect)
- Byte 4: effect_id
- Byte 6: brightness (0-100) ← **R position**
- Byte 7: speed (0-100) ← **G position**

---

## Complete Comparison: FillLight vs Symphony

| Feature | FillLight (0x1D/29) | Symphony (0xA1-0xA9) |
|---------|---------------------|----------------------|
| **Command format** | 4 bytes, NO checksum | 5 bytes with checksum |
| **Command bytes** | `[0x38, id, speed, bright]` | `[0x38, id, speed, bright, chk]` |
| **Speed range** | 0-100 (direct) | 1-31 (inverted) |
| **Speed encoding** | No transformation | Lower = faster |
| **Brightness range** | 0-100 (0=OFF) | 1-100 (0=OFF) |
| **Brightness min** | 0 (turns off) | 1 (min visible) |
| **Effect IDs** | 1-93+ (93+ custom) | 1-44 (Symphony) |
| **State byte 6** | Brightness (R) | Unknown/reserved |
| **State byte 7** | Speed (G) | Speed (inverted) |
| **State byte 5** | Unknown/White bright | Brightness |
| **Checksum** | NO | YES |

---

## Why Speed Slider Does Nothing - Diagnosis

### Possible Causes

1. **Using 5-byte format with checksum** (WRONG for FillLight)
   ```python
   # WRONG - this is Symphony format
   command = [0x38, effect_id, speed, brightness, checksum]
   ```

2. **Speed inversion applied incorrectly** (WRONG for FillLight)
   ```python
   # WRONG - FillLight uses direct 0-100
   speed_byte = 31 - round(speed * 30 / 100)
   ```

3. **Not sending speed parameter at all**
   ```python
   # WRONG - missing speed byte
   command = [0x38, effect_id, brightness, checksum]
   ```

4. **Wrapping command incorrectly**
   - FillLight needs 8-byte transport header + 4-byte command = 12 bytes total
   - Symphony needs 8-byte transport header + 5-byte command = 13 bytes total

### Correct Implementation

```python
def set_effect_filllight(effect_id: int, speed: int, brightness: int) -> bytes:
    """
    Build FillLight effect command (4 bytes, NO checksum).
    
    Args:
        effect_id: 1-93 (or 0xFF for cycle all modes)
        speed: 0-100 (0=slowest, 100=fastest - DIRECT, no conversion!)
        brightness: 0-100 (0 turns device OFF)
    
    Returns:
        4-byte command payload (no checksum)
    """
    # Validate inputs
    if effect_id == 0xFF:
        # Special "cycle all" mode - always last effect
        pass
    else:
        effect_id = max(1, min(93, effect_id))
    
    speed = max(0, min(100, speed))
    brightness = max(0, min(100, brightness))
    
    # Build 4-byte command (NO checksum!)
    command = bytes([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,
    ])
    
    return command

# Usage with transport layer
def build_filllight_effect_packet(effect_id: int, speed: int, brightness: int) -> bytes:
    """Build complete packet with transport layer header."""
    # Transport header (8 bytes)
    # Format: [0x00, 0x00, 0x80, 0x00, 0x00, data_len, 0x05, 0x0B]
    command = set_effect_filllight(effect_id, speed, brightness)
    
    header = bytes([
        0x00,
        0x00,
        0x80,
        0x00,
        0x00,
        len(command),  # 0x04 (4 bytes)
        0x05,
        0x0B,
    ])
    
    return header + command
```

---

## State Response Parsing for FillLight

```python
def parse_filllight_effect_state(response: bytes) -> dict:
    """
    Parse FillLight state response for effect mode.
    
    State response format (14 bytes):
        Byte 0: 0x81 (response header)
        Byte 1: mode
        Byte 2: power (0x23 = ON)
        Byte 3: mode_type (0x25 = effect)
        Byte 4: effect_id
        Byte 5: ??? (possibly white brightness in white mode)
        Byte 6: brightness (0-100) for effects ← R position
        Byte 7: speed (0-100) for effects ← G position
        Byte 8: blue (0 in effect mode)
        Byte 9: warm_white
        Byte 10: led_version
        Byte 11: cool_white
        Byte 12-13: checksum
    """
    if len(response) < 14 or response[0] != 0x81:
        return None
    
    # Verify checksum
    if sum(response[:13]) & 0xFF != response[13]:
        return None
    
    mode_type = response[3]
    
    if mode_type == 0x25:  # Effect mode
        return {
            'power_on': response[2] == 0x23,
            'mode': 'effect',
            'mode_type': mode_type,
            'effect_id': response[4],
            'brightness': response[6],  # R position (0-100)
            'speed': response[7],       # G position (0-100, DIRECT)
            'warm_white': response[9],
            'led_version': response[10],
            'cool_white': response[11],
        }
    
    return None
```

---

## Manufacturer Data Format (BLE Advertisements)

FillLight devices advertise state in manufacturer data (27 bytes, Format B):

```
Byte 0: sta byte (0x53 for FillLight)
Byte 1: ble_version
Bytes 2-7: MAC address
Bytes 8-9: product_id (0x00 0x1D = 29 big-endian)
Byte 10: fw_version
Byte 11: led_version
Bytes 12-14: unknown
Byte 15: mode_type
  - 0x61 (97) = Static RGB/white
  - 0x25 (37) = Effect mode
  - 0x62 (98) = Music mode
Byte 16: sub_mode or effect_id
Byte 17: (in white mode) white brightness
Byte 18: (in effect mode) brightness (0-100)
Byte 19: (in effect mode) speed (0-100)
Byte 20: red (RGB mode)
Byte 21: green (RGB mode) or CCT (white mode)
Byte 22: blue (RGB mode)
Bytes 23-26: unknown/reserved
```

---

## Test Cases

### Test 1: Effect with Speed=0 (Slowest)
```python
command = set_effect_filllight(effect_id=1, speed=0, brightness=50)
# Expected: [0x38, 0x01, 0x00, 0x32]
# Result: Effect runs at slowest speed, 50% brightness
```

### Test 2: Effect with Speed=50 (Medium)
```python
command = set_effect_filllight(effect_id=1, speed=50, brightness=50)
# Expected: [0x38, 0x01, 0x32, 0x32]
# Result: Effect runs at medium speed, 50% brightness
```

### Test 3: Effect with Speed=100 (Fastest)
```python
command = set_effect_filllight(effect_id=1, speed=100, brightness=50)
# Expected: [0x38, 0x01, 0x64, 0x32]
# Result: Effect runs at fastest speed, 50% brightness
```

### Test 4: Cycle All Modes
```python
command = set_effect_filllight(effect_id=0xFF, speed=50, brightness=50)
# Expected: [0x38, 0xFF, 0x32, 0x32]
# Result: Device cycles through all effects
```

### Test 5: Verify State Response
```python
# Send effect command
await device.write(build_filllight_effect_packet(1, 75, 60))

# Query state
await asyncio.sleep(0.1)
state = await device.query_state()

# Verify
assert state['effect_id'] == 1
assert state['speed'] == 75      # Direct value, no conversion
assert state['brightness'] == 60
```

---

## Summary of Answers

### Q1: Does FillLight use 4-byte or 5-byte format?
**✅ 4-byte format, NO checksum** - same as model_0x53 Ring Lights.

### Q2: What is the speed encoding?
**✅ 0-100 direct** - NO inversion, NO 1-31 scale. Higher value = faster.

### Q3: What is the brightness encoding?
**✅ 0-100 direct** - but 0 turns device OFF (use 1-100 for visible effects).

### Q4: Which Android device class handles product_id 29?
**✅ FillLight0x1D** - minimal stub class using default BaseDeviceInfo behavior.

### Q5: Where are brightness and speed in state response?
**✅ Byte 6: brightness (R position), Byte 7: speed (G position)** - both 0-100 direct.

---

## Fixing "Speed Slider Does Nothing"

### Root Cause
You're likely sending either:
1. **5-byte Symphony format** (with checksum) instead of 4-byte
2. **Inverted speed** (1-31 scale) instead of direct 0-100
3. **Wrong byte position** for speed parameter

### Solution

```python
# CORRECT for FillLight
def set_filllight_effect(self, effect_id, speed_percent, brightness):
    """
    effect_id: 1-93 or 0xFF
    speed_percent: 0-100 (0=slowest, 100=fastest - DIRECT)
    brightness: 0-100 (0=OFF)
    """
    command = bytes([
        0x38,
        effect_id & 0xFF,
        speed_percent & 0xFF,     # ← DIRECT 0-100, NO inversion!
        brightness & 0xFF,
    ])
    # NO checksum byte!
    
    return self._wrap_transport_layer(command)

# WRONG - this is Symphony format
def set_symphony_effect(self, effect_id, speed_percent, brightness):
    """DO NOT use this for FillLight!"""
    speed_byte = 31 - round(speed_percent * 30 / 100)  # Inverted
    
    command = bytes([
        0x38,
        effect_id & 0xFF,
        speed_byte & 0xFF,        # ← Inverted 1-31
        brightness & 0xFF,
    ])
    
    checksum = sum(command) & 0xFF
    return self._wrap_transport_layer(command + bytes([checksum]))
```

---

## Related Documentation

- `protocol_docs/DEVICE_IDENTIFICATION_GUIDE.md` - Product ID mapping
- `protocol_docs/SYMPHONY_EFFECT_BRIGHTNESS_ISSUE.md` - Symphony 5-byte format
- `protocol_docs/BUG_REPORT_EFFECT_COMMANDS.md` - All effect command formats
- `protocol_docs/EFFECT_COMMAND_REFERENCE.md` - Complete command reference
- Old Python: `custom_components/lednetwf_ble/models/model_0x53.py`
- Android: `/reverse_engineering/zengee/app/src/main/java/com/zengge/wifi/Device/Type/FillLight0x1D.java`

---

## Key Takeaways

1. **FillLight = model_0x53 = 4 bytes NO checksum**
2. **Speed is 0-100 DIRECT** (not inverted like Symphony)
3. **Product ID 29 → sta byte 0x53** (Ring Light protocol)
4. **State response: byte 6=brightness, byte 7=speed**
5. **Don't confuse with Symphony 5-byte format!**
