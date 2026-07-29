"""kvprobe — is your LLM provider serving the model you're paying for?

A substitution detector whose false-positive rate was MEASURED on self-hosted ground truth, not
assumed. Descriptive fingerprints only: this package has no code path that emits an accusation.
"""
from .detector import NotCalibrated, compare, load_calibration, verdict  # noqa: F401

__version__ = "0.2.0"
__license_tag__ = "CLEAN"
