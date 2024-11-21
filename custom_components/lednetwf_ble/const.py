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


