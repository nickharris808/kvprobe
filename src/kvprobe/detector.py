"""detector.py — the substitution statistic, and the calibration that gives it meaning.

THE ASSET IS THE FALSE-POSITIVE RATE, NOT THE DETECTOR. Anyone can write a function that says two
model responses differ. What makes it worth anything is knowing how often it says that when the model
is UNCHANGED — and that number is only obtainable on ground truth you control (same model, same
precision, different seed and batch composition).

So this module refuses to render a verdict without a calibration certificate. An uncalibrated
detector pointed at a provider produces a fingerprint that means nothing, and would invite exactly the
accusation this tool must never make.

Calibration shipped with the package was measured on self-hosted ground truth:
  control fp16-vs-fp16, 10 pairs  D = 0.0 - 0.025  (5 arms; seed AND batch composition varied)
  positive fp16-vs-fp8-KV          D = 1.0     (40/40 probes differ)
  positive fp16-vs-int4-AWQ        D = 0.825   (33/40 differ)
  => tau = 0.025 (from the sealed RULE, not chosen), probe-level FPR = 0.01 over 400 comparisons,
     TPR = 1.0 on BOTH positive arms.

This is the SECOND calibration. The first shipped with 6 control pairs against a sealed minimum of
10, a held-out FPR that was 0 by arithmetic on tied values, a degenerate tau = 0, and a "zero
observed" FPR that overstated precision. All four are fixed; see oss/AUDIT.md F4. TPR now covers a
KV-PRECISION substitution (fp8) as well as a weight substitution (int4) -- the fp8 arm used to fail
to boot, which was the sole reason for the old "int4 only, do NOT generalize" caveat.

Stdlib only.
"""
from __future__ import annotations

import json
import math
import os

CALIBRATION_ENV = "KVPROBE_CALIBRATION"
_DEFAULT_CAL = os.path.join(os.path.dirname(__file__), "data", "detector_calibration.json")


class NotCalibrated(RuntimeError):
    """Raised rather than guessing. A verdict without a measured FPR is not a verdict."""


def load_calibration(path: str | None = None) -> dict:
    p = path or os.environ.get(CALIBRATION_ENV) or _DEFAULT_CAL
    if not os.path.exists(p):
        raise NotCalibrated(
            f"no calibration certificate at {p}. kvprobe will not emit a verdict without a MEASURED "
            f"false-positive rate — an uncalibrated fingerprint means nothing. Supply one with "
            f"--calibration or ${CALIBRATION_ENV}.")
    c = json.load(open(p))
    if c.get("status") != "MEASURED" or c.get("tau") is None:
        raise NotCalibrated(f"calibration at {p} is not MEASURED (status={c.get('status')})")
    return c


def rule_of_three_upper(n: int) -> float | None:
    """One-sided 95% upper bound on a rate given ZERO observed events in n trials."""
    return (3.0 / n) if n else None


def js_divergence(p: dict, q: dict) -> float:
    """Jensen-Shannon divergence between two top-K logprob dicts (nats)."""
    keys = set(p) | set(q)
    if not keys:
        return 0.0
    pp = {k: math.exp(float(p.get(k, -30.0))) for k in keys}
    qq = {k: math.exp(float(q.get(k, -30.0))) for k in keys}
    sp, sq = sum(pp.values()) or 1.0, sum(qq.values()) or 1.0
    d = 0.0
    for k in keys:
        a, b = pp[k] / sp, qq[k] / sq
        m = 0.5 * (a + b)
        if a > 0 and m > 0:
            d += 0.5 * a * math.log(a / m)
        if b > 0 and m > 0:
            d += 0.5 * b * math.log(b / m)
    return max(0.0, d)


def compare(a_rows: list[dict], b_rows: list[dict]) -> dict:
    """The sealed statistic D = 1 - top1_agreement_rate over a probe set, plus the auxiliary features.

    Each row: {id, text, token_ids?, topk_logprobs?}. When a provider exposes no logprobs the
    comparison degrades to the TEXT-ONLY feature set, and the caller must record that it did.
    """
    ba = {r["id"]: r for r in a_rows}
    bb = {r["id"]: r for r in b_rows}
    ids = sorted(set(ba) & set(bb))
    if not ids:
        return {"n": 0}
    same, js_vals, len_deltas, have_logprobs = 0, [], [], False
    for i in ids:
        ra, rb = ba[i], bb[i]
        ta, tb = ra.get("token_ids"), rb.get("token_ids")
        if ta is not None and tb is not None:
            identical = (ta == tb)
        else:                                  # text-only fallback
            identical = (str(ra.get("text", "")).strip() == str(rb.get("text", "")).strip())
        same += int(identical)
        len_deltas.append(abs(len(str(ra.get("text", ""))) - len(str(rb.get("text", "")))))
        ka, kb = ra.get("topk_logprobs") or [], rb.get("topk_logprobs") or []
        if ka and kb:
            have_logprobs = True
            m = min(len(ka), len(kb))
            js_vals += [js_divergence(ka[j], kb[j]) for j in range(m)]
    agree = same / len(ids)
    return {"n": len(ids), "top1_agreement_rate": round(agree, 6), "D": round(1.0 - agree, 6),
            "mean_js_divergence_topk": round(sum(js_vals) / len(js_vals), 8) if js_vals else None,
            "mean_response_length_delta": round(sum(len_deltas) / len(len_deltas), 3),
            "feature_set": "logprobs+text" if have_logprobs else "text_only",
            "n_probes_differing": len(ids) - same}


def verdict(stat: dict, cal: dict) -> dict:
    """Render a DESCRIPTIVE verdict. There is deliberately no code path that emits an accusation."""
    tau = float(cal["tau"])
    fpr = cal.get("MEASURED_FPR_probe_level")
    n_ctrl = cal.get("n_probe_comparisons_control") or 0
    # rule_of_three only MEANS anything at zero observed events. The current calibration has a
    # NON-zero measured FPR, so the bound is reported only when it is actually applicable.
    ub = (cal.get("FPR_probe_level_95pct_upper_bound_HONEST")
          or cal.get("FPR_probe_level_95pct_upper_bound")
          or (rule_of_three_upper(n_ctrl) if not fpr else None))
    d = stat.get("D")
    if d is None:
        return {"status": "NO_DATA", "note": "no comparable probes"}
    shifted = d > tau
    return {
        "status": "MEASURED",
        "D": d, "tau": tau, "fingerprint_shifted": bool(shifted),
        "calibrated_FPR": fpr, "FPR_95pct_upper_bound": ub, "n_control_comparisons": n_ctrl,
        "feature_set_used": stat.get("feature_set"),
        # descriptive, never an allegation
        "statement": (f"fingerprint shifted (D={d} > tau={tau}) at a measured false-positive rate of "
                      f"{fpr} (95% upper bound ~{ub})" if shifted else
                      f"no fingerprint shift detected (D={d} <= tau={tau}) at FPR {fpr}"),
        "interpretation_limits": [
            "This is a DESCRIPTIVE measurement of a publicly-offered API. It is NOT evidence that any "
            "provider substituted a model, misrepresented anything, or acted in bad faith.",
            "A shift has many benign explanations: a routine version update, a different serving "
            "backend, load-dependent routing, or the provider not honouring temperature=0.",
            "Calibration TPR rests on ONE arm-pair per positive condition (int4 weight quantization "
            "and fp8 KV precision), not a distribution; a subtler change may not be detected.",
            "Control arms are NEAR-identical (9 of 10 pairs at D = 0.0), so this says little about "
            "how the detector behaves against a genuinely NOISY backend -- the realistic adversary.",
            "One model family, one GPU class, one engine build; greedy decoding only.",
        ],
    }
