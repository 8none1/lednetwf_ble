"""Constants for LEDnetWF BLE v2 integration."""
import logging
from enum import IntEnum
from typing import Final

_LOGGER = logging.getLogger(__name__)

DOMAIN: Final = "lednetwf_ble"

# Configuration keys
CONF_MODEL: Final = "model"
CONF_PRODUCT_ID: Final = "product_id"
CONF_DISCONNECT_DELAY: Final = "disconnect_delay"
CONF_LED_COUNT: Final = "led_count"
CONF_SEGMENTS: Final = "segments"
CONF_LED_TYPE: Final = "led_type"
CONF_COLOR_ORDER: Final = "color_order"

# Default values
DEFAULT_DISCONNECT_DELAY: Final = 30  # seconds
DEFAULT_LED_COUNT: Final = 60
DEFAULT_SEGMENTS: Final = 1
DEFAULT_EFFECT_SPEED: Final = 50  # 0-100

# BLE UUIDs
WRITE_CHARACTERISTIC_UUID: Final = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_CHARACTERISTIC_UUID: Final = "0000ff02-0000-1000-8000-00805f9b34fb"

# Manufacturer ID ranges (from protocol docs)
MANUFACTURER_ID_PRIMARY: Final = range(23120, 23123)  # 0x5A50-0x5A52
MANUFACTURER_ID_EXTENDED: Final = (
    list(range(23123, 23134)) +  # 23123-23133
    list(range(23072, 23088)) +  # 0x5A20-0x5A2F
    list(range(23136, 23152)) +  # 0x5A60-0x5A6F
    list(range(23152, 23168)) +  # 0x5A70-0x5A7F
    list(range(23168, 23184))    # 0x5A80-0x5A8F
)

# Color temperature range (Kelvin)
MIN_KELVIN: Final = 2700
MAX_KELVIN: Final = 6500


class LedType(IntEnum):
    """LED chip types for addressable strips.

    Values must match device protocol (0x63 IC settings response byte 5).
    Confirmed via device testing and protocol documentation.
    """
    SM16703 = 0
    WS2812B = 1   # Confirmed: device returns 1 for WS2812B
    SM16716 = 2
    SK6812 = 3
    INK1003 = 4
    WS2811 = 5
    WS2801 = 6
    WS2815 = 7
    SK6812_RGBW = 8
    TM1914 = 9
    UCS1903 = 10
    UCS2904B = 11


class ColorOrder(IntEnum):
    """RGB color ordering for LED strips (addressable/Symphony devices)."""
    RGB = 0
    RBG = 1
    GRB = 2
    GBR = 3
    BRG = 4
    BGR = 5


class SimpleColorOrder(IntEnum):
    """RGB color ordering for SIMPLE devices (0x33, etc.).

    SIMPLE devices use different values than addressable strips.
    Source: protocol_docs/17_color_order_settings.md
    """
    RGB = 1
    GRB = 2
    BRG = 3


class EffectType(IntEnum):
    """Effect command type based on device.

    Based on DEVICE_IDENTIFICATION_GUIDE.md - use product_id for detection.
    """
    NONE = 0
    SIMPLE = 1              # 0x61 command, effects 37-56
    SYMPHONY = 2            # 0x38 command WITH checksum (5 bytes)
    ADDRESSABLE_0x53 = 3    # 0x38 command NO checksum (4 bytes), brightness in byte 3


class ValueScale(IntEnum):
    """Value scale for brightness/speed in advertisement data.

    Determines how to convert raw advertisement values to internal 0-255/0-100 format.
    """
    PERCENT = 0         # 0-100 percentage scale (default for most devices)
    RAW_255 = 1         # 0-255 raw scale (some newer devices)
    INVERTED_31 = 2     # 0x01-0x1F inverted scale (0x54, 0x55, 0x62 devices)


# Simple effects (0x61 command) - IDs 37-56 for non-Symphony RGB devices
SIMPLE_EFFECTS: Final = {
    37: "Seven color cross fade",
    38: "Red gradual change",
    39: "Green gradual change",
    40: "Blue gradual change",
    41: "Yellow gradual change",
    42: "Cyan gradual change",
    43: "Purple gradual change",
    44: "White gradual change",
    45: "Red/green cross fade",
    46: "Red/blue cross fade",
    47: "Green/blue cross fade",
    48: "Seven color strobe flash",
    49: "Red strobe flash",
    50: "Green strobe flash",
    51: "Blue strobe flash",
    52: "Yellow strobe flash",
    53: "Cyan strobe flash",
    54: "Purple strobe flash",
    55: "White strobe flash",
    56: "Seven color jumping change",
}

# Static effects for devices with background color support (0x56, 0x80)
# These effects support both foreground and background colors using the 0x41 command
# Effect ID 1 is "Solid Color" which is just foreground, no background
# Effects 2-10 are "Static Effects" with foreground + background
STATIC_EFFECTS_WITH_BG: Final = {
    2: "Static Effect 2",
    3: "Static Effect 3",
    4: "Static Effect 4",
    5: "Static Effect 5",
    6: "Static Effect 6",
    7: "Static Effect 7",
    8: "Static Effect 8",
    9: "Static Effect 9",
    10: "Static Effect 10",
}

# Regular effects for 0x56/0x80 devices (0x42 command) - IDs 1-99
STRIP_EFFECTS: Final = {
    i: f"Effect {i}" for i in range(1, 100)
}

# Sound reactive effects for 0x56/0x80 devices (0x73 command)
SOUND_REACTIVE_EFFECTS: Final = {
    i: f"Sound Reactive {i}" for i in range(1, 16)
}

# Symphony Function Mode effects (0x42 command) - IDs 1-100
# Source: FunctionModeFragment.java - effects are numbered only, no names in the app
# Format: 0x42 [effect_id] [speed] [brightness] [checksum]
# Note: 0xA6 devices have 227 effects, 0xA9 have 131 effects, others have 100
SYMPHONY_EFFECTS: Final = {
    i: f"Effect {i}" for i in range(1, 101)
}

# Symphony Settled Mode effects (0x41 command) - IDs 1-10
# Source: SettledModeFragment.java, protocol_docs/15_static_effects_with_bg_color.md
# Effect 1 = Solid Color (FG only, no background)
# Effects 2-10 = Static effects with FG+BG color support
# Format: [0x41, mode, FG_R, FG_G, FG_B, BG_R, BG_G, BG_B, speed, direction, 0x00, 0xF0, checksum]
SYMPHONY_SETTLED_EFFECTS: Final = {
    1: "Solid Color",
    2: "Static Effect 2",
    3: "Static Effect 3",
    4: "Static Effect 4",
    5: "Static Effect 5",
    6: "Static Effect 6",
    7: "Static Effect 7",
    8: "Static Effect 8",
    9: "Static Effect 9",
    10: "Static Effect 10",
}

# Symphony Settled effects that support background color (2-10, not 1)
SYMPHONY_SETTLED_BG_EFFECTS: Final = frozenset(range(2, 11))  # 2-10 inclusive

# Symphony Scene effects (0x38 command) - IDs 1-44
# Source: protocol_docs/07_effect_names.md (extracted from Android APK strings.xml)
# These are named effects available in "Scene Mode" - NOT used by most Symphony devices
# UI Type determines which color pickers are available
SYMPHONY_SCENE_EFFECTS: Final = {
    # StartColor_EndColor effects (1-4)
    1: "Change gradually",
    2: "Bright up and Fade gradually",
    3: "Change quickly",
    4: "Strobe-flash",
    # ForegroundColor_BackgroundColor effects (5-18)
    5: "Running, 1point from start to end",
    6: "Running, 1point from end to start",
    7: "Running, 1point from middle to both ends",
    8: "Running, 1point from both ends to middle",
    9: "Overlay, from start to end",
    10: "Overlay, from end to start",
    11: "Overlay, from middle to both ends",
    12: "Overlay, from both ends to middle",
    13: "Fading and running, 1point from start to end",
    14: "Fading and running, 1point from end to start",
    15: "Olivary Flowing, from start to end",
    16: "Olivary Flowing, from end to start",
    17: "Running, 1point w/background from start to end",
    18: "Running, 1point w/background from end to start",
    # FirstColor_SecondColor effects (19-26)
    19: "2 colors run, multi points w/black background from start to end",
    20: "2 colors run, multi points w/black background from end to start",
    21: "2 colors run alternately, fading from start to end",
    22: "2 colors run alternately, fading from end to start",
    23: "2 colors run alternately, multi points from start to end",
    24: "2 colors run alternately, multi points from end to start",
    25: "Fading out Flows, from start to end",
    26: "Fading out Flows, from end to start",
    # Only_BackgroundColor effects (27-28)
    27: "7 colors run alternately, 1 point with multi points background, from start to end",
    28: "7 colors run alternately, 1 point with multi points background, from end to start",
    # NoColor effects (29-44) - use preset rainbow colors
    29: "7 colors run alternately, 1 point from start to end",
    30: "7 colors run alternately, 1 point from end to start",
    31: "7 colors run alternately, multi points from start to end",
    32: "7 colors run alternately, multi points from end to start",
    33: "7 colors overlay, multi points from start to end",
    34: "7 colors overlay, multi points from end to start",
    35: "7 colors overlay, multi points from middle to both ends",
    36: "7 colors overlay, multi points from both ends to middle",
    37: "7 colors flow gradually, from start to end",
    38: "7 colors flow gradually, from end to start",
    39: "Fading out run, 7 colors from start to end",
    40: "Fading out run, 7 colors from end to start",
    41: "Runs in olivary, 7 colors from start to end",
    42: "Runs in olivary, 7 colors from end to start",
    43: "Fading out run, 7 colors start with white from start to end",
    44: "Fading out run, 7 colors start with white from end to start",
}

# Symphony effects that support FG+BG colors via 0x41 command
# Source: protocol_docs/14_symphony_background_colors.md
# UIType_ForegroundColor_BackgroundColor: effects 5-18
SYMPHONY_BG_COLOR_EFFECTS: Final = frozenset(range(5, 19))  # 5-18 inclusive

# Addressable 0x53 effects (Ring Lights) - 0x38 command, NO checksum
# Source: model_0x53.py EFFECTS_LIST_0x53
ADDRESSABLE_0x53_EFFECTS: Final = {
    1: "Gold Ring",
    2: "Red Magenta Fade",
    3: "Yellow Magenta Fade",
    4: "Green Yellow Fade",
    5: "Green Blue Spin",
    6: "Blue Spin",
    7: "Purple Pink Spin",
    8: "Color Fade",
    9: "Red Blue Flash",
    10: "CMRGB Spin",
    11: "RGBYMC Follow",
    12: "CMYRGB Spin",
    13: "RGB Chase",
    14: "RGB Tri Reverse Spin",
    15: "Red Fade",
    16: "Blue Yellow Quad Static",
    17: "Red Green Quad Static",
    18: "Cyan Magenta Quad Static",
    19: "Red Green Reverse Chase",
    20: "Blue Yellow Reverse Chase",
    21: "Cyan Magenta Reverse Chase",
    22: "Yellow RGB Reverse Spin",
    23: "Cyan RGB Reverse Spin",
    24: "Magenta RGB Reverse Spin",
    25: "RGB Reverse Spin",
    26: "RGBY Reverse Spin",
    27: "Magenta RGBY Reverse Spin",
    28: "Cyan RGBYMC Reverse Spin",
    29: "White RGBYMC Reverse Spin",
    30: "Red Green Reverse Chase 2",
    31: "Blue Yellow Reverse Chase 2",
    32: "Cyan Pink Reverse Chase",
    33: "White Strobe",
    34: "White Strobe 2",
    35: "Warm White Strobe",
    36: "Smooth Color Fade",
    37: "White Static",
    38: "Pinks Fade",
    39: "Cyans Fade",
    40: "Cyan Magenta Slow Fade",
    41: "Green Yellow Fade 2",
    42: "RGBCMY Slow Fade",
    43: "Whites Fade",
    44: "Pink Purple Fade",
    45: "Cyan Magenta Fade",
    46: "Cyan Blue Fade",
    47: "Yellow Cyan Fade",
    48: "Red Yellow Fade",
    49: "RGBCMY Strobe",
    50: "Warm Cool White Strobe",
    51: "Magenta Strobe",
    52: "Cyan Strobe",
    53: "Yellow Strobe",
    54: "Magenta Cyan Strobe",
    55: "Cyan Yellow Strobe",
    56: "Cool White Strobe Random",
    57: "Warm White Strobe Random",
    58: "Light Green Strobe Random",
    59: "Magenta Strobe Random",
    60: "Cyan Strobe Random",
    61: "Oranges Ring",
    62: "Blue Ring",
    63: "RMBCGY Loop",
    64: "Cyan Magenta Follow",
    65: "Yellow Green Follow",
    66: "Pink Blue Follow",
    67: "BGP Pastels Loop",
    68: "CYM Follow",
    69: "Pink Purple Demi Spinner",
    70: "Blue Pink Spinner",
    71: "Green Spinner",
    72: "Blue Yellow Tri Spinner",
    73: "Red Yellow Tri Spinner",
    74: "Pink Green Tri Spinner",
    75: "Red Blue Demi Spinner",
    76: "Yellow Green Demi Spinner",
    77: "RGB Tri Spinner",
    78: "Red Magenta Demi Spinner",
    79: "Cyan Magenta Demi Spinner",
    80: "RCBM Quad Spinner",
    81: "RGBCMY Spinner",
    82: "RGB Spinner",
    83: "CMB Spinner",
    84: "Red Blue Demi Spinner 2",
    85: "Cyan Magenta Demi Spinner 2",
    86: "Yellow Orange Demi Spinner",
    87: "Red Blue Striped Spinner",
    88: "Green Yellow Striped Spinner",
    89: "Red Pink Yellow Striped Spinner",
    90: "Cyan Blue Magenta Striped Spinner",
    91: "Pastels Striped Spinner",
    92: "Rainbow Spin",
    93: "Red Pink Blue Spinner",
    94: "Cyan Magenta Spinner",
    95: "Green Cyan Spinner",
    96: "Yellow Red Spinner",
    97: "Rainbow Strobe",
    98: "Magenta Strobe 2",
    99: "Yellow Orange Demi Strobe",
    100: "Yellow Cyan Demi Flash",
    101: "White Lightening Strobe",
    102: "Purple Lightening Strobe",
    103: "Magenta Lightening Strobe",
    104: "Yellow Lightening Strobe",
    105: "Blue With Sparkles",
    106: "Red With Sparkles",
    107: "Blue With Sparkles 2",
    108: "Yellow Dissolve",
    109: "Magenta Dissolve",
    110: "Cyan Dissolve",
    111: "Red Green Dissolve",
    112: "RGB Dissolve",
    113: "RGBCYM Dissolve",
    # 114-115 are "Nothing" effects
    255: "Cycle Through All Modes",  # Special effect ID 0xFF
}

# Product IDs with special speed encoding (inverted 0x01-0x1F scale)
# Source: model_0x54.py, protocol_docs/07a_effect_commands_by_device.md
# These devices use inverted speed where 0x01=fastest, 0x1F=slowest
# Note: Symphony devices (0xA1-0xA9) do NOT use inverted speed - they use 1=slow, 31=fast
INVERTED_SPEED_PRODUCT_IDS: Final = {
    0x54, 0x55, 0x62, 0x5B,  # Strip controllers
}

# Product ID to capabilities mapping
# Source: protocol_docs/04_device_identification_capabilities.md
# Source: protocol_docs/09_effects_addressable_led_support.md
# Note: brightness_scale and speed_scale default to PERCENT if not specified
PRODUCT_CAPABILITIES: Final = {
    # Controllers with RGB + White (RGBWBoth / RGBCWBoth)
    4:   {"name": "Ctrl_RGBW_UFO", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    6:   {"name": "Ctrl_Mini_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    7:   {"name": "Ctrl_Mini_RGBCW", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    32:  {"name": "Ctrl_Mini_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    37:  {"name": "Ctrl_RGBCW_Both", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    38:  {"name": "Ctrl_Mini_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    39:  {"name": "Ctrl_Mini_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    72:  {"name": "Ctrl_Mini_RGBW_Mic", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE, "has_builtin_mic": True, "mic_cmd_format": "simple"},

    # Controllers with RGB only
    8:   {"name": "Ctrl_Mini_RGB_Mic", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_builtin_mic": True, "mic_cmd_format": "simple"},
    16:  {"name": "ChristmasLight", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SIMPLE},
    51:  {"name": "Ctrl_Mini_RGB", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SIMPLE, "has_color_order": True},

    # CCT only - no RGB
    9:   {"name": "Ctrl_Ceiling_CCT", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},
    22:  {"name": "Magnetic_CCT", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},
    28:  {"name": "TableLamp_CCT", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},
    82:  {"name": "Bulb_CCT", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},
    98:  {"name": "Ctrl_CCT", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},

    # Dimmer only
    23:  {"name": "Magnetic_Dim", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "effect_type": EffectType.NONE},
    33:  {"name": "Bulb_Dim", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "effect_type": EffectType.NONE},
    65:  {"name": "Ctrl_Dim", "has_rgb": False, "has_ww": False, "has_cw": False, "has_dim": True, "effect_type": EffectType.NONE},

    # Bulbs with RGBCW
    14:  {"name": "FloorLamp_RGBCW", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    30:  {"name": "CeilingLight_RGBCW", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    53:  {"name": "Bulb_RGBCW_R120", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    59:  {"name": "Bulb_RGBCW", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    68:  {"name": "Bulb_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    84:  {"name": "Downlight_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},

    # Switches and Sockets - not supported as lights
    11:  {"name": "Switch_1c", "is_switch": True, "effect_type": EffectType.NONE},
    147: {"name": "Switch_1C", "is_switch": True, "effect_type": EffectType.NONE},
    148: {"name": "Switch_1c_Watt", "is_switch": True, "effect_type": EffectType.NONE},
    149: {"name": "Switch_2c", "is_switch": True, "effect_type": EffectType.NONE},
    150: {"name": "Switch_4c", "is_switch": True, "effect_type": EffectType.NONE},
    151: {"name": "Socket_1c", "is_switch": True, "effect_type": EffectType.NONE},

    # Special devices
    26:  {"name": "ChristmasLight", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SIMPLE},
    27:  {"name": "SprayLight", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SIMPLE},
    29:  {"name": "FillLight", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.ADDRESSABLE_0x53, "has_segments": True},
    41:  {"name": "MirrorLight", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    209: {"name": "Digital_Light", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True},

    # Ring/Strip lights with background color support
    # Note: product_id 0x53 (83) uses ADDRESSABLE_0x53 effect format (4 bytes, NO checksum)
    0:   {"name": "RingLight_Generic", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.ADDRESSABLE_0x53, "has_segments": True},
    83:  {"name": "RingLight_0x53", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.ADDRESSABLE_0x53, "has_segments": True},  # 0x53
    86:  {"name": "RingLight_0x56", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_bg_color": True},  # 0x56
    128: {"name": "RingLight_0x80", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_bg_color": True},  # 0x80

    # Ceiling lights
    225: {"name": "Ctrl_Ceiling", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},
    226: {"name": "Ctrl_Ceiling_Assist", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},

    # Symphony controllers - addressable RGB with effects
    # Source: protocol_docs/14_symphony_background_colors.md - effects 5-18 support FG+BG colors via 0x41 command
    # Note: has_builtin_mic based on Java source - devices using MusicModeFragment have mic, MusicModeFragmentWithoutMic don't
    161: {"name": "Ctrl_RGB_Symphony", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True},
    162: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True, "has_builtin_mic": True, "mic_cmd_format": "symphony"},
    163: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True, "has_builtin_mic": True, "mic_cmd_format": "symphony"},
    164: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True},  # Uses phone mic, no built-in
    166: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True, "has_builtin_mic": True, "mic_cmd_format": "symphony"},
    167: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True, "has_builtin_mic": True, "mic_cmd_format": "symphony"},
    169: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True, "has_builtin_mic": True, "mic_cmd_format": "symphony"},

    # Symphony Line strips
    170: {"name": "Symphony_Line", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True},  # 0xAA
    171: {"name": "Symphony_Line", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True},  # 0xAB

    # LED Curtain Lights - matrix displays using Symphony protocol
    # Source: protocol_docs/13_led_curtain_lights.md
    172: {"name": "Symphony_Curtain", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True},  # 0xAC
    173: {"name": "Symphony_Curtain", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True, "has_bg_color": True},  # 0xAD
}


def get_device_capabilities(product_id: int | None) -> dict:
    """Get device capabilities from product ID.

    For known devices, returns documented capabilities.
    For unknown devices, returns a stub indicating probing is needed.

    Source: protocol_docs/04_device_identification_capabilities.md
    """
    if product_id is None:
        caps = {
            "name": "Unknown",
            "has_rgb": None,
            "has_ww": None,
            "has_cw": None,
            "effect_type": EffectType.NONE,
            "needs_probing": True,
        }
        _LOGGER.debug(
            "Device capabilities for product_id=None: %s (probing required)",
            caps
        )
        return caps

    if product_id in PRODUCT_CAPABILITIES:
        caps = PRODUCT_CAPABILITIES[product_id].copy()
        caps["needs_probing"] = caps.get("is_stub", False)
        _LOGGER.debug(
            "Device capabilities for product_id=0x%02X (%d): name=%s, "
            "has_rgb=%s, has_ww=%s, has_cw=%s, effect_type=%s, needs_probing=%s",
            product_id, product_id,
            caps.get("name"),
            caps.get("has_rgb"),
            caps.get("has_ww"),
            caps.get("has_cw"),
            caps.get("effect_type"),
            caps.get("needs_probing"),
        )
        return caps

    # Unknown product ID - needs capability probing
    # Per protocol docs: "For devices with unknown Product ID (0x00) or stub classes, probe capabilities"
    caps = {
        "name": f"Unknown_0x{product_id:02X}",
        "has_rgb": None,
        "has_ww": None,
        "has_cw": None,
        "effect_type": EffectType.SYMPHONY,  # Assume modern device with Symphony support
        "needs_probing": True,
    }
    _LOGGER.debug(
        "Device capabilities for UNKNOWN product_id=0x%02X (%d): %s (probing required)",
        product_id, product_id, caps
    )
    return caps


def is_supported_device(product_id: int | None) -> bool:
    """Check if a device might be supported (not a known switch/socket).

    Unknown devices return True since they should be probed for capabilities.
    Only explicitly-known switches/sockets return False.

    Source: protocol_docs/04_device_identification_capabilities.md
    """
    if product_id is None:
        # Unknown product ID - allow and probe
        return True

    caps = PRODUCT_CAPABILITIES.get(product_id)
    if caps is None:
        # Unknown product ID - allow and probe
        return True

    # Only exclude known switches/sockets
    if caps.get("is_switch"):
        return False

    return True


def needs_capability_probing(product_id: int | None) -> bool:
    """Check if device needs capability probing.

    Returns True for unknown product IDs or stub device classes.

    Source: protocol_docs/04_device_identification_capabilities.md
    """
    if product_id is None:
        return True

    if product_id not in PRODUCT_CAPABILITIES:
        return True

    return PRODUCT_CAPABILITIES[product_id].get("is_stub", False)


def get_effect_list(
    effect_type: EffectType,
    has_bg_color: bool = False,
    has_ic_config: bool = False,
    has_builtin_mic: bool = False,
) -> list[str]:
    """Get list of effect names for the given effect type.

    Args:
        effect_type: The effect command type for the device
        has_bg_color: If True, include static effects that support background color
        has_ic_config: If True, device is a Symphony controller (0xA1-0xAD), not 0x56/0x80
        has_builtin_mic: If True, include "Sound Reactive" option for devices with built-in mic

    Returns:
        List of effect names
    """
    effects = []

    if effect_type == EffectType.SIMPLE:
        effects = list(SIMPLE_EFFECTS.values())
    elif effect_type == EffectType.SYMPHONY:
        if has_ic_config:
            # True Symphony devices (0xA1-0xAD):
            # - Settled Mode effects (1-10) via 0x41 command with FG+BG colors
            # - Function Mode effects (1-100) via 0x42 command
            effects = list(SYMPHONY_SETTLED_EFFECTS.values())
            effects.extend(list(SYMPHONY_EFFECTS.values()))
        elif has_bg_color:
            # 0x56/0x80 devices: Static effects + Regular effects + Sound reactive
            effects = list(STATIC_EFFECTS_WITH_BG.values())
            effects.extend(list(STRIP_EFFECTS.values()))
            effects.extend(list(SOUND_REACTIVE_EFFECTS.values()))
            effects.append("Cycle Modes")
        else:
            # Fallback for unknown Symphony-type devices: numbered effects
            effects = list(SYMPHONY_EFFECTS.values())
    elif effect_type == EffectType.ADDRESSABLE_0x53:
        # 0x53 Ring Light effects (113 effects + Cycle All)
        effects = list(ADDRESSABLE_0x53_EFFECTS.values())

    # Add sound reactive option for devices with built-in microphone
    if has_builtin_mic:
        effects.append("Sound Reactive")

    return effects


# Special marker for sound reactive mode (not a real effect ID)
SOUND_REACTIVE_MARKER: Final = 0xFFFF


def get_effect_id(
    effect_name: str,
    effect_type: EffectType,
    has_bg_color: bool = False,
    has_ic_config: bool = False,
    has_builtin_mic: bool = False,
) -> int | None:
    """Get effect ID from name.

    Args:
        effect_name: Effect name to look up
        effect_type: The effect command type for the device
        has_bg_color: If True, check static effects that support background color
        has_ic_config: If True, device is a Symphony controller (0xA1-0xAD), not 0x56/0x80
        has_builtin_mic: If True, recognize "Sound Reactive" effect

    Returns:
        Effect ID or None if not found.
        Returns SOUND_REACTIVE_MARKER (0xFFFF) for "Sound Reactive" effect.
    """
    # Check for sound reactive mode first (special handling, not a real effect ID)
    if effect_name == "Sound Reactive" and has_builtin_mic:
        return SOUND_REACTIVE_MARKER
    if effect_type == EffectType.SIMPLE:
        for eid, name in SIMPLE_EFFECTS.items():
            if name == effect_name:
                return eid
    elif effect_type == EffectType.SYMPHONY:
        if has_ic_config:
            # True Symphony devices (0xA1-0xAD):
            # - Settled Mode effects (1-10) via 0x41 command with FG+BG colors
            # - Function Mode effects (1-100) via 0x42 command
            # Check Settled Mode effects first (encode with << 8 to distinguish from Function Mode)
            for eid, name in SYMPHONY_SETTLED_EFFECTS.items():
                if name == effect_name:
                    # Encode Settled effects with << 8 to distinguish from Function Mode
                    return eid << 8
            # Then check Function Mode effects (1-100)
            for eid, name in SYMPHONY_EFFECTS.items():
                if name == effect_name:
                    return eid
        elif has_bg_color:
            # 0x56/0x80 devices: Check static effects, strip effects, sound reactive
            for eid, name in STATIC_EFFECTS_WITH_BG.items():
                if name == effect_name:
                    # Static effects use ID << 8 to distinguish from regular effects
                    return eid << 8
            for eid, name in STRIP_EFFECTS.items():
                if name == effect_name:
                    return eid
            for eid, name in SOUND_REACTIVE_EFFECTS.items():
                if name == effect_name:
                    # Sound reactive effects use (eid + 0x32) << 8
                    return (eid + 0x32) << 8
            if effect_name == "Cycle Modes":
                return 255
        else:
            # Fallback for unknown Symphony-type devices: numbered effects
            for eid, name in SYMPHONY_EFFECTS.items():
                if name == effect_name:
                    return eid
    elif effect_type == EffectType.ADDRESSABLE_0x53:
        for eid, name in ADDRESSABLE_0x53_EFFECTS.items():
            if name == effect_name:
                return eid
    return None


def get_brightness_scale(product_id: int | None) -> ValueScale:
    """Get the brightness value scale for a product ID.

    Most devices report brightness as 0-100 percentage in manufacturer data.
    Some newer devices may report 0-255 directly.

    Args:
        product_id: Device product ID

    Returns:
        ValueScale indicating how to interpret brightness values
    """
    # Currently all known devices use percentage scale for brightness
    # The > 100 values we saw were likely bugs or malformed data
    # Per protocol docs and old integration, manufacturer data should be 0-100
    return ValueScale.PERCENT


def get_speed_scale(product_id: int | None) -> ValueScale:
    """Get the effect speed value scale for a product ID.

    Most devices report speed as 0-100 percentage.
    0x54, 0x55, 0x62, 0x5B devices use inverted 0x01-0x1F scale.

    Args:
        product_id: Device product ID

    Returns:
        ValueScale indicating how to interpret speed values
    """
    if product_id is not None and product_id in INVERTED_SPEED_PRODUCT_IDS:
        return ValueScale.INVERTED_31
    return ValueScale.PERCENT


def convert_brightness_from_adv(raw_value: int, product_id: int | None) -> int:
    """Convert advertisement brightness value to Home Assistant 0-255 scale.

    Args:
        raw_value: Raw brightness value from advertisement data
        product_id: Device product ID

    Returns:
        Brightness value in 0-255 range
    """
    scale = get_brightness_scale(product_id)

    if scale == ValueScale.RAW_255:
        # Value is already 0-255
        return max(0, min(255, raw_value))
    elif scale == ValueScale.PERCENT:
        # Value is 0-100 percentage, convert to 0-255
        # Handle potential overflow (device reporting 0-255 when we expect 0-100)
        if raw_value > 100:
            _LOGGER.debug(
                "Brightness %d exceeds expected 0-100 range for product_id=0x%02X, "
                "treating as raw 0-255 value",
                raw_value, product_id or 0
            )
            return max(0, min(255, raw_value))
        return int(raw_value * 255 / 100)

    return max(0, min(255, raw_value))


def convert_speed_from_adv(raw_value: int, product_id: int | None) -> int:
    """Convert advertisement speed value to 0-100 percentage scale.

    Args:
        raw_value: Raw speed value from advertisement data
        product_id: Device product ID

    Returns:
        Speed value in 0-100 range
    """
    scale = get_speed_scale(product_id)

    if scale == ValueScale.INVERTED_31:
        # 0x54/0x55/0x62/0x5B: inverted 0x01-0x1F scale
        # 0x01 = 100% (fastest), 0x1F = ~3% (slowest)
        # Formula from model_0x54.py: speed% = round((0x1f - speed_raw) * (100 - 1) / (0x1f - 0x01) + 1)
        if raw_value < 0x01:
            raw_value = 0x01
        elif raw_value > 0x1F:
            raw_value = 0x1F
        speed_pct = round((0x1F - raw_value) * 99 / 30 + 1)
        return max(0, min(100, speed_pct))
    elif scale == ValueScale.PERCENT:
        # Value is 0-100 percentage
        # Handle potential overflow (device reporting 0-255 when we expect 0-100)
        if raw_value > 100:
            _LOGGER.debug(
                "Speed %d exceeds expected 0-100 range for product_id=0x%02X, "
                "converting from 0-255 to 0-100",
                raw_value, product_id or 0
            )
            return int(raw_value * 100 / 255)
        return max(0, min(100, raw_value))

    return max(0, min(100, raw_value))
