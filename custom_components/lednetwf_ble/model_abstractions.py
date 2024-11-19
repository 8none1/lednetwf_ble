# Defines the byte patterns for the various commands
# We need to define the bytes, plus the offsets for each of the parameters
# Some devices support HS colours, some only support RGB so we need to create an abstraction layer too
import logging
import colorsys
#from homeassistant.components.light import (ColorMode)
#from homeassistant.components.light import EFFECT_OFF
from homeassistant.components.light import (
    ColorMode,
    EFFECT_OFF,
    LightEntityFeature
)

from .const import (
    EFFECTS_LIST_0x53,
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

LOGGER = logging.getLogger(__name__)

def rgb_to_hsv(rgb):
    # Home Assistant expects HS in the range 0-360, 0-100
    h,s,v = colorsys.rgb_to_hsv(rgb[0]/255.0, rgb[1]/255.0, rgb[2]/255.0)
    return [int(h*360), int(s*100), int(v*100)]

def hsv_to_rgb(hsv):
    # Home Assistant expects RGB in the range 0-255
    r,g,b = colorsys.hsv_to_rgb(hsv[0]/360.0, hsv[1]/100.0, hsv[2]/100.0)
    return [int(r*255), int(g*255), int(b*255)]

class DefaultLEDNETDevice:
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
        manu_data_id        = next(iter(manu_data))
        self.manu_data      = bytearray(manu_data[manu_data_id])
        self.fw_major       = self.manu_data[0]
        self.fw_minor       = f'{self.manu_data[8]:02X}{self.manu_data[9]:02X}.{self.manu_data[10]:02X}'
        self.led_count      = self.manu_data[24]
        self.chip_type      = None
        self.color_order    = None
        self.is_on          = True if self.manu_data[14] == 0x23 else False
        self.brightness     = None
        self.hs_color       = None
        self.effect         = EFFECT_OFF
        self.effect_speed   = 50
        self.color_mode     = ColorMode.UNKNOWN
        self.icon           = "mdi:lightbulb"
        self.max_color_temp = 6500
        self.min_color_temp = 2700
        self.supported_color_modes   = {ColorMode.UNKNOWN}
        self.supported_features      = LightEntityFeature.EFFECT
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
        return hsv_to_rgb((self.hs_color[0], self.hs_color[1], self.brightness))
    def turn_on(self):
        self.is_on = True
        return bytearray.fromhex("00 01 80 00 00 0d 0e 0b 3b 23 00 00 00 00 00 00 00 32 00 00 90")
    def turn_off(self):
        self._is_on = False
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
        
class Model0x53(DefaultLEDNETDevice):
    # Ring light
    def __init__(self, manu_data):
        LOGGER.debug("Model 0x53 init")
        super().__init__(manu_data)
        self.supported_color_modes = {ColorMode.HS, ColorMode.COLOR_TEMP}
        self.icon = "mdi:lightbulb"
        if self.manu_data[15] == 0x61:
            if self.manu_data[16] == 0xf0:
                # RGB mode
                rgb_color = (self.manu_data[18], self.manu_data[19], self.manu_data[20])
                self.hs_color = tuple(rgb_to_hsv(rgb_color)[0:2])
                self.brightness = rgb_to_hsv(rgb_color)[2]
                self.color_mode = ColorMode.HS
                LOGGER.debug(f"From manu RGB colour: {rgb_color}")
                LOGGER.debug(f"From manu HS colour: {self.hs_color}")
                LOGGER.debug(f"From manu Brightness: {self.brightness}")
            elif self.manu_data[16] == 0x0f:
                # White mode
                col_temp = self.manu_data[21]
                white_brightness = self.manu_data[17]
                self.color_temperature_kelvin = self.min_color_temp + col_temp * (self.max_color_temp - self.min_color_temp) / 100
                self.brightness = int(white_brightness * 255 // 100)
                self.color_mode = ColorMode.COLOR_TEMP
            else:
                LOGGER.error(f"Unknown colour mode: {self.manu_data[16]}. Assuming RGB")
                raise NotImplementedError("Unknown colour mode")
        elif self.manu_data[15] == 0x62:
            # Music reactive mode.  Do the ring lights support this?
            # I don't think so, so...
            LOGGER.debug(f"Music reactive mode detected on 0x53 device, but not supported here")
        elif self.manu_data[15] == 0x25:
            # Effect mode
            self.effect       = EFFECTS_LIST_0x53[self.manu_data[16]-1]
            self.effect_speed = self.manu_data[19]
            self.brightness   = int(self.manu_data[18] * 255 // 100)
            self.color_mode   = ColorMode.BRIGHTNESS
        LOGGER.debug(f"Effect: {self.effect}")
        LOGGER.debug(f"Effect speed: {self.effect_speed}")
        LOGGER.debug(f"Brightness: {self.brightness}")
        LOGGER.debug(f"LED count: {self.led_count}")
        LOGGER.debug(f"Firmware version: {self.fw_major}.{self.fw_minor}")
        LOGGER.debug(f"Is on: {self.is_on}")
        LOGGER.debug(f"Colour mode: {self.color_mode}")
        LOGGER.debug(f"Effect: {self.effect}")
        LOGGER.debug(f"Effect speed: {self.effect_speed}")
        LOGGER.debug(f"Brightness: {self.brightness}")
        LOGGER.debug(f"HS colour: {self.hs_color}")

    def set_color_temp_kelvin(self, color_temp_kelvin: int, brightness: int):
        # Returns the byte array to set the colour temperature
        LOGGER.debug(f"Setting colour temperature: {color_temp_kelvin}")
        self.color_mode = ColorMode.COLOR_TEMP
        self.brightness = brightness
        self.effect = EFFECT_OFF
        color_temp_kelvin = max(2700, min(color_temp_kelvin, 6500))
        self.color_temperature_kelvin = color_temp_kelvin
        color_temp_pct = int((color_temp_kelvin - 2700) * 100 / (6500 - 2700))
        color_temp_kelvin_packet = bytearray.fromhex("00 10 80 00 00 0d 0e 0b 3b b1 00 00 00 00 00 00 00 00 00 00 3d")
        color_temp_kelvin_packet[13] = color_temp_pct
        color_temp_kelvin_packet[14] = self.get_brightness_percent()
        return color_temp_kelvin_packet

    def set_color(self, hs_color, brightness):
        # Returns the byte array to set the HS colour
        self.color_mode = ColorMode.HS
        self.hs_color   = hs_color
        self.brightness = brightness
        self.effect     = EFFECT_OFF
        hue = int(self.hs_color[0] / 2) # This device divides hue by two, I assume to fit in one byte
        saturation = int(self.hs_color[1])
        color_hs_packet = bytearray.fromhex("00 00 80 00 00 0d 0e 0b 3b a1 00 64 64 00 00 00 00 00 00 00 00")
        color_hs_packet[10] = hue
        color_hs_packet[11] = saturation
        color_hs_packet[12] = self.get_brightness_percent()
        LOGGER.debug(f"Setting HS colour: {hue}, {saturation}, {self.get_brightness_percent()}")
        return color_hs_packet

    def set_effect(self, effect, brightness):
        # Returns the byte array to set the effect
        LOGGER.debug(f"Setting effect: {effect}")      
        if effect not in EFFECTS_LIST_0x53:
            raise ValueError(f"Effect '{effect}' not in EFFECTS_LIST_0x53")
        # Deal with special case "All modes" effect.  It must always be the last effect in the list
        if effect == EFFECTS_LIST_0x53[-1]:
            effect_id = 0xFF
        else:
            effect_id = EFFECTS_LIST_0x53.index(effect)+1
        self.effect      = effect
        self.brightness  = brightness
        self.color_mode  = ColorMode.BRIGHTNESS
        effect_packet     = bytearray.fromhex("00 00 80 00 00 04 05 0b 38 01 32 64") if self._model == RING_LIGHT_MODEL else bytearray.fromhex("00 00 80 00 00 05 06 0b 42 01 32 64 d9")
        effect_packet[9]  = effect_id
        effect_packet[10] = self.effect_speed
        effect_packet[11] = self.get_brightness_percent()
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
        elif self.color_mode == ColorMode.COLOR_TEMP:
            return self.set_color_temp_kelvin(self.color_temperature_kelvin, brightness)
        elif self.color_mode == ColorMode.BRIGHTNESS:
            return self.set_effect(self.effect, brightness)
        else:
            LOGGER.error(f"Unknown colour mode: {self.color_mode}")
            return
    
    def set_led_settings(self, options: dict):
        led_count   = options.get(CONF_LEDCOUNT)
        chip_type   = options.get(CONF_LEDTYPE)
        color_order = options.get(CONF_COLORORDER)
        self._delay = options.get(CONF_DELAY, 120)
        if led_count is None or chip_type is None or color_order is None:
            LOGGER.error("LED count, chip type or colour order is None and shouldn't be.  Not setting LED settings.")
            return
        else:
            self.chip_type         = getattr(LedTypes_RingLight, chip_type).value
            self.color_order       = getattr(ColorOrdering, color_order).value
            self.led_count         = led_count
        led_settings_packet     = bytearray.fromhex("00 00 80 00 00 06 07 0a 62 00 0e 01 00 71")
        led_settings_packet[10] = led_count & 0xFF
        led_settings_packet[11] = chip_type
        led_settings_packet[12] = color_order
        led_settings_packet[13] = sum(led_settings_packet[8:12]) & 0xFF
        LOGGER.debug(f"LED settings packet: {' '.join([f'{byte:02X}' for byte in led_settings_packet])}")
        # REMEMBER: The calling function must also call stop() on the device to apply the settings
        return led_settings_packet
    
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
            led_count       = payload[12]
            self.is_on      = True if power == 0x23 else False

            if mode == 0x61:
                if selected_effect == 0xf0:
                    # Light is in colour mode
                    rgb_color = (payload[6], payload[7], payload[8])
                    hsv_color = rgb_to_hsv(rgb_color)
                    self.hs_color = tuple(hsv_color[0:2])
                    self.brightness = int(hsv_color[2] * 255 // 100)
                    self.effect = EFFECT_OFF
                    self.color_mode = ColorMode.HS
                    self.color_temperature_kelvin = None
                elif selected_effect == 0x0f:
                    # Light is in white mode
                    col_temp = payload[9]
                    self.color_temperature_kelvin = self.min_color_temp + col_temp * (self.max_color_temp - self.min_color_temp) / 100
                    self.brightness = int(payload[5] * 255 // 100)
                    self.effect = EFFECT_OFF
                    self.color_mode = ColorMode.COLOR_TEMP
                elif selected_effect == 0x01:
                    LOGGER.debug(f"Light is in RGB mode?  This shouldn't happen with this device")
            elif mode == 0x25:
                # Effects mode
                self.effect = EFFECTS_LIST_0x53[selected_effect-1]
                self.effect_speed = payload[7]
                self.color_mode = ColorMode.BRIGHTNESS
                self.brightness = int(payload[6] * 255 // 100)
        elif payload[0] == 0x63:
            LOGGER.debug(f"LED settings response received")
            self.led_count = payload[2]
            self.chip_type = LedTypes_RingLight.from_value(payload[3])
            self.color_order = ColorOrdering.from_value(payload[4])






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


