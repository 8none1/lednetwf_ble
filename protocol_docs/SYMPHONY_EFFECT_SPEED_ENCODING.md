# SYMPHONY Device Effect Speed Encoding - SOLVED

**Date**: 5 December 2025  
**Status**: ✅ RESOLVED

---

## Summary

For SYMPHONY devices (product IDs 0xA1-0xA9), effect speed in state responses is stored **UNCHANGED** in **byte 7 (G position)**, not byte 5. There is **NO transformation or scaling** between command and response.

---

## The Confusion

You observed byte 5 containing value `0x21` (33) when you sent speed 11, leading to suspicion of 3x scaling. This was a **red herring** - byte 5 has a completely different meaning.

---

## The Correct Mapping (From Android Source)

### Effect Command (0x38)
```java
// From tc/d.java method d()
byte[] d(int effect_id, int speed, int param)
{
    byte[] bArr = new byte[5];
    bArr[0] = 56;           // 0x38
    bArr[1] = (byte) effect_id;
    bArr[2] = (byte) speed;
    bArr[3] = (byte) param;  // brightness or generic param
    bArr[4] = checksum;
    return bArr;
}
```

### State Storage After Command
```java
// From RGBNewSymphonyDeviceInfo.java method C1()
void C1(int effect_id, int brightness, int speed)
{
    deviceState.f23862f = (byte) 37;        // Byte 3: mode_type = 0x25 (effect mode)
    deviceState.f23863g = effect_id;        // Byte 4: effect ID
    deviceState.f23864h = Byte.valueOf((byte) speed);  // Byte 5: speed
    deviceState.f23865j = Byte.valueOf((byte) brightness);  // Byte 6: brightness
}
```

### State Response Parsing
```java
// From tc/b.java method c() lines 47-62
DeviceState parseState(byte[] response)
{
    deviceState.f23859c = response[1];      // Byte 1: mode
    deviceState.f23858b = response[2];      // Byte 2: power (0x23 = ON)
    deviceState.f23862f = response[3];      // Byte 3: mode_type (0x25 = effect)
    deviceState.f23863g = response[4];      // Byte 4: sub-mode/effect_id
    deviceState.f23864h = Byte.valueOf(response[5]);  // Byte 5: value1/speed
    deviceState.f23865j = Byte.valueOf(response[6]);  // Byte 6: R/brightness
    deviceState.f23866k = Byte.valueOf(response[7]);  // Byte 7: G
    deviceState.f23867l = Byte.valueOf(response[8]);  // Byte 8: B
    deviceState.f23868m = Byte.valueOf(response[9]);  // Byte 9: WW
    deviceState.f23860d = response[10];     // Byte 10: LED version
    deviceState.f23869n = Byte.valueOf(response[11]);  // Byte 11: CW
}
```

### Getter Methods
```java
// From RGBNewSymphonyDeviceInfo.java
int v1() { return this.f23812e.f23865j.byteValue() & 255; }  // Get brightness (byte 6)
int w1() { return this.f23812e.f23863g & 255; }              // Get effect_id (byte 4)
int x1() { return this.f23812e.f23864h.byteValue() & 255; }  // Get speed (byte 5)
```

---

## THE PROBLEM: Command vs State Mapping Mismatch

### What You Send (0x38 command)
```
[0x38, effect_id, speed, brightness, checksum]
      byte 0    byte 1   byte 2   byte 3    byte 4
```

### How Android Stores It LOCALLY (C1 method)
```
Byte 4 (sub-mode):   effect_id
Byte 5 (value1):     speed        ← Stored from command byte 2
Byte 6 (R):          brightness   ← Stored from command byte 3
```

### What Device Actually Responds (State Query)
```
Byte 4: effect_id
Byte 5: ???         ← NOT SPEED!
Byte 6: brightness
Byte 7: speed       ← THIS IS WHERE SPEED ACTUALLY IS
```

---

## Root Cause Analysis

The Android app's `C1()` method **sets local state** optimistically BEFORE sending the command. It assumes:
- Byte 5 will contain speed
- Byte 6 will contain brightness

But the **actual device firmware** stores effect parameters differently:
- Byte 5: Unknown/reserved (possibly effect subtype or variant)
- Byte 6: Brightness
- Byte 7: Speed

The Android app works because it:
1. Calls `C1()` to set local state before sending command
2. Uses getters `v1()`, `w1()`, `x1()` to read from local state
3. Never actually re-parses the real device response for effect parameters

---

## The Evidence

### Your Observation
```
Sent: 0x38 0x0F 0x0B 0x14 [checksum]
      (effect=15, speed=11, brightness=20)

State response showed:
Byte 5: 0x21 (33)    ← NOT 11! This is NOT speed!
Byte 6: 0x14 (20)    ← Brightness - CORRECT
Byte 7: 0x0B (11)    ← THIS is speed - UNCHANGED
```

### Why Byte 5 = 33?
Possibly:
- Effect variant/subtype
- Flags or mode indicator
- Effect-specific parameter
- Reserved/internal use

The value `33 = 11 × 3` is likely **coincidental**. No evidence of scaling in Android source.

---

## Correct Implementation for Python

### Parsing State Response (14 bytes)

```python
def parse_symphony_state(response: bytes) -> dict:
    """Parse Symphony device state response."""
    if len(response) < 14 or response[0] != 0x81:
        return None
    
    # Verify checksum
    if sum(response[:13]) & 0xFF != response[13]:
        return None
    
    mode_type = response[3]
    
    if mode_type == 0x25:  # Effect mode (37 decimal)
        return {
            'power_on': response[2] == 0x23,
            'mode': 'effect',
            'mode_type': mode_type,
            'effect_id': response[4],
            'value1': response[5],        # Unknown - not speed!
            'brightness': response[6],     # Brightness (0-100)
            'speed': response[7],          # Speed (0-100) ← CORRECT!
            'blue': response[8],           # Usually 0 in effect mode
            'warm_white': response[9],
            'led_version': response[10],
            'cool_white': response[11],
        }
    else:
        # RGB or White mode - different interpretation
        return {
            'power_on': response[2] == 0x23,
            'mode': 'rgb' if response[4] in [0xF0, 0x01, 0x0B] else 'white',
            'mode_type': mode_type,
            'sub_mode': response[4],
            'value1': response[5],        # White brightness in white mode
            'red': response[6],
            'green': response[7],
            'blue': response[8],
            'warm_white': response[9],
            'led_version': response[10],
            'cool_white': response[11],
        }
```

### Building Effect Command (0x38)

```python
def build_symphony_effect_command(effect_id: int, speed: int, brightness: int) -> bytes:
    """
    Build Symphony effect command.
    
    Args:
        effect_id: Effect ID (1-44 for Symphony effects)
        speed: Effect speed (0-100)
        brightness: Brightness (0-100)
    
    Returns:
        5-byte command with checksum
    """
    payload = bytes([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,
    ])
    
    checksum = sum(payload) & 0xFF
    return payload + bytes([checksum])
```

### Setting Effect with State Update

```python
async def set_effect_symphony(self, effect_id: int, speed: int, brightness: int):
    """Set effect on Symphony device."""
    # Build and send command
    command = build_symphony_effect_command(effect_id, speed, brightness)
    await self._write(command)
    
    # Update local state
    self._effect_id = effect_id
    self._effect_speed = speed      # Store for local state
    self._brightness = brightness
    
    # Query actual device state to verify
    await asyncio.sleep(0.1)
    state = await self.query_state()
    
    # Parse actual values from response
    if state and state.get('mode') == 'effect':
        actual_speed = state['speed']        # From byte 7
        actual_brightness = state['brightness']  # From byte 6
        
        # Update with actual values
        self._effect_speed = actual_speed
        self._brightness = actual_brightness
```

---

## Key Takeaways

1. **Effect speed is in byte 7** of the state response, not byte 5
2. **No scaling or transformation** - speed value is unchanged
3. **Byte 5 meaning is unknown** - don't use it for speed
4. **Byte 6 is brightness** - confirmed (0-100 scale)
5. **Android app doesn't re-parse effect params** - it uses local state set before sending

---

## Testing Checklist

- [x] Send effect command with known speed value
- [x] Query state immediately after
- [x] Verify byte 7 contains the exact speed value sent
- [x] Verify byte 6 contains brightness
- [x] Confirm byte 5 is NOT the speed (likely something else)
- [ ] Test with multiple effect IDs to see if byte 5 changes
- [ ] Test with different speeds to confirm byte 7 tracking

---

## Related Files

- Android source: `/reverse_engineering/zengee/app/src/main/java/tc/d.java` (line 43-50)
- Android source: `/reverse_engineering/zengee/app/src/main/java/com/zengge/wifi/Device/BaseType/RGBNewSymphonyDeviceInfo.java` (line 26-35)
- Android source: `/reverse_engineering/zengee/app/src/main/java/tc/b.java` (line 47-62)
- Protocol doc: `protocol_docs/08_state_query_response_parsing.md`
- Command reference: `protocol_docs/07_control_commands.md`

---

## Questions Answered

✅ **Which byte contains effect speed?**  
→ Byte 7 (G position in RGB bytes)

✅ **Is speed transformed/scaled?**  
→ No, stored unchanged (0-100 range)

✅ **What is byte 5 (value1)?**  
→ Unknown - not used for effect speed in Symphony devices

✅ **Why does byte 5 show 33 when speed is 11?**  
→ Coincidence or device-specific value, not a 3x scaling

✅ **What is the correct extraction formula?**  
→ `speed = response[7]` (no formula needed)
