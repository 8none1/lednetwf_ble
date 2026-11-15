# LEDnetWF BLE - AI Assistant Instructions

## Project Overview

This is a **Home Assistant custom integration** for controlling BLE LED lights (strips, bulbs, controllers) manufactured by Zengge/Surplife/MagicHome. It works without cloud services by communicating directly over Bluetooth Low Energy.

The project involves:
1. **Reverse engineering** the Surplife/MagicHome Android app (decompiled with JADX)
2. **Documenting** the discovered protocols in `protocol_docs/`
3. **Implementing** the Home Assistant integration in `custom_components/lednetwf_ble/`

## Essential Reading

Before starting work, read the detailed context files in `ai_instructions/`:
- `CONTEXT.md` — Full project context, directory structure, decompiled app locations, common tasks
- `QUICK_REFERENCE.md` — Product ID lookup tables, command formats, state response parsing
- `DISCOVERIES.md` — Corrections log and known pitfalls (documentation errors found and fixed)
- `REQUEST_DATA_DRIVEN_ARCHITECTURE.md` — Architecture direction for data-driven device support
- `instructions_doc_review.md` — Guidelines for maintaining protocol documentation

## Key Directories

| Path | Purpose |
|------|---------|
| `custom_components/lednetwf_ble/` | Home Assistant integration code |
| `protocol_docs/` | Protocol documentation (start with `INDEX.md`) |
| `ai_instructions/` | Detailed AI context and task instructions |

## Integration Code Structure

| File | Purpose |
|------|---------|
| `const.py` | `PRODUCT_CAPABILITIES` dict — maps product_id to device capabilities |
| `protocol.py` | Command building and response parsing |
| `device.py` | `LEDNetWFDevice` class — BLE connection, state management, command methods |
| `light.py` | Home Assistant `LightEntity` integration |
| `config_flow.py` | Device discovery and setup flow |
| `capabilities.py` | Data-driven capability loading from JSON |
| `data/ble_devices.json` | Device database extracted from the Zengge app |
| `data/ble_dp_cmd.json` | Command templates extracted from the Zengge app |

## Working Practices

- **Verify against the app source.** Documentation can be wrong. Always cross-reference claims against `ble_devices.json`, `ble_dp_cmd.json`, and the decompiled Java source before confirming device behaviour. See `ai_instructions/DISCOVERIES.md` for past errors found.
- **Be direct and technical.** Show command formats in hex, provide file:line references.
- **Work in feature branches.** Do not commit directly to `main`.
- **Run the tests.** `python3 -m pytest tests -q` (CI runs the same on push/PR and before a release build, see `.github/workflows/tests.yml`).
- **Keep changes minimal.** Only modify what's needed for the task. Don't refactor surrounding code.
- **Bug reports often include log files.** Download and analyse them. Key things to look for: product_id detection, capability resolution, command sends ("Sending to"), state notifications, and the state parse conditions line.

## Decompiled App Location

The Surplife app source is at `/home/will/source/jadx/projects/surplife/`. Key paths:
- Java sources: `sources/sources/com/zengge/`
- JSON configs: `assets/flutter_assets/packages/magichome2_home_data_provide/assets/`
  - `ble_devices.json` — device capabilities per product ID
  - `wifi_dp_cmd.json` — command byte templates (e.g. `bright_value_v2`, `colour_data_v2`)
  - `wifi_device_panel.json` — UI tab configs (used for mic detection)
