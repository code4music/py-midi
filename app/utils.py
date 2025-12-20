import time
import re

GLOBAL_DEBUG = True


def log(msg):
    if GLOBAL_DEBUG:
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{ts}] {msg}")


def note_to_midi(note_str):
    """
    Converte notação musical para número MIDI.
    Exemplos: 'C4' -> 60, 'A#3' -> 58, 'Gb5' -> 78
    
    Args:
        note_str: String ou int. Se int, retorna direto. Se string, converte.
    
    Returns:
        int: Número MIDI (0-127)
    """

    if isinstance(note_str, int):
        return note_str

    note_str = str(note_str).strip().upper()
    match = re.match(r'^([A-G])([#Bb]?)(-?\d+)$', note_str)
    if not match:
        raise ValueError(f"Nota inválida: {note_str}. Use formato C4, D#3, Gb5, etc.")

    note_name, accidental, octave = match.groups()
    octave = int(octave)

    note_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
    midi_note = note_map[note_name]

    if accidental == '#':
        midi_note += 1
    elif accidental == 'B':
        midi_note -= 1
    
    midi_number = (octave + 1) * 12 + midi_note

    return max(0, min(127, midi_number))
