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
