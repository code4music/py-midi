import rtmidi
import threading
from .utils import log


class MidiBridge:
    def __init__(self, cfg, synth):
        self.cfg = cfg
        self.synth = synth
        self.midi_ports = []
        self.cc_map = cfg.midi_map.get('cc', {})
        self.actions = cfg.midi_map.get('actions', {})
        self.midi_learn_mode = cfg.data.get('midi_learn_mode', False)
        self.cc_seen = {}
        self._stop_event = threading.Event()
        self._build_instrument_lookups()
        self.open_all_ports()

    def _build_instrument_lookups(self):
        """Pre-build lookup dicts para evitar iteração O(N) no hot path."""
        self._cc_to_instrument = {}
        self._sustain_channels = []

        for name, inst in self.synth.instruments.items():
            vcc = inst.get('volume_cc')
            if vcc is not None:
                self._cc_to_instrument[vcc] = (name, inst)
            if inst.get('use_sustain', False):
                self._sustain_channels.append(inst['channel'])

    def rebuild_lookups(self):
        """Rebuilda lookups após bank switch ou reload de config."""
        self._build_instrument_lookups()

    def _check_actions(self, ccnum, value):
        """Verifica e executa ações MIDI configuradas (botões)"""
        for action_name, action_cfg in self.actions.items():
            if isinstance(action_cfg, dict):
                if action_cfg.get('cc') == ccnum:
                    required_value = action_cfg.get('value')
                    if required_value is not None and value != required_value:
                        continue

                    if action_name == 'next_bank':
                        bank = self.synth.next_bank()
                        if bank:
                            self.rebuild_lookups()
                            log(f"[midi] Avançar banco -> {bank}")
                        return True
                    elif action_name == 'prev_bank':
                        bank = self.synth.prev_bank()
                        if bank:
                            self.rebuild_lookups()
                            log(f"[midi] Voltar banco -> {bank}")
                        return True
                    elif action_name == 'panic':
                        self.synth.panic()
                        log(f"[midi] PANIC! Todos os sons parados")
                        return True
                    elif action_name == 'reload_config':
                        log(f"[midi] Recarregando configuração...")
                        return True
        return False

    def open_all_ports(self):
        tmp = rtmidi.MidiIn()
        ports = tmp.get_ports()
        log(f"[midi] portas disponíveis: {ports}")

        control_tags = ['midi2', 'ctrl', 'control', 'port-1', 'port1']
        note_tags = ['midi1', 'key', 'keyboard']

        selected = []
        for i, name in enumerate(ports):
            lname = name.lower()
            if any(t in lname for t in control_tags + note_tags):
                log(f"[midi] abrindo porta: {i} -> {name}")
                mi = rtmidi.MidiIn()
                mi.open_port(i)
                mi.set_callback(self._midi_callback)
                selected.append(mi)

        if not selected:
            for i, name in enumerate(ports):
                log(f"[midi] fallback abrindo {i}: {name}")
                mi = rtmidi.MidiIn()
                mi.open_port(i)
                mi.set_callback(self._midi_callback)
                selected.append(mi)

        self.midi_ports = selected

    def _midi_callback(self, message, data=None):
        """Callback chamado pela thread interna do rtmidi quando há dados MIDI."""
        try:
            msg_data, delta = message
            self._handle_message(msg_data, delta)
        except Exception as e:
            log(f"[midi] erro no callback: {e}")

    def _handle_message(self, data, delta):
        status = data[0] & 0xF0
        channel = data[0] & 0x0F

        if status == 0x90 and data[2] > 0:
            self.synth.note_on(channel, data[1], data[2])
        elif status == 0x80 or (status == 0x90 and data[2] == 0):
            self.synth.note_off(channel, data[1])
        elif status == 0xB0:
            ccnum, value = data[1], data[2]

            action_triggered = self._check_actions(ccnum, value)
            if action_triggered:
                return

            if self.midi_learn_mode:
                if ccnum not in self.cc_seen:
                    log(f"[midi] NOVO CONTROLE DETECTADO! CC#{ccnum}")
                    self.cc_seen[ccnum] = True
                if self.cfg.debug:
                    log(f"[midi] CC#{ccnum} = {value} (Canal {channel})")

            # Prioridade 1: lookup direto por CC -> instrumento (O(1))
            entry = self._cc_to_instrument.get(ccnum)
            if entry:
                name, inst = entry
                ch = inst['channel']
                self.synth.send_cc(ch, 7, value)
                inst['volume'] = value
                if self.cfg.debug:
                    log(f"[midi] Volume '{name}' (canal {ch}) = {value}")
            else:
                # Prioridade 2: mapeamento especial no cc_map
                mapped = self.cc_map.get(str(ccnum)) or self.cc_map.get(ccnum)
                if mapped:
                    if isinstance(mapped, str) and mapped in self.synth.instruments:
                        ch = self.synth.instruments[mapped]['channel']
                        self.synth.send_cc(ch, 7, value)
                        self.synth.instruments[mapped]['volume'] = value
                        if self.cfg.debug:
                            log(f"[midi] Volume '{mapped}' (canal {ch}) = {value}")
                    elif mapped == 'sustain':
                        for ch in self._sustain_channels:
                            self.synth.send_cc(ch, 64, value)
                    else:
                        self.synth.send_cc(channel, ccnum, value)
                elif self.cfg.debug:
                    log(f"[midi] CC#{ccnum} não mapeado")
        elif status == 0xC0:
            self.synth.fs.program_change(channel, data[1])

    def process(self):
        """Bloqueia a thread principal. O MIDI é processado via callbacks."""
        log('[midi] MIDI callback mode active')
        try:
            self._stop_event.wait()
        except KeyboardInterrupt:
            log('[midi] stopped')
