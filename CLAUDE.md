# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

py-midi is a Python-based MIDI synthesizer controller that bridges MIDI input devices to FluidSynth for software synthesis. It targets both desktop development and headless Raspberry Pi deployment for live performance. The project includes a Flask web UI for instrument management.

## Commands

```bash
make install          # Create venv + install dependencies
make run              # Run the app (.venv/bin/python -m app.main)
make run-realtime     # Run with nice -n -19 for low-latency
make lint             # flake8 on app/
make clean            # Remove __pycache__ and .pyc files
make reset            # clean + remove .venv
```

Config file path can be overridden with `SF2_CFG` env variable (default: `config.yaml`).

There is no automated test suite. Manual test tools live in `tools/`.

## Architecture

The app is a single-process system with a polling MIDI loop on the main thread and an optional Flask web server on a daemon thread.

**Data flow:** MIDI Device → `MidiBridge` (polls ports) → message dispatch → `SynthModule` → FluidSynth C library

### Core modules (all in `app/`)

- **main.py** — Entry point. Wires Config, SynthModule, MidiBridge, and optionally the Flask web UI + watchdog config file observer.
- **config.py** — Loads `config.yaml` (YAML). Manages bank definitions, active bank state, and MIDI CC/action mappings. `Config.get_active_instruments()` resolves the current instrument list.
- **synth.py** — `SynthModule` wraps pyfluidsynth. Pre-loads all soundfonts from all banks into a cache (`sfid_cache`) at startup so bank switching is instant (no disk I/O). Handles note routing with per-instrument volume gating, note range filtering (`min_note`/`max_note`), and sustain support.
- **midi.py** — `MidiBridge` opens MIDI input ports (auto-detects by name tags like "midi1", "ctrl", "keyboard"). Parses raw MIDI bytes and dispatches: notes → synth, CC → volume/sustain/action mapping, program change → FluidSynth.
- **webui.py** — Flask app with routes for bank switching, preset selection, volume control, and panic.
- **utils.py** — Logging helper and `note_to_midi()` (converts "C4" → 60).

### Key design decisions

- **Soundfont pre-caching:** All SF2 files across all banks are loaded once at startup. Bank switching only re-selects programs, never reloads files.
- **CC priority chain:** instrument `volume_cc` match → global `cc_map` mapping → unmapped warning.
- **MIDI learn mode:** When `midi_learn_mode: true` in config, unknown CCs are highlighted in logs for discovery.
- **Config hot-reload:** watchdog monitors `config.yaml` changes and triggers full instrument reload without restart.

## Configuration

`config.yaml` is the central config file. Key sections:
- `audio` — FluidSynth driver/device and engine settings
- `midi` — CC mappings (`cc_map`), action bindings (`actions` for next_bank, prev_bank, panic, reload_config)
- `banks` — List of named instrument banks, each with instruments defining soundfont file, MIDI channel, bank/preset, volume CC, note range
- `active_bank` — Currently selected bank name
- `http` — Web UI enable/host/port

## Dependencies

Requires system packages: `fluidsynth`, `libasound2-dev`, `portaudio19-dev` (install via `sudo sh ./install.sh`).

Python deps: pyfluidsynth, python-rtmidi, PyYAML, Flask, watchdog.

## Conventions

- Code uses English for identifiers; comments and log messages are in Portuguese
- Commit messages follow `type: message` format (e.g., `refactor:`, `chore:`, `feat:`)
- Soundfont files (`.sf2`) go in `sounds/` subdirectories and are git-ignored
