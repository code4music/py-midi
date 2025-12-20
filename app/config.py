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

    def get_active_bank(self):
        """Retorna o nome do banco ativo"""
        return self.data.get('active_bank', None)

    def get_bank(self, bank_name):
        """Retorna os instrumentos de um banco específico"""
        banks = self.data.get('banks', [])
        for bank in banks:
            if bank.get('name') == bank_name:
                return bank.get('instruments', [])
        return None

    def get_active_instruments(self):
        """Retorna os instrumentos do banco ativo, ou fallback para 'instruments'"""
        active_bank = self.get_active_bank()
        if active_bank:
            instruments = self.get_bank(active_bank)
            if instruments is not None:
                return instruments

        return self.data.get('instruments', [])

    def list_banks(self):
        """Lista todos os bancos disponíveis"""
        banks = self.data.get('banks', [])
        return [{'name': b.get('name'), 'description': b.get('description', '')} for b in banks]

    def switch_bank(self, bank_name):
        """Troca o banco ativo"""
        if self.get_bank(bank_name) is not None:
            self.data['active_bank'] = bank_name
            return True
        return False
