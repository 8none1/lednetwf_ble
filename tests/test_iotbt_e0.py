"""E0 01 string-light family, product 197 (issue #126). Hex is from the issue capture."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lednetwf_ble import protocol
from lednetwf_ble.const import IOTBT_E0_EFFECTS, get_effect_id, get_effect_list
from lednetwf_ble.device import LEDNetWFDevice
from lednetwf_ble.protocol import EffectType

SERVICE_UUID_5A00 = "00005a00-0000-1000-8000-00805f9b34fb"
# IOTBT6E0 service data from the issue: sta 0x5B, product 0x00C5, flags2 0x2A (bit 0x08 set).
ADV_IOTBT6E0 = bytes.fromhex("5B070865F05256E000C54208012A")


def body(packet: bytearray) -> str:
    """Payload after the 8-byte transport header."""
    return bytes(packet[8:]).hex()


def make_device() -> LEDNetWFDevice:
    d = LEDNetWFDevice(MagicMock(), "08:65:F0:52:56:E0", "IOTBT6E0", product_id=0x00)
    d.update_from_advertisement({}, {SERVICE_UUID_5A00: ADV_IOTBT6E0})
    return d


def test_routed_as_e0_not_segment_despite_flags2():
    d = make_device()
    assert d.advertised_product_id == 0xC5
    assert d.is_iotbt_e0
    assert not d.is_iotbt_segment
    assert not d.is_iotbt_v3
    assert d.effect_type == EffectType.IOTBT_E0


@pytest.mark.parametrize("flags2", [0x05, 0x2A])
def test_product_253_routed_as_e0_whatever_flags2(flags2):
    # Surplife tree star, issue #130: product 0x00FD, firmware 0x07. The issue logs
    # carry no advertisement, so flags2 is unknown; routing must not depend on it.
    d = LEDNetWFDevice(MagicMock(), "E4:98:BB:00:00:00", "IOTBTAF1", product_id=0x00)
    adv = bytes.fromhex("5B07E498BB00000000FD260701") + bytes([flags2])
    d.update_from_advertisement({}, {SERVICE_UUID_5A00: adv})
    assert d.advertised_product_id == 0xFD
    assert d.is_iotbt_e0
    assert not d.is_iotbt_segment
    assert not d.is_iotbt_v3
    assert d.effect_type == EffectType.IOTBT_E0


def test_product_100_routed_as_e0_with_flags2_bit_clear():
    # Surplife-app string lights: product 0x0064, flags2 0x05. MAC tail zeroed.
    d = LEDNetWFDevice(MagicMock(), "E4:98:BB:00:00:00", "IOTBT000", product_id=0x00)
    d.update_from_advertisement(
        {}, {SERVICE_UUID_5A00: bytes.fromhex("5B07E498BB000000006426050105")}
    )
    assert d.advertised_product_id == 0x64
    assert d.is_iotbt_e0
    assert not d.is_iotbt_segment
    assert not d.is_iotbt_v3
    assert d.effect_type == EffectType.IOTBT_E0


def test_manual_override_wins():
    d = make_device()
    d.set_iotbt_protocol_override("telink")
    assert not d.is_iotbt_e0


@pytest.mark.parametrize("on,payload", [
    (True, "e0010023" + "00" * 10),
    (False, "e0010024" + "00" * 10),
])
def test_power(on, payload):
    assert body(protocol.build_iotbt_e0_power_command(on)) == payload


@pytest.mark.parametrize("rgb,expected", [
    ((255, 0, 0), "e00100c100646400000000140000"),     # red
    ((0, 255, 0), "e00100c13c646400000000140000"),     # green
    ((0, 0, 255), "e00100c178646400000000140000"),     # blue
    ((255, 255, 0), "e00100c11e646400000000140000"),   # yellow
    ((0, 255, 255), "e00100c15a646400000000140000"),   # cyan
    ((255, 255, 255), "e00100c100006400000000140000"),  # white
])
def test_solid_colours_match_capture(rgb, expected):
    assert body(protocol.build_iotbt_e0_color_command(*rgb, 100)) == expected


def test_brightness_is_value_byte():
    assert body(protocol.build_iotbt_e0_color_command(255, 255, 255, 49)) == "e00100c100003100000000140000"


def test_header_matches_capture():
    # "Power ON" row: 0004 80 00 000e 0f 0a ...; seq is stamped by the device class.
    pkt = protocol.build_iotbt_e0_power_command(True)
    assert pkt[2:4] == b"\x80\x00" and pkt[5] == 0x0E and pkt[6] == 0x0F and pkt[7] == 0x0A


def test_all_scenes_are_well_formed_and_named():
    assert len(IOTBT_E0_EFFECTS) == 42
    assert set(IOTBT_E0_EFFECTS) == set(protocol.IOTBT_E0_SCENES)
    for eid in IOTBT_E0_EFFECTS:
        pkt = protocol.build_iotbt_e0_effect_command(eid)
        p = bytes(pkt[8:])
        assert p[:2] == b"\xe1\x21"
        assert len(p) == 16 + 5 * p[15]            # colour count at byte 15
        assert ((pkt[4] << 8) | pkt[5]) == len(p)  # header length agrees


def test_known_scene_matches_capture():
    eid = get_effect_id("Meteor Shower", EffectType.IOTBT_E0)
    assert body(protocol.build_iotbt_e0_effect_command(eid)) == "e12100640b00056450007864640000011e64640000"


def test_effect_list_and_dispatch():
    assert "Christmas 1" in get_effect_list(EffectType.IOTBT_E0)
    pkt = protocol.build_effect_command(EffectType.IOTBT_E0, 1, 50, 100)
    assert body(pkt).startswith("e12100640200015050")


def test_identity_line_logged_once_per_debug_session(caplog):
    # Bug-report logs rarely contain the advertisement parse (a connected device
    # stops advertising), so the first command of a debug session repeats it.
    import logging

    d = make_device()
    logger = "lednetwf_ble.device"
    with caplog.at_level(logging.DEBUG, logger=logger):
        d._log_identity_once()
        d._log_identity_once()
    lines = [r.getMessage() for r in caplog.records if "Device identity" in r.getMessage()]
    assert len(lines) == 1
    assert "advertised_product_id=0xC5" in lines[0]
    assert "flags2=0x2A" in lines[0]
    assert "effect_type=IOTBT_E0" in lines[0]
    assert "service_data=5B 07 08 65 F0 52 56 E0 00 C5 42 08 01 2A" in lines[0]

    # Debug off clears the flag, so the next debug session logs the line again.
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=logger):
        d._log_identity_once()
    with caplog.at_level(logging.DEBUG, logger=logger):
        d._log_identity_once()
    assert sum("Device identity" in r.getMessage() for r in caplog.records) == 1
