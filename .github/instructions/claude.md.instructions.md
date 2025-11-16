---
applyTo: '**'
---

# LEDnetWF BLE Integration - AI Coding Guidelines

## Project Context
This is a Home Assistant custom integration for LEDnetWF Bluetooth Low Energy devices (Zengge LEDnetWF, Magic Hue, etc.).

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

### Model Architecture
- Each device model (0x53, 0x54, 0x56, etc.) has its own model file
- Models inherit from `DefaultModelAbstraction`
- Models handle device-specific protocol and data parsing
- Store enum objects (not values or names) for chip types and color orders

### Error Handling
- Handle unknown/unsupported device features gracefully
- Log warnings for unknown modes/effects instead of crashing
- Provide safe defaults when encountering unexpected data
- Include full hex dumps in debug logs for troubleshooting

### Bluetooth Communication
- Use `_write()` for sending commands to devices
- Implement notification handlers for device responses
- Support device-specific packets (LED settings, effects, etc.)
- Handle connection timeouts and retries

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

### Configuration Flow
- Enum objects should be passed from config flow to models
- Use `.value` to extract integer values for packets
- Use `.name` for display in UI dropdowns

## Testing
- Test with actual devices when possible
- Request debug logs from users for unsupported variants
- Add safe defaults for unknown device modes

## Documentation
- Keep README.md updated with configuration options
- Maintain translation files for all supported languages
- Document new features in release notes

## Important Notes
- LED count, chip type, and color order are auto-detected during setup
- Devices may have firmware variants that behave differently
- Always include manufacturer data hex dumps in error logs
- Segments support varies by device model
