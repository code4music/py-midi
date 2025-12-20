import os
import re
import time
import traceback
import fluidsynth
from sf2utils.sf2parse import Sf2File
from .utils import log
from .utils import note_to_midi


class SynthModule:
    def __init__(self, cfg):
        self.cfg = cfg
        audio = cfg.data.get('audio', {})
        driver = audio.get('driver', 'alsa')
        device = audio.get('device', None)

        log(f"[synth] starting fluidsynth driver={driver} device={device}")
        self.fs = fluidsynth.Synth()

        fs_cfg = audio.get('fluidsynth', {})
        for key, value in fs_cfg.items():
            log(f"[fs.setting] {key} = {value}")
            try:
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

        self.sfid_cache = {}
        self.preset_cache = {}
        self.sfid_map = {}
        self.instruments = {}
        
        log('[synth] pre-loading all soundfonts from all banks...')
        self._preload_all_soundfonts()
        self._activate_bank_instruments(cfg.get_active_instruments())

    def _preload_all_soundfonts(self):
        """Carrega todos os soundfonts de todos os bancos (cache)"""
        banks = self.cfg.data.get('banks', [])
        
        for bank in banks:
            instruments = bank.get('instruments', [])
            for inst in instruments:
                sf = inst['file']

                if not os.path.isabs(sf):
                    sf = os.path.join(inst.get('presets_dir', '.'), sf) if inst.get('presets_dir') else sf
                if not os.path.exists(sf):
                    if os.path.exists(os.path.join(os.getcwd(), sf)):
                        sf = os.path.join(os.getcwd(), sf)
                    else:
                        log(f"[warn] soundfont {sf} not found, skipping")
                        continue

                if sf not in self.sfid_cache:
                    log(f"[synth] loading soundfont: {sf}")
                    sfid = self.fs.sfload(sf)
                    self.sfid_cache[sf] = sfid
                    self.preset_cache[sf] = self.read_presets_from_sf(sf)
        
        log(f'[synth] pre-loaded {len(self.sfid_cache)} soundfonts')

    def _activate_bank_instruments(self, instruments):
        """Ativa instrumentos do banco sem recarregar soundfonts"""
        self.instruments.clear()
        self.sfid_map.clear()
        
        for inst in instruments:
            name = inst['name']
            sf = inst['file']
            bank = inst.get('bank', 0)
            preset = inst.get('preset', 0)
            channel = inst.get('channel', 0)
            init_vol = int(inst.get('initial_volume', 100))
            
            if not os.path.isabs(sf):
                sf = os.path.join(inst.get('presets_dir', '.'), sf) if inst.get('presets_dir') else sf
            if not os.path.exists(sf):
                if os.path.exists(os.path.join(os.getcwd(), sf)):
                    sf = os.path.join(os.getcwd(), sf)
            
            sfid = self.sfid_cache.get(sf)
            if sfid is None:
                log(f"[warn] soundfont {sf} not in cache, skipping {name}")
                continue
            
            presets = self.preset_cache.get(sf, [])
            preset_name = next(
                (p['name'] for p in presets if p['preset'] == preset and p['bank'] == bank),
                "Desconhecido"
            )
            
            log(f"[synth] activating {name} on channel {channel}")
            
            self.fs.program_select(channel, sfid, bank, preset)
            self.fs.cc(channel, 7, init_vol)
            
            self.instruments[name] = {
                'sf': sf,
                'channel': channel,
                'bank': bank,
                'preset': preset,
                'preset_name': preset_name,
                'volume': init_vol,
                'volume_cc': inst.get('volume_cc', 127),
                'use_sustain': inst.get('use_sustain', True),
                'sfid': sfid,
                'min_note': note_to_midi(inst.get('min_note', 0)),
                'max_note': note_to_midi(inst.get('max_note', 127)),
            }
            self.sfid_map[name] = sfid

    def reload(self, config_data):
        """Recarrega instrumentos quando a configuração muda"""
        log('[synth] reloading instruments...')
        self._preload_all_soundfonts()
        self._activate_bank_instruments(self.cfg.get_active_instruments())
        log('[synth] instruments reloaded')

    def switch_bank(self, bank_name):
        """Troca para outro banco de instrumentos (instantâneo!)"""
        if self.cfg.switch_bank(bank_name):
            log(f'[synth] switching to bank: {bank_name}')
            self._activate_bank_instruments(self.cfg.get_active_instruments())
            log(f'[synth] bank switched: {bank_name}')
            return True
        else:
            log(f'[synth] bank not found: {bank_name}')
            return False

    def load_instruments(self, instruments):
        """Legacy method - redireciona para _activate_bank_instruments"""
        self._activate_bank_instruments(instruments)

    def note_on(self, channel, note, vel):
        t0 = time.perf_counter()
        for inst in self.instruments.values():
            if inst['volume'] > 0:
                if inst['min_note'] <= note <= inst['max_note']:
                    ch = inst['channel']
                    self.fs.noteon(ch, note, vel)
        t1 = time.perf_counter()
        if self.cfg.debug:
            log(f"[synth] NOTE ON ch={channel} note={note} vel={vel} sw-latency={(t1-t0)*1000:.3f} ms")

    def note_off(self, channel, note):
        for inst in self.instruments.values():
            if inst['volume'] > 0:
                if inst['min_note'] <= note <= inst['max_note']:
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

    def panic(self):
        """Para TODOS os sons imediatamente (All Notes Off + All Sound Off)"""
        log('[synth] PANIC! Stopping all sounds...')
        for channel in range(16):
            self.fs.cc(channel, 123, 0)
            self.fs.cc(channel, 120, 0)
        log('[synth] All sounds stopped')

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
        if file_path in self.preset_cache:
            return self.preset_cache[file_path]

        if not os.path.exists(file_path):
            return []

        presets = self.read_presets_from_sf(file_path)
        self.preset_cache[file_path] = presets
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
