# Seven-channel operation

One MMDVM-Multi process owns the SX1255. Seven MMDVM-IQ and seven MMDVM-Host
processes connect through unique UDP port pairs. RF network gateways are
disabled in the supplied templates.

| Channel | Mode | Offset from channel 1 | Default RX | Default TX |
|---:|:---:|---:|---:|---:|
| 1 | DMR | 0 kHz | 431.500 MHz | 446.500 MHz |
| 2 | DMR | +25 kHz | 431.525 MHz | 446.525 MHz |
| 3 | DMR | +50 kHz | 431.550 MHz | 446.550 MHz |
| 4 | DMR | +75 kHz | 431.575 MHz | 446.575 MHz |
| 5 | M17 | -25 kHz | 431.475 MHz | 446.475 MHz |
| 6 | M17 | -50 kHz | 431.450 MHz | 446.450 MHz |
| 7 | FM | -75 kHz | 431.425 MHz | 446.425 MHz |

MMDVM-Multi maps the remaining channels to `+25`, `+50`, `+75`, `-25`,
`-50`, and `-75` kHz around channel 1. Use a sample rate that is native to
the HAT's reference clock:

- `250000` for a 32 MHz reference, including the M17 Project HAT; or
- `300000` for a 38.4 MHz reference used by many SXceiver HATs.

The SXceiver profile detects its reference clock during the SoapySDR probe.
Set `sample_rate` in `config/site.ini` to the corresponding value before
running the configuration check.

Create the local site file, then dry-run the configuration generator:

```sh
sudo cp config/site.example.ini config/site.ini
sudoedit config/site.ini
./tools/run-seven-channel.py --check
less /tmp/mmdvm-seven-channel/MMDVM-Multi.ini
```

Inspect `/tmp/mmdvm-seven-channel/*.ini` before the first RF run. The
supervisor starts 15 processes in dependency order, reports early failures,
writes individual logs, and shuts down its children on SIGINT or SIGTERM.

```sh
sudo ./tools/run-seven-channel.py
sudo ./tools/run-seven-channel.py --stop
```

DMR defaults to color code 1 with both slots enabled. M17 defaults to CAN 0.
FM initially uses carrier/noise squelch for alignment. Network sections and
automatic beacons are disabled.
