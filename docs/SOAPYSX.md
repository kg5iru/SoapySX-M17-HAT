# SoapySX board profiles

The original SXceiver and the Z32IT LittlePA and BigPA boards use the
`board=sxceiver` profile. They must use their own HAT EEPROM/device-tree boot
configuration, not the M17 Project overlay.

The `sxxcvr` submodule adds a `board=m17` profile without changing the legacy
SXceiver defaults. The profile uses:

- `/dev/spidev0.0` for SX1255 register access;
- `/dev/gpiochip0`, BCM GPIO25 for reset;
- ALSA `hw:CARD=SX1255,DEV=1` for capture and `DEV=0` for playback;
- the HAT's fixed 32 MHz TCXO; and
- no external RX/TX switch GPIO or I2S-bit PA control.

Loading `sx1255_m17_raspberrypi.dtbo` creates a compatible device-tree marker,
allowing `board=auto` to select this profile even though the board has no HAT
identification EEPROM.

Explicit selection is always available:

```sh
SoapySDRUtil --probe="driver=sx,board=m17"
```

Supported overrides are `spi`, `gpiochip`, `reset_gpio`, `alsa_card`,
`alsa_rx`, `alsa_tx`, and `master_clock`. For example:

```sh
SoapySDRUtil --probe="driver=sx,board=m17,alsa_card=0"
```

The implementation preserves the original SXceiver profile, including HAT
EEPROM revision detection, its external RF switch GPIOs, automatic clock
detection and I2S sample-bit PA control.

## Named analog gains

SoapySX exposes RX `LNA` (0–48 dB) and `PGA` (0–30 dB), plus TX `DAC`
(0–9 dB) and `MIXER` (0–30 dB). Applications should use named SoapySDR gain
calls when analog gain placement matters. Aggregate gain calls remain
available and are divided between stages by the driver.

MMDVM-Multi's `RxLNAGain`, `RxPGAGain`, `TxDACGain`, and `TxMixerGain`
settings select these stages explicitly for `Type=sx`. `DigitalGain` remains
independent because it changes digital baseband amplitude rather than an
SX1255 analog stage.

## Validation performed

- clean CMake build of `libSXSupport.so` on 64-bit Raspberry Pi OS;
- device-tree compiler build of `sx1255_m17_raspberrypi.dtbo`;
- automatic and explicit M17 board discovery;
- RX and TX streaming at 125, 250 and 500 kS/s;
- M17 and DMR decode through MMDVM-Multi/IQ/Host; and
- simultaneous seven-channel process operation at 250 kS/s.
