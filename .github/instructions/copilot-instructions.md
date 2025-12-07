# LEDnetWF BLE v2 Integration - Development Guidelines

## Project Mission

Build a **new** Home Assistant integration (`lednetwf_ble`) for LEDnetWF Bluetooth Low Energy devices from scratch, based on reverse-engineered protocol documentation rather than copying from the old integration.

### Goals
- Clean, maintainable codebase with minimal files
- Protocol-driven implementation based on `protocol_docs/`
- Dynamic capability detection for unknown devices
- Proper BLE advertisement parsing and state monitoring
- Support for all LEDnetWF/IOTWF/IOTB device variants

## Architecture

### Key Principles
1. **Protocol docs are the source of truth** - Always check `protocol_docs/` before implementing
2. **No per-model files** - Use capability probing instead of hardcoded model classes
3. **Accept unknown devices** - Probe capabilities at runtime rather than rejecting
4. **Separate transport layer** - 8-byte header wrapping/unwrapping in `protocol.py`

### File Structure
```
custom_components/lednetwf_ble/
├── __init__.py      # Integration setup, Bluetooth callbacks
├── config_flow.py   # Device discovery and configuration UI
├── const.py         # Constants, enums, capability mappings
├── device.py        # BLE connection management, state, commands
├── light.py         # Home Assistant Light entity
├── number.py        # Effect speed Number entity
├── protocol.py      # Transport layer, command builders, response parsers
├── manifest.json    # Integration metadata
├── strings.json     # UI strings
└── translations/    # Localization files
```

## Protocol Reference

### Device Discovery
- **Name filter**: Accept `LEDnetWF*`, `IOTWF*`, `IOTB*`
- **Company ID**: Must be in range 0x5A00-0x5AFF (23040-23295)
- **Payload length**: Must be exactly 27 bytes (Format B)
- **Product ID**: Bytes 8-9 of payload (big-endian)

### Command Formats
- **0x3B**: Modern power/color commands (BLE version >= 5)
- **0x31**: Legacy color command with RGB+WW+CW
- **0x61**: Simple effects (IDs 37-56)
- **0x38**: Symphony effects (scene 1-44, build 100-399)
- **0x62**: LED settings (count, IC type, color order)
- **0x81**: State query/response

### Transport Layer
All commands wrapped with 8-byte header:
```
[0x00, seq, 0x80, payload_len, 0x00, cmd_family, 0x00, 0x00] + payload
```

## Capability Detection

### Known Devices
Product IDs in `PRODUCT_CAPABILITIES` table have documented capabilities.

### Unknown Devices
For unknown product IDs:
1. Accept the device (don't reject)
2. Mark as `needs_probing: True`
3. During setup, probe by:
   - Send state query, wait for response
   - Test RGB: set R=0x32, check if reflected in state
   - Test WW: set WW=0x32, check state
   - Test CW: set CW=0x32, check state
   - Restore original state
4. Cache probed capabilities in config entry

## Code Standards

### Python Style
- Type hints on all function signatures
- Async/await for all I/O operations
- Use `protocol_docs/` references in docstrings

### Home Assistant Conventions
- Proper entity lifecycle (async_added_to_hass, async_will_remove_from_hass)
- Use Home Assistant's bluetooth component APIs
- Implement options flow for runtime configuration
- Support Bluetooth advertisement state updates

### Error Handling
- Never crash on unknown device features
- Log warnings with hex dumps for debugging
- Provide safe defaults for unknown modes
- Graceful degradation for unsupported capabilities

## Key Protocol Documentation

| Document | Content |
|----------|---------|
| `02_ble_scanning_device_discovery.md` | Device name filters, scan config |
| `03_manufacturer_data_parsing.md` | Format A/B parsing, field offsets |
| `04_device_identification_capabilities.md` | Product ID mapping, probing methods |
| `06_transport_layer_protocol.md` | 8-byte header format, wrapping |
| `07_control_commands.md` | Power, color, white, effect commands |
| `08_state_query_response_parsing.md` | 0x81 response format |
| `09_effects_addressable_led_support.md` | LED settings, effect types |

## Testing

- Test with actual hardware when possible
- Request debug logs from users for new device variants
- Verify capability probing works for unknown product IDs
- Check state updates from BLE advertisements
- Validate disconnect delay behavior

## Adding Support for New Features

1. Check protocol documentation first
2. Add to `protocol.py` with source reference in docstring
3. Update `const.py` if new capabilities needed
4. Update `device.py` to expose new functionality
5. Update entity files (light.py, number.py) if UI needed
