# Rotary Phone Genealogy Booth

Turns a Western Electric Model 554 rotary phone into a walk-up "story booth":
lift the handset, dial a real phone number, talk over the internet, hang up --
the call is recorded, transcribed, and emailed automatically.

## How it works

1. **Hookswitch** and **rotary dial** are wired to Pi GPIO pins through
   opto-isolators (see Hardware Modification below).
2. Lifting the handset starts digit collection. Once a full number is dialed,
   `rotary_phone/sip_client.py` spawns `baresip` to place the call over a SIP
   trunk that can terminate to real phone numbers (so you can dial your Google
   Fi number, or anyone else's, like a normal phone call).
3. Once answered, PulseAudio routing (`scripts/setup_pulse_routing.sh`) mixes
   the local mic and far-end audio into one source, which is simultaneously
   recorded (`rotary_phone/recorder.py`) and transcribed live
   (`rotary_phone/transcriber.py`, using local/free `faster-whisper` with
   VAD-based segmentation -- expect a few seconds of lag per sentence, not
   sub-second latency, since this runs free and local on the Pi rather than a
   paid cloud streaming API).
4. Hanging up tears everything down and emails the WAV + transcript to the
   configured recipient (`rotary_phone/mailer.py`), automatically, every time.

The state machine that ties all of this together is
`rotary_phone/controller.py`.

## Software setup

```
sudo apt install baresip pulseaudio ffmpeg python3-venv
cd rotary_phone_booth
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.local.yaml   # then edit it
```

Fill in `config.local.yaml`:
- `audio.mic_source` / `audio.speaker_sink`: find with `pactl list short sources`
  / `pactl list short sinks` once your USB sound card is attached.
- `sip.destination_uri_template`: your SIP trunk provider's SIP domain.
- `email.recipient` / `email.smtp_user`.

Set up baresip itself (`scripts/baresip_accounts.example` has the account line
and the `audio_player`/`audio_source` config needed so calls flow through
PulseAudio). You'll need a SIP trunk account from a provider that terminates
calls to real phone numbers (e.g. Telnyx, VoIP.ms, Flowroute) -- Google Fi
doesn't provide SIP trunking itself, but that's fine, your Fi number is just
the destination you dial, exactly as if calling it from any other phone.

Export your Gmail app password (not your login password --
https://myaccount.google.com/apppasswords) and run:

```
export SMTP_APP_PASSWORD=xxxx
python main.py
```

For always-on operation, install `systemd/rotary-phone-booth.service` (see
comments in that file for the `smtp.env` it expects).

### Tuning notes

- `sip_client.py`'s `ANSWERED_MARKERS`/`ENDED_MARKERS` match common baresip log
  wording, but it varies between versions. Run
  `baresip -f <config_dir> -v -e "/dial sip:..."` by hand once, watch what your
  installed version prints on answer/hangup, and adjust those constants if
  calls aren't being detected.
- `transcription.model_size`: `tiny.en`/`base.en` keep up better on Pi-class
  CPUs; `small.en` is more accurate but may lag further behind if your Pi is
  slower than a Pi 4.

## Hardware modification: Western Electric Model 554

The 554 was built to be hardwired into the POTS network, not modular, so this
is a full rewire, not a plug-in job. Read fully before cutting anything.

### 1. Open it up

Remove the handset. Underneath, near the dial, are two case screws -- remove
them and lift the shell off the base plate. You'll see the dial assembly, the
ringer (two large bell coils + clapper), the network box (induction coil,
capacitor, varistor), and a terminal block where the line cord and internal
components land.

### 2. Disconnect from the phone network entirely

Unscrew/desolder the line cord from the terminal block. This phone will never
be plugged into real POTS again -- it's being repurposed to talk to the Pi
only. Leaving the old network box connected is harmless if you want to keep
the phone's original tinkling-bell sidetone behavior, but it's not needed for
this project and simplifies wiring to remove it.

### 3. Tap the hookswitch

The switchhook is the plunger mechanism the handset weight depresses. Trace
its two leads with a multimeter in continuity mode: they should short when the
handset is lifted (or open, depending on how it's wired in this phone --
verify with the meter rather than assuming). **Do not wire this directly to a
GPIO pin.** Route both leads into an opto-isolator (e.g. PC817) input side;
wire the isolator's output side (with a pull-up resistor to 3.3V) to a GPIO
pin. This protects the Pi if the switch mechanism ever sees a stray voltage,
and it's cheap insurance for a 70-year-old mechanical part you can't fully
characterize by inspection alone.

### 4. Tap the rotary dial

The dial has two independent contact sets, both accessible at the dial's
terminal tabs (consult a WE dial pinout diagram for your specific dial
casting, since terminal numbering varies by production year):

- **Pulse (impulse) contacts**: normally closed, open once per pulse as the
  dial spins back to rest. Pulse count = digit dialed (0 is sent as 10
  pulses). This is what `rotary_phone/rotary_dial.py` counts.
- **Off-normal contacts**: close as soon as the dial is pulled away from rest,
  open again once it returns fully. Wiring this (optional but recommended)
  lets the code detect "digit finished" precisely instead of guessing from a
  timeout.

Same rule as the hookswitch: route both sets through separate opto-isolator
channels before they reach GPIO pins.

### 5. Handset audio interface

The F1 handset's transmitter (mic) and receiver (earpiece) need to reach the
Pi's USB sound card instead of the old network box:

- **Receiver (earpiece)**: a low-impedance (~150-300 ohm) magnetic element.
  Wire it from the sound card's headphone/line-out through a small series
  resistor (start around 100-220 ohm and adjust by ear) to keep levels
  reasonable -- add a small audio amp (many cheap PAM8403-based boards work)
  if it's too quiet once attenuated.
- **Transmitter (mic)**: this era of WE handset typically uses a carbon
  element, which needs a small DC bias current (historically supplied by the
  phone line itself) to work at all, plus AC coupling to strip that DC out
  before it reaches the sound card's mic input. A simple bias network is a
  few hundred ohms from a 3-6V supply in series with the transmitter, with a
  coupling capacitor (~1-10uF) feeding the sound card's mic-in. This is the
  fiddliest analog part of the whole build -- prebuilt "carbon mic to
  line-level" interface boards exist and are worth buying rather than
  hand-tuning bias resistors if you want predictable results.

Test both directions with `speaker-test`/`arecord` before wiring anything else
up, so you're not debugging audio and GPIO problems at the same time.

### 6. Ringer

Not implemented in this codebase -- this build is push-to-call only (booth
visitor initiates every call), so nothing needs to ring. If you want incoming
call indication later, know that the original ringer needs real AC ringing
voltage (~90V), which isn't something to improvise around GPIO; a small
independent buzzer/solenoid driven by a relay is a safer path than trying to
resurrect the original ringer coil.

### 7. Mounting the Pi

There's limited room in the base -- a Pi Zero 2 W plus a small perfboard for
the opto-isolators fits most 554 bases; a full-size Pi 4 likely needs to sit
just outside/underneath on a small platform. Keep the opto-isolator board
between the phone's original wiring and the Pi's GPIO header no matter which
Pi you use.

### Before final assembly

Verify every isolated signal with a multimeter (idle level, active level) with
the Pi *disconnected*, then connect the Pi and confirm each GPIO reads the
expected level in both handset positions / dial positions before closing the
case back up.
