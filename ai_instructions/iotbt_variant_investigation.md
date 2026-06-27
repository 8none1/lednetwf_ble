# Investigation: distinguishing IOTBT command-set variants (IOTBT812 vs #83 segment lamp)

## Your task

Using the **decompiled Surplife / MagicHome app**, find out two things:

1. **The discriminator.** What value (or logic) the app uses to decide which colour/effect
   **command set** to send to an "IOTBT"-named / ZengGe-`0x5A00`-family device. We have two
   such devices that advertise almost identically but need *different* commands (details
   below). We need a field we can read from the advertisement, the GATT connection, or the
   device's state reply that reliably tells them apart.
2. **The correct commands for the IOTBT812-class device.** The exact colour-set and
   effect/scene command byte templates the app sends to control IOTBT812 (the device that
   currently does **not** respond to our segment commands).

Deliverable: a written answer with the discriminator and the exact command templates,
**with file:line references into the decompiled app**, so we can implement detection +
handlers without regressing the device that already works.

> Hard constraint: the fix must NOT break the already-working segment lamp (issue #83,
> "IOTBT6BA"). Because the two devices look nearly identical over BLE, a naive detection
> change risks rerouting both. The whole point of this investigation is to find a *safe*
> discriminator.

## Background (what this project is)

Home Assistant integration `lednetwf_ble` controls Zengge/Surplife/MagicHome BLE lights.
Code lives in `custom_components/lednetwf_ble/`. Protocol notes in `protocol_docs/`.
"IOTBT"-named devices are forced to `product_id = 0x00` and handled specially. Among them
there are (at least) these command families:

| Family | Power | Colour | Effects | Notes |
|---|---|---|---|---|
| Old Telink mesh | `0x71` | `0xE2` (quantised hue) | `0xE0 0x02` | company ID `0x1102` |
| "Segment" (issue #83) | `0x3B` | `0xE1 0x03` (per-segment HSB) | `0xE1 0x01` (palette) | company/service `0x5A00`, status `0x80`, **works on IOTBT6BA** |
| Standard LEDnetWF | `0x3B` | `0x41` / `0x3B`-colour | `0x42` / `0x38` | what IOTBT812 *might* actually be |

Relevant code:
- `protocol.py`: `build_iotbt_segment_color_command` (0xE1 0x03),
  `build_iotbt_segment_effect_command` (0xE1 0x01), `build_color_command_0x3B`,
  `build_static_effect_command_0x41`, `build_iotbt_color_command` (0xE2),
  `is_iotbt_segment_variant` (service-data status `0x56`),
  `is_iotbt_segment_from_manu_data` (company ID `0x5A**`).
- `device.py`: `is_iotbt_segment` property and the `async_update` detection that sets it.
- `const.py`: `PRODUCT_CAPABILITIES`, `EffectType`.

## The two devices (captured live from Home Assistant)

### IOTBT812 — BROKEN (only power works)
- Name `IOTBT812`, BLE address `08:65:F0:17:58:12`.
- `ble_version = 7`, `led_version (led_ver) = 14`, `mesh_addr = 0x00C2`, status byte `0x80`.
- Advertises **service data** under UUID `0x5A00` (no manufacturer data under passive scan):
  - service data (14 bytes): `80 07 08 65 F0 17 58 12 00 C2 0E 03 01 05`
    (parsed: sta=`0x80`, ble_v=7, mac=08:65:F0:17:58:12, mesh=0x00C2, led_ver=14, mode=`0x03`, flags=`0x01`)
- Intermittently advertises **manufacturer data** under company `0x5A00` (a *state broadcast*,
  NOT the standard product-ID format):
  - `80 23 66 01 32 F0 00 00 00 00 00 01 01 90 00 00 01 02 03 00 ...`
    (byte0 status `0x80`, byte1 power `0x23`=on, byte5 `0xF0`=colour-mode marker)
- State reply to query `0xEA 0x81` (payload after the 8-byte transport header):
  - `EA 81 01 00 C2 03 23 67 0C 32 F0 00 00 00 00 00 01 01 90 00 00 01 02 03 00`
- Behaviour (confirmed by the device owner):
  - **Power `0x3B 0x23/0x24` WORKS** (lamp physically turns on/off).
  - **Segment colour `0xE1 0x03` does NOTHING.**
  - **Segment effects `0xE1 0x01` do NOTHING.**

### IOTBT6BA — WORKS (issue #83, owner: samoswall)
- Name `IOTBT6BA`, company/service `0x5A00`, status byte `0x80`.
- Fully controllable with the **segment** command set (`0x3B` power, `0xE1 0x03` colour,
  `0xE1 0x01` effects). Confirmed working in beta2/beta3.
- (TODO: confirm this device's `ble_version` / `led_version` from issue #83 logs — see
  the GitHub issue. If IOTBT6BA is `ble_version 5` while IOTBT812 is `ble_version 7`, that
  is a prime discriminator candidate.)

### Key observation / leading hypothesis
The two are nearly indistinguishable over BLE (both `IOTBT*`, `0x5A00`, status `0x80`), yet
IOTBT812 ignores segment colour/effects while responding to `0x3B` power. Since `0x3B` power
is the *standard LEDnetWF* power command, IOTBT812 may actually be a **standard LEDnetWF
addressable device** (wants `0x41`/`0x3B` colour) rather than a segment device. The most
promising machine-readable discriminator we have so far is **`ble_version` (7 vs likely 5)**
and/or **`led_version`** — confirm whether the app branches command selection on these.

## Where to look in the decompiled app

App is at `/home/will/source/jadx/projects/`:
- `surplife/` (and `surplife.jadx`) — Surplife build.
- `zengee/` (and `zengee.jadx`) — Zengge build (cross-check; may be clearer).

Note: the Java is **heavily obfuscated** and class layout has shifted between versions
(e.g. `tc/b.java` referenced in older notes is gone; only `tc/a.java` remains). Search by
behaviour and byte patterns, not by remembered paths.

Promising places:
1. **Flutter / data-driven command templates** (most likely to hold the answer cleanly):
   `*/assets/flutter_assets/packages/magichome2_home_data_provide/assets/`
   - `ble_devices.json` — device/model → capability mapping. Look for how an IOTBT /
     `0x5A00` device, or a device of `ble_version`/`led_version` like IOTBT812's, maps to a
     colour/effect command set.
   - `wifi_dp_cmd.json` (and any `ble_*` / `dp_cmd` variants) — command byte templates
     (e.g. `colour_data_v2`, `bright_value_v2`). Find which colour/effect template applies.
   - `wifi_device_panel.json` — UI/capability tabs per device type.
2. **BLE write path / protocol selection** in code:
   - Search for the ZengGe BLE class samoswall referenced: `com.zunge.hagallbjarkan...`
     (`HBConnectionImpl`, `writer.bytes`).
   - Grep for the opcodes as ints: `0xE1`=225, `0x3B`=59, `0x41`=65, `0xE2`=226, `0x42`=66,
     and the marker `0x5A`=90 / `0x5A00`=23040.
   - Grep for `bleVersion` / `ble_version` / `ledVersion` / `chipType` / model-type switches
     that gate which builder is used.

## Questions to answer (be specific, cite file:line)

1. How does the app choose the colour command family for an IOTBT / `0x5A00` device? What
   field drives it (`ble_version`? `led_version`? a model/type code? a capability flag)?
2. For a device matching IOTBT812 (status `0x80`, `0x5A00`, `ble_version 7`, `led_version 14`),
   what is the exact **colour** command (byte template, with where R/G/B/H/S/V/brightness go)?
3. What is the exact **effect/scene** command for that device?
4. What single field/value reliably separates the IOTBT812 class from the IOTBT6BA segment
   class? (We need this for safe detection.)

If the app cannot be read clearly enough to answer, say so explicitly — the fallback is to
capture the app's own BLE writes (`HBConnectionImpl: writer.bytes`, or an HCI snoop) while
changing colour and running an effect on IOTBT812, exactly as was done for issue #83.

## How to report back

Write findings to `ai_instructions/iotbt_variant_findings.md` (create it), structured as:
- Discriminator: <field + exact values for each class, with file:line>
- IOTBT812 colour command: <hex template + field map, with file:line>
- IOTBT812 effect command: <hex template + field map, with file:line>
- Confidence + anything ambiguous.
