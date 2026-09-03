#!/usr/bin/env python3
"""Read per-channel MMDVM-Multi RX power reports from loopback traffic."""

from __future__ import annotations

import argparse
import json
import socket
import struct
import time
from pathlib import Path

import numpy as np


MODES = ("DMR", "DMR", "DMR", "DMR", "M17", "M17", "FM")
OFFSETS_KHZ = (0, 25, 50, 75, -25, -50, -75)
BASE_PORT = 48100
DEFAULT_CALIBRATION = 70


def capture(seconds: float, interface: str, base_port: int) -> dict[int, list[int]]:
    values = {channel: [] for channel in range(7)}
    raw = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(0x0800))
    raw.bind((interface, 0))
    raw.settimeout(0.5)
    deadline = time.monotonic() + seconds

    try:
        while time.monotonic() < deadline:
            try:
                packet = raw.recv(65535)
            except TimeoutError:
                continue

            if len(packet) < 42 or packet[12:14] != b"\x08\x00":
                continue
            ip_start = 14
            if packet[ip_start] >> 4 != 4 or packet[ip_start + 9] != socket.IPPROTO_UDP:
                continue
            ip_length = (packet[ip_start] & 0x0F) * 4
            udp_start = ip_start + ip_length
            if len(packet) < udp_start + 8:
                continue
            _source_port, destination_port, udp_length, _checksum = struct.unpack_from("!HHHH", packet, udp_start)
            channel = destination_port - base_port
            if channel not in values:
                continue
            payload = packet[udp_start + 8 : udp_start + udp_length]
            if len(payload) < 8:
                continue
            sample_count, rssi = struct.unpack_from("<II", payload)
            if sample_count == 720 and 0 < rssi < 1024:
                values[channel].append(rssi)
    finally:
        raw.close()

    return values


def summarize(values: dict[int, list[int]], calibration: int) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    print("Ch  Mode  Offset   median dBFS   quiet..strong   samples")
    for channel in range(7):
        data = np.asarray(values[channel], dtype=np.float64)
        if data.size == 0:
            print(f"{channel + 1:>2}  {MODES[channel]:<3}  {OFFSETS_KHZ[channel]:+4d}k   no data")
            continue
        p10, median, p90 = np.percentile(data, [10, 50, 90])
        # Multi sends abs(dbFS) + RSSICalibration. Its configured identity
        # RSSI map displays the negative of this value as a relative dB level.
        display = -median
        internal_dbfs = -(median - calibration)
        print(
            f"{channel + 1:>2}  {MODES[channel]:<3}  {OFFSETS_KHZ[channel]:+4d}k  "
            f"{internal_dbfs:8.1f}    {-p90 + calibration:6.1f}.."
            f"{-p10 + calibration:6.1f}  {data.size:8d}"
        )
        result[str(channel + 1)] = {
            "median_reported_db": float(display),
            "median_internal_dbfs": float(internal_dbfs),
            "rssi_calibration": calibration,
            "p10_rssi_index": float(p10),
            "p90_rssi_index": float(p90),
            "samples": int(data.size),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=6.0)
    parser.add_argument("--interface", default="lo", help="capture interface (default: lo)")
    parser.add_argument("--base-port", type=int, default=BASE_PORT)
    parser.add_argument("--calibration", type=int, default=DEFAULT_CALIBRATION)
    parser.add_argument("--save", type=Path, help="save summary JSON for a later comparison")
    parser.add_argument("--compare", type=Path, help="compare medians with a saved quiet baseline")
    args = parser.parse_args()

    print(f"Capturing {args.seconds:.1f} seconds from MMDVM-Multi -> MMDVM-IQ...", flush=True)
    summary = summarize(capture(args.seconds, args.interface, args.base_port), args.calibration)

    if args.compare:
        baseline = json.loads(args.compare.read_text(encoding="utf-8"))
        print("\nStrong-window (P10) power above quiet median")
        for channel in range(1, 8):
            key = str(channel)
            if key not in summary or key not in baseline:
                continue
            active_level = -summary[key]["p10_rssi_index"]
            snr = active_level - baseline[key]["median_reported_db"]
            internal_level = -(summary[key]["p10_rssi_index"] - args.calibration)
            print(
                f"  Ch {channel} {MODES[channel - 1]:<3}: {snr:+.1f} dB, "
                f"active {internal_level:.1f} dBFS internal"
            )

    if args.save:
        args.save.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Saved summary to {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
