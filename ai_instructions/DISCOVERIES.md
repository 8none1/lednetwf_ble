# Discoveries and Corrections Log

This document tracks significant findings and corrections made during the reverse engineering process.

## Documentation Errors Found and Fixed

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
