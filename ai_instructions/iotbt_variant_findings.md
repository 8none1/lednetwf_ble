# Findings: distinguishing IOTBT command-set variants (IOTBT812 vs IOTBT6BA segment lamp)

Investigation of `iotbt_variant_investigation.md`. Sources used:
- Decompiled Surplife app at `/home/will/source/jadx/projects/surplife/`
- Our own protocol parser `custom_components/lednetwf_ble/protocol.py`
- **The #83 btsnoop HCI capture** (GitHub issue #83 attachment), which turned out to be
  the decisive evidence. It contains IOTBT6BA's real advertisement **and** the app's
  unencrypted GATT writes to it.

---

## TL;DR

- **The leading hypothesis is WRONG.** `ble_version` does NOT distinguish the two devices:
  **both IOTBT6BA and IOTBT812 advertise `ble_version = 0x07`.** Do not gate on it.
- The two devices differ only in service-data **bytes 8-13**. In our parser's terms
  (`parse_service_data`, the 14-byte branch, protocol.py:2210-2240) the class-level
  differences are **`led_version` (byte 10)** and **`mode` (byte 11)**:

  | field (our name)      | byte | IOTBT6BA (segment, WORKS) | IOTBT812 (BROKEN) |
  |-----------------------|------|---------------------------|-------------------|
  | sta                   | 0    | 0x80                      | 0x80              |
  | **ble_version**       | 1    | **0x07**                  | **0x07**          |
  | mac                   | 2-7  | 08:65:F0:BB:B6:BA         | 08:65:F0:17:58:12 |
  | mesh_address (8-9 BE) | 8-9  | 0x00AD                    | 0x00C2            |
  | **led_version**       | 10   | **0x1F (31)**             | **0x0E (14)**     |
  | **mode**              | 11   | **0x0A (10)**             | **0x03 (3)**      |
  | flags                 | 12   | 0x01                      | 0x01              |
  | flags2                | 13   | 0x0D (13)                 | 0x05 (5)          |

  `mesh_address` (8-9) and `mac` are per-device, not class signals. The usable
  class discriminators are **`led_version`** and **`mode`**.

- **IOTBT6BA's segment command set is fully confirmed** from the capture (unencrypted,
  byte-for-byte below). It matches our existing builders.
- **IOTBT812's correct colour/effect commands are NOT recoverable** from available
  evidence (see "What we cannot determine" below). They are built in the app's Flutter/Dart
  layer, which is an AOT snapshot and is not decompiled; the segment opcodes appear nowhere
  in the decompiled Java or the JSON assets; and there is no HCI capture of the app driving
  an IOTBT812. The fallback in the brief applies: capture an HCI snoop of the app changing
  colour / running an effect on IOTBT812, exactly as was done for #83.

---

## Discriminator

**Field: NOT `ble_version`.** Proven from the #83 capture: IOTBT6BA's service-data advert is
`80 07 08 65 F0 BB B6 BA 00 AD 1F 0A 01 0D` (byte 1 = `0x07`), identical `ble_version` to
IOTBT812's `80 07 08 65 F0 17 58 12 00 C2 0E 03 01 05` (byte 1 = `0x07`).

This also lines up with how `ble_version` is actually used in the app: in
`surplife/sources/sources/com/zengge/hagallbjarkan/device/ZGHBDevice.java` the `>=5`/`>=6`/`>=7`
checks (lines 116, 147, 152, 188) only change how the **advertisement/state packet is parsed**
(packet layout, firmware-version width, 25-byte state at offset 3 for v7), not which colour/effect
command family is built. Our own `protocol_docs/02_manufacturer_data.md` (lines 98-107, 202)
encodes the same `>=7` parse tiers. So `ble_version` was never a command-family selector; it is a
wire-format version, and here it is the same on both devices.

**Recommended discriminator: `led_version` (byte 10) and/or `mode` (byte 11).**
IOTBT6BA (confirmed-working segment lamp) is `led_version = 0x1F`, `mode = 0x0A`. IOTBT812
(confirmed-broken) is `led_version = 0x0E`, `mode = 0x03`. Both fields are already parsed by
`parse_service_data` (protocol.py:2215-2216) and stored on the device
(`device.py:2110-2111`, `self._led_version`), so no new parsing is needed.

**Caveat / honesty:** with only two devices we cannot be certain *which* of `led_version` /
`mode` is the field the app keys on (that decision lives in non-decompiled Dart). What we can
say for certain is that the **current detection is too broad** and that is the actual bug:
`is_iotbt_segment_from_manu_data` (protocol.py:2486-2525) returns `True` for *any* non-Telink
`0x5A**` device, so it routes IOTBT812 onto the segment command set too. The safe fix is to
narrow segment routing rather than widen it (see "Recommended safe fix").

---

## IOTBT6BA segment command set (CONFIRMED from #83 capture)

All writes go to GATT handle `0x0003` and use the standard wrapped envelope
`00 <seq> 80 00 00 <plen-1> <plen> | <payload>` (the `00 80 00 00` wrapper this integration
already uses). Payloads below are the bytes *after* the 7-byte envelope. Every payload starts
with the constant `0B`.

### Power — opcode `0x3B` (matches `build_iotbt_segment...`/`build_color_command_0x3B` family)
```
0B 3B 24 00 00 00 00 00 00 00 32 00 00 91
   ^^ ^^                      ^^       ^^
   |  power: 0x24=OFF 0x23=ON |        checksum
   opcode 0x3B                0x32=50
```
This is the command the owner confirmed works on **both** devices.

### Colour — opcode `0xE1 0x03` per-segment HSV (matches `build_iotbt_segment_color_command`)
```
0B E1 03 00 14 00 00 14  [A1 HH SS VV] x20
      ^^^^^ ^^                 ^^ ^^ ^^
      |     0x14 = 20 segments hue sat val   (per-segment, A1 = segment marker)
      colour opcode
```
e.g. solid red-ish `A1 00 64 64` x20 (H=0, S=100, V=100); white `A1 00 00 64`;
the count field (`00 14`) and the trailing `00 00 14` track the 20-segment payload.

### Effect / scene — opcode `0xE1 0x01` palette (matches `build_iotbt_segment_effect_command`)
```
0B E1 01 00 64 <effid> 00 01 64 <speed> 00 A1 00 00 00 <n>  [A1 HH SS VV] x n
      ^^^^^ ^^ ^^       ^^             ^^                ^^
      |     |  effect   speed (e.g.    |                 palette colour count
      |     brightness=0x64=100        envelope          (each A1 H S V)
      effect opcode
```
Observed effect IDs 0x02/0x03/0x05/0x09/0x14, speeds 0x14-0x50, palettes of 3-7 colours.

These three confirm the existing `protocol.py` builders are correct for the IOTBT6BA class.

---

## What we cannot determine (and why)

**IOTBT812's correct colour and effect commands.** None of the available artifacts contain them:

1. **JSON assets** (`ble_devices.json`, `wifi_dp_cmd.json`, etc. under
   `surplife/.../magichome2_home_data_provide/assets/`) are keyed by `productId` and only hold
   the standard WiFi/LEDnetWF templates (`0x31`/`0x41`/`0x42`/`0x38`). The segment opcodes
   `0xE1 0x03` / `0xE1 0x01` / `0xE0 0x02` **appear nowhere** in any JSON asset (verified by
   grep across the whole assets dir). The `0x5A00` IOTBT devices are not in the productId DB at
   all - they go through the ZGHB (`com.zengge.hagallbjarkan`) path, which is why this
   integration force-sets `product_id = 0`.
2. **Decompiled Java** (`com.zengge.hagallbjarkan.*`) is only the BLE transport/framing layer
   (`HBConnectionImpl`, `ZGHBWriteUtils`, `UpperTransportLayer`); it contains no colour/effect
   opcodes. The command *bytes* are assembled in the Flutter/Dart layer, which is shipped as an
   AOT snapshot in `flutter_assets/` and is not present as readable source.
3. **No IOTBT812 HCI capture exists.** The #83 capture is IOTBT6BA only.

So we cannot say from the app whether IOTBT812 wants standard `0x41`/`0x3B` colour, a different
segment parameterisation, or something else. The hypothesis in the brief (IOTBT812 is a plain
addressable LEDnetWF) is plausible (it accepts `0x3B` power and has a lower `led_version`) but
**unproven**.

**Fallback (recommended): capture IOTBT812.** Snoop the Surplife app while it changes colour and
runs an effect on the IOTBT812, decode the handle-`0x0003` writes exactly as above. That will
give the real templates in one session. (Owner has the app and the device.)

---

## Recommended safe fix (does not regress IOTBT6BA)

The bug is that `is_iotbt_segment_from_manu_data` (protocol.py:2486) treats every non-Telink
`0x5A**` device as a segment device, so IOTBT812 is wrongly sent `0xE1 03`/`0xE1 01`.

1. **Narrow segment detection** to the confirmed-working profile. Gate the segment route on the
   service-data identity, e.g. require `led_version >= some_threshold` and/or `mode == 0x0A`,
   using the values already parsed into `self._led_version` / `mode`. IOTBT6BA = `led_version
   0x1F`, `mode 0x0A`; IOTBT812 = `led_version 0x0E`, `mode 0x03`. This keeps 6BA on the segment
   path and pulls 812 off it.
2. **Until 812's real commands are captured**, do not send 812 the segment colour/effect
   commands (they do nothing). Power (`0x3B`) is safe and works.
3. Once an IOTBT812 capture exists, add its colour/effect builders and route 812 to them on the
   same `led_version`/`mode` discriminator.

---

## ⚠️ Caveat added after dispatch review (do NOT just narrow detection)

The "narrow segment detection" fix above is **not safe as written**. It traces the detection
(`protocol.py`) but not the command dispatch (`device.py`). The power/colour dispatch is a
three-way `if/elif/else`:

```python
if self.is_iotbt_segment:   build_power_command_0x3B()   # 0x3B  <- 812 is here now; power WORKS
elif self.is_iotbt:         build_iotbt_power_command()  # 0x71 Telink
else:                       build_power_command_0x3B()   # 0x3B
```
(`device.py:1276-1283` power, `1290-1299` power off, `1378-1393` colour.)

If we narrow `is_iotbt_segment` to exclude IOTBT812, it falls to `elif self.is_iotbt` (it is
name-forced `product_id 0x00`, so `is_iotbt` is True) and gets **`0x71` Telink power**, which
**breaks the power that currently works**, plus `0xE2` colour (still wrong). Net regression.

Therefore a correct fix must route the 812-class to the **`else` / standard `0x3B`** path
(0x3B power + `build_color_command_0x3B`), NOT let it fall to the Telink `elif`. That likely
means making 812-class neither `is_iotbt_segment` nor `is_iotbt`, keyed on `led_version`/`mode`.
Whether standard `0x3B` colour actually drives an 812 is **unproven** and still needs the HCI
capture before we change anything. Until then: change nothing, 812 keeps working power.

## IOTBT812 commands — DECODED from capture (pcap/surplife.pcapng, 2026-06-27)

Owner captured the Surplife app driving IOTBT812 (MAC 08:65:F0:17:58:12). 125 GATT writes to
handle 0x0003, standard `00 <seq> 80 00 00 <len> <len+1> 0a` envelope. Payloads (after envelope):

| Action | Payload | Opcode | Matches our builder? |
|---|---|---|---|
| Power on / off | `71 23` / `71 24` | `0x71` (Telink) | `build_iotbt_power_command` ✓ |
| Colour (hue+bri) | `E2 0B <hue> <0xE0\|level>` e.g. `e20b51ff` `e20ba1ff` `e20b01e0..ff` | `0xE2` (Telink) | `build_iotbt_color_command` ✓ **exact** |
| Effect select (~50) | `E0 02 00 <id> 50 50`, id `0x01`..`0x32` | `0xE0 0x02` (Telink) | `build_iotbt_effect_command` ✓ format (but we clamp id to 12) |
| Effect brightness | `E0 14 00 <lvl> 01 90 00 01`, lvl 1-4 | `0xE0 0x14` | not implemented |
| Effect speed | `E0 0E 01` | `0xE0 0x0E` | not implemented (we use the speed byte in 0xE0 0x02) |
| IC type | `E1 0A 01 <t> 00`, t: 1=Common 2=SM16703P 3=WS2812E 4=UC1903B | `0xE1 0x0A` | not implemented |
| (one) scene | `E1 01 00 64 65 00 01 64 50 00 A1 ...palette` (effect 0x65) | `0xE1 0x01` | exists (segment effect) |

**Conclusion: IOTBT812 is the old-Telink command family** (`0x71`/`0xE2`/`0xE0 0x02`), NOT segment,
despite advertising in the `0x5A00` family. Our existing Telink builders are byte-exact for power
and colour. So the fix is **detection-only**: route 812-class to the standard IOTBT (Telink) path.

This resolves the earlier "narrowing breaks power" caveat: `0x71` IS 812's correct power, so letting
it fall to the `elif self.is_iotbt` (Telink) branch in `device.py:1279` is exactly right. (The
`0x3B` power we currently send also happens to work — the device tolerates it — but `0xE1 0x03`
colour does not, which is the actual breakage.)

### Recommended fix
Narrow segment detection so only the 6BA-class profile routes to segment, keyed on
**`led_version`** (6BA `0x1F` segment vs 812 `0x0E` Telink) — preferred over `mode` because
led_version looks like a stable firmware attribute whereas `mode` may be operating state. Default
the rest of the `0x5A**` family to Telink. CAVEAT: this is a 2-device heuristic; the exact
threshold is unconfirmed. More captures from other segment/Telink units would let us set it
properly.

### Bonus follow-ups (not required for the core fix)
- IOTBT (Telink) effect list is only 12 in `const.IOTBT_EFFECTS`; this device has ~50. Expand later.
- IC-type config (`0xE1 0x0A 01 <t> 00`) could become an LED-type setting for Telink IOTBT.

## Confidence

- **HIGH**: `ble_version` is identical (0x07) on both and is not the discriminator. (Direct
  bytes from the #83 capture.)
- **HIGH**: IOTBT6BA segment command bytes (power `0x3B`, colour `0xE1 0x03`, effect `0xE1 0x01`)
  - read directly from the app's own writes.
- **HIGH**: current detection over-matches (catches 812) - that is the root bug.
- **MEDIUM**: `led_version`/`mode` are the right class discriminators. Strong (they are the only
  stable class-level differences and are already parsed) but unconfirmed against the app's Dart
  selection logic, and based on a sample of two devices.
- **NOT DETERMINED**: IOTBT812's correct colour/effect command bytes - require an HCI capture of
  the app driving an IOTBT812.

## Raw evidence (for re-verification)
- IOTBT6BA service-data advert (UUID 0x5A00):
  `80 07 08 65 F0 BB B6 BA 00 AD 1F 0A 01 0D`
- IOTBT6BA manufacturer-data state broadcast (company 0x5A00):
  `80 24 25 09 64 F0 1C E4 64 00 00 01 00 39 FF FF FF FF 01 00 00 01 00 00 00 00 00`
- IOTBT812 service-data advert (from brief):
  `80 07 08 65 F0 17 58 12 00 C2 0E 03 01 05`
- Capture parsed from `FS/data/log/bt/btsnoop_hci.log` inside the #83 bugreport zip
  (https://github.com/user-attachments/files/29181974/btsnoop_hci.log.zip).

## POST-firmware-update comparison (pcap/surplife_after_upgrade.pcapng, 2026-06-27)

Owner updated IOTBT812's firmware via the Surplife app and re-captured the same actions.

**Protocol opcodes UNCHANGED** — still Telink: `0x71` power, `0xE2` colour, `0xE0 0x02` effects,
`0xE1 0x0A` IC type (now 5 types; new "Common RGBW" = `E1 0A 01 05 02`). Our command builders
remain correct for the payloads.

**But two things changed:**

1. **Advert fields shifted (discriminator is now unreliable):**

   | field | 812 PRE | 812 POST | 6BA (segment) |
   |---|---|---|---|
   | ble_version | 0x07 | 0x08 | 0x07 |
   | led_version | 0x0E | **0x1D** | 0x1F |
   | mode | 0x03 | 0x06 | 0x0A |

   Post-update service data: `80 08 08 65 F0 17 58 12 00 C2 1D 06 01 05`.
   `led_version` moved 0x0E→0x1D, adjacent to 6BA's 0x1F, so it no longer separates Telink from
   segment. **Conclusion: auto-detecting Telink vs segment from advert fields is not reliable
   across firmware. The manual override (Auto/Telink/Segment) must be the primary mechanism.**

2. **Transport framing changed, keyed to `ble_version`:**
   - ble_version 7 (PRE / 6BA): header `00 seq 80 00 <lenHi> <lenLo> <len+1> <cmdfam>` (8 bytes,
     1-byte len+1). Notifications start `0x04`.
   - ble_version 8 (POST): header `01 seq 80 00 <lenHi> <lenLo> <len+1Hi> <len+1Lo> <cmdfam>`
     (9 bytes, 2-byte len+1), version byte `0x01`. Notifications start `0x05`.

   Example power: PRE `0004800000 02 03 0a 7124` vs POST `0104800000 02 00 03 0a 7124`.

   `wrap_command` only emits the v0 (8-byte) header, so a ble_version-8 device will likely reject
   ALL writes (incl. power). This is NOT IOTBT-specific — it affects any LEDnetWF device whose
   firmware reaches ble_version 8. **wrap_command should branch on advertised ble_version
   (>=8 → v1 framing).** Likely higher priority than the Telink/segment split.

## IOTBT segment "LEDs per segment" - confirmed fix + read-back format (issue #83, 2026-06-28)

samoswall confirmed setting LEDs-per-segment works in 2.0.1-beta9, and provided a clean HCI
capture (lednum2.zip) of the Save action.

**Set sequence (app -> device), confirmed byte-for-byte:**
```
E1 08 FF 00 <leds> 00 64 3C 64 78 64 00 00 <segs>   <- live PREVIEW, one per keystroke
E0 14 01 00 00 <leds> <segs> 00                     <- COMMIT, sent on Save (e.g. ...3C 01 00 = 60/1)
```
We now send preview then commit (build_iotbt_segment_led_settings_command +
build_iotbt_segment_led_commit_command). The device may restart to apply (brief disconnect).

**Read-back format (device -> app, 0xEA 0x81 state response payload):**
- `payload[16]`   = segment count
- `payload[17:19]` = LEDs per segment, big-endian
Verified by the 57 -> 60 change in the capture (`...01 00 39...` -> `...01 00 3C...`).

**Decision (Will, 2026):** NOT implementing read-back or sensors for this. The LED count
stays a write-only config item, as it is now; the read-back data isn't worth surfacing. The
format is recorded here only in case that changes.
