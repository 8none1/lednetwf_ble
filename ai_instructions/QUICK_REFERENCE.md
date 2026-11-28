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
| 39 | 0x27 | Ctrl_Mini_RGBW | No | **Not in ble_devices.json.** Sold as "sunset lamp" (issue #75). BLE v5 firmware ignores 0x31; colour/white/effects need unified 0x3B and 0x38 (PR #104) |
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
| 0 | 0x00 | 0x5A00-0x5AFF | Same product_id, **four** different command families |

`product_id = 0x00` is not one device type. Known families, all advertising the
same product ID:

| Family | Power | Colour | Effects |
|--------|-------|--------|---------|
| Telink (e.g. IOTBT812) | `0x71` | `E2 0B <hue> <0xE0\|lvl>` | `E0 02` |
| Segment (e.g. IOTBT6BA) | `0x3B` | `E1 03` + `A1` blocks | `E1 01` |
| v3 wrapper (ZJ-BBLA-RGBWW, PR #101) | `0x71` | `E0 01 00 A1 ...` | unknown |
| E0 01 string lights (products 0xC5, 0x64, 0xFD) | `E0 01 00 23/24` | `E0 01 00 C1 ...` (5-byte HSV+W) | `E1 21` |

E0 01 family members (`const.IOTBT_E0_PRODUCT_IDS`), chosen by advertised product ID:

| Product | Device | Status |
|---------|--------|--------|
| 197 (0xC5) | Minetom / Aurelux string lights, also Surplife-app string lights (#126) | Confirmed on firmware 0x08 (flags2 0x2A) and firmware 43 (flags2 0x07) |
| 100 (0x64) | Surplife-app Christmas string lights (PR #129) | Confirmed by direct writes |
| 253 (0xFD) | Surplife Christmas tree star, IOTBTAF1 (#130) | Provisional since 2.0.1-beta27, awaiting a user test |

Detection order: a manual `CONF_IOTBT_PROTOCOL` override (`telink` / `segment` / `v3`)
wins, then the advertised product ID lists (`IOTBT_E0_PRODUCT_IDS`,
`IOTBT_V3_PRODUCT_IDS`, `IOTBT_SEGMENT_PRODUCT_IDS`), then the heuristic on
service-data `flags2` bit `0x08`. See `iotbt_variant_findings.md`.

Signs that an unknown IOTBT device belongs to the E0 01 family: `E0 02` effects are
ignored with no state reply, `E0 01 00 A1 ...` colour works under the `v3` override,
and the `EA 81` reply has byte 7 = `0x24` (solid) / `0x25` (scene) with the fx id in
byte 8 and speed in byte 9.

Debug logs (releases after 2.0.1-beta27): the first command of each debug session is preceded by a
`Device identity for <name>: ...` line giving both product IDs, flags2, versions, the
protocol override, the effect type and the raw service data. Advertisement parse lines
are usually absent from bug-report logs because a connected device stops advertising.

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

### 0xE0 "v3" Command Wrapper

```
E0 {sub} {preview} {v2 payload}     # no checksum on any E0 command
```

`E0` is the app's third-generation command prefix, **not** a Telink opcode.
`switch_led_v3` = `e001{preview}` + the entire `switch_led_v2` form proves it.
Our "IOTBT effect" command `E0 02 00 {id} {speed} {bright}` is really the app's
generic `scene_data_v3`. Full table in
`protocol_docs/17_device_configuration.md`.

### Packed hue+sat (0x3B colour, and everything derived from it)

```
packed  = (hue << 7) | sat          # hue 0-360, sat 0-100
byte_hi = packed >> 8               # == hue // 2 for any sat <= 100
byte_lo = packed & 0xFF             # == sat, or sat + 128 on odd hues
```

**Trap**: for saturated colours this is indistinguishable from "hue in
half-degree units, then saturation". Test a desaturated colour on an odd hue
before writing down a new encoding. This encoding turns up in the `0x3B` colour
command, the `E0 01` colour command, and every `IOTBT_SEGMENT_EFFECT_SCENES`
palette entry.

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
