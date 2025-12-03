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

#### Symphony Format (0x3B) - tc.d.a()

Used by: BLE v5+ devices (when E() returns true)

See "HSV/Symphony Color Command (0x3B)" section below for format details.

This format uses HSV color values instead of RGB and is the preferred format
for modern devices with BLE protocol version 5 or higher.

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

## Effect Command (0x38)

Format (5 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x38 (56)                        |
| 1    | Effect ID       | 1-227 (device-dependent max)     |
| 2    | Speed           | 0-255                            |
| 3    | Parameter       | Effect-specific (often 0)        |
| 4    | Checksum        | Sum of bytes 0-3                 |

Example (effect 5 at speed 128): `[0x38, 0x05, 0x80, 0x00, 0xBD]`

## HSV/Symphony Color Command (0x3B)

Source: tc/d.java method c() lines 19-35

Format (13 bytes) for Symphony devices:

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Prefix          | 0x3B (59)                        |
| 1    | Mode            | 0xA1 (161) for Symphony HSV      |
| 2    | Hue+Sat (hi)    | (hue << 7 \| sat) >> 8            |
| 3    | Hue+Sat (lo)    | (hue << 7 \| sat) & 0xFF          |
| 4    | Brightness      | 0-100                            |
| 5-6  | Params          | Mode-specific                    |
| 7-9  | RGB             | Color as RGB                     |
| 10-11| Time            | Duration                         |
| 12   | Checksum        | Sum of bytes 0-11                |

### Hue/Saturation Encoding

```python
packed = (hue << 7) | (saturation & 0x7F)
byte_hi = (packed >> 8) & 0xFF   # Effectively hue/2
byte_lo = packed & 0xFF          # (hue & 1) << 7 | saturation
```
