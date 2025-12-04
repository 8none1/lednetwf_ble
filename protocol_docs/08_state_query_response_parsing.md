# STATE QUERY AND RESPONSE PARSING

## State Query Command (0x81)

Format (4 bytes):

| Byte | Field           | Value                           |
|------|-----------------|----------------------------------|
| 0    | Command opcode  | 0x81                             |
| 1    | Sub-command 1   | 0x8A                             |
| 2    | Sub-command 2   | 0x8B                             |
| 3    | Checksum        | 0x40                             |

Command: `[0x81, 0x8A, 0x8B, 0x40]`

## State Response Format (14 bytes)

Source: tc/b.java method c() lines 47-62

| Byte | Field           | Description                      |
|------|-----------------|----------------------------------|
| 0    | Header          | 0x81 (response identifier)       |
| 1    | Mode            | Current mode (0-255)             |
| 2    | Power State     | 0x23 = ON, other = OFF           |
| 3    | Mode Type       | 97/98/99 = static, other = effect|
| 4    | Speed           | Effect speed (0-255)             |
| 5    | Value1          | Device-specific                  |
| 6    | Red (R)         | Red channel (0-255)              |
| 7    | Green (G)       | Green channel (0-255)            |
| 8    | Blue (B)        | Blue channel (0-255)             |
| 9    | Warm White (WW) | Warm white (0-255)               |
| 10   | Brightness      | Overall brightness (0-255)       |
| 11   | Cool White (CW) | Cool white (0-255)               |
| 12   | Reserved        | Device-specific                  |
| 13   | Checksum        | Sum of bytes 0-12 mod 256        |

## Python Response Parser

```python
def parse_state_response(response: bytes) -> dict:
    if len(response) < 14 or response[0] != 0x81:
        return None

    # Verify checksum
    if sum(response[:13]) & 0xFF != response[13]:
        return None

    return {
        'power_on': response[2] == 0x23,
        'mode': response[1],
        'mode_type': response[3],
        'speed': response[4],
        'red': response[6],
        'green': response[7],
        'blue': response[8],
        'warm_white': response[9],
        'brightness': response[10],
        'cool_white': response[11],
    }
```

## State in Manufacturer Data (Alternative Method)

Some devices broadcast their current state in BLE advertisement manufacturer data,
which can be read passively without connecting. This is useful for:
- Quick status checks without connection overhead
- Devices where BLE stack issues prevent receiving notifications
- Real-time state monitoring via advertisement scanning

State is embedded in the BLE advertisement:

| Byte | Field             | Description                      |
|------|-------------------|----------------------------------|
| 14   | Power State       | 0x23 = ON, 0x24 = OFF            |
| 15   | Mode              | 0x61 = color/white, 0x25 = effect|
| 16   | Sub-mode          | 0xF0 = RGB, 0x0F = white, effect#|
| 17   | Brightness (white)| Brightness 0-100 (white mode)    |
| 18   | Red               | Red channel 0-255                |
| 19   | Green             | Green channel 0-255              |
| 20   | Blue              | Blue channel 0-255               |
| 21   | Color Temp        | Color temperature 0-100          |

### Detection Strategy for Unknown Devices

When probing a new device:

1. Try sending the standard state query (0x81, 0x8A, 0x8B, checksum)
2. Wait up to 3 seconds for a notification response
3. If no response:
   - Check if state_data is present in manufacturer data advertisement
   - Parse state from manufacturer data bytes 14-24
   - Use product_id and sta byte to determine capabilities
4. Commands (color, power, effects) may still work even if state queries don't

### Java Source Reference

FillLight0x1D.java (com/zengge/wifi/Device/Type/):

- This is a "stub" device class with all methods returning null/0/false
- Product ID 0x1D = 29 (decimal)
- The Java app doesn't fully support this device type
- Control commands still work via BaseDeviceInfo inheritance
