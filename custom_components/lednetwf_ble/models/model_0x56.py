from .model_abstractions import DefaultModelAbstraction
from .. import const

import logging
LOGGER = logging.getLogger(__name__)

import colorsys
from homeassistant.components.light import ( # type: ignore
    ColorMode,
    EFFECT_OFF
)

SUPPORTED_MODELS = [0x56, 0x80]

# 0x56 Effect data
EFFECT_MAP_0x56 = {}
for e in range(1,100):
    EFFECT_MAP_0x56[f"Effect {e}"] = e
EFFECT_MAP_0x56["Cycle Modes"] = 255

# So called "static" effects.  Actually they are effects which can also be set to a specific colour.
# TODO:  Rename "effect 1" here to something which is more indicative of what it really is? 
for e in range(1,11):
    EFFECT_MAP_0x56[f"Static Effect {e}"] = e << 8 # Give the static effects much higher values which we can then shift back again in the effect function

# Sound reactive effects.  Numbered 1-15 internally, we will offset them by 50 to avoid clashes with the other effects
for e in range(1+0x32, 16+0x32):
    EFFECT_MAP_0x56[f"Sound Reactive {e-0x32}"] = e << 8

EFFECT_LIST_0x56 = sorted(EFFECT_MAP_0x56)
EFFECT_ID_TO_NAME_0x56 = {v: k for k, v in EFFECT_MAP_0x56.items()}

class Model0x56(DefaultModelAbstraction):
    # Strip light
    def __init__(self, manu_data):
        LOGGER.debug("Model 0x56 init")
        super().__init__(manu_data)
        self.supported_color_modes = {ColorMode.HS} # Actually, it supports RGB, but this will allow us to separate colours from brightness
        self.icon = "mdi:led-strip-variant"
        self.effect_list = EFFECT_LIST_0x56
        # self.fw_major = self.manu_data[0] # XX this should already exist

        if isinstance(self.manu_data, str):
            self.manu_data = [ord(c) for c in self.manu_data]
        # LOGGER.debug(f"Manu data: {[hex(x) for x in self.manu_data]}")
        # LOGGER.debug(f"Manu data 15: {hex(self.manu_data[15])}")
        # LOGGER.debug(f"Manu data 16: {hex(self.manu_data[16])}")

        if self.fw_major == 0x80:
            # TODO: Is this the same packet for 0x56 devices or only 0x80?  Find an 0x56 and test it
            self.INITIAL_PACKET             = bytearray.fromhex("00 01 80 00 00 0c 0d 0b 10 14 19 09 05 0d 2b 38 05 00 0f cf")
            self.GET_DEVICE_SETTINGS_PACKET = bytearray.fromhex("00 02 80 00 00 02 03 17 22 22")
            self.GET_LED_SETTINGS_PACKET    = bytearray.fromhex("00 05 80 00 00 05 06 0a 63 12 21 0f a5")

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
            effect = self.manu_data[16]
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
    
        @property
        def segments(self):
            """Get segments from parent instance."""
            if hasattr(self, '_parent_instance') and hasattr(self._parent_instance, '_segments'):
                return self._parent_instance._segments
            return None
        
        @segments.setter
        def segments(self, value):
            LOGGER.debug(f"Setting segments to {value}")
            """Set segments in parent instance."""
            if hasattr(self, '_parent_instance'):
                self._parent_instance._segments = value    

    def update_color_state(self, rgb_color):
        hsv_color = super().rgb_to_hsv(rgb_color)
        self.hs_color = tuple(hsv_color[0:2])
        self.brightness = int(hsv_color[2])
    
    def update_effect_state(self, mode, selected_effect, rgb_color=None, effect_speed=None, brightness=None):
        LOGGER.debug(f"Updating effect state. Mode: {mode}, Selected effect: {selected_effect}, RGB color: {rgb_color}, Effect speed: {effect_speed}, Brightness: {brightness/255}")
        if mode == 0x61:
            if selected_effect == 0xf0:
                self.update_color_state(rgb_color)
                LOGGER.debug("Light is in colour mode")
                LOGGER.debug(f"RGB colour: {rgb_color}")
                LOGGER.debug(f"HS colour: {self.hs_color}")
                LOGGER.debug(f"Brightness: {self.brightness}")
                self.effect = EFFECT_OFF
                self.color_mode = ColorMode.HS
                self.color_temperature_kelvin = None
            elif 0x01 <= selected_effect <= 0x0a:
                self.color_mode = ColorMode.HS
                self.effect = EFFECT_ID_TO_NAME_0x56[selected_effect << 8]
                self.effect_speed = effect_speed
                self.update_color_state(rgb_color)
        elif mode == 0x62:
            # Music reactive mode
            # TODO: Brightness?
            scaled_effect = (selected_effect + 0x32) << 8
            try:
                self.effect = EFFECT_ID_TO_NAME_0x56[scaled_effect]
            except KeyError:
                self.effect = "Unknown"
        elif mode == 0x25:
            # Effects mode
            self.effect = EFFECT_ID_TO_NAME_0x56[selected_effect]
            self.effect_speed = effect_speed
            self.color_mode = ColorMode.BRIGHTNESS
            #self.brightness = int(brightness * 255 // 100)
    
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
        segments    = options.get(const.CONF_SEGMENTS, 1)

        if led_count is None or chip_type is None or color_order is None:
            LOGGER.error("LED count, chip type or colour order is None and shouldn't be.  Not setting LED settings.")
            return
        else:
            self.chip_type         = chip_type
            self.color_order       = color_order
            self.led_count         = led_count
            self.segments          = segments
        LOGGER.debug(f"Setting LED values: Count {led_count}, Type {self.chip_type.value}, Order {self.color_order.value}, Segments {getattr(self, 'segments', 'Unknown')}")
        led_settings_packet     = bytearray.fromhex("00 00 80 00 00 0b 0c 0b 62 00 64 00 03 01 00 64 03 f0 21")
        led_count_bytes         = bytearray(led_count.to_bytes(2, byteorder='big'))
        led_settings_packet[9:11] = led_count_bytes
        # TODO: We need to support segments properly
        # I think we have to create a new config element to hold segments - OR...
        # Just don't support it.  Make the changes in the app and not in HA.  Seems reasonable to me :shrug:
        led_settings_packet[12] = self.segments
        led_settings_packet[13] = self.chip_type.value
        led_settings_packet[14] = self.color_order.value
        led_settings_packet[15] = self.led_count & 0xFF
        led_settings_packet[16] = self.segments
        led_settings_packet[17] = sum(led_settings_packet[9:18]) & 0xFF
        LOGGER.debug(f"LED settings packet: {' '.join([f'{byte:02X}' for byte in led_settings_packet])}")
        # REMEMBER: The calling function must also call stop() on the device to apply the settings
        return led_settings_packet
    
    def notification_handler(self, data):
        LOGGER.debug(f"Notification received. fw_major: 0x{self.fw_major:02x}, data: {' '.join([f'{byte:02X}' for byte in data])}")
        if self.fw_major == 0x80:
            # This device doesn't send the JSON like message.  It's all hex.
            # Example response to "LED settings" request:
                #  num  leds =--------------vv-------------vv
            # led colour order -------------||----------vv ||
            # yes, is led type -------------||-------vv || ||
            # segment ----------------------||----vv || || || vv
            # 0404 800000 0b 0c 15 00 63 00 0f 00 01 02 00 0f 01 85
            # 0409 800000 0b 0c 15 00 63 00 0f 00 01 01 00 0f 01 84
            # 040e 800000 0b 0c 15 00 63 00 0f 00 01 02 00 0f 01 85
            # 0413 800000 0b 0c 15 00 63 00 0f 00 01 03 00 0f 01 86
            # 0442 800000 0b 0c 15 00 63 00 13 00 03 01 00 13 03 90
            # 0001 020304 05 06 07 08 09 10 11 12 13 14 15 16 17 18 - index
            if list(data[5:8]) == [0x0b, 0x0c, 0x15]:
                # LED settings response
                LOGGER.debug("Get LED settings response received")
                self.led_count   = data[11]
                self.chip_type   = const.LedTypes_StripLight(data[14])
                self.color_order = const.ColorOrdering(data[15])
                if hasattr(self, '_parent_instance'):
                    self.segments = data[13]
                LOGGER.debug(f"LED count: {self.led_count}, Chip type: {self.chip_type}, Colour order: {self.color_order}, Segments: {self.segments}")
            # elif list(data[5:7]) == [0x1b, 0x1c]: # Not sure if this is a reliable way to identify this packet
            #     LOGGER.debug("Get device settings response received")
            elif list(data[5:7]) == [0x0e, 0x0f]:
                LOGGER.debug("Normal Status response received")
                self.is_on = True if data[10] == 0x23 else False
                mode_type    = data[11]
                effect_num   = data[12]
                effect_speed = data[13]
                rgb_color    = (data[14], data[15], data[16])
                self.update_effect_state(mode_type, effect_num, rgb_color, effect_speed, brightness=data[15]) # TODO: In "25" mode, brighgtness is byte 14
                LOGGER.debug(f"Status response. Is on: {self.is_on}, RGB colour: {rgb_color}, HS colour: {self.hs_color}, Brightness: {self.brightness}")
            else:
                LOGGER.debug("Unknown response received")
                return None
        else:
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
                LOGGER.debug(f"Payload[0]=0x81: Power: {power}, Mode: {mode}, Selected effect: {selected_effect}, LED count: {self.led_count}")

                if mode == 0x61:
                    if selected_effect == 0xf0:
                        # Light is in colour mode
                        rgb_color = (payload[6:9])
                        self.update_color_state(rgb_color)
                        LOGGER.debug("Light is in colour mode")
                        LOGGER.debug(f"RGB colour: {rgb_color}")
                        LOGGER.debug(f"HS colour: {self.hs_color}")
                        LOGGER.debug(f"Brightness: {self.brightness}")
                        self.effect = EFFECT_OFF
                        self.color_mode = ColorMode.HS
                        self.color_temperature_kelvin = None
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
                self.segments = payload[5]
                self.chip_type = const.LedTypes_StripLight(payload[6])
                self.color_order = const.ColorOrdering(payload[7])
                LOGGER.debug(f"From settings response data: LED count: {self.led_count}, Chip type: {self.chip_type}, Colour order: {self.color_order}, Segments: {self.segments}")
