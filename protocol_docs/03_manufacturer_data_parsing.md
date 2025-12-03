# MANUFACTURER DATA PARSING

**CRITICAL: TWO DIFFERENT FORMATS DEPENDING ON DATA SOURCE**

## FORMAT A: Raw AD Type 255 Payload (29 bytes)

**Source**: Android scanRecord.getBytes() → parse TLV → Type 255 value

This includes the 2-byte company ID at the start of the payload.

| Byte | Field           | Size | Description                              |
|------|-----------------|------|------------------------------------------|
| 0    | sta             | 1    | Status/State byte                        |
| 1-2  | company_id      | 2    | Company ID (big-endian)                  |
| 3    | ble_version     | 1    | BLE protocol version                     |
| 4-9  | mac_address     | 6    | Device MAC address                       |
| 10-11| product_id      | 2    | Product identifier (big-endian)          |
| 12   | firmware_ver    | 1    | Firmware version                         |
| 13   | led_version     | 1    | LED controller version                   |
| 14   | check_key_flag  | 1    | Bits 0-1 only (if bleVersion >= 5)       |
| 15   | firmware_flag   | 1    | Bits 0-4 only (if bleVersion >= 5)       |
| 16-26| state_data      | 11   | Device state (if bleVersion >= 5)        |
| 27-28| rfu             | 2    | Reserved for future use                  |

## FORMAT B: bleak Manufacturer Data (27 bytes) - RECOMMENDED

**Source**: Python bleak: `advertisement_data.manufacturer_data[company_id]`

The company ID is returned as the DICTIONARY KEY, not in the payload!

| Byte | Field           | Size | Description                              |
|------|-----------------|------|------------------------------------------|
| 0    | sta             | 1    | Status/State byte                        |
| 1    | ble_version     | 1    | BLE protocol version                     |
| 2-7  | mac_address     | 6    | Device MAC address                       |
| 8-9  | product_id      | 2    | Product identifier (big-endian)          |
| 10   | firmware_ver    | 1    | Firmware version                         |
| 11   | led_version     | 1    | LED controller version                   |
| 12   | check_key_flag  | 1    | Bits 0-1 only (if bleVersion >= 5)       |
| 13   | firmware_flag   | 1    | Bits 0-4 only (if bleVersion >= 5)       |
| 14-24| state_data      | 11   | Device state (if bleVersion >= 5)        |
| 25-26| rfu             | 2    | Reserved for future use                  |

## Parsing Example (Format B - bleak)

Raw hex (27 bytes): `5B 05 E4 98 BB 95 EE 8E 00 33 29 0A 01 02 24 2F...`
Company ID (dict key): 23040 (0x5A00)

- Byte 0: 0x5B = sta
- Byte 1: 0x05 = ble_version (5)
- Bytes 2-7: E4:98:BB:95:EE:8E = mac_address
- Bytes 8-9: 0x0033 = product_id (51 = Ctrl_Mini_RGB_0x33)
- Byte 10: 0x29 = firmware_ver (41)
- Byte 11: 0x0A = led_version (10)

### Python Parsing Example

```python
def parse_lednetwf_device_bleak(device, advertisement_data):
    if device.name is None:
        return None
    if "LEDnetWF" not in device.name and "IOTWF" not in device.name:
        return None

    mfr_data = advertisement_data.manufacturer_data
    if not mfr_data:
        return None

    # Find valid company ID in 0x5A** range
    for cid, payload in mfr_data.items():
        if 23040 <= cid <= 23295 and len(payload) == 27:
            return {
                'sta': payload[0],
                'ble_version': payload[1],
                'mac_address': ':'.join(f'{b:02X}' for b in payload[2:8]),
                'product_id': (payload[8] << 8) | payload[9],
                'firmware_ver': payload[10],
                'led_version': payload[11],
            }
    return None
```
