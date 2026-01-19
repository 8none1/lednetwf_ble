# Beta Testing and Troubleshooting

## How to Install a Beta Version

1. Open HACS
2. Locate the LEDnetWF BLE integration and click on it
3. In the top right corner menu, choose "Redownload"
4. Check the "Show beta versions" checkbox
5. In the version dropdown, select the beta version you want to test
6. Click "Download"
7. Restart Home Assistant

You might see messages about "upgrading" to the previous release. Just ignore these while you are testing the beta.

If you notice any bugs please log an issue and ensure that you note that you are running a beta release, and which beta release you are running.

![image](https://github.com/user-attachments/assets/14f81259-c68a-4ad9-a077-5c16c926ac40)

## How to Downgrade to a Stable Version

If a beta version causes problems, you can go back to the previous stable release:

1. Open HACS
2. Locate the LEDnetWF BLE integration and click on it
3. In the top right corner menu, choose "Redownload"
4. Uncheck "Show beta versions" if it's checked
5. Select the previous stable version from the dropdown
6. Click "Download"
7. Restart Home Assistant

---

## How to Enable Debug Logging

Debug logs are essential for troubleshooting issues. There are two methods depending on your situation.

### Method 1: Via the Integration Page (Easiest)

Use this method if your device is already added to Home Assistant.

1. Navigate to **Settings** → **Devices & Services**
2. Find the **LEDnetWF BLE** integration
3. Click the three-dot menu (⋮) next to the integration
4. Click **"Enable debug logging"**

![image](https://github.com/user-attachments/assets/3023e178-738b-4a2b-b4f8-c906c6ff1bc0)

5. **Reproduce your issue** - try the actions that aren't working (turn on/off, change colour, change brightness, etc.)
6. Go back to the integration and click **"Disable debug logging"**
7. A file will automatically download containing all the debug logs

### Method 2: Via configuration.yaml

Use this method if:
- You can't add the device in the first place
- You need logs from Home Assistant startup
- Method 1 isn't working for you

1. Edit your `configuration.yaml` file (usually found in `/config/configuration.yaml`)

2. Add the following section:

```yaml
logger:
  default: info
  logs:
    custom_components.lednetwf_ble: debug
```

3. Save the file and restart Home Assistant

4. **Reproduce your issue** - try the actions that aren't working

5. Retrieve the logs from **Settings** → **System** → **Logs**
   - Click "Download Full Log" to get the complete log file
   - Or click "Load Full Logs" to view them in the browser

---

## How to Attach Logs to a GitHub Issue

Once you have your log file, here's how to attach it to an issue:

### Before You Post

**Important:** Please review your logs before posting. While we don't intentionally log sensitive information, your logs may contain:
- Device MAC addresses
- Network information
- Other Home Assistant component logs

Feel free to redact any information you're not comfortable sharing.

### Creating or Updating an Issue

1. Go to the [Issues page](https://github.com/8none1/lednetwf_ble/issues)
2. Click **"New Issue"** or open your existing issue

3. **To attach a log file:**
   - Drag and drop the log file directly into the comment box, OR
   - Click the "Attach files" link at the bottom of the comment box and select your file

   GitHub accepts `.log`, `.txt`, and `.zip` files. If your log file is very large, please zip it first.

4. **To paste log snippets:**
   - Use code blocks to format logs properly:

   ````
   ```
   Paste your log content here
   ```
   ````

### What to Include in Your Issue

To help us resolve your problem quickly, please include:

1. **Device information:**
   - Device name (e.g., IOTBT65C, LEDnetWF1234)
   - Where you purchased it / product link if available

2. **What's working and what isn't:**
   - Can you turn it on/off?
   - Can you change colours?
   - Can you change brightness?
   - Do effects work?

3. **Your setup:**
   - Home Assistant version
   - Integration version (stable or which beta)
   - How you connect to Bluetooth (USB adapter, ESPHome proxy, etc.)
   - Are you running HA in a VM? (this often causes Bluetooth issues)

4. **The debug logs** (attached as a file or pasted in a code block)

---

## Common Issues

### "No backend with an available connection slot"

This error means Home Assistant can't establish a Bluetooth connection. Common causes:
- **Too many BLE devices** - ESPHome Bluetooth proxies have limited connection slots
- **Running HA in a VM** - Bluetooth passthrough can be unreliable
- **USB adapter issues** - Try a different USB port or adapter

### Device detected but controls don't work

If on/off works but colour/brightness don't:
- This may be a protocol variant we haven't seen before
- Please provide debug logs so we can investigate

### Device not detected at all

- Make sure Bluetooth is working in Home Assistant (check **Settings** → **Devices & Services** → **Bluetooth**)
- Ensure the device name starts with `LEDnetWF`, `IOTBT`, or `IOTWF`
- Try moving the device closer to your Bluetooth adapter/proxy
