#!/usr/bin/env python3
"""Measure an M17 transmission with a remote SoapySDR receiver."""

import argparse
import math
import sys
import time

import numpy as np
import SoapySDR
from SoapySDR import SOAPY_SDR_CF32, SOAPY_SDR_RX


def db(value: float) -> float:
    return 10.0 * math.log10(max(value, 1.0e-20))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", required=True, help="SoapyRemote URL, for example tcp://receiver:55132")
    parser.add_argument("--remote-driver", default="sx")
    parser.add_argument("--frequency", type=float, default=446.5e6)
    parser.add_argument("--rate", type=float, default=150e3)
    parser.add_argument("--gain", type=float, default=30.0)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--wait", action="store_true", help="wait for Enter before activating RX")
    args = parser.parse_args()

    dev_args = {
        "driver": "remote",
        "remote": args.remote,
        "remote:driver": args.remote_driver,
    }
    sdr = SoapySDR.Device(dev_args)
    sdr.setSampleRate(SOAPY_SDR_RX, 0, args.rate)
    sdr.setFrequency(SOAPY_SDR_RX, 0, args.frequency)
    sdr.setGain(SOAPY_SDR_RX, 0, args.gain)
    sdr.setAntenna(SOAPY_SDR_RX, 0, "RX")

    stream = sdr.setupStream(SOAPY_SDR_RX, SOAPY_SDR_CF32, [0])
    block = np.empty(8192, np.complex64)
    samples = []
    second_samples = []
    powers = []
    deadline = time.monotonic() + args.seconds
    next_report = time.monotonic() + 1.0

    print(
        f"RX-only monitor: {args.frequency / 1e6:.6f} MHz, "
        f"{args.rate / 1e3:.0f} kS/s, gain {args.gain:.0f} dB"
    )
    if args.wait:
        input("ARMED: press Enter to begin capture... ")
    sdr.activateStream(stream)
    print("Capture active: transmit the test signal now.", flush=True)

    try:
        while time.monotonic() < deadline:
            result = sdr.readStream(stream, [block], len(block), timeoutUs=1_000_000)
            if result.ret < 0:
                print(f"readStream failed: {SoapySDR.errToStr(result.ret)}", file=sys.stderr)
                continue
            if result.ret == 0:
                continue
            chunk = block[: result.ret].copy()
            samples.append(chunk)
            second_samples.append(chunk)
            if time.monotonic() >= next_report:
                window = np.concatenate(second_samples)
                power = float(np.mean(np.abs(window) ** 2))
                powers.append(power)
                peak = float(np.max(np.abs(window)))
                print(f"  power {db(power):7.2f} dBFS, peak {20.0 * math.log10(max(peak, 1e-10)):7.2f} dBFS")
                second_samples.clear()
                next_report += 1.0
    finally:
        sdr.deactivateStream(stream)
        sdr.closeStream(stream)

    if not samples or len(powers) < 4:
        print("Not enough samples received.", file=sys.stderr)
        return 1

    data = np.concatenate(samples)
    power_array = np.asarray(powers)
    noise_power = float(np.percentile(power_array, 20.0))
    signal_power = float(np.percentile(power_array, 80.0))
    snr = db(max(signal_power - noise_power, 1e-20) / noise_power)
    peak = float(np.max(np.abs(data)))
    clip_fraction = float(np.mean(np.abs(data) >= 0.98))

    # Average spectra from the strongest captures. Subtract the adjacent-channel
    # median before estimating the M17 spectral centroid and occupied bandwidth.
    fft_size = 8192
    usable = len(data) // fft_size * fft_size
    frames = data[:usable].reshape(-1, fft_size)
    frame_power = np.mean(np.abs(frames) ** 2, axis=1)
    frames = frames[frame_power >= np.percentile(frame_power, 75.0)]
    window = np.hanning(fft_size).astype(np.float32)
    spectra = np.abs(np.fft.fftshift(np.fft.fft(frames * window, axis=1), axes=1)) ** 2
    spectrum = np.mean(spectra, axis=0)
    freqs = np.fft.fftshift(np.fft.fftfreq(fft_size, 1.0 / args.rate))
    adjacent = (np.abs(freqs) >= 20e3) & (np.abs(freqs) <= 60e3)
    floor = float(np.median(spectrum[adjacent]))
    corrected = np.maximum(spectrum - floor, 0.0)
    channel = np.abs(freqs) <= 12.5e3
    channel_power = corrected[channel]
    channel_freqs = freqs[channel]
    centroid = float(np.sum(channel_freqs * channel_power) / max(np.sum(channel_power), 1e-20))
    order = np.argsort(channel_freqs)
    cumulative = np.cumsum(channel_power[order])
    cumulative /= max(cumulative[-1], 1e-20)
    lo = float(channel_freqs[order][np.searchsorted(cumulative, 0.005)])
    hi = float(channel_freqs[order][np.searchsorted(cumulative, 0.995)])

    print("\nMeasurement summary")
    print(f"  quiet-window power: {db(noise_power):.2f} dBFS")
    print(f"  burst-window power: {db(signal_power):.2f} dBFS")
    print(f"  wideband burst/quiet SNR: {snr:.2f} dB")
    print(f"  peak level: {20.0 * math.log10(max(peak, 1e-10)):.2f} dBFS")
    print(f"  samples near clipping: {100.0 * clip_fraction:.5f}%")
    print(f"  spectral centroid offset: {centroid:+.0f} Hz")
    print(f"  occupied bandwidth (99%): {hi - lo:.0f} Hz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
