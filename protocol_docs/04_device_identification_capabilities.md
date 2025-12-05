# DEVICE IDENTIFICATION AND CAPABILITIES

## Critical Rule: Use Product ID, Not sta_byte!

**⚠️ IMPORTANT**: The Android app uses **product_id** (bytes 8-9 in manufacturer data) to determine device capabilities, NOT the sta_byte (byte 0).

- **Product ID** = Device type identifier → Maps to device class with capabilities
- **sta_byte** = Current device status → Changes based on power/mode state

**Always extract product_id first for reliable device identification.**

## How the App Determines Device Capabilities

The ZenGGe app uses a **class hierarchy** to determine device capabilities:

1. **Product ID** (from manufacturer data bytes 8-9) maps to a **Device Type class**
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

---

## Implementation Guide: Extracting Product ID

### Step 1: Parse Manufacturer Data (Python/bleak)

```python
def get_device_info(advertisement_data):
    """
    Extract device info from BLE advertisement manufacturer data.
    
    Args:
        advertisement_data: BleakScanner advertisement_data object
    
    Returns:
        dict with product_id, ble_version, sta_byte, mac, etc.
    """
    mfr_data = advertisement_data.manufacturer_data
    
    # Find LEDnetWF company ID (0x5A00-0x5AFF range: 23040-23295)
    for company_id, payload in mfr_data.items():
        if 23040 <= company_id <= 23295 and len(payload) == 27:
            # Format B (bleak): company ID is dict key, NOT in payload
            # Payload bytes 8-9 contain product_id (big-endian)
            product_id = (payload[8] << 8) | payload[9]
            ble_version = payload[1]
            sta_byte = payload[0]
            
            return {
                'product_id': product_id,
                'ble_version': ble_version,
                'sta_byte': sta_byte,
                'mac': ':'.join(f'{b:02X}' for b in payload[2:8]),
                'fw_version': payload[10],
                'led_version': payload[11],
            }
    return None
```

### Step 2: Map Product ID to Capabilities

```python
def get_device_capabilities(product_id: int) -> dict:
    """
    Determine device capabilities from product_id.
    
    Returns:
        dict with has_rgb, has_ww, has_cw, has_effects, effect_type
    """
    # Symphony devices - addressable LED with advanced effects
    if product_id in [161, 162, 163, 164, 166, 167, 169, 8]:  # 0xA1-0xA9, 0x08
        return {
            'has_rgb': True,
            'has_ww': False,
            'has_cw': False,
            'has_effects': True,
            'effect_type': 'symphony',
            'effect_command': '0x38_5byte_inverted_speed',
        }
    
    # FillLight/Ring Light - addressable with custom effects
    if product_id == 29:  # 0x1D
        return {
            'has_rgb': True,
            'has_ww': False,
            'has_cw': False,
            'has_effects': True,
            'effect_type': 'addressable',
            'effect_command': '0x38_4byte_no_checksum',
        }
    
    # RGBCW devices
    if product_id in [7, 14, 30, 37, 53, 59]:  # RGBCW variants
        return {
            'has_rgb': True,
            'has_ww': True,
            'has_cw': True,
            'has_effects': False,
            'effect_type': None,
        }
    
    # RGBW devices
    if product_id in [4, 6, 20, 26, 27, 38, 39, 44, 48, 68, 84]:  # RGBW variants
        return {
            'has_rgb': True,
            'has_ww': True,
            'has_cw': False,
            'has_effects': True,
            'effect_type': 'simple',
            'effect_command': '0x61_5byte',
        }
    
    # RGB only devices
    if product_id in [33, 51]:  # RGB variants
        return {
            'has_rgb': True,
            'has_ww': False,
            'has_cw': False,
            'has_effects': True,
            'effect_type': 'simple',
            'effect_command': '0x61_5byte',
        }
    
    # CCT only devices
    if product_id in [9, 22, 28, 82, 98]:  # CCT variants
        return {
            'has_rgb': False,
            'has_ww': True,
            'has_cw': True,
            'has_effects': False,
            'effect_type': None,
        }
    
    # Dimmers
    if product_id in [23, 33, 65]:  # Dimmer variants
        return {
            'has_rgb': False,
            'has_ww': True,
            'has_cw': False,
            'has_effects': False,
            'effect_type': None,
        }
    
    # Switches (no dimming/color control)
    if product_id in [11, 147, 148, 149, 150, 151]:  # Switch variants
        return {
            'has_rgb': False,
            'has_ww': False,
            'has_cw': False,
            'has_effects': False,
            'effect_type': None,
        }
    
    # Unknown - need to probe
    return None
```

### Step 3: Fallback Detection (sta_byte as hint)

If product_id is unknown or maps to TypeNone (0x00), use sta_byte as a secondary hint:

```python
def detect_with_fallback(product_id: int, sta_byte: int) -> dict:
    """
    Use product_id first, sta_byte as fallback for unknown devices.
    
    Note: sta_byte is DEVICE STATUS, not device type!
          It's unreliable but better than nothing for unmapped devices.
    """
    # Try product_id first
    capabilities = get_device_capabilities(product_id)
    if capabilities is not None:
        return capabilities
    
    # Fallback to sta_byte patterns (unreliable!)
    # These correlations are observed, not guaranteed
    if sta_byte == 0x53:
        # Often FillLight-style devices
        return {
            'has_rgb': True,
            'has_effects': True,
            'effect_type': 'addressable',
            'effect_command': '0x38_4byte_no_checksum',
            'note': 'Detected from sta_byte - may be inaccurate!',
        }
    elif sta_byte in [0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xA7, 0xA9]:
        # Often Symphony devices
        return {
            'has_rgb': True,
            'has_effects': True,
            'effect_type': 'symphony',
            'effect_command': '0x38_5byte_inverted_speed',
            'note': 'Detected from sta_byte - may be inaccurate!',
        }
    
    # Still unknown - must probe device
    return None
```

---

## Why sta_byte is Unreliable

**Common misconception**: Old implementations used sta_byte (byte 0 of manufacturer data) as a device type identifier.

**Reality**: 
- sta_byte represents **current device status** (power, mode, etc.)
- It can change based on device state
- Different product types can share the same sta_byte value
- No official documentation defines its meaning
- Android app **never uses sta_byte** for device identification

**Only use sta_byte as a last resort fallback when product_id is unknown (0x00 or unmapped).**

---

## Quick Reference: Product ID Ranges

| Range | Device Types | Examples |
|-------|-------------|----------|
| 0x04-0x27 (4-39) | Controllers, bulbs | RGB, RGBW, RGBCW variants |
| 0x29-0x2D (41-45) | Special devices | Mirror lights, plant lights |
| 0x33-0x48 (51-72) | Controllers, bulbs | RGB, RGBW, RGBCW variants |
| 0x52-0x62 (82-98) | CCT/dimmer | Bulbs, controllers |
| 0x93-0x97 (147-151) | Switches/sockets | On/Off, multi-channel |
| 0xA1-0xA9 (161-169) | Symphony | Addressable LED controllers |
| 0xD1 (209) | Digital panels | LED matrix panels |
| 0xE1-0xE2 (225-226) | Ceiling lights | Smart ceiling fixtures |

---

## Summary: Detection Priority

1. **Always extract product_id first** (bytes 8-9, big-endian)
2. **Map product_id to capabilities** using product table
3. **If product_id unknown**, use sta_byte as hint (unreliable)
4. **If still unknown**, probe device with state query
5. **Cache results** by MAC address to avoid repeated detection
