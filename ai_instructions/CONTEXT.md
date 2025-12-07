# AI Context: LEDnetWF BLE Protocol Reverse Engineering

**Last Updated**: 7 December 2025

This document provides context for AI assistants working on this project.

## Project Overview

This project involves:

1. **Reverse engineering** the Surplife/MagicHome Android app to understand BLE LED controller protocols
2. **Documenting** the discovered protocols in `protocol_docs/`
3. **Implementing** a Home Assistant custom integration in `custom_components/lednetwf_ble_2/`

The goal is to control various BLE LED lights (strips, bulbs, controllers) from Home Assistant without relying on cloud services.

## Directory Structure

```
/home/will/source/lednetwf_ble/
├── protocol_docs/           # Protocol documentation (the "source of truth")
│   ├── INDEX.md            # Start here - lists all docs
│   ├── 03_device_identification.md  # Product IDs and capabilities
│   ├── 05_basic_commands.md         # RGB/CCT/power commands
│   ├── 12_iotbt_protocol.md         # Telink BLE mesh devices
│   ├── 17_device_configuration.md   # Service data, mic detection
│   └── ...
├── custom_components/
│   └── lednetwf_ble_2/     # Home Assistant integration
│       ├── const.py        # Device definitions (DEVICES dict)
│       ├── protocol.py     # Command building/parsing
│       ├── device.py       # Device class
│       └── light.py        # HA light entity
├── ai_instructions/        # This directory - AI context docs
└── ...
```

## Decompiled Android App Location

The Surplife app has been decompiled using JADX:

```
/home/will/source/jadx/projects/surplife/
├── sources/sources/com/zengge/   # Java source code
│   ├── wifi/Device/              # Device classes
│   ├── hagallbjarkan/            # BLE handling
│   └── ...
└── assets/flutter_assets/packages/
    └── magichome2_home_data_provide/assets/
        ├── ble_devices.json      # BLE device configurations
        ├── wifi_device_panel.json # UI tab configurations
        └── wifi_devices.json     # WiFi device configurations
```

### Key App Files

| File | Purpose |
|------|---------|
| `ble_devices.json` | Device capabilities, command formats, protocols |
| `wifi_device_panel.json` | UI tabs per product (music vs musicMic) |
| `ZGHBDevice.java` | BLE advertisement parsing |
| `DeviceState.java` | State response parsing |

## Common Tasks

### 1. Researching a Product ID

When asked about a specific product ID:

```python
# Extract from ble_devices.json
python3 << 'EOF'
import json
with open('/home/will/source/jadx/projects/surplife/assets/flutter_assets/packages/magichome2_home_data_provide/assets/ble_devices.json', 'r') as f:
    data = json.load(f)
for item in data:
    if item.get('productId') == 8:  # Change this
        print(json.dumps(item, indent=2))
        break
EOF
```

Key things to check:
- `protocols` - which command protocols it supports
- `hexCmdForms` - actual command byte formats
- `functions` - available device functions
- `stateProtocol` - how to parse state responses

### 2. Verifying Documentation

**ALWAYS verify docs against the app database.** We've found multiple errors where docs were wrong:

- Product 0x08 was incorrectly listed as "Symphony" type
- Product 0xA4 was incorrectly listed as having no mic
- Product 0xA1 is the ONLY Symphony without mic

### 3. Finding Command Formats

Search the decompiled Java code:

```bash
# Find where a command byte is used
grep -r "0x31\|0x46\|0x38" /home/will/source/jadx/projects/surplife/sources/sources/com/zengge/

# Find a specific class
find /home/will/source/jadx/projects/surplife -name "*.java" | xargs grep -l "DeviceState"
```

### 4. Understanding Device Types

| Type | Colour Cmd | Protocol | Examples |
|------|------------|----------|----------|
| Simple RGB | 0x31 | rgb_mini | 0x08, 0x33, 0x51 |
| Simple RGBW | 0x31 | rgbw_mini | 0x06, 0x48, 0x68 |
| RGBCW | 0x31 | common | 0x07, 0x35, 0x53 |
| Symphony (old) | 0x31 | symphony_wifi | 0xA1 |
| Symphony (new) | 0x46 | symphony_wifi_new | 0xA2-0xAD |
| IOTBT/Telink | 0xE1 | telink_mesh | 0x00 (product_id) |

## Protocol Patterns

### BLE Advertisement Parsing

Two main formats:
1. **ZengGe format**: Company ID 0x5A** (23040-23295)
2. **Telink format**: Company ID 0x1102 (4354)

State data location varies by BLE version:
- v5-v6: Manufacturer data offset 14
- v7+: Manufacturer data offset 3 (when service data present)

### Command Formats

Most commands follow: `[cmd_byte] [params...] [checksum]`

Checksum = sum of all preceding bytes & 0xFF

Example RGB command for 0x08:
```
31 {R} {G} {B} 00 00 0F [checksum]
```

### State Response Format

```
81 [product_id] [power] [mode] [sub_mode] ... [checksum]
```

- Power: 0x23 = ON, 0x24 = OFF
- Mode: 0x61 = color/white, 0x25 = effect

## Known Pitfalls

### 1. Product ID Misidentification

Some devices report product_id=0x00 in advertisements but are actually specific types. Check:
- Company ID (ZengGe vs Telink)
- BLE version byte
- Protocol behavior

### 2. Symphony vs Simple

Don't assume all Symphony devices are the same:
- 0xA1: Old protocol, 0x31 command, NO mic
- 0xA2+: New protocol, 0x46 command, HAS mic

### 3. Mic Detection

The app uses database lookups, not dynamic detection:
- `musicMic` UI tab = device has built-in mic
- `music` UI tab = phone mic only
- Check `wifi_device_panel.json` or `ble_devices.json` for `symp_mic_info` functions

### 4. Legacy Products

Some product IDs in documentation aren't in the current app database:
- 0x04 (4), 0x1D (29), 0x25 (37), 0x3B (59), 0xA7 (167), 0xA9 (169)

These may be deprecated or handled dynamically.

## Integration Development

The Home Assistant integration is in `custom_components/lednetwf_ble_2/`.

### Key Files

| File | Purpose |
|------|---------|
| `const.py` | `DEVICES` dict maps product_id to capabilities |
| `protocol.py` | Builds commands, parses responses |
| `device.py` | `LEDNetWFDevice` class - connection, state |
| `light.py` | Home Assistant `LightEntity` |

### Adding Device Support

1. Research the product ID in app database
2. Determine command format (0x31 vs 0x46 vs special)
3. Add entry to `DEVICES` dict in `const.py`
4. If new command format needed, add to `protocol.py`
5. Update documentation

### Testing

The user has physical devices:
- IOTBT (Telink mesh) device with mic
- Various other LED controllers

## Useful Commands

```bash
# Search protocol docs
grep -r "0x08\|product.*8" /home/will/source/lednetwf_ble/protocol_docs/

# Find all mic-related code in app
grep -ri "mic\|music" /home/will/source/jadx/projects/surplife/sources/sources/com/zengge/

# List products with specific feature
python3 -c "
import json
with open('/home/will/source/jadx/projects/surplife/assets/flutter_assets/packages/magichome2_home_data_provide/assets/ble_devices.json') as f:
    data = json.load(f)
for item in data:
    funcs = [f['code'] for f in item.get('functions', [])]
    if 'get_mic_info' in funcs:
        print(item['productId'])
"

# Extract strings from LMDB database
strings /home/will/source/jadx/projects/surplife/assets/flutter_assets/packages/briturn_core/assets/zg_device_db/data.mdb | head -100
```

## Communication Style

When working with the user:
- Be direct and technical
- Verify claims against app database before confirming
- Update documentation when errors are found
- Provide specific file:line references
- Show command byte formats in hex

## Related Resources

- Protocol docs: `protocol_docs/INDEX.md`
- Device capabilities table: `protocol_docs/03_device_identification.md`
- IOTBT/Telink protocol: `protocol_docs/12_iotbt_protocol.md`
- Mic detection: `protocol_docs/17_device_configuration.md` (section: Feature Detection)
