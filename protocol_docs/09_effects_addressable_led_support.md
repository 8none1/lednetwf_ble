# EFFECTS AND ADDRESSABLE LED SUPPORT

## Effect Count by Device Type

Effects are hardcoded in the app, NOT queried from devices.

| Device Type                      | Effect Range | Total |
|----------------------------------|--------------|-------|
| Ctrl_Mini_RGB_Symphony_0xa1      | 1-100        | 100   |
| Ctrl_Mini_RGB_Symphony_new_0xa6  | 1-227        | 227   |
| Ctrl_Mini_RGB_Symphony_new_0xA9  | 1-131        | 131   |
| Other Symphony devices           | 1-100        | 100   |
| Non-Symphony devices (e.g., 0x33)| N/A          | 0     |

## Addressable vs Global-Color LEDs

- **Symphony/Digital families** (productIds 161-169, 209) = addressable LEDs
- **Plain RGB/RGBW/RGBCW/CCT classes** = global color (entire strip changes)

### Detection

If productId in Symphony/Digital family → addressable.
Verify by sending effect command and observing response.

## Segment/Addressable LED Detection

### Method 1: Product ID Lookup

Symphony devices (0xA1-0xA9) and Digital Light (0xD1) support addressable LEDs:

| Product ID | Name                             | Segments | IC Config |
|------------|----------------------------------|----------|-----------|
| 0xA1 (161) | Ctrl_Mini_RGB_Symphony_0xa1      | Yes      | Yes       |
| 0xA2 (162) | Ctrl_Mini_RGB_Symphony_new_0xa2  | Yes      | Yes       |
| 0xA3 (163) | Ctrl_Mini_RGB_Symphony_new_0xA3  | Yes      | Yes       |
| 0xA4 (164) | Ctrl_Mini_RGB_Symphony_new_0xA4  | Yes      | Yes       |
| 0xA6 (166) | Ctrl_Mini_RGB_Symphony_new_0xA6  | Yes      | Yes       |
| 0xA7 (167) | Ctrl_Mini_RGB_Symphony_new_0xA7  | Yes      | Yes       |
| 0xA9 (169) | Ctrl_Mini_RGB_Symphony_new_0xA9  | Yes      | Yes       |
| 0xD1 (209) | Digital_Light_0xd1               | Yes      | No        |

### Method 2: LED Settings Response (0x63)

The most reliable way to detect addressable LED support is to query LED settings
and check for a valid 0x63 response.

Source: tc/b.java method g() lines 180-195

#### Query Command

```text
[0x62, 0x6A, 0x6B, persist, checksum]
```

Wrapped: `00 02 80 00 00 05 06 0a 63 12 21 f0 86`

#### Response Format (0x63)

If the device supports addressable LEDs, it responds with:

| Byte | Field          | Description                              |
|------|----------------|------------------------------------------|
| 0    | Header         | 0x63                                     |
| 1-2  | LED Count      | Big-endian 16-bit LED count              |
| 3    | IC Type        | Chip type code (see table below)         |
| 4    | Color Order    | RGB color order code                     |
| 5    | Param D        | Timing parameter                         |
| 6    | Param E        | Timing parameter                         |
| 7    | Param F        | Timing parameter                         |
| 8-9  | Frequency      | Big-endian 16-bit refresh frequency (Hz) |
| 10   | Unknown        | Reserved                                 |
| 11   | Checksum       | Sum of bytes 0-10                        |

#### IC Chip Types

Source: dd/i.java methods k(), l(), m()

| Code | Chip Name   | Notes                            |
|------|-------------|----------------------------------|
| 1    | UCS1903     | Slower timing                    |
| 2    | SM16703     | Fast timing                      |
| 3    | WS2811      | 12V external IC                  |
| 4    | WS2812B     | Most common 5V integrated        |
| 5    | SK6812      | Compatible with WS2812B          |
| 6    | INK1003     | Alternative IC                   |
| 7    | WS2801      | SPI-based, 2 data lines          |
| 8    | WS2815      | 12V with backup data line        |
| 9    | APA102      | SPI-based, high speed            |
| 10   | TM1914      | Alternative IC                   |
| 11   | UCS2904B    | Higher current support           |

#### Color Order Codes

| Code | Order |
|------|-------|
| 0    | RGB   |
| 1    | RBG   |
| 2    | GRB   |
| 3    | GBR   |
| 4    | BRG   |
| 5    | BGR   |

### Detection Logic

```python
def has_segment_support(product_id: int, led_settings_response: bytes) -> bool:
    """
    Determine if device supports addressable LED segments.
    
    1. Check product ID for Symphony/Digital device types
    2. If unknown product ID, query LED settings (0x62 command)
    3. Valid 0x63 response confirms addressable LED support
    """
    # Known Symphony product IDs
    symphony_ids = {161, 162, 163, 164, 166, 167, 169, 209}
    
    if product_id in symphony_ids:
        return True
    
    # Check for valid 0x63 response
    if led_settings_response and len(led_settings_response) >= 12:
        if led_settings_response[0] == 0x63:
            # Verify checksum
            expected = sum(led_settings_response[:11]) & 0xFF
            actual = led_settings_response[11]
            return expected == actual
    
    return False
```

## 16-Segment Strip View

Symphony devices display a 16-segment preview in the app (StripView class).
This is UI only - the actual LED count is configurable via the 0x62 set command.

Source: com/zengge/wifi/activity/NewSymphony/view/StripView.java

## Setting LED Configuration (0x62)

To configure LED strip settings:

Source: tc/b.java methods B(), C(), E()

### Set LED Count and IC Type

```text
[0x62, count_hi, count_lo, icType, colorOrder, param_d, param_e, param_f, freq_hi, freq_lo, unknown, persist, checksum]
```

Example: Set 150 LEDs, WS2812B, GRB order:
```text
[0x62, 0x00, 0x96, 0x04, 0x02, ...]
```
