from enum import Enum

DOMAIN                    = "lednetwf_ble"
CONF_NAME                 = "name"
#CONF_RESET                = "reset"
CONF_DELAY                = "delay"
CONF_LEDCOUNT             = "ledcount"
CONF_LEDTYPE              = "ledtype"
CONF_COLORORDER           = "colororder"
CONF_MODEL                = "model"
CONF_SEGMENTS             = "segments"
CONF_IGNORE_NOTIFICATIONS = "ignore_notifications"

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
    
    @classmethod
    def from_name(cls, name):
        for member in cls:
            if member.name == name:
                return member
        raise ValueError(f"No member with name {name}")

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
    
    @classmethod
    def from_name(cls, name):
        for member in cls:
            if member.name == name:
                return member
        raise ValueError(f"No member with name {name}")

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

    @classmethod
    def from_name(cls, name):
        for member in cls:
            if member.name == name:
                return member
        raise ValueError(f"No member with name {name}")
