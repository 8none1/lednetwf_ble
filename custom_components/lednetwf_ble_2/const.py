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
CONF_LED_TYPE: Final = "led_type"
CONF_COLOR_ORDER: Final = "color_order"

# Default values
DEFAULT_DISCONNECT_DELAY: Final = 30  # seconds
DEFAULT_LED_COUNT: Final = 60
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
    """LED chip types for addressable strips."""
    UCS1903 = 1
    SM16703 = 2
    WS2811 = 3
    WS2812B = 4
    SK6812 = 5
    INK1003 = 6
    WS2801 = 7
    WS2815 = 8
    APA102 = 9
    TM1914 = 10
    UCS2904B = 11


class ColorOrder(IntEnum):
    """RGB color ordering for LED strips."""
    RGB = 0
    RBG = 1
    GRB = 2
    GBR = 3
    BRG = 4
    BGR = 5


class EffectType(IntEnum):
    """Effect command type based on device."""
    NONE = 0
    SIMPLE = 1      # 0x61 command, effects 37-56
    SYMPHONY = 2    # 0x38 command, effects 1-44 (scene) + 100-399 (build)


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

# Symphony Scene effects (0x38 command) - IDs 1-44
SYMPHONY_SCENE_EFFECTS: Final = {
    1: "Static",
    2: "Breathing",
    3: "Rainbow",
    4: "Color wipe",
    5: "Theater chase",
    6: "Twinkle",
    7: "Scanner",
    8: "Fade",
    9: "Color chase",
    10: "Running lights",
    11: "Sparkle",
    12: "Fire",
    13: "Meteor",
    14: "Wave",
    15: "Comet",
    16: "Bouncing balls",
    17: "Fireworks",
    18: "Ripple",
    # 19-44 are additional variations
}

# Product ID to capabilities mapping
# Source: protocol_docs/04_device_identification_capabilities.md
# Source: protocol_docs/09_effects_addressable_led_support.md
PRODUCT_CAPABILITIES: Final = {
    # Controllers with RGB + White (RGBWBoth / RGBCWBoth)
    4:   {"name": "Ctrl_RGBW_UFO", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    6:   {"name": "Ctrl_Mini_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    7:   {"name": "Ctrl_Mini_RGBCW", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    32:  {"name": "Ctrl_Mini_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    37:  {"name": "Ctrl_RGBCW_Both", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    38:  {"name": "Ctrl_Mini_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    39:  {"name": "Ctrl_Mini_RGBW", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},
    72:  {"name": "Ctrl_Mini_RGBW_Mic", "has_rgb": True, "has_ww": True, "has_cw": False, "effect_type": EffectType.SIMPLE},

    # Controllers with RGB only
    8:   {"name": "Ctrl_Mini_RGB_Mic", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True},
    16:  {"name": "ChristmasLight", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SIMPLE},
    51:  {"name": "Ctrl_Mini_RGB", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SIMPLE},

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
    29:  {"name": "FillLight", "has_rgb": None, "has_ww": None, "has_cw": None, "is_stub": True, "effect_type": EffectType.NONE},
    41:  {"name": "MirrorLight", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SIMPLE},
    209: {"name": "Digital_Light", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True},

    # Ring/Strip lights with background color support
    0:   {"name": "RingLight_Generic", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SYMPHONY, "has_segments": True},
    83:  {"name": "RingLight_0x53", "has_rgb": True, "has_ww": True, "has_cw": True, "effect_type": EffectType.SYMPHONY, "has_segments": True},  # 0x53
    86:  {"name": "RingLight_0x56", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_bg_color": True},  # 0x56
    128: {"name": "RingLight_0x80", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_bg_color": True},  # 0x80

    # Ceiling lights
    225: {"name": "Ctrl_Ceiling", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},
    226: {"name": "Ctrl_Ceiling_Assist", "has_rgb": False, "has_ww": True, "has_cw": True, "effect_type": EffectType.NONE},

    # Symphony controllers - addressable RGB with effects
    161: {"name": "Ctrl_RGB_Symphony", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True},
    162: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True},
    163: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True},
    164: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True},
    166: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True},
    167: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True},
    169: {"name": "Ctrl_RGB_Symphony_new", "has_rgb": True, "has_ww": False, "has_cw": False, "effect_type": EffectType.SYMPHONY, "has_segments": True, "has_ic_config": True},
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


def get_effect_list(effect_type: EffectType) -> list[str]:
    """Get list of effect names for the given effect type."""
    if effect_type == EffectType.SIMPLE:
        return list(SIMPLE_EFFECTS.values())
    elif effect_type == EffectType.SYMPHONY:
        # Scene effects (1-44) + Build effects (100-399)
        effects = list(SYMPHONY_SCENE_EFFECTS.values())
        # Add build effects as numbered entries
        for i in range(100, 400):
            effects.append(f"Build Effect {i - 99}")
        return effects
    return []


def get_effect_id(effect_name: str, effect_type: EffectType) -> int | None:
    """Get effect ID from name."""
    if effect_type == EffectType.SIMPLE:
        for eid, name in SIMPLE_EFFECTS.items():
            if name == effect_name:
                return eid
    elif effect_type == EffectType.SYMPHONY:
        for eid, name in SYMPHONY_SCENE_EFFECTS.items():
            if name == effect_name:
                return eid
        # Check build effects
        if effect_name.startswith("Build Effect "):
            try:
                num = int(effect_name.replace("Build Effect ", ""))
                return num + 99  # Convert back to protocol ID
            except ValueError:
                pass
    return None
