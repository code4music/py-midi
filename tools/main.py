#!/usr/bin/env python3

import time
import yaml
import threading
import os
import re
import fluidsynth
import rtmidi
from flask import Flask, jsonify, request
from sf2utils.sf2parse import Sf2File
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

CFG_FILE = "config.yaml"
MIDI_MAP_FILE = "midi_map.yaml"

GLOBAL_DEBUG = True

# ---------------- LOG -----------------
def log(msg):
    if GLOBAL_DEBUG:
        print(msg)

# ---------------- CONFIG -----------------
class Config:
    def __init__(self):
        self.data = {}
        self.midi_map = {}
        self.debug = True
        self.load()

    def load(self):
        with open(CFG_FILE, "r", encoding="utf-8") as f:
            self.data = yaml.safe_load(f)

        self.debug = self.data.get("debug", False)
        self.data.setdefault("audio", {})
        self.data["audio"].setdefault("fluidsynth", {})

        if os.path.exists(MIDI_MAP_FILE):
            with open(MIDI_MAP_FILE, "r", encoding="utf-8") as f:
                self.midi_map = yaml.safe_load(f)
        else:
            self.midi_map = {"cc": {}, "actions": {}}


class ConfigWatcher(FileSystemEventHandler):
    def __init__(self, callback):
        self.callback = callback

    def on_modified(self, event):
        if event.src_path.endswith(CFG_FILE) or event.src_path.endswith(MIDI_MAP_FILE):
            log("Config changed on disk; reloading...")
            self.callback()


# ---------------- SYNTH MODULE -----------------
class SynthModule:
    def __init__(self, cfg: Config):
        self.cfg = cfg

        audio = cfg.data.get("audio", {})
        driver = audio.get("driver", "alsa")
        device = audio.get("device", "default")

        log(f"[synth] starting fluidsynth driver={driver} device={device}")
        self.fs = fluidsynth.Synth()

        FS_FLOAT_PARAMS = {
            "synth.gain",
            "synth.overflow-percentage",
        }

        FS_INT_PARAMS = {
            "audio.period-size",
            "audio.periods",
            "synth.polyphony",
            "synth.chorus.active",
            "synth.reverb.active",
        }

        fs_cfg = audio.get("fluidsynth", {})

        for key, value in fs_cfg.items():
            log(f"[fs.setting] {key} = {value}")

            try:
                if key in FS_FLOAT_PARAMS:
                    self.fs.setting(key, float(value))
                elif key in FS_INT_PARAMS:
                    self.fs.setting(key, int(value))
                else:
                    # fallback
                    self.fs.setting(key, value)
            except Exception as e:
                print(f"[warn] erro aplicando setting {key}: {e}")

        try:
            if device:
                self.fs.start(driver=driver, device=device)
            else:
                self.fs.start(driver=driver)
        except Exception:
            print("Error starting synth with device; fallback default")
            self.fs.start()

        self.sfid_map = {}
        self.instruments = {}
        self.load_instruments(cfg.data.get("instruments", []))

    def load_instruments(self, instruments):
        self.sfid_map.clear()
        self.instruments.clear()

        for inst in instruments:
            name = inst["name"]
            sf = inst["file"]
            bank = inst.get("bank", 0)
            preset = inst.get("preset", 0)
            channel = inst.get("channel", 0)
            init_vol = int(inst.get("initial_volume", 100))

            if not os.path.isabs(sf):
                sf = os.path.join(inst.get("presets_dir", "."), sf) if inst.get("presets_dir") else sf

            if not os.path.exists(sf):
                if os.path.exists(os.path.join(os.getcwd(), sf)):
                    sf = os.path.join(os.getcwd(), sf)
                else:
                    log(f"[warn] soundfont {sf} not found, skipping")
                    continue

            log(f"[synth] loading {name} -> {sf} (channel {channel})")
            sfid = self.fs.sfload(sf)

            self.fs.program_select(channel, sfid, bank, preset)
            self.fs.cc(channel, 7, init_vol)

            self.instruments[name] = {
                "sf": sf,
                "channel": channel,
                "bank": bank,
                "preset": preset,
                "volume": init_vol,
                "volume_cc": inst.get("volume_cc", 7)
            }
            self.sfid_map[name] = sfid

    def note_on(self, channel, note, vel):
        t_start = time.perf_counter()   # ⏱️ antes de enviar o comando

        for inst in self.instruments.values():
            ch = inst["channel"]
            self.fs.noteon(ch, note, vel)

        t_end = time.perf_counter()     # ⏱️ depois que o Synth recebeu o comando

        latency_ms = (t_end - t_start) * 1000

        log(f"[synth] NOTE ON  ch={channel} note={note} vel={vel} latency={latency_ms:.3f} ms")

    def note_off(self, channel, note):
        log(f"[synth] NOTE OFF ch={channel} note={note}")
        for inst in self.instruments.values():
            ch = inst["channel"]
            self.fs.noteoff(ch, note)

    def send_cc(self, channel, ccnum, value):
        log(f"[synth] CC ch={channel} cc={ccnum} val={value}")
        self.fs.cc(channel, ccnum, value)

    def set_instrument_volume(self, name, value):
        if name not in self.instruments:
            return
        ch = self.instruments[name]["channel"]
        self.fs.cc(ch, 7, int(value))
        self.instruments[name]["volume"] = int(value)

    def get_instruments_status(self):
        out = {}
        for n, v in self.instruments.items():
            out[n] = {"channel": v["channel"], "volume": v["volume"], "sf": v["sf"]}
        return out

    def reload(self, new_cfg):
        self.load_instruments(new_cfg.get("instruments", []))


# ---------------- MIDI BRIDGE -----------------
class MidiBridge:
    def __init__(self, cfg: Config, synth: SynthModule):
        self.cfg = cfg
        self.synth = synth

        log("[midi] Inicializando múltiplas portas MIDI...")
        self.midi_ports = []
        self.open_all_ports()

        self.cc_map = cfg.midi_map.get("cc", {})
        self.actions = cfg.midi_map.get("actions", {})

    def open_all_ports(self):
        tmp = rtmidi.MidiIn()
        ports = tmp.get_ports()

        log(f"[midi] portas disponíveis: {ports}")

        control_tags = ["midi2", "ctrl", "control", "port-1", "port1"]
        note_tags = ["midi1", "key", "keyboard"]

        selected = []

        for i, name in enumerate(ports):
            lname = name.lower()
            if any(t in lname for t in control_tags + note_tags):
                log(f"[midi] abrindo porta: {i} → {name}")
                mi = rtmidi.MidiIn()
                mi.open_port(i)
                selected.append(mi)

        if not selected:
            for i, name in enumerate(ports):
                log(f"[midi] fallback → abrindo {i}: {name}")
                mi = rtmidi.MidiIn()
                mi.open_port(i)
                selected.append(mi)

        self.midi_ports = selected

    def process(self):
        log("[midi] Loop MIDI rodando (múltiplas portas).")

        while True:
            for midi in self.midi_ports:
                msg = midi.get_message()
                if not msg:
                    continue

                data, delta = msg
                status = data[0] & 0xF0
                channel = data[0] & 0x0F

                if status == 0x90 and data[2] > 0:
                    self.synth.note_on(channel, data[1], data[2])

                elif status == 0x80 or (status == 0x90 and data[2] == 0):
                    self.synth.note_off(channel, data[1])

                elif status == 0xB0:
                    ccnum = data[1]
                    value = data[2]

                    if ccnum == 46:
                        gain = (value / 127)
                        self.synth.fs.setting("synth.gain", gain)
                        log(f"[MASTER] gain={gain:.2f}")
                        continue

                    mapped = self.cc_map.get(str(ccnum)) or self.cc_map.get(ccnum)

                    if mapped:
                        if isinstance(mapped, str) and mapped in self.synth.instruments:
                            ch = self.synth.instruments[mapped]["channel"]
                            self.synth.send_cc(ch, 7, value)
                            self.synth.instruments[mapped]["volume"] = value
                        elif mapped == "sustain":
                            self.synth.send_cc(channel, 64, value)
                        else:
                            self.synth.send_cc(channel, ccnum, value)
                    else:
                        for name, inst in self.synth.instruments.items():
                            if inst.get("volume_cc") == ccnum:
                                ch = inst["channel"]
                                self.synth.send_cc(ch, 7, value)
                                inst["volume"] = value

                elif status == 0xC0:
                    self.synth.fs.program_change(channel, data[1])


# ---------------- HTTP UI -----------------
def run_http_app(synth: SynthModule, host="0.0.0.0", port=5000):
    app = Flask("sf2-module")

    @app.route("/status")
    def status():
        return jsonify(synth.get_instruments_status())

    @app.route("/instruments")
    def instruments():
        out = {}

        for name, inst in synth.instruments.items():
            file_path = inst["sf"]

            if not os.path.isabs(file_path):
                file_path = os.path.join(os.getcwd(), file_path)

            if not os.path.exists(file_path):
                out[name] = {"error": "file not found"}
                continue

            try:
                with open(file_path, "rb") as f:
                    sf2 = Sf2File(f)
                    presets_list = []

                    for preset in sf2.presets:
                        s = str(preset)
                        m = re.match(r"Preset\[(\d+):(\d+)\]\s*([^\d].*?)(?:\s+\d+ bag\(s\).*)?$", s)
                        if m:
                            bank, prog, pname = m.groups()
                            presets_list.append({
                                "bank": bank,
                                "preset": prog,
                                "name": pname.strip()
                            })

                out[name] = {
                    "file": inst["sf"],
                    "channel": inst.get("channel", 0),
                    "bank": inst.get("bank", 0),
                    "presets": presets_list
                }
            except Exception as e:
                out[name] = {"error": str(e)}

        return jsonify(out)

    @app.route("/set_volume", methods=["POST"])
    def set_volume():
        payload = request.json or {}
        name = payload.get("name")
        value = payload.get("value")
        synth.set_instrument_volume(name, int(value))
        return jsonify({"ok": True})

    app.run(host=host, port=port, debug=False, use_reloader=False)


# ---------------- MAIN -----------------
def main():
    global GLOBAL_DEBUG

    cfg = Config()
    GLOBAL_DEBUG = cfg.debug

    synth = SynthModule(cfg)
    midi = MidiBridge(cfg, synth)

    if cfg.data.get("reload_on_change", True):
        watcher = ConfigWatcher(lambda: reload_configs(cfg, synth, midi))
        obs = Observer()
        obs.schedule(watcher, ".", recursive=False)
        obs.start()

    http_cfg = cfg.data.get("http", {})
    if http_cfg.get("enabled", False):
        threading.Thread(
            target=run_http_app,
            args=(synth, http_cfg.get("host", "0.0.0.0"), http_cfg.get("port", 5000)),
            daemon=True
        ).start()

    try:
        midi.process()
    except KeyboardInterrupt:
        print("Exiting…")


def reload_configs(cfg, synth, midi):
    try:
        cfg.load()
        synth.reload(cfg.data)
        midi.cc_map = cfg.midi_map.get("cc", {})
        midi.actions = cfg.midi_map.get("actions", {})

        global GLOBAL_DEBUG
        GLOBAL_DEBUG = cfg.debug

        log("[reload] configs reloaded")
    except Exception as e:
        print("[reload] error:", e)


if __name__ == "__main__":
    main()
