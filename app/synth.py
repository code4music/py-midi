import os
import re
import time
import traceback
import fluidsynth
from sf2utils.sf2parse import Sf2File
from .utils import log


class SynthModule:
    def __init__(self, cfg):
        self.cfg = cfg
        audio = cfg.data.get('audio', {})
        driver = audio.get('driver', 'alsa')
        device = audio.get('device', None)

        log(f"[synth] starting fluidsynth driver={driver} device={device}")
        self.fs = fluidsynth.Synth()

        # apply fluidsynth settings from config
        fs_cfg = audio.get('fluidsynth', {})
        for key, value in fs_cfg.items():
            log(f"[fs.setting] {key} = {value}")
            try:
                # try to cast ints/floats if possible, otherwise pass str
                if isinstance(value, int):
                    self.fs.setting(key, int(value))
                elif isinstance(value, float):
                    self.fs.setting(key, float(value))
                else:
                    self.fs.setting(key, str(value))
            except Exception as e:
                log(f"[warn] erro aplicando setting {key}: {e}")

        started = False
        try:
            if driver == 'jack':
                log('[synth] starting with JACK')
                self.fs.start('jack')
            else:
                if device:
                    self.fs.start(driver=driver, device=device)
                else:
                    self.fs.start(driver=driver)
            started = True
            log('[synth] started')
        except Exception as e:
            log(f"[error] start failed for driver={driver}: {e}")
            traceback.print_exc()

        if not started:
            # try fallbacks
            for fallback in ('pulseaudio', None):
                try:
                    if fallback:
                        log(f"[synth] fallback to {fallback}")
                        self.fs.start(fallback)
                    else:
                        log('[synth] final fallback start()')
                        self.fs.start()
                    started = True
                    break
                except Exception:
                    pass

        if not started:
            raise RuntimeError('Could not start FluidSynth')

        self.sfid_map = {}
        self.instruments = {}
        self.load_instruments(cfg.data.get('instruments', []))

    def load_instruments(self, instruments):
        self.sfid_map.clear()
        self.instruments.clear()

        for inst in instruments:
            name = inst['name']
            sf = inst['file']
            bank = inst.get('bank', 0)
            preset = inst.get('preset', 0)
            channel = inst.get('channel', 0)
            init_vol = int(inst.get('initial_volume', 100))

            presets = self.read_presets_from_sf(sf)
            preset_name = next(
                (p['name'] for p in presets if p['preset'] == preset and p['bank'] == bank),
                "Desconhecido"
            )

            if not os.path.isabs(sf):
                sf = os.path.join(inst.get('presets_dir', '.'), sf) if inst.get('presets_dir') else sf

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
                'sf': sf,
                'channel': channel,
                'bank': bank,
                'preset': preset,
                'preset_name': preset_name,
                'volume': init_vol,
                'volume_cc': inst.get('volume_cc', 7),
                'sfid': sfid,
            }
            self.sfid_map[name] = sfid

    def note_on(self, channel, note, vel):
        t0 = time.perf_counter()
        for inst in self.instruments.values():
            ch = inst['channel']
            self.fs.noteon(ch, note, vel)
        t1 = time.perf_counter()
        log(f"[synth] NOTE ON ch={channel} note={note} vel={vel} sw-latency={(t1-t0)*1000:.3f} ms")

    def note_off(self, channel, note):
        for inst in self.instruments.values():
            ch = inst['channel']
            self.fs.noteoff(ch, note)

    def send_cc(self, channel, ccnum, value):
        self.fs.cc(channel, ccnum, value)

    def set_instrument_volume(self, name, value):
        if name not in self.instruments:
            return
        ch = self.instruments[name]['channel']
        self.fs.cc(ch, 7, int(value))
        self.instruments[name]['volume'] = int(value)

    def get_instruments_status(self):
        out = {}
        for n, v in self.instruments.items():
            out[n] = {'channel': v['channel'], 'volume': v['volume'], 'sf': v['sf']}
        return out

    def list_presets(self, name):
        """Retorna lista de presets do SF2 como dicts com bank:int, preset:int, name:str"""
        if name not in self.instruments:
            return []
        file_path = self.instruments[name]['sf']
        if not os.path.exists(file_path):
            return []

        presets = []
        with open(file_path, 'rb') as f:
            sf2 = Sf2File(f)
            for preset in sf2.presets:
                s = str(preset)
                m = re.match(r"Preset\[(\d+):(\d+)\]\s*(.*?)\s*(?:\d+ bag\(s\).*)?$", s)
                if not m:
                    continue
                bank_s, prog_s, pname = m.groups()
                try:
                    bank = int(bank_s)
                    prog = int(prog_s)
                except ValueError:
                    # fallback: ignora entrada malformada
                    continue
                presets.append({
                    "bank": bank,
                    "preset": prog,   # programa (número do preset)
                    "name": pname.strip()
                })
        return presets

    def set_preset(self, name, preset_number):
        inst = self.instruments.get(name)
        if not inst:
            return

        ch = inst["channel"]
        bank = inst.get("bank", 0)

        self.fs.program_select(ch, inst["sfid"], bank, preset_number)

    def read_presets_from_sf(self, sf_path):
        presets = []
        with open(sf_path, 'rb') as f:
            sf2 = Sf2File(f)
            for preset in sf2.presets:
                s = str(preset)
                m = re.match(r"Preset\[(\d+):(\d+)\]\s*(.*?)\s*(?:\d+ bag\(s\).*)?$", s)
                if m:
                    bank, prog, pname = m.groups()
                    presets.append({
                        'bank': int(bank),
                        'preset': int(prog),
                        'name': pname.strip()
                    })
        return presets
