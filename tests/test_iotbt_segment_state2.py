"""Segment-family 0xEA 0x81 (DeviceState2) parsing, from the issue #114 capture.

Frames are copied from the IOTBTC68 Surplife capture (TX command, then the RX
state frame the lamp sent back).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lednetwf_ble import protocol
from lednetwf_ble.const import DEFAULT_EFFECT_SPEED
from lednetwf_ble.device import LEDNetWFDevice

SERVICE_UUID_5A00 = "00005a00-0000-1000-8000-00805f9b34fb"
ADV_IOTBTC68 = bytes.fromhex("80070865F0065C6800AA210A0107")
ADV_IOTBT812 = bytes.fromhex("80070865F017581200C20E030105")

TAIL = "05 00 3c ff ff ff ff 01 00 00 00"


def frame(body: str) -> bytes:
    """Build an RX frame from bytes 6-15 (power .. white brightness)."""
    return bytes.fromhex(f"ea 81 01 00 aa 0a {body} {TAIL}")


# After E0 01 ... 64 (white mode, 100%)
WHITE_100 = frame("23 25 6f 32 f0 70 e4 64 00 64")
# After E0 01 ... 00 (white mode, 0%)
WHITE_0 = frame("23 25 6f 32 f0 70 e4 64 00 00")
# After E0 01 ... 19 (white mode, 25%): the lamp reports 0x18
WHITE_25 = frame("23 25 6f 32 f0 70 e4 64 00 18")
# After E0 01 ... 1e (white mode, 30%): the lamp reports 0x1d
WHITE_30 = frame("23 25 6f 32 f0 75 64 3e 00 1d")
# After E1 03 ... H=4b S=e4 V=64: still carries the previous colour (45 e4 64)
STATIC_LAGGED = frame("23 24 01 32 f0 45 e4 64 00 64")
# After E1 01 scene 0x01 speed 80
SCENE_01_SPEED_80 = frame("23 25 01 50 f0 3c 64 64 00 64")
# After E1 01 scene 0x06 at speeds 34, 1, 100, 95
SCENE_06 = {
    34: frame("23 25 06 22 f0 23 64 64 00 64"),
    1: frame("23 25 06 01 f0 23 64 64 00 64"),
    100: frame("23 25 06 64 f0 23 64 64 00 64"),
    95: frame("23 25 06 5f f0 23 64 64 00 64"),
}
# After 71 24 (power off), lamp in white mode
WHITE_OFF = frame("24 25 6f 32 f0 75 64 3e 00 1d")


def make_device(adv: bytes, name: str) -> LEDNetWFDevice:
    device = LEDNetWFDevice(MagicMock(), "AA:BB:CC:DD:EE:FF", name, product_id=0x00)
    device.update_from_advertisement({}, {SERVICE_UUID_5A00: adv})
    return device


@pytest.fixture
def lamp() -> LEDNetWFDevice:
    device = make_device(ADV_IOTBTC68, "IOTBTC68")
    assert device.is_iotbt_segment
    return device


# ----- protocol.parse_iotbt_segment_state2 -----

def test_parse_white_mode():
    state = protocol.parse_iotbt_segment_state2(WHITE_100)
    assert state["is_on"] is True
    assert state["is_white_mode"] is True
    assert state["is_static_colour"] is False
    assert state["is_scene_mode"] is False
    assert state["white_brightness"] == 100


def test_parse_static_colour_packed_hue():
    state = protocol.parse_iotbt_segment_state2(STATIC_LAGGED)
    assert state["is_static_colour"] is True
    assert state["is_white_mode"] is False
    assert state["is_scene_mode"] is False
    # 0x45 0xE4 packed = (0x45E4 >> 7, 0xE4 & 0x7F)
    assert state["hue"] == 139
    assert state["saturation"] == 100
    assert state["value"] == 100


def test_scene_byte_01_is_not_static_colour():
    state = protocol.parse_iotbt_segment_state2(SCENE_01_SPEED_80)
    assert state["is_scene_mode"] is True
    assert state["is_static_colour"] is False
    assert state["scene"] == 0x01
    assert state["speed"] == 80


def test_parse_power_off():
    assert protocol.parse_iotbt_segment_state2(WHITE_OFF)["is_on"] is False


def test_parse_rejects_short_or_foreign_frames():
    assert protocol.parse_iotbt_segment_state2(WHITE_100[:15]) is None
    assert protocol.parse_iotbt_segment_state2(b"\x81" + WHITE_100[1:]) is None


# ----- LEDNetWFDevice._parse_device_state2_response -----

def test_led_config_still_parsed(lamp):
    lamp._parse_device_state2_response(WHITE_100)
    assert lamp._segments == 5
    assert lamp._led_count == 60


@pytest.mark.parametrize(
    "data,expected",
    [(WHITE_100, 255), (WHITE_0, 0), (WHITE_25, 61), (WHITE_30, 74)],
)
def test_white_mode_brightness(lamp, data, expected):
    lamp._parse_device_state2_response(data)
    assert lamp.brightness == expected


@pytest.mark.parametrize("speed", sorted(SCENE_06))
def test_scene_speed(lamp, speed):
    lamp._parse_device_state2_response(SCENE_06[speed])
    assert lamp.effect_speed == speed


def test_scene_does_not_touch_brightness_or_effect(lamp):
    lamp._brightness = 128
    lamp._effect = "Summer Wind"
    lamp._parse_device_state2_response(SCENE_06[34])
    assert lamp.brightness == 128
    assert lamp.effect == "Summer Wind"


def test_static_colour_frame_leaves_last_sent_colour(lamp):
    # HA just sent a colour; the reply carries the colour from the command before.
    lamp._rgb = (255, 0, 0)
    lamp._brightness = 200
    lamp._effect_speed = 42
    lamp._parse_device_state2_response(STATIC_LAGGED)
    assert lamp.rgb_color == (255, 0, 0)
    assert lamp.brightness == 200
    assert lamp.effect_speed == 42
    assert lamp.is_on is True


def test_white_mode_power_off(lamp):
    lamp._parse_device_state2_response(WHITE_OFF)
    assert lamp.is_on is False


def test_telink_device_ignores_segment_fields():
    device = make_device(ADV_IOTBT812, "IOTBT812")
    assert not device.is_iotbt_segment
    device._brightness = 128
    device._parse_device_state2_response(WHITE_0)
    device._parse_device_state2_response(SCENE_06[34])
    assert device.brightness == 128
    assert device.effect_speed == DEFAULT_EFFECT_SPEED
    assert device._segments is None
