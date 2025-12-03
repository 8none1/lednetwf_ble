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
