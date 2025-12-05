# Device Identification Guide for Effect Command Selection

**Date**: 5 December 2025  
**Purpose**: Instructions for determining which effect command format to use

---

## TL;DR - Quick Answer

**Use Product ID, not sta byte!**

The Android app uses **product_id** (bytes 8-9 in bleak format) to instantiate a device class, which determines all capabilities including effect command format. The **sta byte** (byte 0) is just current device status, not device type.

---

## The Right Way: Product ID Based Detection

### Step 1: Extract Product ID from Manufacturer Data

Using Python bleak library:

```python
def get_device_info(advertisement_data):
    """Extract device info from BLE advertisement."""
    mfr_data = advertisement_data.manufacturer_data
    
    # Find LEDnetWF company ID (0x5A** range)
    for company_id, payload in mfr_data.items():
        if 23040 <= company_id <= 23295 and len(payload) == 27:
            # Format B (bleak) - company ID is dict key
            product_id = (payload[8] << 8) | payload[9]  # Big-endian
            ble_version = payload[1]
            sta_byte = payload[0]
            
            return {
                'product_id': product_id,
                'ble_version': ble_version,
                'sta_byte': sta_byte,
                'mac': ':'.join(f'{b:02X}' for b in payload[2:8]),
                'fw_version': payload[10],
                'led_version': payload[11],
            }
    return None
```

### Step 2: Map Product ID to Effect Command Type

Based on Android source (`com/zengge/wifi/Device/a.java` method `k()`):

```python
def get_effect_command_type(product_id: int) -> str:
    """
    Determine effect command type from product ID.
    
    Returns:
        'none' - No effects supported
        'simple' - 0x61 command (effects 37-56)
        'symphony' - 0x38 Symphony format (5 bytes with checksum)
        'addressable_0x53' - 0x38 format (4 bytes, NO checksum)
        'addressable_0x54' - 0x38/0x39 format (5/9 bytes with checksum)
        'addressable_0x56' - 0x42/0x41/0x73 formats (complex)
        'addressable_0x5b' - 0x38/0x39 format (5/9 bytes with checksum)
    """
    
    # No effects - switches, dimmers, CCT only
    if product_id in [11, 21, 23, 65, 82, 98, 147, 148, 149, 150, 151, 
                      9, 22, 28, 16, 26]:  # Switches, dimmers, CCT
        return 'none'
    
    # Symphony devices (0xA1-0xA9, 0x08)
    if product_id in [161, 162, 163, 164, 166, 167, 169, 8]:
        return 'symphony'
    
    # Addressable LED strips - SPECIAL CASES
    # Product ID 29 (0x1D) - FillLight - maps to sta 0x53
    if product_id == 29:
        return 'addressable_0x53'  # 4 bytes, NO checksum
    
    # Product IDs that likely map to sta 0x54
    # (Based on old Python code: 0x54, 0x55, 0x62)
    if product_id in [84, 98]:  # Downlight_RGBW_0x54, Ctrl_CCT_0x62
        return 'addressable_0x54'  # 5/9 bytes with checksum
    
    # Product IDs that likely map to sta 0x56
    # (Based on old Python code: 0x56, 0x80)
    # Product ID 86 (0x56) - not in Android class list, likely TypeNone
    # But sta byte 0x56 devices exist in old code
    # Need to cross-reference sta byte for unmapped IDs
    
    # Product IDs that likely map to sta 0x5B
    # Product ID 91 (0x5B) - not in Android class list
    # Need to cross-reference sta byte
    
    # Simple RGB devices - use 0x61 command
    if product_id in [4, 6, 20, 26, 27, 33, 38, 39, 51, 68, 72]:
        return 'simple'
    
    # RGBCW/RGBW bulbs and controllers - likely simple effects
    if product_id in [7, 14, 30, 37, 41, 44, 48, 53, 59]:
        return 'simple'
    
    # Unknown/Special devices - need further detection
    return 'unknown'
```

### Step 3: Handle Unknown Product IDs with sta Byte Fallback

For devices where product_id doesn't map clearly (TypeNone class), use sta byte as secondary indicator:

```python
def detect_effect_type_with_fallback(product_id: int, sta_byte: int, ble_version: int) -> str:
    """
    Detect effect command type using product_id first, sta_byte as fallback.
    """
    # Try product_id first
    cmd_type = get_effect_command_type(product_id)
    
    if cmd_type != 'unknown':
        return cmd_type
    
    # Product ID unknown - use sta byte as hint
    # sta byte is the CURRENT DEVICE STATUS, not device type
    # But in practice, certain sta values correlate with device types
    
    if sta_byte == 0x53:
        return 'addressable_0x53'
    elif sta_byte in [0x54, 0x55, 0x62]:
        return 'addressable_0x54'
    elif sta_byte in [0x56, 0x80]:
        return 'addressable_0x56'
    elif sta_byte == 0x5B:
        return 'addressable_0x5b'
    elif sta_byte in [0xA1, 0xA2, 0xA3, 0xA4, 0xA6, 0xA7, 0xA9]:
        return 'symphony'
    
    # Still unknown - query device capabilities
    return 'probe_needed'
```

---

## The Wrong Way: Using sta Byte Alone ❌

**Why the old Python code used sta byte**: The original developer may not have had access to the Android source or understood the manufacturer data format fully. They used sta byte (byte 0) as a simple device type indicator.

**Why this is unreliable**:
1. **sta byte is DEVICE STATUS**, not device type
2. Different product IDs can have same sta byte
3. sta byte can change based on current mode/state
4. No official documentation defines sta byte meanings

**Example of the problem**:
- Product ID 84 (0x54, Downlight_RGBW_0x54)
- Product ID 98 (0x62, Ctrl_CCT_0x62)

Both might show sta byte 0x54 in advertisements, but they're different products with different capabilities!

---

## BLE Version Detection

The **ble_version** field (byte 1) determines command compatibility:

```python
def get_command_version(ble_version: int) -> dict:
    """Determine command format based on BLE version."""
    return {
        'power_command': '0x3B' if ble_version >= 5 else '0x71',
        'supports_state_in_ad': ble_version >= 5,
        'supports_extended_state': ble_version >= 8,
        'supports_modern_features': ble_version >= 11,
    }
```

From Android source (`BaseDeviceInfo.java`):
- `E()` method: returns `true` if `ble_version >= 5`
- `F()` method: returns `true` if `ble_version >= 11`

---

## Complete Detection Flow

```python
class DeviceDetector:
    def __init__(self, advertisement_data):
        self.device_info = self.get_device_info(advertisement_data)
        
        if not self.device_info:
            raise ValueError("Not a LEDnetWF device")
        
        self.product_id = self.device_info['product_id']
        self.ble_version = self.device_info['ble_version']
        self.sta_byte = self.device_info['sta_byte']
        
        # Determine effect command type
        self.effect_type = detect_effect_type_with_fallback(
            self.product_id, 
            self.sta_byte, 
            self.ble_version
        )
        
        # Determine command versions
        self.commands = get_command_version(self.ble_version)
    
    def get_effect_builder(self):
        """Return appropriate effect command builder."""
        if self.effect_type == 'addressable_0x53':
            return build_effect_0x53  # 4 bytes, no checksum
        elif self.effect_type == 'addressable_0x54':
            return build_effect_0x54  # 5/9 bytes with checksum
        elif self.effect_type == 'addressable_0x56':
            return build_effect_0x56  # Multiple formats
        elif self.effect_type == 'addressable_0x5b':
            return build_effect_0x5b  # 5/9 bytes with checksum
        elif self.effect_type == 'symphony':
            return build_effect_symphony  # 5 bytes with checksum
        elif self.effect_type == 'simple':
            return build_effect_simple  # 0x61 command
        else:
            return None
```

---

## Product ID to sta Byte Mapping (Observed)

Based on old Python code and testing, some correlations:

| Product ID | Device Class | sta Byte (observed) | Effect Type |
|------------|--------------|---------------------|-------------|
| 29 (0x1D) | FillLight0x1D | 0x53 | addressable_0x53 |
| 84 (0x54) | Downlight_RGBW_0x54 | 0x54 | addressable_0x54 |
| ??? | ??? | 0x56 | addressable_0x56 |
| ??? | ??? | 0x5B | addressable_0x5b |
| 161-169 (0xA1-0xA9) | Symphony devices | 0xA1-0xA9 | symphony |

**Note**: The sta byte correlation is OBSERVATIONAL, not defined by protocol. Always use product_id as primary indicator.

---

## Capability Probing for Unknown Devices

If both product_id and sta_byte are unknown:

```python
async def probe_device_capabilities(device):
    """
    Query device to determine capabilities.
    
    1. Send state query: [0x81, 0x8A, 0x8B, checksum]
    2. Parse response to determine channels
    3. Try effect command - if device responds, effects supported
    """
    # Send state query
    response = await device.query_state()
    
    # Parse channels from response bytes 6-11
    has_rgb = any(response[6:9])
    has_ww = response[9] > 0
    has_cw = response[11] > 0
    
    # Try simple effect command
    try:
        await device.set_effect_simple(37, 128)  # Effect 37, speed 128
        return 'simple'
    except:
        pass
    
    # Try addressable effect
    try:
        await device.set_effect_addressable(1, 128, 100)
        return 'addressable'
    except:
        pass
    
    return 'none'
```

---

## Instructions for the Other AI

### What to Implement

1. **Parse manufacturer data correctly**:
   - Extract product_id from bytes 8-9 (big-endian)
   - Extract ble_version from byte 1
   - Extract sta_byte from byte 0 (as fallback only)

2. **Use product_id for device detection**:
   - Create mapping: product_id → effect_type
   - Don't rely on sta_byte alone

3. **Store both in device object**:
   ```python
   self._product_id = product_id
   self._ble_version = ble_version
   self._sta_byte = sta_byte  # For debugging/fallback only
   self._effect_type = detect_effect_type(product_id, sta_byte, ble_version)
   ```

4. **Select effect builder based on effect_type**:
   - Not based on sta_byte
   - Use product_id mapping first

### Why This Matters

The old Python code works because:
- Each model file handles ONE specific sta byte
- sta byte happened to correlate with device type
- It was "good enough" but not architecturally correct

The new integration should:
- Use product_id as Android app does
- Fall back to sta_byte for unknown products
- Be ready for new devices with different product_ids

### Testing

When you add a new device:
1. Log: `product_id`, `ble_version`, `sta_byte`
2. Check product_id mapping first
3. If unknown, try sta_byte as hint
4. Test effect commands to confirm type
5. Update mapping table

---

## Summary

| Field | Purpose | Usage |
|-------|---------|-------|
| **product_id** (bytes 8-9) | Device type identifier | **PRIMARY** - Use for capability detection |
| **ble_version** (byte 1) | Protocol version | Determines command format (0x3B vs 0x71) |
| **sta_byte** (byte 0) | Current status | **FALLBACK** - Use only when product_id unknown |

**Always use product_id first, sta_byte as fallback only!**
