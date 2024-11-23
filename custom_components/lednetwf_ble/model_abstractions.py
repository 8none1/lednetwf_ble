# Defines the byte patterns for the various commands
# We need to define the bytes, plus the offsets for each of the parameters
# Some devices support HS colours, some only support RGB so we need to create an abstraction layer too

import colorsys
#from homeassistant.components.light import (ColorMode)
#from homeassistant.components.light import EFFECT_OFF
from homeassistant.components.light import (
    ColorMode,
    EFFECT_OFF,
    LightEntityFeature
)

from .const import (
    # EFFECTS_LIST_0x53,
    EFFECT_MAP_0x56,
    EFFECT_LIST_0x56,
    EFFECT_ID_TO_NAME_0x56,
    RING_LIGHT_MODEL,
    STRIP_LIGHT_MODEL,
    CONF_LEDCOUNT,
    CONF_LEDTYPE,
    CONF_COLORORDER,
    CONF_LEDCOUNT,
    CONF_DELAY,
    DOMAIN,
    CONF_NAME,
    CONF_MODEL,
    LedTypes_StripLight,
    LedTypes_RingLight,
    ColorOrdering
)

import logging
LOGGER = logging.getLogger(__name__)

class DefaultModelAbstraction:
    # The different things a device needs to do are:
    # - Get/Set device info
    #  - Get Firmware version
    #  - Get/Set LED type
    #  - Get/Set LED count
    #  - Get/Set Colour ordering
    #  - Get icon
    # - Get / Set brightness
    # - Get / Set colour
    # - Get / Set white
    # - Get / Set effect
    #  - Effect speed
    #  - Effect type
    #  - Effect colour
    #  - Effect brightness
    # - Get / Set power state
    def __init__(self, manu_data):
        LOGGER.debug(f"Manu data: {manu_data}")
        manu_data_id           = next(iter(manu_data))
        self.manu_data         = bytearray(manu_data[manu_data_id])
        self.fw_major          = self.manu_data[0]
        self.fw_minor          = f'{self.manu_data[8]:02X}{self.manu_data[9]:02X}.{self.manu_data[10]:02X}'
        self.led_count         = self.manu_data[24]
        self.chip_type         = None
        self.color_order       = None
        self.is_on             = True if self.manu_data[14] == 0x23 else False
        self.brightness        = None
        self.hs_color          = None
        self.effect            = EFFECT_OFF
        self.effect_speed      = 50
        self.color_mode        = ColorMode.UNKNOWN
        self.icon              = "mdi:lightbulb"
        self.max_color_temp    = 6500
        self.min_color_temp    = 2700
        self.color_temperature_kelvin      = None
        self.supported_color_modes         = {ColorMode.UNKNOWN}
        self.supported_features            = LightEntityFeature.EFFECT
        self.WRITE_CHARACTERISTIC_UUIDS    = ["0000ff01-0000-1000-8000-00805f9b34fb"]
        self.NOTIFY_CHARACTERISTIC_UUIDS   = ["0000ff02-0000-1000-8000-00805f9b34fb"]
        self.INITIAL_PACKET          = bytearray.fromhex("00 01 80 00 00 04 05 0a 81 8a 8b 96")
        self.GET_LED_SETTINGS_PACKET = bytearray.fromhex("00 02 80 00 00 05 06 0a 63 12 21 f0 86")

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
        raise NotImplementedError("This method should be implemented by the subclass")
    def rgb_to_hsv(self,rgb):
        # Home Assistant expects HS in the range 0-360, 0-100
        h,s,v = colorsys.rgb_to_hsv(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
        return [int(h*360), int(s*100), int(v*100)]
    def hsv_to_rgb(self,hsv):
        # Home Assistant expects RGB in the range 0-255
        r,g,b = colorsys.hsv_to_rgb(hsv[0]/360.0, hsv[1]/100.0, hsv[2]/100.0)
        return [int(r*255), int(g*255), int(b*255)]        


# class Model0x56(DefaultLEDNETDevice):
#     # Strip light
#     def set_color(self, hs_color, brightness):
#                 # Returns the byte array to set the RGB colour
#     # on the device from an HS colour and a brightness
#     # By only using HS cols internally, we can make things
#     # easier to manage.  We don't have to worry about calculating
#     # brightness from RGB values
#     LOGGER.debug(f"Setting colour: {hs_color}")
#     self.color_mode = ColorMode.HS
#     self.hs_color = hs_color
#     self.brightness = brightness
#     self.effect = EFFECT_OFF
#     rgb_color = hsv_to_rgb(hs_color)
#     rgb_color = tuple(max(0, min(255, int(component * self.get_brightness_percent() / 100))) for component in rgb_color)
#     background_col = [0,0,0]
#     rgb_packet = bytearray.fromhex("00 00 80 00 00 0d 0e 0b 41 02 ff 00 00 00 00 00 32 00 00 f0 64")
#     rgb_packet[9]  = 0 # Mode "0" leaves the static current mode unchanged.  If we want this to switch the device back to an actual static RGB mode change this to 1.
#     # Leaving it as zero allows people to use the colour picker to change the colour of the static mode in realtime.  I'm not sure what I prefer.  If people want actual
#     # static colours they can change to "Static Mode 1" in the effects.  But perhaps that's not what they would expect to have to do?  It's quite hidden.
#     # But they pay off is that they can change the colour of the other static modes as they drag the colour picker around, which is pretty neat. ?
#     rgb_packet[10:13] = rgb_color
#     rgb_packet[13:16] = background_col
#     rgb_packet[16]    = self.effect_speed
#     rgb_packet[20]    = sum(rgb_packet[8:19]) & 0xFF # Checksum
#     LOGGER.debug(f"Setting RGB colour: {rgb_color}")
#     return rgb_packet


