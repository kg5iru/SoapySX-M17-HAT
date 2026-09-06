# SoapySX support for SX1255 Raspberry Pi HATs

This repository integrates SX1255-based Raspberry Pi HATs with
[SoapySX/sxxcvr](https://github.com/tejeez/sxxcvr) and the M17-aware
`m17-integration` branches of MMDVM-Multi, MMDVM-IQ and MMDVM-Host. It
supports the original SXceiver, the Z32IT LittlePA and BigPA boards, and the
M17 Project SX1255 HAT.

It includes:

- a pinned `sxxcvr` revision with an M17 HAT board profile and device-tree
  overlay;
- pinned MMDVM integration branches;
- public, callsign-neutral configuration templates;
- a configurable 4x DMR + 2x M17 + 1x FM supervisor; and
- RX gain/SNR and remote SDR spectrum measurement tools.

## Select the HAT profile

The boards use the same SX1255 transceiver but differ in their GPIO, clock,
RF switching and boot configuration. Select the profile that matches the
physical HAT:

| HAT | SoapySX profile | Boot configuration |
| --- | --- | --- |
| Original [SXceiver](https://sxceiver.com/) | `board=sxceiver` | Use the SXceiver HAT EEPROM/device-tree configuration. |
| Z32IT [LittlePA](https://github.com/labdvm/Little-PA-V2) and [BigPA](https://github.com/labdvm/BIG-PA-SPOT-SX1255-HAT) | `board=sxceiver` | Use the configuration supplied for the Z32IT board. |
| [M17 Project SX1255 HAT](https://github.com/M17-Project/SX1255_HAT-hw) | `board=m17` | Install the M17 Project overlay described below. |

For an SXceiver or Z32IT LittlePA/BigPA, verify the legacy profile with:

```sh
sudo SoapySDRUtil --find="driver=sx,board=sxceiver"
sudo SoapySDRUtil --probe="driver=sx,board=sxceiver"
```

Do not install or load the M17 Project overlay for an SXceiver or a Z32IT
LittlePA/BigPA. The probe reports whether the SXceiver profile detected a
32 MHz or 38.4 MHz reference; use that result when selecting the sample rate.

The current tested full-duplex alignment for the M17 Project HAT is RX gain
30 dB and TX gain 0 dB. On the test installation, simultaneous DMR and M17
transmissions decoded at 0.0% and 0.2% BER respectively. These are starting
points, not universal calibration values.

## Clone and build

```sh
cd /usr/src
sudo git clone --recurse-submodules https://github.com/kg5iru/SoapySX-M17-HAT.git
cd SoapySX-M17-HAT
sudo apt-get install --no-install-recommends \
  build-essential cmake device-tree-compiler libasound2-dev libgpiod-dev \
  libliquid-dev libmosquitto-dev libsoapysdr-dev nlohmann-json3-dev \
  python3-numpy python3-soapysdr

sudo cmake -S sxxcvr/SoapySX -B sxxcvr/SoapySX/build \
  -DINSTALL_PIPEWIRE_CONF=OFF
sudo cmake --build sxxcvr/SoapySX/build -j3
sudo cmake --install sxxcvr/SoapySX/build

sudo make -C MMDVM-Multi -j3
sudo make -C MMDVM-IQ -j3
sudo make -C MMDVM-Host -j3
```

## M17 Project SX1255 HAT only: install the overlay

Only perform this section when using the **M17 Project SX1255 HAT**. Skip it
for the original SXceiver and the Z32IT LittlePA/BigPA boards.

Build and install the M17 Project HAT overlay, then reboot:

```sh
cd /usr/src/SoapySX-M17-HAT
sudo make -C sxxcvr/dts overlays
sudo install -m 0644 sxxcvr/dts/build/sx1255_m17_raspberrypi.dtbo \
  /boot/firmware/overlays/
```

Open `/boot/firmware/config.txt` with elevated permissions:

```sh
sudoedit /boot/firmware/config.txt
```

Add this configuration, save the file, and reboot:

```ini
dtparam=spi=on
dtoverlay=sx1255_m17_raspberrypi
```

```sh
sudo reboot
```

After reboot, verify discovery before opening an RF stream:

```sh
sudo SoapySDRUtil --find="driver=sx,board=m17"
sudo SoapySDRUtil --probe="driver=sx,board=m17"
```

See [the SoapySX support notes](docs/SOAPYSX.md) for board behavior and
override arguments.

## Configure and run seven channels

Copy the example and enter your licensed station values and locally authorized
frequencies:

Set `sample_rate=250000` for a 32 MHz reference, including the M17 Project
HAT. Set `sample_rate=300000` when the SXceiver profile detects a 38.4 MHz
reference.

Ensure you have an editor set in `$EDITOR`, normally in `~/.bashrc`.

```sh
sudo cp config/site.example.ini config/site.ini
sudoedit config/site.ini
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
