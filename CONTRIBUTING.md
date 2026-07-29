# Contributing to kvprobe

## Two rules, both load-bearing

**1. No code path may emit an accusation.** Output is descriptive: *"the fingerprint shifted by
Δ at FPR f."* A PR that adds "provider X is cheating", or any phrasing a reader could quote as
an allegation, will be declined. See [`CLAIMS-MAP.md`](CLAIMS-MAP.md). A detector that accuses
has turned its own false-positive rate into a legal exposure.

**2. No verdict without a calibration.** `load_calibration()` raises `NotCalibrated` rather than
guessing. Do not add a default threshold, a fallback constant, or an "approximate" mode. An
uncalibrated fingerprint means nothing, and a tool that emits one anyway is the exact thing this
package exists to argue against.

## Changing the probe set changes everything

The probe set is content-addressed by `probe_sha256`. Editing it invalidates every calibration
derived from it — **by design**. If you add or change a probe you must re-run the calibration and
ship the new certificate; a probe-set change with a stale calibration is a silent correctness bug,
not a cosmetic one.

## Reporting a bound

Never report a bare rate. `0 observed` is not `0`. If a statistic has no interval, say so
explicitly rather than letting the reader assume precision the record does not support — and
remember that `n` trials are only `n` *independent* trials if they actually are. Our own published
FPR bound was too tight for exactly that reason: the control comparisons were derived from fewer
independent arms than the count suggested.

## Tests

```bash
pip install -e ".[dev]"
python -m pytest -q
```

Every test plants a defect and asserts the detector fires. The load-bearing one is
`test_identical_runs_do_not_trigger` — if identical responses ever read as a shift, the FPR is a
lie and nothing else in the package matters.
