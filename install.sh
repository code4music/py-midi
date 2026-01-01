#!/usr/bin/env bash
set -e

apt update

apt install -y \
  build-essential \
  make \
  python3-dev \
  python3-pip \
  python3-rtmidi \
  fluidsynth \
  portaudio19-dev \
  libasound2-dev
