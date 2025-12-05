# Symphony Device Background Color Support

This document covers how Symphony devices (product IDs 0xA1-0xA9) handle foreground and background
colors for effects.

**Source**: Zengee Android app Java source code analysis.

---

## Overview

Symphony devices support TWO different command formats for effects with colors:

1. **0x41 Command** - "Settled Mode" scene effects (1-10 UI modes, maps to effect IDs 1-10)
2. **0xA3 Command** - "Custom Mode" effects with multiple color arrays

Both commands support foreground AND background colors for compatible effects.

---

## Command Format 1: 0x41 (Settled Mode Effects)

**Source**: `com/zengge/wifi/COMM/Protocol/l.java`

This is the simpler format used for scene effects in the "Settled Mode" UI tab.

### Format (13 bytes)

| Byte | Field | Value | Notes |
|------|-------|-------|-------|
| 0 | Command | 0x41 (65) | Fixed |
| 1 | Effect Mode | 1-10 | Scene effect index |
| 2 | FG Red | 0-255 | Foreground red |
| 3 | FG Green | 0-255 | Foreground green |
| 4 | FG Blue | 0-255 | Foreground blue |
| 5 | BG Red | 0-255 | Background red (0 if disabled) |
| 6 | BG Green | 0-255 | Background green |
| 7 | BG Blue | 0-255 | Background blue |
| 8 | Speed | 0-100 | Direct from UI seekbar |
| 9 | Direction | 0/1 | 0=forward, 1=reverse |
| 10 | Reserved | 0x00 | Always zero |
| 11 | Persist | 0xF0 | Always 0xF0 (240) |
| 12 | Checksum | calculated | Sum of bytes 0-11 |

### Java Source

```java
// com/zengge/wifi/COMM/Protocol/l.java
private byte[] a(int i10, int i11, int i12, int i13, boolean z10, BaseDeviceInfo baseDeviceInfo) {
    byte[] bArr = new byte[13];
    bArr[0] = 65;                        // 0x41
    bArr[1] = (byte) i10;                // effect mode
    bArr[2] = (byte) Color.red(i11);     // FG red
    bArr[3] = (byte) Color.green(i11);   // FG green
    bArr[4] = (byte) Color.blue(i11);    // FG blue
    bArr[5] = (byte) Color.red(i12);     // BG red
    bArr[6] = (byte) Color.green(i12);   // BG green
    bArr[7] = (byte) Color.blue(i12);    // BG blue
    bArr[8] = (byte) i13;                // speed
    bArr[9] = (byte) (!z10 ? 1 : 0);     // direction (inverted boolean)
    bArr[10] = 0;
    bArr[11] = -16;                      // 0xF0
    bArr[12] = tc.b.b(bArr, 12);         // checksum
    return bArr;
}
```

### Python Implementation

```python
def build_effect_with_colors_0x41(
    effect_mode: int,
    fg_color: tuple[int, int, int],
    bg_color: tuple[int, int, int] | None = None,
    speed: int = 50,
    forward: bool = True
) -> bytes:
    """
    Build 0x41 command for Symphony settled mode effects with FG/BG colors.

    Args:
        effect_mode: 1-10 (scene effect index)
        fg_color: (R, G, B) tuple 0-255
        bg_color: (R, G, B) tuple 0-255, or None for (0, 0, 0)
        speed: 0-100 (direct, NOT inverted)
        forward: True for forward direction, False for reverse

    Returns:
        13-byte command with checksum
    """
    if bg_color is None:
        bg_color = (0, 0, 0)

    cmd = bytearray([
        0x41,
        effect_mode & 0xFF,
        fg_color[0] & 0xFF,  # FG R
        fg_color[1] & 0xFF,  # FG G
        fg_color[2] & 0xFF,  # FG B
        bg_color[0] & 0xFF,  # BG R
        bg_color[1] & 0xFF,  # BG G
        bg_color[2] & 0xFF,  # BG B
        speed & 0xFF,
        0 if forward else 1,  # direction
        0x00,
        0xF0,
    ])
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)

# Example: Effect 2 with red foreground, blue background, 50% speed
cmd = build_effect_with_colors_0x41(
    effect_mode=2,
    fg_color=(255, 0, 0),
    bg_color=(0, 0, 255),
    speed=50,
    forward=True
)
```

---

## Command Format 2: 0xA3 (Custom Mode with Color Arrays)

**Source**: `tc/a.java` method `a()`

This is the more advanced format used for custom effects with multiple colors. Supports
up to 7 foreground colors and 7 background colors.

### Format (variable length)

| Byte | Field | Value | Notes |
|------|-------|-------|-------|
| 0 | Command | 0xA3 (-93/163) | Fixed |
| 1 | Effect ID | varies | From builtinFuncUniID |
| 2 | Speed | 1-31 | **INVERTED** from 0-100 |
| 3 | Brightness | 100 | Fixed at 100 |
| 4 | Color1 count | N | Number of foreground colors |
| 5+ | Color1 RGB | N×3 bytes | R,G,B for each FG color |
| - | Color2 count | M | Number of background colors |
| - | Color2 RGB | M×3 bytes | R,G,B for each BG color |
| last | Checksum | calculated | Sum of all previous bytes |

### Speed Conversion

The 0xA3 command uses **inverted 1-31 speed** (same as other Symphony commands):

```python
def ui_speed_to_protocol_0xa3(ui_speed: int) -> int:
    """Convert UI speed (0-100) to protocol (1-31 inverted)."""
    # From g2.d.f(100.0f, 0.0f, 1.0f, 31.0f, speed)
    ui_speed = max(0, min(100, ui_speed))
    return max(1, min(31, round(31 - (ui_speed / 100.0) * 30)))
```

### Java Source

```java
// tc/a.java method a()
public static byte[] a(CustomPickerParams customPickerParams) {
    int length = function.color1SelectedColors.length;
    int length2 = function.color2SelectedColors.length;
    int i11 = (length * 3) + 5 + 1 + (length2 * 3) + 1;  // total length
    int iRound = Math.round(g2.d.f(100.0f, 0.0f, 1.0f, 31.0f, customPickerParams.speed));

    byte[] bArr = new byte[i11];
    bArr[0] = -93;                    // 0xA3
    bArr[1] = (byte) effectId;        // effect ID
    bArr[2] = (byte) iRound;          // speed (1-31)
    bArr[3] = 100;                    // brightness
    bArr[4] = (byte) length;          // color1 count

    // ... color1 RGB values follow ...
    // ... color2 count and RGB values follow ...

    bArr[lastIndex] = checksum;
    return bArr;
}
```

### Python Implementation

```python
def build_effect_with_colors_0xa3(
    effect_id: int,
    fg_colors: list[tuple[int, int, int]],
    bg_colors: list[tuple[int, int, int]] | None = None,
    speed: int = 50
) -> bytes:
    """
    Build 0xA3 command for Symphony custom effects with multiple FG/BG colors.

    Args:
        effect_id: Effect number
        fg_colors: List of (R, G, B) tuples for foreground (max 7)
        bg_colors: List of (R, G, B) tuples for background (max 7)
        speed: 0-100 UI speed (converted to 1-31 inverted internally)

    Returns:
        Variable-length command with checksum
    """
    if bg_colors is None:
        bg_colors = []

    # Limit to 7 colors each
    fg_colors = fg_colors[:7]
    bg_colors = bg_colors[:7]

    # Convert speed to protocol format (1-31 inverted)
    protocol_speed = max(1, min(31, round(31 - (speed / 100.0) * 30)))

    cmd = bytearray([
        0xA3,
        effect_id & 0xFF,
        protocol_speed & 0xFF,
        100,  # brightness fixed at 100
        len(fg_colors) & 0xFF,
    ])

    # Add foreground colors
    for r, g, b in fg_colors:
        cmd.extend([r & 0xFF, g & 0xFF, b & 0xFF])

    # Add background color count and colors
    cmd.append(len(bg_colors) & 0xFF)
    for r, g, b in bg_colors:
        cmd.extend([r & 0xFF, g & 0xFF, b & 0xFF])

    # Add checksum
    cmd.append(sum(cmd) & 0xFF)
    return bytes(cmd)

# Example: Effect with 2 FG colors and 1 BG color
cmd = build_effect_with_colors_0xa3(
    effect_id=5,
    fg_colors=[(255, 0, 0), (0, 255, 0)],  # Red, Green foreground
    bg_colors=[(0, 0, 255)],                # Blue background
    speed=75
)
```

---

## Effect Color Support by Effect ID

**Source**: `dd/i.java` method `f()` - SymphonyEffectUIType enum

### Symphony Effect UI Types

| UI Type | Meaning | Effects |
|---------|---------|---------|
| `UIType_ForegroundColor_BackgroundColor` | Both FG and BG | **5-18** |
| `UIType_StartColor_EndColor` | Start/end gradient colors | 1, 3, 4 |
| `UIType_FirstColor_SecondColor` | Alternating two colors | 19-26 |
| `UIType_Only_ForegroundColor` | FG only, no BG | 2 |
| `UIType_Only_BackgroundColor` | BG only, no FG | 27-28 |
| `IType_NoColor` | No color customization | 29-44 |

### Detailed Effect List

| Effect ID | Name (from string resources) | FG Support | BG Support |
|-----------|------------------------------|------------|------------|
| 1 | Solid color | Yes | No* |
| 2 | Meteor | Yes | No |
| 3 | Breath | Yes | No* |
| 4 | Stack | Yes | No* |
| **5** | **Running water** | **Yes** | **Yes** |
| **6** | **Wave** | **Yes** | **Yes** |
| **7** | **Rainbow** | **Yes** | **Yes** |
| **8** | **Flash** | **Yes** | **Yes** |
| **9** | **Theater** | **Yes** | **Yes** |
| **10** | **Twinkle** | **Yes** | **Yes** |
| **11** | **Fire** | **Yes** | **Yes** |
| **12** | **Comet** | **Yes** | **Yes** |
| **13** | **Scanner** | **Yes** | **Yes** |
| **14** | **Color wipe** | **Yes** | **Yes** |
| **15** | **Larson scanner** | **Yes** | **Yes** |
| **16** | **Color chase** | **Yes** | **Yes** |
| **17** | **Fireworks** | **Yes** | **Yes** |
| **18** | **Rainbow chase** | **Yes** | **Yes** |
| 19-26 | Two-color alternating | Yes | Yes (as 2nd) |
| 27-28 | Background only | No | Yes |
| 29-44 | Preset patterns | No | No |

*Note: Effects 1, 3, 4 use "start/end color" which is similar to FG/BG but treated differently in the UI.

---

## UI Implementation Details

**Source**: `SettledModeFragment.java`

The Settled Mode UI provides:

- **Foreground color picker**: Hue (0-359) + brightness (0-100)
- **Background color picker**: Hue (0-359) + brightness (0-100)
- **Speed slider**: 0-100 (passed directly to 0x41 command)
- **Direction toggle**: Forward/reverse via button

### Effect Background Support Check

Each effect class extends `ge.a` and can override `c()` to indicate BG support:

```java
// ge/a.java - base class
public boolean c() {
    return true;  // Default: supports background
}

// ge/s1.java - Effect 1 (solid color)
@Override
public boolean c() {
    return false;  // Override: NO background support
}
```

When `c()` returns false, the BG color picker is disabled and BG is sent as (0, 0, 0).

---

## State Response Parsing

When querying device state for effects with FG/BG colors:

**Response format** (from `SettledModeFragment.o2()`):

| Byte | Field | Notes |
|------|-------|-------|
| 2 | Effect mode | 1-indexed (subtract 1 for 0-indexed) |
| 3 | FG Red | 0-255 |
| 4 | FG Green | 0-255 |
| 5 | FG Blue | 0-255 |
| 6 | BG Red | 0-255 |
| 7 | BG Green | 0-255 |
| 8 | BG Blue | 0-255 |
| 9 | Speed | 0-100 |
| 10 | Direction | 0=forward, 1=reverse |
| 11 | Brightness | 0-100 |

```python
def parse_settled_mode_state(data: bytes) -> dict:
    """Parse state response for settled mode effects."""
    return {
        'effect_mode': (data[2] & 0xFF),  # 1-indexed
        'fg_color': (data[3] & 0xFF, data[4] & 0xFF, data[5] & 0xFF),
        'bg_color': (data[6] & 0xFF, data[7] & 0xFF, data[8] & 0xFF),
        'speed': data[9] & 0xFF,
        'direction': 'forward' if data[10] == 0 else 'reverse',
        'brightness': data[11] & 0xFF,
    }
```

---

## Product IDs that Support Background Colors

The 0x41 settled mode command is used by devices inheriting from `Ctrl_Mini_RGB_Symphony_new_0xa2`:

| Product ID | Device Class | BG Support |
|------------|--------------|------------|
| 0xA2 (162) | Ctrl_Mini_RGB_Symphony_new_0xa2 | Yes |
| 0xA3 (163) | Ctrl_Mini_RGB_Symphony_new_0xA3 | Yes |
| 0xA4 (164) | Ctrl_Mini_RGB_Symphony_new_0xA4 | Yes |
| 0xA6 (166) | Ctrl_Mini_RGB_Symphony_new_0xA6 | Yes |
| 0xA7 (167) | Ctrl_Mini_RGB_Symphony_new_0xA7 | Yes |
| 0xA9 (169) | Ctrl_Mini_RGB_Symphony_new_0xA9 | Yes |

**Note**: Product ID 0xA1 (161) uses the older `Ctrl_Mini_RGB_Symphony_0xa1` class which may have
different capabilities.

---

## Implementation Recommendations

### For Home Assistant Integration

1. **Check product ID** - Only offer BG color for 0xA2-0xA9 devices
2. **Check effect ID** - Only show BG picker for effects 5-18 (or check UIType)
3. **Use 0x41 command** - Simpler and more reliable for single FG/BG pairs
4. **Speed is direct** - For 0x41, send speed 0-100 directly (NOT inverted)
5. **Speed is inverted** - For 0xA3, convert to 1-31 inverted

### Example Implementation

```python
class SymphonyEffectController:
    def supports_background_color(self, effect_id: int) -> bool:
        """Check if effect supports background color."""
        # Effects 5-18 support FG+BG
        return 5 <= effect_id <= 18

    def set_effect_with_colors(
        self,
        effect_id: int,
        fg_color: tuple[int, int, int],
        bg_color: tuple[int, int, int] | None,
        speed: int
    ) -> bytes:
        """Build effect command with FG/BG colors."""
        if not self.supports_background_color(effect_id):
            bg_color = None  # Force to (0,0,0)

        return build_effect_with_colors_0x41(
            effect_mode=effect_id,
            fg_color=fg_color,
            bg_color=bg_color,
            speed=speed
        )
```

---

## Summary

| Feature | 0x41 Command | 0xA3 Command |
|---------|--------------|--------------|
| Use case | Settled mode (simple effects) | Custom mode (multi-color) |
| FG colors | 1 | Up to 7 |
| BG colors | 1 | Up to 7 |
| Speed format | 0-100 direct | 1-31 inverted |
| Brightness | N/A (via mode) | Fixed at 100 |
| Direction | Yes (byte 9) | No |
| Length | 13 bytes fixed | Variable |

**For basic FG/BG support, use the 0x41 command** - it's simpler, well-tested, and provides
all the functionality needed for Home Assistant integration.

---

**End of Symphony Background Color Guide**
