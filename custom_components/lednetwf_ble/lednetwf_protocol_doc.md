
================================================================================
9. MANUFACTURER IDS AND PROTOCOL VARIANTS
================================================================================

9.1 MANUFACTURER ID RANGES
--------------------------
The application supports multiple manufacturer ID ranges. Devices with IDs
in these ranges are recognized as compatible:

PRIMARY RANGE (LEDnetWF devices):
  23120-23122 (0x5A50, 0x5A51, 0x5A52)
  
EXTENDED RANGES (ZGHBDevice validation):
  Exact match IDs: 23123-23133
  Range 1: 23072-23087 (0x5A20-0x5A2F)
  Range 2: 23136-23151 (0x5A60-0x5A6F)
  Range 3: 23152-23167 (0x5A70-0x5A7F)
  Range 4: 23168-23183 (0x5A80-0x5A8F)

VALIDATION LOGIC:
  Java pseudocode from ZGHBDevice.getManufacturer():
    int id = ((byte1 & 0xFF) << 8) | (byte2 & 0xFF)  // Big-endian
    
    // Check exact matches
    if (id == 23123 || id == 23124 || ... || id == 23133):
        return id
    
    // Check ranges
    if ((id >= 23072 && id <= 23087) ||
        (id >= 23136 && id <= 23151) ||
        (id >= 23152 && id <= 23167) ||
        (id >= 23168 && id <= 23183)):
        return id
    
    return -1  // Invalid manufacturer ID

9.2 MANUFACTURER ID ENCODING
----------------------------
The manufacturer ID is stored in bytes 1-2 of the manufacturer data (29-byte
structure) or in the custom advertisement packet. It uses big-endian encoding:

  manufacturer_id = (byte[1] << 8) | byte[2]

Example:
  Bytes: [0x5A, 0x50]
  ID: (0x5A << 8) | 0x50 = 23120

9.3 PROTOCOL VERSION DETERMINATION
----------------------------------
The BLE version field (byte 3 in manufacturer data) determines which write
protocol version to use:

BLE VERSION → WRITE PROTOCOL VERSION:
  bleVersion < 8  → Protocol Version 0 (legacy)
  bleVersion >= 8 → Protocol Version 1 (modern)

Java code from ZGHBWriteUtils.getWriteVersion():
  public static int getWriteVersion(int bleVersion) {
      return bleVersion >= 8 ? 1 : 0;
  }

PROTOCOL DIFFERENCES:

Version 0 (BLE version < 8):
  - Maximum MTU: 255 bytes
  - Standard packet format
  - Compatible with BLE 4.0+ devices
  
Version 1 (BLE version >= 8):
  - Maximum MTU: 512 bytes
  - Optimized packet format
  - Requires BLE 5.0+ features
  - Better throughput for firmware updates

9.4 MTU NEGOTIATION
-------------------
After connecting, the app negotiates the Maximum Transmission Unit:

  requested_mtu = 512 bytes (for protocol v1)
  requested_mtu = 255 bytes (for protocol v0)
  
The actual MTU is min(requested, device_supported):
  
  BluetoothGatt.requestMtu(requested_mtu)
  
  // In callback:
  onMtuChanged(gatt, negotiated_mtu, status) {
      if (status == GATT_SUCCESS) {
          use_mtu = negotiated_mtu
      }
  }

Transport layer max length:
  transport_max = min(negotiated_mtu, protocol_version == 1 ? 512 : 255)

================================================================================
10. WRITE COMMANDS AND CONTROL PROTOCOLS
================================================================================

10.1 COMMAND STRUCTURE
----------------------
Commands sent to devices consist of:

1. COMMAND ID (cmdId): Single byte identifying the operation
2. PAYLOAD DATA: Variable-length byte array with command parameters
3. CHECKSUM: Single byte for validation (sum of all previous bytes)

FLUTTER/BLE COMMAND WRAPPER:
  class Command {
      int cmdId;           // Command identifier (or 10/11 for generic)
      byte[] data;         // Raw payload bytes
      byte resultId;       // Expected response command ID
      int opcode;          // Mesh/broadcast opcode (for non-connected)
      int meshAddress;     // Target mesh address (broadcast only)
      int networkId;       // Network ID (broadcast only)
  }

10.2 COMMAND ID TYPES
---------------------
For BLE-only LED controllers, two command IDs are used:

A) cmdId = 10 (WITH_RESPONSE_CMD_ID):
   - Used for commands that expect a response
   - Example: State query (0x81) expects device state back
   - The actual command opcode is first byte of payload data
   
B) cmdId = 11 (NO_RESPONSE_CMD_ID):
   - Used for commands that don't need a response
   - Example: Set color (0x31), power on/off (0x41/0x42)
   - Fire-and-forget control commands

Note: cmdIds 1-9 are used for WiFi-capable devices during provisioning
and are NOT relevant for BLE-only LED controllers.

Detection logic from FlutterBleControl:
  if (data[0] == 0x81 || cmdId == 65535) {
      // Use generic mode
      command.cmdId = 10;
      command.resultId = 10;
  } else if (response_count > 0) {
      command.cmdId = 10;
  } else {
      command.cmdId = 11;
  }

10.3 CHECKSUM CALCULATION
-------------------------
All commands include a checksum byte as the last byte. This is calculated
by summing all previous bytes:

Java implementation from tc.b class:
  public static byte b(byte[] bArr, int checksumPosition) {
      int sum = 0;
      for (int i = 0; i < checksumPosition; i++) {
          sum += bArr[i] & 0xFF;  // Treat as unsigned
      }
      return (byte) sum;  // Truncate to byte
  }

Python equivalent:
  def calculate_checksum(data, checksum_position):
      return sum(data[:checksum_position]) & 0xFF

Example:
  Command: [0x31, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xF0, 0x0F, ??]
  Checksum position: 8 (last byte)
  Sum: 0x31 + 0xFF + 0x00 + 0x00 + 0x00 + 0x00 + 0xF0 + 0x0F = 0x22F
  Checksum: 0x2F (low byte of sum)

10.4 RGB COLOR COMMANDS
-----------------------
Multiple command formats exist for setting RGB colors. The format depends
on device capabilities and whether warm/cold white channels are present.

FORMAT 1: RGB ONLY (Command 0x31, 9 bytes)
Function signature: s(r, g, b, warm, cold, persist)

  BYTE | FIELD           | VALUE
  -----|-----------------|------------------
  0    | Command opcode  | 0x31 (49 decimal)
  1    | Red             | 0-255
  2    | Green           | 0-255
  3    | Blue            | 0-255
  4    | Warm white      | 0-255
  5    | Cold white      | 0-255
  6    | Mode            | 0x5A (90) = RGB mode
  7    | Persist flag    | 0xF0 = save, 0x0F = don't save
  8    | Checksum        | Sum of bytes 0-7

Java implementation:
  public static byte[] s(int r, int g, int b, int warm, int cold, boolean persist) {
      byte[] cmd = new byte[9];
      cmd[0] = 49;  // 0x31
      cmd[1] = (byte) r;
      cmd[2] = (byte) g;
      cmd[3] = (byte) b;
      cmd[4] = (byte) warm;
      cmd[5] = (byte) cold;
      cmd[6] = 90;  // 0x5A
      cmd[7] = persist ? (byte) 0xF0 : (byte) 0x0F;
      cmd[8] = calculateChecksum(cmd, 8);
      return cmd;
  }

EXAMPLE - Set Red Color (RGB 255,0,0):
  [0x31, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x5A, 0x0F, 0x2F]
  
  Breaking down:
    0x31 = RGB command
    0xFF = Red = 255
    0x00 = Green = 0
    0x00 = Blue = 0
    0x00 = Warm white = 0
    0x00 = Cold white = 0
    0x5A = RGB mode indicator
    0x0F = Don't persist to memory
    0x2F = Checksum

EXAMPLE - Set Green Color (RGB 0,255,0):
  [0x31, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x5A, 0x0F, 0x30]

EXAMPLE - Set Blue Color (RGB 0,0,255):
  [0x31, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x5A, 0x0F, 0x31]

EXAMPLE - Set Purple (RGB 128,0,128):
  [0x31, 0x80, 0x00, 0x80, 0x00, 0x00, 0x5A, 0x0F, 0xB1]

10.4.1 WHAT THE 0x5A MODE INDICATOR IS
--------------------------------------
The byte `0x5A` at position 6 in the `0x31` RGB command (`tc.b.s(...)`) is a
mode selector used by the controller to interpret the payload as “RGB mode”.

- When `cmd[6] = 0x5A`, the device treats bytes 1-5 as RGB (and optional WW/CW)
  channel values and applies them directly.
- Alternate RGB command variants set this field differently to indicate mode:
  - `tc.b.t(...)` uses `cmd[6] = 0xF0` to assert RGB-active mode without WW/CW.
  - Variants `x(...)`/`y(...)` may toggle a white auto-mode byte (`cmd[5]`) and
    keep `cmd[6]` as persistence/mode flag.

Usage:
- Use `0x5A` when sending combined RGB + white values (Format 1) to explicitly
  select RGB mode on mixed-channel devices.
- Use `0xF0` (Format 2) for simplified RGB-only writes on devices or scenes not
  using white channels.

FORMAT 2: RGB ONLY (Command 0x31, 9 bytes, simplified)
Function signature: t(r, g, b, persist)

  BYTE | FIELD           | VALUE
  -----|-----------------|------------------
  0    | Command opcode  | 0x31 (49)
  1    | Red             | 0-255
  2    | Green           | 0-255
  3    | Blue            | 0-255
  4    | Reserved        | 0x00
  5    | Reserved        | 0x00
  6    | Mode            | 0xF0 = RGB active
  7    | Persist flag    | 0xF0 = save, 0x0F = don't save
  8    | Checksum        | Sum of bytes 0-7

EXAMPLE - Set Red (simplified):
  [0x31, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xF0, 0x0F, 0x30]

FORMAT 3: RGB WITH BRIGHTNESS (Command 0x31, 8 bytes)
Function signature: v(r, g, b, brightness, persist)

  BYTE | FIELD           | VALUE
  -----|-----------------|------------------
  0    | Command opcode  | 0x31 (49)
  1    | Red             | 0-255
  2    | Green           | 0-255
  3    | Blue            | 0-255
  4    | Brightness      | 0-255
  5    | Reserved        | 0x00
  6    | Persist flag    | 0xF0 = save, 0x0F = don't save
  7    | Checksum        | Sum of bytes 0-6

EXAMPLE - Set Red at 50% brightness:
  [0x31, 0xFF, 0x00, 0x00, 0x7F, 0x00, 0x0F, 0xBF]
  (brightness 0x7F = 127 = ~50%)

FORMAT 4: RGB WITH AUTO WHITE (Command 0x31, 8 bytes)
Function signature: x(r, g, b, brightness, persist)

  BYTE | FIELD           | VALUE
  -----|-----------------|------------------
  0    | Command opcode  | 0x31 (49)
  1    | Red             | 0-255
  2    | Green           | 0-255
  3    | Blue            | 0-255
  4    | Brightness      | 0-255
  5    | White mode      | 0x0F if brightness>0, else 0xF0
  6    | Persist flag    | 0xF0 = save, 0x0F = don't save
  7    | Checksum        | Sum of bytes 0-6

FORMAT 5: ALTERNATE RGB (Command 0x41, 9 bytes)
Function signature: u(r, g, b, flag)

  BYTE | FIELD           | VALUE
  -----|-----------------|------------------
  0    | Command opcode  | 0x41 (65) or 0x42 (66) if flag=true
  1    | Red             | 0-255
  2    | Green           | 0-255
  3    | Blue            | 0-255
  4    | Reserved        | 0x00
  5    | Reserved        | 0x00
  6    | Mode            | 0xF0
  7    | Persist         | 0x0F
  8    | Checksum        | Sum of bytes 0-7

FORMAT 6: ALTERNATE RGB WITH BRIGHTNESS (Command 0x41, 8 bytes)
Function signatures: w, y, z

Similar to formats 3-4 but using command 0x41 (65) instead of 0x31 (49).

10.5 WHITE CHANNEL COMMANDS
---------------------------
For devices with warm/cold white LEDs:

COMMAND: Set Warm/Cold White Levels
Opcode: Varies by device type

EXAMPLE - Dual white control (8 bytes):
  [OpCode, Warm, Cold, Reserved, Reserved, Reserved, Persist, Checksum]

10.5.1 HOW WHITE CHANNEL PRESENCE IS DETERMINED
-----------------------------------------------
White channel support (Warm White WW and Cool White CW) is determined from
device capability metadata parsed during scanning and device instantiation:

- `productId`:
  NOTE: Offset depends on format! 
    - Format A (29-byte): bytes 10-11
    - Format B (27-byte bleak): bytes 8-9
  Maps to a specific device class in `com.zengge.wifi.Device.*`.
  Device classes indicate capabilities:
    - `RGBDeviceInfo` → RGB only
    - `RGBWBothDeviceInfo` / `RGBCWBothDeviceInfo` / `RGBCWBulbDeviceInfo` → has WW/CW channels
  Example mappings (from `Device/a.java`):
    - `Ctrl_Mini_RGB_0x33` (product_id=51) → RGB only
    - `Ctrl_Mini_RGBW_0x06/0x20/0x26/0x27` → RGB + White (WW/CW as supported)
    - `Ctrl_Mini_RGBCW_0x07`, `Bulb_RGBCW_*`, `CeilingLight_RGBCW_*` → RGBCW

- `ledVersion`:
  NOTE: Offset depends on format!
    - Format A (29-byte): byte 13
    - Format B (27-byte bleak): byte 11
  Used across device classes to differentiate LED hardware versions; in
  conjunction with `productId`, it selects the correct device type and thus
  whether white channels exist.

- `iconFlag` (tail byte of extended state advertisement when BLE version ≥ 7):
  UI hint flag parsed into `ZGHBDevice.iconFlag`; certain values correspond
  to devices with WW/CW controls. This flag is supplementary; capability
  detection primarily relies on `productId` → device class mapping.

Implementation note for Python:
- Maintain a capability map: productId → {has_rgb, has_ww, has_cw} based on
  observed Java class associations. If unknown productId, default to RGB-only
  until a state query confirms WW/CW support.

10.5.2 PRODUCTID → CAPABILITIES QUICK TABLE
-------------------------------------------
Derived from `com.zengge.wifi.Device.a.k(productId, deviceInfo)`:

  productId | Device Class                          | Capabilities
  --------- | ------------------------------------- | ----------------------------
  6         | Ctrl_Mini_RGBW_0x06                   | RGB + White (likely WW/CW)
  7         | Ctrl_Mini_RGBCW_0x07                  | RGB + Warm + Cool (RGBCW)
  8         | Ctrl_Mini_RGB_Mic_0x08                | RGB only
  9         | Ctrl_Ceiling_light_CCT_0x09           | CCT (WW+CW), no RGB
  14        | FloorLamp_RGBCW_0x0E                  | RGBCW
  22        | Magnetic_CCT_0x16                     | CCT only
  23        | Magnetic_Dim_0x17                     | Dim only
  24        | PlantLight_0x18                       | Non-RGB lighting
  25        | Socket_2Usb_0x19                      | Non-light
  26        | ChristmasLight_0x1A                   | RGB (likely)
  27        | SprayLight_0x1B                       | RGB (likely)
  28        | TableLamp_CCT_0x1C                    | CCT only
  29        | FillLight_0x1D                        | RGBCW (dynamic - stub class)
  30        | CeilingLight_RGBCW_0x1E               | RGBCW
  32        | Ctrl_Mini_RGBW_0x20                   | RGB + White (likely WW/CW)
  33        | Bulb_Dim_0x21                         | Dim only
  37        | Ctrl_RGBCW_Both_0x25                  | RGBCW
  38        | Ctrl_Mini_RGBW_0x26                   | RGB + White (likely WW/CW)
  39        | Ctrl_Mini_RGBW_0x27                   | RGB + White (likely WW/CW)
  41        | MirrorLight_0x29                      | RGBCW
  45        | GAON_PlantLight_0x2D                  | Non-RGB lighting
  51        | Ctrl_Mini_RGB_0x33                    | RGB only
  53        | Bulb_RGBCW_R120_0x35                  | RGBCW
  59        | Bulb_RGBCW_0x3B                       | RGBCW
  65        | Ctrl_Dim_0x41                         | Dim only
  68        | Bulb_RGBW_0x44                        | RGB + White (WW/CW)
  72        | Ctrl_Mini_RGBW_Mic_0x48               | RGB + White (WW/CW)
  82        | Bulb_CCT_0x52                         | CCT only
  84        | Downlight_RGBW_0X54                   | RGB + White (WW/CW)
  98        | Ctrl_CCT_0x62                         | CCT only
  147–151   | Switch_*                               | Non-light controls
  161       | Ctrl_Mini_RGB_Symphony_0xa1           | RGB effects (RGB only)
  162       | Ctrl_Mini_RGB_Symphony_new_0xa2       | RGB effects (RGB only)
  163       | Ctrl_Mini_RGB_Symphony_new_0xA3       | RGB effects (RGB only)
  164       | Ctrl_Mini_RGB_Symphony_new_0xA4       | RGB effects (RGB only)
  166       | Ctrl_Mini_RGB_Symphony_new_0xA6       | RGB effects (RGB only)
  167       | Ctrl_Mini_RGB_Symphony_new_0xA7       | RGB effects (RGB only)
  169       | Ctrl_Mini_RGB_Symphony_new_0xA9       | RGB effects (RGB only)
  209       | Digital_Light_0xd1                    | Non-RGB lighting
  225       | Ctrl_Ceiling_light_0xe1               | Ceiling light (varies)
  226       | Ctrl_Ceiling_light_Assist_0xe2        | Ceiling light + assist (varies)

Notes:
- “RGB + White” typically implies both WW and CW channels on these controllers.
- “CCT” implies WW/CW without RGB.
- Symphony classes focus on animated RGB effects and do not indicate WW/CW.
- Use `ledVersion` to refine capabilities per product family if discrepancies arise.

Home Assistant integration focus:
- Exclude Flutter/UI-specific hints. Ignore `iconFlag` or display-only fields.
- Prefer capability inference from `productId`, `ledVersion`, and actual state queries.

IMPORTANT - STUB DEVICE CLASSES:
Some productIds have "stub" Java classes that extend BaseDeviceInfo directly without
implementing any capability interfaces. These include:

  ProductId | Class Name         | Meaning
  ----------|--------------------|----------------------------------------------------------
  29        | FillLight0x1D      | Stub - capabilities VARY by hardware variant (can be RGBCW)

For stub classes, the app determines capabilities DYNAMICALLY from:
1. State query responses - which channels have values
2. The device's actual response to control commands
3. Runtime capability detection rather than static class type

For Home Assistant integration:
- Do NOT assume stub devices have limited capabilities based on class type
- Always probe with a state query and test which channels respond
- Treat stub devices as "unknown capability" until validated
- FillLight devices in particular have been observed with full RGBCW support


10.5.2.1 DEVICE CAPABILITY INTERFACES (hd.* package)
----------------------------------------------------
Each device class implements interfaces from the `hd` package that define its capabilities.
These interfaces are checked via `instanceof` at runtime to determine feature availability.

INTERFACE DEFINITIONS:

  Interface | Methods                                      | Capability Meaning
  ----------|----------------------------------------------|--------------------------------------------
  hd.a      | f(int), g(boolean), k()                      | Assist/auxiliary light control
  hd.b      | (marker interface - no methods)              | CCT color temperature support
  hd.c      | (marker interface - no methods)              | Dimmer-only device (no color)
  hd.d      | d(), m()                                     | Microphone/music mode support
  hd.e      | (marker interface - no methods)              | Extended features (TBD)
  hd.f      | i()                                          | Timer support
  hd.g      | extends hd.h; h(), j()                       | Symphony effect support (legacy)
  hd.h      | b(), n(int)                                  | Effect mode get/set
  hd.i      | c(), o()                                     | Color order/wiring support (new style)
  hd.j      | l(), p()                                     | Wiring order setting (RGB/GRB/BRG)
  hd.k      | (marker interface - no methods)              | Extended timer/schedule features
  hd.l      | a(), e()                                     | LED IC chip type configuration (WS2812B, etc.)

10.5.2.2 DEVICE CLASS -> INTERFACE MAPPING
------------------------------------------
Source: Device type class declarations in com/zengge/wifi/Device/Type/

  productId | Device Class                     | Base Type              | Interfaces        | Key Capabilities
  ----------|----------------------------------|------------------------|-------------------|----------------------------------
  6         | Ctrl_Mini_RGBW_0x06              | RGBWBothDeviceInfo     | l, j, f, k, i     | IC chip, wiring, timer, color order
  7         | Ctrl_Mini_RGBCW_0x07             | RGBCWBothDeviceInfo    | b, l, j, f, k, i  | CCT, IC chip, wiring, timer
  8         | Ctrl_Mini_RGB_Mic_0x08           | RGBDeviceInfo          | j, f, d           | Wiring, timer, microphone/music
  9         | Ctrl_Ceiling_light_CCT_0x09      | StandardCCTDeviceInfo  | b, k              | CCT, extended timer
  37        | Ctrl_RGBCW_Both_0x25             | RGBCWBothDeviceInfo    | b, l, f, k        | CCT, IC chip, timer
  51        | Ctrl_Mini_RGB_0x33               | RGBDeviceInfo          | j, f, d, i        | Wiring, timer, music, color order
  65        | Ctrl_Dim_0x41                    | BrightnessDeviceInfo   | c                 | Dimmer only
  68        | Ctrl_RGBW_UFO_0x04               | RGBWBothDeviceInfo     | f, k              | Timer, extended timer
  72        | Ctrl_Mini_RGBW_Mic_0x48          | RGBDeviceInfo          | l, j, f, k, i, d  | IC chip, wiring, timer, music
  98        | Ctrl_CCT_0x62                    | CCTDeviceInfo          | b, k              | CCT, extended timer
  161       | Ctrl_Mini_RGB_Symphony_0xa1      | RGBSymphonyDeviceInfo  | h, f, d           | Effects, timer, music
  162       | Ctrl_Mini_RGB_Symphony_new_0xa2  | RGBNewSymphonyDeviceInfo| f, k             | Timer, extended timer
  163       | Ctrl_Mini_RGB_Symphony_new_0xA3  | (extends 0xa2)         | (inherits f, k)   | Timer, extended timer
  164       | Ctrl_Mini_RGB_Symphony_new_0xA4  | (extends 0xA3)         | (inherits f, k)   | Timer, extended timer
  166       | Ctrl_Mini_RGB_Symphony_new_0xA6  | (extends 0xA3)         | (inherits f, k)   | Timer, extended timer
  167       | Ctrl_Mini_RGB_Symphony_new_0xA7  | (extends 0xA3)         | (inherits f, k)   | Timer, extended timer
  169       | Ctrl_Mini_RGB_Symphony_new_0xA9  | (extends 0xA3)         | (inherits f, k)   | Timer, extended timer
  225       | Ctrl_Ceiling_light_0xe1          | CeilingDeviceInfo      | b                 | CCT
  226       | Ctrl_Ceiling_light_Assist_0xe2   | (extends 0xe1)         | a                 | Assist/auxiliary light

CAPABILITY FLAG INTERPRETATION:
- hd.b -> Device supports CCT (color temperature) control
- hd.c -> Device is dimmer-only (no RGB, no CCT)
- hd.d -> Device supports microphone input / music reactive mode
- hd.f -> Device supports timer/schedule commands
- hd.i -> Device supports configurable color channel order (RGB/GRB/BRG variants)
- hd.j -> Device supports wiring order configuration UI
- hd.k -> Device supports extended timer/scheduling features
- hd.l -> Device supports LED IC chip type selection (addressable LED driver chips)

WIRING ORDER VALUES (from hd.j implementations):
- 1 = RGB
- 2 = GRB
- 3 = BRG

LED IC CHIP TYPES (from hd.l implementations - SymphonyICTypeItem):
- 1 = WS2812B (standard addressable RGB LED chip)
- 2 = WS2811
- 3 = UCS1903
- 4 = SK6812
- 5 = SK6812RGBW (RGBW variant)
- 6 = INK1003
- 7 = UCS2904B
- 8 = JY1903 (ledVersion >= 2)
- 9 = WS2812E (BLE v2, ledVersion >= 3)
- 10 = CF1903B (WiFi only, ledVersion >= 3)

10.5.2.3 EFFECTS SYSTEM - HARDCODED IN APP (NOT QUERIED FROM DEVICE)
---------------------------------------------------------------------
IMPORTANT: Effects are NOT enumerated from the device at runtime. The app contains
hardcoded effect lists that are assigned based on device type (productId).

Source: com/zengge/wifi/activity/NewSymphony/fragment/FunctionModeFragment.java

EFFECT COUNT BY DEVICE TYPE:
  Device Type                           | Effect Range | Total Effects
  --------------------------------------|--------------|---------------
  Ctrl_Mini_RGB_Symphony_0xa1           | 1-100        | 100 effects
  Ctrl_Mini_RGB_Symphony_new_0xa2       | 1-100        | 100 effects
  Ctrl_Mini_RGB_Symphony_new_0xA3       | 1-100        | 100 effects
  Ctrl_Mini_RGB_Symphony_new_0xA4       | 1-100        | 100 effects
  Ctrl_Mini_RGB_Symphony_new_0xA6       | 1-227        | 227 effects
  Ctrl_Mini_RGB_Symphony_new_0xA7       | 1-100        | 100 effects
  Ctrl_Mini_RGB_Symphony_new_0xA9       | 1-131        | 131 effects
  Non-Symphony devices (e.g., 0x33)     | N/A          | NO effects

Code from FunctionModeFragment.java (lines 182-195):
```java
if (Ctrl_Mini_RGB_Symphony_new_0xA6.F1(baseDeviceInfoY0)) {
    i10 = 227;  // 0xA6 devices get 227 effects
} else if (Ctrl_Mini_RGB_Symphony_new_0xA9.F1(baseDeviceInfoY0)) {
    i10 = 131;  // 0xA9 devices get 131 effects
} else {
    i10 = 100;  // Other Symphony devices get 100 effects
}

// Effect IDs are simply sequential integers: 1, 2, 3, ... up to i10
for (int i11 = 1; i11 <= i10; i11++) {
    arrayList.add(i11 + "");
}
```

NON-SYMPHONY DEVICES (like Ctrl_Mini_RGB_0x33):
- Do NOT have effects - only solid color control
- Method s0() returns empty ArrayList (no effect tabs in UI)
- Use ActivityTabForRGB.class (simple RGB) instead of NewSymphonyActivity.class (effects)

EFFECT DEFINITIONS (from dd/i.java):
The app defines 44 named effects with UI type classifications:

  Effect ID | UI Type Category                      | Parameter Requirements
  ----------|---------------------------------------|----------------------------------
  1         | UIType_StartColor_EndColor            | Start color + End color
  2         | UIType_Only_ForegroundColor           | Single color only
  3         | UIType_StartColor_EndColor            | Start color + End color
  4         | UIType_StartColor_EndColor            | Start color + End color
  5-9       | UIType_ForegroundColor_BackgroundColor| Foreground + Background color
  10-18     | UIType_ForegroundColor_BackgroundColor| Foreground + Background color
  19-26     | UIType_FirstColor_SecondColor         | First color + Second color
  27-28     | UIType_Only_BackgroundColor           | Single background color
  29-44     | IType_NoColor                         | No color parameters (preset)

UI TYPE MEANINGS:
- UIType_StartColor_EndColor: Gradient effects (user picks start and end colors)
- UIType_Only_ForegroundColor: Single color effects (breathing, strobe)
- UIType_ForegroundColor_BackgroundColor: Two-color effects (chase, alternating)
- UIType_FirstColor_SecondColor: Two-color patterns
- UIType_Only_BackgroundColor: Background-only effects
- IType_NoColor: Preset rainbow/multi-color effects (no user color input)

EFFECT COMMAND FORMAT (tc/d.java):
  Opcode: 0x38 (56 decimal)
  
  BYTE | FIELD           | VALUE
  -----|-----------------|---------------------------
  0    | Command opcode  | 0x38 (56)
  1    | Effect mode ID  | 1-227 (device-dependent max)
  2    | Speed           | 0-255
  3    | Parameter       | Effect-specific (often 0)
  4    | Checksum        | Sum of bytes 0-3

EXAMPLE - Set effect 5 (rainbow chase) at speed 128:
  [0x38, 0x05, 0x80, 0x00, 0xBD]

HOME ASSISTANT IMPLEMENTATION NOTES:
1. Effects are static per productId - no device query needed
2. For Symphony devices (productId 161-169), expose effects 1-100 (or device-specific max)
3. For non-Symphony devices, do NOT expose effects (only color control)
4. Effect names are in app string resources (not available in decompiled code)
5. Use generic names like "Effect 1", "Effect 2", etc. or common effect names for known IDs

HSV/SYMPHONY COLOR COMMAND FORMAT (tc/d.java - 0x3b command family)
-------------------------------------------------------------------
Source files:
  - tc/d.java: Command builder methods (lines 8-43)
  - g2/c.java: Byte packing utilities (lines 15-25)
  - hd/h.java: HSV state interface definition

Some devices (particularly Symphony family productId 161 = 0xa1) support HSV-based
color commands using a different format than the standard 0x31 RGB command.

This command format is also used for FillLight devices that accept HS color mode.

COMMAND STRUCTURE (13 bytes):
  Java source: tc/d.java method c() lines 19-35
  Function: tc.d.c(mode, hue, saturation, brightness, param1, param2, color_rgb, time)
  
  Byte | Field             | Value                      | Description
  -----|-------------------|----------------------------|----------------------------------
  0    | Prefix            | 0x3B (59)                  | Command identifier
  1    | Mode/Type         | 0-255                      | Color mode type (see below)
  2    | Hue+Sat (hi)      | see encoding               | Packed hue/saturation high byte
  3    | Hue+Sat (lo)      | see encoding               | Packed hue/saturation low byte
  4    | Brightness        | 0-100                      | Brightness percentage (0-100)
  5    | Param1            | 0-255                      | Mode-specific parameter 1
  6    | Param2            | 0-255                      | Mode-specific parameter 2
  7    | Color R           | 0-255                      | RGB color red (from Android Color)
  8    | Color G           | 0-255                      | RGB color green
  9    | Color B           | 0-255                      | RGB color blue
  10   | Time (hi)         | 0-255                      | Time/duration high byte
  11   | Time (lo)         | 0-255                      | Time/duration low byte
  12   | Checksum          | sum mod 256                | tc.b.b(cmd, 12)

MODE TYPE VALUES (byte 1):
  Value | Hex   | Mode Name          | Usage
  ------|-------|--------------------|-----------------------------------------
  161   | 0xa1  | Symphony HSV       | Standard HSV color for Symphony devices
  166   | 0xa6  | Symphony Alternate | Alternate Symphony mode
  179   | 0xb3  | CCT Mode           | Color temperature mode
  175   | 0xaf  | Effect Mode 1      | Dynamic effect mode
  176   | 0xb0  | Effect Mode 2      | Dynamic effect mode
  177   | 0xb1  | Speed Control      | Effect speed parameter
  178   | 0xb2  | Effect Mode 3      | Dynamic effect mode

HUE + SATURATION ENCODING (bytes 2-3):
  Java source: tc/d.java line 23, g2/c.java lines 18-24
  
  The hue and saturation values are packed into a 16-bit big-endian integer:
  
  packed_value = (hue << 7) | saturation
  
  Where:
    - hue: 0-359 (degrees on color wheel)
    - saturation: 0-100 (percentage, fits in 7 bits)
  
  The 16-bit value is split into two bytes using g2.c.b():
    byte[2] = (packed_value >> 8) & 0xFF  = (hue >> 1)  (high byte ≈ hue/2)
    byte[3] = packed_value & 0xFF         = ((hue & 1) << 7) | saturation
  
  WHY "hue/2" APPEARS TO WORK:
    The high byte effectively contains hue/2 because:
      packed = (hue << 7) | sat
      high_byte = packed >> 8 = (hue << 7) >> 8 = hue >> 1 = hue/2
    
    So if you set byte[2] = hue/2 and byte[3] = saturation, you get approximately
    the same result, but you lose the LSB of hue (±1 degree precision loss).
    The correct encoding preserves full hue precision.

  Decoding (g2.c.a() - note: uses little-endian for device state):
    Java source: g2/c.java lines 15-17
    packed_value = ((byte[1] << 8) & 0xFF00) | (byte[0] & 0xFF)
    hue = packed_value >> 7
    saturation = packed_value & 0x7F

  Java source (g2/c.java lines 18-24):
    // Encode: big-endian split
    public static byte[] b(int i10) {
        return new byte[]{(byte) ((i10 >> 8) & 255), (byte) (i10 & 255)};
    }
    // Decode: little-endian reassemble (used for state response)
    public static int a(byte[] bArr) {
        return ((bArr[1] << 8) & 0xFF00) | (bArr[0] & 255);
    }

USER-OBSERVED HS PACKET FORMAT (FillLight_0x1D device):
  Full packet hex:
    00 00 80 00 00 0d 0e 0b 3b a1 00 64 64 00 00 00 00 00 00 00 00
    \___ header (8 bytes)__/ \___ HSV command payload (13 bytes) __/
    
  Byte breakdown:
    0-7    | Header/Wrapper   | Protocol framing (device-specific)
    8      | Prefix           | 0x3B (59) - HSV command identifier
    9      | Mode             | 0xA1 (161) - Symphony HSV mode
    10-11  | Hue+Sat packed   | See encoding above
    12     | Brightness       | 0-100 brightness percentage
    13-20  | Padding/Reserved | Usually 0x00

  Python implementation (CORRECT - using bit packing):
    def set_hs_color(hue: int, saturation: int, brightness: int) -> bytes:
        """
        Set color using HS (Hue-Saturation) mode with proper bit packing.
        
        Args:
            hue: 0-359 (color wheel degrees)
            saturation: 0-100 (percentage)
            brightness: 0-100 (percentage)
        
        Java reference: tc/d.java method c() lines 19-35
        """
        # Build base packet with header
        packet = bytearray.fromhex("00 00 80 00 00 0d 0e 0b 3b a1 00 00 64 00 00 00 00 00 00 00 00")
        
        # Pack hue and saturation using the correct bit-packing method
        packed = (hue << 7) | (saturation & 0x7F)
        packet[10] = (packed >> 8) & 0xFF   # High byte (effectively hue/2)
        packet[11] = packed & 0xFF          # Low byte (hue LSB << 7 | saturation)
        packet[12] = brightness & 0xFF      # Brightness 0-100
        
        return bytes(packet)

COLOR CONVERSION (from Android Color int):
The tc.d.a() method converts Android RGB color to HSV command:

  Java source (tc/d.java):
    public static byte[] a(int color, int time) {
        float[] hsv = {0.0f, 0.0f, 0.0f};
        Color.colorToHSV(color, hsv);  // Android's color→HSV
        return c(
            161,                        // Mode = 0xa1 (Symphony HSV)
            Math.round(hsv[0]),         // Hue 0-359
            Math.round(hsv[1] * 100),   // Saturation 0-100
            Math.round(hsv[2] * 100),   // Brightness 0-100
            0, 0,                       // Params
            time,                       // Color as RGB int
            0                           // Time
        );
    }

DEVICES USING THIS FORMAT:
Based on decompiled code analysis:
  
  ProductId | Class Name                      | Uses HSV Command
  ----------|---------------------------------|------------------
  161       | Ctrl_Mini_RGB_Symphony_0xa1     | Yes (primary)
  162-169   | Other Symphony variants         | Yes (likely)
  29        | FillLight_0x1D                  | Yes (user confirmed)
  
Symphony devices (RGBSymphonyDeviceInfo base class) are the primary users.
Some FillLight devices also accept this format for color control.

STATE RESPONSE FOR HSV DEVICES:
Devices using HSV commands store H/S values differently in state:

  Java source (Ctrl_Mini_RGB_Symphony_0xa1.java):
    @Override
    public int b() {  // Get packed hue+saturation
        DeviceState state = this.f23812e;
        if (state == null) return 0;
        // f23870p = high byte, f23869n = low byte
        return g2.c.a(new byte[]{
            state.f23870p.byteValue(),
            state.f23869n.byteValue()
        });
    }
    
    @Override
    public void n(int packed) {  // Set packed hue+saturation
        byte[] bytes = g2.c.c(packed);  // Split into bytes
        this.f23812e.f23869n = Byte.valueOf(bytes[1]);  // low byte
        this.f23812e.f23870p = Byte.valueOf(bytes[0]);  // high byte
    }

HOME ASSISTANT IMPLEMENTATION FOR HS MODE:
For devices that use HS color mode:

  class ZengeeLightHS(ZengeeLight):
      """Light entity supporting HS color mode."""
      
      _attr_color_mode = ColorMode.HS
      _attr_supported_color_modes = {ColorMode.HS}
      
      def __init__(self, ...):
          super().__init__(...)
          self._hs_color = (0, 0)  # (hue, saturation)
          self._brightness = 255
      
      @property
      def hs_color(self) -> tuple[float, float] | None:
          return self._hs_color
      
      @property
      def brightness(self) -> int:
          return self._brightness
      
      async def async_turn_on(self, **kwargs):
          if ATTR_HS_COLOR in kwargs:
              self._hs_color = kwargs[ATTR_HS_COLOR]
          if ATTR_BRIGHTNESS in kwargs:
              self._brightness = kwargs[ATTR_BRIGHTNESS]
          
          hue, sat = self._hs_color
          brightness_pct = int(self._brightness / 255 * 100)
          
          # Build HSV command packet
          packet = self._build_hs_packet(
              int(hue), 
              int(sat),
              brightness_pct
          )
          
          await self._send_command(packet)
      
      def _build_hs_packet(self, hue: int, sat: int, bright: int) -> bytes:
          """
          Build HS color command packet with correct bit packing.
          Java reference: tc/d.java method c() lines 19-35
          """
          # Use 21-byte packet format for BLE
          packet = bytearray(21)
          packet[0:8] = b'\x00\x00\x80\x00\x00\x0d\x0e\x0b'  # Header
          packet[8] = 0x3B   # HSV command prefix
          packet[9] = 0xA1   # Mode = Symphony HSV
          # Correct bit-packing for hue+saturation
          packed = (hue << 7) | (sat & 0x7F)
          packet[10] = (packed >> 8) & 0xFF  # High byte
          packet[11] = packed & 0xFF         # Low byte
          packet[12] = bright & 0xFF
          # Bytes 13-20 remain 0x00
          return bytes(packet)

JAVA SOURCE FILE REFERENCE INDEX (for HSV/Symphony commands):
-------------------------------------------------------------
  File Path                                                    | Key Content
  -------------------------------------------------------------|--------------------------------------------
  tc/d.java                                                    | HSV command builder methods a(), b(), c()
    - Line 8-12: method a() - RGB color to HSV command
    - Line 14-17: method b() - RGB color with mode parameter
    - Line 19-35: method c() - Full HSV command builder (13 bytes)
    - Line 37-43: method d() - Effect command (5 bytes, 0x38 prefix)
  
  g2/c.java                                                    | Byte packing/unpacking utilities
    - Line 15-17: method a() - Unpack 16-bit from 2 bytes (little-endian)
    - Line 19-21: method b() - Pack 16-bit to 2 bytes (big-endian)
    - Line 23-25: method c() - Pack 16-bit to 2 bytes (little-endian)
  
  com/zengge/wifi/Device/Type/Ctrl_Mini_RGB_Symphony_0xa1.java | Symphony device implementation
    - Line 60-68: method b() - Get packed hue+saturation from state
    - Line 88-95: method n() - Set packed hue+saturation to state
    - Implements interface hd.h for HSV state handling
  
  com/zengge/wifi/Device/BaseType/RGBSymphonyDeviceInfo.java   | Symphony base class
    - Base class for all Symphony devices (productId 161)
  
  com/zengge/wifi/Device/BaseType/RGBNewSymphonyDeviceInfo.java| New Symphony base class
    - Line 79-85: method b() - Get packed hue+saturation
    - Line 88-94: method n() - Set packed hue+saturation
    - Base class for newer Symphony devices (productId 162+)
  
  hd/h.java                                                    | HSV interface definition
    - Line 5: int b() - Get packed hue+saturation
    - Line 7: void n(int) - Set packed hue+saturation
  
  com/zengge/wifi/FragmentUniteControl.java                    | UI control using tc.d.c()
    - Lines 411-520: Various calls to tc.d.c() with different modes


10.5.3 FIELD OFFSETS CLARIFICATION (RAW MANUFACTURER PAYLOAD)
--------------------------------------------------------------
All offsets below are zero-indexed from the start of the manufacturer data payload
(Type 255 value from scanRecord.getBytes(), or getManufacturerSpecificData() result).

BYTE-LEVEL STRUCTURE (first 16 bytes):

  Byte | Field           | Description
  -----|-----------------|----------------------------------------------------
  0    | sta             | Status/type byte (device-specific flags)
  1    | manufacturer_hi | Upper 8 bits of 16-bit manufacturer ID
  2    | manufacturer_lo | Lower 8 bits of 16-bit manufacturer ID  
  3    | bleVersion      | BLE protocol version (determines command framing)
  4-9  | MAC address     | 6-byte MAC in display order (no reversal needed)
  10   | productId_hi    | Upper 8 bits of 16-bit product ID
  11   | productId_lo    | Lower 8 bits of 16-bit product ID
  12   | firmwareVer     | Firmware version (low byte; high byte in byte 14 for bleVersion >= 6)
  13   | ledVersion      | LED version (determines feature availability)
  14   | checkKeyFlag(2) | Bits 0-1: checkKeyFlag; Bits 2-7: firmwareVer high byte (bleVersion >= 6)
  15   | firmwareFlag    | Bits 0-4: firmwareFlag (5 bits)

BIT PACKING DETAILS:

Manufacturer ID (bytes 1-2, big-endian):
  manufacturer = (byte[1] & 0xFF) << 8 | (byte[2] & 0xFF)

  Valid manufacturer ID ranges (all start with 0x5A high byte):
    - 0x5A53-0x5A5D (23123-23133): Specific device IDs
    - 0x5A20-0x5A2F (23072-23087): Range 1
    - 0x5A60-0x5A6F (23136-23151): Range 2
    - 0x5A70-0x5A7F (23152-23167): Range 3
    - 0x5A80-0x5A8F (23168-23183): Range 4

Product ID (bytes 10-11, big-endian):
  productId = (byte[10] & 0xFF) << 8 | (byte[11] & 0xFF)

Extended Firmware Version (bleVersion >= 6):
  firmwareVer = (byte[12] & 0xFF) | ((byte[14] >> 2) << 8)
  - Byte 12 contains low 8 bits
  - Byte 14 bits 2-7 contain high 6 bits (shifted left by 8)

CheckKeyFlag and FirmwareFlag (bleVersion >= 5):
  checkKeyFlag = byte[14] & 0x03  // 2 bits (0-3)
  firmwareFlag = byte[15] & 0x1F  // 5 bits (0-31)

State Data (bleVersion >= 5):
  - Bytes 16-26 (11 bytes) contain device state
  - Bytes 27-28 contain RFU (reserved for future use)
  
State Data (bleVersion >= 7 with Type 22 service data):
  - State comes from Type 255 manufacturer data, bytes 3-26 (24 bytes)
  - If manufacturer data length >= 29, last byte is iconFlag

Source: ZGHBDevice.java - setDeviceInfo(), getManufacturer(), newDevice() methods

10.5.4 WORKED EXAMPLE: DECODE MANUFACTURER DATA → FEATURES
----------------------------------------------------------
Sample manufacturer data (hex, zero-indexed bytes shown):

  0:53 1:05 2:08 3:65 4:F0 5:0C 6:DA 7:81 8:00 9:1D 10:0F 11:02 12:01 13:01 14:24 15:61 16:0F 17:64 18:64 19:50 20:FF 21:14 22:02 23:00 24:1C 25:00 26:00

Step-by-step:
- Header (0–1): 0x53 0x05 → vendor-specific status/flags (not needed for HA feature mapping).
- MAC (2–7): 08:65:F0:0C:DA:81.
- Device info (from 8 onward):
  - Byte 9 = 0x1D → interpreted as `productId = 29` (FillLight_0x1D) per mapping.
  - Subsequent bytes contain version/flags (exact meanings vary by family). Common fields observed include firmware/LED version indicators and capability flags.

Feature inference (initial):
- Interpreting byte 9 as `productId = 29` → FillLight_0x1D.
- NOTE: FillLight0x1D is a "stub" device class in the app (extends BaseDeviceInfo directly
  with no capability interfaces). This means FillLight devices can have VARYING capabilities
  (some may be CCT-only, others may have full RGBCW). Capabilities MUST be determined
  dynamically from state queries, not from the productId alone.
- For Home Assistant: treat FillLight_0x1D as potentially RGBCW until validated.

Caveat and resolution:
- Field layouts vary slightly across families. If the device empirically supports RGB and WW/CW, prioritize capability detection via state queries and `ledVersion` over a single-byte `productId` guess.
- For Home Assistant: perform an initial state query after connect; if RGB channels respond and white channels exist, set capabilities to RGBCW regardless of the provisional productId inference.

Implementation tips:
- Always extract MAC from bytes 2–7.
- Use byte 9 as `productId` for this family as a provisional value; validate capabilities via a state query.
- Combine `productId` with any available `ledVersion` bytes to refine capabilities when needed.

10.5.5 CAPABILITY VALIDATION STRATEGY
--------------------------------------
- Always validate capabilities by issuing a state/query command on first connect.
- If RGB values are accepted and reflected in reported state, set `has_rgb = true`.
- If warm/cool white controls respond distinctly, set `has_ww = true`, `has_cw = true`.
- Persist learned capabilities keyed by MAC to avoid repeated probing.

10.5.6 HOW CAPABILITY DETECTION WORKS
-------------------------------------
- Signals in advertisement:
  - `productId` and `ledVersion` hint the device family (see 10.5.2). These are reliable for broad capability classes (RGB-only, RGBCW, CCT), but families vary.
  - On BLE version ≥ 7, devices may include an extended tail in the advertisement that the app slices into `stateInfo` and `devInfo`. Some flags in this tail correlate with features, but they are UI-facing and not standardized enough for HA.

Java Source (ZGHBDevice.java - BLE≥7 extended advertisement parsing):
```java
if (zGHBDevice.getBleVersion() >= 7) {
    byte[] state = new byte[24];
    System.arraycopy(advData, 3, state, 0, 24);  // Extract 24-byte state
    zGHBDevice.setState(state);
    if (advData.length >= 29) {
        zGHBDevice.setIconFlag(advData[advData.length - 1]);  // Tail byte = iconFlag
    }
} else {
    int stateLen = advData.length - 3;
    byte[] state = new byte[stateLen];
    System.arraycopy(advData, 3, state, 0, stateLen);
    zGHBDevice.setState(state);
}
```
For HA: iconFlag is a UI hint (product icon selection); ignore for capability detection.
- Byte pattern to get more capability data:
  - There isn’t a magic advertisement byte that guarantees full capabilities. Instead, use an active query.
  - Send the standard “query state” command (e.g., cmdId 0x81 family) after GATT connect. Devices respond with a payload that includes current channel values; presence of RGB channels and distinct WW/CW fields confirms capabilities.
  - If the device supports protocol v1 (bleVersion ≥ 8), use the v1 transport; otherwise v0. The command content is the same at the logic level; only framing differs.
- Practical detection flow (Home Assistant):
  1) Parse advertisement: extract MAC (bytes 2–7), provisional `productId` (family-specific offset), and `ledVersion`.
  2) Choose write protocol v0/v1 via `bleVersion`.
  3) Issue a state/query command; parse response:
     - If response carries RGB channel tuple (R,G,B), set `has_rgb = true`.
     - If response carries separate warm and cool white values, set `has_ww = true`, `has_cw = true`.
  4) Persist capabilities keyed by MAC.
- Rationale:
  - Static mapping is fast but can misclassify edge families.
  - Active query is definitive and cheap; devices that don’t support a channel simply ignore or NACK writes/queries for that channel.

10.5.7 QUERY COMMAND BYTES AND SAMPLE RESPONSES
-----------------------------------------------
- Command family: “Query State” (commonly referred to as 0x81 group in decompiled code). The logical payload requests current color/white/brightness values. Transport framing differs by protocol version.

- v0 Transport (bleVersion < 8):
  - Upper layer fields: ack=0x00, protect=0x00, seq=auto, cmdId=0x81, payload=[] (or minimal selector).
  - Lower v0 framing: generator(...) wraps upper with segmentation headers respecting MTU≈255.
  - Practical implementation: build an “empty” query payload and send; the device returns a state blob.

- v1 Transport (bleVersion ≥ 8):
  - Same upper layer semantics (cmdId=0x81).
  - Lower v1 framing: generatorV1(...) uses compact headers for MTU≈512.

- Example request (logical view):
  - Upper packet bytes (pre-framing): [cmdId=0x81, len=0x00] — many devices accept no subfields and return full state.
  - If a selector is required on some families, payload may include a channel mask; start with empty and fall back to mask if the device returns no data.

- Sample RGBCW response (logical fields):
  - Channels: R=0x64, G=0x32, B=0x10, WW=0x50, CW=0x40, Brightness=0x64.
  - Mode indicator: may include 0x5A (RGB mode) when reporting combined RGB state.
  - Decoding rule: presence of separate WW and CW bytes → has_ww=true, has_cw=true; presence of R/G/B tuple → has_rgb=true.

- Sample RGB-only response:
  - Channels: R=0x64, G=0x32, B=0x10; no WW/CW fields.
  - Brightness present; color temperature absent.
  - Set has_rgb=true; has_ww=false; has_cw=false.

- Edge behavior:
  - Some devices compress white into a single W byte when only one white channel exists; treat single W as WW with CW=false.
  - If the device ignores 0x81, try the legacy “get state” opcode family used alongside 0x31/0x41 command sets; still apply the same detection logic.

- HA implementation snippet (pseudocode):
  - Build upper packet: cmdId=0x81, payload=[].
  - Frame with v0/v1 per bleVersion.
  - Send, parse response into channel map; set capability flags accordingly.

10.5.8 DYNAMIC CAPABILITY DETECTION - DETAILED IMPLEMENTATION
-------------------------------------------------------------
For devices like FillLight_0x1D where the static productId doesn't reliably indicate
capabilities, use this dynamic detection algorithm.

QUICK REFERENCE - ESSENTIAL COMMANDS:
  Purpose          | Command Bytes                                    | Response
  -----------------|--------------------------------------------------|------------------
  Query State      | [0x81, 0x8A, 0x8B, 0x40]                         | 14 bytes, see below
  Set RGBCW        | [0x31, R, G, B, WW, CW, 0x5A, persist, checksum] | None expected
  Power ON         | [0x11, 0x1A, 0x1B, 0xF0, 0xE6]                   | None expected
  Power OFF        | [0x11, 0x1A, 0x1B, 0x0F, 0x55]                   | None expected
  Set Brightness   | [0x47, brightness, checksum]                     | None expected

OVERVIEW:
The app dynamically determines what color channels a device supports by:
1. Sending a state query command (0x81)
2. Parsing the response to extract all channel values
3. Inferring capabilities from which channels have meaningful values or respond to control

STATE QUERY COMMAND:
  Bytes: [0x81, 0x8A, 0x8B, checksum]
  
  Construction:
    cmd[0] = 0x81  (command opcode)
    cmd[1] = 0x8A  (sub-command 1)
    cmd[2] = 0x8B  (sub-command 2)
    cmd[3] = (0x81 + 0x8A + 0x8B) & 0xFF  = 0x40 (checksum)
    
  Full command: [0x81, 0x8A, 0x8B, 0x40]

STATE RESPONSE FORMAT (14 bytes):
  Source: tc/b.java method c() lines 47-62

  Byte | Field Name          | DeviceState Field | Description
  -----|---------------------|-------------------|----------------------------------
  0    | Header              | -                 | 0x81 (response identifier)
  1    | Mode                | f23859c           | Current mode (0-255)
  2    | Power State         | -                 | 0x23 = ON, other = OFF
  3    | Mode Type           | f23862f           | Mode sub-type (static=97,98,99)
  4    | Speed               | f23863g           | Effect speed (0-255)
  5    | Value1              | f23864h           | Device-specific
  6    | Red (R)             | f23865j           | Red channel (0-255)
  7    | Green (G)           | f23866k           | Green channel (0-255)
  8    | Blue (B)            | f23867l           | Blue channel (0-255)
  9    | Warm White (WW)     | f23868m           | Warm white channel (0-255)
  10   | Brightness          | -                 | Overall brightness (0-255)
  11   | Cool White (CW)     | f23869n           | Cool white channel (0-255)
  12   | Reserved            | f23870p           | Reserved/device-specific
  13   | Checksum            | -                 | Sum of bytes 0-12 mod 256

CHANNEL VALUE ACCESSOR METHODS (from BaseDeviceInfo.java):
  Method | Returns           | State Field | Byte Index
  -------|-------------------|-------------|------------
  J()    | RGB as Color int  | f23865j,k,l | 6,7,8
  v0()   | Warm White value  | f23868m     | 9
  L()    | Cool White value  | f23869n     | 11

CAPABILITY DETECTION ALGORITHM:

  def detect_capabilities(response: bytes) -> dict:
      """
      Detect device capabilities from state query response.
      Returns dict with has_rgb, has_ww, has_cw, is_dimmable flags.
      """
      if len(response) < 14 or response[0] != 0x81:
          return None
      
      # Verify checksum
      expected_checksum = sum(response[:13]) & 0xFF
      if response[13] != expected_checksum:
          return None
      
      # Extract channel values
      r = response[6] & 0xFF
      g = response[7] & 0xFF
      b = response[8] & 0xFF
      ww = response[9] & 0xFF
      brightness = response[10] & 0xFF
      cw = response[11] & 0xFF
      mode_type = response[3] & 0xFF
      
      # Static modes (non-effect) are 97, 98, 99 (0x61, 0x62, 0x63)
      is_static_mode = mode_type in [97, 98, 99]
      
      capabilities = {
          'has_rgb': False,
          'has_ww': False,
          'has_cw': False,
          'is_dimmable': brightness > 0
      }
      
      # Method 1: Check if channel values are present
      # (values > 0 suggest the channel is used)
      if r > 0 or g > 0 or b > 0:
          capabilities['has_rgb'] = True
      if ww > 0:
          capabilities['has_ww'] = True
      if cw > 0:
          capabilities['has_cw'] = True
      
      return capabilities

PROBING FOR ACCURATE CAPABILITY DETECTION:
If the device is currently OFF or in an effect mode, channel values may all be 0.
Use active probing to definitively detect capabilities:

  PROBE SEQUENCE:
  1. Query current state and save it
  2. Send RGB color command: set R=50, G=0, B=0
  3. Query state - if R is now ~50, device has RGB
  4. Send WW command: set WW=50, CW=0
  5. Query state - if WW is now ~50, device has WW
  6. Send CW command: set WW=0, CW=50  
  7. Query state - if CW is now ~50, device has CW
  8. Restore original state
  9. Store detected capabilities by MAC

  PROBE COMMANDS:
  
  RGB Probe (set R=50, G=0, B=0):
    Command: [0x31, 0x5A, 0x32, 0x00, 0x00, checksum]
    Or mini format for RGB-only: [0x31, R, G, B, checksum]
    
  WW Probe (set warm white to 50):
    For CCT devices: Use CCT command with warm bias
    Mode byte: 0x61 (static warm)
    
  CW Probe (set cool white to 50):
    For CCT devices: Use CCT command with cool bias
    Mode byte: 0x61 (static cool)

  RESPONSE VALIDATION:
    After each probe command, send state query [0x81, 0x8A, 0x8B, 0x40]
    Check if the corresponding channel value changed.

CAPABILITY PERSISTENCE:
Once detected, persist capabilities keyed by MAC address:
  
  storage_key = f"zengee_caps_{mac_address}"
  capabilities = {
      "has_rgb": true,
      "has_ww": true, 
      "has_cw": true,
      "is_dimmable": true,
      "detected_at": "2024-01-15T10:30:00Z"
  }

HOME ASSISTANT IMPLEMENTATION PSEUDOCODE:

  class ZengeeLight:
      def __init__(self, mac: str, product_id: int):
          self.mac = mac
          self.product_id = product_id
          self.capabilities = self._load_cached_capabilities()
          
      async def async_setup(self):
          if not self.capabilities:
              self.capabilities = await self._detect_capabilities()
              self._save_capabilities()
          
          # Configure HA color modes based on detected capabilities
          if self.capabilities['has_rgb'] and self.capabilities['has_ww']:
              self._color_mode = ColorMode.RGBWW
          elif self.capabilities['has_rgb']:
              self._color_mode = ColorMode.RGB
          elif self.capabilities['has_ww'] and self.capabilities['has_cw']:
              self._color_mode = ColorMode.COLOR_TEMP
          elif self.capabilities['has_ww'] or self.capabilities['has_cw']:
              self._color_mode = ColorMode.WHITE
          else:
              self._color_mode = ColorMode.BRIGHTNESS
      
      async def _detect_capabilities(self) -> dict:
          # Query current state
          response = await self._send_command([0x81, 0x8A, 0x8B, 0x40])
          caps = self._parse_capabilities(response)
          
          # If device is off or uncertain, do active probing
          if not any([caps['has_rgb'], caps['has_ww'], caps['has_cw']]):
              caps = await self._probe_capabilities()
          
          return caps

MODE TYPE VALUES (byte 3 of state response):
  Value | Meaning              | Indicates
  ------|----------------------|------------------------------------------
  97    | Static Solid (0x61)  | Device in solid color mode (RGB or white)
  98    | Static Solid 2       | Alternate solid mode
  99    | Static Solid 3       | Alternate solid mode
  Other | Dynamic/Effect       | Device running an effect/animation

  When mode_type is 97/98/99, the channel values (R,G,B,WW,CW) represent
  the actual current color. When in effect mode, they may not be meaningful.

SPECIAL CASE: STUB DEVICES (like FillLight_0x1D)
Stub device classes in the app return null for capability methods, meaning:
- The app cannot statically determine what channels the device supports
- Capability detection MUST be done dynamically at runtime
- Different hardware variants with the same productId may have different capabilities
- Example: Some FillLight_0x1D devices have full RGBCW, others may be CCT-only

For Home Assistant:
- Never assume capabilities based solely on productId for stub devices
- Always perform the capability detection sequence on first connect
- Log detected capabilities for debugging
- Allow manual capability override in configuration for edge cases

10.5.9 CONTROL COMMANDS FOR EACH CHANNEL TYPE
----------------------------------------------
Once capabilities are detected, use these commands to control each channel type.

A) RGB COLOR CONTROL (0x31 command family)
------------------------------------------
Full RGBCW command - sets all channels at once:
  Function: tc.b.s(r, g, b, warm, cold, persist)
  
  Format (9 bytes):
    Byte | Value           | Description
    -----|-----------------|------------------------------------
    0    | 0x31 (49)       | Command opcode
    1    | 0-255           | Red value
    2    | 0-255           | Green value
    3    | 0-255           | Blue value
    4    | 0-255           | Warm White value
    5    | 0-255           | Cool White value
    6    | 0x5A (90)       | Mode = RGB/Color mode
    7    | 0xF0 or 0x0F    | 0xF0=persist, 0x0F=temporary
    8    | checksum        | Sum of bytes 0-7 mod 256

  Examples:
    Set pure red:        [0x31, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x5A, 0x0F, 0x2F]
    Set pure green:      [0x31, 0x00, 0xFF, 0x00, 0x00, 0x00, 0x5A, 0x0F, 0x30]
    Set pure blue:       [0x31, 0x00, 0x00, 0xFF, 0x00, 0x00, 0x5A, 0x0F, 0x31]
    Set RGB + WW:        [0x31, 0x80, 0x40, 0x20, 0x64, 0x00, 0x5A, 0x0F, 0xF9]
    Set WW only (100):   [0x31, 0x00, 0x00, 0x00, 0x64, 0x00, 0x5A, 0x0F, 0x0F]
    Set CW only (100):   [0x31, 0x00, 0x00, 0x00, 0x00, 0x64, 0x5A, 0x0F, 0x0F]

  Python implementation:
    def set_rgbcw(r, g, b, ww, cw, persist=False):
        cmd = bytearray([
            0x31,           # command opcode
            r & 0xFF,       # red
            g & 0xFF,       # green
            b & 0xFF,       # blue
            ww & 0xFF,      # warm white
            cw & 0xFF,      # cool white
            0x5A,           # mode indicator
            0xF0 if persist else 0x0F  # persist flag
        ])
        cmd.append(sum(cmd) & 0xFF)  # checksum
        return bytes(cmd)

RGB-only command (simplified):
  Function: tc.b.t(r, g, b, persist)
  
  Format (9 bytes):
    Byte | Value           | Description
    -----|-----------------|------------------------------------
    0    | 0x31 (49)       | Command opcode
    1    | 0-255           | Red value
    2    | 0-255           | Green value
    3    | 0-255           | Blue value
    4    | 0x00            | Reserved
    5    | 0x00            | Reserved
    6    | 0xF0 (-16)      | Mode = RGB active
    7    | 0xF0 or 0x0F    | Persist flag
    8    | checksum        | Sum of bytes 0-7 mod 256

B) WHITE/CCT CONTROL
--------------------
For CCT-only devices or when setting white channels independently:

CCT command using color temperature (0x35 family):
  Function: tc.b.G(ww_value, cw_value, brightness_float)
  
  Format (9 bytes):
    Byte | Value           | Description
    -----|-----------------|------------------------------------
    0    | 0x35 (53)       | Command opcode
    1    | 0xB1 (-79)      | Sub-opcode for CCT mode
    2    | 0-100           | Color temperature ratio (0=warm, 100=cool)
    3    | 0-100           | Brightness percentage
    4    | 0x00            | Reserved
    5    | 0x00            | Reserved
    6    | temp_hi         | Temperature value high byte (if needed)
    7    | temp_lo         | Temperature value low byte (if needed)
    8    | checksum        | Sum of bytes 0-7 mod 256

  Color temperature calculation:
    # ww = warm white value, cw = cool white value
    total = ww + cw
    if total == 0:
        ct_ratio = 0
    else:
        ct_ratio = (cw * 100) / total  # 0 = full warm, 100 = full cool
    brightness_pct = (total / 255.0) * 100

Simple white command (if device only has single white):
  Use warm white position (byte 4) in the 0x31 RGBCW command with RGB=0.

C) BRIGHTNESS CONTROL (global)
------------------------------
Set overall brightness affecting all channels:

  Function: tc.b.j(brightness)
  
  Format (3 bytes):
    Byte | Value           | Description
    -----|-----------------|------------------------------------
    0    | 0x47 (71)       | Command opcode
    1    | 0-255           | Brightness (0=off, 255=max)
    2    | checksum        | Sum of bytes 0-1 mod 256

  Examples:
    50% brightness:  [0x47, 0x7F, 0xC6]  # 0x7F = 127
    100% brightness: [0x47, 0xFF, 0x46]
    Off:             [0x47, 0x00, 0x47]

D) POWER CONTROL
----------------
Toggle device power on/off:

  Function: tc.b.m(power_on) - primary power command
  
  Format (5 bytes):
    Byte | Value           | Description
    -----|-----------------|------------------------------------
    0    | 0x11            | Command opcode
    1    | 0x1A            | Sub-opcode 1
    2    | 0x1B            | Sub-opcode 2
    3    | 0xF0 or 0x0F    | 0xF0=ON, 0x0F=OFF
    4    | checksum        | Sum of bytes 0-3 mod 256

  Examples:
    Power ON:  [0x11, 0x1A, 0x1B, 0xF0, 0xE6]
    Power OFF: [0x11, 0x1A, 0x1B, 0x0F, 0x55]

  Alternative power commands (try if 0x11 doesn't work):
    Type 2: [0x62, 0x6A, 0x6B, state, checksum]
    Type 3: [0x73, 0x7A, 0x7B, state, checksum]
    Type 4: [0x32, 0x3A, 0x3B, state, checksum]
    Type 5: [0x22, 0x2A, 0x2B, state, checksum]

E) STATE QUERY
--------------
Query current device state (used for capability detection):

  Function: tc.b.l()
  
  Format (4 bytes):
    [0x81, 0x8A, 0x8B, 0x40]
    
  Response parsing: See section 10.8 STATE QUERY COMMAND for full response format.

10.5.10 CAPABILITY PROBING SEQUENCE
-----------------------------------
For devices with unknown capabilities (stub devices), use this probing sequence:

  STEP 1: Save current state
    Send: [0x81, 0x8A, 0x8B, 0x40]
    Save response for restoration later
    
  STEP 2: Probe RGB capability
    Send: [0x31, 0x32, 0x00, 0x00, 0x00, 0x00, 0x5A, 0x0F, checksum]
    Wait 200ms
    Query: [0x81, 0x8A, 0x8B, 0x40]
    If response[6] (R) is approximately 0x32 → has_rgb = true
    
  STEP 3: Probe Warm White capability  
    Send: [0x31, 0x00, 0x00, 0x00, 0x32, 0x00, 0x5A, 0x0F, checksum]
    Wait 200ms
    Query: [0x81, 0x8A, 0x8B, 0x40]
    If response[9] (WW) is approximately 0x32 → has_ww = true
    
  STEP 4: Probe Cool White capability
    Send: [0x31, 0x00, 0x00, 0x00, 0x00, 0x32, 0x5A, 0x0F, checksum]
    Wait 200ms
    Query: [0x81, 0x8A, 0x8B, 0x40]
    If response[11] (CW) is approximately 0x32 → has_cw = true
    
  STEP 5: Restore original state
    Send original RGBCW values from Step 1

  IMPLEMENTATION NOTES:
  - Use a small test value (0x32 = 50) to minimize visual disruption
  - Allow ±10% tolerance when checking response values
  - Some devices may not update state immediately; retry with longer delay
  - If device doesn't respond to state query, fall back to productId hints

Python probing implementation:
  async def probe_capabilities(self) -> dict:
      caps = {'has_rgb': False, 'has_ww': False, 'has_cw': False}
      
      # Save original state
      original = await self.query_state()
      
      # Probe RGB
      await self.send_command(self.build_rgbcw(50, 0, 0, 0, 0))
      await asyncio.sleep(0.2)
      state = await self.query_state()
      if abs(state['red'] - 50) < 15:
          caps['has_rgb'] = True
      
      # Probe WW
      await self.send_command(self.build_rgbcw(0, 0, 0, 50, 0))
      await asyncio.sleep(0.2)
      state = await self.query_state()
      if abs(state['ww'] - 50) < 15:
          caps['has_ww'] = True
      
      # Probe CW
      await self.send_command(self.build_rgbcw(0, 0, 0, 0, 50))
      await asyncio.sleep(0.2)
      state = await self.query_state()
      if abs(state['cw'] - 50) < 15:
          caps['has_cw'] = True
      
      # Restore original
      await self.send_command(self.build_rgbcw(
          original['red'], original['green'], original['blue'],
          original['ww'], original['cw']
      ))
      
      return caps

10.6 ADDRESSABLE VS. GLOBAL-COLOR LEDS
--------------------------------------
- Indicators from product family:
  - Classes named “Symphony” (e.g., `Ctrl_Mini_RGB_Symphony_*` with productIds 161–169) and “Digital_Light” typically indicate addressable LEDs (individually controlled pixels or segments).
  - Plain `RGB`, `RGBW`, `RGBCW`, `CCT`, `Dim` classes typically indicate global color (entire strip/bulb changes together).

- Advertisement hints:
  - No stable adv flag was found that universally marks addressable capability. Treat `productId` membership in Symphony/Digital families as the best static hint.

- Definitive detection via command behavior:
  - Addressable devices accept effect/pixel/segment commands beyond simple 0x31/0x41 color writes (e.g., running patterns, gradients, per-segment brightness).
  - When you issue effect commands (pattern IDs, speed, segment count) the device responds/executes them; global-color devices ignore or constrain these.

- Practical HA detection flow:
  1) From `productId`, set provisional `is_addressable = true` for Symphony/Digital families; else false.
  2) On first connect, try a lightweight effect query/set:
     - Send an effect select command with a simple pattern (e.g., rainbow) and minimal params.
     - If the device acknowledges/changes behavior distinctly from solid color, mark `is_addressable = true`.
  3) Persist learned `is_addressable` by MAC.

- Implementation guidance:
  - Use normal color commands for global-color devices (0x31 family with mode 0x5A or simplified variants).
  - For addressable devices, prefer effect APIs (pattern ID, speed, segment count) and avoid mapping RGB per-pixel unless necessary.
  - If the device supports segment count in responses or configuration (some families report number of segments/pixels), store it for HA effects.

10.7 EFFECTS ENUMERATION AND CONTROL
------------------------------------
- Static hints from product family:
  - Symphony/Digital families expose a list of builtin effects (e.g., rainbow, meteor, breathing, chase) via pattern IDs. Global-color families may expose a smaller set (breathing, strobe) or none.

- Discovering supported effects:
  - Try an “effects list” query if available; some families respond with a table of pattern IDs and names. If not documented, probe by sending small pattern IDs (e.g., 0x01..0x10) and observe accept/ignore behavior.
  - Acknowledgement behavior: accepted pattern IDs return success or change light behavior; unsupported IDs are NACKed or ignored.

- Control parameters commonly supported:
  - Pattern ID: selects effect type.
  - Speed: 0–255 or a bounded range.
  - Brightness: global cap across effects.
  - Segment count / pixel length: for addressable devices; may be fixed or configurable.
  - Color slots: some effects accept 1–3 colors to compose the animation.

- Command family:
  - Effects often share the 0x31/0x41 write family with distinct opcodes or sub-modes (e.g., mode values differing from 0x5A RGB solid). If the device ignores solid color writes but reacts to pattern IDs, treat it as addressable.

- HA enumeration strategy:
  1) If productId indicates Symphony/Digital, seed a default effect list (rainbow, meteor, breathing, chase, gradient, strobe).
  2) Probe pattern IDs in a safe range (e.g., 1–16) at low brightness for a short duration.
  3) Record IDs that produce a visible change; store as supported effects.
  4) Persist learned effects by MAC. Optionally attach parameter ranges (speed min/max; color slot count).

- Safety and UX:
  - Keep probing brief and at moderate brightness to avoid nuisance.
  - Provide a user option to disable effect probing and rely on defaults.

10.8 POWER COMMANDS (ON/OFF)
----------------------------
- Two patterns observed in devices:

- A) Mini-command power opcodes
  - Purpose: direct power control independent of color commands.
  - Opcodes: Family-specific (0x11, 0x22, 0x32, 0x62, 0x73, 0x62); NOT universal 0x23/0x24.
  - Placement: 5-byte format with persist flag at byte[3]; checksum at byte[4].
  - Transport: still uses v0/v1 framing based on `bleVersion`, but payload is short and fixed-format.
  - Guidance (HA): Use the appropriate family method; 0x23/0x24 may appear in state responses (response[2]==35 indicates ON).

Java Source (tc/b.java - power command builders):
```java
// Method m: General power control
public static byte[] m(boolean powerOn) {
    byte[] cmd = new byte[5];
    cmd[0] = 17;   // 0x11 - opcode
    cmd[1] = 26;   // 0x1A - sub-opcode
    cmd[2] = 27;   // 0x1B - sub-opcode
    cmd[3] = powerOn ? (byte) 0xF0 : (byte) 0x0F;  // Persist flag
    cmd[4] = checksum(cmd, 4);
    return cmd;
}

// Method n: Broadcast power control
public static byte[] n(boolean powerOn) {
    byte[] cmd = new byte[5];
    cmd[0] = 98;  // 0x62
    cmd[1] = 106; // 0x6A
    cmd[2] = 107; // 0x6B
    cmd[3] = powerOn ? (byte) 0xF0 : (byte) 0x0F;
    cmd[4] = checksum(cmd, 4);
    return cmd;
}

// Methods o, p, q follow similar 5-byte pattern with opcodes:
// o: [0x73, 0x7A, 0x7B, persist, checksum]
// p: [0x32, 0x3A, 0x3B, persist, checksum]
// q: [0x22, 0x2A, 0x2B, persist, checksum]
```

Note: The user's observation of 0x23 for ON likely refers to the power state indicator
in the 0x81 query response (byte[2] == 0x23 means device is ON), not a command opcode.

- B) Rich color/state command families (0x31/0x41)
  - Purpose: set RGB/WW/CW/brightness and sometimes include power flags.
  - Mode bytes:
    - 0x5A: RGB solid/color mode selector in the 0x31 family.
    - 0xF0: simplified solid-color variant used by some families; not a power opcode.
  - Relationship to power: Color commands don't directly control power - use mini-command power functions (m, n, o, p, q) to toggle power separately.

- Practical rules:
  - Use one of the 5-byte power commands (0x11, 0x22, 0x32, 0x62, 0x73 families) for power control.
  - The value 0x23 is a STATE indicator in responses (byte[2]==0x23 means ON), NOT a command opcode.
  - Use 0x31/0x41 with 0x5A (or 0xF0 variant where applicable) for color changes.
  - Do not conflate 0xF0/0x0F with power; they are mode/parameter values inside color commands, not ON/OFF.
  - Continue to frame writes with v0/v1 transport selected by `bleVersion`.

- Implementation note:
  - Some device families may implicitly turn ON when receiving color commands with non-zero brightness.
  - To ensure power state, first send an explicit power command from the mini set, then confirm via state query.
  - Different product types may respond to different power command families. Try them in order: m() [0x11], n() [0x62], etc.

Python example - Power ON:
  def power_on():
      # Try 0x11 family first
      cmd = bytes([0x11, 0x1A, 0x1B, 0xF0, 0])  # checksum placeholder
      cmd = cmd[:4] + bytes([sum(cmd[:4]) & 0xFF])
      return cmd

  def power_off():
      cmd = bytes([0x11, 0x1A, 0x1B, 0x0F, 0])  # checksum placeholder
      cmd = cmd[:4] + bytes([sum(cmd[:4]) & 0xFF])
      return cmd

10.6 BRIGHTNESS COMMANDS
------------------------
Global brightness adjustment (affects all active channels):

COMMAND: Set Brightness
Function signature: j(brightness)

  BYTE | FIELD           | VALUE
  -----|-----------------|------------------
  0    | Command opcode  | 0x47 (71)
  1    | Brightness      | 0-255 (0=off, 255=max)
  2    | Checksum        | Sum of bytes 0-1

EXAMPLE - Set 50% brightness:
  [0x47, 0x7F, 0xC6]

10.7 POWER ON/OFF COMMANDS
--------------------------

COMMAND: Power On/Off
Function signatures: m, n, o, p, q (various device types)

Generic format (5 bytes):
  [OpCode, SubCmd1, SubCmd2, State, Checksum]
  
  State byte:
    0xF0 = Power ON
    0x0F = Power OFF

EXAMPLES:
  Power ON (type 1):  [0x11, 0x1A, 0x1B, 0xF0, checksum]
  Power OFF (type 1): [0x11, 0x1A, 0x1B, 0x0F, checksum]
  
  Power ON (type 2):  [0x62, 0x6A, 0x6B, 0xF0, checksum]
  Power OFF (type 2): [0x62, 0x6A, 0x6B, 0x0F, checksum]

10.8 STATE QUERY COMMAND
------------------------

COMMAND: Query Device State
Function: l()

  BYTE | FIELD           | VALUE
  -----|-----------------|------------------
  0    | Command opcode  | 0x81 (-127 signed)
  1    | Sub-command 1   | 0x8A (-118 signed)
  2    | Sub-command 2   | 0x8B (-117 signed)
  3    | Checksum        | Sum of bytes 0-2

EXAMPLE:
  [0x81, 0x8A, 0x8B, checksum]

Response format (14 bytes) - VERIFIED from tc/b.java lines 47-62:
  Byte 0:  0x81 (response header, -127 signed)
  Byte 1:  Mode value (0-255)
  Byte 2:  Power state (0x23 = ON, any other value = OFF)
  Byte 3:  Mode Type (97/98/99 = static solid, other = effect/dynamic)
  Byte 4:  Speed (effect speed, 0-255)
  Byte 5:  Value1 (device-specific)
  Byte 6:  R (Red, 0-255) - field f23865j
  Byte 7:  G (Green, 0-255) - field f23866k
  Byte 8:  B (Blue, 0-255) - field f23867l
  Byte 9:  WW (Warm White, 0-255) - field f23868m
  Byte 10: Brightness (0-255)
  Byte 11: CW (Cool White, 0-255) - field f23869n
  Byte 12: Reserved - field f23870p
  Byte 13: Checksum (sum of bytes 0-12 mod 256)

  NOTE: See section 10.5.8 for detailed capability detection using these fields.

Python parsing example:
  def parse_state_response(response: bytes) -> dict:
      if len(response) < 14 or response[0] != 0x81:
          return None
      # Verify checksum
      if sum(response[:13]) & 0xFF != response[13]:
          return None
      return {
          'power_on': response[2] == 0x23,
          'mode': response[1],
          'red': response[6],
          'green': response[7],
          'blue': response[8],
          'brightness': response[10],
          'raw': response
      }

10.9 TRANSPORT LAYER PROTOCOL
------------------------------
Commands are wrapped in a transport layer before transmission. This handles
packet segmentation and reassembly for commands larger than MTU.

UPPER TRANSPORT LAYER:
  Structure from UpperTransportLayer.java:
    - ack: boolean (acknowledge required)
    - protect: boolean (encryption flag)
    - type: byte (always 0 for HEX mode)
    - seq: byte (sequence number, increments per command)
    - cmdId: byte (command identifier)
    - payload: byte[] (command data)

  Factory method:
    UpperTransportLayer.createUpper(ack, protect, seq, cmdId, payload)

LOWER TRANSPORT LAYER:
  Takes UpperTransportLayer and segments it into MTU-sized packets.
  
  For Protocol Version 0 (255 byte MTU):
    Uses generator() method
    Standard packet format
    
  For Protocol Version 1 (512 byte MTU):
    Uses generatorV1() method
    Optimized packet format
    
PACKET HEADER STRUCTURE (Version 1):

Single-segment packet (fits in MTU):
  Byte 0: Control byte (ack, protect, seq bits)
  Bytes 1-2: Segment info (0x8000 for single segment)
  Byte 3: Command ID
  Bytes 4-5: Payload length (big-endian)
  Bytes 6-8: Total length info
  Bytes 9+: Payload data

Multi-segment packet:
  First segment:
    Control byte with segment flag
    Segment number 0
    Command ID
    Payload length
    First chunk of payload
    
  Middle segments:
    Control byte
    Segment number (1, 2, 3...)
    Continuation of payload
    
  Last segment:
    Control byte with end flag (0x8000 | segment_num)
    Final chunk of payload

10.10 WRITE PROTOCOL FLOW
-------------------------
Complete flow from command to device:

1. Application creates command bytes (e.g., RGB color command)
2. Wrap in Flutter Command object:
     command.cmdId = determined by response requirements
     command.data = raw command bytes
     command.resultId = expected response cmdId (if any)

3. Send to FlutterBleWorker.write():
     write(entityType, mac, command, waitGattResponse, callback)

4. FlutterBleWorker routes to ZGHBDeviceHandler.write():
     write(mac, cmdId, data, waitGattResponse)

5. ZGHBDeviceHandler calls ZGHBWriteUtils.write():
     - Determines protocol version from device BLE version
     - Creates UpperTransportLayer:
         upper = UpperTransportLayer.createUpper(
             ack=waitGattResponse,
             protect=false,
             seq=nextSequenceNumber(),
             cmdId=command.cmdId,
             payload=command.data
         )
     - Encodes to packets:
         if (protocolVersion == 1) {
             packets = LowerTransportLayerEncoder.generatorV1(upper, mtu)
         } else {
             packets = LowerTransportLayerEncoder.generator(upper, mtu)
         }
     - Writes each packet to GATT characteristic

6. For each packet:
     bluetoothGatt.writeCharacteristic(characteristic, packet, WRITE_TYPE_DEFAULT)

7. If ack=true, wait for response via notification characteristic

10.11 MANUFACTURER-SPECIFIC DIFFERENCES
---------------------------------------
While the basic command structure is consistent, different manufacturer IDs
may support different features:

FEATURE DETECTION:
  Based on BLE version field and product ID:
  
  - BLE version < 6: Basic RGB control only
  - BLE version >= 6: 
      * Extended firmware version in byte 14
      * Additional color modes
      * Symphony/effect support
  - BLE version >= 8:
      * Protocol version 1
      * 512 byte MTU support
      * Faster updates

PRODUCT ID VARIATIONS:
  Product ID indicates device capabilities:
  NOTE: Offset depends on format!
    - Format A (29-byte raw): bytes 10-11
    - Format B (27-byte bleak): bytes 8-9
  
  - 0xA2, 0xA3, 0xA6, 0xA9: RGB + Symphony controller variants
  - 0x33 (51): Ctrl_Mini_RGB - RGB only
  - Different IDs support different numbers of addressable LEDs
  - Some support warm/cold white, others RGB only

The write protocol DOES NOT change based on manufacturer ID. The same
packet structure is used across all devices. However:
  - Available commands may differ (some devices don't support certain opcodes)
  - Response formats are consistent
  - Command parameters (RGB values, brightness) are universal

10.12 COMMAND EXAMPLES SUMMARY
------------------------------

OPERATION         | OPCODE | BYTES | EXAMPLE (HEX)
------------------|--------|-------|--------------------------------
Set Red           | 0x31   | 9     | 31 FF 00 00 00 00 5A 0F 2F
Set Green         | 0x31   | 9     | 31 00 FF 00 00 00 5A 0F 30
Set Blue          | 0x31   | 9     | 31 00 00 FF 00 00 5A 0F 31
Set White (W+C)   | 0x31   | 9     | 31 00 00 00 FF FF 5A 0F 31
Set Brightness    | 0x47   | 3     | 47 7F C6 (50% brightness)
Power ON          | 0x11   | 5     | 11 1A 1B F0 [checksum]
Power OFF         | 0x11   | 5     | 11 1A 1B 0F [checksum]
Query State       | 0x81   | 4     | 81 8A 8B [checksum]

ALL COMMANDS MUST:
  1. Include proper checksum as last byte
  2. Be wrapped in transport layer
  3. Be segmented if larger than MTU
  4. Use correct protocol version for device

================================================================================
11. PYTHON IMPLEMENTATION CHECKLIST
================================================================================

To implement this protocol in Python, you will need:

1. BLE SCANNING (using bleak):
   - Scan for devices with "LEDnetWF" or "IOTWF" in name
   - Use advertisement_data.manufacturer_data dictionary
   - Company ID is the dictionary KEY (not in payload!)
   - Accept company IDs in range 23040-23295 (0x5A00-0x5AFF)
   - Payload is 27 bytes (Format B - without company ID)

2. MANUFACTURER DATA PARSING (Format B - 27 bytes):
   - Byte 0: sta
   - Byte 1: ble_version
   - Bytes 2-7: MAC address
   - Bytes 8-9: product_id (big-endian)
   - Byte 10: firmware_ver
   - Byte 11: led_version
   - Byte 12: check_key_flag (bits 0-1)
   - Byte 13: firmware_flag (bits 0-4)
   - Bytes 14-24: state_data (if ble_version >= 5)
   - Bytes 25-26: rfu

3. CONNECTION MANAGEMENT:
   - Connect to device via GATT
   - Service UUID: 0000ffff-0000-1000-8000-00805f9b34fb
   - Write Characteristic: 0000ff01-0000-1000-8000-00805f9b34fb
   - Read/Notify Characteristic: 0000ff02-0000-1000-8000-00805f9b34fb
   - Negotiate MTU (request 512 if ble_version >= 8, else 255)
   - Subscribe to notification characteristic for responses

4. COMMAND GENERATION:
   - Implement command builder functions (RGB, brightness, power, etc.)
   - Calculate checksums correctly
   - Support all command formats

5. TRANSPORT LAYER:
   - Implement UpperTransportLayer structure
   - Implement packet segmentation (LowerTransportLayer)
   - Handle sequence numbers
   - Support both protocol versions

6. WRITE OPERATIONS:
   - Determine protocol version from BLE version (>= 8 → v1, else v0)
   - Wrap commands in transport layer
   - Segment into MTU-sized packets
   - Write packets sequentially
   - Handle acknowledgments if required

7. RESPONSE HANDLING:
   - Listen for notifications
   - Reassemble multi-segment responses
   - Parse state response (14-byte format)
   - Validate checksums on received data

8. ERROR HANDLING:
   - Connection timeouts
   - Invalid manufacturer IDs
   - Checksum mismatches
   - MTU negotiation failures
   - Write operation failures

================================================================================
12. PYTHON TRANSPORT LAYER IMPLEMENTATION
================================================================================

The transport layer is REQUIRED for all commands. Simply sending raw command
bytes WILL NOT WORK. Here's a complete Python implementation:

12.1 UPPER TRANSPORT LAYER
--------------------------
```python
from dataclasses import dataclass
from typing import List

@dataclass
class UpperTransportLayer:
    """Wraps command payload with metadata for transport."""
    ack: bool           # True if response expected
    protect: bool       # False for normal commands
    seq: int            # Sequence number (0-255)
    cmd_id: int         # Command ID (10=with response, 11=no response)
    payload: bytes      # Raw command bytes
    
    @staticmethod
    def create(ack: bool, protect: bool, seq: int, cmd_id: int, payload: bytes) -> 'UpperTransportLayer':
        return UpperTransportLayer(ack, protect, seq & 0xFF, cmd_id & 0xFF, payload)
```

12.2 LOWER TRANSPORT LAYER ENCODER
----------------------------------
```python
def create_ctrl_byte(protect: bool, ack: bool, has_segments: bool, version: int = 0) -> int:
    """Create control byte with flags."""
    ctrl = 0x80  # Bit 7 always set
    if has_segments:
        ctrl |= 0x40  # Bit 6 = segment flag
    if ack:
        ctrl |= 0x20  # Bit 5 = ack flag
    if protect:
        ctrl |= 0x10  # Bit 4 = protect flag
    if version == 1:
        ctrl |= 0x01  # Bit 0 = version 1
    return ctrl

def encode_transport_v0(upper: UpperTransportLayer, mtu: int = 255) -> List[bytes]:
    """
    Encode command for Protocol Version 0 (BLE version < 8).
    Returns list of packets to send sequentially.
    """
    payload = upper.payload
    header_len = 8
    max_payload_first = mtu - header_len
    
    if len(payload) <= max_payload_first:
        # Single packet
        packet = bytearray(len(payload) + header_len)
        packet[0] = create_ctrl_byte(upper.protect, upper.ack, False)
        packet[1] = upper.seq
        packet[2] = 0x80  # Segment info high byte (0x8000 = single)
        packet[3] = 0x00  # Segment info low byte
        packet[4] = (len(payload) >> 8) & 0xFF  # Payload length high
        packet[5] = len(payload) & 0xFF          # Payload length low
        packet[6] = (len(payload) + 1) & 0xFF    # Total length
        packet[7] = upper.cmd_id
        packet[header_len:] = payload
        return [bytes(packet)]
    
    # Multi-segment - calculate number of segments
    segments = []
    max_payload_cont = mtu - 5
    remaining = len(payload)
    offset = 0
    seg_num = 0
    
    while remaining > 0:
        if seg_num == 0:
            # First segment
            chunk_len = min(remaining, max_payload_first)
            packet = bytearray(chunk_len + header_len)
            packet[0] = create_ctrl_byte(upper.protect, upper.ack, True)
            packet[1] = upper.seq
            packet[2] = 0x00  # Segment 0
            packet[3] = 0x00
            packet[4] = (len(payload) >> 8) & 0xFF
            packet[5] = len(payload) & 0xFF
            packet[6] = mtu - 7
            packet[7] = upper.cmd_id
            packet[header_len:] = payload[offset:offset + chunk_len]
        else:
            # Continuation segment
            chunk_len = min(remaining, max_payload_cont)
            is_last = (remaining <= max_payload_cont)
            seg_info = seg_num | (0x8000 if is_last else 0)
            
            packet = bytearray(chunk_len + 5)
            packet[0] = create_ctrl_byte(upper.protect, upper.ack, True)
            packet[1] = upper.seq
            packet[2] = (seg_info >> 8) & 0xFF
            packet[3] = seg_info & 0xFF
            packet[4] = chunk_len
            packet[5:] = payload[offset:offset + chunk_len]
        
        segments.append(bytes(packet))
        offset += chunk_len
        remaining -= chunk_len
        seg_num += 1
    
    return segments

def encode_transport_v1(upper: UpperTransportLayer, mtu: int = 512) -> List[bytes]:
    """
    Encode command for Protocol Version 1 (BLE version >= 8).
    Similar to v0 but with 9-byte header for single packets.
    """
    payload = upper.payload
    header_len = 9
    max_payload_first = mtu - header_len
    
    if len(payload) <= max_payload_first:
        # Single packet
        packet = bytearray(len(payload) + header_len)
        packet[0] = create_ctrl_byte(upper.protect, upper.ack, False, version=1)
        packet[1] = upper.seq
        packet[2] = 0x80
        packet[3] = 0x00
        packet[4] = (len(payload) >> 8) & 0xFF
        packet[5] = len(payload) & 0xFF
        total_len = len(payload) + 1
        packet[6] = (total_len >> 8) & 0xFF
        packet[7] = total_len & 0xFF
        packet[8] = upper.cmd_id
        packet[header_len:] = payload
        return [bytes(packet)]
    
    # Multi-segment encoding similar to v0, with 6-byte continuation headers
    # Implementation follows same pattern as v0
    # ...
    return encode_transport_v0(upper, mtu)  # Fallback for simplicity
```

12.3 COMPLETE WRITE FLOW
------------------------
```python
import asyncio
from bleak import BleakClient

SERVICE_UUID = "0000ffff-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
READ_CHAR_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

class LEDController:
    def __init__(self, address: str, ble_version: int = 0):
        self.address = address
        self.ble_version = ble_version
        self.seq = 0
        self.client = None
        self.response_event = asyncio.Event()
        self.last_response = None
    
    def _next_seq(self) -> int:
        seq = self.seq
        self.seq = (self.seq + 1) & 0xFF
        return seq
    
    def _calc_checksum(self, data: bytes) -> int:
        return sum(data) & 0xFF
    
    def _notification_handler(self, sender, data: bytearray):
        """Handle incoming notifications."""
        self.last_response = bytes(data)
        self.response_event.set()
    
    async def connect(self):
        self.client = BleakClient(self.address)
        await self.client.connect()
        # Request MTU based on BLE version
        # (bleak handles this automatically in most cases)
        # Subscribe to notifications
        await self.client.start_notify(READ_CHAR_UUID, self._notification_handler)
    
    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
    
    async def send_command(self, cmd_bytes: bytes, expect_response: bool = False) -> bytes:
        """Send a command with proper transport wrapping."""
        # Create upper transport layer
        cmd_id = 10 if expect_response else 11
        upper = UpperTransportLayer.create(
            ack=expect_response,
            protect=False,
            seq=self._next_seq(),
            cmd_id=cmd_id,
            payload=cmd_bytes
        )
        
        # Encode to packets
        mtu = 512 if self.ble_version >= 8 else 255
        if self.ble_version >= 8:
            packets = encode_transport_v1(upper, mtu)
        else:
            packets = encode_transport_v0(upper, mtu)
        
        # Send packets
        for packet in packets:
            await self.client.write_gatt_char(WRITE_CHAR_UUID, packet)
        
        # Wait for response if expected
        if expect_response:
            self.response_event.clear()
            try:
                await asyncio.wait_for(self.response_event.wait(), timeout=5.0)
                return self.last_response
            except asyncio.TimeoutError:
                return None
        
        return None
    
    # Convenience methods
    async def power_on(self):
        cmd = bytes([0x11, 0x1A, 0x1B, 0xF0])
        cmd = cmd + bytes([self._calc_checksum(cmd)])
        await self.send_command(cmd)
    
    async def power_off(self):
        cmd = bytes([0x11, 0x1A, 0x1B, 0x0F])
        cmd = cmd + bytes([self._calc_checksum(cmd)])
        await self.send_command(cmd)
    
    async def set_rgb(self, r: int, g: int, b: int, ww: int = 0, cw: int = 0, persist: bool = False):
        cmd = bytes([0x31, r & 0xFF, g & 0xFF, b & 0xFF, ww & 0xFF, cw & 0xFF, 0x5A, 0xF0 if persist else 0x0F])
        cmd = cmd + bytes([self._calc_checksum(cmd)])
        await self.send_command(cmd)
    
    async def set_brightness(self, brightness: int):
        cmd = bytes([0x47, brightness & 0xFF])
        cmd = cmd + bytes([self._calc_checksum(cmd)])
        await self.send_command(cmd)
    
    async def query_state(self) -> dict:
        cmd = bytes([0x81, 0x8A, 0x8B])
        cmd = cmd + bytes([self._calc_checksum(cmd)])
        response = await self.send_command(cmd, expect_response=True)
        
        if response and len(response) >= 14 and response[0] == 0x81:
            return {
                'power_on': response[2] == 0x23,
                'mode': response[1],
                'red': response[6],
                'green': response[7],
                'blue': response[8],
                'brightness': response[10],
            }
        return None

# Usage example
async def main():
    # Replace with actual device address
    device_address = "E4:98:BB:95:EE:8E"
    ble_version = 5  # Get from manufacturer data parsing
    
    controller = LEDController(device_address, ble_version)
    await controller.connect()
    
    try:
        # Query current state
        state = await controller.query_state()
        print(f"Current state: {state}")
        
        # Turn on and set to red
        await controller.power_on()
        await controller.set_rgb(255, 0, 0)
        
        await asyncio.sleep(2)
        
        # Set to green at 50% brightness
        await controller.set_rgb(0, 255, 0)
        await controller.set_brightness(127)
        
    finally:
        await controller.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

================================================================================
END OF DOCUMENT
================================================================================
================================================================================
BLE COMMUNICATION AND MANUFACTURER DATA PARSING - IMPLEMENTATION GUIDE
================================================================================
Document Version: 1.0
Date: 2 December 2025
Purpose: Complete technical specification for Python implementation
Target Audience: AI implementing BLE functionality in Python

================================================================================
TABLE OF CONTENTS
================================================================================
1. Overview
2. Standard BLE Manufacturer Data Protocol (LEDnetWF Devices)
3. Custom Advertisement Protocol (Non-Connectable Devices)
4. Data Structures
5. Parsing Algorithms with Pseudocode
6. Connection Management
7. Security and Validation
8. Implementation Notes

================================================================================
1. OVERVIEW
================================================================================

This document describes the BLE communication protocols used by a LED lighting
control system. The app supports two distinct device types:

A) CONNECTABLE DEVICES (LEDnetWF/IOTWF):
   - Standard BLE GATT profile
   - Uses manufacturer-specific data in advertisements
   - Requires pairing and connection for control
   - 29-byte manufacturer data structure

B) NON-CONNECTABLE BROADCAST DEVICES:
   - Custom proprietary advertisement protocol
   - No connection required
   - Device state embedded in advertisement packets
   - 26+ byte custom packet structure

Both protocols use the standard Android BLE scanning API, processing the raw
advertisement bytes differently based on device type.

================================================================================
2. STANDARD BLE MANUFACTURER DATA PROTOCOL (LEDnetWF Devices)
================================================================================

2.1 DEVICE IDENTIFICATION
-------------------------
Target device names: "LEDnetWF" or "IOTWF" (case-sensitive substring match)
Scan mode: BLE_SCAN_MODE_LOW_LATENCY (mode=2)
Report delay: 0ms (immediate reporting)

2.2 ADVERTISEMENT STRUCTURE (TLV Format)
----------------------------------------
The raw advertisement data follows Type-Length-Value encoding:

Structure of each TLV block:
  Byte 0: Length (includes type byte, so actual_length = length - 1)
  Byte 1: Type (AD Type as per Bluetooth spec)
  Bytes 2+: Value (data, length determined by byte 0)

Example parsing loop:
  position = 0
  while position < data_length:
      length = data[position] - 1  # Subtract 1 for type byte
      if length <= 0:
          break
      type = data[position + 1]
      value_start = position + 2
      value = data[value_start : value_start + length]
      store(type, value)
      position += length + 2  # Move to next block

2.3 RELEVANT AD TYPES
---------------------
Type 1 (0x01): Flags
  - 1 byte indicating device capabilities
  
Type 9 (0x09): Complete Local Name
  - UTF-8 encoded device name
  
Type 22 (0x16): Service Data - 16-bit UUID
  - Contains service-specific information
  - Used for additional device parameters
  
Type 255 (0xFF): Manufacturer Specific Data
  - THIS IS THE PRIMARY DATA SOURCE
  - Contains all device identification and state
  - MUST be 29 bytes long (validate length)

2.4 MANUFACTURER DATA STRUCTURE
--------------------------------

*** CRITICAL: TWO DIFFERENT FORMATS DEPENDING ON DATA SOURCE ***

The manufacturer data can be obtained in two ways with DIFFERENT byte layouts:

FORMAT A: Raw AD Type 255 Payload (29 bytes)
--------------------------------------------
Source: Android scanRecord.getBytes() → parse TLV → Type 255 value
        iOS peripheral.advertisement.manufacturerData (raw)
        
This includes the 2-byte company ID at the start of the payload.

BYTE OFFSET | FIELD NAME       | SIZE   | DATA TYPE | DESCRIPTION
------------|------------------|--------|-----------|---------------------------
0           | sta              | 1      | uint8     | Status/State byte
1-2         | company_id       | 2      | uint16_be | Company ID (big-endian)
3           | ble_version      | 1      | uint8     | BLE protocol version
4-9         | mac_address      | 6      | bytes     | Device MAC address
10-11       | product_id       | 2      | uint16_be | Product identifier
12          | firmware_ver     | 1      | uint8     | Firmware version
13          | led_version      | 1      | uint8     | LED controller version
14          | check_key_flag   | 1      | uint8     | Bits 0-1 only (if bleVersion >= 5)
15          | firmware_flag    | 1      | uint8     | Bits 0-4 only (if bleVersion >= 5)
16-26       | state_data       | 11     | bytes     | Device state (if bleVersion >= 5)
27-28       | rfu              | 2      | bytes     | Reserved for future use

FORMAT B: Manufacturer-Specific Data (27 bytes) - USE THIS FOR HOME ASSISTANT
------------------------------------------------------------------------------
Source: Android scanRecord.getManufacturerSpecificData() 
        Python bleak: advertisement_data.manufacturer_data[company_id]
        
The company ID is returned as the DICTIONARY KEY, not in the payload!
The payload is 27 bytes starting AFTER the company ID.

BYTE OFFSET | FIELD NAME       | SIZE   | DATA TYPE | DESCRIPTION
------------|------------------|--------|-----------|---------------------------
0           | sta              | 1      | uint8     | Status/State byte
1           | ble_version      | 1      | uint8     | BLE protocol version
2-7         | mac_address      | 6      | bytes     | Device MAC address
8-9         | product_id       | 2      | uint16_be | Product identifier
10          | firmware_ver     | 1      | uint8     | Firmware version
11          | led_version      | 1      | uint8     | LED controller version
12          | check_key_flag   | 1      | uint8     | Bits 0-1 only (if bleVersion >= 5)
13          | firmware_flag    | 1      | uint8     | Bits 0-4 only (if bleVersion >= 5)
14-24       | state_data       | 11     | bytes     | Device state (if bleVersion >= 5)
25-26       | rfu              | 2      | bytes     | Reserved for future use

COMPANY ID RANGES (validated from source):
------------------------------------------
Primary Range (LEDnetWF): 23120, 23121, 23122 (0x5A50, 0x5A51, 0x5A52)
Extended Range (native): 23123, 23124 (0x5A53, 0x5A54) 
Extended Range (ZGHBDevice): 23072-23087, 23123-23133, 23136-23183

IMPORTANT FOR HOME ASSISTANT:
For device discovery, ALSO accept the broader range 0x5A00-0x5AFF (23040-23295)
since real devices have been observed with company ID 23040 (0x5A00) that
work correctly with the protocol. Filter by device name "LEDnetWF" or "IOTWF"
as the primary identification method.

WORKED EXAMPLE (Format B - 27-byte payload from bleak):
-------------------------------------------------------
Raw hex (27 bytes): 5B 05 E4 98 BB 95 EE 8E 00 33 29 0A 01 02 24 2F 23 08 00 00 00 00 0A 00 0F 00 00
Company ID (dict key): 23040 (0x5A00)

Byte 0:     0x5B = 91 = sta
Byte 1:     0x05 = 5 = ble_version
Bytes 2-7:  E4:98:BB:95:EE:8E = mac_address
Bytes 8-9:  0x0033 = 51 = product_id (Ctrl_Mini_RGB_0x33)
Byte 10:    0x29 = 41 = firmware_ver
Byte 11:    0x0A = 10 = led_version
Byte 12:    0x01 = check_key_flag (bits 0-1 = 1)
Byte 13:    0x02 = firmware_flag (bits 0-4 = 2)
Bytes 14-24: 24 2F 23 08 00 00 00 00 0A 00 0F = state_data
Bytes 25-26: 00 00 = rfu

2.5 PARSING WITH SERVICE DATA (Type 22)
---------------------------------------
When BOTH Type 255 AND Type 22 are present (this is for Format A - raw scan record):

NOTE: Type 22 parsing applies to the 29-byte Format A. The offsets here refer
to positions within the Type 22 payload (not the Type 255 payload).

Type 22 structure (14 bytes minimum):
  Bytes 0-2: Service UUID or header
  Byte 3: ble_version
  Bytes 4-9: mac_address
  Bytes 10-11: product_id
  Byte 12: firmware_ver
  Byte 13: led_version

When both Type 255 and Type 22 are present:
1. Parse Type 255 for sta and company_id
2. Parse Type 22 for ble_version, mac_address, product_id, firmware_ver, led_version
3. Type 22 values override Type 255 values

2.6 MAC ADDRESS FORMATTING
--------------------------
The 6-byte MAC address should be converted to string format:
  
  Input: bytes [0xE4, 0x98, 0xBB, 0x95, 0xEE, 0x8E]
  Output: "E4:98:BB:95:EE:8E" (with colons) or "E498BB95EE8E" (without)

Python:
  mac_string = ':'.join(format(b, '02X') for b in mac_bytes)

Pseudocode:
  mac_string = ""
  for byte in mac_bytes:
      mac_string += format(byte, "02X")
  return mac_string

2.7 DEVICE OBJECT CREATION
--------------------------
After parsing, create a device object with these fields:

LEDNetWFDevice:
  - device_name: string (from scan result)
  - sta: int (status byte)
  - manufacturer_id: int (2-byte manufacturer code)
  - ble_version: int (protocol version)
  - mac_address: string (formatted as described above)
  - product_id: int (2-byte product ID)
  - firmware_ver: int (firmware version)
  - led_version: int (LED version)
  - device_info: bytes (11-byte extended info from Type 255)
  - raw_manufacturer_data: bytes (full 29-byte Type 255 data)
  - bluetooth_device: object (platform BLE device reference)
  - scan_result: object (platform scan result object)

================================================================================
3. CUSTOM ADVERTISEMENT PROTOCOL (Non-Connectable Devices)
================================================================================

3.1 PROTOCOL OVERVIEW
---------------------
This is a PROPRIETARY protocol for broadcasting device state without connection.
Designed for ultra-low-power operation - devices never accept connections.

Key features:
- Stateless operation (no pairing required)
- Full device state in advertisement
- Network ID filtering (multi-network support)
- Sequence numbers for tracking
- CRC validation
- Bit-packed for space efficiency

3.2 PACKET STRUCTURE
--------------------
Minimum length: 26 bytes
The data is heavily bit-packed using bitwise operations.

RAW BYTES (as received from BLE scanner):
  Bytes 0-1: [Variable header/preamble]
  Bytes 2-25: Main data payload (24 bytes)
  Additional bytes may follow

IMPORTANT: Before parsing, bytes 2-25 must be REVERSED in 4-byte chunks!

3.3 BYTE REVERSAL ALGORITHM
---------------------------
The packet uses a custom byte order that must be corrected before parsing:

Pseudocode:
  def reverse_bytes(data):
      """Reverse bytes in 4-byte chunks starting at offset 2"""
      position = 2
      for chunk in range(6):  # 6 chunks of 4 bytes
          start = position
          end = position + 3
          # Reverse this 4-byte chunk
          while start < end:
              data[start], data[end] = data[end], data[start]
              start += 1
              end -= 1
          position += 4
      return data

Example:
  Before: [... 02 03 04 05 06 07 08 09 ...]
  After:  [... 05 04 03 02 09 08 07 06 ...]

3.4 PARSED DATA STRUCTURE (ADVModel)
------------------------------------

After parsing, extract these fields:

FIELD NAME    | SIZE (bits) | VALUE RANGE      | DESCRIPTION
--------------|-------------|------------------|--------------------------------
opCode        | 6 bits      | 0-63             | Operation/command code
networkId     | 24 bits     | 0-16777215       | Network identifier (filter key)
sn            | 8 bits      | 0-255            | Sequence number
macAddress    | 32 bits     | 0-4294967295     | Device MAC (as integer)
productId     | 12 bits     | 0-4095           | Product type identifier
firmwareId    | 4 bits      | 0-15             | Firmware version identifier
param         | 72 bits     | 9 bytes          | Device state parameters
crc           | 16 bits     | 2 bytes          | CRC-16 checksum

3.5 BIT EXTRACTION ALGORITHM
----------------------------
After byte reversal, extract fields using bitwise operations.

STEP 1: Extract Network ID (24 bits)
  network_id = ((data[3] & 0xFF) << 16) | ((data[4] & 0xFF) << 8) | (data[5] & 0xFF)

STEP 2: Extract OpCode (6 bits scattered across multiple bytes)
  The OpCode is intentionally scattered for obfuscation:
  
  bit_5 = (data[2] & 0x10) << 1     # Bit 5 from byte 2, bit position 4
  bit_4 = (data[6] & 0x10)          # Bit 4 from byte 6, bit position 4
  bit_3 = (data[10] & 0x10) >> 1    # Bit 3 from byte 10, bit position 4
  bit_2 = (data[14] & 0x10) >> 2    # Bit 2 from byte 14, bit position 4
  bit_1 = (data[18] & 0x10) >> 3    # Bit 1 from byte 18, bit position 4
  bit_0 = (data[22] & 0x10) >> 4    # Bit 0 from byte 22, bit position 4
  
  opcode = bit_5 | bit_4 | bit_3 | bit_2 | bit_1 | bit_0

STEP 3: Extract Sequence Number (8 bits)
  sn_high = (data[2] & 0x0F) << 4   # Lower 4 bits of byte 2, shifted up
  sn_low = (data[6] & 0x0F)         # Lower 4 bits of byte 6
  sn = sn_high | sn_low

STEP 4: Extract MAC Address (32 bits)
  mac = ((data[9] & 0xFF) << 8) | 
        ((data[8] & 0xFF) << 16) | 
        ((data[7] & 0xFF) << 24) | 
        (data[11] & 0xFF)

STEP 5: Extract Product ID (12 bits)
  product_high = (data[12] & 0xFF) << 4
  product_low = (data[13] & 0xF0) >> 4
  product_id = product_high | product_low

STEP 6: Extract Firmware ID (4 bits)
  firmware_id = data[13] & 0x0F

STEP 7: Extract Parameters (9 bytes)
  param[0] = ((data[10] & 0x0F) << 4) | (data[14] & 0x0F)
  param[1] = ((data[18] & 0x0F) << 4) | (data[22] & 0x0F)
  param[2] = data[15]
  param[3] = data[16]
  param[4] = data[17]
  param[5] = data[19]
  param[6] = data[20]
  param[7] = data[21]
  param[8] = data[23]

STEP 8: Extract CRC (2 bytes)
  crc[0] = data[24]
  crc[1] = data[25]

3.6 COMPLETE PARSING PSEUDOCODE
-------------------------------

def parse_advertisement(raw_data, allowed_network_ids):
    """
    Parse custom advertisement protocol
    
    Args:
        raw_data: bytes, raw BLE advertisement data (min 26 bytes)
        allowed_network_ids: list of ints, whitelist of network IDs
        
    Returns:
        ADVModel object or None if invalid
    """
    # Validation
    if raw_data is None or len(raw_data) < 26:
        return None
    
    # Make a copy to avoid modifying original
    data = bytearray(raw_data)
    
    # Reverse bytes in 4-byte chunks
    reverse_bytes(data)
    
    # Extract Network ID first (for filtering)
    network_id = ((data[3] & 0xFF) << 16) | \
                 ((data[4] & 0xFF) << 8) | \
                 (data[5] & 0xFF)
    
    # Filter by network ID
    if allowed_network_ids and network_id not in allowed_network_ids:
        return None
    
    # Extract OpCode (scattered across bytes)
    opcode = ((data[2] & 0x10) << 1) | \
             (data[6] & 0x10) | \
             ((data[10] & 0x10) >> 1) | \
             ((data[14] & 0x10) >> 2) | \
             ((data[18] & 0x10) >> 3) | \
             ((data[22] & 0x10) >> 4)
    
    # Extract Sequence Number
    sn = ((data[2] & 0x0F) << 4) | (data[6] & 0x0F)
    
    # Extract MAC Address (32-bit integer)
    mac_address = ((data[9] & 0xFF) << 8) | \
                  ((data[8] & 0xFF) << 16) | \
                  ((data[7] & 0xFF) << 24) | \
                  (data[11] & 0xFF)
    
    # Extract Product ID (12 bits)
    product_id = ((data[12] & 0xFF) << 4) | ((data[13] & 0xF0) >> 4)
    
    # Extract Firmware ID (4 bits)
    firmware_id = data[13] & 0x0F
    
    # Extract Parameters (9 bytes)
    param = bytearray(9)
    param[0] = ((data[10] & 0x0F) << 4) | (data[14] & 0x0F)
    param[1] = ((data[18] & 0x0F) << 4) | (data[22] & 0x0F)
    param[2] = data[15]
    param[3] = data[16]
    param[4] = data[17]
    param[5] = data[19]
    param[6] = data[20]
    param[7] = data[21]
    param[8] = data[23]
    
    # Extract CRC
    crc = bytes([data[24], data[25]])
    
    # Create and return ADVModel
    model = ADVModel()
    model.opcode = opcode
    model.network_id = network_id
    model.sn = sn
    model.mac_address = mac_address
    model.product_id = product_id
    model.firmware_id = firmware_id
    model.param = bytes(param)
    model.crc = crc
    
    # Optional: Validate CRC here
    # if not validate_crc(model):
    #     return None
    
    return model

3.7 ENCODING ALGORITHM (For Writing Commands)
----------------------------------------------
To send commands to devices, you must encode ADVModel back to bytes.

def encode_advertisement(model):
    """
    Encode ADVModel to byte array for transmission
    
    Returns 6 arrays of 4 bytes each (24 bytes total payload)
    """
    opcode = model.opcode & 0x3F  # 6 bits
    
    # Create 6 chunks of 4 bytes each
    chunks = []
    
    # Chunk 0: OpCode bits [5,4], SN high nibble, Network ID
    chunks.append([
        ((opcode & 0x20) >> 1) | 0x20 | ((model.sn & 0xF0) >> 4),
        (model.network_id & 0xFF0000) >> 16,
        (model.network_id & 0xFF00) >> 8,
        model.network_id & 0xFF
    ])
    
    # Chunk 1: OpCode bit [3], SN low nibble, MAC Address high bytes
    chunks.append([
        (opcode & 0x10) | 0x40 | (model.sn & 0x0F),
        (model.mac_address & 0xFF000000) >> 24,
        (model.mac_address & 0xFF0000) >> 16,
        (model.mac_address & 0xFF00) >> 8
    ])
    
    # Chunk 2: OpCode bit [2], param[0] high, MAC low, Product/Firmware IDs
    chunks.append([
        ((opcode & 0x08) << 1) | 0x60 | ((model.param[0] & 0xF0) >> 4),
        model.mac_address & 0xFF,
        (model.product_id & 0xFF0) >> 4,
        ((model.product_id & 0x0F) << 4) | (model.firmware_id & 0x0F)
    ])
    
    # Chunk 3: OpCode bit [1], param[0] low, param[2-4]
    chunks.append([
        ((opcode & 0x04) << 2) | 0x80 | (model.param[0] & 0x0F),
        model.param[2],
        model.param[3],
        model.param[4]
    ])
    
    # Chunk 4: OpCode bit [0], param[1] high, param[5-7]
    chunks.append([
        ((opcode & 0x02) << 3) | 0xA0 | ((model.param[1] & 0xF0) >> 4),
        model.param[5],
        model.param[6],
        model.param[7]
    ])
    
    # Calculate CRC before final chunk
    crc = calculate_crc(chunks)
    
    # Chunk 5: param[1] low, param[8], CRC
    chunks.append([
        ((opcode & 0x01) << 4) | 0xC0 | (model.param[1] & 0x0F),
        model.param[8],
        crc[0],
        crc[1]
    ])
    
    # Convert to flat byte array
    result = bytearray(24)
    for i, chunk in enumerate(chunks):
        result[i*4:(i+1)*4] = chunk
    
    # Reverse bytes in 4-byte chunks (inverse of parsing)
    reverse_bytes_for_transmission(result)
    
    return result

3.8 CRC CALCULATION
-------------------
CRC is calculated by summing all data bytes before the CRC field:

def calculate_crc(chunks):
    """
    Calculate 16-bit CRC by summing all bytes
    
    Args:
        chunks: List of 6 4-byte arrays
        
    Returns:
        [high_byte, low_byte]
    """
    total = 0
    # Sum first 5 chunks (last chunk contains CRC, exclude it)
    for i in range(5):
        for byte in chunks[i]:
            total += byte & 0xFF
    
    # Also add first 2 bytes of chunk 5 (param[1] and param[8])
    total += chunks[5][0] & 0xFF
    total += chunks[5][1] & 0xFF
    
    # Split into 2 bytes
    high_byte = (total & 0xFF00) >> 8
    low_byte = total & 0xFF
    
    return [high_byte, low_byte]

================================================================================
4. DATA STRUCTURES
================================================================================

4.1 LEDNetWFDevice (Standard BLE)
----------------------------------
class LEDNetWFDevice:
    device_name: str          # "LEDnetWF..." or "IOTWF..."
    sta: int                  # Status byte (0-255)
    company_id: int           # Company ID (23040-23295 range, 0x5A00-0x5AFF)
    ble_version: int          # BLE protocol version (0-255)
    mac_address: str          # "E4:98:BB:95:EE:8E" format (with colons)
    product_id: int           # Product identifier (0-65535)
    firmware_ver: int         # Firmware version (0-255)
    led_version: int          # LED version (0-255)
    check_key_flag: int       # Bits 0-1 (0-3) - if ble_version >= 5
    firmware_flag: int        # Bits 0-4 (0-31) - if ble_version >= 5
    state_data: bytes         # 11-byte state data - if ble_version >= 5
    rfu: bytes                # 2-byte reserved for future use
    raw_manufacturer_data: bytes  # Full payload (27 bytes for bleak, 29 for raw)
    bluetooth_device: object  # Platform BLE device reference
    timestamp: float          # Last seen timestamp

4.2 ADVModel (Custom Protocol)
-------------------------------
class ADVModel:
    opcode: int              # 0-63 (6-bit operation code)
    network_id: int          # 0-16777215 (24-bit network ID)
    sn: int                  # 0-255 (8-bit sequence number)
    mac_address: int         # 0-4294967295 (32-bit MAC as integer)
    product_id: int          # 0-4095 (12-bit product ID)
    firmware_id: int         # 0-15 (4-bit firmware ID)
    param: bytes             # 9 bytes of device parameters
    crc: bytes               # 2 bytes CRC checksum
    
    # Validation on setters:
    # - opcode: must be 0-63
    # - network_id: must be 0-16777215
    # - product_id: must be 0-4095
    # - firmware_id: must be 0-15
    # - param: must be exactly 9 bytes

4.3 NonConnectHBDevice (Broadcast Device)
------------------------------------------
class NonConnectHBDevice:
    mac_address: str         # Derived from ADVModel.mac_address (as string)
    status: str              # "ONLINE", "OFFLINE"
    adv_model: ADVModel      # Parsed advertisement data
    scan_result: object      # Platform scan result
    last_seen: float         # Timestamp of last advertisement
    
    # Derived properties from adv_model:
    @property
    def opcode(self):
        return self.adv_model.opcode
    
    @property
    def params(self):
        return self.adv_model.param

================================================================================
5. PARSING ALGORITHMS WITH PSEUDOCODE
================================================================================

5.1 BLEAK PARSING (Recommended for Home Assistant)
--------------------------------------------------
This is the correct parsing for Python bleak where the company ID is returned
as the dictionary key and the payload does NOT include the company ID.

def parse_lednetwf_device_bleak(device, advertisement_data):
    """
    Parse LEDnetWF device from bleak scanner
    
    Args:
        device: BLEDevice from bleak scanner
        advertisement_data: AdvertisementData from bleak scanner
        
    Returns:
        LEDNetWFDevice or None
    """
    # Filter by name
    device_name = device.name
    if device_name is None:
        return None
    if "LEDnetWF" not in device_name and "IOTWF" not in device_name:
        return None
    
    # Get manufacturer data (dict: company_id -> payload)
    mfr_data = advertisement_data.manufacturer_data
    if not mfr_data:
        return None
    
    # Find a valid company ID in the 0x5A** range
    company_id = None
    payload = None
    for cid, data in mfr_data.items():
        # Accept broader range 0x5A00-0x5AFF (23040-23295)
        if 23040 <= cid <= 23295:
            company_id = cid
            payload = data
            break
    
    if payload is None:
        return None
    
    # Validate payload length (27 bytes without company ID)
    if len(payload) != 27:
        return None
    
    # Parse 27-byte Format B payload
    sta = payload[0] & 0xFF
    ble_version = payload[1] & 0xFF
    mac_bytes = payload[2:8]
    mac_address = ':'.join(format(b, '02X') for b in mac_bytes)
    product_id = ((payload[8] & 0xFF) << 8) | (payload[9] & 0xFF)
    firmware_ver = payload[10] & 0xFF
    led_version = payload[11] & 0xFF
    
    # Extended fields (if ble_version >= 5)
    check_key_flag = (payload[12] & 0x03) if ble_version >= 5 else 0
    firmware_flag = (payload[13] & 0x1F) if ble_version >= 5 else 0
    state_data = bytes(payload[14:25]) if ble_version >= 5 else b''
    rfu = bytes(payload[25:27])
    
    # Create device object
    device_obj = LEDNetWFDevice()
    device_obj.device_name = device_name
    device_obj.sta = sta
    device_obj.company_id = company_id
    device_obj.ble_version = ble_version
    device_obj.mac_address = mac_address
    device_obj.product_id = product_id
    device_obj.firmware_ver = firmware_ver
    device_obj.led_version = led_version
    device_obj.check_key_flag = check_key_flag
    device_obj.firmware_flag = firmware_flag
    device_obj.state_data = state_data
    device_obj.rfu = rfu
    device_obj.raw_manufacturer_data = payload
    device_obj.bluetooth_device = device
    
    return device_obj

# Usage with bleak:
from bleak import BleakScanner

async def scan_lednetwf_devices():
    devices = []
    
    def detection_callback(device, advertisement_data):
        parsed = parse_lednetwf_device_bleak(device, advertisement_data)
        if parsed:
            devices.append(parsed)
    
    scanner = BleakScanner(detection_callback)
    await scanner.start()
    await asyncio.sleep(10.0)
    await scanner.stop()
    return devices


5.2 RAW SCAN RECORD PARSING (Android Native - 29 bytes)
-------------------------------------------------------
This format includes the company ID in the payload at bytes 1-2.
Use this only if you have raw advertisement bytes from TLV parsing.

def parse_lednetwf_device_raw(scan_result):
    """
    Complete parsing logic for LEDnetWF devices (raw scan record format)
    
    Args:
        scan_result: Platform-specific BLE scan result object
        
    Returns:
        LEDNetWFDevice or None
    """
    # Get device name
    device_name = scan_result.device.name
    if device_name is None:
        return None
    
    # Filter by name
    if "LEDnetWF" not in device_name and "IOTWF" not in device_name:
        return None
    
    # Get scan record
    scan_record = scan_result.scan_record
    if scan_record is None:
        return None
    
    # Get raw bytes
    raw_bytes = scan_record.bytes
    if raw_bytes is None or len(raw_bytes) < 32:
        return None
    
    # Parse TLV structure
    ad_data = {}
    position = 0
    
    while position < len(raw_bytes):
        length = raw_bytes[position] & 0xFF
        if length == 0:
            break
        
        actual_length = length - 1  # Subtract type byte
        if actual_length <= 0:
            position += 1
            continue
        
        ad_type = raw_bytes[position + 1] & 0xFF
        value_start = position + 2
        
        if value_start + actual_length > len(raw_bytes):
            break
        
        value = raw_bytes[value_start : value_start + actual_length]
        ad_data[ad_type] = value
        
        position += length + 1
    
    # Check for required Type 255 (manufacturer data)
    if 255 not in ad_data:
        return None
    
    manufacturer_data = ad_data[255]
    
    # Validate length (29 bytes with company ID)
    if len(manufacturer_data) != 29:
        return None
    
    # Extract company ID (big-endian from bytes 1-2)
    company_id = ((manufacturer_data[1] & 0xFF) << 8) | \
                 (manufacturer_data[2] & 0xFF)
    
    # Validate company ID (broader range)
    if not (23040 <= company_id <= 23295):
        return None
    
    # Create device object - parse 29-byte Format A (with company ID in payload)
    device = LEDNetWFDevice()
    device.device_name = device_name
    device.sta = manufacturer_data[0] & 0xFF
    device.company_id = company_id
    device.ble_version = manufacturer_data[3] & 0xFF
    
    mac_bytes = manufacturer_data[4:10]
    device.mac_address = ':'.join(format(b, '02X') for b in mac_bytes)
    
    device.product_id = ((manufacturer_data[10] & 0xFF) << 8) | \
                       (manufacturer_data[11] & 0xFF)
    device.firmware_ver = manufacturer_data[12] & 0xFF
    device.led_version = manufacturer_data[13] & 0xFF
    
    # Extended fields (if ble_version >= 5)
    if device.ble_version >= 5:
        device.check_key_flag = manufacturer_data[14] & 0x03
        device.firmware_flag = manufacturer_data[15] & 0x1F
        device.state_data = bytes(manufacturer_data[16:27])
        device.rfu = bytes(manufacturer_data[27:29])
    else:
        device.check_key_flag = 0
        device.firmware_flag = 0
        device.state_data = b''
        device.rfu = bytes(manufacturer_data[16:29])
    
    device.raw_manufacturer_data = manufacturer_data
    device.bluetooth_device = scan_result.device
    
    # Check if Type 22 (service data) also present - may override some fields
    if 22 in ad_data and len(ad_data[22]) >= 14:
        service_data = ad_data[22]
        # Type 22 has same offset layout as Type 255 (bytes 3+ = ble_version, etc.)
        device.ble_version = service_data[3] & 0xFF
        mac_bytes = service_data[4:10]
        device.mac_address = ':'.join(format(b, '02X') for b in mac_bytes)
        device.product_id = ((service_data[10] & 0xFF) << 8) | \
                           (service_data[11] & 0xFF)
        device.firmware_ver = service_data[12] & 0xFF
        device.led_version = service_data[13] & 0xFF
    
    return device

5.3 CUSTOM PROTOCOL PARSING (Complete Example)
----------------------------------------------
See section 3.6 for complete pseudocode.

================================================================================
6. CONNECTION MANAGEMENT
================================================================================

6.1 BLE GATT CONNECTION (for LEDnetWF devices)
----------------------------------------------

Standard BLE GATT profile is used for connected operation:

SERVICE UUIDs (Discovered from Service.java):
  - Primary Service:       0000ffff-0000-1000-8000-00805f9b34fb (short: 0xFFFF)
  - Write Characteristic:  0000ff01-0000-1000-8000-00805f9b34fb (short: 0xFF01)
  - Read/Notify Characteristic: 0000ff02-0000-1000-8000-00805f9b34fb (short: 0xFF02)

OTA (Over-The-Air Update) Service:
  - OTA Service UUID:      0000fe00-0000-1000-8000-00805f9b34fb (short: 0xFE00)
  - OTA Write UUID:        0000ff11-0000-1000-8000-00805f9b34fb (short: 0xFF11)
  - OTA Read UUID:         0000ff22-0000-1000-8000-00805f9b34fb (short: 0xFF22)

IMPORTANT: These are 16-bit UUIDs in the Bluetooth Base UUID format:
  0000XXXX-0000-1000-8000-00805f9b34fb

Python bleak usage:
  SERVICE_UUID = "0000ffff-0000-1000-8000-00805f9b34fb"
  WRITE_CHAR_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
  READ_CHAR_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"
  
  async with BleakClient(device) as client:
      # Enable notifications on read characteristic
      await client.start_notify(READ_CHAR_UUID, notification_handler)
      
      # Write command to write characteristic
      await client.write_gatt_char(WRITE_CHAR_UUID, command_bytes)

Connection Parameters:
  - Connection Priority: HIGH (low latency mode)
  - Auto-connect: false (explicit connection)
  - Transport: LE only (not BR/EDR)
  - MTU: Request 512 bytes if BLE version >= 8 (see section 9.3)
  - Default MTU: 23 bytes (BLE 4.0/4.2)

Connection Flow:
  1. Scan and identify device
  2. Stop scanning
  3. Connect to device (connectGatt)
  4. Wait for onConnectionStateChange -> STATE_CONNECTED
  5. Request connection priority (HIGH)
  6. Discover services (discoverServices)
  7. Wait for onServicesDiscovered
  8. Request MTU if supported
  9. Enable notifications on read characteristic
  10. Ready for read/write operations

6.2 CONNECTION STATE MANAGEMENT
-------------------------------

Device States:
  - OFFLINE: Not seen in recent scans
  - ONLINE: Visible in scans but not connected
  - CONNECTING: Connection attempt in progress
  - CONNECTED: Active GATT connection established
  - DISCONNECTED: Was connected, now disconnected

State Transitions:
  OFFLINE -> ONLINE: Device appears in scan
  ONLINE -> CONNECTING: User initiates connection
  CONNECTING -> CONNECTED: GATT connection established
  CONNECTED -> DISCONNECTED: Connection lost or closed
  DISCONNECTED -> CONNECTING: Reconnection attempt
  Any -> OFFLINE: Not seen for timeout period (15 seconds)

6.3 LRU CACHE FOR CONNECTIONS
-----------------------------
To manage resources, connections are cached with LRU eviction:

Cache Parameters:
  - Max Size: 7 concurrent connections
  - Eviction: Least Recently Used
  - On Eviction: Disconnect and cleanup

Cache Operations:
  - fetch(mac_address): Get existing or create new connection
  - cache(mac_address, connection): Store connection
  - remove(mac_address): Remove and disconnect
  - refresh(mac_address): Update last access time

6.4 WRITE OPERATIONS
--------------------

For BLE version 0 (older devices):
  - Use standard write (20-byte packets)
  - No MTU negotiation

For BLE version >= 1 (newer devices):
  - Request MTU of 512 bytes
  - Use larger packets for efficiency
  - Split large commands across multiple writes

Write with Response:
  - Set characteristic value
  - Call writeCharacteristic
  - Wait for onCharacteristicWrite callback
  - Check status before sending next packet

6.5 READ/NOTIFICATION OPERATIONS
---------------------------------

Enable Notifications:
  1. Get characteristic descriptor (CLIENT_CHARACTERISTIC_CONFIG)
  2. Set descriptor value to ENABLE_NOTIFICATION_VALUE
  3. Write descriptor
  4. Call setCharacteristicNotification(characteristic, true)

Receiving Data:
  - Implement onCharacteristicChanged callback
  - Parse incoming bytes according to device protocol
  - Handle multi-packet messages (reassembly may be needed)

================================================================================
7. SECURITY AND VALIDATION
================================================================================

7.1 NETWORK ID FILTERING
------------------------
For custom protocol devices, ALWAYS filter by network ID:

  - Maintain a whitelist of allowed network_id values
  - Reject any packet where network_id not in whitelist
  - This prevents processing rogue/interference devices
  - Network IDs are 24-bit (0 to 16,777,215)

7.2 MAC ADDRESS WHITELISTING
----------------------------
Optional additional security:

  - Maintain set of known device MAC addresses
  - Only process advertisements from known devices
  - Can be used for both protocols
  - Allows dynamic add/remove of devices

7.3 CRC VALIDATION
------------------
For custom protocol, ALWAYS validate CRC:

  def validate_crc(adv_model):
      """Validate CRC matches calculated value"""
      # Recalculate CRC from data
      calculated = calculate_crc_from_model(adv_model)
      
      # Compare with received CRC
      return (calculated[0] == adv_model.crc[0] and
              calculated[1] == adv_model.crc[1])

Reject packets with invalid CRC to prevent:
  - Corrupted data processing
  - Interference from other devices
  - Malicious packet injection

7.4 SEQUENCE NUMBER TRACKING
----------------------------
Track sequence numbers to detect:
  - Duplicate packets (replay attacks)
  - Missing packets (gaps in sequence)
  - Out-of-order delivery

Implementation:
  sequence_tracker = {}  # mac_address -> last_sn
  
  def check_sequence(mac_address, new_sn):
      if mac_address not in sequence_tracker:
          sequence_tracker[mac_address] = new_sn
          return True
      
      last_sn = sequence_tracker[mac_address]
      
      # Allow for wraparound (8-bit counter)
      expected_sn = (last_sn + 1) % 256
      
      if new_sn == last_sn:
          # Duplicate packet
          return False
      
      if new_sn == expected_sn or \
         (new_sn > last_sn and new_sn - last_sn < 128) or \
         (new_sn < last_sn and last_sn - new_sn > 128):
          # Valid new sequence
          sequence_tracker[mac_address] = new_sn
          return True
      
      # Out of order or gap
      # Decide policy: accept or reject
      return True  # Accept but log warning

7.5 TIMEOUT MANAGEMENT
----------------------
Mark devices OFFLINE if not seen recently:

  OFFLINE_TIMEOUT = 15.0  # seconds
  
  def periodic_check():
      """Call this periodically (e.g., every 15 seconds)"""
      current_time = time.time()
      
      for device in all_devices:
          if current_time - device.last_seen > OFFLINE_TIMEOUT:
              device.status = "OFFLINE"
              emit_event(device)  # Notify listeners

7.6 DATA VALIDATION
-------------------
Always validate ranges before using parsed data:

  def validate_adv_model(model):
      """Validate ADVModel field ranges"""
      if model.opcode < 0 or model.opcode > 63:
          return False
      if model.network_id < 0 or model.network_id > 16777215:
          return False
      if model.product_id < 0 or model.product_id > 4095:
          return False
      if model.firmware_id < 0 or model.firmware_id > 15:
          return False
      if len(model.param) != 9:
          return False
      if len(model.crc) != 2:
          return False
      return True

================================================================================
8. IMPLEMENTATION NOTES
================================================================================

8.1 PYTHON BLE LIBRARIES
------------------------
Recommended libraries for Python implementation:

  - bleak: Cross-platform BLE library (Windows, Linux, macOS)
    * Modern async/await API
    * Good advertisement scanning support
    * GATT client implementation
    
  - pybluez: Traditional BLE library (Linux focused)
    * More low-level control
    * Requires system Bluetooth stack
    
  - bluepy: Lightweight BLE library (Linux only)
    * Direct control over scanning
    * Good for Raspberry Pi

Example with bleak:

  from bleak import BleakScanner, BleakClient
  
  def detection_callback(device, advertisement_data):
      # device.name, device.address
      # advertisement_data.manufacturer_data
      # advertisement_data.service_data
      pass
  
  async def scan():
      scanner = BleakScanner(detection_callback)
      await scanner.start()
      await asyncio.sleep(10.0)
      await scanner.stop()

8.2 ENDIANNESS CONSIDERATIONS
-----------------------------
Be careful with byte order:

  - Manufacturer ID: Big-endian (network byte order)
  - Product ID: Big-endian
  - MAC Address: As-is (no conversion)
  - Custom protocol: Mixed (follow bit extraction exactly)

Python struct module for byte conversions:
  
  import struct
  
  # Big-endian 16-bit unsigned
  value = struct.unpack('>H', bytes([0x5A, 0x50]))[0]
  # Result: 23120
  
  # Little-endian 32-bit unsigned
  value = struct.unpack('<I', bytes([0x12, 0x34, 0x56, 0x78]))[0]

8.3 BIT MANIPULATION IN PYTHON
------------------------------
Python handles arbitrary precision integers well:

  # Extract bits
  value = (data[0] & 0x10) >> 4  # Get bit 4
  
  # Set bits
  result = (value1 << 8) | value2  # Combine two bytes
  
  # Mask and shift
  upper = (data[0] & 0xF0) >> 4   # Upper nibble
  lower = data[0] & 0x0F           # Lower nibble

8.4 ASYNC vs SYNC DESIGN
------------------------
Modern BLE libraries use async/await:

  async def scan_devices():
      devices = await scanner.discover()
      for device in devices:
          parsed = parse_lednetwf_device(device)
          if parsed:
              await process_device(parsed)

For simpler synchronous design:
  - Use threading
  - Wrap async calls in blocking wrappers
  - May be less efficient

8.5 ERROR HANDLING
------------------
Robust error handling is critical:

  try:
      parsed = parse_advertisement(data, network_ids)
      if parsed is None:
          return  # Invalid packet, ignore
      
      if not validate_crc(parsed):
          log_warning("CRC mismatch")
          return
      
      process_device(parsed)
      
  except Exception as e:
      log_error(f"Parse error: {e}")
      # Don't crash on malformed data

8.6 LOGGING AND DEBUGGING
-------------------------
Add detailed logging for development:

  import logging
  
  # Log raw bytes
  logging.debug(f"Raw data: {data.hex()}")
  
  # Log parsed values
  logging.debug(f"Parsed: opcode={model.opcode}, "
                f"network={model.network_id}, "
                f"mac={model.mac_address:08X}")
  
  # Log validation failures
  logging.warning(f"CRC validation failed for {mac}")

8.7 TESTING STRATEGY
--------------------

Unit Tests:
  - Test TLV parser with known good data
  - Test bit extraction with sample packets
  - Test CRC calculation
  - Test byte reversal algorithm
  - Test encoding/decoding round-trip

Integration Tests:
  - Capture real BLE advertisements
  - Save as test fixtures
  - Verify parsing matches expected values

Mock Devices:
  - Create fake BLE advertisements
  - Test filtering logic
  - Test timeout handling
  - Test sequence number tracking

8.8 PERFORMANCE CONSIDERATIONS
------------------------------

Scanning:
  - Use appropriate scan interval (balance power vs latency)
  - Filter advertisements at BLE layer if possible
  - Process in background thread

Parsing:
  - Pre-compile regular expressions if used
  - Cache parsed devices
  - Avoid re-parsing unchanged data

Connection Management:
  - Limit concurrent connections (use LRU cache)
  - Implement connection pooling
  - Clean up disconnected devices

8.9 PLATFORM-SPECIFIC NOTES
---------------------------

Linux:
  - Requires BlueZ stack
  - May need sudo for scanning
  - Use hciconfig to manage adapters

Windows:
  - Requires Windows 10+ with BLE support
  - May need admin rights
  - Limited to built-in adapter or specific dongles

macOS:
  - Uses Core Bluetooth framework
  - No special permissions needed
  - Good BLE support

Raspberry Pi:
  - Excellent BLE support
  - Use bluepy or bleak
  - Can run headless
  - Power management considerations

================================================================================
APPENDIX A: JAVA SOURCE CODE REFERENCES
================================================================================

A.1 QUERY STATE COMMAND (0x81) - CONSTRUCTION AND RESPONSE PARSING
-------------------------------------------------------------------
Java Source (FlutterBleControl.java - 0x81 query detection):
```java
if (commInfo.getCmd().get("hex").toString().startsWith("81") || command.cmdId == 65535) {
    command.cmdId = 10;           // Generic command with response
    command.resultId = (byte) 10; // Expect response on cmdId 10
    // Use BleStateUploadCallback to parse response
}
```

Response parsing (tc/b.java class a.c/d - DeviceState parser):
```java
// CORRECTED byte positions based on actual source code analysis
public static DeviceState parseStateResponse(byte[] response) {
    if (response.length >= 14 && response[0] == -127) {  // 0x81
        // Verify checksum: sum of bytes 0-12 mod 256 should equal byte 13
        byte checksum = calculateChecksum(response, 13);
        if (response[13] != checksum) return null;
        
        DeviceState state = new DeviceState();
        state.setMode(response[1] & 0xFF);        // Mode value
        state.setPowerOn(response[2] == 35);      // 0x23 = ON
        // Bytes 3-5 are device-specific values (mode sub-type, etc.)
        state.setRed(response[6] & 0xFF);         // R (NOT byte 3!)
        state.setGreen(response[7] & 0xFF);       // G (NOT byte 4!)
        state.setBlue(response[8] & 0xFF);        // B (NOT byte 5!)
        // Byte 9 is device-specific (may be WW on some devices)
        state.setBrightness(response[10] & 0xFF); // Brightness
        // Bytes 11-12 are reserved/device-specific
        return state;
    }
    return null;
}
```

NOTE: The original app uses generic value1-value7 fields rather than explicit
setRed/setGreen/setBlue methods. The RGB byte positions were determined by
tracing BaseDeviceInfo.java which uses f23865j (byte 6) for R, f23866k (byte 7)
for G, and f23867l (byte 8) for B.

A.2 POWER COMMANDS - ACTUAL JAVA IMPLEMENTATIONS
-------------------------------------------------
Java Source (tc/b.java - power command builders):
```java
// Method m: General power control
public static byte[] m(boolean powerOn) {
    byte[] cmd = new byte[5];
    cmd[0] = 17;   // 0x11 - opcode
    cmd[1] = 26;   // 0x1A - sub-opcode
    cmd[2] = 27;   // 0x1B - sub-opcode
    cmd[3] = powerOn ? (byte) 0xF0 : (byte) 0x0F;  // Persist flag
    cmd[4] = checksum(cmd, 4);
    return cmd;
}

// Method n: Broadcast power control
public static byte[] n(boolean powerOn) {
    byte[] cmd = new byte[5];
    cmd[0] = 98;  // 0x62
    cmd[1] = 106; // 0x6A
    cmd[2] = 107; // 0x6B
    cmd[3] = powerOn ? (byte) 0xF0 : (byte) 0x0F;
    cmd[4] = checksum(cmd, 4);
    return cmd;
}

// Methods o, p, q follow similar 5-byte pattern with opcodes:
// o: [0x73, 0x7A, 0x7B, persist, checksum]
// p: [0x32, 0x3A, 0x3B, persist, checksum]
// q: [0x22, 0x2A, 0x2B, persist, checksum]
```

IMPORTANT: The doc mentions 0x23/0x24 for power based on user observation. The Java code shows:
- Power COMMANDS use family-specific opcodes (0x11, 0x62, etc.) with persist flags
- Power STATE in responses uses byte[2] == 0x23 (35) to indicate device is ON
- User's 0x23 observation likely refers to state responses, not command opcodes

A.3 SYMPHONY/EFFECT COMMANDS - ADDRESSABLE LED CONTROL
-------------------------------------------------------
Java Source (tc/b.java - Symphony effect command builder):
```java
// SymphonyICTypeItem fields:
// f24022a = pattern/effect ID
// f24024c, f24025d, f24026e = RGB color slots (3 bytes)
// f24027f = brightness
// f24028g = IC/pixel count (int16)

public static byte[] B(int modeId, SymphonyICTypeItem effect, int speed) {
    byte[] modeBytes = intToBytes(modeId);        // 2-byte mode ID
    byte[] icCountBytes = intToBytes(effect.f24028g);  // 2-byte IC count
    byte[] cmd = new byte[13];
    cmd[0] = 98;  // 0x62 - Symphony command opcode
    cmd[1] = modeBytes[1];  // Mode ID high byte
    cmd[2] = modeBytes[0];  // Mode ID low byte
    cmd[3] = (byte) effect.f24022a;  // Pattern/effect ID
    cmd[4] = (byte) effect.f24024c;  // Color slot 1 (R or color 1)
    cmd[5] = (byte) effect.f24025d;  // Color slot 2 (G or color 2)
    cmd[6] = (byte) effect.f24026e;  // Color slot 3 (B or color 3)
    cmd[7] = (byte) effect.f24027f;  // Brightness
    cmd[8] = icCountBytes[1];  // IC count high byte
    cmd[9] = icCountBytes[0];  // IC count low byte
    cmd[10] = (byte) speed;    // Speed parameter
    cmd[11] = (byte) 0xF0;     // Persist flag
    cmd[12] = checksum(cmd, 12);
    return cmd;
}

// Query current effect state (response parser in tc/b.java class a.g):
public static SymphonyICTypeItem parseEffectResponse(byte[] response) {
    if (response.length >= 12 && response[0] == 99) {  // 0x63 response
        SymphonyICTypeItem item = new SymphonyICTypeItem();
        item.f24022a = response[3] & 0xFF;  // Pattern ID
        item.f24024c = response[4] & 0xFF;  // Color 1
        item.f24025d = response[5] & 0xFF;  // Color 2
        item.f24026e = response[6] & 0xFF;  // Color 3
        item.f24027f = response[7] & 0xFF;  // Brightness
        item.f24028g = bytesToInt(new byte[]{response[9], response[8]});  // IC count
        // response[11] = checksum
        return item;
    }
    return null;
}
```

================================================================================
13. TRANSPORT LAYER PACKET ANALYSIS
================================================================================

This section explains how to decode raw BLE packets captured from Wireshark
or other BLE sniffers. Focus is on BLE-only LED controllers.

13.1 TRANSPORT LAYER STRUCTURE (Version 0)
------------------------------------------
All commands are wrapped in the transport layer before being sent over BLE.

Single-segment packet format (most common):
  BYTE | FIELD           | DESCRIPTION
  -----|-----------------|------------------------------------------
  0    | Header          | Flags: bits[0-1]=version, bit[6]=segmented
  1    | Sequence        | Packet sequence number (0-255)
  2-3  | Frag Control    | 0x8000 = single complete segment
  4-5  | Total Length    | Total payload length (big-endian)
  6    | Payload Length  | Length of payload + 1 (for cmdId)
  7    | cmdId           | Command ID: 10=expects response, 11=no response
  8+   | Payload         | Actual LED command data (opcode + params)

13.2 EXAMPLE PACKET DECODES
---------------------------
Example 1: State Query Command
To query device state, send [0x81, 0x8A, 0x8B, checksum] wrapped in transport.

Expected wrapped packet structure:
  00 XX 80 00 00 04 05 0A 81 8A 8B CS
  |  |  |     |     |  |  |  +---------  Payload: state query command
  |  |  |     |     |  |  +-- cmdId=10 (expects response)
  |  |  |     |     |  +-- payload+cmdId length = 5
  |  |  |     |     +-- total payload = 4 bytes
  |  |  |     +-- frag ctrl = 0x8000 (single segment)
  |  |  +-- sequence number
  +-- header (version 0)

Example 2: Set RGB Color Command  
To set color to Red (255,0,0), send [0x31, 0xFF, 0x00, 0x00, ...] wrapped.

Expected wrapped packet for RGB command (9 bytes payload):
  00 XX 80 00 00 09 0A 0B 31 FF 00 00 00 00 F0 0F CS
  |              |     |  |  +-- Payload: RGB command
  |              |     |  +-- cmdId=11 (no response needed)
  |              |     +-- payload+cmdId length = 10
  |              +-- total payload = 9 bytes
  +-- transport header

13.3 PYTHON TRANSPORT LAYER DECODER
-----------------------------------
```python
def decode_transport_packet(data: bytes) -> dict:
    """
    Decode a raw BLE transport layer packet.
    
    Args:
        data: Raw bytes received from BLE notification/write
        
    Returns:
        Dictionary with decoded packet fields
    """
    if len(data) < 8:
        return {"error": "Packet too short"}
    
    header = data[0]
    version = header & 0x03
    is_segmented = (header & 0x40) == 0x40
    needs_ack = (header & 0x10) == 0x10
    
    seq = data[1]
    frag_ctrl = (data[2] << 8) | data[3]
    total_length = (data[4] << 8) | data[5]
    
    # For version 0 single-segment packets
    if version == 0 and not is_segmented:
        payload_plus_cmd_len = data[6]
        cmd_id = data[7]
        payload = data[8:8+total_length] if len(data) >= 8+total_length else data[8:]
        
        return {
            "version": version,
            "sequence": seq,
            "is_segmented": is_segmented,
            "needs_ack": needs_ack,
            "frag_ctrl": hex(frag_ctrl),
            "total_length": total_length,
            "payload_plus_cmd_len": payload_plus_cmd_len,
            "cmd_id": cmd_id,
            "cmd_id_name": get_cmd_id_name(cmd_id),
            "payload": payload.hex(),
            "payload_bytes": list(payload)
        }
    
    return {"error": "Unknown packet format", "version": version}

def get_cmd_id_name(cmd_id: int) -> str:
    """Get human-readable name for cmdId."""
    names = {
        1: "WIFI_LIST",
        6: "CHECK_LOG",
        7: "CHECK_NETWORK (WiFi Provisioning)",
        10: "WITH_RESPONSE (Generic command expecting response)",
        11: "NO_RESPONSE (Generic command, no response)",
        65535: "APP_STATE_QUERY"
    }
    return names.get(cmd_id, f"UNKNOWN_{cmd_id}")

# Example usage:
packet1 = bytes.fromhex("00 01 80 00 00 02 03 07 22 22".replace(" ", ""))
print(decode_transport_packet(packet1))
# Output:
# {
#   'version': 0,
#   'sequence': 1,
#   'is_segmented': False,
#   'needs_ack': False,
#   'frag_ctrl': '0x8000',
#   'total_length': 2,
#   'payload_plus_cmd_len': 3,
#   'cmd_id': 7,
#   'cmd_id_name': 'CHECK_NETWORK (WiFi Provisioning)',
#   'payload': '2222',
#   'payload_bytes': [34, 34]
# }

packet2 = bytes.fromhex("00 02 80 00 00 0c 0d 0b 10 14 18 0b 18 0e 05 15 07 00 0f 9d".replace(" ", ""))
print(decode_transport_packet(packet2))
# Output:
# {
#   'version': 0,
#   'sequence': 2,
#   'is_segmented': False,
#   'needs_ack': False,
#   'frag_ctrl': '0x8000',
#   'total_length': 12,
#   'payload_plus_cmd_len': 13,
#   'cmd_id': 11,
#   'cmd_id_name': 'NO_RESPONSE (Generic command, no response)',
#   'payload': '10141808180e05150700079d',
#   'payload_bytes': [16, 20, 24, 11, 24, 14, 5, 21, 7, 0, 15, 157]
# }
```

13.4 COMMAND IDS FOR BLE-ONLY LED CONTROLLERS
----------------------------------------------
| cmdId | Constant Name           | Use Case                         |
|-------|-------------------------|----------------------------------|
| 10    | WITH_RESPONSE_CMD_ID    | Commands expecting response      |
|       |                         | - State query (0x81)             |
|       |                         | - Timer query                    |
| 11    | NO_RESPONSE_CMD_ID      | Fire-and-forget commands         |
|       |                         | - Set RGB color (0x31)           |
|       |                         | - Power on/off (0x41/0x42)       |
|       |                         | - Set effect (0x38)              |
| 65535 | APP_STATE_QUERY_CMD_ID  | Special: state query routing     |

Note: cmdIds 1-9 are for WiFi-capable devices and NOT used by BLE-only
LED controllers like Ctrl_Mini_RGB.

================================================================================
END OF DOCUMENT
================================================================================

This documentation will be updated as additional information is discovered
through further analysis or questions.

Last updated: 2 December 2025
Version: 1.2 (Fixed state response byte positions, added Python transport layer implementation)
