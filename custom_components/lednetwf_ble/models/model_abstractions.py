# Defines the byte patterns for the various commands
# We need to define the bytes, plus the offsets for each of the parameters
# Some devices support HS colours, some only support RGB so we need to create an abstraction layer too

import colorsys
from homeassistant.components.light import (
    ColorMode,
    EFFECT_OFF,
    LightEntityFeature
)

from ..const import (
    LedTypes_StripLight,
    LedTypes_RingLight,
    ColorOrdering
)

import logging
LOGGER = logging.getLogger(__name__)

class DefaultModelAbstraction:
    def __init__(self, manu_data):
        self.process_manu_data(manu_data)
        self.chip_type                     = None
        self.color_order                   = None
        self.brightness                    = None
        self.hs_color                      = None
        self.effect                        = EFFECT_OFF
        self.effect_speed                  = 50
        self.color_mode                    = ColorMode.UNKNOWN
        self.icon                          = "mdi:lightbulb"
        self.max_color_temp                = 6500
        self.min_color_temp                = 2700
        self.color_temperature_kelvin      = None
        self.supported_color_modes         = {ColorMode.UNKNOWN}
        self.supported_features            = LightEntityFeature.EFFECT
        self.WRITE_CHARACTERISTIC_UUIDS    = ["0000ff01-0000-1000-8000-00805f9b34fb"]
        self.NOTIFY_CHARACTERISTIC_UUIDS   = ["0000ff02-0000-1000-8000-00805f9b34fb"]
        self.INITIAL_PACKET          = bytearray.fromhex("00 01 80 00 00 04 05 0a 81 8a 8b 96")
        self.GET_LED_SETTINGS_PACKET = bytearray.fromhex("00 02 80 00 00 05 06 0a 63 12 21 f0 86")

    def process_manu_data(self, manu_data):
        LOGGER.debug(f"Manu data: {manu_data}")
        if manu_data:
            manu_data_id           = next(iter(manu_data))
            self.manu_data         = bytearray(manu_data[manu_data_id])
            self.fw_major          = self.manu_data[0]
            self.fw_minor          = f'{self.manu_data[8]:02X}{self.manu_data[9]:02X}.{self.manu_data[10]:02X}'
            self.led_count         = self.manu_data[24]
            self.is_on             = True if self.manu_data[14] == 0x23 else False
        else:
            LOGGER.debug("No manu data")
            self.manu_data         = chr(0) * 25 # Mock manu_data to prevent truth testing errors in the future
            self.fw_major          = 0x00
            self.fw_minor          = "Unknown version"
            self.led_count         = None
            self.chip_type         = None
            self.color_order       = None
            self.is_on             = False # Needs to be something which isn't None or the device won't be "available"

    def detect_model(self):
        raise NotImplementedError("This method should be implemented by the subclass")
    def get_hs_color(self):
        # Return HS colour in the range 0-360, 0-100 (Home Assistant format)
        return self.hs_color
    def get_brightness(self):
        # Return brightness in the range 0-255
        return self.brightness
    def get_brightness_percent(self):
        # Return brightness in the range 0-100
        return int(self.brightness * 100 / 255)
    def get_rgb_color(self):
        # Return RGB colour in the range 0-255
        return self.hsv_to_rgb((self.hs_color[0], self.hs_color[1], self.brightness))
    def turn_on(self):
        self.is_on = True
        return bytearray.fromhex("00 01 80 00 00 0d 0e 0b 3b 23 00 00 00 00 00 00 00 32 00 00 90")
    def turn_off(self):
        self.is_on = False
        return bytearray.fromhex("00 01 80 00 00 0d 0e 0b 3b 24 00 00 00 00 00 00 00 32 00 00 91")
    def set_effect(self):
        return NotImplementedError("This method should be implemented by the subclass")
    def set_color(self):
        return NotImplementedError("This method should be implemented by the subclass")
    def set_brightness(self):
        return NotImplementedError("This method should be implemented by the subclass")
    def set_color_temp_kelvin(self):
        return NotImplementedError("This method should be implemented by the subclass")
    def notification_handler(self):
        LOGGER.debug("ZZZ Notification handler not implemented")
        raise NotImplementedError("This method should be implemented by the subclass")
    def rgb_to_hsv(self,rgb):
        # Home Assistant expects HS in the range 0-360, 0-100
        h,s,v = colorsys.rgb_to_hsv(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
        return [int(h*360), int(s*100), int(v*255)]
    def hsv_to_rgb(self,hsv):
        LOGGER.debug(f"HSV: {hsv}")
        # Home Assistant expects RGB in the range 0-255
        r,g,b = colorsys.hsv_to_rgb(hsv[0]/360.0, hsv[1]/100.0, hsv[2]/255.0)
        LOGGER.debug(f"RGB: {r, g, b}")
        return [int(r*255), int(g*255), int(b*255)]        

