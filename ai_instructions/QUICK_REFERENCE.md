# Quick Reference: Product IDs and Commands

## Product ID Quick Lookup

### Simple RGB Controllers (0x31 command)

| ID | Hex | Name | Has Mic | Notes |
|----|-----|------|---------|-------|
| 8 | 0x08 | Ctrl_Mini_RGB_Mic | Yes | rgb_mini_mic protocol |
| 51 | 0x33 | Ctrl_Mini_RGB | No | rgb_mini protocol |
| 60 | 0x3C | Ctrl_Mini_RGB_Mic | Yes | rgb_mini_mic protocol |

### Simple RGBW Controllers (0x31 command)

| ID | Hex | Name | Has Mic | Notes |
|----|-----|------|---------|-------|
| 6 | 0x06 | Ctrl_Mini_RGBW | No | Has CCT (temp_value) |
| 68 | 0x44 | Bulb_RGBW | No | warm_value only |
| 72 | 0x48 | Ctrl_Mini_RGBW_Mic | Yes | rgb_mini_mic protocol |
| 84 | 0x54 | Downlight_RGBW | No | |

### RGBCW Controllers (0x31 command)

| ID | Hex | Name | Notes |
|----|-----|------|-------|
| 7 | 0x07 | Ctrl_Mini_RGBCW | |
| 14 | 0x0E | FloorLamp_RGBCW | |
| 30 | 0x1E | CeilingLight_RGBCW | |
| 53 | 0x35 | Bulb_RGBCW | |

### Symphony Controllers

| ID | Hex | Name | Cmd | Has Mic | Notes |
|----|-----|------|-----|---------|-------|
| 161 | 0xA1 | Symphony (old) | 0x31 | **NO** | Only Symphony without mic |
| 162 | 0xA2 | Symphony_new | 0x46 | Yes | |
| 163 | 0xA3 | Symphony_new | 0x46 | Yes | |
| 164 | 0xA4 | Symphony_new | 0x46 | Yes | symp_mic_info |
| 166 | 0xA6 | Symphony_new | 0x46 | Yes | |
| 170 | 0xAA | Symphony_Line | 0x46 | Yes | musicMic UI |
| 171 | 0xAB | Symphony_Line | 0x46 | Yes | musicMic UI |
| 172 | 0xAC | Symphony_Curtain | 0x46 | Yes | musicMic UI |
| 173 | 0xAD | Symphony_Curtain | 0x46 | Yes | musicMic UI |

### CCT Only

| ID | Hex | Name |
|----|-----|------|
| 9 | 0x09 | Ceiling_CCT |
| 22 | 0x16 | Magnetic_CCT |
| 28 | 0x1C | TableLamp_CCT |
| 82 | 0x52 | Bulb_CCT |
| 98 | 0x62 | Ctrl_CCT |

### Dimmer Only

| ID | Hex | Name |
|----|-----|------|
| 23 | 0x17 | Magnetic_Dim |
| 33 | 0x21 | Bulb_Dim |
| 65 | 0x41 | Ctrl_Dim |

### IOTBT / Telink Mesh

| ID | Hex | Company ID | Notes |
|----|-----|------------|-------|
| 0 | 0x00 | 0x1102 | Telink BLE Mesh |

## Command Formats

### 0x31 RGB Command Variants

```
# RGB only (0x08, 0x33, 0x51, 0xA1)
31 {R} {G} {B} 00 00 0F [checksum]

# RGBW (0x06, 0x44, 0x48, 0x54)
31 {R} {G} {B} 00 F0 0F [checksum]
  or
31 {R} {G} {B} {W} mode persist [checksum]

# RGBCW (0x07, 0x35, 0x53)
31 {R} {G} {B} 00 00 F0 0F [checksum]
```

### 0x46 Symphony New Command

```
46 {R} {G} {B} 00 00 [checksum?]
```

### 0xE1 IOTBT Music Command

```
E1 05 [effect_id] [brightness] [sensitivity] ... (46 bytes total)
```

## State Response Parsing

```
81 [product_id] [power] [mode] [sub_mode] [brightness] [R] [G] [B] ...

power: 0x23=ON, 0x24=OFF
mode: 0x61=color/white, 0x25=effect
```

## BLE Advertisement Company IDs

| Company ID | Format | Devices |
|------------|--------|---------|
| 0x5A00-0x5AFF | ZengGe | Most LED controllers |
| 0x1102 | Telink | IOTBT mesh devices |

## Mic Detection

```python
# Devices with built-in mic (verified from app database)
SIMPLE_MIC = {0x08, 0x48}
SYMPHONY_MIC = {0xA2, 0xA3, 0xA4, 0xA6}
SYMPHONY_LINE_MIC = {0xAA, 0xAB, 0xAC, 0xAD}

# NO mic despite being Symphony
NO_MIC = {0xA1}
```

## File Paths

```
# Protocol docs
/home/will/source/lednetwf_ble/protocol_docs/

# Integration code
/home/will/source/lednetwf_ble/custom_components/lednetwf_ble/

# Decompiled app - Java sources
/home/will/source/jadx/projects/surplife/sources/sources/com/zengge/

# Decompiled app - JSON configs
/home/will/source/jadx/projects/surplife/assets/flutter_assets/packages/magichome2_home_data_provide/assets/
```
