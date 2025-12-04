# Py MIDI

Instalar:

```
make install
```

Eecutar:

```
make run
```

sudo sh ./install.sh

## Debug

```
aseqdump -p 20:1
```

```
fluidsynth sounds/pianos/nord-stage-4.sf2
inst 1
select 0 1 0 3
noteon 0 60 100
```

# Raspberry

/etc/systemd/system/sf2-module.service

```
[Unit]
Description=SF2 Module (FluidSynth) Service
After=network.target sound.target

[Service]
User=pi
WorkingDirectory=/home/pi/sf2-module
ExecStart=/usr/bin/python3 /home/pi/sf2-module/main.py
Restart=on-failure
LimitNOFILE=4096

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable sf2-module.service
sudo systemctl start sf2-module.service
```
