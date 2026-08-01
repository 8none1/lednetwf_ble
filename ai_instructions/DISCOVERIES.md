# Discoveries and Corrections Log

This document tracks significant findings and corrections made during the reverse engineering process.

## Documentation Errors Found and Fixed

### Effect ID 37 collides with the 0x25 "effect mode" marker

**Date**: 1 August 2026 (issue #99)

**Problem**: SIMPLE devices report the running effect ID directly in the
mode_type byte (37-56). The first effect in the list is ID 37, which is 0x25,
the same value Symphony/Addressable devices use as the "effect mode" marker
with the real ID in sub_mode.

Both parsers assumed the Symphony meaning unconditionally:

- `parse_state_response()` set `is_effect_mode = mode_type == 0x25` and then
  took the effect ID from sub_mode. Effect 37 decoded as "effect id = whatever
  is in sub_mode", and effects 38-56 were not recognised as effect mode at all.
- `parse_manufacturer_data()` had an `elif mode_type == 0x25` branch that
  shadowed the correct `elif 37 <= mode_type <= 56` branch below it, then
  applied a +20 offset guess to sub_mode.

Observed effect: a device running effect 37 was reported as effect 55 with the
speed read out of an RGB byte.

**Fix**: both parsers now take a `simple_effects` flag from the caller and
check the 37-56 range first for those devices.

**Note**: sub_mode is NOT reliably the speed on these devices. It is often an
echo of the power state (0x23=ON, 0x24=OFF), so it is ignored when it holds
those values. The full byte layout for SIMPLE effect state is still unconfirmed
and needs a capture.

---

### Speed encode/decode were not inverses (drift on every round-trip)

**Date**: 1 August 2026 (issue #99)

**Problem**: two independent bugs made the effect speed drift every time state
was read back and reused by the next effect command:

1. Products 0x08 and 0x3C send effects with the inverted 1-31 speed encoding
   (`scene_data_v2` declares speed min=1 max=31) but were missing from
   `INVERTED_SPEED_PRODUCT_IDS`, so the reported value was read as a 0-100
   percentage.
2. The encoder `1 + int(30 * (1.0 - pct / 100))` truncates the wrong way for
   some values because of float representation. At 80%, `30 * 0.19999999999999996`
   is 5.999... which truncates to 5 instead of 6, so it disagreed with the
   decoder even once the scale was right.

**Fix**: added `convert_speed_to_inverted_31()` using integer arithmetic, used
by every inverted-speed encoder, and rewrote the decoder to be its exact
inverse. `decode(encode(pct))` is now a fixed point for all values 1-100.

---

### Product 0x3C (60) was missing from PRODUCT_CAPABILITIES

**Date**: 1 August 2026 (issue #99)

**Problem**: 0x3C is the same Ctrl_Mini_RGB_Mic as 0x08 (identical function
list in `ble_devices.json`) but had no entry, so it fell through to the
unknown-product fallback which assumes `EffectType.SYMPHONY` - an entirely
different command family.

---

### Product 0x08 (8) - Ctrl_Mini_RGB_Mic

**Date**: 7 December 2025

**Error**: Documentation listed 0x08 as "RGBSymphony" type using Symphony commands.

**Reality**:
- Uses `rgb_mini_mic` protocol
- Uses standard 0x31 colour command: `31{r}{g}{b}00000f`
- State response uses `wifibleLightStandardV1` (mode byte 0x61)
- IS NOT a Symphony device

**Files fixed**:
- `protocol_docs/03_device_identification.md`
- `protocol_docs/18_sound_reactive_music_mode.md`

---

### Product 0xA1 (161) - Symphony WITHOUT Mic

**Date**: 7 December 2025

**Error**: Assumed all Symphony devices have built-in microphone.

**Reality**:
- 0xA1 uses older `symphony_wifi` protocol
- Has NO mic functions in app database (empty `mic_funcs=[]`)
- Is the ONLY Symphony device without mic support

**Files fixed**:
- `protocol_docs/03_device_identification.md`
- `protocol_docs/18_sound_reactive_music_mode.md`

---

### Product 0xA4 (164) - HAS Mic (was listed as no mic)

**Date**: 7 December 2025

**Error**: Documentation listed 0xA4 as using `MusicModeFragmentWithoutMic`.

**Reality**:
- App database shows 0xA4 HAS `symp_get_mic_info` and `symp_mic_info` functions
- Should be grouped with mic-enabled Symphony devices

**Files fixed**:
- `protocol_docs/18_sound_reactive_music_mode.md`

---

### Symphony New Devices Use 0x46 Command (not 0x31)

**Date**: 7 December 2025

**Discovery**: New Symphony devices (0xA2-0xAD) use different colour command.

**Details**:
- Old Symphony (0xA1): Uses `31{r}{g}{b}00000f`
- New Symphony (0xA2+): Uses `46{r}{g}{b}0000`

**Files updated**:
- `protocol_docs/03_device_identification.md` - Added Colour Cmd column

---

### Effect Brightness is Firmware AND Product Dependent

**Date**: 7 December 2025

**Discovery**: SIMPLE effects (IDs 37-56) have different command formats. The minimum firmware version for brightness support varies by product.

**Command Formats**:

| Command | Format | Brightness |
|---------|--------|------------|
| `scene_data` (0x61) | `61 {model} {speed} {persist} [chk]` | **NO** |
| `scene_data_v2` (0x38) | `38 {model} {speed} {bright} [chk]` | **YES** (1-100) |
| `scene_data_v3` (0xE0 02) | `e0 02 {preview} {model} {speed} {bright}` | **YES** (0-100) |

**Products with EARLY 0x38 support (minVer 0-2)**:

- 0x08, 0x3C (Ctrl_Mini_RGB_Mic): minVer=1
- 0x06, 0x07, 0x48: minVer=2
- 0x10, 0x1A: minVer=0

**Products with LATER 0x38 support (minVer 8-9)**:

- 0x33, 0x35, 0x55, etc.: minVer=8-9

**Products with ONLY legacy (no brightness)**:

- 0x44 (Bulb_RGBW), 0x54 (Downlight_RGBW)

**Additional notes**:

- `bright_value_v2` (0x3B command) provides standalone brightness control
- Speed encoding changed from INVERTED (1-31) in v0-10 to DIRECT (0-100) in v11+
- Source: `wifi_dp_cmd.json`, `ble_devices.json`

**Files updated**:

- `protocol_docs/BRIGHTNESS_SPEED_VALUE_RANGES.md`

**Implications**:

- Integration should check BOTH product ID and firmware version
- Product 0x08 supports brightness from firmware v1+
- Must use different command builders based on product AND firmware

---

## Database Verification Process

When verifying product information, use this process:

```python
import json

# Load BLE device database
with open('/home/will/source/jadx/projects/surplife/assets/flutter_assets/packages/magichome2_home_data_provide/assets/ble_devices.json') as f:
    ble_data = json.load(f)

# Load UI panel config
with open('/home/will/source/jadx/projects/surplife/assets/flutter_assets/packages/magichome2_home_data_provide/assets/wifi_device_panel.json') as f:
    panel_data = json.load(f)

# Find device by product ID
for device in ble_data:
    if device.get('productId') == TARGET_ID:
        # Check protocols
        protocols = [p['name'] for p in device.get('protocols', [])]

        # Check command format
        hex_forms = device.get('hexCmdForms', {})
        colour_cmd = hex_forms.get('colour_data', {}).get('cmdForm', 'N/A')

        # Check for mic functions
        funcs = [f['code'] for f in device.get('functions', [])]
        mic_funcs = [f for f in funcs if 'mic' in f.lower()]

        print(f"Protocols: {protocols}")
        print(f"Colour cmd: {colour_cmd}")
        print(f"Mic functions: {mic_funcs}")
```

---

### IOTBT Segment Commands - Wrong Transport cmd_family (0x0A vs 0x0B)

**Date**: 18 July 2026

**Error**: `build_iotbt_segment_effect_command` (0xE1 0x01) and
`build_iotbt_segment_color_command` (0xE1 0x03) wrapped their payloads with
`cmd_family=0x0A` ("expects response"). The 0x0A was carried over from earlier
IOTBT builders, not taken from a capture.

**Reality**: In both app captures (issue #83 IOTBT6BA, issue #97 IOTBT4B0) the
app sends ALL state-changing commands with cmd_family **0x0B** (power 0x3B,
time sync 0x10, effects 0xE1 0x01) and reserves **0x0A for queries** (the
0xEA 0x81 state read). Tolerance of the wrong family byte varies by firmware
and opcode: the IOTBT6BA (#83) accepted 0x0A for both colour AND effects
(confirmed working), while the IOTBT4B0 (#97) accepted 0x0A for colour but
ignored 0x0A effects entirely. The issue #97 capture confirmed our 0xE1 0x01
payloads were already byte-identical to the app's (scenes 2-10 verified); the
family byte was the only difference on the wire. Switching to 0x0B is safe for
devices that worked on 0x0A, because 0x0B is what the official app sends to
these exact devices (proven by both captures).

**Rule of thumb**: when adding a command builder, take the cmd_family byte
from the capture too, not just the payload. 0x0A = query, 0x0B = command.

**Files fixed**:
- `custom_components/lednetwf_ble/protocol.py` (both segment builders now 0x0B)

---

## Products Not in Current Database

These product IDs appear in documentation but NOT in the current app database:

| Product ID | Notes |
|------------|-------|
| 0x04 (4) | Ctrl_RGBW_UFO - may be legacy |
| 0x1D (29) | FillLight - "stub" device, probe dynamically |
| 0x25 (37) | Ctrl_RGBCW_Both - may be legacy |
| 0x3B (59) | Bulb_RGBCW - may be legacy |
| 0xA7 (167) | Symphony_new - may be legacy |
| 0xA9 (169) | Symphony_new - may be legacy |

These are marked with (†) in the documentation.

---

## Mic Detection Method

**Key Finding**: The app uses database lookups, NOT dynamic detection.

The app determines mic support by:
1. Looking up `productId` in device database
2. Checking for `musicMic` in `tab_ui` config
3. Checking for `symp_mic_info` or `get_mic_info` in `functions`

There is NO "query device for mic capability" command.

**Implications for integration**:
- Hardcoding mic capability per product ID is the correct approach
- This matches what the official app does

---

## IOTBT / Telink Mesh Notes

**Key Finding**: IOTBT devices use completely different protocol.

- Company ID: 0x1102 (Telink)
- Product ID in advertisements: Usually 0x00
- Music command: 0xE1 0x05 format (46 bytes)
- State in advertisement: Offset 10 (not 14)

Do NOT apply ZengGe parsing to Telink devices.

---

## Service Data vs Manufacturer Data

**Key Finding**: BLE v7+ devices split data between service data and manufacturer data.

- **Service data** (UUID 0xFFFF): Device ID, version info (16 bytes)
- **Manufacturer data**: State info at offset 3 (not 14)

For v7+, parse device ID from service data, state from manufacturer data.

---

## Verification Checklist

Before confirming any device capability claim:

- [ ] Check `ble_devices.json` for the product ID
- [ ] Verify `hexCmdForms` for actual command format
- [ ] Check `functions` array for feature support
- [ ] Check `wifi_device_panel.json` for UI tabs
- [ ] Note if product is marked (†) not in database
