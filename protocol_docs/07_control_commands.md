# CONTROL COMMANDS

## Checksum Calculation

All commands include a checksum byte as the last byte:

```python
def calculate_checksum(data: bytes) -> int:
    return sum(data) & 0xFF
```

## RGB Color Command (0x31)

Format (9 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x31 (49)                        |
| 1    | Red             | 0-255                            |
| 2    | Green           | 0-255                            |
| 3    | Blue            | 0-255                            |
| 4    | Warm White      | 0-255                            |
| 5    | Cool White      | 0-255                            |
| 6    | Mode            | 0x5A = RGB mode                  |
| 7    | Persist         | 0xF0 = save, 0x0F = don't save   |
| 8    | Checksum        | Sum of bytes 0-7                 |

### Examples

- Red:    `[0x31, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x5A, 0x0F, 0x2F]`
- Green:  `[0x31, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x5A, 0x0F, 0x30]`
- Blue:   `[0x31, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x5A, 0x0F, 0x31]`

### Python Implementation

```python
def set_rgbcw(r, g, b, ww=0, cw=0, persist=False):
    cmd = bytearray([0x31, r&0xFF, g&0xFF, b&0xFF, ww&0xFF, cw&0xFF,
                     0x5A, 0xF0 if persist else 0x0F])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

### Command Format Variants

Different devices require different 0x31 command formats. The format depends on
the device's product ID and BLE version.

Source: tc/b.java methods t(), v(), x() and Protocol/r.java

#### Format Selection Logic

From Protocol/r.java, the app selects the format based on:

```java
// Simplified logic from Protocol/r.java method q()
if (productId in [68, 84, 6, 72]) {
    // Use tc.b.x() - 8-byte format with mode
} else if (R0(deviceInfo) || productId == 37) {
    // Use tc.b.t() - 9-byte format
} else if (productId in [51, 8, 4, 161]) {
    // Use tc.b.v() - 8-byte format
} else if (E(deviceInfo)) {  // BLE v5+
    // Use tc.d.a() - Symphony 0x3B command
} else {
    // Default: tc.b.x() - 8-byte format with mode
}
```

#### 9-Byte Format - tc.b.t()

Used by: Product IDs checked via R0() function, Product ID 37

```text
[0x31, R, G, B, WW, CW, 0xF0, persist, checksum]
```

| Byte | Field      | Value                    |
|------|------------|--------------------------|
| 0    | Command    | 0x31                     |
| 1    | Red        | 0-255                    |
| 2    | Green      | 0-255                    |
| 3    | Blue       | 0-255                    |
| 4    | Warm White | 0-255                    |
| 5    | Cool White | 0-255                    |
| 6    | Mode       | 0xF0 (240)               |
| 7    | Persist    | 0xF0 or 0x0F             |
| 8    | Checksum   | Sum of bytes 0-7         |

#### 8-Byte Format (v) - tc.b.v()

Used by: Product IDs 51, 8, 4, 161

```text
[0x31, R, G, B, W, 0x00, persist, checksum]
```

| Byte | Field      | Value                    |
|------|------------|--------------------------|
| 0    | Command    | 0x31                     |
| 1    | Red        | 0-255                    |
| 2    | Green      | 0-255                    |
| 3    | Blue       | 0-255                    |
| 4    | White      | 0-255 (single WW channel)|
| 5    | Reserved   | 0x00                     |
| 6    | Persist    | 0xF0 or 0x0F             |
| 7    | Checksum   | Sum of bytes 0-6         |

#### 8-Byte Format (x) - tc.b.x()

Used by: Product IDs 68, 84, 6, 72, and as default for unknown devices (BLE < v5)

```text
[0x31, R, G, B, W, mode, persist, checksum]
```

| Byte | Field      | Value                    |
|------|------------|--------------------------|
| 0    | Command    | 0x31                     |
| 1    | Red        | 0-255                    |
| 2    | Green      | 0-255                    |
| 3    | Blue       | 0-255                    |
| 4    | White      | 0-255                    |
| 5    | Mode       | 0x0F if W>0, else 0xF0   |
| 6    | Persist    | 0xF0 or 0x0F             |
| 7    | Checksum   | Sum of bytes 0-6         |

Note: Mode byte 5 indicates whether RGB (0xF0) or White (0x0F) is active.

#### 9-Byte White/CCT Format - tc.b.f()

Used for: Setting CCT (warm white + cool white) without RGB

Source: tc/b.java method f() lines 1368-1385

```text
[0x31, 0x00, 0x00, 0x00, WW, CW, 0x0F, persist, checksum]
```

| Byte | Field      | Value                    |
|------|------------|--------------------------|
| 0    | Command    | 0x31                     |
| 1    | Red        | 0x00 (off)               |
| 2    | Green      | 0x00 (off)               |
| 3    | Blue       | 0x00 (off)               |
| 4    | Warm White | 0-255                    |
| 5    | Cool White | 0-255                    |
| 6    | Mode       | 0x0F (white mode)        |
| 7    | Persist    | 0xF0 or 0x0F             |
| 8    | Checksum   | Sum of bytes 0-7         |

```java
// tc/b.java method f()
public static byte[] f(int i10, int i11, boolean z10) {
    byte[] bArr = new byte[9];
    bArr[0] = 49;           // 0x31
    bArr[1] = 0;            // R = 0
    bArr[2] = 0;            // G = 0
    bArr[3] = 0;            // B = 0
    bArr[4] = (byte) i10;   // Warm White
    bArr[5] = (byte) i11;   // Cool White
    bArr[6] = 15;           // 0x0F = white mode
    bArr[7] = z10 ? -16 : 15;  // persist flag
    bArr[8] = b(bArr, 8);   // checksum
    return bArr;
}
```

**Mode Byte Values (byte 6):**

| Value | Hex  | Mode        | Description                     |
|-------|------|-------------|---------------------------------|
| 90    | 0x5A | RGBCW       | All channels active             |
| 240   | 0xF0 | RGB only    | RGB mode, whites ignored        |
| 15    | 0x0F | White only  | White mode, RGB ignored         |

#### 9-Byte Full RGBCW Format - tc.b.s()

Used for: Setting RGB and white channels simultaneously

Source: tc/b.java method s() lines 1712-1728

```text
[0x31, R, G, B, WW, CW, 0x5A, persist, checksum]
```

| Byte | Field      | Value                    |
|------|------------|--------------------------|
| 0    | Command    | 0x31                     |
| 1    | Red        | 0-255                    |
| 2    | Green      | 0-255                    |
| 3    | Blue       | 0-255                    |
| 4    | Warm White | 0-255                    |
| 5    | Cool White | 0-255                    |
| 6    | Mode       | 0x5A (RGBCW mode)        |
| 7    | Persist    | 0xF0 or 0x0F             |
| 8    | Checksum   | Sum of bytes 0-7         |

```java
// tc/b.java method s()
public static byte[] s(int i10, int i11, int i12, int i13, int i14, boolean z10) {
    byte[] bArr = new byte[9];
    bArr[0] = 49;           // 0x31
    bArr[1] = (byte) i10;   // Red
    bArr[2] = (byte) i11;   // Green
    bArr[3] = (byte) i12;   // Blue
    bArr[4] = (byte) i13;   // Warm White
    bArr[5] = (byte) i14;   // Cool White
    bArr[6] = 90;           // 0x5A = RGBCW mode
    bArr[7] = z10 ? -16 : 15;  // persist flag
    bArr[8] = b(bArr, 8);   // checksum
    return bArr;
}
```

#### Symphony Format (0x3B) - tc.d.a()

Used by: BLE v5+ devices (when E() returns true)

See "HSV/Symphony Color Command (0x3B)" section below for format details.

This format uses HSV color values instead of RGB and is the preferred format
for modern devices with BLE protocol version 5 or higher.

---

## CCT Temperature Command (0x35)

Source: tc/b.java methods G(), H(), I() lines 603-644

For CCT-only devices (ceiling lights, etc.) that use color temperature control
instead of separate WW/CW channels.

### Format (9 bytes)

```text
[0x35, 0xB1, temp%, brightness%, 0x00, 0x00, duration_hi, duration_lo, checksum]
```

| Byte | Field           | Value                              |
|------|-----------------|-------------------------------------|
| 0    | Command opcode  | 0x35 (53)                           |
| 1    | Sub-command     | 0xB1 (177)                          |
| 2    | Temperature %   | 0-100 (0=warm/2700K, 100=cool/6500K)|
| 3    | Brightness %    | 0-100                               |
| 4    | Reserved        | 0x00                                |
| 5    | Reserved        | 0x00                                |
| 6    | Duration (hi)   | Transition duration × 10 (high byte)|
| 7    | Duration (lo)   | Transition duration × 10 (low byte) |
| 8    | Checksum        | Sum of bytes 0-7                    |

### Variants

**tc.b.G(ww, cw, duration)** - Calculate temperature from WW/CW values:

```java
// Temperature calculated as: (cw * 100) / (ww + cw)
bArr[2] = (byte) (i12 == 0 ? 0.0d : (i11 * 100.0d) / i12);  // temp%
bArr[3] = (byte) Math.round((i12 / 255.0f) * 100.0f);       // brightness%
```

**tc.b.H(brightness, duration)** - Fixed warm temperature (100%):

```java
bArr[2] = 100;                                              // temp% = 100 (warm)
bArr[3] = (byte) Math.round((i10 / 255.0f) * 100.0f);       // brightness%
```

**tc.b.I(brightness, duration)** - Fixed cool temperature (0%):

```java
bArr[2] = 0;                                                // temp% = 0 (cool)
bArr[3] = (byte) Math.round((i10 / 255.0f) * 100.0f);       // brightness%
```

### Duration Encoding

The duration is specified in tenths of a second:

- Duration value = seconds × 10
- Example: 0.3 seconds → `Math.round(0.3f * 10.0f)` = 3

```java
byte[] bArrB = g2.c.b(Math.round(f10 * 10.0f));  // f10 = duration in seconds
bArr[6] = bArrB[0];  // high byte
bArr[7] = bArrB[1];  // low byte
```

### Python Implementation

```python
def set_cct_temperature(temp_percent: int, brightness_percent: int, 
                        duration_sec: float = 0.3, persist: bool = False) -> bytes:
    """
    Set CCT color temperature.
    
    Args:
        temp_percent: 0-100 (0=warm/2700K, 100=cool/6500K)
        brightness_percent: 0-100
        duration_sec: Transition duration in seconds
    """
    duration = int(duration_sec * 10)
    cmd = bytearray([
        0x35,                           # Command
        0xB1,                           # Sub-command
        temp_percent & 0xFF,            # Temperature %
        brightness_percent & 0xFF,      # Brightness %
        0x00,                           # Reserved
        0x00,                           # Reserved
        (duration >> 8) & 0xFF,         # Duration high
        duration & 0xFF,                # Duration low
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)
```

### Example Commands

- Warm white (100%) at 50% brightness: `[0x35, 0xB1, 0x64, 0x32, 0x00, 0x00, 0x00, 0x03, 0x19]`
- Cool white (0%) at 100% brightness: `[0x35, 0xB1, 0x00, 0x64, 0x00, 0x00, 0x00, 0x03, 0xB7]`
- Neutral (50%) at 75% brightness: `[0x35, 0xB1, 0x32, 0x4B, 0x00, 0x00, 0x00, 0x03, 0xE6]`

---

## CCT Alternate Command (0x36)

Source: tc/b.java method F() lines 587-600

Alternative CCT command format used by some devices.

### Format (9 bytes)

```text
[0x36, 0xB1, brightness, temp_value, 0x00, 0x00, duration_hi, duration_lo, checksum]
```

| Byte | Field           | Value                              |
|------|-----------------|-------------------------------------|
| 0    | Command opcode  | 0x36 (54)                           |
| 1    | Sub-command     | 0xB1 (177)                          |
| 2    | Brightness      | Raw brightness value               |
| 3    | Temperature     | Raw temperature value              |
| 4    | Reserved        | 0x00                                |
| 5    | Reserved        | 0x00                                |
| 6    | Duration (hi)   | Transition duration × 10 (high byte)|
| 7    | Duration (lo)   | Transition duration × 10 (low byte) |
| 8    | Checksum        | Sum of bytes 0-7                    |

```java
// tc/b.java method F()
public static byte[] F(int i10, int i11, float f10, boolean z10) {
    byte[] bArrB = g2.c.b(Math.round(f10 * 10.0f));
    byte[] bArr = new byte[9];
    bArr[0] = 54;           // 0x36
    bArr[1] = -79;          // 0xB1
    bArr[2] = (byte) i10;   // brightness
    bArr[3] = (byte) i11;   // temperature
    bArr[4] = 0;
    bArr[5] = 0;
    bArr[6] = bArrB[0];     // duration high
    bArr[7] = bArrB[1];     // duration low
    bArr[8] = b(bArr, 8);   // checksum
    return bArr;
}
```

---

## Brightness Command (0x47)

Format (3 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x47 (71)                        |
| 1    | Brightness      | 0-255                            |
| 2    | Checksum        | Sum of bytes 0-1                 |

Example (50% brightness): `[0x47, 0x7F, 0xC6]`

## Power Commands

The power command format depends on the device's BLE protocol version.
Source: com/zengge/wifi/COMM/Protocol/q.java

### Version Detection Logic

```java
// From BaseDeviceInfo.E() - determines which power command to use
if (baseDeviceInfo.E()) {
    // BLE version >= 5: Use 0x3B command
    return tc.d.c(powerType.c(), 0, 0, 0, 0, 0, 0, 0);
}
// BLE version < 5: Use 0x71 command
return tc.b.M(z10, false);
```

### Modern Power Command (0x3B) - BLE v5+

**RECOMMENDED** - Works on most modern devices (BLE protocol version 5 and above).

Source: com/zengge/wifi/COMM/Protocol/CommandPackagePowerOverDuraion.java

PowerType enum values:
- `PowerType_PowerON` = **0x23 (35)**
- `PowerType_PowerOFF` = **0x24 (36)**
- `PowerType_PowerSwitch` = 0x25 (37) - toggle

Format (13 bytes before transport wrapper):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x3B (59)                        |
| 1    | PowerType       | 0x23=ON, 0x24=OFF, 0x25=toggle   |
| 2-3  | HSV (zeros)     | 0x00, 0x00                       |
| 4-6  | Params          | 0x00, 0x00, 0x00                 |
| 7-9  | Duration 1      | Typically 0x00, 0x00, 0x32 (50)  |
| 10-11| Duration 2      | 0x00, 0x00                       |
| 12   | Checksum        | Sum of bytes 0-11                |

#### Examples (with transport layer)

Power ON (pre-wrapped):
```
00 01 80 00 00 0d 0e 0b 3b 23 00 00 00 00 00 00 00 32 00 00 90
```

Power OFF (pre-wrapped):
```
00 01 80 00 00 0d 0e 0b 3b 24 00 00 00 00 00 00 00 32 00 00 91
```

### Legacy Power Command (0x71) - BLE v1-4

Source: tc/b.java method M() lines 759-772

Format (4 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x71 (113)                       |
| 1    | State           | 0x23=ON, 0x24=OFF                |
| 2    | Persist         | 0xF0=save, 0x0F=don't save       |
| 3    | Checksum        | Sum of bytes 0-2                 |

Examples:
- Power ON:  `[0x71, 0x23, 0x0F, 0xA3]`
- Power OFF: `[0x71, 0x24, 0x0F, 0xA4]`

### Very Old Power Command (0x11) - Legacy

Source: tc/b.java method m() lines 1648-1657

**NOTE:** This command may only work on very old devices. Most modern devices
ignore it and require 0x3B or 0x71 commands instead.

Format (5 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x11                             |
| 1    | Sub-command 1   | 0x1A                             |
| 2    | Sub-command 2   | 0x1B                             |
| 3    | State           | 0xF0 = ON, 0x0F = OFF            |
| 4    | Checksum        | Sum of bytes 0-3                 |

Examples:
- Power ON:  `[0x11, 0x1A, 0x1B, 0xF0, 0xE6]`
- Power OFF: `[0x11, 0x1A, 0x1B, 0x0F, 0x55]`

### Extended Power Command (0x72) - With timing

Source: tc/b.java method L() lines 740-756

Format (7 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x72 (114)                       |
| 1    | State           | 0x23=ON, 0x24=OFF                |
| 2-3  | Duration bytes  | From g2.c.c()                    |
| 4    | Persist         | 0xF0=save, 0x0F=don't save       |
| 5    | Always 1        | 0x01                             |
| 6    | Checksum        | Sum of bytes 0-5                 |

---

# EFFECT COMMANDS

There are multiple effect command formats depending on device type and firmware.
All command structures documented here are derived from the decompiled Java source code.

## Effect Command (0x38) - Two Variants

**IMPORTANT**: There are TWO different 0x38 command formats depending on device type!

### Variant 1: Symphony Devices (5 bytes with checksum)

Source: tc/d.java method d() lines 37-48

Used by: Symphony devices (product IDs 0xA1-0xA9, possibly others)

Format (5 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x38 (56)                        |
| 1    | Effect ID       | Effect number                    |
| 2    | Speed           | 0-255                            |
| 3    | Parameter       | Effect-specific (often 0)        |
| 4    | Checksum        | Sum of bytes 0-3                 |

Example (effect 5 at speed 128): `[0x38, 0x05, 0x80, 0x00, 0xBD]`

```java
// tc/d.java method d()
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

### Variant 2: Addressable LED Strip Devices (4 bytes, NO checksum)

Source: Working Python implementation (model_0x53.py, model_0x54.py, model_0x56.py)

Used by: Addressable LED strip controllers (sta bytes 0x53, 0x54, 0x56, product IDs 0x001D, etc.)

**Format (4 bytes - NO CHECKSUM):**

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x38 (56)                        |
| 1    | Effect ID       | Effect number (1-93+)            |
| 2    | Speed           | 0-255                            |
| 3    | Brightness      | 0-100 (percentage!)              |

**CRITICAL**: The raw payload is only 4 bytes before transport wrapping. NO checksum byte!

Example (effect 1, speed 50, brightness 100%):
```
Raw payload: [0x38, 0x01, 0x32, 0x64]
Wrapped: 00 00 80 00 00 04 05 0b 38 01 32 64
         └──────transport────┘ └─payload──┘
                               ^  ^  ^  ^
                               |  |  |  └─ brightness (0x64 = 100%)
                               |  |  └──── speed (0x32 = 50)
                               |  └─────── effect_id (0x01)
                               └────────── command (0x38)
```

**Python Implementation:**
```python
def build_addressable_effect_0x38(effect_id: int, speed: int, brightness: int) -> bytearray:
    """
    Build effect command for addressable LED devices (0x53, 0x54, 0x56).
    
    Args:
        effect_id: Effect number (1-93+)
        speed: Effect speed (0-255)
        brightness: Brightness percentage (0-100)
    
    Returns:
        Wrapped command packet
    """
    raw_cmd = bytearray([
        0x38,
        effect_id & 0xFF,
        speed & 0xFF,
        brightness & 0xFF,  # Brightness in percent (0-100)
    ])
    # NO CHECKSUM for this variant!
    return wrap_command(raw_cmd, cmd_family=0x0b)
```

**Device Classification:**
- 0x53 devices: 93+ custom effects
- 0x54 devices: Similar effect set
- 0x56 devices: Similar effect set
- These are NOT "Simple Effects" (37-56) or "Symphony Effects" (1-44)
- Each sta byte has its own custom effect list

## Effect Command (0x61) - Built-in Mode Effects

Source: tc/b.java method c() lines 1283-1293

For devices with built-in effect modes (legacy format):

### 5-byte format:

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x61 (97)                        |
| 1    | Effect ID       | Effect number                    |
| 2    | Speed           | 0-255 (signed byte in Java)      |
| 3    | Persist         | 0xF0=save, 0x0F=don't save       |
| 4    | Checksum        | Sum of bytes 0-3                 |

```java
// tc/b.java method c()
public static byte[] c(int i10, byte b10, boolean z10) {
    byte[] bArr = new byte[5];
    bArr[0] = 97;           // 0x61
    bArr[1] = (byte) i10;   // effect ID
    bArr[2] = b10;          // speed
    bArr[3] = z10 ? -16 : 15;  // 0xF0 or 0x0F persist
    bArr[4] = b(bArr, 4);   // checksum
    return bArr;
}
```

## Static Effect with FG/BG Colors (0x41) - Symphony Devices

Source: com/zengge/wifi/COMM/Protocol/l.java

For Symphony devices (product types 162/0xA2 and 163/0xA3) that support
foreground and background colors with effect animations.

Format (13 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x41 (65)                        |
| 1    | Effect Mode     | Effect/mode number               |
| 2    | Red (FG)        | Foreground red 0-255             |
| 3    | Green (FG)      | Foreground green 0-255           |
| 4    | Blue (FG)       | Foreground blue 0-255            |
| 5    | Red (BG)        | Background red 0-255             |
| 6    | Green (BG)      | Background green 0-255           |
| 7    | Blue (BG)       | Background blue 0-255            |
| 8    | Speed           | Effect speed 0-255               |
| 9    | Direction       | 0=forward, 1=reverse             |
| 10   | Reserved        | 0x00                             |
| 11   | Persist         | 0xF0 (240)                       |
| 12   | Checksum        | Sum of bytes 0-11                |

```java
// com/zengge/wifi/COMM/Protocol/l.java
private byte[] a(int i10, int i11, int i12, int i13, boolean z10, BaseDeviceInfo baseDeviceInfo) {
    byte[] bArr = new byte[13];
    bArr[0] = 65;                          // 0x41
    bArr[1] = (byte) i10;                  // effect mode
    bArr[2] = (byte) Color.red(i11);       // FG red
    bArr[3] = (byte) Color.green(i11);     // FG green
    bArr[4] = (byte) Color.blue(i11);      // FG blue
    bArr[5] = (byte) Color.red(i12);       // BG red
    bArr[6] = (byte) Color.green(i12);     // BG green
    bArr[7] = (byte) Color.blue(i12);      // BG blue
    bArr[8] = (byte) i13;                  // speed
    bArr[9] = (byte) (!z10 ? 1 : 0);       // direction (inverted bool)
    bArr[10] = 0;
    bArr[11] = -16;                        // 0xF0 persist
    bArr[12] = tc.b.b(bArr, 12);           // checksum
    return bArr;
}
```

**Usage Context:**
- Used by SettledModeFragment.java for "Settled Mode" effects
- Called via `new l(deviceList, effectMode, fgColor, bgColor, speed, direction)`
- FG/BG colors are Android Color ints (0xAARRGGBB format)

## RGB Color Commands (0x41 variants) - Non-Symphony

Source: tc/b.java methods w(), y(), z()

For non-Symphony devices, 0x41 is used as an alternative RGB color command
(similar to 0x31 but with different mode handling):

### 8-byte format - tc/b.java method w():

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x41 (65)                        |
| 1    | Red             | 0-255                            |
| 2    | Green           | 0-255                            |
| 3    | Blue            | 0-255                            |
| 4    | White           | 0-255                            |
| 5    | Reserved        | 0x00                             |
| 6    | Persist         | 0xF0=save, 0x0F=don't save       |
| 7    | Checksum        | Sum of bytes 0-6                 |

### 8-byte format with mode - tc/b.java method y():

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x41 (65)                        |
| 1    | Red             | 0-255                            |
| 2    | Green           | 0-255                            |
| 3    | Blue            | 0-255                            |
| 4    | White           | 0-255                            |
| 5    | Mode            | 0x0F if W>0, else 0xF0           |
| 6    | Persist         | 0xF0=save, 0x0F=don't save       |
| 7    | Checksum        | Sum of bytes 0-6                 |

## Custom Effect with Color Arrays (0xA3)

Source: tc/a.java method a() lines 8-49

For devices supporting custom color palettes with multiple foreground and
background colors (advanced Symphony devices):

Format (variable length):

| Byte | Field                 | Value                           |
|------|-----------------------|----------------------------------|
| 0    | Command opcode        | 0xA3 (-93 signed / 163 unsigned) |
| 1    | Effect ID             | builtinFuncUniID parsed as int   |
| 2    | Speed                 | Mapped from 0-100 to 1-31 range  |
| 3    | Brightness            | Fixed at 100                     |
| 4    | Color1 count          | Number of foreground colors (N)  |
| 5+   | Color1 array          | N * 3 bytes (R,G,B for each)     |
| -    | Color2 count          | Number of background colors (M)  |
| -    | Color2 array          | M * 3 bytes (R,G,B for each)     |
| last | Checksum              | Sum of all previous bytes        |

```java
// tc/a.java method a() - excerpt
bArr[0] = -93;                                    // 0xA3
bArr[1] = (byte) i12;                             // effect ID
bArr[2] = (byte) iRound;                          // speed (mapped 1-31)
bArr[3] = 100;                                    // brightness
bArr[4] = (byte) length;                          // color1 count
// ... color1 RGB values follow ...
bArr[i10] = (byte) length2;                       // color2 count
// ... color2 RGB values follow ...
bArr[i17] = b.b(bArr, i11 - 1);                   // checksum
```

**Speed Mapping:**
The speed is mapped from the UI range (0-100) to protocol range (1-31):
```java
int iRound = Math.round(g2.d.f(100.0f, 0.0f, 1.0f, 31.0f, customPickerParams.speed));
```

**Color Arrays:**
- `color1SelectedColors[]`: Foreground/primary colors (up to 7)
- `color2SelectedColors[]`: Background/secondary colors (up to 7)
- Each color is an Android Color int, extracted as RGB bytes

## Segment Color Command (0xA0)

Source: tc/a.java method b() lines 51-76

For setting individual segment colors on addressable LED strips:

Format (variable length):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0xA0 (-96 signed / 160 unsigned) |
| 1    | Reserved        | 0x00                             |
| 2    | Segment count   | Number of segments               |
| 3+   | Segment data    | 8 bytes per segment (see below)  |
| last | Checksum        | Sum of all previous bytes        |

Per-segment data (8 bytes):

| Offset | Field     | Value                |
|--------|-----------|----------------------|
| 0      | Reserved  | 0x00                 |
| 1      | Segment # | 1-based segment index|
| 2      | Red       | 0-255                |
| 3      | Green     | 0-255                |
| 4      | Blue      | 0-255                |
| 5      | Reserved  | 0x00                 |
| 6      | Reserved  | 0x00                 |
| 7      | End marker| 0xFF (-1 signed)     |

```java
// tc/a.java method b() - per-segment loop
bArr[i10] = 0;                            // reserved
bArr[i13] = (byte) i11;                   // segment number (1-based)
bArr[i14] = bRed;                         // red
bArr[i15] = bGreen;                       // green
bArr[i16] = bBlue;                        // blue
bArr[i17] = 0;                            // reserved
bArr[i18] = 0;                            // reserved
bArr[i19] = -1;                           // 0xFF end marker
```

---

## HSV/Symphony Color Command (0x3B)

Source: tc/d.java methods a(), b(), c() lines 8-35

Format (13 bytes) for Symphony/BLE v5+ devices:

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x3B (59)                        |
| 1    | Mode            | See mode table below             |
| 2    | Hue+Sat (hi)    | `(hue << 7 \| sat) >> 8`         |
| 3    | Hue+Sat (lo)    | `(hue << 7 \| sat) & 0xFF`       |
| 4    | Brightness      | 0-100                            |
| 5    | Param1          | Mode-specific                    |
| 6    | Param2          | Mode-specific                    |
| 7    | Red             | RGB red (from color int)         |
| 8    | Green           | RGB green                        |
| 9    | Blue            | RGB blue                         |
| 10   | Time (hi)       | Duration high byte               |
| 11   | Time (lo)       | Duration low byte                |
| 12   | Checksum        | Sum of bytes 0-11                |

### CRITICAL: Time Field (bytes 10-11)

**Use `0x00, 0x00` for instant response!**

The time field controls transition duration. Non-zero values cause significant delays (possibly interpreted as seconds, not milliseconds):

| Value | Result |
|-------|--------|
| `0x00, 0x00` | **Instant** - command executes immediately (RECOMMENDED) |
| `0x00, 0x1E` | ~30 second delay before execution |
| `0x00, 0x32` | ~50 second delay before execution |

The working Android app packets use `0x00, 0x00` for all color commands. Only use non-zero values if you specifically need a fade/transition effect and understand the timing.

**Example working color packet (raw payload):**

```text
3b a1 00 64 64 00 00 00 00 00 00 00 [checksum]
                           ^^ ^^ = time = 0 (instant)
```

### Mode Values (byte 1)

From FragmentUniteControl.java and CipherSuite constants:

| Mode  | Hex  | Name/Purpose              | Notes                          |
|-------|------|---------------------------|--------------------------------|
| 0x23  | 35   | Power ON                  | PowerType_PowerON              |
| 0x24  | 36   | Power OFF                 | PowerType_PowerOFF             |
| 0x25  | 37   | Power Toggle              | PowerType_PowerSwitch          |
| 0xA0  | 160  | Reserved                  | TLS_DH_RSA_WITH_AES_128_GCM    |
| 0xA1  | 161  | Solid Color (HSV)         | Main color mode                |
| 0xA2  | 162  | Mic-reactive              | TLS_DHE_DSS_WITH_AES_128_GCM   |
| 0xA3  | 163  | Music strip               | TLS_DHE_DSS_WITH_AES_256_GCM   |
| 0xA4  | 164  | Scene mode                | TLS_DH_DSS_WITH_AES_128_GCM    |
| 0xA5  | 165  | Multiple colors/gradient  | TLS_DH_DSS_WITH_AES_256_GCM    |
| 0xA6  | 166  | Animation                 | TLS_DH_anon_WITH_AES_128_GCM   |
| 0xA7  | 167  | Animation 2               | TLS_DH_anon_WITH_AES_256_GCM   |
| 0xAA  | 170  | Effect mode               | TLS_DHE_PSK_WITH_AES_128_GCM   |
| 0xB1  | 177  | CCT Temperature Mode      | TLS_PSK_WITH_NULL_SHA384       |
| 0xB2  | 178  | Special effect 2          | TLS_DHE_PSK_WITH_AES_128_CBC   |
| 0xB3  | 179  | Special effect 3          | TLS_DHE_PSK_WITH_AES_256_CBC   |
| 0xB4  | 180  | Brightness mode           | TLS_DHE_PSK_WITH_NULL_SHA256   |
| 0xB6  | 182  | Effect with params        | TLS_RSA_PSK_WITH_AES_128_CBC   |
| 0xC1  | 193  | Custom color mode         | TLS_DH_DSS_WITH_CAMELLIA_256   |
| 0xC2  | 194  | Multi-param mode          | TLS_DH_RSA_WITH_CAMELLIA_256   |

### HSV Encoding (bytes 2-3)

From Java source `tc/d.java` line 24:

```java
byte[] bArrB = g2.c.b((i11 << 7) | i12);
bArr[2] = bArrB[0];  // high byte
bArr[3] = bArrB[1];  // low byte
```

**Parameters:**
- `i11` = hue (0-360)
- `i12` = saturation (0-100, NOT 0-127!)

**Encoding formula:**

```python
packed = (hue << 7) | saturation
byte_hi = (packed >> 8) & 0xFF
byte_lo = packed & 0xFF
```

**Decoding formula:**

```python
packed = (byte_hi << 8) | byte_lo
hue = packed >> 7            # Range: 0-360
saturation = packed & 0x7F   # Range: 0-100
```

**Important**: Saturation is 0-100 (percentage), NOT scaled to 0-127!
The `& 0x7F` mask just ensures it fits in 7 bits.

### Color Conversion (tc/d.java method a)

```java
// Android Color.colorToHSV returns:
// fArr[0] = hue (0-360)
// fArr[1] = saturation (0.0-1.0)
// fArr[2] = value/brightness (0.0-1.0)

Color.colorToHSV(colorInt, fArr);
return c(0xA1,                           // mode = solid color
         Math.round(fArr[0]),            // hue 0-360
         Math.round(fArr[1] * 100.0f),   // sat 0-100 (scaled from 0-1)
         Math.round(fArr[2] * 100.0f),   // brightness 0-100
         0, 0,                           // params
         rgbColorInt,                    // original RGB for bytes 7-9
         0);                             // time
```

### RGB Extraction (bytes 7-9)

The RGB values are extracted from an Android Color int:

```java
bArr[7] = (byte) ((16711680 & i16) >> 16);  // Red:   (color & 0xFF0000) >> 16
bArr[8] = (byte) ((65280 & i16) >> 8);      // Green: (color & 0x00FF00) >> 8
bArr[9] = (byte) (i16 & 255);               // Blue:  color & 0x0000FF
```

### CCT Temperature Mode (0xB1)

Source: tc/d.java method c() and com/zengge/wifi/COMM/Protocol/c0.java

When mode byte is 0xB1 (177), the 0x3B command is used for CCT (color temperature)
control instead of RGB. This is an alternative to the 0x35 CCT command.

**Format for CCT mode:**

```text
[0x3B, 0xB1, 0x00, 0x00, 0x00, temp%, bright%, 0x00, 0x00, 0x00, time_hi, time_lo, checksum]
```

| Byte | Field           | Value for CCT mode                 |
|------|-----------------|-------------------------------------|
| 0    | Command opcode  | 0x3B (59)                           |
| 1    | Mode            | 0xB1 (177) = CCT Temperature Mode   |
| 2    | Hue+Sat (hi)    | 0x00 (unused)                       |
| 3    | Hue+Sat (lo)    | 0x00 (unused)                       |
| 4    | Brightness      | 0x00 (unused for CCT)               |
| 5    | Temperature %   | 0-100 (0=warm/2700K, 100=cool/6500K)|
| 6    | Brightness %    | 0-100                               |
| 7    | Red             | 0x00 (unused)                       |
| 8    | Green           | 0x00 (unused)                       |
| 9    | Blue            | 0x00 (unused)                       |
| 10   | Time (hi)       | Duration high byte (use 0x00)       |
| 11   | Time (lo)       | Duration low byte (use 0x00 for instant) |
| 12   | Checksum        | Sum of bytes 0-11                   |

**IMPORTANT**: Use `0x00, 0x00` for time bytes for instant response. See "CRITICAL: Time Field" section above.

**Java usage (c0.java line 56):**

```java
// For CCT brightness-only (no temperature control):
tc.d.c(CipherSuite.TLS_PSK_WITH_NULL_SHA384, 0, 0, 0, 0, (i10 * 100) / 255, 30, 0);
//     mode=0xB1                             h  s  br temp  brightness    time delay

// For CCT with temperature control (model_0x53 style):
tc.d.c(0xB1, 0, 0, 0, temp_percent, brightness_percent, 30, 0);
```

**Python implementation:**

```python
def build_cct_command_0x3B(temp_percent: int, brightness_percent: int,
                           duration: int = 0) -> bytearray:
    """
    Build CCT temperature command using 0x3B format with mode 0xB1.

    This format is used by Ring Lights (model_0x53) and Symphony devices.
    Alternative to the 0x35 CCT command used by some ceiling lights.

    Args:
        temp_percent: 0-100 (0=warm/2700K, 100=cool/6500K)
        brightness_percent: 0-100
        duration: Transition time (default 0 = instant)

    Returns:
        13-byte command packet
    """
    temp_percent = max(0, min(100, temp_percent))
    brightness_percent = max(0, min(100, brightness_percent))
    
    raw_cmd = bytearray([
        0x3B,                      # Command opcode
        0xB1,                      # Mode: CCT temperature
        0x00, 0x00,                # Hue/Sat (unused)
        0x00,                      # Brightness param (unused)
        temp_percent & 0xFF,       # Temperature %
        brightness_percent & 0xFF, # Brightness %
        0x00, 0x00, 0x00,          # RGB (unused)
        (duration >> 8) & 0xFF,    # Time high byte
        duration & 0xFF,           # Time low byte
    ])
    raw_cmd.append(sum(raw_cmd) & 0xFF)  # Checksum
    return raw_cmd
```

**Device compatibility:**

| Device Type       | Product ID | CCT Method      |
|-------------------|------------|-----------------|
| Ring Light        | 0x53, 0x00 | 0x3B 0xB1       |
| Symphony devices  | 0xA1-0xA9  | 0x3B 0xB1       |
| CCT-only (ceiling)| 0x09, 0x1C | 0x35 0xB1       |
| Generic           | varies     | 0x31 with WW/CW |

**Why use 0x3B 0xB1 instead of 0x31 or 0x35?**

1. **Temperature as percentage**: The 0x3B B1 format uses temperature as a 
   simple percentage (0-100) rather than separate WW/CW channel values.
   This is more intuitive for devices that have a single temperature slider.

2. **BLE v5+ devices**: Symphony and modern devices use the 0x3B command 
   family for all control operations, maintaining consistency.

3. **Firmware compatibility**: Some devices (like Ring Lights) only respond
   to the 0x3B format and ignore 0x31/0x35 CCT commands.

---

# EFFECT ENUMERATIONS

Effect IDs are hardcoded in the app. The number and type of effects depends on
the device model/product type.

## Symphony "Settled Mode" Effects (0x41 command)

Source: ge/*.java classes used in SettledModeFragment.java

These are the 10 "Settled Mode" effects for Symphony devices (product types
0xA2/162, 0xA3/163). They use the 0x41 command with FG/BG colors.

| ID | Class | Has Background | Has Speed | Description |
|----|-------|----------------|-----------|-------------|
| 1  | s1    | No             | Conditional | Solid color (FG only) |
| 2  | u1    | Yes            | Yes       | Animation with FG/BG |
| 3  | w1    | Yes            | Yes       | Animation with FG/BG |
| 4  | y1    | Yes            | Yes       | Animation with FG/BG |
| 5  | a2    | Yes            | Yes       | Animation with FG/BG |
| 6  | c2    | Yes            | Yes       | Animation with FG/BG |
| 7  | e2    | No             | Yes       | Animation (FG only) |
| 8  | g2    | Yes            | Yes       | Animation with FG/BG |
| 9  | i2    | Yes            | Yes       | Animation with FG/BG |
| 10 | r1    | Yes            | Yes       | Animation with FG/BG |

**Notes:**
- Effect 1 is solid color mode (no animation, just foreground color)
- Effects 2-6, 8-10 support both foreground and background colors
- Effect 7 only supports foreground color
- Speed support varies; Effect 1 speed depends on device configuration

## Symphony "Scene" Effects (0xA3/0x38 commands)

Source: dd/i.java method f() - 44 hardcoded effects

These effects use the SymphonyEffect class with UI type hints for color support.

| ID | UI Type | Color Support |
|----|---------|---------------|
| 1  | StartColor_EndColor | Start + End colors |
| 2  | Only_ForegroundColor | FG only |
| 3  | StartColor_EndColor | Start + End colors |
| 4  | StartColor_EndColor | Start + End colors |
| 5-18 | ForegroundColor_BackgroundColor | FG + BG colors |
| 19-26 | FirstColor_SecondColor | First + Second colors |
| 27-28 | Only_BackgroundColor | BG only |
| 29-44 | NoColor | No color customization |

**UI Type Meanings:**
- `ForegroundColor_BackgroundColor`: Effect uses two colors (FG animation, BG static)
- `StartColor_EndColor`: Gradient/transition between two colors
- `FirstColor_SecondColor`: Alternating or paired colors
- `Only_ForegroundColor`: Single animated color
- `Only_BackgroundColor`: Single background color
- `NoColor`: Preset colors, no customization

## Symphony "Build" Effects (0x38 command)

Source: dd/i.java method i() - Dynamic loading from resources

These are numbered effects 1-300, loaded from string resources named
`symphony_SymphonyBuild_N`. Effect IDs are offset by +99 in the ListValueItem.

Protocol: `[0x38, effect_id, speed, param, checksum]`

## Device-Specific Effect Counts

**Note:** The Java source code does not hardcode effect counts per product type.
Effect availability appears to be determined at runtime, possibly via device
query responses or stored in app string resources (not in decompiled Java).

**What we know from Java:**

- Symphony devices (0xA2, 0xA3, etc.) use the Symphony effect system:
  - 10 Settled Mode effects (ge/*.java classes)
  - 44 Scene effects (dd/i.java method f())
  - Up to 300 Build effects (dd/i.java method i(), loaded from resources)
- Legacy devices use 0x61 command with device-specific effect IDs
- Effect IDs and ranges must be determined through device testing

**To determine effect counts for a specific product type:**

1. Query the device for supported modes (if protocol supports it)
2. Test effect IDs incrementally to find valid range
3. Check device documentation or app UI for hints

## Legacy Built-in Effects (0x61 command)

Source: tc/b.java method c()

For older/simpler devices using the 5-byte 0x61 command format.
Effect IDs are device-specific and must be determined through testing.
Common ranges observed: 0x25-0x38 (37-56) but this varies by product.

## Effect Speed Mapping

The Java app maps UI speed (0-100) to protocol speed differently per command:

**0xA3 command (tc/a.java):**

```java
// Maps 0-100 → 1-31
int speed = Math.round(g2.d.f(100.0f, 0.0f, 1.0f, 31.0f, uiSpeed));
```

**0x61 command (tc/b.java):**

```java
// Direct byte value, may be inverted (higher = slower)
bArr[2] = (byte) speed;  // 0-255
```

**0x38 command (tc/d.java):**

```java
// Direct byte value
bArr[2] = (byte) speed;  // 0-255
```

