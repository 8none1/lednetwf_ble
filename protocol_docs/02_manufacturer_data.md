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

## State Data Parsing (Bytes 14-24, BLE v5+ only)

Devices with BLE protocol version 5 or higher include 11 bytes of current device state in manufacturer data.

**Format B offsets**: bytes 14-24 (11 bytes)
**Format A offsets**: bytes 16-26 (11 bytes)

| Offset in state_data | Format B byte | Field | Description |
|---------------------|---------------|-------|-------------|
| 0 | 14 | Power | 0x23=ON, 0x24=OFF |
| 1 | 15 | Mode | 0x61=static, 0x25=effect |
| 2 | 16 | Sub-mode | 0xF0=RGB, 0x0F=white, or effect# |
| 3 | 17 | Value1 | White brightness (0-100) or effect param |
| 4-6 | 18-20 | R, G, B | RGB values (0-255) |
| 7 | 21 | Warm White | WW value (0-255) or color temp |
| 8 | 22 | LED Version | Firmware/LED version (NOT brightness!) |
| 9 | 23 | Cool White | CW value (0-255) |
| 10 | 24 | Reserved | Device-specific |

**IMPORTANT**: The state_data format matches the 0x81 state query response format (see file 08). Byte 8 (offset 22 in Format B) is LED version, NOT brightness. Brightness must be derived based on mode - see file 08 for brightness derivation formulas.

### Python State Parsing Example

```python
def parse_state_from_mfr_data(payload):
    """Parse state data from Format B manufacturer data (bleak)"""
    if len(payload) < 25:
        return None
    if payload[1] < 5:  # BLE version check
        return None  # No state data in older versions
    
    state = {
        'power': payload[14],  # 0x23=ON, 0x24=OFF
        'mode': payload[15],   # 0x61=static, 0x25=effect
        'sub_mode': payload[16],  # 0xF0=RGB, 0x0F=white
        'value1': payload[17],    # White brightness or param
        'r': payload[18],
        'g': payload[19],
        'b': payload[20],
        'ww': payload[21],
        'led_version': payload[22],  # NOT brightness!
        'cw': payload[23],
    }
    return state
```
