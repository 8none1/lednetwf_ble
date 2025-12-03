# BLE SCANNING AND DEVICE DISCOVERY

## Scan Configuration

- **Scan mode**: BLE_SCAN_MODE_LOW_LATENCY (mode=2)
- **Report delay**: 0ms (immediate reporting)
- **Filter**: Device name containing "LEDnetWF" or "IOTWF"

## Advertisement Data Structure (TLV Format)

Raw advertisement data follows Type-Length-Value encoding:

### Structure of each TLV block

- **Byte 0**: Length (includes type byte, so actual_length = length - 1)
- **Byte 1**: Type (AD Type per Bluetooth spec)
- **Bytes 2+**: Value (data)

### Relevant AD Types

- **Type 1 (0x01)**: Flags
- **Type 9 (0x09)**: Complete Local Name
- **Type 22 (0x16)**: Service Data - 16-bit UUID
- **Type 255 (0xFF)**: Manufacturer Specific Data (PRIMARY DATA SOURCE)
