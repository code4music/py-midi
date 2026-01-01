#!/usr/bin/env bash
set -e

apt update

apt install -y build-essential python3-dev python3-pip \
 fluidsynth portaudio19-dev libasound2-dev python3-rtmidi

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "Instalação completa. Coloque seus .sf2 em ./sounds/ e edite config.yaml"
