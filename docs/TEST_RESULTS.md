# Prototype alignment results

These results document one M17 Project SX1255 HAT installation. RF levels,
antenna isolation and local noise will differ elsewhere.

| RX gain | DMR BER | M17 BER | Observation |
|---:|---:|---:|---|
| 60 dB | up to 2.1% / lost call | 0.2% | adjacent false lock; inadequate duplex headroom |
| 48 dB | 0.0% | 0.2% | clean simultaneous decode |
| 42 dB | 0.0% | 0.2% | clean simultaneous decode |
| 36 dB | 0.0% | 0.2% | clean, increased headroom |
| 30 dB | 0.0% | 0.2% | selected balance of sensitivity and headroom |
| 24 dB | 0.3% | 0.2% | lower floor but no BER improvement |

At RX gain 30 dB, the intended DMR and M17 channels measured approximately
82 dB and 86 dB above their quiet digital baselines during the test. Strong
windows reached about -13 dBFS (DMR) and -5 dBFS (M17). TX gain was 0 dB, the
minimum exposed by the SX1255 driver.

The one-time RX overrun and late-TX warnings occurred during process startup
and did not continue during steady-state reception.
