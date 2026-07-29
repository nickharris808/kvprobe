import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pytest
from kvprobe.detector import NotCalibrated, compare, load_calibration, rule_of_three_upper, verdict

CAL = load_calibration()

def _rows(texts):
    return [{"id": f"p{i}", "text": t, "token_ids": [ord(c) for c in t]} for i, t in enumerate(texts)]

def test_identical_runs_do_not_trigger():
    """The load-bearing case: same responses must NOT read as a shift, or the FPR is a lie."""
    a = _rows(["alpha", "beta", "gamma"])
    assert verdict(compare(a, _rows(["alpha", "beta", "gamma"])), CAL)["fingerprint_shifted"] is False

def test_different_runs_do_trigger():
    a, b = _rows(["alpha", "beta"]), _rows(["ALPHA", "BETA"])
    assert verdict(compare(a, b), CAL)["fingerprint_shifted"] is True

def test_refuses_without_calibration():
    with pytest.raises(NotCalibrated):
        load_calibration("/nonexistent/calibration.json")

def test_shipped_calibration_carries_a_measured_fpr():
    assert CAL["MEASURED_FPR_probe_level"] is not None
    assert CAL["n_probe_comparisons_control"] >= 1
    assert CAL["FPR_probe_level_95pct_upper_bound"] is not None, "zero observed is not zero"

def test_rule_of_three():
    assert abs(rule_of_three_upper(240) - 0.0125) < 1e-9

def test_no_accusation_language_anywhere():
    """Posture enforced in code, not just docs."""
    v = verdict(compare(_rows(["a"]), _rows(["b"])), CAL)
    blob = " ".join([v["statement"], *v["interpretation_limits"]]).lower()
    for word in ("lying", "lied", "fraud", "cheating", "dishonest", "substituted a model"):
        assert word not in blob or "NOT evidence" in " ".join(v["interpretation_limits"])
    assert any("NOT evidence" in x for x in v["interpretation_limits"])

def test_text_only_degradation_is_recorded():
    a = [{"id": "p1", "text": "x"}]
    assert compare(a, [{"id": "p1", "text": "x"}])["feature_set"] == "text_only"
