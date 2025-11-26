from .model_abstractions import DefaultModelAbstraction
from .. import const

import logging
LOGGER = logging.getLogger(__name__)

import colorsys
from homeassistant.components.light import ( # type: ignore
    ColorMode,
    EFFECT_OFF
)

SUPPORTED_MODELS = [0x80]

# IOTBT 0x80 Effect data (starting with known effects, can be expanded)
EFFECT_MAP_IOTBT_0x80 = {}
for e in range(1,100):
    EFFECT_MAP_IOTBT_0x80[f"Effect {e}"] = e
EFFECT_MAP_IOTBT_0x80["Cycle Modes"] = 255

# Static effects with color support
EFFECT_MAP_IOTBT_0x80["Solid Color"] = 1 << 8  # Static Effect 1 - solid foreground color
for e in range(2,11):
    EFFECT_MAP_IOTBT_0x80[f"Static Effect {e}"] = e << 8

# Sound reactive effects (if supported)
for e in range(1+0x32, 16+0x32):
    EFFECT_MAP_IOTBT_0x80[f"Sound Reactive {e-0x32}"] = e << 8

# Effect list ordering
EFFECT_LIST_IOTBT_0x80 = ["Solid Color"]
EFFECT_LIST_IOTBT_0x80.extend([f"Static Effect {e}" for e in range(2, 11)])
EFFECT_LIST_IOTBT_0x80.extend([f"Effect {e}" for e in range(1, 100)])
EFFECT_LIST_IOTBT_0x80.extend([f"Sound Reactive {e}" for e in range(1, 16)])
EFFECT_LIST_IOTBT_0x80.append("Cycle Modes")

EFFECT_ID_TO_NAME_IOTBT_0x80 = {v: k for k, v in EFFECT_MAP_IOTBT_0x80.items()}

class ModelIotbt0x80(DefaultModelAbstraction):
    # IOTBT BLE LED controller
    def _parse_state_from_manu_data(self):
        """Parse device state from manufacturer data. Called during init and when advertisements arrive."""
        if len(self.manu_data) < 25:
            LOGGER.warning(f"IOTBT: Manufacturer data too short: {len(self.manu_data)} bytes")
            return
        
        # IOTBT uses mode 0x67 for static effects with color
        if self.manu_data[15] == 0x67:
            # Static effect mode with color
            self.color_mode = ColorMode.HS
            self.effect_speed = self.manu_data[17]
            rgb_color = (self.manu_data[18], self.manu_data[19], self.manu_data[20])
            self.hs_color = tuple(super().rgb_to_hsv(rgb_color))[0:2]
            self.brightness = (super().rgb_to_hsv(rgb_color)[2])
            
            if self.manu_data[16] == 0x01 or self.manu_data[16] == 0xf0:
                self.effect = EFFECT_OFF
            elif 0x02 <= self.manu_data[16] <= 0x0a:
                scaled_effect = self.manu_data[16] << 8
                if scaled_effect in EFFECT_ID_TO_NAME_IOTBT_0x80:
                    self.effect = EFFECT_ID_TO_NAME_IOTBT_0x80[scaled_effect]
                else:
                    LOGGER.warning(f"IOTBT: Unknown static effect: 0x{self.manu_data[16]:02X}, defaulting to EFFECT_OFF")
                    self.effect = EFFECT_OFF
            else:
                LOGGER.debug(f"IOTBT: Unhandled effect number: 0x{self.manu_data[16]:02X}")
                self.effect = EFFECT_OFF
                
            LOGGER.debug(f"IOTBT mode 0x67: RGB={rgb_color}, HS={self.hs_color}, brightness={self.brightness}, effect={self.effect}")
        
        elif self.manu_data[15] == 0x62:
            # Music reactive mode
            self._color_mode = ColorMode.BRIGHTNESS
            effect = self.manu_data[16]
            scaled_effect = (effect + 0x32) << 8
            if scaled_effect in EFFECT_ID_TO_NAME_IOTBT_0x80:
                self.effect = EFFECT_ID_TO_NAME_IOTBT_0x80[scaled_effect]
            else:
                LOGGER.warning(f"IOTBT: Unknown music reactive effect: 0x{effect:02X}")
                self.effect = EFFECT_OFF
                self._color_mode = ColorMode.HS
        
        elif self.manu_data[15] == 0x25:
            # Effect mode
            effect = self.manu_data[16]
            if effect in EFFECT_ID_TO_NAME_IOTBT_0x80:
                self.effect = EFFECT_ID_TO_NAME_IOTBT_0x80[effect]
            else:
                LOGGER.warning(f"IOTBT: Unknown effect: 0x{effect:02X}")
                self.effect = EFFECT_OFF
            self.effect_speed = self.manu_data[17]
            self.brightness   = int(self.manu_data[18] * 255 // 100)
            self.color_mode   = ColorMode.BRIGHTNESS
        
        else:
            LOGGER.debug(f"IOTBT: Unhandled mode: 0x{self.manu_data[15]:02X}")
        
        LOGGER.debug(f"IOTBT Effect:           {self.effect}")
        LOGGER.debug(f"IOTBT Effect speed:     {self.effect_speed}")
        LOGGER.debug(f"IOTBT Brightness:       {self.brightness}")
        LOGGER.debug(f"IOTBT LED count:        {self.led_count}")
        LOGGER.debug(f"IOTBT Firmware version: {self.fw_major}.{self.fw_minor}")
        LOGGER.debug(f"IOTBT Is on:            {self.is_on}")
        LOGGER.debug(f"IOTBT Colour mode:      {self.color_mode}")
        LOGGER.debug(f"IOTBT HS colour:        {self.hs_color}")

    def process_manu_data(self, manu_data):
        """Override to parse full state from manufacturer data on updates."""
        # Call parent to update basic fields first
        super().process_manu_data(manu_data)
        
        # IOTBT: Power state is in byte 1 instead of byte 14
        if len(self.manu_data) > 1:
            if self.manu_data[1] == 0x23:
                self.is_on = True
                LOGGER.debug("IOTBT: Updated is_on from manu data: True (byte 1 = 0x23)")
            elif self.manu_data[1] == 0x24:
                self.is_on = False
                LOGGER.debug("IOTBT: Updated is_on from manu data: False (byte 1 = 0x24)")
            else:
                LOGGER.warning(f"IOTBT: Unknown power state in manu data byte 1: 0x{self.manu_data[1]:02X}, keeping current state")
        
        # Parse additional state (colors, effects, etc.)
        self._parse_state_from_manu_data()

    def __init__(self, manu_data):
        LOGGER.debug("IOTBT Model 0x80 init")
        super().__init__(manu_data)
        self.supported_color_modes = {ColorMode.HS}
        self.icon = "mdi:led-strip-variant"
        self.effect_list = EFFECT_LIST_IOTBT_0x80

        if isinstance(self.manu_data, str):
            self.manu_data = [ord(c) for c in self.manu_data]

        # IOTBT-specific packets from captured traffic
        self.INITIAL_PACKET             = bytearray.fromhex("00 03 80 00 00 05 06 0a ea 81 8a 8b 59")
        self.GET_DEVICE_SETTINGS_PACKET = bytearray.fromhex("00 02 80 00 00 02 03 17 22 22")
        self.GET_LED_SETTINGS_PACKET    = bytearray.fromhex("00 05 80 00 00 05 06 0a 63 12 21 0f a5")
        self.GET_STATUS_PACKET          = bytearray.fromhex("00 14 80 00 00 05 06 0a 44 4a 4b 0f e8")

        # Parse initial state from manufacturer data
        self._parse_state_from_manu_data()
    
    @property
    def segments(self):
        """Get segments from parent instance."""
        if hasattr(self, '_parent_instance') and hasattr(self._parent_instance, '_segments'):
            return self._parent_instance._segments
        return None
    
    @segments.setter
    def segments(self, value):
        LOGGER.debug(f"IOTBT: Setting segments to {value}")
        """Set segments in parent instance."""
        if hasattr(self, '_parent_instance'):
            self._parent_instance._segments = value    
    
    def update_color_state(self, rgb_color):
        hsv_color = super().rgb_to_hsv(rgb_color)
        self.hs_color = tuple(hsv_color[0:2])
        self.brightness = int(hsv_color[2])
    
    def update_effect_state(self, mode, selected_effect, rgb_color=None, effect_speed=None, brightness=None):
        LOGGER.debug(f"IOTBT: Updating effect state. Mode: {mode}, Selected effect: {selected_effect}, RGB color: {rgb_color}, Effect speed: {effect_speed}, Brightness: {brightness/255 if brightness is not None else 'None'}")
        
        if mode == 0x66 or mode == 0x67:
            # IOTBT: Static effect mode with color (0x66 and 0x67 appear to be similar)
            self.color_mode = ColorMode.HS
            self.effect_speed = effect_speed
            if rgb_color:
                self.update_color_state(rgb_color)
            
            if selected_effect == 0x01 or selected_effect == 0xf0:
                self.effect = EFFECT_OFF
            elif 0x02 <= selected_effect <= 0x0a:
                scaled_effect = selected_effect << 8
                if scaled_effect in EFFECT_ID_TO_NAME_IOTBT_0x80:
                    self.effect = EFFECT_ID_TO_NAME_IOTBT_0x80[scaled_effect]
                else:
                    LOGGER.warning(f"IOTBT: Unknown static effect in notification: 0x{selected_effect:02X}")
                    self.effect = EFFECT_OFF
            else:
                self.effect = EFFECT_OFF
                
            LOGGER.debug(f"IOTBT mode 0x{mode:02X}: effect={self.effect}, speed={self.effect_speed}, HS={self.hs_color}, brightness={self.brightness}")
        
        elif mode == 0x62:
            # Music reactive mode
            scaled_effect = (selected_effect + 0x32) << 8
            try:
                self.effect = EFFECT_ID_TO_NAME_IOTBT_0x80[scaled_effect]
            except KeyError:
                self.effect = "Unknown"
        
        elif mode == 0x25:
            # Effects mode
            self.effect = EFFECT_ID_TO_NAME_IOTBT_0x80[selected_effect]
            self.effect_speed = effect_speed
            self.color_mode = ColorMode.BRIGHTNESS
        
        else:
            LOGGER.debug(f"IOTBT: Unhandled mode in update_effect_state: 0x{mode:02X}")
    
    # def set_bg_color(self, hs_color, brightness):
    #     # Returns the byte array to set the background RGB colour
    #     # TODO: Verify if IOTBT supports background colors the same way
    #     self.bg_hs_color = hs_color
    #     self.bg_brightness = brightness
    #     bg_rgb_color = self.hsv_to_rgb((hs_color[0], hs_color[1], self.bg_brightness))
    #     LOGGER.debug(f"IOTBT: Setting background RGB colour: {bg_rgb_color}")
        
    #     rgb_packet = bytearray.fromhex("00 00 80 00 00 0d 0e 0b 41 02 ff 00 00 00 00 00 32 00 00 f0 64")
    #     rgb_packet[9]  = 0
    #     rgb_packet[10:13] = self.get_rgb_color()
    #     rgb_packet[13:16] = bg_rgb_color
    #     rgb_packet[16]    = self.effect_speed
    #     rgb_packet[20]    = sum(rgb_packet[8:19]) & 0xFF
    #     LOGGER.debug(f"IOTBT: Set background RGB. RGB {bg_rgb_color} Brightness {self.bg_brightness}")
    #     return rgb_packet

    def set_color(self, hs_color, brightness):
        """
        iotbt static-colour command.
        - Byte 10 (cc): quantised hue mapped into 240-step ring (1..240).
                        cc==0 reserved for white.
        - Byte 11 (bb): brightness, low 5 bits used (0..31), gamma corrected.
        """
        hue, sat = hs_color
        if sat > 1.0:
            sat = sat / 100.0

        # --- hue quantisation (anchored so red maps to cc=0x01) ---
        N_HUES = 24  # try 36; drop to 24 if you still hit white zones

        def hue_to_cc_240(hue_deg):
            bin_idx = int(round((hue_deg % 360) / 360 * N_HUES)) % N_HUES
            step = 240 / N_HUES
            ring_pos = int(round(bin_idx * step)) % 240  # <-- no +0.5
            return ring_pos + 1  # 1..240

        if sat < 0.05:
            cc = 0x00
        else:
            cc = hue_to_cc_240(hue)
            if cc == 0x00:
                cc = 0x01

        # --- brightness gamma ---
        def brightness_to_level(b_0_255, gamma=2.2, max_level=31):
            x = max(0.0, min(1.0, b_0_255 / 255.0))
            x_gamma = x ** gamma
            return int(round(x_gamma * max_level))

        level = brightness_to_level(brightness)
        level = max(0, min(31, level))
        bb = 0xE0 | level   # mimic app (top bits don't matter)

        pkt = bytearray.fromhex("00 00 80 00 00 04 05 0a e2 0b 00 00")
        pkt[1] = (pkt[1] + 1) & 0xFF
        pkt[10] = cc
        pkt[11] = bb
        return pkt






    def set_effect(self, effect_name, brightness):
        # Based on 0x56 implementation but may need adjustments
        LOGGER.debug(f"IOTBT: Setting effect: {effect_name}, Brightness: {brightness}")
        
        if effect_name not in EFFECT_MAP_IOTBT_0x80:
            LOGGER.error(f"IOTBT: Effect {effect_name} not found in effect map")
            return None

        effect_id = EFFECT_MAP_IOTBT_0x80[effect_name]
        
        # Initialize background color if not set
        # if self.bg_hs_color is None or self.bg_brightness is None:
        #     self.bg_hs_color = self.hs_color
        #     self.bg_brightness = self.brightness
        #     LOGGER.debug(f"IOTBT: Initialized background color to match foreground: HS={self.bg_hs_color}, brightness={self.bg_brightness}")

        # Handle different effect types
        if effect_id == 255:  # Cycle Modes
            effect_packet = bytearray.fromhex("00 00 80 00 00 0d 0e 0b 41 00 00 01 02 03 04 05 06 07 08 c5")
            effect_packet[9]  = 0x26
            effect_packet[10] = effect_id
            effect_packet[11] = self.effect_speed
            effect_packet[12] = self.get_brightness_percent()
            effect_packet[13] = sum(effect_packet[8:12]) & 0xFF
            self.effect = effect_name
            self.brightness = brightness
            self.color_mode = ColorMode.BRIGHTNESS
            return effect_packet
        
        elif effect_id >= 256:  # Static or Sound Reactive effects
            effect_packet = bytearray.fromhex("00 00 80 00 00 0d 0e 0b 41 00 ff 00 00 00 00 00 32 00 00 f0 64")
            effect_id_real = effect_id >> 8
            
            if effect_id >= (0x32 << 8):  # Sound Reactive
                effect_packet[9] = 0x62
                effect_id_real = effect_id_real - 0x32
            else:  # Static effects
                effect_packet[9] = 0x61
            
            effect_packet[10] = effect_id_real
            effect_packet[10:13] = self.get_rgb_color()
            effect_packet[13:16] = self.get_bg_rgb_color()
            effect_packet[16] = self.effect_speed
            effect_packet[20] = sum(effect_packet[8:19]) & 0xFF
            self.effect = effect_name
            self.brightness = brightness
            self.color_mode = ColorMode.HS
            return effect_packet
        
        else:  # Regular effects
            effect_packet = bytearray.fromhex("00 00 80 00 00 09 0a 0b 3a 00 00 00 00 00")
            effect_packet[9]  = effect_id
            effect_packet[10] = self.effect_speed
            effect_packet[11] = self.get_brightness_percent()
            effect_packet[12] = sum(effect_packet[8:11]) & 0xFF
            self.effect = effect_name
            self.brightness = brightness
            self.color_mode = ColorMode.BRIGHTNESS
            return effect_packet

    def set_brightness(self, brightness):
        if brightness == self.brightness:
            LOGGER.debug(f"IOTBT: Brightness already set to {brightness}")
            return
        else:
            self.brightness = min(255, max(0, brightness))
        
        if self.color_mode == ColorMode.HS:
            return self.set_color(self.hs_color, brightness)
        elif self.color_mode == ColorMode.BRIGHTNESS:
            return self.set_effect(self.effect, brightness)
        else:
            LOGGER.error(f"IOTBT: Unknown colour mode: {self.color_mode}")
            return

    def set_power(self, power_on):
        """Set power on/off using IOTBT format.
        
        IOTBT power packets:
        - Byte 8: 0x0A (power mode)
        - Byte 9: 0x71 (constant)
        - Byte 10: 0x23 (on) or 0x24 (off)
        """
        LOGGER.debug(f"IOTBT: Setting power to {power_on}")
        power_packet = bytearray.fromhex("00 00 80 00 00 02 03 0a 71 23")
        power_packet[10] = 0x23 if power_on else 0x24
        self.is_on = power_on
        return power_packet

    def notification_handler(self, data):
        # Handle notifications from the device
        # Based on logs showing notification responses from IOTBT
        data_hex = ' '.join(f'{byte:02X}' for byte in data)
        LOGGER.debug(f"IOTBT: Notification received. fw_major: 0x{self.fw_major:02X}, data: {data_hex}")
        return
        if len(data) > 10:
            if data[0] == 0x04:  # Status response
                LOGGER.debug("IOTBT: Normal Status response received - Long type")
                
                # Parse power state from notification (byte 14)
                if data[14] == 0x23:
                    self.is_on = True
                elif data[14] == 0x24:
                    self.is_on = False
                else:
                    LOGGER.warning(f"IOTBT: Unknown power state byte 0x{data[14]:02X}, setting to None")
                    self.is_on = None
                
                mode_type    = data[15]
                effect_num   = data[16]
                effect_speed = data[17]
                rgb_color    = (data[18], data[19], data[20])
                
                self.update_effect_state(mode_type, effect_num, rgb_color, effect_speed, brightness=data[15])
                LOGGER.debug(f"IOTBT: Status response. Is on: {self.is_on}, RGB colour: {rgb_color}, HS colour: {self.hs_color}, Brightness: {self.brightness}, Mode: {mode_type}, Effect: {effect_num}, Speed: {effect_speed}")
            else:
                LOGGER.debug("IOTBT: Unknown response received")
                return None
        else:
            notification_data = data.decode("utf-8", errors="ignore")
            last_quote = notification_data.rfind('"')
            if last_quote > 0:
                name = notification_data[1:last_quote]
                LOGGER.debug(f"IOTBT: Device name from notification: {name}")
                return None
            else:
                LOGGER.debug("IOTBT: Unknown notification format")
                return None
