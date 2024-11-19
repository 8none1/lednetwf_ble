from enum import Enum

DOMAIN            = "lednetwf_ble"
CONF_NAME         = "name"
CONF_RESET        = "reset"
CONF_DELAY        = "delay"
CONF_LEDCOUNT     = "ledcount"
CONF_LEDTYPE      = "ledtype"
CONF_COLORORDER   = "colororder"
CONF_MODEL        = "model"
RING_LIGHT_MODEL  = 0x53
STRIP_LIGHT_MODEL = 0x56

# The names given to the effects are just what I thought they looked like.  Updates are welcome.

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

# 0x56 Effect data
EFFECT_MAP_0x56 = {}
for e in range(1,100):
    EFFECT_MAP_0x56[f"Effect {e}"] = e

# So called "static" effects.  Actually they are effects which can also be set to a specific colour.
for e in range(1,11):
    EFFECT_MAP_0x56[f"Static Effect {e}"] = e << 8 # Give the static effects much higher values which we can then shift back again in the effect function

# Sound reactive effects.  Numbered 1-15 internally, we will offset them by 50 to avoid clashes with the other effects
for e in range(1+0x32, 16+0x32):
    EFFECT_MAP_0x56[f"Sound Reactive {e-0x32}"] = e << 8

#EFFECT_MAP_0x56["_Sound Reactive"] = 0xFFFF # This is going to be a special case




# EFFECT_LIST_0x53 = sorted(EFFECT_MAP_0x53)
EFFECT_LIST_0x56 = sorted(EFFECT_MAP_0x56)

# EFFECT_ID_TO_NAME_0x53 = {v: k for k, v in EFFECT_MAP_0x53.items()}
EFFECT_ID_TO_NAME_0x56 = {v: k for k, v in EFFECT_MAP_0x56.items()}

class LedTypes_StripLight(Enum):
    WS2812B    = 0x01
    SM16703    = 0x02
    SM16704    = 0x03
    WS2811     = 0x04
    UCS1903    = 0x05
    SK6812     = 0x06
    SK6812RGBW = 0x07
    INK1003    = 0x08
    UCS2904B   = 0x09
    JY1903     = 0x0A
    WS2812E    = 0x0B
    
    @classmethod # TODO make a super class for this
    def from_value(cls, value):
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"No member with value {value}")

class LedTypes_RingLight(Enum):
    Unknown    = 0x00
    WS2812B    = 0x01
    SM16703    = 0x02
    WS2811     = 0x03
    UCS1903    = 0x04
    SK6812     = 0x05
    INK1003    = 0x06
    
    @classmethod
    def from_value(cls, value):
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"No member with value {value}")

class ColorOrdering(Enum):
    RGB = 0x00
    RBG = 0x01
    GRB = 0x02
    GBR = 0x03
    BRG = 0x04
    BGR = 0x05
    
    @classmethod
    def from_value(cls, value):
        for member in cls:
            if member.value == value:
                return member
        raise ValueError(f"No member with value {value}")


