# OVERVIEW AND QUICK REFERENCE

## Quick Reference - Essential Commands

| Purpose          | Command Bytes                                    | Response |
|------------------|--------------------------------------------------|----------|
| Query State      | [0x81, 0x8A, 0x8B, 0x40]                         | 14 bytes |
| Set RGBCW        | [0x31, R, G, B, WW, CW, 0x5A, persist, checksum] | None     |
| Power ON         | [0x11, 0x1A, 0x1B, 0xF0, 0xE6]                   | None     |
| Power OFF        | [0x11, 0x1A, 0x1B, 0x0F, 0x55]                   | None     |
| Set Brightness   | [0x47, brightness, checksum]                     | None     |
| Set Effect       | [0x38, effect_id, speed, param, checksum]        | None     |

## BLE Service and Characteristic UUIDs

- **Service UUID**: `0000ffff-0000-1000-8000-00805f9b34fb`
- **Write Characteristic**: `0000ff01-0000-1000-8000-00805f9b34fb`
- **Notify Characteristic**: `0000ff02-0000-1000-8000-00805f9b34fb`

## Device Naming

Target device names: "LEDnetWF" or "IOTWF" (substring match)

## Company ID Ranges

Accept company IDs in range 0x5A00-0x5AFF (23040-23295) from manufacturer data.
