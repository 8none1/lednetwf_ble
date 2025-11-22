# 0x54 device
# Currently a copy of 0x62 

from .model_abstractions import DefaultModelAbstraction
from .. import const
from enum import Enum
import logging

from homeassistant.components.light import (
    ColorMode,
    EFFECT_OFF
)

LOGGER = logging.getLogger(__name__)
SUPPORTED_MODELS = [0x54, 0x55, 0x62]

# This device only supports three colour orders, so override the defaults with our own
# In order to maintain compatibility with the rest of the code, we'll use some of the same values for unsupported colour orders
# This will manifest to the user as the same colour order as RGB.
class ColorOrdering(Enum):
    RGB = 0x01
    RBG = 0x01
    GRB = 0x02
    GBR = 0x01
    BRG = 0x03
    BGR = 0x01
    
    @classmethod
    def from_value(cls, value):
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"No member with value {value}")

# 0x54 Effect data
EFFECT_MAP_0x54 = {}
for e in range(37,58):
    EFFECT_MAP_0x54[f"Effect {e-36}"] = e
EFFECT_MAP_0x54["_Effect Off"]         = 0
EFFECT_MAP_0x54["Candle Mode"]        = 100
EFFECT_MAP_0x54["Sound Reactive"]     = 200
EFFECT_LIST_0x54 = sorted(EFFECT_MAP_0x54)
EFFECT_ID_TO_NAME_0x54 = {v: k for k, v in EFFECT_MAP_0x54.items()}

class Model0x54(DefaultModelAbstraction):
    # Strip light
    def __init__(self, manu_data):
        LOGGER.debug("Model 0x54 init")
        super().__init__(manu_data)
        self.SUPPORTED_VERSIONS      = [0x54]
        self.INITIAL_PACKET          = bytearray.fromhex("00 01 80 00 00 02 03 07 22 22")
        #self.GET_LED_SETTINGS_PACKET = bytearray.fromhex("00 02 80 00 00 0c 0d 0b 10 14 18 0b 18 08 2c 02 07 00 0f ab")
        self.GET_LED_SETTINGS_PACKET = bytearray.fromhex("00 02 80 00 00 0c 0d 0b 10 14 18 0b 18 0e 05 15 07 00 0f 9d")
        #                                                 
        self.supported_color_modes = {ColorMode.HS} # Actually, it supports RGB, but this will allow us to separate colours from brightness
        self.icon = "mdi:led-strip-variant"
        self.effect_list = EFFECT_LIST_0x54

        LOGGER.debug(f"Manu data: {[f'{i}: {hex(x)}' for i, x in enumerate(self.manu_data)]}")
        LOGGER.debug(f"Manu data 15: {hex(self.manu_data[15])}")
        LOGGER.debug(f"Manu data 16: {hex(self.manu_data[16])}")
        # return
        # Power state is already set by parent class from manu_data[14]
        # Just handle the 0x38 (off) case specifically
        if self.manu_data[15] == 0x38:
            # Device is definitely off
            self.is_on = False
        elif self.manu_data[15] == 0x61:
            # Color mode - parse RGB color
            rgb_color = (self.manu_data[18], self.manu_data[19], self.manu_data[20])
            self.hs_color = tuple(super().rgb_to_hsv(rgb_color))[0:2]
            self.brightness = (super().rgb_to_hsv(rgb_color)[2])
            self.color_mode = ColorMode.HS
            # Power state already handled by parent class
            LOGGER.debug(f"From manu RGB colour: {rgb_color}")
            LOGGER.debug(f"From manu HS colour: {self.hs_color}")
            LOGGER.debug(f"From manu Brightness: {self.brightness}")
            # if self.manu_data[16] != 0xf0:
            #     # We're not in a colour mode, so set the effect
            #     self.effect_speed = self.manu_data[17]
            #     if 0x02 <= self.manu_data[16] <= 0x0a:
            #         self.effect = EFFECT_ID_TO_NAME_0x62[self.manu_data[16] << 8]
            #     else:
            #         self._effect = EFFECT_OFF
        # elif self.manu_data[15] == 0x62:
        #     # Music reactive mode. 
        #     self._color_mode = ColorMode.BRIGHTNESS
        #     effect = manu_data[16]
        #     scaled_effect = (effect + 0x32) << 8
        #     self.effect = EFFECT_ID_TO_NAME_0x62[scaled_effect]
        elif self.manu_data[15] >= 37 and self.manu_data[15] <= 56:
            # Effect mode
            effect = self.manu_data[15]
            self.effect = EFFECT_ID_TO_NAME_0x54[effect]
            self.effect_speed = self.manu_data[17]
            self.brightness   = int(self.manu_data[18] * 255 // 100)
            self.color_mode   = ColorMode.BRIGHTNESS
            self.is_on        = True
        
        LOGGER.debug(f"Effect:           {self.effect}")
        LOGGER.debug(f"Effect speed:     {self.effect_speed}")
        LOGGER.debug(f"Brightness:       {self.brightness}")
        LOGGER.debug(f"LED count:        {self.led_count}")
        LOGGER.debug(f"Firmware version: {self.fw_major}.{self.fw_minor}")
        LOGGER.debug(f"Is on:            {self.is_on}")
        LOGGER.debug(f"Colour mode:      {self.color_mode}")
        LOGGER.debug(f"HS colour:        {self.hs_color}")

    def set_color(self, hs_color, brightness):
        # Returns the byte array to set the RGB colour
        self.color_mode = ColorMode.HS
        self.hs_color   = hs_color
        self.brightness = brightness
        self.effect     = EFFECT_OFF
        rgb_color = self.hsv_to_rgb((hs_color[0], hs_color[1], self.brightness))
        LOGGER.debug(f"Setting RGB colour: {rgb_color}")
        rgb_packet = bytearray.fromhex("00 05 80 00 00 08 09 0b 31 ff 00 00 00 00 0f 3f")
        rgb_packet[9:12] = rgb_color
        rgb_packet[15]    = sum(rgb_packet[8:15]) & 0xFF # Checksum
        LOGGER.debug(f"Set RGB. RGB {self.get_rgb_color()} Brightness {self.brightness}")
        return rgb_packet

    def set_effect(self, effect, brightness):
        # Returns the byte array to set the effect
        LOGGER.debug(f"Setting effect: {effect}")
        if effect not in EFFECT_LIST_0x54:
            raise ValueError(f"Effect '{effect}' not in EFFECTS_LIST_0x54")
        self.effect = effect
        # Ensure brightness is in valid range (0-255)
        self.brightness = min(255, max(0, brightness)) if brightness is not None else 255
        effect_id = EFFECT_MAP_0x54.get(effect)
        
        if effect_id == 0: # Effect off - switch to color mode
            return self.set_color(self.hs_color, self.brightness)
        
        if 100 <= effect_id <= 200: # Candle mode
            effect_packet = bytearray.fromhex("00 04 80 00 00 09 0a 0b 39 d1 ff 00 00 18 2e 03 52")
            effect_packet[10:13] = self.get_rgb_color()
            effect_packet[13]    = round(0x1f - (self.effect_speed - 1) * (0x1f - 0x01) / (100 - 1))
            effect_packet[14]    = self.get_brightness_percent()
            effect_packet[16]    = sum(effect_packet[8:16]) & 0xFF
            LOGGER.debug(f"Candle effect packet : {' '.join([f'{byte:02X}' for byte in effect_packet])}")
            #return effect_packet
        if 200 <= effect_id <= 300: # Sound reactive mode
            LOGGER.debug("Sound reactive mode not implemented")
            #return None
            effect_packet = None
        else:
            effect_packet     = bytearray.fromhex("00 15 80 00 00 05 06 0b 38 25 01 64 c2")
            self.color_mode   = ColorMode.BRIGHTNESS # 2024.2 Allows setting color mode for changing effects brightness.  Effects above here support RGB, so only set here.
            effect_packet[9]  = effect_id
            # Convert speed from percentage (0-100) to a value between 0x1f and 0x01
            # 0x01 = 100% and 0x1f = 1%
            speed = round(0x1f - (self.effect_speed - 1) * (0x1f - 0x01) / (100 - 1))
            effect_packet[10] = speed
            effect_packet[11] = self.get_brightness_percent()
            effect_packet[12] = sum(effect_packet[8:11]) & 0xFF
            LOGGER.debug(f"Effect packet: {' '.join([f'{byte:02X}' for byte in effect_packet])}")
        LOGGER.debug(f"Set Effect. Effect {self.effect} Brightness {self.get_brightness_percent()} Speed {self.effect_speed}")
        LOGGER.debug(f"Effect packet to send: {' '.join([f'0x{byte:02x}' for byte in effect_packet]) if effect_packet else 'None'}")
        return effect_packet
        
    def set_brightness(self, brightness):
        if brightness == self.brightness:
            LOGGER.debug(f"Brightness already set to {brightness}")
            return
        else:
            # Normalise brightness to 0-255
            self.brightness = min(255, max(0, brightness))
        if self.color_mode == ColorMode.HS:
            return self.set_color(self.hs_color, brightness)
        elif self.color_mode == ColorMode.BRIGHTNESS:
            return self.set_effect(self.effect, brightness)
        else:
            LOGGER.error(f"Unknown colour mode: {self.color_mode}")
            return
    
    def set_led_settings(self, options: dict):
        LOGGER.debug(f"Setting LED settings: {options}")
        color_order = options.get(const.CONF_COLORORDER)
        self._delay = options.get(const.CONF_DELAY, 120)
        if color_order is None:
            LOGGER.error("LED colour order is None and shouldn't be.  Not setting LED settings.")
            return
        else:
            # Convert from const.ColorOrdering to local ColorOrdering if needed
            if hasattr(color_order, 'name'):
                # It's an enum member, get the name and map to local enum
                local_color_order = ColorOrdering[color_order.name]
                self.color_order = local_color_order
            else:
                self.color_order = color_order
        
        LOGGER.debug(f"Setting LED settings: Colour order: {self.color_order}")
        led_settings_packet     = bytearray.fromhex("00 04 80 00 00 05 06 0b 62 00 01 0f 72")
        led_settings_packet[10] = self.color_order.value
        led_settings_packet[12] = sum(led_settings_packet[8:12]) & 0xFF
        LOGGER.debug(f"LED settings packet: {' '.join([f'{byte:02X}' for byte in led_settings_packet])}")
        # REMEMBER: The calling function must also call stop() on the device to apply the settings
        return led_settings_packet
    
    def notification_handler(self, data):
        notification_data = data.decode("utf-8", errors="ignore")
        
        # Check if this is a JSON-wrapped notification (0x62 devices)
        if notification_data.strip().startswith('{'):
            try:
                import json
                json_data = json.loads(notification_data)
                # Check if payload is a hex string (not a nested object)
                if isinstance(json_data.get('payload'), str):
                    payload = json_data['payload']
                else:
                    # This is device info JSON, not state - ignore it
                    LOGGER.debug(f"JSON device info notification (ignoring): {json_data}")
                    return None
            except (json.JSONDecodeError, KeyError) as e:
                LOGGER.debug(f"Failed to parse JSON notification: {e}")
                return None
        else:
            # Original format: extract hex from quotes
            last_quote = notification_data.rfind('"')
            if last_quote > 0:
                first_quote = notification_data.rfind('"', 0, last_quote)
                if first_quote > 0:
                    payload = notification_data[first_quote+1:last_quote]
                else:
                    return None
            else:
                return None
        
        # Validate and parse hex payload
        if not all(c in "0123456789abcdefABCDEF" for c in payload):
            LOGGER.debug(f"Non-hex notification received (ignoring): {payload}")
            return None
        
        try:
            payload = bytearray.fromhex(payload)
        except ValueError:
            LOGGER.debug(f"Failed to parse hex payload (ignoring): {payload}")
            return None
        
        LOGGER.debug(f"N: Response Payload: {' '.join([f'{i}:{byte:02X}' for i, byte in enumerate(payload)])}")
        # return
        if payload[0] == 0x81:
            # Status request response
            power           = payload[2]
            mode            = payload[3]
            selected_effect = payload[4]
            self.is_on      = True if power == 0x23 else False

            if mode == 0x61:
                if selected_effect == 0x23:
                    # Light is in colour mode
                    rgb_color = (payload[6], payload[7], payload[8])
                    hsv_color = super().rgb_to_hsv(rgb_color)
                    self.hs_color = tuple(hsv_color[0:2])
                    
                    # Don't recalculate brightness from RGB - preserve what we sent
                    # Device may round RGB values causing brightness drift
                    # Only update brightness if it's currently None (initial state)
                    if self.brightness is None or self.brightness == 0:
                        self.brightness = int(hsv_color[2])
                        # Ensure non-zero default brightness for powered on devices
                        if self.brightness == 0:
                            self.brightness = 255
                    
                    LOGGER.debug(f"RGB colour: {rgb_color}")
                    LOGGER.debug(f"HS colour: {self.hs_color}")
                    LOGGER.debug(f"Brightness: {self.brightness}")

                    self.effect = EFFECT_OFF
                    self.color_mode = ColorMode.HS
                    self.color_temperature_kelvin = None
            elif mode in EFFECT_ID_TO_NAME_0x54:
                # Effect mode - the mode byte IS the effect ID!
                # Effect IDs range from 36-100, plus special values (100=Candle, 200=Sound)
                # Byte 3 is the effect ID (0x2E = Effect 10, 0x37 = Effect 19, etc.)
                # Byte 4 is 0x23 (consistent across modes, meaning unclear - sub-mode?)
                # Byte 5 is the effect speed (inverted: 0x01=fastest/100%, 0x1F=slowest/1%)
                effect_id = mode  # mode byte IS the effect ID!
                selected_effect = payload[4]  # Always 0x23 in observed cases
                # Convert device speed (0x01-0x1F) to percentage (100%-1%)
                speed_raw = payload[5]
                self.effect_speed = round((0x1f - speed_raw) * (100 - 1) / (0x1f - 0x01) + 1)
                self.color_mode = ColorMode.BRIGHTNESS
                self.effect = EFFECT_ID_TO_NAME_0x54[effect_id]
                LOGGER.debug(f"Effect mode: {self.effect} (ID: 0x{effect_id:02X}, Speed: {self.effect_speed}% [raw: 0x{speed_raw:02X}])")
                
                # Effect mode notifications don't contain brightness data
                # Bytes 6-8 are not RGB color - meaning unknown
                # Brightness is controlled but not echoed back by the device
                # Keep existing brightness value, default to 255 if not set
                if self.brightness is None or self.brightness == 0:
                    self.brightness = 255
            elif mode == 0x5f:
                # Alternative effect mode identifier
                LOGGER.debug("Effect mode notification (0x5f)?")
            #     elif selected_effect == 0x01:
            #         self.color_mode = ColorMode.HS
            #         self.effect = EFFECT_OFF
            #         hs_color = self.rgb_to_hsv(payload[6:9])
            #         self.hs_color = hs_color[0:2]
            #         self.brightness = hs_color[2]
            #     elif 0x02 <= selected_effect <= 0x0a:
            #         self.color_mode = ColorMode.HS
            #         self.effect = EFFECT_ID_TO_NAME_0x62[selected_effect << 8]
            #         self.effect_speed = payload[5]
            #         # TODO: What about colours and brightness?
            # elif mode == 0x62:
            #     # Music reactive mode
            #     # TODO: Brightness?
            #     effect = payload[4]
            #     scaled_effect = (effect + 0x32) << 8
            #     try:
            #         self.effect = EFFECT_ID_TO_NAME_0x62[scaled_effect]
            #     except KeyError:
            #         self.effect = "Unknown"
            # elif mode == 0x25:
            #     # Effects mode
            #     self.effect = EFFECT_ID_TO_NAME_0x62[selected_effect]
            #     self.effect_speed = payload[5]
            #     self.color_mode = ColorMode.BRIGHTNESS
            #     self.brightness = int(payload[6] * 255 // 100)
        
        elif payload[1] == 0x63:
            LOGGER.debug("LED settings response received")
            #self.led_count = int.from_bytes(bytes([payload[2], payload[3]]), byteorder='big') * payload[5]
            #self.chip_type = const.LedTypes_StripLight.from_value(payload[6])
            #self.color_order = const.ColorOrdering.from_value(payload[7])


