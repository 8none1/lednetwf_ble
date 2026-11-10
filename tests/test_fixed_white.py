"""Fixed single-white-channel lamp, product 39 Sunset Lamp (issue #121).

Frames are copied from the debug log in issue #75: the 0x3B 0xB1 white command
and the state replies the lamp sent for it and for an RGB change.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lednetwf_ble.device import LEDNetWFDevice

# 81 27 23 61 16 01 | 00 00 00 | FF 01 00 0F 52 : white mode, 100%
WHITE_STATE = bytes.fromhex("812723611601000000FF01000F52")
# Same lamp after an RGB change to (255, 120, 31)
RGB_STATE = bytes.fromhex("812723611601FF781F000100F0CA")


def make_lamp(product_id: int = 39) -> LEDNetWFDevice:
    device = LEDNetWFDevice(MagicMock(), "AA:BB:CC:DD:EE:FF", "LEDnetWF02", product_id=product_id)
    device._ble_version = 5
    return device


def test_product_39_has_fixed_white_and_no_colour_temp():
    lamp = make_lamp(39)
    assert lamp.has_fixed_white
    assert not lamp.has_color_temp
    assert lamp.has_rgb


@pytest.mark.parametrize("product_id", [6, 7, 32, 38, 72])
def test_other_products_are_unchanged(product_id):
    # Only uses_color_v2 products (39) switch to the fixed white mode
    lamp = make_lamp(product_id)
    assert not lamp.has_fixed_white
    assert lamp.has_color_temp == bool(
        lamp._capabilities.get("has_ww") or lamp._capabilities.get("has_cw")
    )


def test_white_state_sets_white_mode_without_kelvin():
    lamp = make_lamp()
    lamp._parse_state_response(WHITE_STATE)
    assert lamp.white_mode
    assert lamp.color_temp_kelvin is None
    assert lamp.brightness == 255


def test_rgb_state_clears_white_mode():
    lamp = make_lamp()
    lamp._parse_state_response(WHITE_STATE)
    lamp._parse_state_response(RGB_STATE)
    assert not lamp.white_mode
    assert lamp.rgb_color == (255, 120, 31)


def test_set_white_sends_the_frame_the_lamp_acked():
    import asyncio
    from unittest.mock import AsyncMock

    lamp = make_lamp()
    lamp._send_command = AsyncMock(return_value=True)
    assert asyncio.run(lamp.set_white(255))
    sent = bytes(lamp._send_command.call_args.args[0])
    # Frame from the issue #75 log, ignoring the sequence byte at index 1
    logged = bytes.fromhex("002C800000 0D0E0B3BB1000000006400000000 0050".replace(" ", ""))
    assert sent[:1] + sent[2:] == logged[:1] + logged[2:]
    assert lamp.white_mode
