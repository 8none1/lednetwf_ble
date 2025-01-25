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

class Model0x5b(DefaultModelAbstraction):
    # CCT only strip
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
            self.hs_color = None
            self.brightness = 255
            self.effect = EFFECT_OFF
            self.led_count = None
        else:
            if self.manu_data[15] == 0x61:
                # if self.manu_data[16] == 0xf0:
                #     # RGB mode
                #     rgb_color       = (self.manu_data[18], self.manu_data[19], self.manu_data[20])
                #     self.hs_color   = tuple(super().rgb_to_hsv(rgb_color)[0:2])
                #     self.brightness = super().rgb_to_hsv(rgb_color)[2]
                #     self.color_mode = ColorMode.HS
                #     #self.color_temperature_kelvin = self.min_color_temp
                #     LOGGER.debug(f"From manu RGB colour: {rgb_color}")
                #     LOGGER.debug(f"From manu HS colour: {self.hs_color}")
                #     LOGGER.debug(f"From manu RGB Brightness: {self.brightness}")
                if self.manu_data[16] == 0x0f:
                    # White mode
                    self.color_temperature_kelvin = self.min_color_temp + self.manu_data[21] * (self.max_color_temp - self.min_color_temp) / 100
                    self.brightness               = int(self.manu_data[17] * 255 // 100) # This one is in range 0-FF
                    self.color_mode               = ColorMode.COLOR_TEMP
                    LOGGER.debug(f"From manu data white brightness: {self.brightness}")
                # else:
                #     LOGGER.error(f"Unknown colour mode: {self.manu_data[16]}. Assuming RGB")
                #     raise NotImplementedError("Unknown colour mode")
            # elif self.manu_data[15] == 0x25:
            #     # Effect mode
            #     LOGGER.debug(f"Effect mode detected. self.manu_data: {self.manu_data}")
            #     effect = self.manu_data[16]
            #     if effect < len(EFFECTS_LIST_0x53):
            #         self.effect = EFFECTS_LIST_0x53[effect - 1]
            #     elif effect == 0xFF:
            #         self.effect = EFFECTS_LIST_0x53[-1]
            #     else:
            #         LOGGER.error(f"Unknown effect: {effect}")
            #         raise NotImplementedError("Unknown effect")
            #     self.effect_speed = self.manu_data[19]
            #     self.brightness   = int(self.manu_data[18] * 255 // 100)
            #     self.color_mode   = ColorMode.BRIGHTNESS
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

    def set_brightness(self, brightness):
        if brightness == self.brightness:
            LOGGER.debug(f"Brightness already set to {brightness}")
            return
        else:
            # Normalise brightness to 0-255
            self.brightness = min(255, max(0, brightness))
        if self.color_mode == ColorMode.COLOR_TEMP:
            return self.set_color_temp_kelvin(self.color_temperature_kelvin, brightness)
        else:
            LOGGER.error(f"Unknown colour mode: {self.color_mode}")
            return
    
    def set_led_settings(self, options: dict):
        LOGGER.debug(f"Setting LED settings: {options}")
        # Don't know how to handle this yet
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
        last_quote = notification_data.rfind('"')
        if last_quote > 0:
            first_quote = notification_data.rfind('"', 0, last_quote)
            if first_quote > 0:
                payload = notification_data[first_quote+1:last_quote]
            else:
                return None
        else:
            return None
        payload = bytearray.fromhex(payload)
        LOGGER.debug(f"N: Response Payload: {' '.join([f'{byte:02X}' for byte in payload])}")
        if payload[0] == 0x81:
            # Status request response
            power           = payload[2]
            mode            = payload[3]
            selected_effect = payload[4]
            self.led_count  = payload[12]
            self.is_on      = True if power == 0x23 else False

            # if mode == 0x61:
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
