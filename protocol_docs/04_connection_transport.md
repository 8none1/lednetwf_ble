# Connection and Transport Layer

## BLE Connection Sequence

1. Discover device via BLE scanning (filter by name)
2. Initiate GATT connection: `bluetoothDevice.connectGatt()`
3. Wait for `onConnectionStateChange` with `STATE_CONNECTED`
4. Call `gatt.discoverServices()`
5. Wait for `onServicesDiscovered`
6. Enable notifications on notify characteristic (CCCD)
7. Request MTU (512 if bleVersion >= 8, else 255)
8. Device ready for commands

## Notification Enable (CCCD)

The `01 00` bytes seen in Wireshark are the standard BLE CCCD value, NOT a protocol command.

**CCCD UUID**: `00002902-0000-1000-8000-00805f9b34fb`

| Value | Meaning |
|-------|---------|
| 01 00 | Enable notifications |
| 02 00 | Enable indications |
| 00 00 | Disable |

Most BLE libraries handle this automatically when subscribing to notifications.

---

## Transport Layer Protocol

**All commands MUST be wrapped in the transport layer. Raw command bytes will NOT work.**

### Packet Format (Version 0)

Single-segment packet (most common):

| Byte | Field | Description |
|------|-------|-------------|
| 0 | Header | Flags: bits[0-1]=version, bit[6]=segmented |
| 1 | Sequence | Packet sequence number (0-255) |
| 2-3 | Frag Control | 0x8000 = single complete segment |
| 4-5 | Total Length | Total payload length (big-endian) |
| 6 | Payload Length | Length of payload + 1 (for cmdId) |
| 7 | cmdId | 10=expects response, 11=no response |
| 8+ | Payload | Actual LED command data |

### Header Byte Structure

```
Bit Position: 7 6 5 4 3 2 1 0
              │ │ │ │ │ └─┴─── Version (bits 0-1): 00=v0
              │ │ │ │ └─┴───── Type (bits 2-3): 0=JSON, 1=HEX, 2=ACK
              │ │ │ └───────── Ack flag (bit 4): 1=expects ack
              │ │ └─────────── Protect flag (bit 5): 1=protected
              │ └───────────── Segmented (bit 6): 1=multi-segment
              └─────────────── Reserved (bit 7)
```

### Response Message Types

| Type | Purpose | Notes |
|------|---------|-------|
| 0 | JSON | JSON-encoded payloads |
| 1 | HEX | Binary payloads |
| 2 | ACK | Acknowledgment (filtered out) |

**Warning**: Type bits are unreliable for JSON detection. Only type=2 (ACK) is reliably used.
Detect JSON by inspecting payload for `{` (0x7B) or `[` (0x5B).

---

## JSON-Wrapped Responses

Some devices wrap responses in JSON:

```json
{"code": 0, "payload": "8133242B231DED00ED000A000F36"}
```

- **`code`**: Status (0 = success)
- **`payload`**: Hex string of actual response (parse as binary)

### Detection and Parsing

```python
def parse_notification(data: bytes) -> bytes:
    """Parse notification, handling both binary and JSON formats."""
    if len(data) < 8:
        return None

    payload = data[8:]  # Skip transport header

    # Check if payload starts with JSON
    if payload and payload[0] in (0x7B, 0x5B):  # '{' or '['
        try:
            import json
            json_obj = json.loads(payload.decode('utf-8', errors='ignore'))
            if 'payload' in json_obj:
                return bytes.fromhex(json_obj['payload'])
        except:
            pass

    return payload  # Binary format
```

---

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

### Example

Command `[0x81, 0x8A, 0x8B, 0x40]` (state query) with seq=1, expect_response=True:

```
Transport: 00 01 80 00 00 04 05 0A 81 8A 8B 40
           │  │  │     │     │  │  └─────────── Payload
           │  │  │     │     │  └───────────── cmdId=10 (expects response)
           │  │  │     │     └─────────────── payload_len+1 = 5
           │  │  │     └───────────────────── total_len = 4
           │  │  └─────────────────────────── frag_ctrl = 0x8000
           │  └────────────────────────────── seq = 1
           └───────────────────────────────── header = 0x00
```
