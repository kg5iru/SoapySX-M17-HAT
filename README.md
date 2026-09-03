# SoapySX support for the M17 Project SX1255 HAT

This repository integrates the
[M17 Project SX1255 HAT](https://github.com/M17-Project/SX1255_HAT-hw) with
[SoapySX/sxxcvr](https://github.com/tejeez/sxxcvr) and the M17-aware
`m17-integration` branches of MMDVM-Multi, MMDVM-IQ and MMDVM-Host.

It includes:

- a pinned `sxxcvr` revision with an M17 HAT board profile and device-tree
  overlay;
- pinned MMDVM integration branches;
- public, callsign-neutral configuration templates;
- a configurable 4x DMR + 2x M17 + 1x FM supervisor; and
- RX gain/SNR and remote SDR spectrum measurement tools.

The current tested full-duplex alignment is RX gain 30 dB and TX gain 0 dB.
On the test installation, simultaneous DMR and M17 transmissions decoded at
0.0% and 0.2% BER respectively. These are starting points, not universal
calibration values.

## Clone and build

```sh
git clone --recurse-submodules https://github.com/kg5iru/SoapySX-M17-HAT.git
cd SoapySX-M17-HAT
sudo apt-get install --no-install-recommends \
  build-essential cmake device-tree-compiler libasound2-dev libgpiod-dev \
  libliquid-dev libsoapysdr-dev python3-numpy python3-soapysdr

cmake -S sxxcvr/SoapySX -B sxxcvr/SoapySX/build \
  -DINSTALL_PIPEWIRE_CONF=OFF
cmake --build sxxcvr/SoapySX/build -j2
sudo cmake --install sxxcvr/SoapySX/build

make -C MMDVM-Multi -j2
make -C MMDVM-IQ -j2
make -C MMDVM-Host -j2
```

Install the M17 HAT overlay and reboot:

```sh
make -C sxxcvr/dts overlays
sudo install -m 0644 sxxcvr/dts/build/sx1255_m17_raspberrypi.dtbo \
  /boot/firmware/overlays/
```

Add this to `/boot/firmware/config.txt`:

```ini
dtparam=spi=on
dtoverlay=sx1255_m17_raspberrypi
```

After reboot, verify discovery before opening an RF stream:

```sh
SoapySDRUtil --find="driver=sx,board=m17"
SoapySDRUtil --probe="driver=sx,board=m17"
```

See [the SoapySX support notes](docs/SOAPYSX.md) for board behavior and
override arguments.

## Configure and run seven channels

Copy the example and enter your licensed station values and locally authorized
frequencies:

```sh
cp config/site.example.ini config/site.ini
$EDITOR config/site.ini
./tools/run-seven-channel.py --check
sudo ./tools/run-seven-channel.py
```

`config/site.ini` is ignored by Git. Generated configurations, logs and PID
files are written to `/tmp/mmdvm-seven-channel`. Stop a background supervisor
with:

```sh
sudo ./tools/run-seven-channel.py --stop
```

The example frequencies are laboratory/alignment values. Confirm band-plan,
license, coordination, filtering, duplex isolation and occupied-bandwidth
requirements before transmitting.

See [seven-channel operation](docs/SEVEN_CHANNEL.md),
[debugging tools](docs/DEBUGGING.md), and
[measured alignment results](docs/TEST_RESULTS.md).

## Repository layout

| Path | Purpose |
|---|---|
| `sxxcvr/` | SoapySX fork with the M17 HAT board profile |
| `MMDVM-{Multi,IQ,Host}/` | pinned `m17-integration` source trees |
| `SX1255_HAT-hw/` | upstream HAT hardware reference |
| `config/templates/` | callsign-neutral MMDVM templates |
| `config/site.example.ini` | local station/radio settings example |
| `tools/` | supervisor and RF diagnostic utilities |
| `docs/` | setup, testing and implementation notes |

## Licensing

The integration scripts and documentation in this repository are MIT licensed.
Each submodule retains its own license; notably, the MMDVM projects are GPLv2.
