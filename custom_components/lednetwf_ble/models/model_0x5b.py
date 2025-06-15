from .model_abstractions import DefaultModelAbstraction
from .. import const

import logging
LOGGER = logging.getLogger(__name__)

import colorsys
from homeassistant.components.light import (
    ColorMode,
    EFFECT_OFF
)

SUPPORTED_MODELS = [0x5B]

# 0x5B Effect data
EFFECT_MAP_0x5b = {}
for e in range(37,58): # 0x25 onwards
    EFFECT_MAP_0x5b[f"Effect {e-37}"] = e
EFFECT_MAP_0x5b["_Effect Off"]        = 0
EFFECT_MAP_0x5b["RGB Jump"]           = 0x63
EFFECT_MAP_0x5b["Candle Mode"]        = 100
# EFFECT_MAP_0x5b["Sound Reactive"]     = 200
EFFECT_LIST_0x5b = sorted(EFFECT_MAP_0x5b)
EFFECT_ID_TO_NAME_0x5b = {v: k for k, v in EFFECT_MAP_0x5b.items()}


class Model0x5b(DefaultModelAbstraction):
    # CCT only strip & Sunrise lamps
    def __init__(self, manu_data):
        LOGGER.debug("Model 0x5B init")
        super().__init__(manu_data)
        self.SUPPORTED_VERSIONS    = SUPPORTED_MODELS
        self.supported_color_modes = {ColorMode.COLOR_TEMP}
        self.icon                  = "mdi:led-strip-variant"
        self.effect_list           = None
        self.effect                = EFFECT_OFF
        self.model_specific_manu_data(manu_data)

    def model_specific_manu_data(self, manu_data):
        if manu_data is None:
            LOGGER.debug("Manu data is None, using defaults")
            self.color_mode = ColorMode.COLOR_TEMP
            self.hs_color   = None
            self.brightness = 255
            self.effect     = EFFECT_OFF
            self.led_count  = None
        else:
            if self.manu_data[15] == 0x61:
                # Solid colour mode
                if self.manu_data[16] == 0x23:
                    # RGB mode - Could be a sun rise lamp?
                    rgb_color                    = (self.manu_data[18], self.manu_data[19], self.manu_data[20])
                    self.hs_color                = tuple(super().rgb_to_hsv(rgb_color)[0:2])
                    self.brightness              = super().rgb_to_hsv(rgb_color)[2]
                    self.color_mode              = ColorMode.HS
                    self.supported_color_modes   = {ColorMode.HS}
                    self.effect_list             = EFFECT_LIST_0x5b
                    self.effect                  = EFFECT_OFF
                    self.icon                    = "mdi:lightbulb"
                    self.GET_LED_SETTINGS_PACKET = bytearray.fromhex("00 05 80 00 00 02 03 07 22 22")
                    self.led_count               = 1
                    LOGGER.debug(f"Setting led count to 1 for RGB mode")
                    # self.color_temperature_kelvin = self.min_color_temp
                    LOGGER.debug(f"From manu RGB colour: {rgb_color}")
                    LOGGER.debug(f"From manu HS colour: {self.hs_color}")
                    LOGGER.debug(f"From manu RGB Brightness: {self.brightness}")
                if self.manu_data[16] == 0x0f:
                    # White mode - seems to be a CCT strip
                    self.color_temperature_kelvin = self.min_color_temp + self.manu_data[21] * (self.max_color_temp - self.min_color_temp) / 100
                    self.brightness               = int(self.manu_data[17] * 255 // 100) # This one is in range 0-FF
                    self.color_mode               = ColorMode.COLOR_TEMP
                    LOGGER.debug(f"From manu data white brightness: {self.brightness}")
                # else:
                #     LOGGER.error(f"Unknown colour mode: {self.manu_data[16]}. Assuming RGB")
                #     raise NotImplementedError("Unknown colour mode")
            elif 0x25 <= self.manu_data[15] <= 0x3a or self.manu_data[15] == 0x63:
                # Effect mode of RGB device
                effect = self.manu_data[15]
                speed  = self.manu_data[17]
                # Convert from device speed (0x1f = 1%, 0x01 = 100%) to percentage (0-100)
                self.effect_speed = round((0x1f - speed) * (100 - 1) / (0x1f - 0x01) + 1)
                LOGGER.debug(f"Manu effect speed: {self.effect_speed}")
                self.effect                  = EFFECT_ID_TO_NAME_0x5b[effect]
                self.supported_color_modes   = {ColorMode.HS, ColorMode.BRIGHTNESS}
                self.effect_list             = EFFECT_LIST_0x5b
                self.icon                    = "mdi:lightbulb"
                self.GET_LED_SETTINGS_PACKET = bytearray.fromhex("00 05 80 00 00 02 03 07 22 22")
                self.led_count               = 1
                self.color_mode              = ColorMode.BRIGHTNESS
                # self.brightness   = int(self.manu_data[18] * 255 // 100)
                self.is_on        = True if self.manu_data[14] == 0x23 else False

        # LOGGER.debug(f"Effect: {self.effect}")
        # LOGGER.debug(f"Effect speed: {self.effect_speed}")
        LOGGER.debug(f"Brightness: {self.brightness}")
        LOGGER.debug(f"LED count: {self.led_count}")
        LOGGER.debug(f"Firmware version: {self.fw_major}.{self.fw_minor}")
        LOGGER.debug(f"Is on: {self.is_on}")
        LOGGER.debug(f"Colour mode: {self.color_mode}")
        # LOGGER.debug(f"HS colour: {self.hs_color}")

    def set_color_temp_kelvin(self, color_temp_kelvin: int, brightness: int):
        # Returns the byte array to set the colour temperature
        LOGGER.debug(f"Setting colour temperature: {color_temp_kelvin}")
        self.color_mode = ColorMode.COLOR_TEMP
        self.brightness = brightness
        self.effect = EFFECT_OFF
        if color_temp_kelvin is None:
            LOGGER.debug("color_temp_kelvin is None")
            color_temp_kelvin = self.min_color_temp
        color_temp_kelvin = max(2700, min(color_temp_kelvin, 6500))
        self.color_temperature_kelvin = color_temp_kelvin
        color_temp_pct = int((color_temp_kelvin - 2700) * 100 / (6500 - 2700))
        color_temp_kelvin_packet = bytearray.fromhex("00 10 80 00 00 0d 0e 0b 3b b1 00 00 00 00 00 00 00 00 00 00 3d")
        color_temp_kelvin_packet[13] = color_temp_pct
        color_temp_kelvin_packet[14] = self.get_brightness_percent()
        return color_temp_kelvin_packet
    
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
            LOGGER.debug(f"Setting effect: {effect}")
            LOGGER.debug(f"Setting effect brightness: {brightness}")
            if effect not in EFFECT_LIST_0x5b:
                raise ValueError(f"Effect '{effect}' not in EFFECTS_LIST_0x5b")
            self.effect     = effect
            self.brightness = 255 if brightness is None else brightness
            effect_id       = EFFECT_MAP_0x5b.get(effect)

            if effect_id == 0: # Effect off
                self.set_color(self.hs_color, self.brightness)
                return None
            if 100 <= effect_id <= 200: # Candle mode
                effect_packet = bytearray.fromhex("00 04 80 00 00 09 0a 0b 39 d1 ff 00 00 18 2e 03 52")
                effect_packet[10:13] = self.get_rgb_color()
                effect_packet[13]    = round(0x1f - (self.effect_speed - 1) * (0x1f - 0x01) / (100 - 1))
                effect_packet[14]    = self.get_brightness_percent()
                effect_packet[16]    = sum(effect_packet[8:16]) & 0xFF
                LOGGER.debug(f"Candle effect packet : {' '.join([f'{byte:02X}' for byte in effect_packet])}")
                # return effect_packet

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

            return effect_packet

    def set_brightness(self, brightness):
        if brightness == self.brightness:
            LOGGER.debug(f"Brightness already set to {brightness}")
            return
        else:
            # Normalise brightness to 0-255
            self.brightness = min(255, max(0, brightness))
        if self.color_mode == ColorMode.COLOR_TEMP:
            return self.set_color_temp_kelvin(self.color_temperature_kelvin, brightness)
        elif self.color_mode == ColorMode.HS:
            return self.set_color(self.hs_color, brightness)
        else:
            LOGGER.error(f"Unknown colour mode: {self.color_mode}")
            return
    
    def set_led_settings(self, options: dict):
        LOGGER.debug(f"Setting LED settings: {options}")
        # Don't know how to handle this device's settings yet, so returning None
        return None
        # led_count   = options.get(const.CONF_LEDCOUNT)
        # chip_type   = options.get(const.CONF_LEDTYPE)
        # color_order = options.get(const.CONF_COLORORDER)
        # self._delay = options.get(const.CONF_DELAY, 120)
        # if led_count is None or chip_type is None or color_order is None:
        #     LOGGER.error("LED count, chip type or colour order is None and shouldn't be.  Not setting LED settings.")
        #     return
        # else:
        #     self.chip_type         = getattr(const.LedTypes_RingLight, chip_type).value
        #     self.color_order       = getattr(const.ColorOrdering, color_order).value
        #     self.led_count         = led_count
        # LOGGER.debug(f"Setting LED count: {self.led_count}, Chip type: {self.chip_type}, Colour order: {self.color_order}")
        # led_settings_packet     = bytearray.fromhex("00 00 80 00 00 06 07 0a 62 00 0e 01 00 71")
        # led_settings_packet[10] = self.led_count & 0xFF
        # led_settings_packet[11] = self.chip_type
        # led_settings_packet[12] = self.color_order
        # led_settings_packet[13] = sum(led_settings_packet[8:12]) & 0xFF
        # LOGGER.debug(f"LED settings packet: {' '.join([f'{byte:02X}' for byte in led_settings_packet])}")
        # # REMEMBER: The calling function must also call stop() on the device to apply the settings
        # return led_settings_packet
    
    def notification_handler(self, data):
        notification_data = data.decode("utf-8", errors="ignore")
        LOGGER.debug(f"N: Notification data: {notification_data}")
        last_quote = notification_data.rfind('"')
        if last_quote > 0:
            first_quote = notification_data.rfind('"', 0, last_quote)
            if first_quote > 0:
                payload = notification_data[first_quote+1:last_quote]
                if any(c not in "0123456789abcdefABCDEF" for c in payload):
                    return None
            else:
                return None
        else:
            return None
        LOGGER.debug(f"N: Notification Payload after processing: {payload}")
        try:
            payload = bytearray.fromhex(payload)
        except ValueError as e:
            LOGGER.error(f"Error decoding notification data: {e}")
            return None
        
        LOGGER.debug(f"N: Response Payload: {' '.join([f'{byte:02X}' for byte in payload])}")
        if payload[0] == 0x81:
            # Status request response
            power           = payload[2]
            mode            = payload[3]
            selected_effect = payload[4]
            # self.led_count  = payload[12] # These devices don't send LED count in the same place I think
            self.is_on      = True if power == 0x23 else False

            if mode == 0x61:
                # Solid colour mode
                if selected_effect == 0x23:
                    # Light is in RGB mode
                    rgb_color = (payload[6], payload[7], payload[8])
                    hsv_color = super().rgb_to_hsv(rgb_color)
                    self.hs_color = tuple(hsv_color[0:2])
                    self.brightness = int(hsv_color[2]) # self.brightness = int(hsv_color[2] * 255 // 100)
                    LOGGER.debug(f"RGB colour: {rgb_color}")
                    LOGGER.debug(f"HS colour: {self.hs_color}")
                    LOGGER.debug(f"Brightness: {self.brightness}")
                    self.effect = EFFECT_OFF
                    self.color_mode = ColorMode.HS
                    self.color_temperature_kelvin = None
            elif 0x25 <= mode <= 0x3a or mode == 0x63:
                # Effect mode of RGB device
                speed  = payload[5]
                # Convert from device speed (0x1f = 1%, 0x01 = 100%) to percentage (0-100)
                self.effect_speed = round((0x1f - speed) * (100 - 1) / (0x1f - 0x01) + 1)
                LOGGER.debug(f"Effect speed: {self.effect_speed}")
                self.effect = EFFECT_ID_TO_NAME_0x5b[mode]
                LOGGER.debug(f"Effect: {self.effect}")

            #     if selected_effect == 0xf0:
            #         # Light is in colour mode
            #         rgb_color = (payload[6], payload[7], payload[8])
            #         hsv_color = super().rgb_to_hsv(rgb_color)
            #         self.hs_color = tuple(hsv_color[0:2])
            #         self.brightness = int(hsv_color[2]) # self.brightness = int(hsv_color[2] * 255 // 100)
            #         LOGGER.debug(f"RGB colour: {rgb_color}")
            #         LOGGER.debug(f"HS colour: {self.hs_color}")
            #         LOGGER.debug(f"Brightness: {self.brightness}")
            #         self.effect = EFFECT_OFF
            #         self.color_mode = ColorMode.HS
            #         self.color_temperature_kelvin = None
            #     elif selected_effect == 0x0f:
            #         # Light is in white mode
            #         col_temp = payload[9]
            #         self.color_temperature_kelvin = self.min_color_temp + col_temp * (self.max_color_temp - self.min_color_temp) / 100
            #         self.brightness = int(payload[5] * 255 // 100)
            #         # self.effect = EFFECT_OFF
            #         self.color_mode = ColorMode.COLOR_TEMP
            #     elif selected_effect == 0x01:
            #         LOGGER.debug(f"Light is in RGB mode?  This shouldn't happen with this device")
            # # elif mode == 0x25:
            #     # Effects mode
            #     self.effect = EFFECTS_LIST_0x53[selected_effect-1]
            #     self.effect_speed = payload[7]
            #     self.color_mode = ColorMode.BRIGHTNESS
            #     self.brightness = int(payload[6] * 255 // 100)
        elif payload[0] == 0x63:
            LOGGER.debug(f"LED settings response received")
            self.led_count   = payload[2]
            self.chip_type   = const.LedTypes_RingLight(payload[3]).name
            self.color_order = const.ColorOrdering(payload[4]).name
            LOGGER.debug(f"LED count: {self.led_count}, Chip type: {self.chip_type}, Colour order: {self.color_order}")
