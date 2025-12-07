# Sound Reactive Mode Protocol (Built-in Microphone Devices)

**Updated**: 7 December 2025

This document describes how to enable sound-reactive modes on LEDnetWF/Zengge BLE LED devices **with built-in microphones**.

---

## Scope

This documentation covers **only devices with built-in microphones** that process audio on-device. These devices work autonomously once sound reactive mode is enabled - no continuous audio streaming from the phone/host is required.

Phone-processed audio modes (where the app analyzes audio and sends rapid color commands) are **out of scope** as they require continuous high-frequency BLE writes that aren't practical for Home Assistant.

---

## Supported Devices

### Devices WITH Built-in Microphone

Determined by which UI fragment the device uses:
- `MusicModeFragment` = has device mic option (built-in microphone)
- `MusicModeFragmentWithoutMic` = app mic only (no built-in microphone)

| Product ID | Device Name | Command Format | Notes |
|------------|-------------|----------------|-------|
| 0x08 (8) | Ctrl_Mini_RGB_Mic | 5-byte simple | RGB only (rgb_mini_mic protocol) |
| 0x48 (72) | Ctrl_Mini_RGBW_Mic | 5-byte simple | RGBW (rgb_mini_mic protocol) |
| 0xA2 (162) | Ctrl_Mini_RGB_Symphony_new | 13-byte full | Symphony controller |
| 0xA3 (163) | Ctrl_RGB_Symphony_new | 13-byte full | Symphony controller |
| 0xA4 (164) | Ctrl_Mini_RGB_Symphony_new | 13-byte full | Symphony controller (has symp_mic_info) |
| 0xA6 (166) | Ctrl_Mini_RGB_Symphony_new | 13-byte full | Extends 0xA3 |
| 0xA7 (167) | Ctrl_Mini_RGB_Symphony_new | 13-byte full | Symphony controller (†) |
| 0xA9 (169) | Ctrl_Mini_RGB_Symphony_new | 13-byte full | Symphony controller (†) |
| 0xAA (170) | Symphony_Line | 13-byte full | Symphony strip (musicMic UI) |
| 0xAB (171) | Symphony_Line | 13-byte full | Symphony strip (musicMic UI) |
| 0xAC (172) | Symphony_Curtain | 13-byte full | LED curtain (musicMic UI) |
| 0xAD (173) | Symphony_Curtain | 13-byte full | LED curtain (musicMic UI) |

**(†)** = Not found in current app database, may be legacy

### Devices WITHOUT Built-in Microphone

These devices support music mode but only via phone audio processing (not supported):

| Product ID | Device Name | Notes |
|------------|-------------|-------|
| 0xA1 (161) | Ctrl_Mini_RGB_Symphony | Old Symphony protocol, NO mic functions |

**Note**: Previous documentation incorrectly listed 0xA4 (164) as having no mic. App database shows 0xA4 HAS `symp_mic_info` functions.

### How to Detect

```python
product_id = (mfr_data[8] << 8) | mfr_data[9]

# Simple mic devices (5-byte command)
SIMPLE_MIC_DEVICES = {0x08, 0x48}

# Symphony mic devices (13-byte command) - verified from app database
SYMPHONY_MIC_DEVICES = {0xA2, 0xA3, 0xA4, 0xA6, 0xA7, 0xA9}  # 0xA4 HAS mic!

# Symphony line/curtain devices with mic (musicMic UI tab)
SYMPHONY_LINE_MIC_DEVICES = {0xAA, 0xAB, 0xAC, 0xAD}  # 170-173

# 0xA1 (161) specifically does NOT have mic
SYMPHONY_NO_MIC = {0xA1}

has_builtin_mic = product_id in (SIMPLE_MIC_DEVICES | SYMPHONY_MIC_DEVICES | SYMPHONY_LINE_MIC_DEVICES)
```

### How the Android App Detects Mic Support

The app uses a **database-driven approach**:

1. **Product ID lookup** in `data.mdb` (LMDB format) maps productId to capabilities
2. **Tab UI config** determines available modes:
   - `"music"` = Phone mic only (app analyzes audio, sends to device)
   - `"musicMic"` = Device has built-in mic
3. **Protocol naming**: `rgb_mini_mic` = has mic, `rgb_mini` = no mic

**Additional products with built-in mic** (from database analysis):

| Product ID | Protocol | Notes |
|------------|----------|-------|
| 60 | rgb_mini_mic | RGB controller with mic |
| 16 | common | Has mic functions |
| 170-188 | symphony_line | Symphony line lights |
| 172-173 | symphony_curtain | Symphony curtain lights |

---

## Command Format 1: Simple 5-Byte with Sensitivity (0x08, 0x48)

For simple mic devices, use the command with sensitivity control.

### Format (Raw Payload) - From Packet Capture

```
[0x73, enable, sensitivity, 0x0F, checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x73 (115) | Command ID |
| 1 | 0x01/0x00 | 0x01 = Enable, 0x00 = Disable |
| 2 | 0x01-0x64 | Sensitivity (1-100) |
| 3 | 0x0F (15) | Fixed byte |
| 4 | checksum | Sum of bytes 0-3 & 0xFF |

### Example Packets (from BLE packet capture)

**Enable with 33% sensitivity:**

```text
Raw:     73 01 21 0F A4
         ^^ ^^ ^^ ^^ ^^
         |  |  |  |  checksum (0x73+0x01+0x21+0x0F = 0xA4)
         |  |  |  fixed byte
         |  |  sensitivity 0x21 = 33
         |  enable (0x01)
         command ID
```

**Enable with 100% sensitivity (maximum):**

```text
Raw:     73 01 64 0F E7
```

**Enable with 1% sensitivity (minimum):**

```text
Raw:     73 01 01 0F 84
```

**Disable (sensitivity value ignored but required):**

```text
Raw:     73 00 32 0F B4
```

### Sensitivity Range

- **Minimum**: 1 (0x01) - lowest mic gain
- **Maximum**: 100 (0x64) - highest mic gain
- **Default**: 50 (0x32) - recommended starting point

### Advertisement State (Byte 17)

When in sound reactive mode, the device broadcasts sensitivity in manufacturer data byte 17:

| Advertisement Value | Interpretation |
|--------------------|----------------|
| 1-31 | IR remote scale (map to 1-100: `value * 100 / 31`) |
| 32-100 | Direct BLE/app scale (use as-is) |

### Legacy Format (from Java decompile)

The Android app Java code shows an older format that may be legacy:

```
[0x73, 0x7A, 0x7B, state, checksum]
state: 0xF0 = On, 0x0F = Off
```

This format does NOT include sensitivity control. Packet captures from the actual app show the format above with sensitivity is what's actually used.

### Java Source Reference

`tc/b.java` method `o(boolean z10)` (line 1670) - shows legacy format

---

## Command Format 2: Symphony 13-Byte (0xA2, 0xA3, 0xA6, 0xA7, 0xA9)

Symphony devices with built-in microphones use a more complex command with effect selection, colors, and sensitivity.

### Format (Raw Payload)

```
[0x73, enable, mode, effect_id, FG_R, FG_G, FG_B, BG_R, BG_G, BG_B, sensitivity, brightness, checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x73 (115) | Command ID |
| 1 | 0x01/0x00 | 0x01 = Device mic on, 0x00 = Off |
| 2 | 0x26/0x27 | 0x27 (39) = Device mic mode, 0x26 (38) = App mic mode |
| 3 | 1-255 | Effect ID (255 = all colors mode) |
| 4-6 | RGB | Foreground color |
| 7-9 | RGB | Background color |
| 10 | 0-100 | Sensitivity (microphone gain) |
| 11 | 0-100 | Brightness percentage |
| 12 | checksum | Sum of bytes 0-11 & 0xFF |

### Example Packets

**Enable device mic with effect 1, red foreground, blue background, 50% sensitivity, 100% brightness:**
```
Raw:     73 01 27 01 FF 00 00 00 00 FF 32 64 XX
         ^^ ^^ ^^ ^^ ^^^^^^^^^ ^^^^^^^^^ ^^ ^^ ^^
         |  |  |  |  red FG    blue BG   |  |  checksum
         |  |  |  effect 1               |  100% brightness
         |  |  device mic mode (0x27)    50% sensitivity
         |  on (0x01)
         cmd
```

**Disable device mic:**
```
Raw:     73 00 27 01 FF 00 00 00 00 FF 32 64 XX
         ^^ ^^
         |  off (0x00)
         cmd
```

### Java Source

`com/zengge/wifi/COMM/Protocol/z.java`:

```java
private byte[] a(boolean z10, boolean z11, int i10, int i11, int i12, int i13, int i14, BaseDeviceInfo baseDeviceInfo) {
    byte[] bArr = new byte[13];
    bArr[0] = 115;                          // 0x73 command
    bArr[1] = z10 ? (byte) 1 : (byte) 0;    // enable (1) / disable (0)
    bArr[2] = (byte) (z11 ? 38 : 39);       // 0x26 app mic, 0x27 device mic
    bArr[3] = (byte) i10;                   // effect ID
    bArr[4] = (byte) Color.red(i11);        // FG red
    bArr[5] = (byte) Color.green(i11);      // FG green
    bArr[6] = (byte) Color.blue(i11);       // FG blue
    bArr[7] = (byte) Color.red(i12);        // BG red
    bArr[8] = (byte) Color.green(i12);      // BG green
    bArr[9] = (byte) Color.blue(i12);       // BG blue
    bArr[10] = (byte) i13;                  // sensitivity
    bArr[11] = (byte) i14;                  // brightness
    bArr[12] = tc.b.b(bArr, 12);            // checksum
    return bArr;
}
```

### UI Fragment Logic

In `MusicModeFragment.java`, the K2() method builds the command:
- `C0 = true` → App mic mode (z10=false in Protocol/z.java)
- `C0 = false` → Device mic mode (z10=true in Protocol/z.java)

---

## State Detection

### From Manufacturer Data (Byte 15 = mode_type)

When the device is in sound reactive mode, the mode_type byte indicates the active mode:

| mode_type | Value | Device Type | Description |
|-----------|-------|-------------|-------------|
| 0x5D | 93 | Simple (0x08, 0x48) | Sound reactive mode active |
| 0x62 | 98 | Symphony | Sound reactive mode active |

```python
# Check manufacturer data byte 15 for mode_type
mode_type = manu_data[15]

if mode_type == 0x5D:
    # Simple device (0x08, 0x48) in sound reactive mode
    # Byte 17 contains sensitivity (1-100 or 1-31 scale)
    sensitivity = manu_data[17]
    is_sound_reactive = True

elif mode_type == 0x62:
    # Symphony device in sound reactive mode
    is_sound_reactive = True
```

### State Bytes Layout (Sound Reactive Mode)

For simple devices in sound reactive mode (mode_type 0x5D):

```text
Bytes [14:24]: 23 5D 23 XX 00 00 00 00 03 00 0F
               ^^ ^^ ^^ ^^
               |  |  |  sensitivity (1-100)
               |  |  sub_mode (0x23)
               |  mode_type (0x5D = sound reactive)
               power (0x23 = ON)
```

### From Notification Responses

Mode byte in notification responses indicates sound reactive mode:

```python
if mode_type in (0x5D, 0x62):
    # Sound reactive mode active
    pass
```

---

## Implementation Notes for lednetwf_ble_2

### 1. Add Capability Flag to DEVICE_CAPABILITIES

In [const.py](../custom_components/lednetwf_ble_2/const.py), add `has_builtin_mic` flag:

```python
# Simple mic devices (5-byte command)
8:   {"name": "Ctrl_Mini_RGB_Mic", ..., "has_builtin_mic": True, "mic_cmd_format": "simple"},
72:  {"name": "Ctrl_Mini_RGBW_Mic", ..., "has_builtin_mic": True, "mic_cmd_format": "simple"},

# Symphony mic devices (13-byte command)
162: {"name": "Ctrl_Mini_RGB_Symphony_new", ..., "has_builtin_mic": True, "mic_cmd_format": "symphony"},
163: {"name": "Ctrl_RGB_Symphony_new", ..., "has_builtin_mic": True, "mic_cmd_format": "symphony"},
166: {"name": "Ctrl_Mini_RGB_Symphony_new", ..., "has_builtin_mic": True, "mic_cmd_format": "symphony"},
167: {"name": "Ctrl_Mini_RGB_Symphony_new", ..., "has_builtin_mic": True, "mic_cmd_format": "symphony"},
169: {"name": "Ctrl_Mini_RGB_Symphony_new", ..., "has_builtin_mic": True, "mic_cmd_format": "symphony"},

# No built-in mic (DO NOT add has_builtin_mic)
161: {"name": "Ctrl_Mini_RGB_Symphony", ...},  # No music tabs
164: {"name": "Ctrl_Mini_RGB_Symphony_new", ...},  # App mic only
```

### 2. Add Property to LEDNetWFDevice

In [device.py](../custom_components/lednetwf_ble_2/device.py), add properties:

```python
@property
def has_builtin_mic(self) -> bool:
    """Return True if device has built-in microphone for sound reactive mode."""
    return self._capabilities.get("has_builtin_mic", False)

@property
def mic_command_format(self) -> str:
    """Return the mic command format: 'simple' or 'symphony'."""
    return self._capabilities.get("mic_cmd_format", "simple")
```

### 3. Add Sound Reactive Effect to Effect List

In [const.py](../custom_components/lednetwf_ble_2/const.py):

```python
def get_effect_list(..., has_builtin_mic: bool = False) -> list[str]:
    # ... existing logic ...

    # Add sound reactive option for devices with built-in mic
    if has_builtin_mic:
        effects.append("Sound Reactive")

    return effects
```

### 4. Add Protocol Command Builders

In [protocol.py](../custom_components/lednetwf_ble_2/protocol.py):

```python
def build_sound_reactive_simple(enable: bool) -> bytearray:
    """
    Build simple 5-byte sound reactive command for 0x08, 0x48 devices.
    """
    raw_cmd = bytearray([0x73, 0x7A, 0x7B])
    raw_cmd.append(0xF0 if enable else 0x0F)
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0a)


def build_sound_reactive_symphony(
    enable: bool,
    effect_id: int = 1,
    fg_rgb: tuple[int, int, int] = (255, 0, 0),
    bg_rgb: tuple[int, int, int] = (0, 0, 255),
    sensitivity: int = 50,
    brightness: int = 100
) -> bytearray:
    """
    Build 13-byte sound reactive command for Symphony devices (0xA2, 0xA3, etc).

    Args:
        enable: True to enable device mic, False to disable
        effect_id: Effect number (1-255, 255 = all colors)
        fg_rgb: Foreground color tuple
        bg_rgb: Background color tuple
        sensitivity: Microphone sensitivity 0-100
        brightness: Brightness percentage 0-100
    """
    raw_cmd = bytearray([
        0x73,                           # Command
        0x01 if enable else 0x00,       # Enable/disable
        0x27,                           # Device mic mode (0x27)
        effect_id,                      # Effect ID
        fg_rgb[0], fg_rgb[1], fg_rgb[2],  # FG RGB
        bg_rgb[0], bg_rgb[1], bg_rgb[2],  # BG RGB
        sensitivity,                    # Sensitivity
        brightness                      # Brightness
    ])
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0a)
```

### 5. Handle Effect Selection

In [light.py](../custom_components/lednetwf_ble_2/light.py):

```python
async def async_set_effect(self, effect: str) -> None:
    """Set the effect."""
    if effect == "Sound Reactive":
        if self._device.has_builtin_mic:
            if self._device.mic_command_format == "symphony":
                cmd = build_sound_reactive_symphony(
                    enable=True,
                    effect_id=1,
                    sensitivity=50,
                    brightness=self._device.brightness_percent
                )
            else:
                cmd = build_sound_reactive_simple(enable=True)
            await self._device.send_command(cmd)
            self._device._effect = effect
            return
    # ... existing effect handling ...
```

### 6. Handle Exiting Sound Reactive Mode

```python
# In color/effect setting methods:
if self._device._effect == "Sound Reactive" and self._device.has_builtin_mic:
    if self._device.mic_command_format == "symphony":
        cmd = build_sound_reactive_symphony(enable=False)
    else:
        cmd = build_sound_reactive_simple(enable=False)
    await self._device.send_command(cmd)
```

---

## Testing Checklist

- [ ] Device 0x08 shows "Sound Reactive" and uses 5-byte command
- [ ] Device 0x48 shows "Sound Reactive" and uses 5-byte command
- [ ] Device 0xA3 shows "Sound Reactive" and uses 13-byte command
- [ ] Device 0xA2/0xA6/0xA7/0xA9 work with 13-byte command
- [ ] Device 0xA4 does NOT show "Sound Reactive" option
- [ ] Selecting "Sound Reactive" enables microphone mode
- [ ] LED responds to ambient sound when enabled
- [ ] Exiting sound reactive mode works correctly

---

## Java Source References

| File | Method/Class | Purpose |
|------|--------------|---------|
| `tc/b.java` | `o(boolean)` | Simple 5-byte command (0x08, 0x48) |
| `Protocol/z.java` | class | 13-byte Symphony command |
| `MusicModeFragment.java` | K2() | Builds Symphony sound reactive command |
| `MusicModeFragment.java` | P2() | Toggles app mic vs device mic |
| `MusicModeFragmentWithoutMic.java` | - | Devices without built-in mic |
| `BaseDeviceInfo.java` | `M0()` | Returns true if device supports music mode |
