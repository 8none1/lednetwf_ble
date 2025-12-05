# JSON-Wrapped BLE Notification Responses

## ⚠️ IMPORTANT UPDATE

**The transport layer type bits (bits 2-3) DO NOT reliably indicate JSON vs binary format!**

See `TRANSPORT_HEADER_TYPE_BITS_ANALYSIS.md` for complete analysis. Type bits are ONLY reliable for filtering ACK packets (type=2). JSON detection must be done by payload inspection, not type bits.

## Overview

Some LEDnetWF BLE devices wrap their notification responses in a JSON structure instead of sending raw binary data. This document explains when JSON wrapping occurs, how to detect it, and how to parse it.

## Message Type Classification (UNRELIABLE - See Warning Above)

The transport layer protocol **defines** three message types in `UpperTransportLayer.java`:

| Type | Constant | Value | Purpose                    |
|------|----------|-------|----------------------------|
| JSON | `JSON`   | 0     | JSON-encoded text payloads |
| HEX  | `HEX`    | 1     | Binary/hex payloads (most common) |
| ACK  | `ACK_PACK` | 2   | Acknowledgment packets (filtered out) |

**However:** Android app does NOT use type 0 vs 1 to detect JSON. Only type=2 is checked (to filter ACKs).

### Type Extraction (For ACK Filtering Only)

Type bits are extracted from **bits 2-3 of byte 0**:

```python
type = (header_byte[0] & 0x0C) >> 2
# Only reliable check: type == 2 (ACK)
```

From `LowerTransportLayerDecoder.java`:
```java
// In getData() method:
UpperTransportLayer upperTransportLayer = new UpperTransportLayer(
    ByteUtil.bitGet(b10, 4) == 1,  // ack flag
    ByteUtil.bitGet(b10, 5) == 1,  // protect flag
    (byte) ((b10 & 12) >> 2),      // TYPE: bits 2-3
    (byte) this.receiveSeq,
    (byte) this.cmdId,
    this.buffer
);
```

### Header Byte Structure

```
Bit Position: 7 6 5 4 3 2 1 0
              | | | | | | | |
              | | | | | +-+-+-- Version (bits 0-1)
              | | | | +-+------ Type (bits 2-3)
              | | | +---------- Ack flag (bit 4)
              | | +------------ Protect flag (bit 5)
              | +-------------- Segmented flag (bit 6)
              +---------------- Reserved (bit 7)
```

## JSON Response Format

### Structure

When `type == 0` (JSON), the payload is a UTF-8 encoded JSON object:

```json
{
  "code": 0,
  "payload": "8133242B231DED00ED000A000F36"
}
```

### Fields

- **`code`**: Integer status code
  - `0` = Success
  - Other values may indicate errors (not fully documented)
  
- **`payload`**: Hex string containing the actual device state response
  - No `0x` prefix
  - Uppercase or lowercase hex characters
  - Same format as raw binary responses (0x81 state response, etc.)

### Alternative JSON Format

Some devices may send complete JSON structures for device info (not state):

```json
{
  "device_id": "...",
  "firmware_version": "...",
  "other_info": {...}
}
```

These should be **ignored** for state parsing. Only process JSON with a hex string `payload` field.

## Detection Method

### Critical Finding

**You CANNOT use type bits to detect JSON vs binary!**

Android app evidence shows:
- Type bits may say type=1 (HEX) when payload is actually JSON
- Android code only checks type==2 to filter ACKs
- No type-based JSON detection in Android app
- Must detect JSON by inspecting payload content

### What Doesn't Work

You **cannot** determine notification format from:
- Type bits in transport header (unreliable!)
- Product ID alone
- BLE version alone
- Manufacturer data

### What Does Work

**Option 1: Payload Inspection** (Modern approach)
1. Filter ACK packets: Check if `(header[0] & 0x0C) >> 2 == 2`
2. Skip 8-byte transport header
3. Check if payload starts with `{` (0x7B)
4. Try UTF-8 decode + JSON parse
5. Fall back to binary if JSON parse fails

**Option 2: Old Python Approach** (Robust, proven)
1. Filter ACK packets only
2. Decode ENTIRE notification (including header) as UTF-8
3. Use `rfind('"')` to find last quote
4. Extract hex string between last two quotes
5. Parse as binary state response

## Implementation Guide

### CORRECT Python Notification Handler (Payload Inspection)

```python
def notification_handler(self, data: bytes) -> dict:
    """Parse notification using CORRECT payload inspection method."""
    
    # Filter ACK packets ONLY (type bits only reliable for this)
    header = data[0]
    type_bits = (header & 0x0C) >> 2
    if type_bits == 2:  # ACK packet
        return None
    
    # Extract payload (skip 8-byte transport header for version 0)
    version = header & 0x03
    if version == 0:
        payload_bytes = data[8:]
    else:
        # Handle version 1 differently if needed
        payload_bytes = data[8:]  # Simplified
    
    # Detect JSON by PAYLOAD CONTENT, not type bits!
    if len(payload_bytes) > 0 and payload_bytes[0] == 0x7B:  # '{'
        try:
            # Decode as UTF-8 string
            notification_str = payload_bytes.decode('utf-8')
            
            # Try parsing as JSON
            import json
            json_data = json.loads(notification_str)
            
            # Extract hex payload
            if isinstance(json_data.get('payload'), str):
                hex_payload = json_data['payload']
                payload_bytes = bytearray.fromhex(hex_payload)
            else:
                # Device info JSON, not state - ignore
                _LOGGER.debug(f"Ignoring non-state JSON: {json_data}")
                return None
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as e:
            _LOGGER.debug(f"Failed to parse as JSON, trying binary: {e}")
            # Fall through to binary parsing
    
    # Parse as binary state response
    return parse_state_response(payload_bytes)
```

### Simplified Approach (Old Code Compatible)

The old Python implementations used a simpler approach that works for both formats:

```python
def notification_handler(self, data: bytes) -> dict:
    """Parse notification with auto-detection of JSON wrapping."""
    
    # Try decoding as UTF-8 first
    notification_str = data.decode('utf-8', errors='ignore')
    
    # Check for JSON format
    if notification_str.strip().startswith('{'):
        try:
            import json
            json_data = json.loads(notification_str)
            if isinstance(json_data.get('payload'), str):
                hex_payload = json_data['payload']
            else:
                return None  # Not a state response
        except json.JSONDecodeError:
            # Fallback to quote extraction
            hex_payload = extract_hex_from_quotes(notification_str)
    else:
        # Extract hex string between quotes
        hex_payload = extract_hex_from_quotes(notification_str)
    
    # Convert to bytes and parse
    payload_bytes = bytearray.fromhex(hex_payload)
    return parse_state_response(payload_bytes)

def extract_hex_from_quotes(text: str) -> str:
    """Extract hex string between last two double quotes."""
    last_quote = text.rfind('"')
    if last_quote > 0:
        first_quote = text.rfind('"', 0, last_quote)
        if first_quote >= 0:
            return text[first_quote+1:last_quote]
    return ""
```

## Device Examples

### Known JSON Devices

From the old Python code, these device types use JSON wrapping:

- **model_0x53** (FillLight 0x1D): Always uses JSON wrapping
- **model_0x54**: May use JSON wrapping (checks for `{` prefix)
- **model_0x5b**: Uses JSON wrapping with quote extraction

### Known Binary Devices

- **model_0x56**: Pure binary, no JSON wrapping

## Android Implementation

### ZGHBReceiveCallback (Binary Path)

Most devices use the binary notification path:

```java
public void onCharacteristicChanged(UUID uuid, byte[] bArr) {
    UpperTransportLayer transport = this.decoder.getTransport(bArr);
    if (transport == null || transport.getType() == 2) {
        return;  // Skip null and ACK packets
    }
    // Type checking happens here but typically == 1 (HEX)
    this.handler.postSubscriber(transport.getCmdId(), transport.getPayload(), this.baseDevice);
}
```

### z2.f (JSON Path)

WiFi provisioning and some device setup uses JSON:

```java
private void onNotificationReceived(UpperTransportLayer transport) {
    Type typeB = gVar.b();
    // Convert payload to UTF-8 string
    String str = new String(transport.getPayload(), StandardCharsets.UTF_8);
    Log.i(TAG, " JSON " + str);
    // Parse as JSON using Gson
    gVar.a().a(cmdId, gson.fromJson(str, typeB), null);
}
```

### Flutter/BLE State Upload

```java
String strE = (String) ((Result) gson.fromJson(
    new String(bArr, StandardCharsets.UTF_8), 
    new TypeToken<Result<String>>(){}.getType()
)).getPayload();
```

Where `Result` is:
```java
public class Result<T> {
    private int code;
    private T payload;
    // getters/setters
}
```

## Key Insights

1. **Message type is per-notification, not per-device**
   - Same device may send different types for different responses
   - Must check type bits on every notification

2. **JSON is less common**
   - Most LED state responses are binary (type=1)
   - JSON typically used for WiFi provisioning, device info
   - Some older/specific devices always use JSON

3. **Simplified detection works**
   - Old Python code didn't check type bits
   - Simply tried UTF-8 decode + JSON parse first
   - Fallback to binary if JSON fails
   - This approach is more forgiving and works for all devices

4. **Quote extraction is fallback**
   - Very old format: just `"hex_string"` in UTF-8
   - Newer format: `{"code":0,"payload":"hex_string"}`
   - Both can be handled with quote extraction fallback

## Recommendations

### For New Implementations

1. **Use transport layer type detection**
   ```python
   type_bits = (data[0] & 0x0C) >> 2
   ```

2. **Handle all three types**
   - Type 0: JSON unwrap
   - Type 1: Direct binary
   - Type 2: Skip (ACK)

3. **Robust JSON parsing**
   - Check for `{` prefix
   - Validate `payload` is string (not nested object)
   - Fallback to quote extraction for old format

### For Backward Compatibility

Use the simplified approach from old Python code:
- UTF-8 decode first
- Check for JSON with `{` prefix
- Extract hex from quotes as fallback
- Validate hex before parsing

This approach works with all known device types without needing transport layer type detection.

## Related Documents

- `06_transport_layer_protocol.md` - Transport layer structure
- `08_state_query_response_parsing.md` - State response format (0x81)
- Model implementations:
  - `model_0x53.py` - JSON with quote extraction
  - `model_0x54.py` - JSON detection with fallback
  - `model_0x56.py` - Pure binary

## Example Traces

### JSON Response (Type 0)

Raw notification (59 bytes):
```
00 00 80 00 00 2F 30 0A 7B 22 63 6F 64 65 22 3A 30 2C 22 70 61 79 6C 6F 61 64 22 3A 22 38 31 33 33 32 34 32 42 32 33 31 44 45 44 30 30 45 44 30 30 30 41 30 30 30 46 33 36 22 7D
```

Breakdown:
- Bytes 0-7: Transport header
  - `00`: Header (version 0, type 0=JSON, not segmented)
  - `00`: Sequence
  - `80 00`: Frag control (single segment)
  - `00 2F`: Total length (47 bytes)
  - `30`: Payload length + 1
  - `0A`: Command ID (10 = with response)
- Bytes 8-58: Payload (UTF-8 JSON)
  ```
  {"code":0,"payload":"8133242B231DED00ED000A000F36"}
  ```

Extracted state:
```
81 33 24 2B 23 1D ED 00 ED 00 0A 00 0F 36
```

### Binary Response (Type 1)

Raw notification (23 bytes):
```
04 00 80 00 00 0E 0F 0A 81 33 24 2B 23 1D ED 00 ED 00 0A 00 0F 36
```

Breakdown:
- Bytes 0-7: Transport header
  - `04`: Header (version 0, type 1=HEX, ack=true)
  - `00`: Sequence
  - `80 00`: Frag control
  - `00 0E`: Total length (14 bytes)
  - `0F`: Payload length + 1
  - `0A`: Command ID
- Bytes 8-22: Direct binary state response
  ```
  81 33 24 2B 23 1D ED 00 ED 00 0A 00 0F 36
  ```

## Summary - CORRECTED

### Critical Corrections

- **Type bits (2-3) DO NOT reliably indicate JSON vs binary format**
- **Type bits ONLY reliable for filtering ACK packets (type=2)**
- **Android app does NOT check type 0 vs 1 for format detection**
- **Must detect JSON by inspecting payload content, not type bits**

### Correct Detection Strategy

**DO:**
- Filter ACK packets: Check if `(header[0] & 0x0C) >> 2 == 2`
- Detect JSON by checking if payload starts with `{` (0x7B)
- Try UTF-8 decode + JSON parse on suspected JSON payloads
- Use old Python's robust approach (decode full notification, extract from quotes)

**DON'T:**
- Trust type bits to indicate JSON vs binary
- Make parsing decisions based on type 0 vs 1
- Assume type bits match payload format

### Why This Matters

Observed in practice: Header byte `0x04` (type=1, supposedly binary) with JSON payload starting with `{`. Android app handles this correctly because it doesn't trust type bits for format detection.

See `TRANSPORT_HEADER_TYPE_BITS_ANALYSIS.md` for complete evidence and analysis.
