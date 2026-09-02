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

---

### Never pair 0x3B brightness with a colour command (write-without-response)

**Date**: 2 August 2026 (issue #99)

Commands are sent write-without-response (`_send_command` defaults to
`with_response=False`), so two writes issued back to back land about 1ms
apart. If a `0x3B 0x01` brightness command follows a `0x31` colour command
that closely, the device has not yet committed the colour, and `0x3B`
rescales the colour it *still holds* - cancelling the change.

Observed on a green light asked repeatedly for pure blue: the blue channel
crept 0 -> 16 -> 28 over three attempts and never arrived, because each `0x31`
only had ~1ms to act before the `0x3B` reasserted green.

`bright_value_v2` itself is fine and does exactly what it says. Verified in
the same log: 1% on a green light gives `(0,3,0)`, 100% restores `(0,255,0)`.

**Rules:**

- Brightness-only change: use `0x3B 0x01`. One command, no colour re-send, and
  it does not re-trigger a running effect.
- Colour change: put the brightness in the scaled RGB of the `0x31` and send
  nothing else. The device stores the scaled RGB anyway, which is why
  deriving brightness back out of the reported RGB via HSV is correct.

---

### SIMPLE state layout confirmed by capture (product 0x08)

**Date**: 2 August 2026 (issue #99)

An nRF Connect capture of the 0x81 notifications, cross-checked against the
commands the integration sent, pins the layout down. Every checksum verified.

Effect running (`mode_type` = effect ID, 37-56):

| Byte | Meaning |
|------|---------|
| 3 | Effect ID (37-56). NOT a 0x25 mode marker |
| 4 | Sub-mode: echo of the power state (0x23=ON, 0x24=OFF) |
| 5 | **Effect speed, inverted 1-31** |
| 6-8 | The colour the effect is showing *right now*, changes constantly |

Solid colour:

| Byte | Meaning |
|------|---------|
| 3 | 0x61 |
| 4 | Echo of the power state (0x23/0x24), NOT a colour-mode marker |
| 5 | Effect speed, retained from the last effect |
| 6-8 | The solid RGB colour |

**Evidence for byte 5 being the speed.** The outbound command is
`38{model}{speed}{bright}`, so a pair only tells us anything when speed and
bright differ:

| Sent | speed | bright | Response `value1` | Discriminates? |
|------|-------|--------|-------------------|----------------|
| `38 25 10 1E` | 16 | 30 | 16 | Yes - matches speed |
| `38 25 01 01` | 1 | 1 | 1 | No - both fields are 1 |
| `38 25 1F 01` | 31 | 1 | 31 | Yes - matches speed |

Two discriminating observations, and they are complementary: the speed is the
larger of the two fields in one and the smaller in the other, so the match is
not an artefact of always picking the bigger byte.

The advertisement byte is separately confirmed, and this is the one that was
corrupting the brightness. At a point where the device's brightness was 100
(set via `3b 01 ... 64`) and its speed was 31 (set via `38 25 1F 01`), advert
byte 17 read 31. Directly discriminating, not just positional alignment.

**Brightness is confirmed absent from the effect-mode state.** A later
controlled test settled this: with an effect running and everything else left
alone, brightness was changed to 15%, and the advertisement state block was
byte-for-byte identical before and after.

```
before 15%   23 38 23 10 FF 00 00 00 03 00 F0
after  15%   23 38 23 10 FF 00 00 00 03 00 F0   <- identical
later        23 38 23 10 FF 00 FF 00 03 00 F0   <- only the live RGB moved
```

Consequence: **brightness changed by any other controller (IR remote, the
app) cannot be detected while an effect is running.** The device does not
report it. This is a protocol limitation, not something to fix.

Note also that the RGB reported in effect mode is the effect's nominal colour
at full intensity, NOT scaled by brightness - the (255,0,0) above was
captured while the light was at 15%. This is the opposite of solid-colour
mode, where the reported RGB *is* brightness-scaled. Never derive brightness
from the RGB in effect mode.

**Brightness is not reported at all while an effect is running.** The old docs
claimed byte 6 was the brightness in effect mode, which is wrong for this
family - byte 6 is the red channel of the live effect colour.

The advertisement state block mirrors this from byte 14 onwards, so advert
byte 17 is the speed, not the brightness as previously assumed:

```
advert[14] = power     <-> response[2]
advert[15] = mode_type <-> response[3]
advert[16] = sub_mode  <-> response[4]
advert[17] = speed     <-> response[5]
advert[18:21] = rgb    <-> response[6:9]
```

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

**Amendment, 31 August 2026**: that rule holds for the *segment* family, but is
not universal. The IOTBT812 (Telink family) capture shows the app using `0x0A`
for all 125 writes, including `E0 02` effect selects and `E2 0B` colour. So the
family byte is itself family-dependent: take it from a capture of the device in
front of you, and do not "correct" a Telink-family builder to `0x0B` on the
strength of the segment captures alone.

**Files fixed**:
- `custom_components/lednetwf_ble/protocol.py` (both segment builders now 0x0B)

---

### 0xE0 and 0xEA are ZengGe commands, not Telink opcodes

**Date**: 31 August 2026 (PR #101)

**Error**: `protocol_docs/17_device_configuration.md` listed our IOTBT effect
command (`0xE0 0x02`) and state query (`0xEA 0x81`) directly under a "Telink BLE
Mesh Opcode Reference" taken from `com/telink/bluetooth/light/Opcode.java`,
where `0xE0` is "set device address" and `0xEA` is "user all". That framing made
these look like mesh opcodes that only Telink-family hardware would understand.

**Reality**: both are ordinary ZengGe app commands, present verbatim in
`assets/flutter_assets/packages/magichome2_home_data_provide/assets/wifi_dp_cmd.json`:

| Our builder | App template | Template form |
|-------------|--------------|---------------|
| `build_iotbt_effect_command` (`E0 02 00 <id> <speed> <bright>`) | `scene_data_v3` | `e002{preview}{model}{speed}{bright}` |
| `build_iotbt_state_query` (`EA 81 8A 8B`) | `state_upload_v2` | `ea818a8b` |

The `0x00` we send as a constant third byte in the effect command is the
template's `{preview}` flag, not part of the effect payload.

`0xE0` is a general "v3 command wrapper" in the app: `E0 <sub> <preview>`
followed by the v2 payload, with the checksum dropped (`needChecksum: false` on
every `e0` template). `switch_led_v3` = `e001{preview}` + the entire
`switch_led_v2` form proves the pattern.

**Why it matters**: it explains why the `0xE0 0x02` effect command works on
devices that share no other command family, and it means an `0xE0` prefix in a
capture tells you nothing about whether the device is Telink. Only `0xE2`
(colour) and `0x71` (power) in our IOTBT builders are genuinely Telink.

**Files fixed**:
- `protocol_docs/17_device_configuration.md` (new "0xE0 v3 Command Wrapper"
  section, caution added to the Telink opcode table)

---

### `led_version` in the 14-byte IOTBT service data is really the firmware version

**Date**: 31 August 2026

**Error**: `parse_service_data`'s 14-byte branch names byte 10 `led_version` and byte 11
`mode`. Months of IOTBT variant investigation then tried to use `led_version` to tell the
Telink and segment command families apart, and kept finding it unstable.

**Reality**: byte 10 is a firmware version. The IOTBT812 was captured before and after a
real firmware update and byte 10 went `0x0E` -> `0x1D`, i.e. 14 -> 29. That is what a
firmware version byte does; an LED *hardware* version would not move. This one relabelling
explains the whole "the discriminator keeps shifting" saga.

The 14-byte format is the standard 16-byte ZengGe service data with the 2-byte manufacturer
prefix omitted, which realigns every field by -2 and makes bytes 8-9 (currently
`mesh_address`) the **product ID**. Confirmed the same day: PR #101's reporter supplied both
their service data and their `0xEA 0x81` state frame, the same value `0x003E` (62) appears in
both in fields we call "mesh address", and product 62 in `ble_devices.json` declares exactly
the capabilities the device demonstrably has (`colour_data_v3`, `state_upload_v2`,
`temp_value_v2`, protocol `common2_0`). The device speaks the v3 command family *because of
its product ID*. Full evidence: `ai_instructions/iotbt_variant_findings.md`.

The same mislabelling is in the `0xEA 0x81` (DeviceState2) response table in
`protocol_docs/17_device_configuration.md`, which calls bytes 3-4 the mesh address.

**Why it matters**: we force `product_id = 0x00` for these devices in two independent places
(`parse_service_data` hardcodes it, and `parse_manufacturer_data` forces it for any
"IOTBT"-prefixed name at protocol.py:1869 via an early return that also discards ble_version
and all state). If the real product ID is sitting in bytes 8-9, we are discarding it and then
guessing the command family from a heuristic on a mislabelled neighbouring byte. Resolve this
before adding more detection heuristics.

**Partly fixed** in PR #103 (2.0.1-beta14): the fields are now parsed and named correctly,
the product ID is logged, and it drives v3 command-family detection in place of the `flags2`
heuristic. What is deliberately NOT done is using it for capability lookup, because that would
re-resolve capabilities and the command family for every IOTBT device at once - product 173
would become `Symphony_Curtain` and lose the segment command set that IOTBT6BA needs and
currently works on. Remaining work: add product 62 to `PRODUCT_CAPABILITIES` (it declares
`temp_value_v2` and its model name ends in RGBWW, but forced to `product_id = 0x00` it has no
colour temperature support at all), and decide on a fallback for product IDs in neither
database, such as IOTBT812's 194.

---

### `hue // 2` and the packed hue+sat high byte are the same byte

**Date**: 31 August 2026 (PR #101)

**The trap**: our standard `0x3B` colour command packs hue and saturation as
`(hue << 7) | sat` across two bytes. Because `sat` only goes up to 100, it can
never carry into the high byte, so:

```
byte_hi == hue // 2                             for any sat <= 100
byte_lo == sat + (128 if hue is odd else 0)
```

A capture of fully saturated colours is therefore **indistinguishable** from
"hue in half-degree units, followed by a saturation byte". Red, yellow and blue
all give identical bytes under both readings (`00 64`, `1e 64`, `78 64`). The two
only diverge on odd hues, and then only by a half-degree of hue.

**How it bit us**: PR #101 captured a working colour command on a
`product_id=0x00` device and documented it as a new "hue = degrees / 2"
encoding. It is actually the existing packed hue+sat encoding, wrapped in the
`0xE0 0x01` v3 wrapper. The proposed patch worked, but under a description that
would have sent the next person looking for a protocol that does not exist.

**The same misreading is in our segment code.** The `IOTBT_SEGMENT_EFFECT_SCENES`
palette entries in `protocol.py` are documented as
"`b2`/`b3` carry saturation/value plus an anchor flag in the high bit". There is
no anchor flag: `b1`/`b2` are the packed hue+sat pair and `b3` is brightness, so
each palette entry is `A1 <hs_hi> <hs_lo> <bright>`, byte-for-byte the same
four bytes as the `0x3B` colour command's mode + hue/sat + brightness.

Checked against all 166 palette entries from the issue #83 capture:

- Under the packed reading, every entry gives a valid hue (0-340) and
  saturation (0-100). Zero exceptions.
- 76 of the 166 have `b2 > 100`, which is impossible if `b2` were a plain
  saturation byte. Those are exactly the odd-hue entries, where the low byte
  carries `sat + 128`.
- Spot checks decode to obviously-intended colours: `0x96 0x64` = hue 300
  (magenta), `0x00 0x00` = white, `0x63 0xAC` = hue 199 at 44% saturation in
  the "Iceland Blue" scene.

`build_iotbt_segment_color_command` computes `hue_180 = int(h / 2)` and a
separate `sat` byte, which happens to produce the correct packed bytes for even
hues and is a half-degree out on odd ones. Harmless in practice, but it means
the builder silently quantises hue to even degrees when the wire format has full
0-360 resolution. Worth tidying when someone next touches that function.

**Rule**: when decoding a colour command from a capture, test a **desaturated**
colour on an **odd** hue before writing down the encoding. Saturated primaries
cannot distinguish these two formats.

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

---

## IOTBT "v3" variant (0xE0 0x01 colour command)

**Date**: 31 August 2026 (PR #101)

**Device**: Briturn app / JM Zengge "ZJ-BBLA-RGBWW" battery mood light.
Reported by the integration as `product_id=0x00`, `effect_type=IOTBT`,
`ble_version=7`, `firmware_version=68` (byte 10 of the service data below -
this field is commonly labelled `led_version` in this codebase, but it is
the firmware version: confirmed by a before/after firmware-update capture
on another device where this exact byte moved. An LED hardware version
would not change on a firmware update).
`flags2=0x01` (14-byte 0x5A00 service data, MAC-derived bytes redacted:
`5b 07 08 [XX XX XX XX XX] 00 3e 44 0a 01 01`).

**The real product ID was being discarded.** Bytes 8-9 of that service
data (`00 3e` above) are the device's actual product ID: **62**, not
`0x00`. `parse_service_data` hardcodes `product_id: 0` for every 14-byte
device, and `parse_manufacturer_data` separately forces `0x00` for any
device whose name starts with `IOTBT`, so the real ID sitting right there
in the advertisement is thrown away. Product 62 in the vendor app's
`ble_devices.json` declares `colour_data_v3` (the `0xE0 0x01` command
found below), `switch_led_v3`, `state_upload_v2` (matches the `0xEA 0x81`
query captured below), `temp_value_v2`, and protocol family `common2_0`
(the v3 family) - so this device speaks v3 *because of its product ID*,
by the vendor's own classification, not as an edge case. It also means
this device should have colour-temperature (CCT) support - the model name
is literally "...RGBWW" and `temp_value_v2` is declared - but forced to
`product_id=0x00` it inherits `has_ww: False, has_cw: False` and gets no
CCT entity. Wiring up the real product ID is a separate, larger change
(tracked as a follow-up issue) since several products declare functions
that don't fully determine their actual command family on their own.

**Problem**: A third 0x5A00-family variant exists alongside Telink (0xE2
colour) and segment (0xE1 0x03 colour). It does not respond to 0xE2
(quantized or unquantized hue), the standard 0x3B HSV command, or the
legacy 0x31 RGB command - all three are silently accepted over BLE (no
error, write completes) but produce no change on the device. Only power
(0x71) worked, which is what made this look like a Telink device at first.

**Finding**: Captured real traffic from the vendor app via Android's
Bluetooth HCI snoop log while setting the device to known colours (red,
yellow). The app sends:

```
red    (hue=0 deg):  e0 01 00 a1 00 64 64 00 00 00 00 14 00 00
yellow (hue=60 deg): e0 01 00 a1 1e 64 64 00 00 00 00 14 00 00
```

Initially read as a standalone "hue/2 in one byte, then plain saturation"
encoding, since both bytes happened to match that reading for these two
(fully-saturated, even-degree) test colours. Turned out to be the same
packed `(hue << 7) | saturation` encoding already used by
`build_color_command_0x3B`, just wrapped in the vendor app's "v3" envelope
(`e0 01 00 a1 ...`, matching `switch_led_v3` in `wifi_dp_cmd.json`) rather
than the plain `3b a1 ...` form. Confirmed by testing the plain 0x3B
command directly (byte-for-byte what the existing builder produces) - it
does **not** work on this device, so the v3 envelope itself is load-bearing,
not just a detection question.

`cmd_family` confirmed as `0x0a` directly from the captured packet header
(byte 7), not assumed from the app's `needChecksum` field.

See `build_iotbt_v3_color_command()` / `pack_hue_saturation()` in
`protocol.py`, `is_iotbt_v3` in `device.py`, and `IOTBT_PROTOCOL_V3` in
`const.py`. No auto-detection signal found yet - manual override required.

---

## IOTBT 0xEA 0x81 status/notification frame

**Date**: 31 August 2026 (PR #101)

While capturing the v3 colour traffic above, also captured the device's
notification response to its own `0xEA 0x81` state query (sent by the app
right after connecting). Wrapped in a JSON envelope over the notify
characteristic:

```
{"code":0,"payload":"<hex>"}
```

Decoded inner payload:

```
ea 81 00 00 [X] 0a [4 bytes, MAC-independent, device-specific] f0 [hue] 64 64 00 00 00 00 00 00 00 00 00 00
```

The `[hue]` byte correctly mirrors live state (matched the active colour
in every sample), confirming this is a genuine, readable status frame -
useful for anyone adding state polling/sync for this device family.

**Resolved**: byte `[X]` (`0x3E` / 62 decimal on this unit) is the
device's **product ID**, not battery. Confirmed by matching it against the
same field in the service data (see above): both frames agree on this
byte *and* the adjacent one (service-data byte 11 / state-frame byte 5,
both `0x0a`), which rules out coincidence. Originally suspected as
battery percentage since it was constant across samples and the vendor
app doesn't expose battery at all - the fact that it also shows up
unchanged in the passively broadcast advertisement (not just in response
to a query) turned out to be exactly the right instinct that pointed away
from battery and toward a static identifier.

Full annotated capture, including this frame and the colour commands
below: https://gist.github.com/HelloPackets89/f7836b577a714576b206af4ca3574a1f

