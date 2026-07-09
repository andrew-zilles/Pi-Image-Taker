#!/bin/bash
# Unloads whatever setup_pulse_routing.sh created, matched by name rather than by the
# module IDs it printed (simpler to call from Python without capturing that output).
set -uo pipefail

CALL_RECORD_SINK="${1:-call_record}"

for id in $(pactl list short modules | grep -E "sink_name=${CALL_RECORD_SINK}$|sink_name=phone_out" | awk '{print $1}'); do
    pactl unload-module "$id"
done

for id in $(pactl list short modules | grep -E "module-loopback.*sink=${CALL_RECORD_SINK}" | awk '{print $1}'); do
    pactl unload-module "$id"
done
