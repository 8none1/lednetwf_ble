# Static Effects with Foreground/Background Colors

**Last Updated**: 5 December 2025
**Status**: Research complete, ready for implementation
**Purpose**: Document static effects that support customizable FG and BG colors

---

## Overview

Some devices support "static effects" that allow users to set both a **foreground color** and a **background color**. These are different from regular effects which use preset colors.

**Devices that support FG+BG static effects:**
- **0x56/0x80** (Strip Lights) - 10 effects via 0x41 command
- **0xA1-0xAD** (Symphony devices) - 10 "Settled Mode" effects via 0x41 command

**Devices that do NOT support FG+BG static effects:**
- **0x1D** (FillLight/Ring Light) - Uses 0x38 command with 113 effects, no BG color support
- **0x53** (Ring Light) - Same as 0x1D

---

## Command Format: 0x41 (Static Effect with Colors)

**Source**: `Protocol/l.java`, `model_0x56.py`

### Raw Command (13 bytes)

```
[0x41] [mode] [FG_R] [FG_G] [FG_B] [BG_R] [BG_G] [BG_B] [speed] [direction] [0x00] [0xF0] [checksum]
```

| Byte | Field | Range | Description |
|------|-------|-------|-------------|
| 0 | Command | 0x41 | Fixed opcode |
| 1 | Mode/Effect ID | 0-10 | Effect mode (see table below) |
| 2 | FG Red | 0-255 | Foreground color red |
| 3 | FG Green | 0-255 | Foreground color green |
| 4 | FG Blue | 0-255 | Foreground color blue |
| 5 | BG Red | 0-255 | Background color red |
| 6 | BG Green | 0-255 | Background color green |
| 7 | BG Blue | 0-255 | Background color blue |
| 8 | Speed | 0-100 | Effect speed (direct, not inverted) |
| 9 | Direction | 0 or 1 | 0 = forward, 1 = reverse |
| 10 | Reserved | 0x00 | Always 0 |
| 11 | Terminator | 0xF0 | Always 0xF0 (-16 signed) |
| 12 | Checksum | calc | Sum of bytes 0-11, masked with 0xFF |

### Special Mode Values

| Mode | Behavior |
|------|----------|
| 0 | Keep current mode, just update colors |
| 1 | Solid Color (FG only, no animation) |
| 2-10 | Static effects with FG+BG |

---

## Effect List: 0x56/0x80 Strip Lights

**Source**: `model_0x56.py:21-36`

| Effect ID | Name | Supports BG | Notes |
|-----------|------|-------------|-------|
| 1 | Solid Color | No | Just foreground color, no animation |
| 2 | Static Effect 2 | Yes | |
| 3 | Static Effect 3 | Yes | |
| 4 | Static Effect 4 | Yes | |
| 5 | Static Effect 5 | Yes | |
| 6 | Static Effect 6 | Yes | |
| 7 | Static Effect 7 | Yes | |
| 8 | Static Effect 8 | Yes | |
| 9 | Static Effect 9 | Yes | |
| 10 | Static Effect 10 | Yes | |

**Implementation Note**: In `model_0x56.py`, these are stored with shifted IDs (`effect_id << 8`) to distinguish them from regular effects (1-99). When sending the command, shift back: `actual_id = stored_id >> 8`.

---

## Effect List: Symphony Devices (0xA1-0xAD) "Settled Mode"

**Source**: `SettledModeFragment.java:377-388`, `ge/*.java`

| Effect ID | Class | Supports BG | Supports Speed | Animation |
|-----------|-------|-------------|----------------|-----------|
| 1 | `s1` | **No** | Yes | Single color fill |
| 2 | `u1` | Yes | Yes | Running point |
| 3 | `w1` | Yes | Yes | |
| 4 | `y1` | Yes | Yes | |
| 5 | `a2` | Yes | Yes | |
| 6 | `c2` | Yes | Yes | |
| 7 | `e2` | Yes | Yes | |
| 8 | `g2` | Yes | Yes | |
| 9 | `i2` | Yes | Yes | |
| 10 | `r1` | Yes | Yes | |

**Note**: Effect 1 (`s1`) explicitly returns `c() = false` meaning it does NOT support background color. All others default to supporting BG color.

---

## Python Implementation

### Building the Command

```python
def build_static_effect_command_0x41(
    effect_id: int,
    fg_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int],
    speed: int = 50,
    direction: bool = True,  # True = forward
) -> bytearray:
    """
    Build static effect command with foreground and background colors.

    Used for:
    - 0x56/0x80 devices: Static effects 1-10
    - Symphony devices (0xA1-0xAD): Settled Mode effects 1-10

    Args:
        effect_id: 0 = keep current mode, 1-10 = static effect ID
        fg_rgb: Foreground color (R, G, B) each 0-255
        bg_rgb: Background color (R, G, B) each 0-255
        speed: Effect speed 0-100 (direct, higher = faster)
        direction: True = forward, False = reverse

    Returns:
        13-byte command (needs transport wrapper)
    """
    speed = max(0, min(100, speed))

    raw_cmd = bytearray([
        0x41,                           # Command opcode
        effect_id & 0xFF,               # Mode/Effect ID
        fg_rgb[0] & 0xFF,               # FG Red
        fg_rgb[1] & 0xFF,               # FG Green
        fg_rgb[2] & 0xFF,               # FG Blue
        bg_rgb[0] & 0xFF,               # BG Red
        bg_rgb[1] & 0xFF,               # BG Green
        bg_rgb[2] & 0xFF,               # BG Blue
        speed & 0xFF,                   # Speed
        0 if direction else 1,          # Direction: 0=forward, 1=reverse
        0x00,                           # Reserved
        0xF0,                           # Terminator (0xF0 = -16 signed)
    ])

    # Add checksum
    checksum = sum(raw_cmd) & 0xFF
    raw_cmd.append(checksum)

    return raw_cmd
```

### Wrapping with Transport Layer

```python
def wrap_command(raw_cmd: bytearray, cmd_family: int = 0x0b) -> bytearray:
    """Wrap raw command in transport layer."""
    length = len(raw_cmd)
    packet = bytearray([
        0x00,                    # Byte 0: Always 0
        0x00,                    # Byte 1: Sequence (can be 0)
        0x80,                    # Byte 2: Always 0x80
        0x00,                    # Byte 3: Always 0
        0x00,                    # Byte 4: Always 0
        length & 0xFF,           # Byte 5: Payload length (low)
        (length + 1) & 0xFF,     # Byte 6: Payload length + 1
        cmd_family & 0xFF,       # Byte 7: Command family (0x0b for effects)
    ])
    packet.extend(raw_cmd)
    return packet
```

### Full Example

```python
# Set Static Effect 3 with red foreground and blue background
fg = (255, 0, 0)      # Red
bg = (0, 0, 255)      # Blue
speed = 50
direction = True

raw_cmd = build_static_effect_command_0x41(3, fg, bg, speed, direction)
packet = wrap_command(raw_cmd, cmd_family=0x0b)

# packet is ready to send via BLE write
```

---

## Updating Colors Without Changing Mode

To update FG/BG colors while keeping the current static effect mode, send with `mode=0`:

```python
# Update colors only, keep current effect
raw_cmd = build_static_effect_command_0x41(
    effect_id=0,          # 0 = keep current mode
    fg_rgb=(255, 128, 0), # New foreground (orange)
    bg_rgb=(0, 64, 128),  # New background (teal)
    speed=50,
)
```

This is useful for real-time color updates as the user drags a color picker.

---

## Exiting Static Effect Mode (Return to Solid Color)

### Option 1: Use Static Effect 1 (Solid Color)

Effect 1 is "Solid Color" which just displays the foreground color with no animation and no background:

```python
# Return to solid color mode
raw_cmd = build_static_effect_command_0x41(
    effect_id=1,          # Solid Color mode
    fg_rgb=(255, 255, 255), # Desired color
    bg_rgb=(0, 0, 0),     # Ignored for effect 1
    speed=0,              # Ignored for effect 1
)
```

### Option 2: Send RGB Color Command

For 0x56/0x80 devices, you can also send the standard RGB color command (0x31 or device-specific) to exit effect mode.

---

## State Response Parsing

When parsing state responses, static effects are indicated by:

### 0x56/0x80 Devices

**Source**: `model_0x56.py:57-71`

In manufacturer data or notification response:
- `manu_data[15] == 0x61` indicates color/static mode
- `manu_data[16]` contains the effect ID:
  - `0xF0` = pure RGB color mode (no effect)
  - `0x01-0x0A` = Static Effect 1-10

```python
if manu_data[15] == 0x61:
    if manu_data[16] == 0xF0:
        # Pure RGB mode, no effect
        effect = None
    elif 0x01 <= manu_data[16] <= 0x0A:
        # Static effect mode
        effect_id = manu_data[16]  # 1-10
        # RGB is in bytes 18-20
        fg_rgb = (manu_data[18], manu_data[19], manu_data[20])
```

### Symphony Devices

**Source**: `SettledModeFragment.java:500-530`

State query response contains:
- Byte 2: Effect ID (1-10)
- Bytes 3-5: Foreground RGB
- Bytes 6-8: Background RGB
- Byte 9: Speed
- Byte 10: Direction (0=forward, 1=reverse)
- Byte 11: Brightness/bulb setting

---

## Effect ID Encoding in const.py

For 0x56/0x80 devices, static effects use shifted IDs to avoid collision with regular effects:

```python
# In const.py
STATIC_EFFECTS_WITH_BG: Final = {
    1: "Solid Color",       # No BG support
    2: "Static Effect 2",
    3: "Static Effect 3",
    4: "Static Effect 4",
    5: "Static Effect 5",
    6: "Static Effect 6",
    7: "Static Effect 7",
    8: "Static Effect 8",
    9: "Static Effect 9",
    10: "Static Effect 10",
}

# When storing effect ID for 0x56/0x80:
# - Regular effects (1-99, 255): store directly
# - Static effects (1-10): store as (id << 8)
# Example: Static Effect 3 stored as 0x0300 (768)

# When sending command:
if effect_id >= 0x100:
    # It's a static effect
    actual_id = effect_id >> 8  # Shift back to 1-10
    use_0x41_command(actual_id, fg_rgb, bg_rgb, speed)
else:
    # Regular effect
    use_0x42_command(effect_id, speed, brightness)
```

---

## Summary

| Feature | 0x56/0x80 | Symphony (0xA1-0xAD) | 0x1D/0x53 |
|---------|-----------|----------------------|-----------|
| Static effects with BG | Yes (10) | Yes (10) | No |
| Command | 0x41 | 0x41 | N/A |
| Effect 1 BG support | No | No | N/A |
| Effects 2-10 BG support | Yes | Yes | N/A |
| Speed range | 0-100 direct | 0-100 direct | N/A |

---

## Files to Modify for Implementation

1. **const.py**: Add `STATIC_EFFECTS_WITH_BG` dictionary (already partially exists)
2. **protocol.py**: Ensure `build_static_effect_command_0x41()` handles all cases
3. **device.py**: Update `set_effect()` to detect static effects and use 0x41 command
4. **light.py**: Add background color light entity for devices that support it

---

## Source Files Reference

| File | Purpose |
|------|---------|
| `Protocol/l.java` | 0x41 command builder for Symphony |
| `model_0x56.py` | Old integration's 0x56 static effect handling |
| `SettledModeFragment.java` | Symphony Settled Mode UI and command sending |
| `ge/s1.java`, `ge/u1.java`, etc. | Individual settled mode effect implementations |
| `ge/a.java` | Base class for settled mode effects |
