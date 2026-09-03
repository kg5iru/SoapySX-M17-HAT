# Debugging and measurement tools

All reported dBFS values are relative digital levels unless the receiving SDR
has been calibrated against a signal generator. They are not absolute dBm.

## Per-channel RX level

`measure_multi_rx.py` observes MMDVM-Multi's loopback UDP reports. Raw packet
capture requires root or `CAP_NET_RAW`.

Capture a quiet baseline:

```sh
sudo ./tools/measure_multi_rx.py --seconds 10 --save results/noise.json
```

Then transmit the test signals and compare:

```sh
sudo ./tools/measure_multi_rx.py --seconds 20 \
  --compare results/noise.json --save results/keyed.json
```

Use the corresponding MMDVM-Host logs for decoded BER. The level tool measures
power and headroom; it does not demodulate DMR or M17 itself.

## Remote receiver tools

Both tools require NumPy, the SoapySDR Python bindings and an explicitly named
SoapyRemote endpoint. They are receive-only.

Measure all seven transmit bins in a 250/300 kS/s composite capture:

```sh
./tools/measure_multichannel_tx.py \
  --remote tcp://receiver.example:55132 --frequency 446500000
```

Measure burst/quiet SNR, clipping, centroid and occupied bandwidth for one
signal:

```sh
./tools/measure_remote_tx.py \
  --remote tcp://receiver.example:55132 --frequency 446500000 --wait
```

Place an attenuator or suitable RF isolation between the transmitter and test
receiver. Never exceed the receiver's maximum input level.
