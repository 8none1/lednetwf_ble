# Transport Header Type Bits - Discrepancy Analysis

## The Problem

We observed a discrepancy between the transport layer header type bits and the actual payload format:

**Observed Example:**
```
Full notification: 04 16 81 7B 22 63 6F 64 65 22 3A 30 2C 22 70 61 79 6C 6F 61 64 22 3A 22 38 31 ...
                   │  │  │  └─ Start of JSON: 0x7B = '{'
                   └─ Header byte: 0x04
```

**Analysis of 0x04 header:**
```
0x04 = 0000 0100 binary

Bit 0-1 (version): 00 = version 0
Bit 2-3 (type):    01 = type 1 (HEX/binary) ← Says binary!
Bit 4 (ack):       0 = no ack
Bit 5 (protect):   0 = no protect  
Bit 6 (segment):   0 = not segmented
```

**But the actual payload after transport header is JSON:**
```
Bytes after header: 7B 22 63 6F 64 65 22 3A 30 2C 22 70 61 79 6C 6F 61 64 22 3A 22 38 31 ...
Decoded:            {"code":0,"payload":"81..."}
```

**Type bits say HEX (binary), payload is actually JSON!**

## Investigation Findings

### Android Code Analysis

#### Two Transport Layer Decoders

There are **two different** `LowerTransportLayerDecoder` implementations:

1. **com.zengge.hagallbjarkan.protocol.zgble.LowerTransportLayerDecoder**
   - Full-featured decoder
   - **DOES extract type bits**: `(byte) ((b10 & 12) >> 2)`
   - Used by newer ZGHBReceiveCallback

2. **com.example.blelibrary.protocol.layer.LowerTransportLayerDecoder**
   - Simplified decoder
   - **DOES NOT extract type bits** - UpperTransportLayer has no type field
   - Used by z2.f (WiFi provisioning)

#### Type Bit Usage

Searched for `getType()` checks in Android code:

**Finding: Type bits are ONLY used to filter ACK packets (type=2)**

```java
// ZGHBReceiveCallback.java line 24
if (transport == null || transport.getType() == 2) {
    return;  // Filter out ACK packets
}
this.handler.postSubscriber(transport.getCmdId(), transport.getPayload(), this.baseDevice);
```

**NEVER checks type == 0 vs type == 1** to decide JSON vs binary parsing!

#### z2.f WiFi Provisioning Handler

This handler **always** treats payloads as JSON:

```java
// z2/f.java line 95-97
String str = new String(upperTransportLayer.getPayload(), StandardCharsets.UTF_8);
Log.i(f.f43409r, " JSON " + str);
gVar.a().a(i10, f.this.f43410a.m(str, typeB), null);  // Parse as JSON with Gson
```

**No type checking at all** - assumes everything is JSON.

Uses `com.example.blelibrary` decoder which doesn't even have type field.

### Old Python Code Analysis

The old Python implementation **completely ignores** the transport header:

```python
# model_0x53.py line 313
def notification_handler(self, data):
    notification_data = data.decode("utf-8", errors="ignore")
    # Extract hex string between last two quotes
    last_quote = notification_data.rfind('"')
    first_quote = notification_data.rfind('"', 0, last_quote)
    payload = notification_data[first_quote+1:last_quote]
```

**Key insight:** It decodes the **entire notification** including transport header as UTF-8!

Example with your packet:
```
Raw bytes: 04 16 81 7B 22 63 6F 64 65 22 3A 30 2C 22 70 61 79 6C 6F 61 64 22 3A 22 38 31 33 33 ...

As UTF-8: <EOT><SYN><junk>{"code":0,"payload":"8133..."}

rfind('"') finds the LAST quote in the JSON
rfind('"', 0, last) finds the quote before it
Result: Extracts "8133..." from between the quotes
```

**The old code accidentally works** because `rfind('"')` skips all the transport header junk and finds the hex string inside the JSON payload!

## The Truth About Type Bits

### Transport Header Type Field

The type bits (bits 2-3 of byte 0) **are defined** in the protocol:

```java
// UpperTransportLayer.java
public static final byte ACK_PACK = 2;
public static final byte HEX = 1;
public static final byte JSON = 0;
```

Extraction:
```java
(byte) ((headerByte & 0x0C) >> 2)  // Bits 2-3
```

### But Android Code Doesn't Use Them!

**Critical Finding:** The Android app **DOES NOT** check type bits to determine JSON vs binary parsing.

Instead:
1. **Filters ACK packets** (type=2) only
2. **Always tries UTF-8 decode + JSON parse** in provisioning path (z2.f)
3. **Passes raw payload** to handlers in device control path (ZGHBReceiveCallback)
4. **Handlers decide** based on cmdId or other context

### Why Type Bits Don't Match Payload

Possible explanations:

1. **Type bits may indicate command format, not response format**
   - Commands sent TO device use one format
   - Responses FROM device may use different format
   - Type bits describe what was SENT, not what will be RECEIVED

2. **Type bits may be unreliable/unused in practice**
   - Defined in spec but not enforced
   - Implementations don't trust them
   - Default to safe parsing (try JSON, fall back to binary)

3. **Type bits may have different meaning for responses**
   - Documentation describes command direction
   - Response direction may use different encoding

4. **Firmware variations**
   - Different device firmware versions
   - Inconsistent implementation
   - Android app handles all variants

## How Parsing Actually Works

### z2.f Path (WiFi Provisioning)

```
1. Receive notification bytes
2. Extract payload from transport layer (skip 8-byte header)
3. Convert payload to UTF-8 string
4. Parse as JSON using Gson
5. Extract hex from JSON "payload" field
```

Uses JSON **always**, ignores type bits.

### ZGHBReceiveCallback Path (Device Control)

```
1. Receive notification bytes
2. Decode transport layer
3. Filter if type == 2 (ACK)
4. Pass payload to handler
5. Handler decides how to parse (usually binary 0x81 response)
```

Only filters ACKs, passes everything else as-is.

### Old Python Path

```
1. Receive entire notification (including transport header)
2. Decode full bytes as UTF-8 (with errors='ignore')
3. Use rfind('"') to find quotes in resulting string
4. Extract hex string between quotes
5. Convert hex to bytes
6. Parse as binary state response
```

Works by accident - skips junk, finds JSON, extracts hex.

## Correct Implementation Strategy

### Don't Trust Type Bits for JSON Detection

**DO NOT** use bits 2-3 to determine if payload is JSON or binary.

**Instead:**

1. **Skip transport header** (8 bytes for version 0)
2. **Try to detect JSON** by checking payload content:
   ```python
   # Check if payload starts with printable ASCII/JSON chars
   if payload_bytes[0] == 0x7B:  # '{'
       # Try JSON parse
   elif all(32 <= b < 127 for b in payload_bytes[:4]):
       # Might be JSON, try decode + parse
   else:
       # Binary payload
   ```

3. **Or use old Python approach** (decode full notification, extract from quotes)

### Filter ACK Packets

**DO** check type == 2 to filter acknowledgments:

```python
type_bits = (header_byte[0] & 0x0C) >> 2
if type_bits == 2:
    return None  # Skip ACK
```

### Payload Detection Example

```python
def parse_notification(data: bytes) -> dict:
    """Parse notification with proper type detection."""
    
    # Check transport header version
    header = data[0]
    version = header & 0x03
    
    if version == 0:
        # Version 0: 8-byte header
        type_bits = (header & 0x0C) >> 2
        
        # Filter ACKs
        if type_bits == 2:
            return None
        
        # Extract payload (skip 8-byte header)
        payload = data[8:]
        
    elif version == 1:
        # Version 1: different format (see getTransportV1)
        # Implementation depends on version 1 spec
        pass
    
    # Try JSON detection
    if len(payload) > 0 and payload[0] == 0x7B:  # '{'
        try:
            # Decode as UTF-8 JSON
            json_str = payload.decode('utf-8')
            json_data = json.loads(json_str)
            
            # Extract hex from "payload" field
            if 'payload' in json_data and isinstance(json_data['payload'], str):
                hex_str = json_data['payload']
                state_bytes = bytearray.fromhex(hex_str)
                return parse_state_response(state_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    
    # Try old Python approach (full notification decode)
    try:
        full_str = data.decode('utf-8', errors='ignore')
        last_quote = full_str.rfind('"')
        if last_quote > 0:
            first_quote = full_str.rfind('"', 0, last_quote)
            if first_quote >= 0:
                hex_str = full_str[first_quote+1:last_quote]
                if all(c in '0123456789abcdefABCDEF' for c in hex_str):
                    state_bytes = bytearray.fromhex(hex_str)
                    return parse_state_response(state_bytes)
    except:
        pass
    
    # Fall back to binary parsing
    return parse_state_response(payload)
```

## Summary

### Key Findings

1. **Type bits (2-3) DO NOT reliably indicate JSON vs binary**
   - Header may say type=1 (HEX) when payload is JSON
   - Android code does not trust these bits for format detection

2. **Type bits ONLY used to filter ACK packets (type=2)**
   - Android code: `if (transport.getType() == 2) return;`
   - This is the ONLY type bit usage in Android

3. **Android uses context-based parsing**
   - z2.f WiFi path: Always parse as JSON
   - ZGHBReceiveCallback: Pass binary to handlers
   - No decision based on type bits

4. **Old Python code ignores transport header completely**
   - Decodes full notification as UTF-8
   - Extracts hex from quotes using rfind()
   - Works by accident but is robust

### Recommendations

**For new implementations:**

1. **Filter ACK packets** by checking type == 2
2. **Detect JSON by payload inspection**, not type bits:
   - Check for `{` at start
   - Try UTF-8 decode + JSON parse
   - Fall back to binary
3. **Or use old Python approach** (decode full notification, extract from quotes)
4. **Don't trust type bits for format detection**

**Update documentation:**

The previous `JSON_WRAPPED_NOTIFICATION_RESPONSES.md` document incorrectly stated that type bits determine JSON vs binary format. This needs correction to reflect that:
- Type bits are ONLY reliable for filtering ACKs (type=2)
- JSON detection must be done by payload inspection
- Header type field may not match actual payload format

## Related Files

- Android decoders:
  - `com/zengge/hagallbjarkan/protocol/zgble/LowerTransportLayerDecoder.java` (has type)
  - `com/example/blelibrary/protocol/layer/LowerTransportLayerDecoder.java` (no type)
- Handlers:
  - `com/zengge/hagallbjarkan/handler/zghb/ZGHBReceiveCallback.java` (filters ACK only)
  - `z2/f.java` (always JSON, no type check)
- Old Python:
  - `custom_components/lednetwf_ble/models/model_0x53.py` (quote extraction)
  - `custom_components/lednetwf_ble/lednetwf.py` (passes full notification)
