from fluidsynth import Synth
import time

fs = Synth()

print("Inicializando driver…")
fs.start(driver="pulseaudio")

sfid = fs.sfload("sounds/pianos/nord-stage-4.sf2")
print("SFID:", sfid)

fs.program_select(0, sfid, 0, 3)

print("Tocando nota…")
fs.noteon(0, 60, 120)
time.sleep(1)
fs.noteoff(0, 60)

print("Fim")
