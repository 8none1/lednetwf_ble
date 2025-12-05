# Quick Reference

## BLE Service and Characteristic UUIDs

| UUID | Purpose |
|------|---------|
| `0000ffff-0000-1000-8000-00805f9b34fb` | Service |
| `0000ff01-0000-1000-8000-00805f9b34fb` | Write Characteristic |
| `0000ff02-0000-1000-8000-00805f9b34fb` | Notify Characteristic |

## Device Discovery

| Setting | Value |
|---------|-------|
| Device name filter | Contains "LEDnetWF" or "IOTWF" |
| Company ID range | 0x5A00-0x5AFF (23040-23295) |
| Scan mode | BLE_SCAN_MODE_LOW_LATENCY (mode=2) |
| Report delay | 0ms (immediate) |

## Essential Commands

| Purpose | Command Bytes | Notes |
|---------|---------------|-------|
| Query State | `[0x81, 0x8A, 0x8B, 0x40]` | Returns 14 bytes |
| Set RGBCW | `[0x31, R, G, B, WW, CW, 0x5A, persist, chk]` | persist: 0xF0/0x0F |
| Power ON | `[0x3B, 0x23, ...]` or `[0x71, 0x23, 0x0F, chk]` | BLE v5+ vs legacy |
| Power OFF | `[0x3B, 0x24, ...]` or `[0x71, 0x24, 0x0F, chk]` | BLE v5+ vs legacy |
| Brightness | `[0x47, brightness, chk]` | 0-100 percent |
| Effect | `[0x38, effect_id, speed, bright, ...]` | Format varies by device |

**Note**: All commands must be wrapped in transport layer. See [04_connection_transport.md](04_connection_transport.md).

## Advertisement Data (TLV Format)

| AD Type | Value | Purpose |
|---------|-------|---------|
| 0x01 | Flags | Device capabilities |
| 0x09 | Complete Local Name | Device name |
| 0x16 | Service Data (16-bit) | Service info |
| 0xFF | Manufacturer Data | **Primary data source** |

TLV structure: `[length, type, value...]` where `actual_length = length - 1`
