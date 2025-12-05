# TRANSPORT LAYER PROTOCOL

## Overview

All commands MUST be wrapped in the transport layer. Raw command bytes will NOT work.

## Upper Transport Layer Structure

```python
@dataclass
class UpperTransportLayer:
    ack: bool           # True if response expected
    protect: bool       # False for normal commands
    seq: int            # Sequence number (0-255)
    cmd_id: int         # 10=with response, 11=no response
    payload: bytes      # Raw command bytes
```

## Lower Transport Layer Packet Format (Version 0)

Single-segment packet (most common):

| Byte | Field           | Description                              |
|------|-----------------|------------------------------------------|
| 0    | Header          | Flags: bits[0-1]=version, bit[6]=segmented|
| 1    | Sequence        | Packet sequence number (0-255)           |
| 2-3  | Frag Control    | 0x8000 = single complete segment         |
| 4-5  | Total Length    | Total payload length (big-endian)        |
| 6    | Payload Length  | Length of payload + 1 (for cmdId)        |
| 7    | cmdId           | 10=expects response, 11=no response      |
| 8+   | Payload         | Actual LED command data                  |

## Header Byte Structure

The first byte contains flags and version information:

```
Bit Position: 7 6 5 4 3 2 1 0
              | | | | | | | |
              | | | | | +-+-+-- Version (bits 0-1): 00=v0, 01=v1
              | | | | +-+------ Type (bits 2-3): See below
              | | | +---------- Ack flag (bit 4): 1=expects ack
              | | +------------ Protect flag (bit 5): 1=protected
              | +-------------- Segmented (bit 6): 1=multi-segment
              +---------------- Reserved (bit 7)
```

Type extraction: `type = (header_byte[0] & 0x0C) >> 2`

## Response Message Types

The protocol defines three message types (from UpperTransportLayer.java):

| Type | Constant | Purpose                    |
|------|----------|----------------------------|
| 0    | JSON     | JSON-encoded text payloads |
| 1    | HEX      | Binary/hex payloads        |
| 2    | ACK_PACK | Acknowledgment packets     |

### ⚠️ IMPORTANT: Type Bits Unreliable for JSON Detection

**The type bits (bits 2-3) do NOT reliably indicate JSON vs binary format!**

- **Only type=2 (ACK) is reliably checked** by the Android app to filter ACK packets
- **Type 0 vs 1 distinction is NOT used** for JSON vs binary detection
- JSON detection must be done by **payload inspection**, not type bits

Evidence from Android source:
```java
// ZGHBReceiveCallback.java - ONLY checks for ACK (type=2)
if (transport == null || transport.getType() == 2) {
    return;  // Filter out ACK packets only
}
// Never checks type 0 vs 1 for JSON detection!
```

ACK packets (Type 2) are filtered out:
```java
if (transport.getType() == 2) return;  // Skip ACKs
```

## JSON-Wrapped Responses

### When JSON Wrapping Occurs

Some devices (particularly during WiFi provisioning or certain models) wrap responses in JSON:

```json
{
  "code": 0,
  "payload": "8133242B231DED00ED000A000F36"
}
```

### JSON Response Structure

- **`code`**: Integer status code (0 = success)
- **`payload`**: Hex string containing actual device response (no `0x` prefix)
  - Same format as raw binary responses
  - Can be converted to bytes and parsed normally

### Detecting JSON Responses

**Do NOT rely on type bits!** Instead, inspect the payload:

```python
def parse_notification(data: bytes) -> bytes:
    """
    Parse notification, handling both binary and JSON-wrapped formats.
    
    Args:
        data: Complete notification data (including transport header)
    
    Returns:
        Parsed payload bytes
    """
    # Skip transport header (typically 8 bytes for single-segment)
    # Header format: [flags, seq, frag_hi, frag_lo, len_hi, len_lo, payload_len, cmd_id]
    
    if len(data) < 8:
        return None
    
    payload_start = 8
    payload = data[payload_start:]
    
    # Check if payload starts with JSON
    if payload and payload[0] in (0x7B, 0x5B):  # '{' or '['
        try:
            # Try to decode as UTF-8 JSON
            json_str = payload.decode('utf-8', errors='ignore')
            import json
            json_obj = json.loads(json_str)
            
            # Extract hex payload string
            if 'payload' in json_obj:
                hex_str = json_obj['payload']
                # Convert hex string to bytes
                return bytes.fromhex(hex_str)
        except:
            pass
    
    # Return as-is (binary format)
    return payload
```

### Example: JSON-Wrapped State Response

**Raw notification:**
```
04 16 81 7B 22 63 6F 64 65 22 3A 30 2C 22 70 61 79 6C 6F 61 64 22 3A 22 38 31 33 33 ...
│  │  │  └─ JSON starts here: 0x7B = '{'
│  │  └─ cmd_id: 0x81 (but this is NOT the state response header!)
│  └─ seq: 0x16
└─ header: 0x04 (version=0, type=1 ← Says binary but contains JSON!)
```

**JSON payload (after transport header):**
```json
{"code":0,"payload":"8133242B231DED00ED000A000F36"}
```

**Extracted hex payload:**
```
81 33 24 2B 23 1D ED 00 ED 00 0A 00 0F 36
└─ Actual state response (0x81 header)
```

**Parse as normal binary state response** - see file 08 for format.

## Python Transport Layer Encoder

```python
def encode_transport_v0(cmd_bytes: bytes, seq: int, expect_response: bool) -> bytes:
    """Wrap command bytes in transport layer."""
    cmd_id = 10 if expect_response else 11
    payload_len = len(cmd_bytes)

    packet = bytearray(8 + payload_len)
    packet[0] = 0x00  # Header (version 0, not segmented)
    packet[1] = seq & 0xFF
    packet[2] = 0x80  # Frag control high
    packet[3] = 0x00  # Frag control low
    packet[4] = (payload_len >> 8) & 0xFF
    packet[5] = payload_len & 0xFF
    packet[6] = (payload_len + 1) & 0xFF
    packet[7] = cmd_id
    packet[8:] = cmd_bytes

    return bytes(packet)
```
