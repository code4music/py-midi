import os
import yaml

CFG_FILE = os.environ.get('SF2_CFG', 'config.yaml')


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

        # Lê mapeamento MIDI do próprio config.yaml
        midi_config = self.data.get('midi', {})
        self.midi_map = {
            'cc': midi_config.get('cc_map', {}),
            'actions': midi_config.get('actions', {})
        }

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

    def next_bank(self):
        """Avança para o próximo banco (cíclico)"""
        banks = self.data.get('banks', [])
        if not banks:
            return None
        
        active = self.get_active_bank()
        bank_names = [b.get('name') for b in banks]
        
        try:
            current_idx = bank_names.index(active)
            next_idx = (current_idx + 1) % len(bank_names)
        except ValueError:
            next_idx = 0
        
        next_bank_name = bank_names[next_idx]
        self.switch_bank(next_bank_name)
        return next_bank_name

    def prev_bank(self):
        """Volta para o banco anterior (cíclico)"""
        banks = self.data.get('banks', [])
        if not banks:
            return None
        
        active = self.get_active_bank()
        bank_names = [b.get('name') for b in banks]
        
        try:
            current_idx = bank_names.index(active)
            prev_idx = (current_idx - 1) % len(bank_names)
        except ValueError:
            prev_idx = 0
        
        prev_bank_name = bank_names[prev_idx]
        self.switch_bank(prev_bank_name)
        return prev_bank_name
