"""Device capability lookup from app JSON configuration files.

This module loads device capabilities from the Surplife Android app's
JSON configuration files and provides lookup functionality.

The data files define:
- Device functions and their firmware version requirements
- Command byte templates
- Parameter ranges (min/max/step)
- State protocol types

Usage:
    from .capabilities import CAPABILITIES

    # Get device info
    device = CAPABILITIES.get_device(0x08)

    # Check if function is supported
    if CAPABILITIES.supports_function(0x08, "scene_data_v2", firmware_ver=1):
        ...

    # Get command template
    template = CAPABILITIES.get_command_template(0x08, "colour_data")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class FunctionCapability:
    """A device function capability with firmware requirements."""

    code: str
    name: str
    desc: str
    min_firmware: int
    type: str  # "Json", "Hex", etc.
    fields: dict[str, dict[str, Any]] = field(default_factory=dict)

    def get_field_range(self, field_name: str) -> tuple[int | None, int | None, int]:
        """Get (min, max, step) for a field."""
        if field_name not in self.fields:
            return (None, None, 1)
        f = self.fields[field_name]
        return (f.get("min"), f.get("max"), f.get("step", 1))


@dataclass
class CommandTemplate:
    """A command template with format and options."""

    cmd_form: str
    need_checksum: bool = False
    need_set_online: bool = False
    response_count: int = 0
    at_cmd: bool = False
    opcode: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandTemplate":
        """Create from JSON dict."""
        # Handle nested customParams for device-specific overrides
        custom = data.get("customParams", {})
        return cls(
            cmd_form=data.get("cmdForm", ""),
            need_checksum=data.get("needChecksum", False) or custom.get("needChecksum", False),
            need_set_online=data.get("needSetOnline", False),
            response_count=data.get("responseCount", 0),
            at_cmd=data.get("ATCmd", False),
            opcode=data.get("opcode"),
        )


@dataclass
class ProtocolInfo:
    """Protocol information with firmware requirements."""

    name: str
    desc: str
    min_firmware: int


@dataclass
class DeviceCapabilities:
    """Complete device capabilities from JSON."""

    product_id: int
    icon: str
    category: str
    category_code: str
    functions: dict[str, FunctionCapability]
    hex_cmd_forms: dict[str, CommandTemplate]
    protocols: list[ProtocolInfo]
    state_protocols: list[ProtocolInfo]

    def supports_function(self, function_code: str, firmware_version: int = 0) -> bool:
        """Check if device supports a function at given firmware version."""
        if function_code not in self.functions:
            return False
        return firmware_version >= self.functions[function_code].min_firmware

    def get_function(self, function_code: str) -> FunctionCapability | None:
        """Get function capability by code."""
        return self.functions.get(function_code)

    def get_state_protocol(self, firmware_version: int = 0) -> str:
        """Get the appropriate state protocol name for firmware version."""
        # Return the highest-versioned protocol that this firmware supports
        best = None
        best_ver = -1
        for sp in self.state_protocols:
            if firmware_version >= sp.min_firmware and sp.min_firmware > best_ver:
                best = sp.name
                best_ver = sp.min_firmware
        return best or "wifibleLightStandardV1"


class CapabilityDatabase:
    """Database of device capabilities loaded from JSON files."""

    def __init__(self) -> None:
        """Initialize and load data files."""
        self._devices: dict[int, dict[str, Any]] = {}
        self._cmd_templates: dict[str, dict[str, Any]] = {}
        self._ble_cmd_overrides: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy load data files on first access."""
        if self._loaded:
            return

        data_dir = Path(__file__).parent / "data"

        # Load BLE devices
        ble_devices_path = data_dir / "ble_devices.json"
        if ble_devices_path.exists():
            try:
                with open(ble_devices_path, encoding="utf-8") as f:
                    devices = json.load(f)
                    self._devices = {d["productId"]: d for d in devices}
                _LOGGER.debug("Loaded %d BLE devices from JSON", len(self._devices))
            except Exception as ex:
                _LOGGER.error("Failed to load ble_devices.json: %s", ex)

        # Load WiFi command templates (shared with BLE)
        wifi_cmd_path = data_dir / "wifi_dp_cmd.json"
        if wifi_cmd_path.exists():
            try:
                with open(wifi_cmd_path, encoding="utf-8") as f:
                    self._cmd_templates = json.load(f)
                _LOGGER.debug("Loaded %d command templates from JSON", len(self._cmd_templates))
            except Exception as ex:
                _LOGGER.error("Failed to load wifi_dp_cmd.json: %s", ex)

        # Load BLE-specific command overrides
        ble_cmd_path = data_dir / "ble_dp_cmd.json"
        if ble_cmd_path.exists():
            try:
                with open(ble_cmd_path, encoding="utf-8") as f:
                    self._ble_cmd_overrides = json.load(f)
                _LOGGER.debug("Loaded %d BLE command overrides", len(self._ble_cmd_overrides))
            except Exception as ex:
                _LOGGER.error("Failed to load ble_dp_cmd.json: %s", ex)

        self._loaded = True

    def get_device(self, product_id: int) -> DeviceCapabilities | None:
        """Get capabilities for a device by product ID."""
        self._ensure_loaded()

        if product_id not in self._devices:
            return None

        device = self._devices[product_id]

        # Parse functions
        functions: dict[str, FunctionCapability] = {}
        for func in device.get("functions", []):
            fields: dict[str, dict[str, Any]] = {}
            for fld in func.get("value", {}).get("fields", []):
                fields[fld["fieldName"]] = {
                    "min": fld.get("min"),
                    "max": fld.get("max"),
                    "step": fld.get("step", 1),
                }
            functions[func["code"]] = FunctionCapability(
                code=func["code"],
                name=func.get("name", func["code"]),
                desc=func.get("desc", ""),
                min_firmware=func.get("deviceMinVer", 0),
                type=func.get("type", "Hex"),
                fields=fields,
            )

        # Parse device-specific command overrides
        hex_cmd_forms: dict[str, CommandTemplate] = {}
        for code, template in device.get("hexCmdForms", {}).items():
            hex_cmd_forms[code] = CommandTemplate.from_dict(template)

        # Parse protocols
        protocols = [
            ProtocolInfo(
                name=p["name"],
                desc=p.get("desc", ""),
                min_firmware=p.get("deviceMinVer", 0),
            )
            for p in device.get("protocols", [])
        ]

        # Parse state protocols
        state_protocols = [
            ProtocolInfo(
                name=p["name"],
                desc=p.get("desc", ""),
                min_firmware=p.get("deviceMinVer", 0),
            )
            for p in device.get("stateProtocol", [])
        ]

        return DeviceCapabilities(
            product_id=product_id,
            icon=device.get("icon", ""),
            category=device.get("category", ""),
            category_code=device.get("categoryCode", ""),
            functions=functions,
            hex_cmd_forms=hex_cmd_forms,
            protocols=protocols,
            state_protocols=state_protocols,
        )

    def get_device_raw(self, product_id: int) -> dict[str, Any] | None:
        """Get raw device data dict (for debugging)."""
        self._ensure_loaded()
        return self._devices.get(product_id)

    def supports_function(
        self, product_id: int, function_code: str, firmware_version: int = 0
    ) -> bool:
        """Check if device supports a function at given firmware version."""
        device = self.get_device(product_id)
        if not device:
            return False
        return device.supports_function(function_code, firmware_version)

    def get_function(
        self, product_id: int, function_code: str
    ) -> FunctionCapability | None:
        """Get function capability for a device."""
        device = self.get_device(product_id)
        if not device:
            return None
        return device.get_function(function_code)

    def get_command_template(
        self, product_id: int, function_code: str
    ) -> CommandTemplate | None:
        """Get command template, preferring device-specific over global.

        Resolution order:
        1. Device-specific hexCmdForms (in ble_devices.json)
        2. BLE command overrides (ble_dp_cmd.json)
        3. Global WiFi templates (wifi_dp_cmd.json)
        """
        self._ensure_loaded()

        device = self.get_device(product_id)

        # 1. Check device-specific hexCmdForms first
        if device and function_code in device.hex_cmd_forms:
            return device.hex_cmd_forms[function_code]

        # 2. Check BLE-specific overrides
        if function_code in self._ble_cmd_overrides:
            return CommandTemplate.from_dict(self._ble_cmd_overrides[function_code])

        # 3. Fall back to global WiFi templates
        if function_code in self._cmd_templates:
            return CommandTemplate.from_dict(self._cmd_templates[function_code])

        return None

    def get_all_product_ids(self) -> list[int]:
        """Get list of all known product IDs."""
        self._ensure_loaded()
        return list(self._devices.keys())

    def get_best_function(
        self,
        product_id: int,
        firmware_version: int,
        function_preferences: list[str],
    ) -> str | None:
        """Get the best available function from a preference list.

        Args:
            product_id: Device product ID
            firmware_version: Device firmware version
            function_preferences: List of functions in preference order
                                  e.g., ["scene_data_v3", "scene_data_v2", "scene_data"]

        Returns:
            Best supported function code, or None
        """
        for func in function_preferences:
            if self.supports_function(product_id, func, firmware_version):
                return func
        return None


# Global instance - lazy loaded on first access
CAPABILITIES = CapabilityDatabase()
