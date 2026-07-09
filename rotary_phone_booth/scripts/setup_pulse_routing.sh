#!/bin/bash
# Builds a single mixed-audio point for both sides of the call:
#   call_record.monitor  ==  local mic  +  far-end audio (from baresip)
#
# That one source is used both for the final WAV recording and for live
# transcription, so we don't have to reconcile two separate streams later.
#
# baresip must be configured to send its playback to the "phone_out" combined
# sink created here (module aupulse, audio_player pulse,phone_out in its config)
# so the far end is heard on the real speaker AND mixed into call_record.
set -euo pipefail

MIC_SOURCE="$1"
SPEAKER_SINK="$2"
CALL_RECORD_SINK="${3:-call_record}"

pactl load-module module-null-sink sink_name="$CALL_RECORD_SINK" sink_properties=device.description="CallRecord"
pactl load-module module-combine-sink sink_name=phone_out slaves="${SPEAKER_SINK},${CALL_RECORD_SINK}"
pactl load-module module-loopback source="$MIC_SOURCE" sink="$CALL_RECORD_SINK" latency_msec=1
