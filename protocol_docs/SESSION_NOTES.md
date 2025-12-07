# Session Notes - AI Assistant Role & Mission

## Project Context

This project is developing a Home Assistant custom integration for LEDnetWF/Zengge BLE LED lights. The integration is being reverse-engineered from the official Android application.

## My Role

### Primary Mission
Help develop the integration by analyzing and documenting the Android app's BLE protocol implementation.

### Source Code Locations

| Location | Purpose | Action |
|----------|---------|--------|
| `/home/will/source/jadx/projects/surplife/` | Android app (decompiled) | Analyze - **SOURCE OF TRUTH** |
| `surplife/.../ble_devices.json` | Device capabilities JSON | **PRIMARY REFERENCE** |
| `surplife/.../ble_dp_cmd.json` | Command definitions JSON | **PRIMARY REFERENCE** |
| `/home/will/source/jadx/projects/zengee/` | Older Android app | Analyze (alternative) |
| `custom_components/lednetwf_ble/` | Old Python integration | **READ ONLY** - reference |
| `custom_components/lednetwf_ble/` | New Python integration | Analyze and report bugs only |
| `protocol_docs/` | Protocol documentation | Check first, update with findings |

### Workflow

1. **Questions** → Check `protocol_docs/` first
2. **Exploring** → Analyze Android app code
3. **Documenting** → Write findings to `protocol_docs/`
4. **Verifying** → Cross-reference with old Python code
5. **Reviewing new code** → Analyze and report, don't fix

---

## Current Investigation Status

**Date**: 7 December 2025
**Branch**: 8none1/version_2

### Device Under Test

- **Name**: LEDnetWF02001D0CDA81
- **sta byte**: 0x53 (FillLight0x1D)
- **Product ID**: 0x001D (29)
- **BLE Version**: 5

### Key Findings This Session

1. **Effect command formats vary by device** - Five different formats discovered
   - See [06_effect_commands.md](06_effect_commands.md) for complete reference

2. **0x53 devices use 4-byte effect command with NO checksum**
   - Format: `[0x38, effect_id, speed, brightness]`
   - Other devices use 5-byte with checksum

3. **Symphony devices use inverted speed (1-31)**
   - UI 100% → protocol 1 (fastest)
   - UI 0% → protocol 31 (slowest)

4. **JSON-wrapped notifications**
   - Some devices wrap responses in JSON
   - Detection must be payload-based, not type-bit-based
   - See [04_connection_transport.md](04_connection_transport.md)

5. **IOTBT (0x80) protocol fully researched**
   - Uses Telink BLE Mesh opcodes (0xE0-0xEA range)
   - Different transport layer with `{0xB0, 0xB1, 0xB2, 0xB3}` header
   - Firmware < 11: Uses legacy 0x81 query
   - Firmware >= 11: Uses 0xEA 0x81 query with special transport
   - Response magic header: `{0xEA, 0x81}`
   - See [17_device_configuration.md](17_device_configuration.md)

### Known Issues

- **Linux BLE notifications**: Some devices don't trigger notification callbacks on Linux
  - Device DOES send notifications (confirmed via LightBlue on phone)
  - Appears to be Linux BLE stack issue

---

## Key Java Files

**Zengee sources** (`/home/will/source/jadx/projects/zengee/`):

| File | Purpose |
|------|---------|
| `tc/b.java` | Main protocol - state query, power, color commands |
| `tc/d.java` | Symphony commands (0x3B, 0x38) |
| `tc/a.java` | Custom color arrays (0xA3, 0xA0) |
| `com/zengge/wifi/Device/a.java` | Product ID → device class mapping |
| `dd/i.java` | IC chip types, effect definitions |

**Surplife sources** (`/home/will/source/jadx/projects/surplife/`) - IOTBT protocol:

| File | Purpose |
|------|---------|
| `ok/a.java` | IOTBT state query commands (0x81, 0xEA) |
| `ok/b.java` | IOTBT connection and query handling |
| `zk/f.java` | IOTBT transport layer (0xB0 header) |
| `DeviceState2.java` | IOTBT response parsing |
| `Opcode.java` | Telink BLE Mesh opcodes (0xE0-0xEA) |

---

## Next Steps

1. Debug Linux BLE notification issue
2. Test effect commands across device types
3. Document remaining timer/schedule commands (tc/e.java)

---

**For protocol details, see the numbered documentation files.**
