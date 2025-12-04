#!/usr/bin/env bash
set -e

# atualizar
apt update
apt install -y build-essential python3-dev python3-pip \
 libfluidsynth2 fluidsynth \
 portaudio19-dev libasound2-dev

# opcional (jack)
apt install -y jackd2

apt install python3-rtmidi


# instalar pip packages
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

echo "Instalação completa. Coloque seus .sf2 em ./sounds/ e edite config.yaml"
