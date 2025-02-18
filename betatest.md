# Beta tests

## How to install a beta version

 1. Open HACS
 2. Locate the LEDnetWF BLE integration and click on it
 3. In the top right corner menu, choose "redownload"
 4. Note the "Need a different version?" drop down, click that and you should see a "Release" drop down
 5. Choose the release tagged "pre release" which should have "beta" in the name
 6. Restart Home Assistant

You might see messages about "upgrading" to the previous release.  Just ignore these while you are testing the beta.

If you notice any bugs please log an issue and ensure that you note that you are running a beta release, and which beta release you are running.

![image](https://github.com/user-attachments/assets/14f81259-c68a-4ad9-a077-5c16c926ac40)

## How to enable debugging

There are two options for enabling debugging.

The easiest one is via the integration's page in Home Assistant.  Navigate to Settings -> Integrations -> LEDnetWF BLE -> Click "Enable debug logging".

![image](https://github.com/user-attachments/assets/3023e178-738b-4a2b-b4f8-c906c6ff1bc0)

This will start gathering logs and when you click "Disable debug logging" you will be given a file to download with all the logs in.

The second option is slightly more difficult, but is necessary if you can't actually add a LEDnetWF device in the first place.

You need to edit your `configuration.yaml` and add a section like:

```yaml
logger:
  logs:
    custom_components.lednetwf_ble: debug
```
or something even wider, which will enable debug logging for all custom components:

```yaml
logger:
  default: info
  logs:
    custom_components: debug
```

This will enable debug logging from start up.  You may need to copy off the logs from your HA server and attach them to an issue.
