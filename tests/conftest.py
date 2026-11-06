"""Test setup: import the integration modules without Home Assistant installed.

The package __init__.py pulls in Home Assistant at import time, so the tests
register a bare package object pointing at the source directory (skipping
__init__.py) and stub the few Home Assistant and bleak names that device.py
imports. Only pure logic (detection properties, state parsing) is tested here.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

PKG_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "lednetwf_ble"
PKG_NAME = "lednetwf_ble"


def _stub(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    sys.modules[name] = mod
    return mod


class _BleakError(Exception):
    """Stand-in for bleak.exc.BleakError (must be a real exception class)."""


if "homeassistant" not in sys.modules:
    _stub("bleak", BleakClient=MagicMock())
    _stub("bleak.backends")
    _stub("bleak.backends.device", BLEDevice=MagicMock())
    _stub("bleak.exc", BleakError=_BleakError)
    _stub(
        "bleak_retry_connector",
        establish_connection=MagicMock(),
        BleakClientWithServiceCache=MagicMock(),
    )
    _stub("homeassistant")
    _stub("homeassistant.components", bluetooth=MagicMock())
    _stub("homeassistant.core", HomeAssistant=MagicMock(), callback=lambda func: func)

if PKG_NAME not in sys.modules:
    pkg = types.ModuleType(PKG_NAME)
    pkg.__path__ = [str(PKG_DIR)]
    sys.modules[PKG_NAME] = pkg
