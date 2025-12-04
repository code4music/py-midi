import os
import yaml

CFG_FILE = os.environ.get('SF2_CFG', 'config.yaml')
MIDI_MAP_FILE = os.environ.get('SF2_MIDI_MAP', 'midi_map.yaml')


class Config:
    def __init__(self):
        self.data = {}
        self.midi_map = {}
        self.debug = True
        self.load()

    def load(self):
        with open(CFG_FILE, 'r', encoding='utf-8') as f:
            self.data = yaml.safe_load(f) or {}

        self.debug = bool(self.data.get('debug', False))
        self.data.setdefault('audio', {})
        self.data['audio'].setdefault('fluidsynth', {})

        if os.path.exists(MIDI_MAP_FILE):
            with open(MIDI_MAP_FILE, 'r', encoding='utf-8') as f:
                self.midi_map = yaml.safe_load(f) or {"cc": {}, "actions": {}}
        else:
            self.midi_map = {"cc": {}, "actions": {}}
