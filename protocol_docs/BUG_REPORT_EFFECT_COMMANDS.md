# BUG REPORT: Effect Commands Turning Off Device

**Date**: 4 December 2025  
**Reporter**: Protocol Analysis AI  
**Severity**: HIGH  
**Affected Devices**: Addressable LED strip controllers (sta byte 0x53 - CRITICAL, others have different formats)  
**Status**: ROOT CAUSE IDENTIFIED - MULTIPLE EFFECT COMMAND VARIANTS FOUND

---

## Problem Description

When setting an effect on addressable LED devices, the device often:
1. Turns OFF instead of showing the effect
2. Sets brightness to incorrect/unexpected values
3. May show random behavior

## CRITICAL DISCOVERY: Multiple Effect Command Formats

Research into the Android source and old Python code reveals **FIVE different effect command formats** used by different device types:

| Device (sta) | Command | Format | Bytes | Checksum | Notes |
|--------------|---------|--------|-------|----------|-------|
| **0x53** | **0x38** | `[0x38, effect_id, speed, brightness]` | **4** | **NO** | **UNIQUE - No checksum!** |
| 0x54 | 0x38 | `[0x38, effect_id, speed, brightness, checksum]` | 5 | YES | Standard effects |
| 0x54 | 0x39 | `[0x39, on, R, G, B, speed, brightness, 0, checksum]` | 9 | YES | Candle mode |
| 0x56 | 0x42 | `[0x42, effect_id, speed, brightness, checksum]` | 5 | YES | Standard effects |
| 0x56 | 0x41 | `[0x41, effect_id, R_fg, G_fg, B_fg, R_bg, G_bg, B_bg, speed, dir, 0, 0xF0, checksum]` | 13 | YES | Static effects with FG/BG colors |
| 0x56 | 0x73 | `[0x73, on, ?, effect_id, R_fg, G_fg, B_fg, R_bg, G_bg, B_bg, speed, brightness, checksum]` | 13 | YES | Music reactive |
| 0x5B | 0x38 | `[0x38, effect_id, speed, brightness, checksum]` | 5 | YES | Standard effects |
| 0x5B | 0x39 | `[0x39, on, R, G, B, speed, brightness, 0, checksum]` | 9 | YES | Candle mode |

**Key Finding**: 0x53 is the ONLY device that uses 0x38 without a checksum!

## Root Cause Analysis

### Issue 1: Incorrect 0x38 Command Format

**File**: `custom_components/lednetwf_ble_2/protocol.py`  
**Function**: `build_effect_command_0x38()`  
**Line**: ~324

**Current Implementation (WRONG)**:
```python
def build_effect_command_0x38(effect_id: int, speed: int = 128, param: int = 0) -> bytearray:
    """
    Build Symphony effect command (0x38).
    Format: [0x38, effect_id, speed, param, checksum]
    """
    internal_id = effect_id - 99 if effect_id >= 100 else effect_id
    
    raw_cmd = bytearray([
        0x38,
        internal_id & 0xFF,
        speed & 0xFF,
        param & 0xFF,        # ❌ WRONG: Should be brightness!
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))  # ❌ WRONG: No checksum for addressable LEDs!
    return wrap_command(raw_cmd, cmd_family=0x0b)
```

**Correct Implementation** (based on working old code):
```python
def build_effect_command_0x38_addressable(effect_id: int, speed: int = 128, brightness: int = 100) -> bytearray:
    """
    Build effect command for addressable LED devices (0x53, 0x54, 0x56).
    
    Args:
        effect_id: Effect number (1-93+)
        speed: Effect speed (0-255)
        brightness: Brightness percentage (0-100) ⚠️ NOT 0-255!
    
    Returns:
        Wrapped command packet
    """
    raw_cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,  # ✅ Brightness in PERCENT (0-100)
    ])
    # ✅ NO CHECKSUM for addressable LED variant!
    return wrap_command(raw_cmd, cmd_family=0x0b)
```

**Key Differences**:
1. **Third parameter is brightness** (0-100 percent), not a generic "param"
2. **NO checksum byte** in the raw payload (only 4 bytes total)
3. **Brightness is in percent (0-100)**, NOT 0-255 like other commands

### Issue 2: Missing Brightness in set_effect()

**File**: `custom_components/lednetwf_ble_2/device.py`  
**Function**: `set_effect()`  
**Line**: ~556

**Current Implementation**:
```python
async def set_effect(self, effect_name: str, speed: int | None = None) -> bool:
    # ... validation code ...
    
    if speed is None:
        speed = self._effect_speed

    # Convert speed to 0-255 for protocol
    speed_byte = int(speed * 255 / 100)

    packet = protocol.build_effect_command(effect_type, effect_id, speed_byte)
    # ❌ MISSING: No brightness parameter passed!
```

**Should be**:
```python
async def set_effect(self, effect_name: str, speed: int | None = None) -> bool:
    # ... validation code ...
    
    if speed is None:
        speed = self._effect_speed

    # Convert speed to 0-255 for protocol
    speed_byte = int(speed * 255 / 100)
    
    # ✅ Get current brightness as percent (0-100)
    brightness_percent = int(self._brightness * 100 / 255)

    packet = protocol.build_effect_command(effect_type, effect_id, speed_byte, brightness_percent)
```

### Issue 3: Effect Type Classification

**Problem**: The code treats all addressable LED devices the same way, but they use **completely different command formats**.

**Device Types and Commands** (from old working Python code):

#### 0x53 Devices (Product ID 0x001D - "FillLight")
- **Command**: 0x38
- **Format**: `[0x38, effect_id, speed, brightness]` - **4 bytes, NO checksum**
- **Effects**: 93+ custom effects (IDs 1-93+, plus 0xFF for "All modes")
- **Brightness**: 0-100 percent
- **Speed**: 0-255 (inverted in some contexts)
- **Example**: `38 01 32 64` = Effect 1, speed 50, brightness 100%

#### 0x54 Devices (also 0x55, 0x62)
- **Command 1**: 0x38 - Standard effects (IDs 37-56)
  - **Format**: `[0x38, effect_id, speed, brightness, checksum]` - **5 bytes**
  - Speed is inverted: `0x1F - ((speed-1) * (0x1F-0x01) / 99)`
- **Command 2**: 0x39 - Candle mode (effect ID 100)
  - **Format**: `[0x39, 0xD1, R, G, B, speed_inverted, brightness, 0x03, checksum]` - **9 bytes**
- **Brightness**: 0-100 percent
- **Checksum**: Sum of bytes 8 to length-1 (after transport wrapping)

#### 0x56 Devices (also 0x80)
- **Command 1**: 0x42 - Standard effects (IDs 1-99)
  - **Format**: `[0x42, effect_id, speed, brightness, checksum]` - **5 bytes**
- **Command 2**: 0x41 - "Static" effects with FG/BG colors (IDs 1-10, shifted `<< 8`)
  - **Format**: `[0x41, effect_id, R_fg, G_fg, B_fg, R_bg, G_bg, B_bg, speed, direction, 0, 0xF0, checksum]` - **13 bytes**
- **Command 3**: 0x73 - Music reactive effects (IDs 0x33-0x42, shifted `<< 8`)
  - **Format**: `[0x73, on, 0x26, effect_id, R_fg, G_fg, B_fg, R_bg, G_bg, B_bg, speed, brightness, checksum]` - **13 bytes**
- **Brightness**: 0-100 percent
- **Effect ID encoding**: Some effects use shifted IDs (e.g., `effect_id << 8`) as markers

#### 0x5B Devices
- **Command 1**: 0x38 - Standard effects (IDs 37-56, plus 0x63 for "RGB Jump")
  - **Format**: `[0x38, effect_id, speed, brightness, checksum]` - **5 bytes**
  - Speed is inverted: `0x1F - ((speed-1) * (0x1F-0x01) / 99)`
- **Command 2**: 0x39 - Candle mode (effect ID 100)
  - **Format**: `[0x39, 0xD1, R, G, B, speed_inverted, brightness, 0x03, checksum]` - **9 bytes**
- **Brightness**: 0-100 percent

**Current code incorrectly assumes all addressable LED devices use the same format.**

---

## Evidence

### From Working Old Code

File: `custom_components/lednetwf_ble/models/model_0x53.py`, lines 263-267:

```python
def set_effect(self, effect, brightness):
    # ... validation ...
    effect_packet     = bytearray.fromhex("00 00 80 00 00 04 05 0b 38 01 32 64")
    effect_packet[9]  = effect_id      # Byte 9 of wrapped packet = effect ID
    effect_packet[10] = self.effect_speed  # Byte 10 = speed
    effect_packet[11] = self.get_brightness_percent()  # Byte 11 = brightness (0-100)!
    return effect_packet
```

**Packet breakdown**:
```
00 00 80 00 00 04 05 0b 38 01 32 64
└──────transport────┘ └─payload──┘
Byte 0-7: Transport header
  - 00 04: Payload length = 4 bytes
  - 05: Payload + 1 = 5
  - 0b: cmd_family (no response expected)
Byte 8-11: Raw payload (NO CHECKSUM)
  - 38: Command opcode
  - 01: Effect ID
  - 32: Speed (0x32 = 50)
  - 64: Brightness (0x64 = 100%)
```

### From Android Source Code

File: `tc/d.java`, method `d()`:
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

**Note**: This is for **Symphony devices**. The addressable LED variant (used by 0x53 devices) is NOT in the Android code as a separate method - it's constructed inline in various places with only 4 bytes.

---

## Recommended Fix

### 1. Create Separate Effect Command Builders

Add to `protocol.py`:

```python
def build_effect_command_0x38_symphony(effect_id: int, speed: int = 128, param: int = 0) -> bytearray:
    """
    Build Symphony effect command (0x38).
    
    For Symphony devices (product IDs 0xA1-0xA9, 0x08).
    Scene effects: IDs 1-44
    Build effects: IDs 100-399 (internal 1-300)
    
    Format: [0x38, effect_id, speed, param, checksum] - 5 bytes
    """
    internal_id = effect_id - 99 if effect_id >= 100 else effect_id
    
    raw_cmd = bytearray([
        0x38,
        internal_id & 0xFF,
        speed & 0xFF,
        param & 0xFF,
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0b)


def build_effect_command_0x38_addressable(effect_id: int, speed: int = 128, brightness: int = 100) -> bytearray:
    """
    Build effect command for addressable LED strip devices.
    
    For addressable LED devices (sta bytes 0x53, 0x54, 0x56, product ID 0x001D, etc.).
    Effect IDs: 1-93+ (device-specific custom effects)
    
    Format: [0x38, effect_id, speed, brightness] - 4 bytes, NO checksum
    
    Args:
        effect_id: Effect number (1-93+)
        speed: Effect speed (0-255)
        brightness: Brightness PERCENTAGE (0-100), not 0-255!
    """
    raw_cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,  # Brightness in percent (0-100)
    ])
    # NO checksum for addressable LED variant
    return wrap_command(raw_cmd, cmd_family=0x0b)
```

### 2. Add Effect Type Enum

Add to `const.py`:

```python
class EffectType(Enum):
    """Effect command types."""
    NONE = "none"
    SIMPLE = "simple"          # 0x61 command, effects 37-56
    SYMPHONY = "symphony"      # 0x38 with checksum, Symphony devices
    ADDRESSABLE = "addressable"  # 0x38 without checksum, LED strips
```

### 3. Update build_effect_command()

Modify in `protocol.py`:

```python
def build_effect_command(
    effect_type: EffectType, 
    effect_id: int, 
    speed: int = 128,
    brightness: int = 100
) -> bytearray | None:
    """
    Build effect command based on device effect type.
    
    Args:
        effect_type: SIMPLE, SYMPHONY, or ADDRESSABLE
        effect_id: Effect ID
        speed: Effect speed (0-255)
        brightness: Brightness for addressable LEDs (0-100 percent)
    
    Returns:
        Command packet or None if effect type is NONE
    """
    if effect_type == EffectType.SYMPHONY:
        return build_effect_command_0x38_symphony(effect_id, speed)
    elif effect_type == EffectType.ADDRESSABLE:
        return build_effect_command_0x38_addressable(effect_id, speed, brightness)
    elif effect_type == EffectType.SIMPLE:
        return build_effect_command_0x61(effect_id, speed)
    return None
```

### 4. Update device.py

Modify `set_effect()`:

```python
async def set_effect(self, effect_name: str, speed: int | None = None) -> bool:
    """Set an effect by name."""
    if not self.has_effects:
        _LOGGER.warning("Device %s does not support effects", self._name)
        return False

    effect_type = self._capabilities.get("effect_type", EffectType.NONE)
    effect_id = get_effect_id(effect_name, effect_type)

    if effect_id is None:
        _LOGGER.warning("Unknown effect: %s", effect_name)
        return False

    if speed is None:
        speed = self._effect_speed

    # Convert speed to 0-255 for protocol
    speed_byte = int(speed * 255 / 100)
    
    # Get brightness as percentage for addressable LEDs
    brightness_percent = int(self._brightness * 100 / 255)

    packet = protocol.build_effect_command(
        effect_type, 
        effect_id, 
        speed_byte,
        brightness_percent  # ✅ Pass brightness
    )
    
    if packet is None:
        return False

    if await self._send_command(packet):
        self._effect = effect_name
        self._effect_speed = speed
        self._notify_callbacks()
        return True
    return False
```

### 5. Update Device Capability Detection

Each sta byte needs its own effect command builder. Suggested classification:

```python
# In device detection/capability setup
if sta_byte == 0x53:
    effect_type = EffectType.ADDRESSABLE_0x53  # Uses 0x38, 4 bytes, no checksum
elif sta_byte in [0x54, 0x55, 0x62]:
    effect_type = EffectType.ADDRESSABLE_0x54  # Uses 0x38/0x39, 5/9 bytes, with checksum
elif sta_byte in [0x56, 0x80]:
    effect_type = EffectType.ADDRESSABLE_0x56  # Uses 0x42/0x41/0x73, various formats
elif sta_byte == 0x5B:
    effect_type = EffectType.ADDRESSABLE_0x5B  # Uses 0x38/0x39, 5/9 bytes, with checksum
elif sta_byte in [0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xA7, 0xA9, 0x08]:
    effect_type = EffectType.SYMPHONY  # Uses 0x38 Symphony format with checksum
else:
    effect_type = EffectType.SIMPLE  # Uses 0x61, effects 37-56
```

### 6. Command Builder Mapping

Create separate command builders for each sta byte group:

```python
def build_effect_command(sta_byte: int, effect_id: int, speed: int, brightness: int, **kwargs) -> bytearray | None:
    """
    Build effect command based on device sta byte.
    
    Args:
        sta_byte: Device sta byte (0x53, 0x54, 0x56, etc.)
        effect_id: Effect ID (device-specific range)
        speed: Effect speed (0-255)
        brightness: Brightness percentage (0-100)
        **kwargs: Additional parameters (e.g., fg_color, bg_color for 0x56)
    """
    if sta_byte == 0x53:
        return build_effect_0x53(effect_id, speed, brightness)
    elif sta_byte in [0x54, 0x55, 0x62]:
        if 100 <= effect_id < 200:  # Candle mode
            rgb = kwargs.get('rgb_color', (255, 255, 255))
            return build_candle_0x39(rgb, speed, brightness)
        else:
            return build_effect_0x54(effect_id, speed, brightness)
    elif sta_byte in [0x56, 0x80]:
        if effect_id & 0xFF00:  # Shifted effect ID
            return build_special_effect_0x56(effect_id, speed, brightness, **kwargs)
        else:
            return build_effect_0x56(effect_id, speed, brightness)
    elif sta_byte == 0x5B:
        if effect_id == 100:  # Candle mode
            rgb = kwargs.get('rgb_color', (255, 255, 255))
            return build_candle_0x39(rgb, speed, brightness)
        else:
            return build_effect_0x5b(effect_id, speed, brightness)
    # ... etc
```

---

## Testing Checklist

After implementing fixes:

1. ✅ Test effect setting on 0x53 device - should NOT turn off
2. ✅ Test brightness stays at current level when setting effect
3. ✅ Test different brightness levels (25%, 50%, 75%, 100%)
4. ✅ Test effect speed changes
5. ✅ Test effect changes while effect is already running
6. ✅ Verify with packet capture that raw payload is 4 bytes (no checksum)
7. ✅ Verify third byte is brightness in range 0-100, not 0-255

---

## References

- **Old working code**: `custom_components/lednetwf_ble/models/model_0x53.py` lines 250-267
- **Android source**: `tc/d.java` method `d()` (Symphony variant with checksum)
- **Documentation**: `protocol_docs/07_control_commands.md` (updated with both variants)
- **Session notes**: `protocol_docs/SESSION_NOTES.md` (bug analysis)

---

## Additional Notes

### Why No Checksum?

The addressable LED variant doesn't include a checksum in the raw payload because:
1. The transport layer provides its own integrity checking
2. The working old code never added one
3. Adding a checksum byte causes the device to misinterpret the command
4. The device firmware expects exactly 4 bytes for this command variant

### Brightness Scale

The brightness parameter for addressable LED effects is in **percentage (0-100)**, not the usual 0-255 scale used elsewhere. This is confirmed by:
1. Old working code: `self.get_brightness_percent()` returns 0-100
2. Successful packet captures showing 0x64 (100) for full brightness
3. Device behavior when receiving these values

### Effect Count

The 0x53 device has 93+ custom effects (not 20 "Simple" or 44 "Symphony"). The exact count may vary by firmware. The old code's `EFFECTS_LIST_0x53` has 93 named effects, but effect 0xFF is also supported as "All modes" cycle.
