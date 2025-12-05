# ZENGEE BLE LED CONTROLLER - DOCUMENTATION INDEX

**Document Version**: 2.0
**Last Updated**: 3 December 2025
**Purpose**: Index for navigating split protocol documentation

## About This Documentation

This documentation has been split into 11 separate files for easier navigation and maintenance. Each file covers a specific aspect of the ZENGEE BLE LED Controller protocol.

## Quick Navigation by Topic

### Need to... → Go to...

| Need                                          | File                                      |
|-----------------------------------------------|-------------------------------------------|
| **Get started quickly** / see command syntax  | `01_overview_quick_reference.md`          |
| **Scan for devices** / understand BLE ads     | `02_ble_scanning_device_discovery.md`     |
| **Parse manufacturer data** / device info     | `03_manufacturer_data_parsing.md`         |
| **Identify device capabilities** / product IDs| `04_device_identification_capabilities.md`|
| **Connect to device** / setup GATT            | `05_connection_management.md`             |
| **Understand transport layer** / wrap commands| `06_transport_layer_protocol.md`          |
| **Send color/power commands** / control device| `07_control_commands.md`                  |
| **Query device state** / parse responses      | `08_state_query_response_parsing.md`      |
| **Work with effects** / addressable LEDs      | `09_effects_addressable_led_support.md`   |
| **Implement in Python** / complete example    | `10_python_implementation_guide.md`       |
| **Reference original code** / Java files      | `11_java_source_code_references.md`       |
| **Look up effect names** / Symphony modes     | `12_symphony_effect_names.md`             |
| **Control LED curtain lights** / matrix panels| `13_led_curtain_lights.md`                |
| **Symphony FG/BG colors** / effect colors     | `14_symphony_background_colors.md`        |

---

## Detailed File Contents

### 01. Overview and Quick Reference
**File**: `01_overview_quick_reference.md`

**Contains**:
- Quick reference table of essential commands
- BLE service/characteristic UUIDs
- Device naming patterns
- Company ID ranges

**Keywords**: quick start, UUIDs, commands, reference

**Use this when**: You need a quick lookup for basic commands or UUIDs.

---

### 02. BLE Scanning and Device Discovery
**File**: `02_ble_scanning_device_discovery.md`

**Contains**:
- BLE scan configuration settings
- Advertisement data structure (TLV format)
- AD Types explanation
- Device filtering criteria

**Keywords**: scanning, discovery, advertisement, TLV, filtering

**Use this when**: You're implementing device scanning or need to understand BLE advertisement structure.

---

### 03. Manufacturer Data Parsing
**File**: `03_manufacturer_data_parsing.md`

**Contains**:
- Two manufacturer data formats (Format A: 29 bytes, Format B: 27 bytes)
- Field-by-field breakdown of manufacturer data
- Python parsing example
- Bleak library usage

**Keywords**: manufacturer data, parsing, bleak, company ID, MAC address, product ID

**Use this when**: You need to extract device information from BLE manufacturer data.

---

### 04. Device Identification and Capabilities
**File**: `04_device_identification_capabilities.md`

**Contains**:
- Manufacturer ID ranges
- Protocol version determination
- Product ID to capabilities mapping table
- Capability detection algorithm

**Keywords**: product ID, capabilities, RGB, RGBCW, CCT, device types

**Use this when**: You need to determine what features a device supports based on its product ID.

---

### 05. Connection Management
**File**: `05_connection_management.md`

**Contains**:
- BLE GATT connection sequence
- Notification enable procedure
- CCCD descriptor explanation
- MTU negotiation

**Keywords**: connection, GATT, notifications, CCCD, MTU

**Use this when**: You're implementing BLE connection logic or troubleshooting connection issues.

---

### 06. Transport Layer Protocol
**File**: `06_transport_layer_protocol.md`

**Contains**:
- Upper transport layer structure
- Lower transport layer packet format
- Response message types
- Python encoder implementation

**Keywords**: transport layer, packet wrapping, sequence numbers, cmd_id

**Use this when**: You need to wrap commands in the transport layer or understand packet structure.

---

### 07. Control Commands
**File**: `07_control_commands.md`

**Contains**:
- Checksum calculation
- RGB color command (0x31)
- Brightness command (0x47)
- Power commands (0x11)
- Effect command (0x38)
- HSV/Symphony command (0x3B)

**Keywords**: commands, RGB, brightness, power, effects, HSV, checksum

**Use this when**: You need to construct specific control commands to send to the device.

---

### 08. State Query and Response Parsing
**File**: `08_state_query_response_parsing.md`

**Contains**:
- State query command (0x81)
- State response format (14 bytes)
- Field descriptions
- Python response parser

**Keywords**: state query, response parsing, device state, power state

**Use this when**: You need to read the current state of the device.

---

### 09. Effects and Addressable LED Support
**File**: `09_effects_addressable_led_support.md`

**Contains**:
- Effect counts by device type
- Addressable vs global-color LEDs
- Symphony device information
- Effect detection

**Keywords**: effects, addressable LEDs, Symphony, LED strips

**Use this when**: You're working with LED effects or addressable LED strips.

---

### 10. Python Implementation Guide
**File**: `10_python_implementation_guide.md`

**Contains**:
- Complete Python implementation using bleak
- LEDController class with all methods
- Connection handling
- Command sending
- State querying
- Usage example

**Keywords**: Python, bleak, implementation, example, async

**Use this when**: You want a working Python implementation to start from.

---

### 11. Java Source Code References
**File**: `11_java_source_code_references.md`

**Contains**:
- Key Java source file list
- Command builder method references
- File purposes and locations

**Keywords**: Java, source code, reference, tc/b.java, tc/d.java

**Use this when**: You need to reference the original Java implementation.

---

### 13. LED Curtain Light Protocol

**File**: `13_led_curtain_lights.md`

**Contains**:

- LED curtain light device identification (Product IDs 172, 173)
- Supported matrix sizes (13x10 to 30x30)
- On/Off commands (0x3B, 0x71)
- RGB color commands (0x3B HSV, 0x31 direct)
- Effect commands (0x38 Symphony format)
- Speed encoding (1-31 inverted)

**Keywords**: curtain light, LED matrix, panel, symphony_curtain, surplife

**Use this when**: You're working with LED curtain/matrix panel devices from surplife.

---

### 14. Symphony Background Colors

**File**: `14_symphony_background_colors.md`

**Contains**:

- 0x41 command format for FG/BG colors (13 bytes)
- 0xA3 command format for multi-color arrays (variable)
- Effect UI types and which effects support background colors
- State response parsing for FG/BG colors
- Python implementations for both command formats

**Keywords**: Symphony, background color, foreground, 0x41, 0xA3, effect colors, settled mode

**Use this when**: You need to set foreground and background colors for Symphony device effects.

---

## Common Task Workflows

### Task: Implement a basic LED controller

1. Start with `01_overview_quick_reference.md` to understand the basics
2. Read `02_ble_scanning_device_discovery.md` for device scanning
3. Read `03_manufacturer_data_parsing.md` to extract device info
4. Read `05_connection_management.md` for connection setup
5. Read `06_transport_layer_protocol.md` to understand command wrapping
6. Read `07_control_commands.md` for available commands
7. Use `10_python_implementation_guide.md` for a complete example

### Task: Determine device capabilities

1. Read `03_manufacturer_data_parsing.md` to get product ID
2. Read `04_device_identification_capabilities.md` to look up capabilities
3. If unknown, use capability detection algorithm in same file

### Task: Troubleshoot command issues

1. Check `07_control_commands.md` for correct command format
2. Verify transport layer wrapping in `06_transport_layer_protocol.md`
3. Check connection setup in `05_connection_management.md`
4. Query device state using `08_state_query_response_parsing.md`

### Task: Work with LED effects

1. Identify device type using `04_device_identification_capabilities.md`
2. Check if device supports effects in `09_effects_addressable_led_support.md`
3. Use effect command from `07_control_commands.md`

---

## Command Quick Reference

| Command Type        | Opcode | Details File                       |
|---------------------|--------|------------------------------------|
| Query State         | 0x81   | `08_state_query_response_parsing.md` |
| Set RGB/RGBCW       | 0x31   | `07_control_commands.md`           |
| Power On/Off        | 0x11   | `07_control_commands.md`           |
| Set Brightness      | 0x47   | `07_control_commands.md`           |
| Set Effect          | 0x38   | `07_control_commands.md`           |
| HSV/Symphony Color  | 0x3B   | `07_control_commands.md`           |

---

## Important Constants

| Constant                | Value                                   | File                            |
|-------------------------|-----------------------------------------|---------------------------------|
| Service UUID            | `0000ffff-0000-1000-8000-00805f9b34fb`  | `01_overview_quick_reference.md`|
| Write Characteristic    | `0000ff01-0000-1000-8000-00805f9b34fb`  | `01_overview_quick_reference.md`|
| Notify Characteristic   | `0000ff02-0000-1000-8000-00805f9b34fb`  | `01_overview_quick_reference.md`|
| Company ID Range        | 23040-23295 (0x5A00-0x5AFF)             | `01_overview_quick_reference.md`|
| Device Names            | "LEDnetWF", "IOTWF"                     | `01_overview_quick_reference.md`|

---

## Data Structure Sizes

| Structure               | Size    | File                                  |
|-------------------------|---------|---------------------------------------|
| Manufacturer Data (A)   | 29 bytes| `03_manufacturer_data_parsing.md`     |
| Manufacturer Data (B)   | 27 bytes| `03_manufacturer_data_parsing.md`     |
| State Response          | 14 bytes| `08_state_query_response_parsing.md`  |
| RGB Command             | 9 bytes | `07_control_commands.md`              |
| Power Command           | 5 bytes | `07_control_commands.md`              |
| Effect Command          | 5 bytes | `07_control_commands.md`              |
| Brightness Command      | 3 bytes | `07_control_commands.md`              |

---

## For AI Assistants

When helping users with ZENGEE BLE LED Controller questions:

1. **Identify the topic** from the user's question
2. **Reference the appropriate file** using the navigation table above
3. **Provide specific information** from that file
4. **Link related concepts** from other files when necessary

### Example Query Mapping

- "How do I turn on the light?" → `07_control_commands.md` (Power Commands)
- "How do I scan for devices?" → `02_ble_scanning_device_discovery.md`
- "What is product ID 51?" → `04_device_identification_capabilities.md`
- "How do I parse the response?" → `08_state_query_response_parsing.md`
- "Show me a working example" → `10_python_implementation_guide.md`
- "What are the UUIDs?" → `01_overview_quick_reference.md`

---

## File List

All documentation files are in the `docs/` directory:

```
docs/
├── INDEX.md (this file)
├── 01_overview_quick_reference.md
├── 02_ble_scanning_device_discovery.md
├── 03_manufacturer_data_parsing.md
├── 04_device_identification_capabilities.md
├── 05_connection_management.md
├── 06_transport_layer_protocol.md
├── 07_control_commands.md
├── 08_state_query_response_parsing.md
├── 09_effects_addressable_led_support.md
├── 10_python_implementation_guide.md
├── 11_java_source_code_references.md
├── 12_symphony_effect_names.md
├── 13_led_curtain_lights.md
└── 14_symphony_background_colors.md
```

---

**End of Index**
