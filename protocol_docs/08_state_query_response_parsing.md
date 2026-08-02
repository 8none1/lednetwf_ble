# STATE QUERY AND RESPONSE PARSING

## State Query Command (0x81)

Format (4 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x81                             |
| 1    | Sub-command 1   | 0x8A                             |
| 2    | Sub-command 2   | 0x8B                             |
| 3    | Checksum        | 0x40                             |

Command: `[0x81, 0x8A, 0x8B, 0x40]`

## State Response Format (14 bytes)

Source: tc/b.java method c() lines 47-62, DeviceState.java

| Byte | Field           | DeviceState Field | Description                      |
|------|-----------------|-------------------|----------------------------------|
| 0    | Header          | -                 | 0x81 (response identifier)       |
| 1    | Mode            | f23859c (via g()) | Current mode (0-255)             |
| 2    | Power State     | f23858b (via h()) | 0x23 = ON, other = OFF           |
| 3    | Mode Type       | f23862f           | 97/98/99 = static, other = effect|
| 4    | Sub-mode        | f23863g           | See mode table below             |
| 5    | Value1          | f23864h           | White brightness (0-100) in white mode |
| 6    | Red (R)         | f23865j           | Red channel (0-255)              |
| 7    | Green (G)       | f23866k           | Green channel (0-255)            |
| 8    | Blue (B)        | f23867l           | Blue channel (0-255)             |
| 9    | Warm White (WW) | f23868m           | Warm white (0-255)               |
| 10   | LED Version     | f23860d (via i()) | LED/firmware version - NOT brightness! |
| 11   | Cool White (CW) | f23869n           | Cool white (0-255)               |
| 12   | Reserved        | f23870p           | Device-specific                  |
| 13   | Checksum        | -                 | Sum of bytes 0-12 mod 256        |

### Byte 10 Clarification (LED Version, NOT Brightness)

**IMPORTANT**: Byte 10 is stored as `ledVersionNum` in the Java app, NOT brightness!
The app uses `u0()` to retrieve this value and checks it for firmware version features.
Never use this byte for brightness calculations.

### Mode Type (Byte 3) Values

| Value | Hex  | Meaning                          |
|-------|------|----------------------------------|
| 97    | 0x61 | Static color/white mode          |
| 98    | 0x62 | Music reactive mode              |
| 99    | 0x63 | LED settings response (different format) |
| 37    | 0x25 | Effect mode (Symphony/Addressable - effect ID in sub-mode) |
| 37-56 | 0x25-0x38 | SIMPLE effect mode - mode_type IS the effect ID |

> **These two rows overlap and cannot be told apart from the response alone.**
> Effect 37 (the first SIMPLE effect) is 0x25, the same value Symphony and
> Addressable devices use as the effect-mode marker. The device type must
> decide which reading applies: parse as a SIMPLE effect ID when the device
> uses SIMPLE effects, otherwise as the 0x25 marker with the ID in sub-mode.
> Getting this wrong reports effect 37 as some other effect entirely.
> See `ai_instructions/DISCOVERIES.md` and issue #99.

**SIMPLE Effect Mode (mode_type 37-56):**
For SIMPLE devices (e.g., product_id 0x33), when running effects like "Yellow gradual change"
(effect 41 = 0x29), the mode_type byte directly contains the effect ID rather than a mode
indicator.

Confirmed against a product 0x08 capture (issue #99), all checksums verified:

| Byte | Meaning |
|------|---------|
| 3 | Effect ID (37-56) |
| 4 | Sub-mode: **echo of the power state** (0x23=ON, 0x24=OFF), not a parameter |
| 5 | **Effect speed, inverted 1-31** (1 = fastest) |
| 6-8 | The colour the effect is showing at that instant, changes constantly |

Byte 5 was verified by pairing outbound `38{model}{speed}{bright}` commands
with the response they produced. A pair only discriminates when speed and
bright differ: `38 25 10 1E` (speed 16, bright 30) → value1 16, and
`38 25 1F 01` (speed 31, bright 1) → value1 31. Both match the speed. A third
pair, `38 25 01 01`, has both fields set to 1 and so proves nothing.

> **Brightness is NOT reported while an effect is running.** An earlier version
> of this document said byte 6 held the brightness in effect mode. That is
> wrong for this family: byte 6 is the red channel of the live effect colour.
> Treat brightness as unknown and keep the last commanded value.

The same applies to solid colour on these devices: sub-mode is the power-state
echo rather than one of the colour-mode markers in the table below, and the
RGB is in bytes 6-8 as usual.

### Sub-mode (Byte 4) Values (when Mode Type = 0x61)

| Value | Hex  | Meaning                          |
|-------|------|----------------------------------|
| 240   | 0xF0 | RGB mode                         |
| 15    | 0x0F | White/CCT mode                   |
| 1     | 0x01 | RGB mode (variant)               |
| 11    | 0x0B | Music mode (treated as RGB)      |

### Brightness Derivation (Mode-Dependent)

**The Java app derives brightness differently based on mode:**

#### RGB Mode (sub-mode = 0xF0, 0x01, 0x0B)

Brightness is extracted from the RGB color using HSV conversion:

```java
// From g2/d.java method a():
float[] fArr = new float[3];
Color.colorToHSV(rgbColor, fArr);
float brightness = fArr[2];  // Value component (0.0-1.0)
```

In Python:
```python
import colorsys
r, g, b = response[6], response[7], response[8]
_, _, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
brightness = int(v * 255)  # 0-255 scale
```

#### White/CCT Mode (sub-mode = 0x0F)

Brightness comes from byte 5 (Value1), scaled from 0-100 to 0-255:

```java
// From model_0x53.py observation, confirmed by Java patterns
brightness = (byte5 * 255) / 100
```

In Python:
```python
if response[4] == 0x0F:  # White mode
    brightness = int(response[5] * 255 / 100)
```

#### Effect Mode (mode_type = 0x25)

Effect mode repurposes RGB bytes for effect parameters:
- Byte 6: Brightness (0-100, scale to 0-255)
- Byte 7: Effect speed (0-100)

```python
if response[3] == 0x25:  # Effect mode
    brightness = int(response[6] * 255 / 100)
    effect_speed = response[7]
```

## Python Response Parser

```python
def parse_state_response(response: bytes) -> dict:
    if len(response) < 14 or response[0] != 0x81:
        return None

    # Verify checksum
    if sum(response[:13]) & 0xFF != response[13]:
        return None

    return {
        'power_on': response[2] == 0x23,
        'mode': response[1],
        'mode_type': response[3],
        'speed': response[4],
        'red': response[6],
        'green': response[7],
        'blue': response[8],
        'warm_white': response[9],
        'brightness': response[10],
        'cool_white': response[11],
    }
```

## Optimized State Detection

For Home Assistant or other polling applications:

1. **Use BLE advertisements for state (BLE v5+ devices)**:
   - Check if state_data is present in manufacturer data advertisement
   - Parse state from manufacturer data (see file 03 for format details)
   - No need to connect/query for every state update
   - Only connect when sending commands

2. **Query state only when needed (older devices)**:
   - Send 0x81 query command
   - Wait for 14-byte response
   - Parse state fields

3. **Cache capabilities**:
   - Device capabilities don't change after initial detection
   - No need to re-query chip_type, led_count, color_order
   - Store these in device configuration

**Cross-reference**: See file 03 (Manufacturer Data Parsing) for details on state_data embedded in BLE advertisements (bytes 14-24 in Format B).

### Detection Strategy for Unknown Devices

When probing a new device:

1. Try sending the standard state query (0x81, 0x8A, 0x8B, checksum)
2. Wait up to 3 seconds for a notification response
3. If no response:
   - Check if state_data is present in manufacturer data advertisement
   - Parse state from manufacturer data bytes 14-24
   - Use product_id and sta byte to determine capabilities
4. Commands (color, power, effects) may still work even if state queries don't

### Java Source Reference

FillLight0x1D.java (com/zengge/wifi/Device/Type/):

- This is a "stub" device class with all methods returning null/0/false
- Product ID 0x1D = 29 (decimal)
- The Java app doesn't fully support this device type
- Control commands still work via BaseDeviceInfo inheritance
