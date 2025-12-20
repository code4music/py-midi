import rtmidi
import time
from .utils import log


class MidiBridge:
    def __init__(self, cfg, synth):
        self.cfg = cfg
        self.synth = synth
        self.midi_ports = []
        self.cc_map = cfg.midi_map.get('cc', {})
        self.actions = cfg.midi_map.get('actions', {})
        self.midi_learn_mode = cfg.data.get('midi_learn_mode', False)
        self.cc_seen = {}  # Rastreia quais CCs foram vistos
        self.open_all_ports()

    def _check_actions(self, ccnum, value):
        """Verifica e executa ações MIDI configuradas (botões)"""
        for action_name, action_cfg in self.actions.items():
            if isinstance(action_cfg, dict):
                if action_cfg.get('cc') == ccnum:
                    # Verifica se há um valor específico requerido
                    required_value = action_cfg.get('value')
                    if required_value is not None and value != required_value:
                        continue
                    
                    # Executar ação
                    if action_name == 'next_bank':
                        bank = self.synth.next_bank()
                        if bank:
                            log(f"[midi] ⏭️  Avançar banco -> {bank}")
                        return True
                    elif action_name == 'prev_bank':
                        bank = self.synth.prev_bank()
                        if bank:
                            log(f"[midi] ⏮️  Voltar banco -> {bank}")
                        return True
                    elif action_name == 'panic':
                        self.synth.panic()
                        log(f"[midi] 🚨 PANIC! Todos os sons parados")
                        return True
                    elif action_name == 'reload_config':
                        log(f"[midi] 🔄 Recarregando configuração...")
                        # Esta ação já deve ser tratada no main.py
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
                selected.append(mi)

        if not selected:
            for i, name in enumerate(ports):
                log(f"[midi] fallback abrindo {i}: {name}")
                mi = rtmidi.MidiIn()
                mi.open_port(i)
                selected.append(mi)

        self.midi_ports = selected

    def _handle_message(self, data, delta):
        status = data[0] & 0xF0
        channel = data[0] & 0x0F

        if status == 0x90 and data[2] > 0:
            self.synth.note_on(channel, data[1], data[2])
        elif status == 0x80 or (status == 0x90 and data[2] == 0):
            self.synth.note_off(channel, data[1])
        elif status == 0xB0:
            ccnum, value = data[1], data[2]
            
            # Verificar ações antes de processar como CC normal
            action_triggered = self._check_actions(ccnum, value)
            if action_triggered:
                return
            
            # Modo de descoberta MIDI - destaca novos controles
            if self.midi_learn_mode:
                if ccnum not in self.cc_seen:
                    log(f"[midi] 🎛️  NOVO CONTROLE DETECTADO! CC#{ccnum}")
                    log(f"[midi] 📝 Adicione no config.yaml como volume_cc do instrumento")
                    self.cc_seen[ccnum] = True
                log(f"[midi] 🎚️  CC#{ccnum} = {value} (Canal {channel})")
            else:
                log(f"[midi] CC recebido - Canal: {channel}, CC#: {ccnum}, Valor: {value}")
            
            # Prioridade 1: Verificar se algum instrumento usa este CC para volume
            volume_handled = False
            for name, inst in self.synth.instruments.items():
                if inst.get('volume_cc') == ccnum:
                    ch = inst['channel']
                    self.synth.send_cc(ch, 7, value)
                    inst['volume'] = value
                    log(f"[midi] 🎚️  Volume '{name}' (canal {ch}) = {value}")
                    volume_handled = True
                    break
            
            if volume_handled:
                pass  # Já processado
            else:
                # Prioridade 2: Verificar mapeamento especial no cc_map
                mapped = self.cc_map.get(str(ccnum)) or self.cc_map.get(ccnum)
                if mapped:
                    log(f"[midi] CC#{ccnum} mapeado para: {mapped}")
                    if isinstance(mapped, str) and mapped in self.synth.instruments:
                        ch = self.synth.instruments[mapped]['channel']
                        self.synth.send_cc(ch, 7, value)
                        self.synth.instruments[mapped]['volume'] = value
                        log(f"[midi] Volume do instrumento '{mapped}' (canal {ch}) ajustado para {value}")
                    elif mapped == 'sustain':
                        # Envia sustain para todos os instrumentos que têm use_sustain: true
                        count = 0
                        for name, inst in self.synth.instruments.items():
                            if inst.get('use_sustain', False):
                                ch = inst['channel']
                                self.synth.send_cc(ch, 64, value)
                                count += 1
                        if count > 0:
                            log(f"[midi] 🎹 Sustain = {value} ({count} instrumentos)")
                        else:
                            log(f"[midi] ⚠️ Sustain recebido mas nenhum instrumento configurado com use_sustain: true")
                    else:
                        self.synth.send_cc(channel, ccnum, value)
                        log(f"[midi] CC passthrough: canal {channel}, CC#{ccnum} = {value}")
                else:
                    log(f"[midi] ⚠️ CC#{ccnum} não mapeado")
                    log(f"[midi] 💡 Configure volume_cc: {ccnum} no instrumento desejado")
        elif status == 0xC0:
            self.synth.fs.program_change(channel, data[1])

    def process(self):
        log('[midi] Loop MIDI polling ports...')
        try:
            while True:
                for midi in self.midi_ports:
                    msg = midi.get_message()
                    if not msg:
                        continue
                    data, delta = msg
                    self._handle_message(data, delta)
        except KeyboardInterrupt:
            log('[midi] stopped')
