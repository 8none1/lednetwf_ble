from .model_abstractions import DefaultModelAbstraction
from .. import const

import logging
LOGGER = logging.getLogger(__name__)

import colorsys
from homeassistant.components.light import (
    ColorMode,
    EFFECT_OFF
)

SUPPORTED_MODELS = [0x00, 0x53, 0x55] # Probably 0x55 is not supported here, but in 0x54 instead

EFFECTS_LIST_0x53 = [
    "Gold Ring",
    "Red Magenta Fade",
    "Yellow Magenta Fade",
    "Green Yellow Fade",
    "Green Blue Spin",
    "Blue Spin",
    "Purple Pink Spin",
    "Color Fade",
    "Red Blue Flash",
    "CMRGB Spin",
    "RGBYMC Follow",
    "CMYRGB Spin",
    "RGB Chase",
    "RGB Tri Reverse Spin",
    "Red Fade",
    "Blue Yellow Quad Static",
    "Red Green Quad Static",
    "Cyan Magenta Quad Static",
    "Red Green Reverse Chase",
    "Blue Yellow Reverse Chase",
    "Cyan Magenta Reverse Chase",
    "Yellow RGB Reverse Spin",
    "Cyan RGB Reverse Spin",
    "Magenta RGB Reverse Spin",
    "RGB Reverse Spin",
    "RGBY Reverse Spin",
    "Magenta RGBY Reverse Spin",
    "Cyan RGBYMC Reverse Spin",
    "White RGBYMC Reverse Spin",
    "Red Green Reverse Chase 2",
    "Blue Yellow Reverse Chase 2",
    "Cyan Pink Reverse Chase",
    "White Strobe",
    "White Strobe 2",
    "Warm White Strobe",
    "Smooth Color Fade",
    "White Static",
    "Pinks Fade",
    "Cyans Fade",
    "Cyan Magenta Slow Fade",
    "Green Yellow Fade 2",
    "RGBCMY Slow Fade",
    "Whites Fade",
    "Pink Purple Fade",
    "Cyan Magenta Fade",
    "Cyan Blue Fade",
    "Yellow Cyan Fade",
    "Red Yellow Fade",
    "RGBCMY Strobe",
    "Warm Cool White Strobe",
    "Magenta Strobe",
    "Cyan Strobe",
    "Yellow Strobe",
    "Magenta Cyan Strobe",
    "Cyan Yellow Strobe",
    "Cool White Strobe Random",
    "Warm White Strobe Random",
    "Light Green Strobe Random",
    "Magenta Strobe Random",
    "Cyan Strobe Random",
    "Oranges Ring",
    "Blue Ring",
    "RMBCGY Loop",
    "Cyan Magenta Follow",
    "Yellow Green Follow",
    "Pink Blue Follow",
    "BGP Pastels Loop",
    "CYM Follow",
    "Pink Purple Demi Spinner",
    "Blue Pink Spinner",
    "Green Spinner",
    "Blue Yellow Tri Spinner",
    "Red Yellow Tri Spinner",
    "Pink Green Tri Spinner",
    "Red Blue Demi Spinner",
    "Yellow Green Demi Spinner",
    "RGB Tri Spinner",
    "Red Magenta Demi Spinner",
    "Cyan Magenta Demi Spinner",
    "RCBM Quad Spinner",
    "RGBCMY Spinner",
    "RGB Spinner",
    "CMB Spinner",
    "Red Blue Demi Spinner",
    "Cyan Magenta Demi Spinner",
    "Yellow Orange Demi Spinner",
    "Red Blue Striped Spinner",
    "Green Yellow Striped Spinner",
    "Red Pink Yellow Striped Spinner",
    "Cyan Blue Magenta Striped Spinner",
    "Pastels Striped Spinner",
    "Rainbow Spin",
    "Red Pink Blue Spinner",
    "Cyan Magenta Spinner",
    "Green Cyan Spinner",
    "Yellow Red Spinner",
    "Rainbow Strobe",
    "Magenta Strobe",
    "Yellow Orange Demi Strobe",
    "Yellow Cyan Demi Flash",
    "White Lightening Strobe",
    "Purple Lightening Strobe",
    "Magenta Lightening Strobe",
    "Yellow Lightening Strobe",
    "Blue With Sparkles",
    "Red With Sparkles",
    "Blue With Sparkles",
    "Yellow Dissolve",
    "Magenta Dissolve",
    "Cyan Dissolve",
    "Red Green Dissolve",
    "RGB Dissolve",
    "RGBCYM Dissolve",
    "Nothing",
    "Nothing 2",
    "_Cycle Through All Modes"
]

class Model0x53(DefaultModelAbstraction):
    # Ring light
    def __init__(self, manu_data):
        LOGGER.debug("Model 0x53 init")
        super().__init__(manu_data)
        self.SUPPORTED_VERSIONS    = [0x53, 0x00] # Why am I mixing case here?  FIXME
        self.supported_color_modes = {ColorMode.HS, ColorMode.COLOR_TEMP}
        self.icon                  = "mdi:lightbulb"
        self.effect_list           = EFFECTS_LIST_0x53
        self.model_specific_manu_data(manu_data)

    def model_specific_manu_data(self, manu_data):
        if manu_data is None:
            LOGGER.debug("Manu data is None, using defaults")
            self.color_mode = ColorMode.HS
            self.hs_color = (0, 100)
            self.brightness = 255
            self.effect = EFFECT_OFF
            self.effect_speed = 50
            self.led_count = None
        else:
            if self.manu_data[15] == 0x61:
                if self.manu_data[16] == 0xf0:
                    # RGB mode
                    rgb_color       = (self.manu_data[18], self.manu_data[19], self.manu_data[20])
                    self.hs_color   = tuple(super().rgb_to_hsv(rgb_color)[0:2])
                    self.brightness = super().rgb_to_hsv(rgb_color)[2]
                    self.color_mode = ColorMode.HS
                    #self.color_temperature_kelvin = self.min_color_temp
                    LOGGER.debug(f"From manu RGB colour: {rgb_color}")
                    LOGGER.debug(f"From manu HS colour: {self.hs_color}")
                    LOGGER.debug(f"From manu RGB Brightness: {self.brightness}")
                elif self.manu_data[16] == 0x0f:
                    # White mode
                    self.color_temperature_kelvin = self.min_color_temp + self.manu_data[21] * (self.max_color_temp - self.min_color_temp) / 100
                    self.brightness               = int(self.manu_data[17] * 255 // 100) # This one is in range 0-FF
                    self.color_mode               = ColorMode.COLOR_TEMP
                    LOGGER.debug(f"From manu data white brightness: {self.brightness}")
                else:
                    LOGGER.error(f"Unknown colour mode: {self.manu_data[16]}. Assuming RGB")
                    raise NotImplementedError("Unknown colour mode")
            elif self.manu_data[15] == 0x25:
                # Effect mode
                LOGGER.debug(f"Effect mode detected. self.manu_data: {self.manu_data}")
                effect = self.manu_data[16]
                if effect < len(EFFECTS_LIST_0x53):
                    self.effect = EFFECTS_LIST_0x53[effect - 1]
                elif effect == 0xFF:
                    self.effect = EFFECTS_LIST_0x53[-1]
                else:
                    LOGGER.error(f"Unknown effect: {effect}")
                    raise NotImplementedError("Unknown effect")
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
        LOGGER.debug(f"HS colour: {self.hs_color}")

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
        effect_packet     = bytearray.fromhex("00 00 80 00 00 04 05 0b 38 01 32 64")
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
        LOGGER.debug(f"Setting LED settings: {options}")
        led_count   = options.get(const.CONF_LEDCOUNT)
        chip_type   = options.get(const.CONF_LEDTYPE)
        color_order = options.get(const.CONF_COLORORDER)
        self._delay = options.get(const.CONF_DELAY, 120)
        if led_count is None or chip_type is None or color_order is None:
            LOGGER.error("LED count, chip type or colour order is None and shouldn't be.  Not setting LED settings.")
            return
        else:
            self.chip_type         = getattr(const.LedTypes_RingLight, chip_type).value
            self.color_order       = getattr(const.ColorOrdering, color_order).value
            self.led_count         = led_count
        LOGGER.debug(f"Setting LED count: {self.led_count}, Chip type: {self.chip_type}, Colour order: {self.color_order}")
        led_settings_packet     = bytearray.fromhex("00 00 80 00 00 06 07 0a 62 00 0e 01 00 71")
        led_settings_packet[10] = self.led_count & 0xFF
        led_settings_packet[11] = self.chip_type
        led_settings_packet[12] = self.color_order
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
            self.led_count  = payload[12]
            self.is_on      = True if power == 0x23 else False

            if mode == 0x61:
                if selected_effect == 0xf0:
                    # Light is in colour mode
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
            self.led_count   = payload[2]
            self.chip_type   = const.LedTypes_RingLight.from_value(payload[3])
            self.color_order = const.ColorOrdering.from_value(payload[4])

# TODO:

# # Fix for turn of circle effect of HSV MODE(controller skips turn off animation if state is not changed since last turn on)
# Disabling for now, needs to be moved in to the 0x53 code as it is specific to that model
# if self._instance.brightness == 255:
#     temp_brightness = 254
# else:
#     temp_brightness = self._instance.brightness + 1
# if self._instance.color_mode is ColorMode.HS and ATTR_HS_COLOR not in kwargs:
#     await self._instance.set_hs_color(self._instance.hs_color, temp_brightness)
