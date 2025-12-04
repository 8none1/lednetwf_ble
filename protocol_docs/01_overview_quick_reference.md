# OVERVIEW AND QUICK REFERENCE

## Quick Reference - Essential Commands

| Purpose          | Command Bytes                                    | Response |
|------------------|--------------------------------------------------|---------|
| Query State      | [0x81, 0x8A, 0x8B, 0x40]                         | 14 bytes |
| Set RGBCW        | [0x31, R, G, B, WW, CW, 0x5A, persist, checksum] | None     |
| Power ON (modern)| [0x3B, 0x23, ...] (BLE v5+) or [0x71, 0x23, 0x0F, 0xA3] (legacy) | None     |
| Power OFF (modern)| [0x3B, 0x24, ...] (BLE v5+) or [0x71, 0x24, 0x0F, 0xA4] (legacy) | None     |
| Set Brightness   | [0x47, brightness, checksum]                     | None     |
| Set Effect       | [0x38, effect_id, speed, param, checksum]        | None     |

**Note**: Power command format depends on BLE version. See section 07 for details.

## BLE Service and Characteristic UUIDs

- **Service UUID**: `0000ffff-0000-1000-8000-00805f9b34fb`
- **Write Characteristic**: `0000ff01-0000-1000-8000-00805f9b34fb`
- **Notify Characteristic**: `0000ff02-0000-1000-8000-00805f9b34fb`

## Device Naming

Target device names: "LEDnetWF" or "IOTWF" (substring match)

## Company ID Ranges

Accept company IDs in range 0x5A00-0x5AFF (23040-23295) from manufacturer data.
