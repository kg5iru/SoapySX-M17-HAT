#!/usr/bin/env python3
"""Generate and supervise a seven-channel MMDVM stack for an SX1255 HAT."""

from __future__ import annotations

import argparse
import configparser
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = Path("/tmp/mmdvm-seven-channel")
DEFAULT_SITE_CONFIG = ROOT / "config" / "site.ini"
TEMPLATE_DIR = ROOT / "config" / "templates"
MULTI_TEMPLATE = TEMPLATE_DIR / "MMDVM-Multi.ini"
IQ_TEMPLATE = TEMPLATE_DIR / "MMDVM-IQ.ini"
HOST_TEMPLATES = {
    "DMR": TEMPLATE_DIR / "MMDVM-Host-DMR.ini",
    "M17": TEMPLATE_DIR / "MMDVM-Host-M17.ini",
    "FM": TEMPLATE_DIR / "MMDVM-Host-FM.ini",
}
RSSI_TEMPLATE = TEMPLATE_DIR / "RSSI-relative.dat"


@dataclass(frozen=True)
class Site:
    callsign: str
    dmr_id: int
    rx_base_hz: int
    tx_base_hz: int
    sample_rate: int
    rx_gain_db: int
    tx_gain_db: int
    digital_gain: int
    rssi_calibration: int


@dataclass(frozen=True)
class Channel:
    number: int
    mode: str
    offset_hz: int
    rx_hz: int
    tx_hz: int

    @property
    def iq_local_port(self) -> int:
        return 3334 + (self.number - 1) * 2

    @property
    def host_local_port(self) -> int:
        return self.iq_local_port + 1


CHANNEL_LAYOUT = (
    (1, "DMR", 0),
    (2, "DMR", 25_000),
    (3, "DMR", 50_000),
    (4, "DMR", 75_000),
    (5, "M17", -25_000),
    (6, "M17", -50_000),
    (7, "FM", -75_000),
)


def load_site(path: Path) -> Site:
    parser = configparser.ConfigParser(interpolation=None)
    if not parser.read(path):
        raise RuntimeError(
            f"site configuration not found: {path}\n"
            "Copy config/site.example.ini to config/site.ini and set your station values."
        )

    try:
        site = Site(
            callsign=parser.get("station", "callsign").strip().upper(),
            dmr_id=parser.getint("station", "dmr_id"),
            rx_base_hz=parser.getint("radio", "rx_base_hz"),
            tx_base_hz=parser.getint("radio", "tx_base_hz"),
            sample_rate=parser.getint("radio", "sample_rate"),
            rx_gain_db=parser.getint("radio", "rx_gain_db"),
            tx_gain_db=parser.getint("radio", "tx_gain_db"),
            digital_gain=parser.getint("radio", "digital_gain"),
            rssi_calibration=parser.getint("radio", "rssi_calibration"),
        )
    except (configparser.Error, ValueError) as error:
        raise RuntimeError(f"invalid site configuration {path}: {error}") from error

    if not site.callsign or site.callsign == "N0CALL":
        raise RuntimeError(f"set a licensed callsign in {path}")
    if site.dmr_id <= 0:
        raise RuntimeError(f"set a positive DMR ID in {path}")
    if site.sample_rate != 250_000:
        raise RuntimeError("this seven-channel layout requires sample_rate=250000")
    if not 0 <= site.rx_gain_db <= 60 or not 0 <= site.tx_gain_db <= 15:
        raise RuntimeError("SX1255 gains must be RX 0..60 dB and TX 0..15 dB")
    return site


def build_channels(site: Site) -> tuple[Channel, ...]:
    return tuple(
        Channel(number, mode, offset, site.rx_base_hz + offset, site.tx_base_hz + offset)
        for number, mode, offset in CHANNEL_LAYOUT
    )


def render_ini(source: Path, destination: Path, changes: dict[tuple[str, str], str]) -> None:
    """Copy an INI while replacing selected section/key values."""
    section = ""
    seen: set[tuple[str, str]] = set()
    output: list[str] = []

    for original in source.read_text(encoding="utf-8").splitlines(keepends=True):
        stripped = original.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped[1:-1]
            output.append(original)
            continue

        if stripped and not stripped.startswith(("#", ";")) and "=" in original:
            key = original.split("=", 1)[0].strip()
            item = (section, key)
            if item in changes:
                output.append(f"{key}={changes[item]}\n")
                seen.add(item)
                continue
        output.append(original)

    missing = set(changes) - seen
    if missing:
        formatted = ", ".join(f"[{section}] {key}" for section, key in sorted(missing))
        raise RuntimeError(f"template {source} is missing: {formatted}")

    destination.write_text("".join(output), encoding="utf-8")


def prepare_configs(site: Site, channels: tuple[Channel, ...], run_dir: Path) -> list[tuple[Channel, Path, Path]]:
    run_dir.mkdir(mode=0o755, parents=True, exist_ok=True)
    rssi_mapping = run_dir / "RSSI-relative.dat"
    rssi_mapping.write_text(RSSI_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    render_ini(
        MULTI_TEMPLATE,
        run_dir / "MMDVM-Multi.ini",
        {
            ("Modem", "RxFrequency"): str(site.rx_base_hz),
            ("Modem", "TxFrequency"): str(site.tx_base_hz),
            ("Modem", "SampleRate"): str(site.sample_rate),
            ("Modem", "RxGain"): str(site.rx_gain_db),
            ("Modem", "TxGain"): str(site.tx_gain_db),
            ("Modem", "DigitalGain"): str(site.digital_gain),
            ("General", "RSSICalibration"): str(site.rssi_calibration),
        },
    )

    configs: list[tuple[Channel, Path, Path]] = []
    for channel in channels:
        iq_config = run_dir / f"MMDVM-IQ-{channel.number}-{channel.mode}.ini"
        host_config = run_dir / f"MMDVM-Host-{channel.number}-{channel.mode}.ini"
        index = channel.number - 1

        render_ini(
            IQ_TEMPLATE,
            iq_config,
            {
                ("MQTT", "Name"): f"mmdvm-iq-7ch-{channel.number}-{channel.mode.lower()}",
                ("Host", "HostPort"): str(channel.host_local_port),
                ("Host", "LocalPort"): str(channel.iq_local_port),
                ("Multi", "ModemPort"): str(48200 + index),
                ("Multi", "LocalPort"): str(48100 + index),
            },
        )

        host_changes = {
            ("General", "Callsign"): site.callsign,
            ("General", "Id"): str(site.dmr_id),
            ("CW Id", "Callsign"): site.callsign,
            ("MQTT", "Name"): f"mmdvm-host-7ch-{channel.number}-{channel.mode.lower()}",
            ("Modem", "ModemPort"): str(channel.iq_local_port),
            ("Modem", "LocalPort"): str(channel.host_local_port),
            ("Modem", "RXFrequency"): str(channel.rx_hz),
            ("Modem", "TXFrequency"): str(channel.tx_hz),
            ("Modem", "RSSIMappingFile"): str(rssi_mapping),
        }
        if channel.mode == "FM":
            host_changes[("FM", "Callsign")] = site.callsign
        render_ini(HOST_TEMPLATES[channel.mode], host_config, host_changes)
        configs.append((channel, iq_config, host_config))

    return configs


def print_plan(site: Site, channels: tuple[Channel, ...]) -> None:
    print(
        f"Station {site.callsign} / DMR ID {site.dmr_id}; "
        f"RX gain {site.rx_gain_db} dB; TX gain {site.tx_gain_db} dB"
    )
    print("Ch  Mode  Offset   RX MHz      TX MHz      Host<->IQ    IQ<->Multi")
    for channel in channels:
        sign = f"{channel.offset_hz // 1000:+d} kHz"
        iq_multi = f"{48100 + channel.number - 1}/{48200 + channel.number - 1}"
        print(
            f"{channel.number:>2}  {channel.mode:<3}  {sign:>7}  "
            f"{channel.rx_hz / 1e6:10.6f}  {channel.tx_hz / 1e6:10.6f}  "
            f"{channel.host_local_port}/{channel.iq_local_port}      {iq_multi}"
        )


def tail(path: Path, lines: int = 20) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log output)"


def stop_supervisor(run_dir: Path) -> int:
    supervisor_pid_path = run_dir / "supervisor.pid"
    try:
        pid = int(supervisor_pid_path.read_text(encoding="utf-8").strip())
        command_line = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
        if b"run-seven-channel.py" not in command_line:
            raise RuntimeError(f"PID {pid} is not the seven-channel supervisor")
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to seven-channel supervisor PID {pid}")
        return 0
    except FileNotFoundError:
        print("The seven-channel stack is not running", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Unable to stop seven-channel stack: {error}", file=sys.stderr)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-config", type=Path, default=DEFAULT_SITE_CONFIG)
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--check", action="store_true", help="generate configs and print the plan without opening the radio")
    parser.add_argument("--stop", action="store_true", help="stop a running seven-channel supervisor")
    args = parser.parse_args()

    if args.stop:
        return stop_supervisor(args.run_dir)

    try:
        site = load_site(args.site_config)
        channels = build_channels(site)
        configs = prepare_configs(site, channels, args.run_dir)
    except (OSError, RuntimeError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    print_plan(site, channels)
    if args.check:
        print(f"Generated runtime configs in {args.run_dir}")
        return 0

    binaries = (
        ROOT / "MMDVM-Multi" / "MMDVM-Multi",
        ROOT / "MMDVM-IQ" / "MMDVM-IQ",
        ROOT / "MMDVM-Host" / "MMDVM-Host",
    )
    required = (*binaries, MULTI_TEMPLATE, IQ_TEMPLATE, RSSI_TEMPLATE, *HOST_TEMPLATES.values())
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        print("Missing required files:\n  " + "\n  ".join(missing), file=sys.stderr)
        return 1

    processes: list[tuple[str, subprocess.Popen[bytes], object, Path]] = []
    stopping = False
    supervisor_pid_path = args.run_dir / "supervisor.pid"

    def stop_all(_signum: int | None = None, _frame: object | None = None) -> None:
        nonlocal stopping
        if stopping:
            return
        stopping = True
        for _name, process, _log_handle, _log_path in reversed(processes):
            if process.poll() is None:
                process.terminate()
        deadline = time.monotonic() + 5.0
        for _name, process, _log_handle, _log_path in reversed(processes):
            if process.poll() is None:
                try:
                    process.wait(timeout=max(0.1, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    process.kill()
        for _name, _process, log_handle, _log_path in processes:
            log_handle.close()
        try:
            if supervisor_pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                supervisor_pid_path.unlink()
        except FileNotFoundError:
            pass

    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)

    def launch(name: str, command: list[str]) -> None:
        log_path = args.run_dir / f"{name}.log"
        log_handle = log_path.open("wb")
        process = subprocess.Popen(
            command,
            cwd=Path(command[0]).parent,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
        )
        processes.append((name, process, log_handle, log_path))

    try:
        supervisor_pid_path.write_text(f"{os.getpid()}\n", encoding="utf-8")
        launch("multi", [str(binaries[0]), str(args.run_dir / "MMDVM-Multi.ini")])
        time.sleep(1.5)
        if processes[-1][1].poll() is not None:
            raise RuntimeError(f"MMDVM-Multi exited early:\n{tail(processes[-1][3])}")

        for channel, iq_config, _host_config in configs:
            launch(f"iq-{channel.number}-{channel.mode.lower()}", [str(binaries[1]), str(iq_config)])
        time.sleep(1.5)

        for channel, _iq_config, host_config in configs:
            launch(f"host-{channel.number}-{channel.mode.lower()}", [str(binaries[2]), str(host_config)])
        time.sleep(3.0)

        failures = [
            f"{name} exited with {process.returncode}:\n{tail(log_path)}"
            for name, process, _handle, log_path in processes
            if process.poll() is not None
        ]
        if failures:
            raise RuntimeError("\n\n".join(failures))

        (args.run_dir / "pids").write_text(
            "".join(f"{process.pid} {name}\n" for name, process, _handle, _path in processes),
            encoding="utf-8",
        )
        print(f"All {len(processes)} processes are running. Logs: {args.run_dir}", flush=True)

        while not stopping:
            time.sleep(1.0)
            if stopping:
                break
            failures = [name for name, process, _handle, _path in processes if process.poll() is not None]
            if failures:
                raise RuntimeError("processes exited unexpectedly: " + ", ".join(failures))
    except Exception as error:
        print(f"Seven-channel stack failed: {error}", file=sys.stderr)
        stop_all()
        return 1
    finally:
        stop_all()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
