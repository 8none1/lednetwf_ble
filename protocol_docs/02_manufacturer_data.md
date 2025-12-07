# BLE Advertisement Data Parsing

**Last Updated**: 6 December 2025

This document covers all BLE advertisement data formats used by LEDnetWF/Zengge devices.

---

## Device Families by Company ID

| Company ID | Range | Device Type | Format |
|------------|-------|-------------|--------|
| 0x5A00-0x5AFF | 23040-23295 | Standard LEDnetWF | ZengGe format |
| 0x1102 | 4354 | IOTBT/Telink Mesh | Telink format |

---

## ZengGe Format (Company ID 0x5A**)

### Format A: Raw AD Type 255 (29 bytes)

**Source**: Android `scanRecord.getBytes()` → parse TLV → Type 255 value

Includes 2-byte company ID at the start.

| Byte | Field | Description |
|------|-------|-------------|
| 0 | sta | Status byte |
| 1-2 | company_id | Company ID (big-endian) |
| 3 | ble_version | BLE protocol version |
| 4-9 | mac_address | Device MAC (6 bytes) |
| 10-11 | product_id | Product ID (big-endian) |
| 12 | firmware_ver | Firmware version (low byte) |
| 13 | led_version | LED version |
| 14 | check_key_flag | Bits 0-1: check_key, Bits 2-7: fw high (v6+) |
| 15 | firmware_flag | Firmware flags (bits 0-4) |
| 16-26 | state_data | Device state (BLE v5+) |
| 27-28 | rfu | Reserved |

### Format B: bleak/Python (27 bytes) - RECOMMENDED

**Source**: `advertisement_data.manufacturer_data[company_id]`

Company ID is the dictionary key, NOT in the payload.

| Byte | Field | Description |
|------|-------|-------------|
| 0 | sta | Status byte |
| 1 | ble_version | BLE protocol version |
| 2-7 | mac_address | Device MAC (6 bytes) |
| 8-9 | product_id | Product ID (big-endian) |
| 10 | firmware_ver | Firmware version (low byte) |
| 11 | led_version | LED version |
| 12 | check_key_flag | Bits 0-1: check_key, Bits 2-7: fw high (v6+) |
| 13 | firmware_flag | Firmware flags (bits 0-4) |
| **14** | **power** | **0x23=ON, 0x24=OFF** (v5+) |
| 15 | mode_type | 0x61=color/white, 0x25=effect |
| 16 | sub_mode | Effect ID or 0xF0=RGB, 0x0F=white |
| 17-24 | state_data | Color/brightness/speed |
| 25-26 | rfu | Reserved |

### State Data (Bytes 14-24, BLE v5+)

| Offset | Field | Description |
|--------|-------|-------------|
| 0 (14) | Power | 0x23=ON, 0x24=OFF |
| 1 (15) | Mode | 0x61=static, 0x25=effect |
| 2 (16) | Sub-mode | 0xF0=RGB, 0x0F=white, or effect# |
| 3 (17) | Value1 | White brightness or effect param |
| 4-6 (18-20) | R, G, B | RGB values (0-255) |
| 7 (21) | WW | Warm white or color temp |
| 8 (22) | LED Ver | LED version (NOT brightness!) |
| 9 (23) | CW | Cool white |

---

## BLE v7+ with Service Data

For BLE version >= 7, devices advertise BOTH service data AND manufacturer data.

### Service Data (16 bytes)

**UUID**: `0000FFFF-0000-1000-8000-00805f9b34fb`

| Byte | Field | Description |
|------|-------|-------------|
| 0 | sta | Status (0xFF = OTA mode) |
| 1 | mfr_hi | Manufacturer prefix (0x5A/0x5B) |
| 2 | mfr_lo | Manufacturer low byte |
| 3 | ble_version | BLE protocol version |
| 4-9 | mac_address | Device MAC (6 bytes) |
| 10-11 | product_id | Product ID (big-endian) |
| 12 | firmware_ver_lo | Firmware low byte |
| 13 | led_version | LED version |
| 14 | check_key+fw_hi | Bits 0-1: check_key, Bits 2-7: fw high |
| 15 | firmware_flag | Feature flags (bits 0-4) |

### When Both Present (v7+)

- **Device ID**: From service data
- **State data**: From manufacturer data at **offset 3** (NOT 14!)

```python
if ble_version >= 7 and has_service_data:
    state_data = mfr_data[3:28]  # 25 bytes at offset 3
    power_state = state_data[11]  # Power at offset 11 within state
```

---

## Telink Mesh Format (Company ID 0x1102)

**Used by**: IOTBT devices, Telink BLE Mesh

| Offset | Field | Description |
|--------|-------|-------------|
| 0-1 | company_id | 4354 (0x1102) |
| 2-3 | mesh_uuid | Mesh network ID (little-endian) |
| 4-7 | reserved | MAC or reserved |
| 8-9 | product_uuid | Product UUID (little-endian) |
| **10** | **status** | **Power/brightness: non-zero = ON** |
| 11-12 | mesh_address | Device mesh address (little-endian) |

---

## Python Parsing

### Basic ZengGe Parsing (Format B)

```python
def parse_zengge_mfr_data(mfr_data: dict[int, bytes]) -> dict | None:
    """Parse standard ZengGe manufacturer data."""
    for cid, payload in mfr_data.items():
        if 23040 <= cid <= 23295 and len(payload) >= 27:
            ble_version = payload[1]
            return {
                "format": "zengge",
                "sta": payload[0],
                "ble_version": ble_version,
                "mac": ":".join(f"{b:02X}" for b in payload[2:8]),
                "product_id": (payload[8] << 8) | payload[9],
                "firmware_ver": payload[10],
                "led_version": payload[11],
                "power_on": payload[14] == 0x23 if ble_version >= 5 else None,
            }
    return None
```

### Telink Parsing

```python
def parse_telink_mfr_data(mfr_data: dict[int, bytes]) -> dict | None:
    """Parse Telink BLE Mesh manufacturer data."""
    for cid, payload in mfr_data.items():
        if cid == 4354 and len(payload) >= 13:  # 0x1102
            status = payload[10] & 0xFF
            return {
                "format": "telink",
                "product_id": 0x80,  # IOTBT
                "mesh_uuid": (payload[3] << 8) | payload[2],
                "product_uuid": (payload[9] << 8) | payload[8],
                "status": status,
                "power_on": status > 0,
                "mesh_address": (payload[12] << 8) | payload[11],
            }
    return None
```

### Complete Parsing (All Formats)

```python
def parse_advertisement(
    mfr_data: dict[int, bytes],
    service_data: dict[str, bytes]
) -> dict | None:
    """Parse LEDnetWF advertisement - all formats."""

    # Check for service data (BLE v7+)
    sd = None
    for uuid_str, data in service_data.items():
        if "ffff" in uuid_str.lower() and len(data) >= 16:
            sd = data
            break

    # Check manufacturer data
    md = None
    for cid, data in mfr_data.items():
        if 23040 <= cid <= 23295:  # ZengGe
            md = data
            break
        if cid == 4354:  # Telink
            return parse_telink_mfr_data(mfr_data)

    if md is None and sd is None:
        return None

    # Parse based on what's available
    if sd is not None and md is not None:
        # BLE v7+: ID from service data, state from mfr_data offset 3
        ble_version = sd[3]
        product_id = (sd[10] << 8) | sd[11]
        if ble_version >= 7 and len(md) >= 28:
            power_byte = md[14]  # state_data[11] = mfr_data[3+11]
        else:
            power_byte = md[14] if len(md) > 14 else None
    elif sd is not None:
        # Service data only
        ble_version = sd[3]
        product_id = (sd[10] << 8) | sd[11]
        power_byte = sd[16] if len(sd) >= 29 else None
    else:
        # Manufacturer data only
        ble_version = md[1]
        product_id = (md[8] << 8) | md[9]
        power_byte = md[14] if ble_version >= 5 and len(md) > 14 else None

    power_on = None
    if power_byte == 0x23:
        power_on = True
    elif power_byte == 0x24:
        power_on = False

    return {
        "format": "zengge",
        "product_id": product_id,
        "ble_version": ble_version,
        "power_on": power_on,
        "has_service_data": sd is not None,
    }
```

---

## Home Assistant / bleak Integration

```python
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak

def parse_discovery(info: BluetoothServiceInfoBleak) -> dict | None:
    """Parse BLE discovery for LEDnetWF device."""
    # Service data: dict[uuid_string, bytes]
    service_data = info.service_data

    # Manufacturer data: dict[company_id: int, bytes]
    mfr_data = info.manufacturer_data

    return parse_advertisement(mfr_data, service_data)
```

---

## Key Points

1. **Company ID identifies format**: 0x5A** = ZengGe, 0x1102 = Telink
2. **BLE v7+ uses service data**: Device ID in service data, state at mfr_data offset 3
3. **Power state**: 0x23 = ON, 0x24 = OFF (ZengGe); non-zero = ON (Telink)
4. **Product ID is big-endian**: `(byte[8] << 8) | byte[9]`

---

## Source Files

| File | Purpose |
|------|---------|
| `ZGHBDevice.java` | ZengGe advertisement parsing |
| `com/telink/bluetooth/light/c.java` | Telink format parsing |
| `Service.java` | Service UUID definitions |
