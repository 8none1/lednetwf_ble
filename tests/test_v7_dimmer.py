"""BLE v7 state-only manufacturer data on a dimmer controller (issue #119)."""
from __future__ import annotations

from lednetwf_ble.protocol import (
    get_service_data_from_advertisement,
    parse_manufacturer_data,
    parse_service_data,
)

# Real IOTWF1BB advertisement from the issue (product 0x41, Ctrl_Dim, BLE v7).
MFR = bytes.fromhex("52246101500F000000646400000000000000000000000000000000")
SERVICE = bytes.fromhex("5207A817106631BB0041E0040100")
SERVICE_UUID = "00005a02-0000-1000-8000-00805f9b34fb"


def test_product_id_comes_from_service_data():
    sd = get_service_data_from_advertisement({SERVICE_UUID: SERVICE})
    parsed = parse_service_data(sd)
    assert parsed["advertised_product_id"] == 0x41
    assert parsed["ble_version"] == 7


def test_v7_state_only_not_misread_as_format_b():
    result = parse_manufacturer_data({0x5A02: MFR}, "IOTWF1BB", has_service_data=True)
    assert result["format"] == "v7_state"
    assert result["product_id"] is None
    assert result["power_state"] is False
    assert result["brightness_percent"] == 100


def test_without_service_data_behaviour_is_unchanged():
    # Same bytes with no service data still take the old Format B path.
    result = parse_manufacturer_data({0x5A02: MFR}, "IOTWF1BB")
    assert result["product_id"] == 0x64
