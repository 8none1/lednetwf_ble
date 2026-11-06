"""IOTBT segment detection from the advertised product ID (issue #114)."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from lednetwf_ble.const import IOTBT_SEGMENT_PRODUCT_IDS, IOTBT_V3_PRODUCT_IDS
from lednetwf_ble.device import LEDNetWFDevice
from lednetwf_ble.protocol import EffectType

SERVICE_UUID_5A00 = "00005a00-0000-1000-8000-00805f9b34fb"

# Real advertisements (14-byte service data under UUID 0x5A00).
# IOTBTC68, issue #114: product 0x00AA (170), flags2 0x07 (bit 0x08 clear).
ADV_IOTBTC68 = bytes.fromhex("80070865F0065C6800AA210A0107")
# IOTBT6BA, issue #83: product 0x00AD (173), flags2 0x0D (bit 0x08 set).
ADV_IOTBT6BA = bytes.fromhex("80070865F0BBB6BA00AD1F0A010D")
# IOTBT812: product 0x00C2 (194), flags2 0x05 (Telink).
ADV_IOTBT812 = bytes.fromhex("80070865F017581200C20E030105")


def make_device(name: str = "IOTBTC68") -> LEDNetWFDevice:
    return LEDNetWFDevice(MagicMock(), "AA:BB:CC:DD:EE:FF", name, product_id=0x00)


def advertise(device: LEDNetWFDevice, service_data: bytes) -> None:
    device.update_from_advertisement({}, {SERVICE_UUID_5A00: service_data})


def with_product_and_flags2(adv: bytes, product_id: int, flags2: int) -> bytes:
    out = bytearray(adv)
    out[8] = (product_id >> 8) & 0xFF
    out[9] = product_id & 0xFF
    out[13] = flags2
    return bytes(out)


def test_product_170_is_segment_despite_flags2():
    device = make_device()
    advertise(device, ADV_IOTBTC68)
    assert device._advertised_product_id == 170
    assert device._iotbt_flags2 == 0x07
    assert device.is_iotbt_segment is True
    assert device.is_iotbt_v3 is False
    # effect_type reads the auto-detected flag directly, so it must follow too
    assert device.effect_type == EffectType.IOTBT_SEGMENT


def test_repeated_adverts_do_not_flip_170_back_to_telink():
    device = make_device()
    for _ in range(3):
        advertise(device, ADV_IOTBTC68)
        assert device.is_iotbt_segment is True
        assert device._is_iotbt_segment is True


def test_iotbt6ba_still_segment():
    device = make_device("IOTBT6BA")
    advertise(device, ADV_IOTBT6BA)
    assert device._advertised_product_id == 173
    assert device.is_iotbt_segment is True
    assert device.effect_type == EffectType.IOTBT_SEGMENT


def test_173_segment_even_with_flags2_bit_clear():
    device = make_device("IOTBT6BA")
    advertise(device, with_product_and_flags2(ADV_IOTBT6BA, 173, 0x05))
    assert device.is_iotbt_segment is True


def test_iotbt812_still_telink():
    device = make_device("IOTBT812")
    advertise(device, ADV_IOTBT812)
    assert device._advertised_product_id == 194
    assert device.is_iotbt_segment is False
    assert device.effect_type != EffectType.IOTBT_SEGMENT


def test_unlisted_product_still_uses_flags2():
    device = make_device("IOTBTXXX")
    advertise(device, with_product_and_flags2(ADV_IOTBTC68, 0x1234, 0x0D))
    assert device.is_iotbt_segment is True
    advertise(device, with_product_and_flags2(ADV_IOTBTC68, 0x1234, 0x05))
    assert device.is_iotbt_segment is False


@pytest.mark.parametrize("override", ["telink", "v3"])
def test_manual_override_beats_product_list(override):
    device = make_device()
    advertise(device, ADV_IOTBTC68)
    device.set_iotbt_protocol_override(override)
    assert device.is_iotbt_segment is False
    assert device.is_iotbt_v3 is (override == "v3")


def test_telink_override_also_drives_effect_type():
    device = make_device()
    advertise(device, ADV_IOTBTC68)
    device.set_iotbt_protocol_override("telink")
    assert device.effect_type != EffectType.IOTBT_SEGMENT


def test_auto_override_restores_product_detection():
    device = make_device()
    advertise(device, ADV_IOTBTC68)
    device.set_iotbt_protocol_override("telink")
    device.set_iotbt_protocol_override("auto")
    assert device.is_iotbt_segment is True


def test_v3_product_is_never_segment():
    device = make_device("IOTBTV3")
    # flags2 bit set, which on its own would say segment
    advertise(device, with_product_and_flags2(ADV_IOTBTC68, 62, 0x0D))
    assert device.is_iotbt_v3 is True
    assert device.is_iotbt_segment is False


def test_product_lists_do_not_overlap():
    assert not (IOTBT_SEGMENT_PRODUCT_IDS & IOTBT_V3_PRODUCT_IDS)
