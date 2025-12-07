# Request: Data-Driven Device Support Architecture

**Date**: 7 December 2025
**Priority**: High
**Type**: Architecture Refactor

---

## Summary

Refactor the LEDnetWF BLE Home Assistant integration to use a **data-driven architecture** that reads device capabilities and command formats from JSON configuration files extracted from the official Surplife Android app.

This eliminates hardcoded device models and makes the integration automatically support new devices as they're added to the app's configuration.

---

## Background

### Current Problem

The current integration uses hardcoded device models in `custom_components/lednetwf_ble/models/`:
- `model_0x53.py`, `model_0x54.py`, `model_0x56.py`, etc.
- Each model duplicates command building logic
- Adding new device support requires writing new Python files
- Device capabilities are guessed through reverse engineering

### Discovery

The Surplife Android app uses JSON configuration files that define **all device capabilities**:

1. **`ble_devices.json`** - Device capabilities per product ID
2. **`wifi_dp_cmd.json`** - Command byte templates
3. **`wifi_device_panel.json`** - UI configuration (which features to show)

These files are located at:
```
/home/will/source/jadx/projects/surplife/assets/flutter_assets/packages/magichome2_home_data_provide/assets/
```

---

## Source Data Files

### 1. `ble_devices.json` - Device Capabilities

Each device entry contains:

```json
{
  "productId": 8,
  "icon": "enum://dengdai",
  "category": "zm",
  "categoryCode": "dj",
  "protocols": [
    {"name": "common", "deviceMinVer": 0},
    {"name": "rgb_mini_mic", "deviceMinVer": 0},
    {"name": "common1_0", "deviceMinVer": 2},
    {"name": "common2_0", "deviceMinVer": 3}
  ],
  "functions": [
    {
      "code": "scene_data",
      "deviceMinVer": 0,
      "value": {
        "fields": [
          {"fieldName": "model", "min": 37, "max": 56, "step": 1},
          {"fieldName": "speed", "min": 1, "max": 31, "step": 1}
        ]
      }
    },
    {
      "code": "scene_data_v2",
      "deviceMinVer": 1,
      "value": {
        "fields": [
          {"fieldName": "model", "min": 37, "max": 56, "step": 1},
          {"fieldName": "speed", "min": 1, "max": 31, "step": 1},
          {"fieldName": "bright", "min": 1, "max": 100, "step": 1}
        ]
      }
    },
    {
      "code": "colour_data",
      "deviceMinVer": 0,
      "value": {
        "fields": [
          {"fieldName": "r", "min": 0, "max": 255},
          {"fieldName": "g", "min": 0, "max": 255},
          {"fieldName": "b", "min": 0, "max": 255}
        ]
      }
    }
  ],
  "hexCmdForms": {
    "colour_data": {
      "cmdForm": "31{r}{g}{b}00000f",
      "customParams": {"needChecksum": true}
    },
    "music_color_data": {
      "cmdForm": "41{r}{g}{b}00000f",
      "customParams": {"needChecksum": true}
    }
  },
  "stateProtocol": [
    {"name": "wifibleLightStandardV1", "deviceMinVer": 0}
  ]
}
```

**Key fields:**
- `productId` - Device identifier from BLE advertisement
- `functions` - What the device supports and at which firmware version
- `functions[].value.fields` - Parameter ranges (min, max, step)
- `hexCmdForms` - Device-specific command overrides
- `stateProtocol` - How to parse state responses

### 2. `wifi_dp_cmd.json` - Command Templates

Global command templates (used when not overridden in hexCmdForms):

```json
{
  "scene_data_v2": {
    "cmdForm": "38{model}{speed}{bright}",
    "needChecksum": true
  },
  "scene_data_v3": {
    "cmdForm": "e002{preview}{model}{speed}{bright}",
    "needChecksum": false
  },
  "switch_led": {
    "cmdForm": "71{open}0f",
    "needChecksum": true
  },
  "switch_led_v2": {
    "cmdForm": "3b{open}0000000000{gradient}{gradient}{gradient}{delay}{delay}",
    "needChecksum": true
  },
  "bright_value_v2": {
    "cmdForm": "3b010000{value}00{value}{delay}{delay}{delay}{gradient}{gradient}",
    "needChecksum": true
  },
  "colour_data_v2": {
    "cmdForm": "3ba10000{hue}{saturation}{bright}00001e0000",
    "needChecksum": true
  },
  "temp_value_v2": {
    "cmdForm": "3bb1000000{cct}{bright}00001e0000",
    "needChecksum": true
  },
  "candle_data": {
    "cmdForm": "39{exeType}{exeValue}{exeValue}{exeValue}{speed}{bright}{extent}",
    "needChecksum": true
  },
  "state_upload": {
    "cmdForm": "818A8B96",
    "needChecksum": false,
    "responseCount": 1
  }
}
```

**Key fields:**
- `cmdForm` - Hex template with `{parameter}` placeholders
- `needChecksum` - Whether to append checksum byte
- `responseCount` - Expected response length (for queries)

---

## Proposed Architecture

### Directory Structure

```
custom_components/lednetwf_ble/
├── __init__.py
├── manifest.json
├── config_flow.py
├── const.py
├── light.py
├── device.py
├── data/                          # NEW: JSON data files
│   ├── ble_devices.json          # Copy from app
│   ├── wifi_dp_cmd.json          # Copy from app
│   └── wifi_device_panel.json    # Copy from app (optional)
├── capabilities.py                # NEW: Device capability lookup
├── commands.py                    # NEW: Command builder from templates
└── protocol.py                    # Simplified - uses commands.py
```

### Core Components

#### 1. `capabilities.py` - Device Capability Lookup

```python
"""Device capability lookup from ble_devices.json."""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

@dataclass
class FunctionCapability:
    code: str
    min_firmware: int
    fields: dict[str, dict]  # fieldName -> {min, max, step}

@dataclass
class DeviceCapabilities:
    product_id: int
    protocols: list[str]
    functions: dict[str, FunctionCapability]
    hex_cmd_forms: dict[str, dict]
    state_protocol: str

class CapabilityDatabase:
    def __init__(self):
        data_dir = Path(__file__).parent / "data"

        with open(data_dir / "ble_devices.json") as f:
            self._devices = {d["productId"]: d for d in json.load(f)}

        with open(data_dir / "wifi_dp_cmd.json") as f:
            self._cmd_templates = json.load(f)

    def get_device(self, product_id: int) -> Optional[DeviceCapabilities]:
        """Get capabilities for a device by product ID."""
        if product_id not in self._devices:
            return None

        device = self._devices[product_id]

        # Parse functions
        functions = {}
        for func in device.get("functions", []):
            fields = {}
            for field in func.get("value", {}).get("fields", []):
                fields[field["fieldName"]] = {
                    "min": field.get("min"),
                    "max": field.get("max"),
                    "step": field.get("step", 1)
                }
            functions[func["code"]] = FunctionCapability(
                code=func["code"],
                min_firmware=func.get("deviceMinVer", 0),
                fields=fields
            )

        return DeviceCapabilities(
            product_id=product_id,
            protocols=[p["name"] for p in device.get("protocols", [])],
            functions=functions,
            hex_cmd_forms=device.get("hexCmdForms", {}),
            state_protocol=device.get("stateProtocol", [{}])[0].get("name", "")
        )

    def supports_function(self, product_id: int, function_code: str,
                          firmware_version: int) -> bool:
        """Check if device supports a function at given firmware."""
        device = self.get_device(product_id)
        if not device or function_code not in device.functions:
            return False
        return firmware_version >= device.functions[function_code].min_firmware

    def get_command_template(self, product_id: int, function_code: str) -> dict:
        """Get command template, preferring device-specific over global."""
        device = self.get_device(product_id)

        # Check device-specific hexCmdForms first
        if device and function_code in device.hex_cmd_forms:
            return device.hex_cmd_forms[function_code]

        # Fall back to global templates
        return self._cmd_templates.get(function_code, {})

# Global instance
CAPABILITIES = CapabilityDatabase()
```

#### 2. `commands.py` - Command Builder

```python
"""Build commands from templates."""

from .capabilities import CAPABILITIES

def build_command(product_id: int, function_code: str,
                  params: dict[str, int]) -> bytes:
    """
    Build a command from template and parameters.

    Args:
        product_id: Device product ID
        function_code: Function name (e.g., "scene_data_v2")
        params: Parameter values (e.g., {"model": 41, "speed": 16, "bright": 100})

    Returns:
        Command bytes ready to send (with checksum if needed)
    """
    template = CAPABILITIES.get_command_template(product_id, function_code)
    if not template:
        raise ValueError(f"No template for {function_code}")

    cmd_form = template.get("cmdForm", "")

    # Replace parameters - each {param} becomes 2 hex chars
    for key, value in params.items():
        placeholder = f"{{{key}}}"
        if placeholder in cmd_form:
            cmd_form = cmd_form.replace(placeholder, f"{value:02x}")

    # Convert to bytes
    cmd = bytes.fromhex(cmd_form)

    # Add checksum if needed
    if template.get("needChecksum") or template.get("customParams", {}).get("needChecksum"):
        cmd = cmd + bytes([sum(cmd) & 0xFF])

    return cmd


def get_best_function(product_id: int, firmware_version: int,
                      function_preferences: list[str]) -> Optional[str]:
    """
    Get the best available function from a preference list.

    Args:
        product_id: Device product ID
        firmware_version: Device firmware version
        function_preferences: List of functions in preference order
                              e.g., ["scene_data_v3", "scene_data_v2", "scene_data"]

    Returns:
        Best supported function code, or None
    """
    for func in function_preferences:
        if CAPABILITIES.supports_function(product_id, func, firmware_version):
            return func
    return None
```

#### 3. Usage in `device.py`

```python
from .capabilities import CAPABILITIES
from .commands import build_command, get_best_function

class LEDNetWFDevice:
    def __init__(self, product_id: int, firmware_version: int):
        self.product_id = product_id
        self.firmware_version = firmware_version
        self.capabilities = CAPABILITIES.get_device(product_id)

    def set_effect(self, effect_id: int, speed: int, brightness: int) -> bytes:
        """Build effect command using best available function."""

        # Find best effect function for this device/firmware
        func = get_best_function(
            self.product_id,
            self.firmware_version,
            ["scene_data_v3", "scene_data_v2", "scene_data"]
        )

        if func == "scene_data_v3":
            # v3: direct speed 0-100, has preview
            return build_command(self.product_id, func, {
                "preview": 0,
                "model": effect_id,
                "speed": speed,  # 0-100 direct
                "bright": brightness
            })

        elif func == "scene_data_v2":
            # v2: inverted speed 1-31
            protocol_speed = 1 + int(30 * (1.0 - speed/100.0))
            return build_command(self.product_id, func, {
                "model": effect_id,
                "speed": protocol_speed,
                "bright": brightness
            })

        elif func == "scene_data":
            # Legacy: no brightness
            protocol_speed = 1 + int(30 * (1.0 - speed/100.0))
            return build_command(self.product_id, func, {
                "model": effect_id,
                "speed": protocol_speed
            })

        raise ValueError(f"No effect function for product {self.product_id:#x}")

    def set_color(self, r: int, g: int, b: int) -> bytes:
        """Build color command."""
        func = get_best_function(
            self.product_id,
            self.firmware_version,
            ["colour_data_v3", "colour_data_v2", "colour_data"]
        )
        return build_command(self.product_id, func, {"r": r, "g": g, "b": b})

    def supports_effect_brightness(self) -> bool:
        """Check if device supports brightness in effects."""
        return CAPABILITIES.supports_function(
            self.product_id, "scene_data_v2", self.firmware_version
        ) or CAPABILITIES.supports_function(
            self.product_id, "scene_data_v3", self.firmware_version
        )
```

---

## State Response Parsing (NOT Data-Driven)

**IMPORTANT**: The JSON configuration files only define **command formats**, NOT response parsing. State response parsing is complex, mode-dependent, and must remain in Python code.

### Why State Parsing Cannot Be Data-Driven

1. **Response format varies by mode** - Same device uses different byte meanings in RGB vs CCT vs Effect modes
2. **Mode detection is complex** - Must check multiple bytes to determine current mode
3. **Brightness derivation varies** - HSV extraction for RGB, direct value for white mode, different byte for effects
4. **Device-specific quirks** - SIMPLE devices report mode_type=effect_id, Symphony uses different format

### State Protocol Types (from `ble_devices.json`)

The `stateProtocol` field indicates which parser to use, but the actual parsing logic is in code:

| Protocol Name | Description | Products |
|---------------|-------------|----------|
| `wifibleLightStandardV1` | Standard 14-byte 0x81 format | 0x08, 0x33, most devices |
| `wifibleLightStandardV2` | Extended standard format | Newer firmware |
| `wifibleNewRGBSymphony` | Symphony-specific parsing | 0xA2-0xAD |
| `wifibleRGBSymphony` | Old Symphony format | 0xA1 |
| `wifibleCCT` | CCT-only devices | CCT bulbs |
| `wifibleBrightness` | Brightness-only devices | Dimmers |

### Standard 0x81 State Response Format

Source: `protocol_docs/08_state_query_response_parsing.md`

```text
Byte 0:  Header (0x81)
Byte 1:  Mode
Byte 2:  Power State (0x23 = ON)
Byte 3:  Mode Type (0x61=static, 0x25=effect, 37-56=SIMPLE effect ID)
Byte 4:  Sub-mode (0xF0=RGB, 0x0F=white, or effect params)
Byte 5:  Value1 (brightness 0-100 for white mode)
Byte 6:  R (or brightness in effect mode)
Byte 7:  G (or speed in effect mode)
Byte 8:  B
Byte 9:  WW / Color Temp
Byte 10: LED Version (NOT brightness!)
Byte 11: CW
Byte 12: Reserved
Byte 13: Checksum
```

### Mode-Dependent Brightness Derivation

```python
def get_brightness_from_state(response: dict, device_type: str) -> int:
    """Brightness extraction varies by mode."""

    if response["is_effect_mode"]:
        # Effect mode: byte 6 contains brightness 0-100
        return int(response["r"] * 255 / 100)

    elif response["is_white_mode"]:
        # White mode: byte 5 (value1) contains brightness 0-100
        return int(response["value1"] * 255 / 100)

    elif response["is_rgb_mode"]:
        # RGB mode: derive from RGB via HSV (V component)
        r, g, b = response["r"], response["g"], response["b"]
        _, _, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        return int(v * 255)
```

### Current Implementation Location

State parsing is currently implemented in:

- `protocol.py:parse_state_response()` - Basic 0x81 parsing
- `device.py:_parse_state_response()` - Mode-dependent interpretation
- `device.py:_parse_device_state2_response()` - IOTBT devices (0xEA 0x81 format)

### Recommendation for Data-Driven Architecture

1. **Keep state parsing in Python** - Don't try to make this data-driven
2. **Use `stateProtocol` to select parser** - Map protocol names to parsing functions
3. **Capability lookup can inform parsing** - Use JSON data to know which modes device supports
4. **Document protocol variants** - See `protocol_docs/08_state_query_response_parsing.md`

---

## Implementation Steps

### Phase 1: Data Files

1. Copy JSON files from decompiled app to `data/` directory
2. Validate JSON structure and fix any issues
3. Create `__init__.py` in `data/` if needed

### Phase 2: Capability Lookup

1. Implement `capabilities.py` with `CapabilityDatabase` class
2. Add unit tests for capability lookup
3. Verify against known devices (0x08, 0x33, 0x54, etc.)

### Phase 3: Command Builder

1. Implement `commands.py` with template-based building
2. Handle multi-byte parameters (e.g., `{delay}{delay}{delay}` for 3-byte delay)
3. Add unit tests comparing output to known-good commands

### Phase 4: Integration

1. Refactor `device.py` to use new command builder
2. Remove hardcoded model files (or deprecate)
3. Update `protocol.py` to use capabilities for response parsing

### Phase 5: Testing

1. Test with physical devices
2. Verify all existing functionality still works
3. Test new devices that weren't previously supported

---

## Benefits

1. **Automatic device support** - New devices work if they're in the JSON
2. **Accurate capabilities** - Uses same data as official app
3. **Maintainable** - Update JSON files to add features
4. **Reduced code** - No more per-device model files
5. **Correct parameters** - Min/max/step values from app
6. **Future-proof** - Easy to update from newer app versions

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| JSON format changes | Version the data files, validate on load |
| Missing devices | Fallback to legacy behavior |
| Command template bugs | Extensive unit tests against known commands |
| Performance | Cache parsed data, lazy load |

---

## Files to Reference

- **Source JSON files**: `/home/will/source/jadx/projects/surplife/assets/flutter_assets/packages/magichome2_home_data_provide/assets/`
- **Current integration**: `/home/will/source/lednetwf_ble/custom_components/lednetwf_ble/`
- **Old models**: `/home/will/source/lednetwf_ble/custom_components/lednetwf_ble/models/`
- **Protocol docs**: `/home/will/source/lednetwf_ble/protocol_docs/`

---

## Success Criteria

1. All existing device functionality preserved
2. Product 0x08 supports effect brightness (currently doesn't)
3. No more hardcoded model files needed
4. Command output matches known-good captured commands
5. New devices can be supported by updating JSON only

---

**End of Request**
