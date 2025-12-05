# LEDnetWF BLE Protocol Documentation

**Version**: 3.0
**Updated**: 5 December 2025

---

## Document Index

| # | File | Description |
|---|------|-------------|
| - | [SESSION_NOTES.md](SESSION_NOTES.md) | AI assistant role, investigation status |
| 01 | [01_quick_reference.md](01_quick_reference.md) | UUIDs, device discovery, essential commands |
| 02 | [02_manufacturer_data.md](02_manufacturer_data.md) | Advertisement data format (27 bytes) |
| 03 | [03_device_identification.md](03_device_identification.md) | Product ID mapping, capability detection |
| 04 | [04_connection_transport.md](04_connection_transport.md) | BLE connection, transport layer, JSON handling |
| 05 | [05_basic_commands.md](05_basic_commands.md) | RGB, CCT, brightness, power commands |
| 06 | [06_effect_commands.md](06_effect_commands.md) | **Main effects reference** - formats by device |
| 07 | [07_effect_names.md](07_effect_names.md) | Effect name lists (Symphony Scene/Build) |
| 08 | [08_state_query_response_parsing.md](08_state_query_response_parsing.md) | State query format, response parsing |
| 09 | [09_python_guide.md](09_python_guide.md) | Complete Python implementation example |
| 10 | [10_device_specific.md](10_device_specific.md) | Device-specific quirks, product ID reference |

---

## Quick Start

### 1. Discover Device
Scan for BLE devices with names containing "LEDnetWF" or "IOTWF".

### 2. Extract Product ID
```python
product_id = (mfr_data[8] << 8) | mfr_data[9]  # Big-endian
```

### 3. Connect
```
Service:  0000ffff-0000-1000-8000-00805f9b34fb
Write:    0000ff01-0000-1000-8000-00805f9b34fb
Notify:   0000ff02-0000-1000-8000-00805f9b34fb
```

### 4. Wrap Commands
All commands must be wrapped in transport layer. See [04_connection_transport.md](04_connection_transport.md).

### 5. Send Commands
| Task | Command | Details |
|------|---------|---------|
| Power | 0x3B (v5+) / 0x71 (legacy) | [05_basic_commands.md](05_basic_commands.md) |
| Color | 0x3B (HSV) / 0x31 (RGB) | [05_basic_commands.md](05_basic_commands.md) |
| Effect | 0x38 / 0x61 | [06_effect_commands.md](06_effect_commands.md) |

---

## Common Tasks

| Task | Document |
|------|----------|
| Parse advertisement data | [02_manufacturer_data.md](02_manufacturer_data.md) |
| Determine capabilities | [03_device_identification.md](03_device_identification.md) |
| Set color/brightness | [05_basic_commands.md](05_basic_commands.md) |
| Set effect | [06_effect_commands.md](06_effect_commands.md) |
| Parse state response | [08_state_query_response_parsing.md](08_state_query_response_parsing.md) |

---

## Key Concepts

### Product ID vs sta_byte
- **Product ID** (bytes 8-9): Device model - use for detection
- **sta_byte** (byte 0): Status - NOT for identification

### BLE Version
- **v1-4**: Legacy (0x31, 0x71, 0x61)
- **v5+**: Symphony (0x3B, 0x38)

### Effect Formats (Critical!)

| Device | Command | Bytes | Checksum |
|--------|---------|-------|----------|
| FillLight (0x1D) | 0x38 | 4 | NO |
| Symphony (0xA1+) | 0x38 | 5 | YES |
| Legacy RGB | 0x61 | 5 | YES |

**See [06_effect_commands.md](06_effect_commands.md) for details.**

---

## Java Source References

Key files in `/home/will/source/jadx/projects/zengee/`:

| File | Purpose |
|------|---------|
| `tc/b.java` | Main protocol commands |
| `tc/d.java` | Symphony (0x3B) commands |
| `tc/a.java` | Custom color arrays |
| `com/zengge/wifi/Device/a.java` | Product ID mapping |
| `dd/i.java` | IC types, effects |

---

## Version History

| Date | Changes |
|------|---------|
| 5 Dec 2025 | v3.0 - Consolidated 18 files → 11 |
| 4 Dec 2025 | v2.1 - Effect formats by device |
| 3 Dec 2025 | v2.0 - Initial split documentation |
