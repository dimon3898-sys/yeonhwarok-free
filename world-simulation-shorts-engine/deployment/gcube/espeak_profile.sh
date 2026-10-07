#!/bin/sh
# Only this offline speech child uses the calibrated library/data profile.
# NVIDIA/Chromium and the system loader environment are never changed.
speech_root=/opt/world-engine/tts-offline-profile
LD_LIBRARY_PATH="$speech_root/usr/lib/x86_64-linux-gnu" \
exec "$speech_root/usr/bin/espeak-ng" \
  --path="$speech_root/usr/lib/x86_64-linux-gnu/espeak-ng-data" "$@"
