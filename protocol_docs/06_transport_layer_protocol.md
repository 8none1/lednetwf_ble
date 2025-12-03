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

## Response Message Types

The protocol supports three message types (from UpperTransportLayer.java):

| Type | Constant | Purpose                    |
|------|----------|----------------------------|
| 0    | JSON     | JSON-encoded text payloads |
| 1    | HEX      | Binary/hex payloads        |
| 2    | ACK_PACK | Acknowledgment packets     |

Type is extracted from bits 2-3 of first byte: `(byte[0] & 0x0C) >> 2`

**For BLE-only LED controllers, virtually all responses are Binary (Type 1).**

ACK packets (Type 2) are filtered out in ZGHBReceiveCallback.java:
```java
if (transport.getType() == 2) return;  // Skip ACKs
```

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
