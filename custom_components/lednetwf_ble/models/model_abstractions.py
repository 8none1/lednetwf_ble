# Defines the byte patterns for the various commands
# We need to define the bytes, plus the offsets for each of the parameters
# Some devices support HS colours, some only support RGB so we need to create an abstraction layer too

import colorsys
from homeassistant.components.light import ( # type: ignore
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
        # Initialize default attributes BEFORE calling process_manu_data
        self.chip_type                     = None
        self.color_order                   = None
        self.brightness                    = None
        self.hs_color                      = [0, 100]  # Default to red instead of None to avoid exceptions when enabling effects before selecting a colour
        self.bg_hs_color                   = [0, 0]    # Background color - defaults to white (hue 0, saturation 0 = white)
        self.bg_brightness                 = None      # Background brightness - will be set to current brightness when first used
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
        self.INITIAL_PACKET                = bytearray.fromhex("00 01 80 00 00 04 05 0a 81 8a 8b 96")
        self.GET_LED_SETTINGS_PACKET       = bytearray.fromhex("00 02 80 00 00 05 06 0a 63 12 21 f0 86")
        
        # Now parse manufacturer data (may override defaults)
        self.process_manu_data(manu_data)

    def process_manu_data(self, manu_data):
        if manu_data:
            manu_data_str = ' '.join(f'0x{byte:02X}' for byte in manu_data[next(iter(manu_data))])
            LOGGER.debug(f"Manu data: {manu_data_str}")
            manu_data_id           = next(iter(manu_data))
            self.manu_data         = bytearray(manu_data[manu_data_id])
            self.fw_major          = self.manu_data[0]
            self.fw_minor          = f'{self.manu_data[8]:02X}{self.manu_data[9]:02X}.{self.manu_data[10]:02X}'
            self.led_count         = self.manu_data[24]
            # Parse power state: 0x23 = on, 0x24 = off, anything else = unknown
            if self.manu_data[14] == 0x23:
                self.is_on = True
                LOGGER.debug(f"Updated is_on from manu data: True (byte 14 = 0x23)")
            elif self.manu_data[14] == 0x24:
                self.is_on = False
                LOGGER.debug(f"Updated is_on from manu data: False (byte 14 = 0x24)")
            else:
                LOGGER.warning(f"Unknown power state in manu data: 0x{self.manu_data[14]:02X}, setting to None")
                self.is_on = None
        else:
            LOGGER.debug("No manu data")
            self.manu_data         = bytearray(25)
            self.fw_major          = 0x00
            self.fw_minor          = "Unknown version"
            self.led_count         = None
            self.chip_type         = None
            self.color_order       = None
            self.is_on             = None  # No data means unknown state

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
    def get_bg_hs_color(self):
        # Return background HS colour in the range 0-360, 0-100 (Home Assistant format)
        return self.bg_hs_color
    def get_bg_rgb_color(self):
        # Return background RGB colour in the range 0-255
        # Initialize bg_brightness on first use if still None
        if self.bg_brightness is None:
            self.bg_brightness = self.brightness if self.brightness is not None else 255
            LOGGER.debug(f"Initialized bg_brightness to {self.bg_brightness} in get_bg_rgb_color")
        return self.hsv_to_rgb((self.bg_hs_color[0], self.bg_hs_color[1], self.bg_brightness))
    def update_bg_color_state(self, rgb_color):
        # Update background color state from RGB values
        hsv_color = self.rgb_to_hsv(rgb_color)
        self.bg_hs_color = tuple(hsv_color[0:2])
        self.bg_brightness = int(hsv_color[2])
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

