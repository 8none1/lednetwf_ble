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

### Config

After setting up, you can config two parameters Settings -> Integrations -> LEDnetWF -> Config.

- Disconnect delay or timeout: Timeout for bluetooth disconnect (0 for never)

## Credits

This integration is possible thanks to the work of this incredible people!

- https://github.com/dave-code-ruiz/elkbledom for most of the base Home Assistant integration code adapted for this integration.
- https://openclipart.org/detail/185270/light-bulb-icon for the original icon.

Thanks!
