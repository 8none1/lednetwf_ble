# DEVICE IDENTIFICATION AND CAPABILITIES

## How the App Determines Device Capabilities

The ZenGGe app uses a **class hierarchy** to determine device capabilities:

1. **Product ID** (from manufacturer data byte 1) maps to a **Device Type class**
2. Device Type class inherits from a **BaseType** that defines core capabilities
3. **Interfaces** (`hd.*`) mark additional features like Symphony effects

Source: `com/zengge/wifi/Device/a.java` method `k()` - Product ID to class mapping

## BaseType Class Hierarchy

| BaseType Class         | Capabilities | Description |
|------------------------|--------------|-------------|
| `RGBDeviceInfo`        | RGB only | RGB channels, no white |
| `CCTDeviceInfo`        | CCT only | Warm white + Cool white |
| `BrightnessDeviceInfo` | DIM only | Single channel dimmer |
| `RGBWBothDeviceInfo`   | RGB + W | RGB + single white (WW or CW) |
| `RGBCWBothDeviceInfo`  | RGB + CCT | RGB + WW + CW (full RGBCW) |
| `RGBWBulbDeviceInfo`   | RGBW bulb | Bulb with RGB + white |
| `RGBCWBulbDeviceInfo`  | RGBCW bulb | Bulb with full 5-channel |
| `RGBSymphonyDeviceInfo`| RGB + Effects | Addressable LED controller |
| `RGBNewSymphonyDeviceInfo` | RGB + Symphony | Newer addressable LED |
| `SwitchDeviceInfo`     | Switch | On/Off relay, no dimming |
| `CeilingDeviceInfo`    | Ceiling light | Typically CCT or RGBCW |

## Interface Markers (hd.* package)

These interfaces mark additional capabilities:

| Interface | Purpose | Method |
|-----------|---------|--------|
| `hd.b` | BLE device marker | (empty marker) |
| `hd.f` | Supports dimming curves | `i()` - returns boolean |
| `hd.g` | Symphony/addressable LED | `b()` - LED count, `h()` - advanced |
| `hd.h` | Segment support | `b()` - segments, `n(int)` - set segment |
| `hd.i` | Wiring configuration | `c()` - has wiring, `o()` - options |
| `hd.j` | Color order settings | `l()` - supports, `p()` - values |
| `hd.k` | Extended CCT support | (empty marker) |
| `hd.l` | IC type selection | `a()` - supports, `e()` - IC list |

## Manufacturer ID Ranges

### PRIMARY RANGE (LEDnetWF devices)
- 23120-23122 (0x5A50, 0x5A51, 0x5A52)

### EXTENDED RANGES (ZGHBDevice validation)
- Exact match IDs: 23123-23133
- Range 1: 23072-23087 (0x5A20-0x5A2F)
- Range 2: 23136-23151 (0x5A60-0x5A6F)
- Range 3: 23152-23167 (0x5A70-0x5A7F)
- Range 4: 23168-23183 (0x5A80-0x5A8F)

## BLE Protocol Version Detection

Source: `BaseDeviceInfo.E()` and `BaseModuleType.f23897c`

The BLE version field determines command compatibility:

| Version | Method Check | Power Command | Features |
|---------|--------------|---------------|----------|
| < 5     | `!E()`       | 0x71          | Legacy command format |
| >= 5    | `E()`        | 0x3B          | Modern command format |
| >= 8    | `F()`        | 0x3B          | Extended state (24+ bytes) |
| >= 10   | `b0().d()`   | 0x3B          | Additional features |
| >= 11   | `b0().c()`   | 0x3B          | Full modern support |

**Note**: The version is extracted from the device name suffix (e.g., "LEDnetWF07" → version 7).

## Product ID → Capabilities Table

Source: `com/zengge/wifi/Device/a.java` method `k()`

| productId (hex) | Device Class                    | BaseType         | Capabilities        |
|-----------------|---------------------------------|------------------|---------------------|
| 0x04 (4)        | Ctrl_RGBW_UFO_0x04              | RGBW             | RGB + W             |
| 0x06 (6)        | Ctrl_Mini_RGBW_0x06             | RGBWBoth         | RGB + W             |
| 0x07 (7)        | Ctrl_Mini_RGBCW_0x07            | RGBCWBoth + hd.l | RGB + WW + CW + IC  |
| 0x08 (8)        | Ctrl_Mini_RGB_Mic_0x08          | RGBSymphony      | RGB + Mic effects   |
| 0x09 (9)        | Ctrl_Ceiling_light_CCT_0x09     | CCT              | CCT only (WW+CW)    |
| 0x0B (11)       | Switch_1c_0x0b                  | Switch           | On/Off only         |
| 0x0E (14)       | FloorLamp_RGBCW_0x0E            | RGBCWBoth        | RGBCW               |
| 0x10 (16)       | ChristmasLight_0x10             | RGB              | RGB effects         |
| 0x16 (22)       | Magnetic_CCT_0x16               | CCT              | CCT only            |
| 0x17 (23)       | Magnetic_Dim_0x17               | Brightness       | Dimmer only         |
| 0x18 (24)       | PlantLight_0x18                 | Special          | Plant grow light    |
| 0x19 (25)       | Socket_2Usb_0x19                | Switch           | Socket + USB        |
| 0x1A (26)       | ChristmasLight_0x1A             | RGB              | Christmas effects   |
| 0x1B (27)       | SprayLight_0x1B                 | Special          | Spray light         |
| 0x1C (28)       | TableLamp_CCT_0x1C              | CCT              | CCT table lamp      |
| 0x1D (29)       | FillLight_0x1D                  | Special*         | Fill light (probe!) |
| 0x1E (30)       | CeilingLight_RGBCW_0x1E         | RGBCWBoth        | RGBCW               |
| 0x20 (32)       | Ctrl_Mini_RGBW_0x20             | RGBWBoth         | RGB + W             |
| 0x21 (33)       | Bulb_Dim_0x21                   | Brightness       | Dimmer bulb         |
| 0x25 (37)       | Ctrl_RGBCW_Both_0x25            | RGBCWBoth        | RGBCW               |
| 0x26 (38)       | Ctrl_Mini_RGBW_0x26             | RGBWBoth         | RGB + W             |
| 0x27 (39)       | Ctrl_Mini_RGBW_0x27             | RGBWBoth         | RGB + W             |
| 0x29 (41)       | MirrorLight_0x29                | Special          | Mirror light        |
| 0x2D (45)       | GAON_PlantLight_0x2D            | Special          | GAON plant light    |
| 0x33 (51)       | Ctrl_Mini_RGB_0x33              | RGB              | RGB only            |
| 0x35 (53)       | Bulb_RGBCW_R120_0x35            | RGBCWBulb        | RGBCW bulb          |
| 0x3B (59)       | Bulb_RGBCW_0x3B                 | RGBCWBulb        | RGBCW bulb          |
| 0x41 (65)       | Ctrl_Dim_0x41                   | Brightness       | Dimmer controller   |
| 0x44 (68)       | Bulb_RGBW_0x44                  | RGBWBulb         | RGBW bulb           |
| 0x48 (72)       | Ctrl_Mini_RGBW_Mic_0x48         | RGBWBoth + hd.l  | RGBW + Mic + IC     |
| 0x52 (82)       | Bulb_CCT_0x52                   | CCT              | CCT bulb            |
| 0x54 (84)       | Downlight_RGBW_0x54             | RGBWBoth         | RGBW downlight      |
| 0x62 (98)       | Ctrl_CCT_0x62                   | CCT              | CCT controller      |
| 0x93 (147)      | Switch_1C_0x93                  | Switch           | 1-channel switch    |
| 0x94 (148)      | Switch_1c_Watt_0x94             | Switch           | Switch + power      |
| 0x95 (149)      | Switch_2c_0x95                  | Switch           | 2-channel switch    |
| 0x96 (150)      | Switch_4c_0x96                  | Switch           | 4-channel switch    |
| 0x97 (151)      | Socket_1c_0x97                  | Switch           | 1-channel socket    |
| 0xA1 (161)      | Ctrl_Mini_RGB_Symphony_0xa1     | RGBSymphony+hd.g | Symphony effects    |
| 0xA2 (162)      | Ctrl_Mini_RGB_Symphony_new_0xa2 | RGBNewSymphony   | New Symphony        |
| 0xA3 (163)      | Ctrl_Mini_RGB_Symphony_new_0xA3 | RGBNewSymphony   | New Symphony        |
| 0xA4 (164)      | Ctrl_Mini_RGB_Symphony_new_0xA4 | RGBNewSymphony   | New Symphony        |
| 0xA6 (166)      | Ctrl_Mini_RGB_Symphony_new_0xA6 | RGBNewSymphony   | New Symphony        |
| 0xA7 (167)      | Ctrl_Mini_RGB_Symphony_new_0xA7 | RGBNewSymphony   | New Symphony        |
| 0xA9 (169)      | Ctrl_Mini_RGB_Symphony_new_0xA9 | RGBNewSymphony   | New Symphony        |
| 0xD1 (209)      | Digital_Light_0xd1              | Special          | Digital LED panel   |
| 0xE1 (225)      | Ctrl_Ceiling_light_0xe1         | Ceiling          | Ceiling light       |
| 0xE2 (226)      | Ctrl_Ceiling_light_Assist_0xe2  | Ceiling          | Ceiling assist      |
| 0x00 (0)        | TypeNone                        | None             | Unknown device      |

**Note**: FillLight_0x1D (29) is a "stub" device class - capabilities vary by hardware. Always probe capabilities with state query.

## State-Based Capability Detection

For devices with unknown Product ID (0x00) or stub classes, probe capabilities:

### Method 1: Parse State Query Response

State response byte positions:
- Byte 3 (`f23862f`): Mode (97 = RGB mode, other = effect/white mode)
- Bytes 6-8 (`f23865j`, `f23866k`, `f23867l`): R, G, B values
- Byte 9 (`f23868m`): Warm White value
- Byte 11 (`f23869n`): Cool White value

If values are non-zero when device is in color mode, that channel is supported.

### Method 2: Active Channel Probing

1. Send state query `[0x81, 0x8A, 0x8B, 0x40]`
2. Parse response bytes 6-11 for current channel values
3. Set RGB test value (R=50): `[0x31, 0x32, 0x00, 0x00, 0x00, 0x00, 0x5A, 0x0F, CS]`
4. Query state - if response[6] ≈ 0x32 → has_rgb = true
5. Set WW test: `[0x31, 0x00, 0x00, 0x00, 0x32, 0x00, 0x5A, 0x0F, CS]`
6. Query state - if response[9] ≈ 0x32 → has_ww = true
7. Set CW test: `[0x31, 0x00, 0x00, 0x00, 0x00, 0x32, 0x5A, 0x0F, CS]`
8. Query state - if response[11] ≈ 0x32 → has_cw = true
9. Restore original state
10. Cache capabilities by MAC address

## StatusModeType Enum

Source: `BaseDeviceInfo.StatusModeType`

Defines the current operating mode of the device:

| Mode | Description |
|------|-------------|
| `StatusModeType_Cool` | Cool white mode |
| `StatusModeType_RGB` | RGB color mode |
| `StatusModeType_RGB_W_Both` | RGB and white simultaneously |
| `StatusModeType_Warm` | Warm white mode |
| `StatusModeType_CCT` | Color temperature mode |
| `StatusModeType_Dynamic` | Running an effect |
| `StatusModeType_NONE_NO_BRIGHT` | Off, no brightness |
| `StatusModeType_NONE` | Unknown/none |
