# EFFECTS AND ADDRESSABLE LED SUPPORT

## Effect Types Overview

The app supports **three distinct effect systems**, determined by device class (Product ID):

| Effect Type | Effect Count | ID Range | Devices |
|-------------|--------------|----------|---------|
| **Simple Effects** | 20 | 37-56 | Non-Symphony RGB devices |
| **Symphony Scene** | 44 | 1-44 | Symphony devices only |
| **Symphony Build** | 300 | 100-399 (UI) / 1-300 (internal) | Symphony devices only |

Effects are **hardcoded in the app**, NOT queried from devices.

## Effect Type Detection by Product ID

Source: `com/zengge/wifi/Device/a.java` method `k()`

The app uses **Product ID** to instantiate a device class, which determines effect support:

### Symphony Effect Devices

| Product ID | Device Class | Effects |
|------------|--------------|---------|
| 0xA1 (161) | `Ctrl_Mini_RGB_Symphony_0xa1` | Scene (44) + Build (300) |
| 0xA2 (162) | `Ctrl_Mini_RGB_Symphony_new_0xa2` | Scene (44) + Build (300) |
| 0xA3 (163) | `Ctrl_Mini_RGB_Symphony_new_0xA3` | Scene (44) + Build (300) |
| 0xA4 (164) | `Ctrl_Mini_RGB_Symphony_new_0xA4` | Scene (44) + Build (300) |
| 0xA6 (166) | `Ctrl_Mini_RGB_Symphony_new_0xA6` | Scene (44) + Build (300) |
| 0xA7 (167) | `Ctrl_Mini_RGB_Symphony_new_0xA7` | Scene (44) + Build (300) |
| 0xA9 (169) | `Ctrl_Mini_RGB_Symphony_new_0xA9` | Scene (44) + Build (300) |
| 0x08 (8) | `Ctrl_Mini_RGB_Mic_0x08` | Symphony + Mic |

### Simple Effect Devices

| Product ID | Device Class | Effects |
|------------|--------------|---------|
| 0x33 (51) | `Ctrl_Mini_RGB_0x33` | Simple (20) |
| 0x06 (6) | `Ctrl_Mini_RGBW_0x06` | Simple (20) |
| 0x04 (4) | `Ctrl_RGBW_UFO_0x04` | Simple (20) |
| 0x44 (68) | `Bulb_RGBW_0x44` | Simple (20) |
| Other RGB | Various | Simple (20) |

### No Effect Devices

| Product ID | Device Class | Notes |
|------------|--------------|-------|
| 0x52 (82) | `Bulb_CCT_0x52` | CCT only |
| 0x41 (65) | `Ctrl_Dim_0x41` | Dimmer only |
| 0x93-0x97 | Switch devices | On/Off only |

## Effect Command Formats

**CRITICAL**: Different device types use different effect command formats!

### ADDRESSABLE_0x53 Format (Ring Lights) - NO CHECKSUM

Used by: Product IDs 0, 29, 83 (Ring Lights)
Source: `model_0x53.py` set_effect() method

**Format (4 bytes, NO checksum):**
```
[0x38, effect_id, speed, brightness]
```

| Byte | Field       | Range    | Description                    |
|------|-------------|----------|--------------------------------|
| 0    | Command     | 0x38     | Effect command opcode          |
| 1    | Effect ID   | 1-113, 255 | Effect number (255=cycle all)|
| 2    | Speed       | 0-100    | Effect speed percentage        |
| 3    | Brightness  | 0-100    | Effect brightness percentage   |

**Example:** Effect 1 "Gold Ring" at speed 50, brightness 100
```
Wrapped: 00 00 80 00 00 04 05 0b 38 01 32 64
         [----transport header---] ^  ^  ^  ^
                                   |  |  |  brightness (100)
                                   |  |  speed (50)
                                   |  effect_id (1)
                                   command (0x38)
```

**NO CHECKSUM** - The 4th byte is brightness, NOT a checksum!

### SYMPHONY Format - WITH CHECKSUM

Used by: Product IDs 161-169 (Symphony controllers)
Source: Protocol documentation, Symphony device classes

**Format (5 bytes, WITH checksum):**
```
[0x38, effect_id, speed, brightness, checksum]
```

| Byte | Field       | Range    | Description                    |
|------|-------------|----------|--------------------------------|
| 0    | Command     | 0x38     | Effect command opcode          |
| 1    | Effect ID   | 1-44     | Scene effect, or 1-300 internal for build |
| 2    | Speed       | 0-255    | Effect speed                   |
| 3    | Brightness  | 0-100    | Effect brightness percentage   |
| 4    | Checksum    | 0-255    | Sum of bytes 0-3 & 0xFF        |

### SIMPLE Format (0x61 Command)

Used by: Non-Symphony RGB devices
Source: `dd/g.java`

**Format (5 bytes):**
```
[0x61, effect_id, speed, persist, checksum]
```

| Byte | Field       | Range    | Description                    |
|------|-------------|----------|--------------------------------|
| 0    | Command     | 0x61     | Legacy effect command          |
| 1    | Effect ID   | 37-56    | Simple effect number           |
| 2    | Speed       | 0-255    | Effect speed                   |
| 3    | Persist     | 0x0F/0xF0| 0xF0=persist, 0x0F=temporary  |
| 4    | Checksum    | 0-255    | Sum of bytes 0-3 & 0xFF        |

---

## Simple Effects (IDs 37-56)

Source: `dd/g.java` method `k()`

These are the classic "magic light" effects for non-Symphony RGB devices:

| ID | Effect Name |
|----|-------------|
| 37 | Seven color cross fade |
| 38 | Red gradual change |
| 39 | Green gradual change |
| 40 | Blue gradual change |
| 41 | Yellow gradual change |
| 42 | Cyan gradual change |
| 43 | Purple gradual change |
| 44 | White gradual change |
| 45 | Red/green cross fade |
| 46 | Red/blue cross fade |
| 47 | Green/blue cross fade |
| 48 | Seven color strobe flash |
| 49 | Red strobe flash |
| 50 | Green strobe flash |
| 51 | Blue strobe flash |
| 52 | Yellow strobe flash |
| 53 | Cyan strobe flash |
| 54 | Purple strobe flash |
| 55 | White strobe flash |
| 56 | Seven color jumping change |

String resources: `java_Mode_01` through `java_Mode_20`

## Symphony Effects

Symphony devices support two effect categories:

### Symphony Scene Effects (IDs 1-44)

Source: `dd/i.java` method `f()`

See `12_symphony_effect_names.md` for complete list with UI types.

### Symphony Build Effects (IDs 100-399)

Source: `dd/i.java` method `i()`

- Internal IDs: 1-300
- UI Display IDs: 100-399 (internal + 99)
- String resources: `symphony_SymphonyBuild_{N}` where N = 1-300

See `12_symphony_effect_names.md` for complete list.

## Device Class Hierarchy for Effects

Source: Device class declarations in `com/zengge/wifi/Device/Type/`

### Interface Markers (hd.* package)

Symphony devices implement specific interfaces:

| Interface | Purpose | Method |
|-----------|---------|--------|
| `hd.g` | Full Symphony support | `h()` - advanced features |
| `hd.h` | Segment/LED count | `b()` - LED count, `n(int)` - set segments |
| `hd.f` | Dimming curves | `i()` - returns boolean |

### Base Type Classes

| Base Class | Effect Support |
|------------|----------------|
| `RGBSymphonyDeviceInfo` | Symphony (older devices) |
| `RGBNewSymphonyDeviceInfo` | Symphony (newer devices) |
| `RGBDeviceInfo` | Simple effects only |
| `CCTDeviceInfo` | No effects |
| `BrightnessDeviceInfo` | No effects |

## Effect Type Detection Logic

```python
def get_effect_type(product_id: int) -> str:
    """
    Determine effect type based on Product ID.
    
    Source: com/zengge/wifi/Device/a.java method k()
    """
    # Symphony device Product IDs
    symphony_ids = {0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xA7, 0xA9, 0x08}
    
    # RGB devices that support simple effects
    simple_effect_ids = {0x33, 0x06, 0x04, 0x07, 0x20, 0x26, 0x27, 
                         0x44, 0x48, 0x3B, 0x35, 0x25, 0x0E, 0x1E}
    
    # No-effect devices (CCT, Dimmer, Switch)
    no_effect_ids = {0x52, 0x41, 0x62, 0x09, 0x16, 0x17, 0x1C,
                     0x93, 0x94, 0x95, 0x96, 0x97}
    
    if product_id in symphony_ids:
        return "symphony"  # 44 scene + 300 build effects
    elif product_id in simple_effect_ids:
        return "simple"    # 20 effects (IDs 37-56)
    elif product_id in no_effect_ids:
        return "none"
    else:
        return "unknown"   # Probe with effect command
```

## Addressable vs Global-Color LEDs

- **Symphony/Digital families** (productIds 161-169, 209) = addressable LEDs
- **Plain RGB/RGBW/RGBCW/CCT classes** = global color (entire strip changes)

### Detection

If productId in Symphony/Digital family → addressable.
Verify by sending effect command and observing response.

## Segment/Addressable LED Detection

### Method 1: Product ID Lookup

Symphony devices (0xA1-0xA9) and Digital Light (0xD1) support addressable LEDs:

| Product ID | Name                             | Segments | IC Config |
|------------|----------------------------------|----------|-----------|
| 0xA1 (161) | Ctrl_Mini_RGB_Symphony_0xa1      | Yes      | Yes       |
| 0xA2 (162) | Ctrl_Mini_RGB_Symphony_new_0xa2  | Yes      | Yes       |
| 0xA3 (163) | Ctrl_Mini_RGB_Symphony_new_0xA3  | Yes      | Yes       |
| 0xA4 (164) | Ctrl_Mini_RGB_Symphony_new_0xA4  | Yes      | Yes       |
| 0xA6 (166) | Ctrl_Mini_RGB_Symphony_new_0xA6  | Yes      | Yes       |
| 0xA7 (167) | Ctrl_Mini_RGB_Symphony_new_0xA7  | Yes      | Yes       |
| 0xA9 (169) | Ctrl_Mini_RGB_Symphony_new_0xA9  | Yes      | Yes       |
| 0xD1 (209) | Digital_Light_0xd1               | Yes      | No        |

### Method 2: LED Settings Response (0x63)

The most reliable way to detect addressable LED support is to query LED settings
and check for a valid 0x63 response.

There are TWO different query/response formats depending on device type:

- **Original format** (0x63): Used by most Symphony devices
- **A3+ format** (0x44): Used by newer A3+ Symphony devices with extended features

---

## Original LED Settings Protocol (0x63)

Source: tc/b.java methods f0(), B(), and inner class a.g()

### Query Command (f0 method)

```java
// tc/b.java f0() - lines 1386-1392
byte[] bArr = new byte[5];
bArr[0] = 99;   // 0x63
bArr[1] = 18;   // 0x12
bArr[2] = 33;   // 0x21
bArr[3] = -16;  // 0xF0 (persist flag)
bArr[4] = checksum;
```

Query: `[0x63, 0x12, 0x21, 0xF0, checksum]`

Wrapped: `00 02 80 00 00 05 06 0a 63 12 21 f0 86`

### Response Format (0x63 - 12 bytes)

Source: tc/b.java inner class a, method g() lines 180-195

If the device supports addressable LEDs, it responds with:

| Byte | Field          | Description                              | Java Source                                |
|------|----------------|------------------------------------------|--------------------------------------------|
| 0    | Header         | 0x63                                     | `bArr[0] != 99` check                      |
| 1-2  | LED Count      | Big-endian 16-bit LED count              | `g2.c.a(new byte[]{bArr[2], bArr[1]})`     |
| 3    | IC Type        | Chip type code (see table below)         | `symphonyICTypeItem.f24022a = bArr[3]`     |
| 4    | Color Order    | RGB color order code                     | `symphonyICTypeItem.f24024c = bArr[4]`     |
| 5    | Param D        | Timing parameter                         | `symphonyICTypeItem.f24025d = bArr[5]`     |
| 6    | Param E        | Timing parameter                         | `symphonyICTypeItem.f24026e = bArr[6]`     |
| 7    | Param F        | Timing parameter                         | `symphonyICTypeItem.f24027f = bArr[7]`     |
| 8-9  | Frequency      | Big-endian 16-bit refresh frequency (Hz) | `g2.c.a(new byte[]{bArr[9], bArr[8]})`     |
| 10   | Unknown        | Reserved (color order in some contexts)  | `bArr[10] & 255`                           |
| 11   | Checksum       | Sum of bytes 0-10                        | `b.b(bArr, 11)`                            |

Note: The Java code parses LED count separately from SymphonyICTypeItem. The g() method
only populates IC type, color order, timing params, and frequency into the item object.
LED count is extracted independently using `g2.c.a(new byte[]{bArr[2], bArr[1]})`.

### Set Command - Original Format (B method - 13 bytes)

Source: tc/b.java method B() lines 518-531

```java
// B(int ledCount, SymphonyICTypeItem item, int unknown)
public static byte[] B(int i10, SymphonyICTypeItem symphonyICTypeItem, int i11) {
    byte[] bArrC = g2.c.c(i10);           // Convert LED count to 2 bytes
    byte[] bArrC2 = g2.c.c(symphonyICTypeItem.f24028g);  // Frequency to 2 bytes
    byte[] bArr = new byte[13];
    bArr[0] = 98;                          // 0x62
    bArr[1] = bArrC[1];                    // LED count low byte
    bArr[2] = bArrC[0];                    // LED count high byte
    bArr[3] = (byte) symphonyICTypeItem.f24022a;  // IC Type
    bArr[4] = (byte) symphonyICTypeItem.f24024c;  // Color Order
    bArr[5] = (byte) symphonyICTypeItem.f24025d;  // Param D
    bArr[6] = (byte) symphonyICTypeItem.f24026e;  // Param E
    bArr[7] = (byte) symphonyICTypeItem.f24027f;  // Param F
    bArr[8] = bArrC2[1];                   // Frequency low byte
    bArr[9] = bArrC2[0];                   // Frequency high byte
    bArr[10] = (byte) i11;                 // Unknown parameter
    bArr[11] = -16;                        // 0xF0 persist flag
    bArr[12] = b(bArr, 12);                // Checksum
    return bArr;
}
```

| Byte | Field          | Description                    |
|------|----------------|--------------------------------|
| 0    | Header         | 0x62                           |
| 1    | LED Count Lo   | Low byte of LED count          |
| 2    | LED Count Hi   | High byte of LED count         |
| 3    | IC Type        | Chip type code                 |
| 4    | Color Order    | RGB order code                 |
| 5    | Param D        | Timing parameter               |
| 6    | Param E        | Timing parameter               |
| 7    | Param F        | Timing parameter               |
| 8    | Frequency Lo   | Low byte of frequency          |
| 9    | Frequency Hi   | High byte of frequency         |
| 10   | Unknown        | Reserved/extra parameter       |
| 11   | Persist        | 0xF0 = persist, 0x0F = temp    |
| 12   | Checksum       | Sum of bytes 0-11              |

---

## A3+ LED Settings Protocol (0x44)

Source: tc/b.java method d0(), SymphonySettingForA3.java

A3+ devices use an extended protocol with support for:

- Segments (parallel strip sections)
- Music-reactive LED settings
- 4th channel (RGBW) detection

### Query Command (d0 method)

Source: tc/b.java method d0() lines 1336-1343

```java
// tc/b.java d0()
byte[] bArr = new byte[5];
bArr[0] = 68;   // 0x44
bArr[1] = 74;   // 0x4A
bArr[2] = 75;   // 0x4B
bArr[3] = persist ? -16 : 15;  // 0xF0 or 0x0F
bArr[4] = checksum;
```

Query: `[0x44, 0x4A, 0x4B, persist, checksum]`

### Response Format (A3+ - 10 bytes payload)

Source: SymphonySettingForA3.java inner class a, method c() lines 130-148

```java
// Response callback in SymphonySettingForA3.java
public void c(byte[] bArr) {
    f24959w = bArr[0] == 1;                              // Has 4th channel (RGBW)
    f24953l = g2.c.a(new byte[]{bArr[3], bArr[2]});      // LED count
    f24954m = g2.c.a(new byte[]{bArr[5], bArr[4]});      // Segments
    f24957q = bArr[6] & 255;                             // IC Type
    f24958t = bArr[7] & 255;                             // Color Order
    f24955n = bArr[8] & 255;                             // Music LED count
    f24956p = bArr[9] & 255;                             // Music segments
}
```

| Byte | Field              | Description                          | Java Field      |
|------|--------------------|--------------------------------------|-----------------|
| 0    | Has 4th Channel    | 1 = RGBW, 0 = RGB                    | `f24959w`       |
| 1    | LED Count Hi       | High byte (note: bytes swapped)      | —               |
| 2    | LED Count Lo       | Low byte                             | `f24953l`       |
| 3    | Segments Hi        | High byte (note: bytes swapped)      | —               |
| 4    | Segments Lo        | Low byte                             | `f24954m`       |
| 5    | IC Type            | Chip type code                       | `f24957q`       |
| 6    | Color Order        | RGB order code                       | `f24958t`       |
| 7    | Music LED Count    | LED count for music reactive modes   | `f24955n`       |
| 8    | Music Segments     | Segments for music reactive modes    | `f24956p`       |

Note: Response bytes 1-2 and 3-4 are swapped when parsing (big-endian to little-endian conversion).

### Set Command - A3+ Format (C method - 11 bytes)

Source: tc/b.java method C() lines 533-547

```java
// C(ledCount, segments, icType, colorOrder, musicLedCount, musicSegments)
public static byte[] C(int i10, int i11, int i12, int i13, int i14, int i15) {
    byte[] bArrC = g2.c.c(i10);    // LED count to 2 bytes
    byte[] bArrC2 = g2.c.c(i11);   // Segments to 2 bytes
    byte[] bArr = new byte[11];
    bArr[0] = 98;                   // 0x62
    bArr[1] = bArrC[1];             // LED count low
    bArr[2] = bArrC[0];             // LED count high
    bArr[3] = bArrC2[1];            // Segments low
    bArr[4] = bArrC2[0];            // Segments high
    bArr[5] = (byte) i12;           // IC Type
    bArr[6] = (byte) i13;           // Color Order
    bArr[7] = (byte) i14;           // Music LED count
    bArr[8] = (byte) i15;           // Music segments
    bArr[9] = -16;                  // 0xF0 persist
    bArr[10] = b(bArr, 10);         // Checksum
    return bArr;
}
```

| Byte | Field              | Description                    |
|------|--------------------|--------------------------------|
| 0    | Header             | 0x62                           |
| 1    | LED Count Lo       | Low byte of LED count          |
| 2    | LED Count Hi       | High byte of LED count         |
| 3    | Segments Lo        | Low byte of segments           |
| 4    | Segments Hi        | High byte of segments          |
| 5    | IC Type            | Chip type code                 |
| 6    | Color Order        | RGB order code                 |
| 7    | Music LED Count    | LEDs for music mode            |
| 8    | Music Segments     | Segments for music mode        |
| 9    | Persist            | 0xF0 = persist, 0x0F = temp    |
| 10   | Checksum           | Sum of bytes 0-9               |

Called from SymphonySettingForA3.java line 328:

```java
tc.b.C(this.f24953l, this.f24954m, this.f24957q, this.f24958t, this.f24955n, this.f24956p)
//     ledCount,     segments,     icType,       colorOrder,   musicCount,   musicSeg
```

---

## IC Chip Types

Source: dd/i.java methods k(), l(), m(); SymphonyICTypeItem.java

| Code | Chip Name   | Notes                            |
|------|-------------|----------------------------------|
| 1    | UCS1903     | Slower timing                    |
| 2    | SM16703     | Fast timing                      |
| 3    | WS2811      | 12V external IC                  |
| 4    | WS2812B     | Most common 5V integrated        |
| 5    | SK6812      | Compatible with WS2812B          |
| 6    | INK1003     | Alternative IC                   |
| 7    | WS2801      | SPI-based, 2 data lines          |
| 8    | WS2815      | 12V with backup data line        |
| 9    | APA102      | SPI-based, high speed            |
| 10   | TM1914      | Alternative IC                   |
| 11   | UCS2904B    | Higher current support           |

## Color Order Codes

| Code | Order |
|------|-------|
| 0    | RGB   |
| 1    | RBG   |
| 2    | GRB   |
| 3    | GBR   |
| 4    | BRG   |
| 5    | BGR   |

## SymphonyICTypeItem Structure

Source: com/zengge/wifi/Model/SymphonyICTypeItem.java

```java
public class SymphonyICTypeItem {
    public int f24022a;  // IC Type code
    public String b;     // Display name
    public int f24024c;  // Color Order
    public int f24025d;  // Timing param D
    public int f24026e;  // Timing param E
    public int f24027f;  // Timing param F
    public int f24028g;  // Refresh frequency (Hz)
}
```

---

## Detection Logic

```python
def has_segment_support(product_id: int, led_settings_response: bytes) -> bool:
    """
    Determine if device supports addressable LED segments.
    
    1. Check product ID for Symphony/Digital device types
    2. If unknown product ID, query LED settings (0x63 or 0x44 command)
    3. Valid response confirms addressable LED support
    """
    # Known Symphony product IDs
    symphony_ids = {161, 162, 163, 164, 166, 167, 169, 209}
    
    if product_id in symphony_ids:
        return True
    
    # Check for valid 0x63 response (original format)
    if led_settings_response and len(led_settings_response) >= 12:
        if led_settings_response[0] == 0x63:
            # Verify checksum
            expected = sum(led_settings_response[:11]) & 0xFF
            actual = led_settings_response[11]
            return expected == actual
    
    return False


def query_led_settings(device_type: str) -> bytes:
    """
    Build appropriate LED settings query based on device type.
    """
    if device_type == "A3+":
        # A3+ format: [0x44, 0x4A, 0x4B, persist, checksum]
        cmd = bytearray([0x44, 0x4A, 0x4B, 0xF0])
        cmd.append(sum(cmd) & 0xFF)
        return bytes(cmd)
    else:
        # Original format: [0x63, 0x12, 0x21, persist, checksum]
        cmd = bytearray([0x63, 0x12, 0x21, 0xF0])
        cmd.append(sum(cmd) & 0xFF)
        return bytes(cmd)
```

## 16-Segment Strip View

Symphony devices display a 16-segment preview in the app (StripView class).
This is UI only - the actual LED count is configurable via the 0x62 set command.

Source: com/zengge/wifi/activity/NewSymphony/view/StripView.java

## Default Values

From SymphonySettingForA3.java method d1() lines 336-341:

```java
private void d1() {
    this.f24953l = 30;   // Default LED count
    this.f24954m = 10;   // Default segments
    this.f24955n = 30;   // Default music LED count
    this.f24956p = 10;   // Default music segments
}
```

## Music Mode Constraints

From SymphonySettingForA3.java - music LED count × music segments must not exceed 960:

```java
if (f24955n * f24956p > 960) {
    f24956p = 960 / f24955n;
}
```
