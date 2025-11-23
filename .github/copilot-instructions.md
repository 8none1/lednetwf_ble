# LEDnetWF BLE Integration - Copilot Guidelines

## Project Context
This is a Home Assistant custom integration for LEDnetWF Bluetooth Low Energy devices (Zengge LEDnetWF, Magic Hue, etc.). The integration enables Home Assistant to discover and control various models of LED strips and lights that use the Zengge platform via Bluetooth.

## Code Style & Standards

### Python Style
- Follow PEP 8 conventions
- Use type hints where appropriate
- Import statements should be at the top of files
- Use `is` and `is not` for None comparisons, not `==` or `!=`

### Home Assistant Conventions
- Follow Home Assistant integration best practices
- Use async/await patterns for I/O operations
- Properly implement retry logic for Bluetooth connections
- Use Home Assistant's logging framework
- Implement proper entity lifecycle management

### Model Architecture
- Each device model (0x53, 0x54, 0x56, 0x5b, etc.) has its own model file in `custom_components/lednetwf_ble/models/`
- Models inherit from `DefaultModelAbstraction`
- Models handle device-specific protocol and data parsing
- Store enum objects (not values or names) for chip types and color orders

### Error Handling
- Handle unknown/unsupported device features gracefully
- Log warnings for unknown modes/effects instead of crashing
- Provide safe defaults when encountering unexpected data
- Include full hex dumps in debug logs for troubleshooting
- Never let an unknown device feature crash the integration

### Bluetooth Communication
- Use `_write()` for sending commands to devices
- Implement notification handlers for device responses
- Support device-specific packets (LED settings, effects, etc.)
- Handle connection timeouts and retries
- Respect disconnect delays to manage Bluetooth resources

## Common Patterns

### Enum Handling
```python
# CORRECT: Store enum objects
self.chip_type = const.LedTypes_StripLight.WS2812B

# CORRECT: Get value when needed for packets
packet[10] = self.chip_type.value

# INCORRECT: Don't store just the value or name
self.chip_type = chip_type.value  # Wrong
self.chip_type = chip_type.name   # Wrong
```

### Effect Handling
- Check for "Unknown Effect" prefix before processing
- Return None for unsupported effects instead of raising errors
- Log appropriate warnings for debugging
- Gracefully degrade when encountering unknown effects

### Configuration Flow
- Enum objects should be passed from config flow to models
- Use `.value` to extract integer values for packets
- Use `.name` for display in UI dropdowns
- Auto-detect LED count, chip type, and color order during setup

## Testing
- Test with actual devices when possible
- Request debug logs from users for unsupported variants
- Add safe defaults for unknown device modes
- Include manufacturer data hex dumps for debugging

## Documentation
- Keep README.md updated with configuration options
- Maintain translation files for all supported languages (en, de, es, fr, pt, chef)
- Document new features in release notes
- Update configuration option descriptions when adding new features

## Important Notes
- LED count, chip type, and color order are auto-detected during setup
- Devices may have firmware variants that behave differently
- Always include manufacturer data hex dumps in error logs
- Segments support varies by device model
- Real-time state updates via Bluetooth advertisements are supported
- Connection management is critical - respect disconnect delays

## File Structure
- `custom_components/lednetwf_ble/` - Main integration code
- `custom_components/lednetwf_ble/models/` - Device model implementations
- `custom_components/lednetwf_ble/translations/` - Localization files
- Main files:
  - `light.py` - Light entity implementation
  - `config_flow.py` - Configuration UI flow
  - `lednetwf.py` - Core device communication
  - `const.py` - Constants and enums
  - `number.py` - Number entities for configuration

## Adding Support for New Devices
1. Capture BLE traffic using the guide in `SNIFFING_BLE_TRAFFIC.md`
2. Create a new model file in `custom_components/lednetwf_ble/models/`
3. Inherit from `DefaultModelAbstraction`
4. Implement device-specific protocol parsing
5. Add model detection logic based on manufacturer data
6. Test thoroughly with actual hardware
