# Session Notes - AI Assistant Role & Mission

## Project Context

This project is developing a Home Assistant custom integration for LEDnetWF/Zengge BLE LED lights. The integration is being reverse-engineered from the official Android application.

## My Role

### Primary Mission
Help develop the integration by analyzing and documenting the Android app's BLE protocol implementation.

### Source Code Locations

| Location | Purpose | Action |
|----------|---------|--------|
| `/home/will/source/reverse_engineering/zengee/` | Android app (decompiled) | Analyze - **SOURCE OF TRUTH** |
| `/home/will/source/jadx/projects/zengee/` | Android app (alternative) | Analyze |
| `custom_components/lednetwf_ble/` | Old Python integration | **READ ONLY** - reference |
| `custom_components/lednetwf_ble_2/` | New Python integration | Analyze and report bugs only |
| `protocol_docs/` | Protocol documentation | Check first, update with findings |

### Workflow

1. **Questions** → Check `protocol_docs/` first
2. **Exploring** → Analyze Android app code
3. **Documenting** → Write findings to `protocol_docs/`
4. **Verifying** → Cross-reference with old Python code
5. **Reviewing new code** → Analyze and report, don't fix

---

## Current Investigation Status

**Date**: 5 December 2025
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

### Known Issues

- **Linux BLE notifications**: Some devices don't trigger notification callbacks on Linux
  - Device DOES send notifications (confirmed via LightBlue on phone)
  - Appears to be Linux BLE stack issue

---

## Key Java Files

| File | Purpose |
|------|---------|
| `tc/b.java` | Main protocol - state query, power, color commands |
| `tc/d.java` | Symphony commands (0x3B, 0x38) |
| `tc/a.java` | Custom color arrays (0xA3, 0xA0) |
| `com/zengge/wifi/Device/a.java` | Product ID → device class mapping |
| `dd/i.java` | IC chip types, effect definitions |

---

## Next Steps

1. Debug Linux BLE notification issue
2. Test effect commands across device types
3. Document remaining timer/schedule commands (tc/e.java)

---

**For protocol details, see the numbered documentation files.**
