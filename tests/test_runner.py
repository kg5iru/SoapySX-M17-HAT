"""Tests for seven-channel configuration generation."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_seven_channel", ROOT / "tools" / "run-seven-channel.py"
)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = RUNNER
SPEC.loader.exec_module(RUNNER)


SITE_TEXT = """\
[station]
callsign=TEST1
dmr_id=1234567

[radio]
rx_base_hz=431500000
tx_base_hz=446500000
sample_rate=250000
rx_gain_db=30
tx_gain_db=0
digital_gain=35
rssi_calibration=70
"""


class RunnerTests(unittest.TestCase):
    def test_generates_all_channels_and_site_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            site_path = work / "site.ini"
            site_path.write_text(SITE_TEXT, encoding="utf-8")
            site = RUNNER.load_site(site_path)
            channels = RUNNER.build_channels(site)
            configs = RUNNER.prepare_configs(site, channels, work / "run")

            self.assertEqual(len(configs), 7)
            self.assertEqual(channels[2].rx_hz, 431_550_000)
            self.assertEqual(channels[5].tx_hz, 446_450_000)

            dmr = configs[2][2].read_text(encoding="utf-8")
            m17 = configs[5][2].read_text(encoding="utf-8")
            multi = (work / "run" / "MMDVM-Multi.ini").read_text(encoding="utf-8")
            self.assertIn("Callsign=TEST1", dmr)
            self.assertIn("Id=1234567", m17)
            self.assertIn("RXFrequency=431550000", dmr)
            self.assertIn("TXFrequency=446450000", m17)
            self.assertIn("RxGain=30", multi)
            self.assertIn("TxGain=0", multi)
            self.assertIn(str(work / "run" / "RSSI-relative.dat"), dmr)

    def test_rejects_unconfigured_example_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            site_path = Path(temporary) / "site.ini"
            site_path.write_text(
                SITE_TEXT.replace("TEST1", "N0CALL").replace("1234567", "0"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "licensed callsign"):
                RUNNER.load_site(site_path)


if __name__ == "__main__":
    unittest.main()
