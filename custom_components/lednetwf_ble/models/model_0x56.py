from .model_abstractions import DefaultModelAbstraction
from .. import const

import logging
LOGGER = logging.getLogger(__name__)

import colorsys
from homeassistant.components.light import (
    ColorMode,
    EFFECT_OFF
)

SUPPORTED_MODELS = [0x56]

# 0x56 Effect data
EFFECT_MAP_0x56 = {}
for e in range(1,100):
    EFFECT_MAP_0x56[f"Effect {e}"] = e
EFFECT_MAP_0x56["Cycle Modes"] = 255

# So called "static" effects.  Actually they are effects which can also be set to a specific colour.
for e in range(1,11):
    EFFECT_MAP_0x56[f"Static Effect {e}"] = e << 8 # Give the static effects much higher values which we can then shift back again in the effect function

# Sound reactive effects.  Numbered 1-15 internally, we will offset them by 50 to avoid clashes with the other effects
for e in range(1+0x32, 16+0x32):
    EFFECT_MAP_0x56[f"Sound Reactive {e-0x32}"] = e << 8

#EFFECT_MAP_0x56["_Sound Reactive"] = 0xFFFF # This is going to be a special case
EFFECT_LIST_0x56 = sorted(EFFECT_MAP_0x56)

EFFECT_ID_TO_NAME_0x56 = {v: k for k, v in EFFECT_MAP_0x56.items()}


class Model0x56(DefaultModelAbstraction):
    # Strip light
    def __init__(self, manu_data):
        LOGGER.debug("Model 0x56 init")
        super().__init__(manu_data)
        self.SUPPORTED_VERSIONS    = [0x56]
        self.supported_color_modes = {ColorMode.HS} # Actually, it supports RGB, but this will allow us to separate colours from brightness
        self.icon = "mdi:led-strip-variant"
        self.effect_list = EFFECT_LIST_0x56

        if isinstance(self.manu_data, str):
            self.manu_data = [ord(c) for c in self.manu_data]
        LOGGER.debug(f"Manu data: {[hex(x) for x in self.manu_data]}")
        LOGGER.debug(f"Manu data 15: {hex(self.manu_data[15])}")
        LOGGER.debug(f"Manu data 16: {hex(self.manu_data[16])}")

        if self.manu_data[15] == 0x61:
            rgb_color = (self.manu_data[18], self.manu_data[19], self.manu_data[20])
            self.hs_color = tuple(super().rgb_to_hsv(rgb_color))[0:2]
            self.brightness = (super().rgb_to_hsv(rgb_color)[2])
            self.color_mode = ColorMode.HS
            LOGGER.debug(f"From manu RGB colour: {rgb_color}")
            LOGGER.debug(f"From manu HS colour: {self.hs_color}")
            LOGGER.debug(f"From manu Brightness: {self.brightness}")
            if self.manu_data[16] != 0xf0:
                # We're not in a colour mode, so set the effect
                self.effect_speed = self.manu_data[17]
                if 0x01 <= self.manu_data[16] <= 0x0a:
                    self.effect = EFFECT_ID_TO_NAME_0x56[self.manu_data[16] << 8]
                else:
                    self.effect = EFFECT_OFF
        elif self.manu_data[15] == 0x62:
            # Music reactive mode. 
            self._color_mode = ColorMode.BRIGHTNESS
            effect = manu_data[16]
            scaled_effect = (effect + 0x32) << 8
            self.effect = EFFECT_ID_TO_NAME_0x56[scaled_effect]
        elif self.manu_data[15] == 0x25:
            # Effect mode
            effect = self.manu_data[16]
            self.effect = EFFECT_ID_TO_NAME_0x56[effect]
            self.effect_speed = self.manu_data[17]
            self.brightness   = int(self.manu_data[18] * 255 // 100)
            self.color_mode   = ColorMode.BRIGHTNESS
        
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
        #self.effect     = EFFECT_OFF # The effect is NOT actually off when setting a colour. Static effect 1 is close to effect off, but it's still an effect.
        rgb_color = self.hsv_to_rgb((hs_color[0], hs_color[1], self.brightness))
        LOGGER.debug(f"Setting RGB colour: {rgb_color}")
        background_col = [0,0,0] # Consider adding support for this in the future?  For now, set black
        rgb_packet = bytearray.fromhex("00 00 80 00 00 0d 0e 0b 41 02 ff 00 00 00 00 00 32 00 00 f0 64")
        rgb_packet[9]  = 0 # Mode "0" leaves the static current mode unchanged.  If we want this to switch the device back to an actual static RGB mode change this to 1.
        # Leaving it as zero allows people to use the colour picker to change the colour of the static mode in realtime.  I'm not sure what I prefer.  If people want actual
        # static colours they can change to "Static Mode 1" in the effects.  But perhaps that's not what they would expect to have to do?  It's quite hidden.
        # But they pay off is that they can change the colour of the other static modes as they drag the colour picker around, which is pretty neat. ?
        rgb_packet[10:13] = rgb_color
        rgb_packet[13:16] = background_col
        rgb_packet[16]    = self.effect_speed
        rgb_packet[20]    = sum(rgb_packet[8:19]) & 0xFF # Checksum
        LOGGER.debug(f"Set RGB. RGB {self.get_rgb_color()} Brightness {self.brightness}")
        return rgb_packet

    def set_effect(self, effect, brightness):
        # Returns the byte array to set the effect
        LOGGER.debug(f"Setting effect: {effect}")      
        if effect not in EFFECT_LIST_0x56:
            raise ValueError(f"Effect '{effect}' not in EFFECTS_LIST_0x53")
        self.effect = effect
        self.brightness = brightness
        #self.color_mode  = XXX ColorMode.BRIGHTNESS # Don't set this here, we might want to change the color of the effects?
        effect_id = EFFECT_MAP_0x56.get(effect)
        # We might need to force a colour if there isn't one set. The strip lights effects sometimes need a colour to work properly
        # Leaving this off for now, but in the old way we just forced red.
        
        if 0x0100 <= effect_id <= 0x1100: # See above for the meaning of these values.
            # We are dealing with "static" special effect numbers
            LOGGER.debug(f"'Static' effect: {effect_id}")
            effect_id = effect_id >> 8 # Shift back to the actual effect id
            LOGGER.debug(f"Special effect after shifting: {effect_id}")
            effect_packet = bytearray.fromhex("00 00 80 00 00 0d 0e 0b 41 02 ff 00 00 00 00 00 32 00 00 f0 64")
            effect_packet[9] = effect_id
            effect_packet[10:13] = self.get_rgb_color()
            effect_packet[16] = self.effect_speed
            effect_packet[20] = sum(effect_packet[8:19]) & 0xFF # checksum
            LOGGER.debug(f"static effect packet : {' '.join([f'{byte:02X}' for byte in effect_packet])}")
            return effect_packet
        
        if 0x2100 <= effect_id <= 0x4100: # Music mode.
            # We are dealing with a music mode effect
            effect_packet = bytearray.fromhex("00 22 80 00 00 0d 0e 0b 73 00 26 01 ff 00 00 ff 00 00 20 1a d2")
            LOGGER.debug(f"Music effect: {effect_id}")
            effect_id = (effect_id >> 8) - 0x32 # Shift back to the actual effect id
            LOGGER.debug(f"Music effect after shifting: {effect_id}")
            effect_packet[9]     = 1 # On
            effect_packet[11]    = effect_id
            effect_packet[12:15] = self.get_rgb_color()
            effect_packet[15:18] = self.get_rgb_color() # maybe background colour?
            effect_packet[18]    = self.effect_speed # Actually sensitivity, but would like to avoid another slider if possible
            effect_packet[19]    = self.get_brightness_percent()
            effect_packet[20]    = sum(effect_packet[8:19]) & 0xFF
            LOGGER.debug(f"music effect packet : {' '.join([f'{byte:02X}' for byte in effect_packet])}")
            return effect_packet
        
        effect_packet     = bytearray.fromhex("00 00 80 00 00 05 06 0b 42 01 32 64 d9")
        self.color_mode  = ColorMode.BRIGHTNESS # 2024.2 Allows setting color mode for changing effects brightness.  Effects above here support RGB, so only set here.
        effect_packet[9]  = effect_id
        effect_packet[10] = self.effect_speed
        effect_packet[11] = self.get_brightness_percent()
        effect_packet[12] = sum(effect_packet[8:11]) & 0xFF
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
        led_count   = options.get(const.CONF_LEDCOUNT)
        chip_type   = options.get(const.CONF_LEDTYPE)
        color_order = options.get(const.CONF_COLORORDER)
        self._delay = options.get(const.CONF_DELAY, 120)
        if led_count is None or chip_type is None or color_order is None:
            LOGGER.error("LED count, chip type or colour order is None and shouldn't be.  Not setting LED settings.")
            return
        else:
            self.chip_type         = getattr(const.LedTypes_StripLight, chip_type).value
            self.color_order       = getattr(const.ColorOrdering, color_order).value
            self.led_count         = led_count
        LOGGER.debug(f"Setting LED count: {self.led_count}, Chip type: {self.chip_type}, Colour order: {self.color_order}")
        led_settings_packet     = bytearray.fromhex("00 00 80 00 00 0b 0c 0b 62 00 64 00 03 01 00 64 03 f0 21")
        led_count_bytes         = bytearray(led_count.to_bytes(2, byteorder='big'))
        led_settings_packet[9:11] = led_count_bytes
        led_settings_packet[11:13] = [0, 1]  # We're only supporting a single segment
        led_settings_packet[13] = self.chip_type
        led_settings_packet[14] = self.color_order
        led_settings_packet[15] = self.led_count & 0xFF
        led_settings_packet[16] = 1 # 1 music mode segment, can support more in the app.
        led_settings_packet[17] = sum(led_settings_packet[9:18]) & 0xFF
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
                    rgb_color = (payload[6:9])
                    hsv_color = super().rgb_to_hsv(rgb_color)
                    self.hs_color = tuple(hsv_color[0:2])
                    self.brightness = int(hsv_color[2])
                    LOGGER.debug("Light is in colour mode")
                    LOGGER.debug(f"RGB colour: {rgb_color}")
                    LOGGER.debug(f"HS colour: {self.hs_color}")
                    LOGGER.debug(f"Brightness: {self.brightness}")
                    self.effect = EFFECT_OFF
                    self.color_mode = ColorMode.HS
                    self.color_temperature_kelvin = None
                # elif selected_effect == 0x01: # We don't really need this any more, deal with it below instead
                #     self.color_mode = ColorMode.HS
                #     # self.effect = EFFECT_OFF
                #     self.effect = EFFECT_ID_TO_NAME_0x56[selected_effect << 8] # Effect 1 is still an effect
                #     hs_color = self.rgb_to_hsv(payload[6:9])
                #     self.hs_color = hs_color[0:2]
                #     self.brightness = hs_color[2]
                elif 0x01 <= selected_effect <= 0x0a:
                    self.color_mode = ColorMode.HS
                    self.effect = EFFECT_ID_TO_NAME_0x56[selected_effect << 8]
                    self.effect_speed = payload[5]
                    hs_color = self.rgb_to_hsv(payload[6:9])
                    rgb_color = tuple(int(b) for b in payload[6:9])
                    LOGGER.debug(f"RGB Color: {rgb_color}, HS colour: {hs_color}, Brightness: {hs_color[2]}")
                    self.hs_color = hs_color[0:2]
                    self.brightness = hs_color[2]
            elif mode == 0x62:
                # Music reactive mode
                # TODO: Brightness?
                effect = payload[4]
                scaled_effect = (effect + 0x32) << 8
                try:
                    self.effect = EFFECT_ID_TO_NAME_0x56[scaled_effect]
                except KeyError:
                    self.effect = "Unknown"
            elif mode == 0x25:
                # Effects mode
                self.effect = EFFECT_ID_TO_NAME_0x56[selected_effect]
                self.effect_speed = payload[5]
                self.color_mode = ColorMode.BRIGHTNESS
                self.brightness = int(payload[6] * 255 // 100)
        
        elif payload[1] == 0x63:
            LOGGER.debug(f"LED settings response received")
            self.led_count = int.from_bytes(bytes([payload[2], payload[3]]), byteorder='big') * payload[5]
            # self.chip_type = const.LedTypes_StripLight.from_value(payload[6])
            self.chip_type = const.LedTypes_StripLight(payload[6]).name
            # self.color_order = const.ColorOrdering.from_value(payload[7])
            self.color_order = const.ColorOrdering(payload[7]).name


