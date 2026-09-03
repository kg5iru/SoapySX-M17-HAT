#!/usr/bin/env python3
"""Measure the seven MMDVM-Multi transmit bins with a remote Soapy receiver."""

from __future__ import annotations

import argparse
import math
import time

import numpy as np
import SoapySDR
from SoapySDR import SOAPY_SDR_CF32, SOAPY_SDR_RX


CHANNELS = (
    (1, "DMR", 0),
    (2, "DMR", 25_000),
    (3, "DMR", 50_000),
    (4, "DMR", 75_000),
    (5, "M17", -25_000),
    (6, "M17", -50_000),
    (7, "FM", -75_000),
)


def db(power: float) -> float:
    return 10.0 * math.log10(max(power, 1.0e-20))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", required=True, help="SoapyRemote URL, for example tcp://receiver:55132")
    parser.add_argument("--remote-driver", default="sx")
    parser.add_argument("--frequency", type=float, default=446.5e6)
    # The remote SX1255 uses a 38.4 MHz reference; 300 kS/s is native.
    parser.add_argument("--rate", type=float, default=300e3)
    parser.add_argument("--gain", type=float, default=30.0)
    parser.add_argument("--seconds", type=float, default=5.0)
    args = parser.parse_args()

    sdr = SoapySDR.Device(
        {
            "driver": "remote",
            "remote": args.remote,
            "remote:driver": args.remote_driver,
        }
    )
    sdr.setSampleRate(SOAPY_SDR_RX, 0, args.rate)
    sdr.setFrequency(SOAPY_SDR_RX, 0, args.frequency)
    sdr.setGain(SOAPY_SDR_RX, 0, args.gain)
    sdr.setAntenna(SOAPY_SDR_RX, 0, "RX")

    stream = sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32, [0])
    block = np.empty(8192, np.complex64)
    captures: list[np.ndarray] = []
    deadline = time.monotonic() + args.seconds
    sdr.activateStream(stream)
    try:
        while time.monotonic() < deadline:
            result = sdr.readStream(stream, [block], len(block), timeoutUs=1_000_000)
            if result.ret > 0:
                captures.append(block[: result.ret].copy())
    finally:
        sdr.deactivateStream(stream)
        sdr.closeStream(stream)

    if not captures:
        raise RuntimeError("remote receiver returned no samples")

    data = np.concatenate(captures)
    fft_size = 16384
    usable = len(data) // fft_size * fft_size
    frames = data[:usable].reshape(-1, fft_size)
    frames = frames - np.mean(frames, axis=1, keepdims=True)
    window = np.hanning(fft_size).astype(np.float32)
    spectra = np.abs(np.fft.fftshift(np.fft.fft(frames * window, axis=1), axes=1)) ** 2
    spectrum = np.mean(spectra, axis=0) / (fft_size * np.sum(window**2))
    freqs = np.fft.fftshift(np.fft.fftfreq(fft_size, 1.0 / args.rate))

    # Median-bin noise estimate, integrated over the same 12.5 kHz channel.
    noise_per_bin = float(np.median(spectrum[np.abs(freqs) > 90_000]))
    bin_width = args.rate / fft_size
    channel_bins = max(1, round(12_500 / bin_width))
    noise_power = noise_per_bin * channel_bins

    print(
        f"Remote composite TX: {args.frequency / 1e6:.6f} MHz, "
        f"{args.rate / 1e3:.0f} kS/s, {args.seconds:.1f} s"
    )
    print("Ch  Mode  Offset   12.5-kHz power  Above floor")
    for number, mode, offset in CHANNELS:
        mask = np.abs(freqs - offset) <= 6_250
        power = float(np.sum(spectrum[mask]))
        excess = db(max(power - noise_power, 1.0e-20) / noise_power)
        print(f"{number:>2}  {mode:<3}  {offset / 1000:+6.0f}k   {db(power):9.2f} dBFS  {excess:8.2f} dB")

    peak = float(np.max(np.abs(data)))
    clipped = float(np.mean(np.abs(data) >= 0.98))
    print(f"Peak: {20.0 * math.log10(max(peak, 1e-10)):.2f} dBFS; clipped: {100.0 * clipped:.5f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
