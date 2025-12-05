# Device-Specific Notes

This document covers device-specific quirks and variations not covered in the main protocol docs.

---

## LED Curtain Lights (Product IDs 172, 173)

**Protocol**: Same as Symphony devices (hc3 category)

These are matrix/panel LED devices that display effects in a 2D grid pattern.

### Identification

| Product ID | Type | Protocol |
|------------|------|----------|
| 172 (0xAC) | symphony_curtain | curtainLightE2 |
| 173 (0xAD) | symphony_curtain | curtainLightE2 |

### Supported Matrix Sizes

| Dimensions | LEDs | Dimensions | LEDs |
|------------|------|------------|------|
| 13 × 10 | 130 | 20 × 20 | 400 |
| 15 × 17 | 255 | 20 × 28 | 560 |
| 15 × 19 | 285 | 24 × 22 | 528 |
| 15 × 24 | 360 | 30 × 15 | 450 |
| 18 × 12 | 216 | 30 × 30 | 900 |
| 20 × 13 | 260 | | |

### Commands

Use standard Symphony commands:
- **Power**: 0x3B with 0x23/0x24
- **Color**: 0x3B with mode 0xA1 (HSV)
- **Effects**: 0x38 (5-byte with checksum, 1-31 inverted speed)
- **State**: 0x81 query

### Effects

Same effects as Symphony devices (Scene 1-44, Build 1-300). Effects render on 2D matrix instead of linear strip.

### NOT Supported (in this integration)

- Text display
- Image gallery
- DIY animations
- Multi-panel splicing

---

## Ring Lights / Fill Lights (Product ID 0x1D)

See [06_effect_commands.md](06_effect_commands.md) Format A.

**Key difference**: 4-byte effect command with NO checksum.

---

## Legacy RGB Controllers (0x33, 0x06, 0x04)

See [06_effect_commands.md](06_effect_commands.md) Format E.

**Key differences**:
- Use 0x61 command for effects (not 0x38)
- Speed is 1-31 inverted (same as Symphony)
- Only 20 simple effects (IDs 37-56)

---

## Music-Reactive Strips (0x56, 0x80)

See [06_effect_commands.md](06_effect_commands.md) Format D.

**Key difference**: Use 0x42 opcode instead of 0x38 for effects.

---

## CCT-Only Devices (0x52, 0x09, 0x1C)

No effect support. Use:
- 0x35 command for CCT control
- 0x3B with mode 0xB1 for Symphony-style CCT

---

## Product ID Quick Reference

### Symphony Family (Addressable LEDs)
- 0xA1-0xA9 (161-169): Mini RGB Symphony controllers
- 0xAA-0xAB (170-171): Symphony strips
- 0xAC-0xAD (172-173): LED curtain lights
- 0x08 (8): Mini RGB with mic

### Standard RGB
- 0x33 (51): Mini RGB
- 0x06 (6): Mini RGBW
- 0x04 (4): RGBW UFO
- 0x44 (68): RGBW Bulb

### Addressable Strips
- 0x1D (29): Fill Light / Ring Light
- 0x54, 0x55: LED strips
- 0x56, 0x80: Music strips
- 0x5B: Strip controller

### CCT / Dimmer
- 0x52 (82): CCT Bulb
- 0x41 (65): Dimmer
- 0x09, 0x1C: CCT controllers

### Switches
- 0x93-0x97: Various switch devices

---

**For detailed command formats, see [06_effect_commands.md](06_effect_commands.md)**
