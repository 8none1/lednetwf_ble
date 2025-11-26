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

# IOTBT 0x80 Effect configuration
NUM_FX = 12
NUM_MUSIC_FX = 0x0D

def _build_iotbt_effects():
    """Build effect mappings for IOTBT 0x80 controller.

    Returns:
        tuple: (effect_map, effect_list, id_to_name_map)
            - effect_map: dict mapping effect name to ID
            - effect_list: ordered list of effect names for UI
            - id_to_name_map: dict mapping ID back to effect name
    """
    effect_map = {}
    effect_list = []

    # Regular effects (1-12): ID is the effect number
    for i in range(1, NUM_FX + 1):
        name = f"Effect {i}"
        effect_map[name] = i
        effect_list.append(name)

    # Music reactive effects: ID is effect_num << 8
    # Skip effects 5, 6, 9, 10, 11 as they don't exist on the device
    valid_music_effects = [1, 2, 3, 4, 7, 8, 12, 13]
    for i in valid_music_effects:
        name = f"Music {i}"
        effect_map[name] = i << 8
        effect_list.append(name)

    # Reverse mapping: ID -> name
    id_to_name = {effect_id: name for name, effect_id in effect_map.items()}
    return effect_map, effect_list, id_to_name

EFFECT_MAP_IOTBT_0x80, EFFECT_LIST_IOTBT_0x80, EFFECT_ID_TO_NAME_IOTBT_0x80 = _build_iotbt_effects()

class ModelIotbt0x80(DefaultModelAbstraction):
    # IOTBT BLE LED controller
    def _parse_state_from_manu_data(self):
        self.is_on = True if self.manu_data[1] == 0x23 else False

    def process_manu_data(self, manu_data):
        """Override to parse full state from manufacturer data on updates."""
        # Call parent to update basic fields first
        super().process_manu_data(manu_data)
        self._parse_state_from_manu_data()

    def __init__(self, manu_data):
        LOGGER.debug("IOTBT Model 0x80 init")
        self.is_on = False
        super().__init__(manu_data)
        self.supported_color_modes = {ColorMode.HS}
        self.icon = "mdi:led-strip-variant"
        self.effect_list = EFFECT_LIST_IOTBT_0x80
        self.brightness = 255
        self.hs_color = (0, 100) # Default to red.  We can't read this from the device
        self.effect = EFFECT_OFF
        self.color_mode = ColorMode.HS
        LOGGER.debug(f"IOTBT init: brightness={self.brightness}, hs_color={self.hs_color}, effect={self.effect}, color_mode={self.color_mode}")

        if isinstance(self.manu_data, str):
            self.manu_data = [ord(c) for c in self.manu_data]

        # IOTBT-specific packets from captured traffic
        self.INITIAL_PACKET             = bytearray.fromhex("00 03 80 00 00 05 06 0a ea 81 8a 8b 59")
        self.GET_DEVICE_SETTINGS_PACKET = bytearray.fromhex("00 02 80 00 00 02 03 17 22 22")
        self.GET_LED_SETTINGS_PACKET    = bytearray.fromhex("00 b3 80 00 00 03 04 0a e0 0e 01")
        self.GET_STATUS_PACKET          = bytearray.fromhex("00 14 80 00 00 05 06 0a 44 4a 4b 0f e8")

        # Parse initial state from manufacturer data
        self._parse_state_from_manu_data()
    
    # @property
    # def segments(self):
    #     """Get segments from parent instance."""
    #     if hasattr(self, '_parent_instance') and hasattr(self._parent_instance, '_segments'):
    #         return self._parent_instance._segments
    #     return None
    
    # @segments.setter
    # def segments(self, value):
    #     LOGGER.debug(f"IOTBT: Setting segments to {value}")
    #     """Set segments in parent instance."""
    #     if hasattr(self, '_parent_instance'):
    #         self._parent_instance._segments = value    
    
    def update_color_state(self, rgb_color):
        hsv_color = super().rgb_to_hsv(rgb_color)
        self.hs_color = tuple(hsv_color[0:2])
        self.brightness = int(hsv_color[2])
    
    def update_effect_state(self, mode, selected_effect, rgb_color=None, effect_speed=None, brightness=None):
        LOGGER.debug(f"IOTBT: Updating effect state. Mode: {mode}, Selected effect: {selected_effect}, RGB color: {rgb_color}, Effect speed: {effect_speed}, Brightness: {brightness/255 if brightness is not None else 'None'}")
        
        if mode == 0x66:
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
    
    def set_color(self, hs_color, brightness):
        """
        iotbt static-colour command.
        - Byte 10 (cc): quantised hue mapped into 240-step ring (1..240).
                        cc==0 reserved for white.
        - Byte 11 (bb): brightness, low 5 bits used (0..31), gamma corrected.
        """
        LOGGER.debug(f"IOTBT: set_color called with hs_color={hs_color}, brightness={brightness}")
        self.color_mode = ColorMode.HS
        self.effect     = EFFECT_OFF
        self.hs_color   = hs_color
        self.brightness = brightness

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
        LOGGER.debug(f"IOTBT: Setting effect: {effect_name}, Brightness: {brightness}")
        
        if effect_name not in EFFECT_MAP_IOTBT_0x80:
            LOGGER.error(f"IOTBT: Effect {effect_name} not found in effect map")
            return None

        effect_id = EFFECT_MAP_IOTBT_0x80[effect_name]

        # Handle different effect types
        if effect_id >= 256:  # Music mode
            brightness   = max(1, min(0x64, brightness))
            sensitivity  = max(1, min(0x64, self.effect_speed)) # Use effect_speed as sensitivity
            effect_id_real = effect_id >> 8
            effect_packet = bytearray.fromhex(
            "00 e2 80 00 00 36 37 0a e1 05 01 64 08 00 00 64 "
            "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 "
            "a1 00 00 00 06 a1 00 64 64 a1 96 64 64 a1 78 64 64 "
            "a1 5a 64 64 a1 3c 64 64 a1 1e 64 64"
            )
            effect_packet[11] = brightness
            effect_packet[12] = effect_id_real
            effect_packet[15] = sensitivity
            self.effect       = effect_name
            self.brightness   = brightness
            self.color_mode   = ColorMode.BRIGHTNESS
            LOGGER.debug(f"IOTBT: Music mode: effect id pre-shift: {effect_id}, effect id real: {effect_id_real}, speed: {self.effect_speed}")
        
        else:  # Regular effects
            self.brightness    = brightness
            self.effect        = effect_name
            LOGGER.debug(f"IOTBT: Setting regular effect ID: {effect_id}. Speed: {self.effect_speed}, Brightness: {self.get_brightness_percent()}%")
            effect_packet = bytearray.fromhex("00 00 80 00 00 06 07 0a e0 02 00 00 50 50")
            effect_packet[11]  = effect_id
            effect_packet[12]  = self.effect_speed
            effect_packet[13]  = self.get_brightness_percent()
            self.color_mode    = ColorMode.BRIGHTNESS
        
        return effect_packet

    def set_brightness(self, brightness):
        if brightness == self.brightness:
            LOGGER.debug(f"IOTBT: Brightness already set to {brightness}")
            return
        else:
            self.brightness = min(255, max(0, brightness))
        
        if self.color_mode == ColorMode.HS:
            LOGGER.debug(f"IOTBT: Setting brightness in HS mode to {brightness}")
            return self.set_color(self.hs_color, brightness)
        elif self.color_mode == ColorMode.BRIGHTNESS:
            LOGGER.debug(f"IOTBT: Setting effect brightness to {brightness}")
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
            # LOGGER.debug(f"Setting LED values: Count {led_count}, Type {self.chip_type.value}, Order {self.color_order.value}, Segments {getattr(self, 'segments', 'Unknown')}")
            # led_settings_packet       = bytearray.fromhex("00 00 80 00 00 0b 0c 0b 62 00 64 00 03 01 00 64 03 f0 21")
            # led_count_bytes           = bytearray(led_count.to_bytes(2, byteorder='big'))
            # led_settings_packet[9:11] = led_count_bytes
            # led_settings_packet[12]   = self.segments
            # led_settings_packet[13]   = self.chip_type.value
            # led_settings_packet[14]   = self.color_order.value
            # led_settings_packet[15]   = self.led_count & 0xFF
            # led_settings_packet[16]   = self.segments
            # led_settings_packet[17]   = sum(led_settings_packet[9:18]) & 0xFF
            # LOGGER.debug(f"LED settings packet: {' '.join([f'{byte:02X}' for byte in led_settings_packet])}")
            # REMEMBER: The calling function must also call stop() on the device to apply the settings
            return None

    def notification_handler(self, data):
        # This devices notifications are useless and convey only which mode the device is in
        # so we ignore them.  Some old code left here for reference.
        return None
        data_hex = ' '.join(f'{byte:02X}' for byte in data)
        LOGGER.debug(f"IOTBT: Notification received. fw_major: 0x{self.fw_major:02X}, data: {data_hex}")
        rgb_color = None
        effect_num = None
        effect_speed = None

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
                if mode_type == 0x62:
                    # Music mode
                    effect_num   = data[16] << 8
                    effect_speed = data[17]
                if mode_type == 0x66:
                    LOGGER.debug("IOTBT: Static colour mode detected in notification?")
                    return None
                if mode_type == 0x67:
                    effect_num   = data[16]
                    effect_speed = data[17]
                self.update_effect_state(mode_type, effect_num, rgb_color, effect_speed, brightness=data[15])
            else:
                LOGGER.debug("IOTBT: Unknown response received")
                return None
        else:
            LOGGER.debug("IOTBT: Unknown notification format")
            return None
