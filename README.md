# LEDnetWF_ble

Home Assistant custom integration for LEDnetWF devices which use the Zengge Android or iPhone app. WIP

## Important note for upgraders

If, after upgrading, your devices suddenly don't work, please delete them via the UI and re-add them again.  There are a number of new features which require
new metadata to be discovered at the setup phase.  This may not be present on existing devices.
If this doesn't work you can roll back to a previous release via HACS, and please log an issue with the details of your problem.

## Supported devices

This integration supports various models of Zengge LEDnetWF devices, which may also be known as:

- Zengge LEDnetWF
- YBCRG-RGBWW
- Magic Hue
- Bluetooth full colors selfie ring light

New devices using the Zengge platform are being released all the time.  We support as many of these as we can.  If you have a device which isn't supported, please log an issue and we will work with you to try and add support.

## Supported Features

- Automatic discovery of supported devices
- On/Off
- White / Color temperature mode
- RGB mode
- Brightness
- Effects
- Live status updates from remote control (once connected)

## Installation

### Requirements

You need to have the bluetooth component configured and working in Home Assistant in order to use this integration.

### Manual installation

Clone this repository into `config/` Home Assistant folder.

### HACS

This integration is now available from within HACS.

Search for "LEDnetWF BLE" and click install.  You will also get notified of future upgrades.

### Configuration Options

#### Basic Settings

**Disconnect Delay (Timeout)**
- **Default**: 120 seconds
- **Range**: 0 (never disconnect) to any positive number
- **Description**: How long to wait before disconnecting from the device when not in use. Setting to 0 means the connection will be maintained permanently, this is not recommended. Shorter timeouts may cause slower response times when controlling the device but will more quickly free up Bluetooth connections for use by other devices.

**Device Name**
- **Description**: Friendly name for your device as it appears in Home Assistant. This can be changed to something more meaningful like "Living Room Strip" or "Bedroom Lights".

#### LED Hardware Settings

**Number of LEDs**
- **Default**: 64
- **Description**: The total number of individual LEDs in your strip or device in each segment.  This should be auto detected, but relies on your device being correctly configured in the first place.  If you have 1 segment configured (where your device supports segments) this would be the total number of LEDs on the device.  If you had 2 segments configured this would be half the total number of LEDs.  i.e. each of the two segments would control half the LEDs.

**LED Type (Chip Type)**
- **Options**: WS2812B, SM16703, SM16704, WS2811, UCS1903, SK6812, SK6812RGBW, INK1003, UCS2904B, JY1903, WS2812E
- **Default**: WS2812B
- **Description**: The specific LED chip model used in your device. This affects how colors are processed and displayed. Most common strips use WS2812B. Check your device documentation or try different options if colors appear incorrect.

**Color Order**
- **Options**: RGB, RBG, GRB, GBR, BRG, BGR
- **Default**: GRB
- **Description**: The order in which red, green, and blue color data is sent to the LEDs. If colors appear wrong (e.g., red shows as blue), try different color orders until colors display correctly.

**Number of Segments**
- **Default**: 1
- **Description**: How many logical segments your LED strip is divided into. Some devices support multiple segments that can be controlled independently. Most single strips use 1 segment.  Not all devices support segments.

#### Advanced Settings

**Ignore Notification Data**
- **Default**: False (disabled)
- **Description**: When enabled, the integration will ignore status update notifications from the device and will not update the state of the light in Home Assistant in real time.  When disabled, you'll receive real-time updates when the device state changes (e.g., from physical remote control) while the Bluetooth connection is live.

### Configuration Notes

- **Recommendation**: It's generally recommended to make configuration changes through the official Zengge app first, then use these settings to match your device's actual configuration.
- **Device Detection**: Many settings (LED count, type, color order, segments) are automatically detected from supported devices during setup. Manual configuration may be needed for older devices or if auto-detection fails.
- **Effect Performance**: Incorrect LED count or type settings may cause effects to display incorrectly or perform poorly.


## Credits

This integration is possible thanks to the work of this incredible people!

- https://github.com/dave-code-ruiz/elkbledom for most of the base Home Assistant integration code adapted for this integration.
- https://openclipart.org/detail/185270/light-bulb-icon for the original icon.

Thanks!

## Support

In order to add support for more and newer lights I really need to get my hands on them.  That costs money.  Not a lot of money, but some money none the less.  If you would like to support the development of this integration and expanding support for newer devices in the future you can consider a small contribution to the costs via buymeacoffee.  There is no obligation to do this and you are free to use this software with no payments at all.  Any money raised will go exclusively towards purchasing new lights to try and build integrations for.  There is no suggestion that contributing money will get your bug fixed or support added for your lights.  You can see issues where hardware is needed here:  https://github.com/8none1/lednetwf_ble/labels/needs_hardware

https://coff.ee/8none1
