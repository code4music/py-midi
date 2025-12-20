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
        self.open_all_ports()

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
            mapped = self.cc_map.get(str(ccnum)) or self.cc_map.get(ccnum)
            if mapped:
                if isinstance(mapped, str) and mapped in self.synth.instruments:
                    ch = self.synth.instruments[mapped]['channel']
                    self.synth.send_cc(ch, 7, value)
                    self.synth.instruments[mapped]['volume'] = value
                elif mapped == 'sustain':
                    self.synth.send_cc(channel, 64, value)
                else:
                    self.synth.send_cc(channel, ccnum, value)
            else:
                for name, inst in self.synth.instruments.items():
                    if inst.get('volume_cc') == ccnum:
                        ch = inst['channel']
                        self.synth.send_cc(ch, 7, value)
                        inst['volume'] = value
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
                # Sem sleep - latência mínima! rtmidi.get_message() já é não-bloqueante
        except KeyboardInterrupt:
            log('[midi] stopped')
