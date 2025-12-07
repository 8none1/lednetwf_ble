"""Command builder from JSON templates.

This module builds BLE commands from templates defined in the app's JSON files.
It handles parameter substitution and checksum calculation.

Usage:
    from .commands import build_command, get_best_function

    # Build a color command
    cmd = build_command(0x08, "colour_data", {"r": 255, "g": 0, "b": 128})

    # Build an effect command with the best available function
    func = get_best_function(0x08, firmware_ver, ["scene_data_v2", "scene_data"])
    cmd = build_command(0x08, func, {"model": 41, "speed": 16, "bright": 100})
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .capabilities import CAPABILITIES, CommandTemplate, FunctionCapability

_LOGGER = logging.getLogger(__name__)


class CommandBuildError(Exception):
    """Raised when command building fails."""

    pass


def build_command(
    product_id: int,
    function_code: str,
    params: dict[str, int],
    firmware_version: int = 0,
) -> bytes:
    """Build a command from template and parameters.

    Args:
        product_id: Device product ID
        function_code: Function name (e.g., "scene_data_v2")
        params: Parameter values (e.g., {"model": 41, "speed": 16, "bright": 100})
        firmware_version: Device firmware version for validation

    Returns:
        Command bytes ready to send (with checksum if needed)

    Raises:
        CommandBuildError: If template not found or parameters invalid
    """
    template = CAPABILITIES.get_command_template(product_id, function_code)
    if not template:
        raise CommandBuildError(
            f"No command template for function '{function_code}' "
            f"(product_id=0x{product_id:02X})"
        )

    return build_from_template(template, params, product_id, function_code)


def build_from_template(
    template: CommandTemplate,
    params: dict[str, int],
    product_id: int | None = None,
    function_code: str | None = None,
) -> bytes:
    """Build command bytes from a template.

    Args:
        template: CommandTemplate with format string
        params: Parameter values to substitute
        product_id: Optional product ID for validation
        function_code: Optional function code for validation

    Returns:
        Command bytes with checksum if needed
    """
    cmd_form = template.cmd_form

    # Validate parameters against function definition if available
    if product_id is not None and function_code is not None:
        func = CAPABILITIES.get_function(product_id, function_code)
        if func:
            _validate_params(params, func)

    # Substitute parameters in template
    cmd_form = _substitute_params(cmd_form, params)

    # Convert hex string to bytes
    try:
        cmd = bytes.fromhex(cmd_form)
    except ValueError as ex:
        raise CommandBuildError(
            f"Invalid hex after substitution: '{cmd_form}' - {ex}"
        ) from ex

    # Add checksum if needed
    if template.need_checksum:
        checksum = sum(cmd) & 0xFF
        cmd = cmd + bytes([checksum])

    return cmd


def _substitute_params(cmd_form: str, params: dict[str, int]) -> str:
    """Substitute parameter placeholders in command template.

    Handles:
    - Single byte: {param} -> 2 hex chars
    - Multi-byte by repetition: {param}{param}{param} -> repeated param bytes
      (e.g., {delay}{delay} for 16-bit value split into 2 bytes)
    """
    result = cmd_form

    # Find all placeholders
    placeholders = re.findall(r"\{(\w+)\}", cmd_form)

    # Count occurrences of each parameter
    param_counts: dict[str, int] = {}
    for p in placeholders:
        param_counts[p] = param_counts.get(p, 0) + 1

    # Substitute each parameter
    for param_name, count in param_counts.items():
        if param_name not in params:
            _LOGGER.warning(
                "Missing parameter '%s' in command template, using 0", param_name
            )
            value = 0
        else:
            value = params[param_name]

        placeholder = f"{{{param_name}}}"

        if count == 1:
            # Single byte parameter
            result = result.replace(placeholder, f"{value & 0xFF:02x}")
        else:
            # Multi-byte parameter - split value into bytes
            # e.g., {delay}{delay} for 16-bit: high byte first, then low byte
            # e.g., {gradient}{gradient}{gradient} for 24-bit: high to low
            byte_values = _split_value_to_bytes(value, count)
            for byte_val in byte_values:
                # Replace one occurrence at a time
                result = result.replace(placeholder, f"{byte_val:02x}", 1)

    return result


def _split_value_to_bytes(value: int, num_bytes: int) -> list[int]:
    """Split a multi-byte value into individual bytes (big-endian).

    Args:
        value: Integer value to split
        num_bytes: Number of bytes to produce

    Returns:
        List of byte values, most significant first
    """
    # Mask to the appropriate number of bits
    max_val = (1 << (num_bytes * 8)) - 1
    value = value & max_val

    result = []
    for i in range(num_bytes - 1, -1, -1):
        byte_val = (value >> (i * 8)) & 0xFF
        result.append(byte_val)
    return result


def _validate_params(params: dict[str, int], func: FunctionCapability) -> None:
    """Validate parameter values against function definition.

    Logs warnings for out-of-range values but doesn't raise exceptions.
    """
    for param_name, value in params.items():
        if param_name not in func.fields:
            continue

        min_val, max_val, step = func.get_field_range(param_name)

        if min_val is not None and value < min_val:
            _LOGGER.warning(
                "Parameter '%s' value %d below minimum %d",
                param_name,
                value,
                min_val,
            )

        if max_val is not None and value > max_val:
            _LOGGER.warning(
                "Parameter '%s' value %d above maximum %d",
                param_name,
                value,
                max_val,
            )


def get_best_function(
    product_id: int,
    firmware_version: int,
    function_preferences: list[str],
) -> str | None:
    """Get the best available function from a preference list.

    Convenience wrapper around CAPABILITIES.get_best_function().

    Args:
        product_id: Device product ID
        firmware_version: Device firmware version
        function_preferences: List of functions in preference order

    Returns:
        Best supported function code, or None
    """
    return CAPABILITIES.get_best_function(
        product_id, firmware_version, function_preferences
    )


def build_effect_command(
    product_id: int,
    firmware_version: int,
    effect_id: int,
    speed: int,
    brightness: int = 100,
) -> bytes | None:
    """Build an effect command using the best available function.

    Args:
        product_id: Device product ID
        firmware_version: Device firmware version
        effect_id: Effect ID (37-56 for SIMPLE effects)
        speed: Speed 0-100 (will be converted to protocol format)
        brightness: Brightness 0-100

    Returns:
        Command bytes or None if no effect function available
    """
    func = get_best_function(
        product_id,
        firmware_version,
        ["scene_data_v3", "scene_data_v2", "scene_data"],
    )

    if not func:
        return None

    # Convert speed from 0-100 to protocol format
    # For v2/v1: 1-31, inverted (100% speed = 1, 0% speed = 31)
    # For v3: 0-100 direct
    if func == "scene_data_v3":
        # v3: direct 0-100
        protocol_speed = speed
        params = {
            "preview": 0,
            "model": effect_id,
            "speed": protocol_speed,
            "bright": brightness,
        }
    elif func == "scene_data_v2":
        # v2: inverted 1-31 + brightness
        protocol_speed = 1 + int(30 * (1.0 - speed / 100.0))
        params = {
            "model": effect_id,
            "speed": protocol_speed,
            "bright": brightness,
        }
    else:
        # Legacy scene_data: inverted 1-31, no brightness
        protocol_speed = 1 + int(30 * (1.0 - speed / 100.0))
        params = {
            "model": effect_id,
            "speed": protocol_speed,
        }

    return build_command(product_id, func, params, firmware_version)


def build_color_command(
    product_id: int,
    firmware_version: int,
    r: int,
    g: int,
    b: int,
) -> bytes | None:
    """Build a color command using the best available function.

    Args:
        product_id: Device product ID
        firmware_version: Device firmware version
        r, g, b: RGB color values 0-255

    Returns:
        Command bytes or None if no color function available
    """
    func = get_best_function(
        product_id,
        firmware_version,
        ["colour_data_v3", "colour_data_v2", "colour_data"],
    )

    if not func:
        return None

    params = {"r": r, "g": g, "b": b}
    return build_command(product_id, func, params, firmware_version)


def build_power_command(
    product_id: int,
    firmware_version: int,
    on: bool,
    delay: int = 0,
    gradient: int = 0,
) -> bytes | None:
    """Build a power on/off command.

    Args:
        product_id: Device product ID
        firmware_version: Device firmware version
        on: True for on, False for off
        delay: Transition delay (for v2+)
        gradient: Fade gradient (for v2+)

    Returns:
        Command bytes or None if no power function available
    """
    func = get_best_function(
        product_id,
        firmware_version,
        ["switch_led_v3", "switch_led_v2", "switch_led"],
    )

    if not func:
        return None

    open_val = 0x23 if on else 0x24

    if func == "switch_led_v3":
        params = {
            "preview": 0,
            "open": open_val,
            "gradient": gradient,
            "delay": delay,
        }
    elif func == "switch_led_v2":
        params = {
            "open": open_val,
            "gradient": gradient,
            "delay": delay,
        }
    else:
        # Legacy: just open
        params = {"open": open_val}

    return build_command(product_id, func, params, firmware_version)


def build_candle_command(
    product_id: int,
    firmware_version: int,
    exe_type: int,
    exe_value: int,
    speed: int,
    brightness: int,
    extent: int = 2,
) -> bytes | None:
    """Build a candle mode command.

    Args:
        product_id: Device product ID
        firmware_version: Device firmware version
        exe_type: Execution type
        exe_value: Execution value (color component)
        speed: Speed 1-31
        brightness: Brightness 1-100
        extent: Extent/range 1-3

    Returns:
        Command bytes or None if candle not supported
    """
    func = get_best_function(
        product_id,
        firmware_version,
        ["candle_data_v2", "candle_data"],
    )

    if not func:
        return None

    params = {
        "exeType": exe_type,
        "exeValue": exe_value,
        "speed": speed,
        "bright": brightness,
        "extent": extent,
    }

    if func == "candle_data_v2":
        params["preview"] = 0

    return build_command(product_id, func, params, firmware_version)


def build_music_color_command(
    product_id: int,
    firmware_version: int,
    r: int,
    g: int,
    b: int,
) -> bytes | None:
    """Build a music/reactive color command.

    This is used for sound reactive mode where colors update rapidly.

    Args:
        product_id: Device product ID
        firmware_version: Device firmware version
        r, g, b: RGB color values 0-255

    Returns:
        Command bytes or None if not supported
    """
    # music_color_data uses 0x41 prefix instead of 0x31
    template = CAPABILITIES.get_command_template(product_id, "music_color_data")
    if not template:
        return None

    params = {"r": r, "g": g, "b": b}
    return build_from_template(template, params, product_id, "music_color_data")
