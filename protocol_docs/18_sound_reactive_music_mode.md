# Sound Reactive Mode Protocol (Built-in Microphone Devices)

**Updated**: 6 December 2025

This document describes how to enable sound-reactive modes on LEDnetWF/Zengge BLE LED devices **with built-in microphones**.

---

## Scope

This documentation covers **only devices with built-in microphones** that process audio on-device. These devices work autonomously once sound reactive mode is enabled - no continuous audio streaming from the phone/host is required.

Phone-processed audio modes (where the app analyzes audio and sends rapid color commands) are **out of scope** as they require continuous high-frequency BLE writes that aren't practical for Home Assistant.

---

## Supported Devices

| Product ID | Device Name | Effect Type | Notes |
|------------|-------------|-------------|-------|
| 0x08 (8) | Ctrl_Mini_RGB_Mic | SYMPHONY | RGB only, has segments |
| 0x48 (72) | Ctrl_Mini_RGBW_Mic | SIMPLE | RGBW support |

### How to Detect

Check product ID from manufacturer data bytes 8-9:
```python
product_id = (mfr_data[8] << 8) | mfr_data[9]
has_builtin_mic = product_id in (0x08, 0x48)
```

---

## Command: 0x73 - Sound Reactive Enable/Disable

This simple command enables or disables the built-in microphone mode.

### Format (Raw Payload)

```
[0x73, 0x7A, 0x7B, state, checksum]
```

| Byte | Value | Description |
|------|-------|-------------|
| 0 | 0x73 (115) | Command ID |
| 1 | 0x7A (122) | Fixed |
| 2 | 0x7B (123) | Fixed |
| 3 | 0xF0/0x0F | 0xF0 = On, 0x0F = Off |
| 4 | checksum | Sum of bytes 0-3 & 0xFF |

### Example Packets

**Enable sound reactive mode:**
```
Raw:     73 7A 7B F0 58
         ^^ ^^ ^^ ^^ ^^
         |  |  |  |  checksum (0x73+0x7A+0x7B+0xF0 = 0x258, &0xFF = 0x58)
         |  |  |  on (0xF0)
         |  |  fixed
         |  fixed
         cmd
```

**Disable sound reactive mode:**
```
Raw:     73 7A 7B 0F 67
         ^^ ^^ ^^ ^^ ^^
         |  |  |  |  checksum (0x73+0x7A+0x7B+0x0F = 0x167, &0xFF = 0x67)
         |  |  |  off (0x0F)
         |  |  fixed
         |  fixed
         cmd
```

### Java Source

`tc/b.java` method `o(boolean z10)` (line 1670):
```java
public static byte[] o(boolean z10) {
    byte[] bArr = new byte[5];
    bArr[0] = 115;  // 0x73
    bArr[1] = 122;  // 0x7A
    bArr[2] = 123;  // 0x7B
    if (z10) {
        bArr[3] = -16;  // 0xF0 = on
    } else {
        bArr[3] = 15;   // 0x0F = off
    }
    bArr[4] = b(bArr, 4);  // checksum
    return bArr;
}
```

---

## State Detection

### From Manufacturer Data

When the device is in sound reactive mode, the mode byte changes to 0x62:

```python
# For devices with manu_data structure like 0x56
if manu_data[15] == 0x62:
    # Device is in music/sound reactive mode
    is_sound_reactive = True
```

### From Notification Responses

Mode byte 0x62 in notification responses indicates sound reactive mode is active:

```python
if mode_type == 0x62:
    # Sound reactive mode active
    pass
```

---

## Implementation Notes for lednetwf_ble_2

### 1. Add Capability Flag to DEVICE_CAPABILITIES

In [const.py](../custom_components/lednetwf_ble_2/const.py), add `has_builtin_mic` flag:

```python
# Current entries (around line 387-390):
72:  {"name": "Ctrl_Mini_RGBW_Mic", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
8:   {"name": "Ctrl_Mini_RGB_Mic", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True},

# Add has_builtin_mic flag:
72:  {"name": "Ctrl_Mini_RGBW_Mic", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE, "has_builtin_mic": True},
8:   {"name": "Ctrl_Mini_RGB_Mic", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_builtin_mic": True},
```

### 2. Add Property to LEDNetWFDevice

In [device.py](../custom_components/lednetwf_ble_2/device.py), add property:

```python
@property
def has_builtin_mic(self) -> bool:
    """Return True if device has built-in microphone for sound reactive mode."""
    return self._capabilities.get("has_builtin_mic", False)
```

### 3. Add Sound Reactive Effect to Effect List

In [const.py](../custom_components/lednetwf_ble_2/const.py), modify `get_effect_list()` to include sound reactive option for mic devices:

```python
def get_effect_list(effect_type: EffectType, has_ic_config: bool = False,
                    has_bg_color: bool = False, has_builtin_mic: bool = False) -> list[str]:
    # ... existing logic ...

    # Add sound reactive option for devices with built-in mic
    if has_builtin_mic:
        effects.append("Sound Reactive")

    return effects
```

### 4. Add Protocol Command Builder

In [protocol.py](../custom_components/lednetwf_ble_2/protocol.py), add:

```python
def build_sound_reactive_command(enable: bool) -> bytearray:
    """
    Build command to enable/disable built-in microphone sound reactive mode.

    Only for devices with built-in microphones (product IDs 0x08, 0x48).

    Args:
        enable: True to enable, False to disable

    Returns:
        Wrapped command packet
    """
    raw_cmd = bytearray([0x73, 0x7A, 0x7B])
    raw_cmd.append(0xF0 if enable else 0x0F)
    raw_cmd.append(calculate_checksum(raw_cmd))
    return wrap_command(raw_cmd, cmd_family=0x0a)
```

### 5. Handle Effect Selection in Light Entity

In [light.py](../custom_components/lednetwf_ble_2/light.py), modify `async_set_effect()` to handle sound reactive:

```python
async def async_set_effect(self, effect: str) -> None:
    """Set the effect."""
    if effect == "Sound Reactive":
        if self._device.has_builtin_mic:
            cmd = build_sound_reactive_command(enable=True)
            await self._device.send_command(cmd)
            self._device._effect = effect
            return
    # ... existing effect handling ...
```

### 6. Handle Exiting Sound Reactive Mode

When user selects a different effect or sets a color, disable sound reactive first:

```python
# In color/effect setting methods:
if self._device._effect == "Sound Reactive" and self._device.has_builtin_mic:
    # Disable sound reactive before changing mode
    cmd = build_sound_reactive_command(enable=False)
    await self._device.send_command(cmd)
```

### 7. Parse State Response for Sound Reactive

In device state parsing, detect mode 0x62:

```python
# In notification/state parsing:
if mode_byte == 0x62:
    self._effect = "Sound Reactive"
    self._is_sound_reactive = True
```

---

## Testing Checklist

- [ ] Device with product ID 0x08 shows "Sound Reactive" in effect list
- [ ] Device with product ID 0x48 shows "Sound Reactive" in effect list
- [ ] Selecting "Sound Reactive" enables microphone mode on device
- [ ] LED responds to ambient sound when enabled
- [ ] Selecting another effect disables sound reactive mode
- [ ] Setting a color disables sound reactive mode
- [ ] State correctly shows "Sound Reactive" when mode is active

---

## Java Source References

| File | Method | Purpose |
|------|--------|---------|
| `tc/b.java` | `o(boolean)` | Command 0x73 - sound reactive enable/disable |
| `BaseDeviceInfo.java` | `M0()` | Returns true if device supports music/mic |
| `Ctrl_Mini_RGB_Mic_0x08.java` | `M0()` | Overrides to return true |
| `Ctrl_Mini_RGBW_Mic_0x48.java` | `M0()` | Overrides to return true |
