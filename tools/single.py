#!/usr/bin/env python3
import rtmidi
import fluidsynth
import time
import re
from sf2utils.sf2parse import Sf2File
import os

# ---------------- CONFIG -----------------
SF2_FILE = "sounds/organ/virtual.sf2"
NEXT_CC = 112  # CC para próximo preset
PREV_CC = 111  # CC para preset anterior
MIDI_DRIVER = "pulseaudio"

# ----------------- Carregar presets -----------------
if not os.path.exists(SF2_FILE):
    raise FileNotFoundError(f"{SF2_FILE} não encontrado")

with open(SF2_FILE, "rb") as f:
    sf2 = Sf2File(f)
    presets = []
    for preset in sf2.presets:
        s = str(preset)
        m = re.match(r"Preset\[(\d+):(\d+)\]\s*([^\d].*?)(?:\s+\d+ bag\(s\).*)?$", s)
        if m:
            bank, prog, pname = m.groups()
            presets.append({
                "bank": int(bank),
                "program": int(prog),
                "name": pname.strip()
            })

if not presets:
    raise ValueError("Nenhum preset encontrado no SF2")
print(f"[INFO] Encontrados {len(presets)} presets.")

# ----------------- Inicializar FluidSynth -----------------
fs = fluidsynth.Synth()
fs.start(driver=MIDI_DRIVER)
sfid = fs.sfload(SF2_FILE)

# ----------------- Controle de preset -----------------
current_idx = 0
def load_preset(idx):
    global current_idx
    if 0 <= idx < len(presets):
        current_idx = idx
        bank = presets[idx]["bank"]
        prog = presets[idx]["program"]
        fs.program_select(0, sfid, bank, prog)
        print(f"[INFO] Preset carregado ({idx}): {presets[idx]['name']} [{bank}:{prog}]")

load_preset(current_idx)

# ----------------- Inicializar MIDI -----------------
midi_in_list = []
midi_tmp = rtmidi.MidiIn()
ports = midi_tmp.get_ports()
print("[INFO] Portas MIDI disponíveis:", ports)

# Abre todas as portas
for i, name in enumerate(ports):
    mi = rtmidi.MidiIn()
    mi.open_port(i)
    midi_in_list.append(mi)
    print(f"[INFO] Porta MIDI aberta: {i} → {name}")

print("[INFO] Pressione teclas ou CCs (NEXT=20, PREV=21) para navegar presets. Ctrl+C para sair.")

# ----------------- Loop principal -----------------
try:
    while True:
        for midi_in in midi_in_list:
            msg = midi_in.get_message()
            if not msg:
                continue
            data, delta = msg
            status = data[0] & 0xF0
            channel = data[0] & 0x0F

            # --- Note On ---
            if status == 0x90 and data[2] > 0:
                note, vel = data[1], data[2]
                print(f"[MIDI] Note ON ch={channel} note={note} vel={vel}")
                fs.noteon(channel, note, vel)

            # --- Note Off ---
            elif status == 0x80 or (status == 0x90 and data[2] == 0):
                note = data[1]
                print(f"[MIDI] Note OFF ch={channel} note={note}")
                fs.noteoff(channel, note)

            # --- Control Change ---
            elif status == 0xB0:  # Control Change
                cc, val = data[1], data[2]
                if val > 0:  # só ao pressionar
                    if cc == NEXT_CC:
                        load_preset((current_idx + 1) % len(presets))
                    elif cc == PREV_CC:
                        load_preset((current_idx - 1) % len(presets))

            # --- Program Change (opcional) ---
            elif status == 0xC0:
                prog = data[1]
                print(f"[MIDI] Program Change ch={channel} prog={prog}")
                fs.program_change(channel, prog)

        time.sleep(0.001)

except KeyboardInterrupt:
    print("\n[INFO] Saindo…")
finally:
    fs.delete()
