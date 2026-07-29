"""kvprobe CLI — descriptive provider fingerprints, never accusations."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

from .detector import NotCalibrated, compare, load_calibration, verdict
from .probe_set import PROBES, probe_sha256


def _post(url, payload, headers, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode()), "LIVE"
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode()[:180]
        except Exception:
            pass
        return None, f"BLOCKED_INFRA: HTTP {e.code} {body}"
    except Exception as ex:
        return None, f"BLOCKED_INFRA: {type(ex).__name__}: {str(ex)[:180]}"


def collect(url, model, key, n, max_tokens=32, sleep=0.3):
    """OpenAI-compatible chat completions. Records which feature set the provider allowed."""
    rows, errors = [], {}
    hdr = {"Authorization": f"Bearer {key}"} if key else {}
    for p in PROBES[:n]:
        d, st = _post(url, {"model": model, "messages": [{"role": "user", "content": p["prompt"]}],
                            "temperature": 0.0, "max_tokens": max_tokens, "logprobs": True,
                            "top_logprobs": 20}, hdr)
        if d is None:
            errors[p["id"]] = st
            if "401" in st or "403" in st:
                break
            continue
        try:
            ch = d["choices"][0]
            text = ch["message"]["content"]
            topk = []
            lp = (ch.get("logprobs") or {}).get("content") or []
            for tok in lp:
                topk.append({t["token"]: t["logprob"] for t in (tok.get("top_logprobs") or [])})
            rows.append({"id": p["id"], "cls": p["cls"], "text": text,
                         "topk_logprobs": topk or None})
        except Exception as ex:
            errors[p["id"]] = f"BLOCKED_INFRA: parse {ex}"
        time.sleep(sleep)
    return rows, errors


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="kvprobe",
        description="Is your provider serving the model you're paying for? Descriptive fingerprints "
                    "with a MEASURED false-positive rate. This tool does not accuse anyone.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrate", help="show the shipped calibration (the FPR that gives verdicts meaning)")
    c.add_argument("--calibration")
    r = sub.add_parser("run", help="probe a provider twice and report self-consistency")
    r.add_argument("--provider", required=True, help="OpenAI-compatible /chat/completions URL")
    r.add_argument("--model", required=True)
    r.add_argument("--api-key-env", default="KVPROBE_API_KEY")
    r.add_argument("--n", type=int, default=len(PROBES))
    r.add_argument("--calibration")
    r.add_argument("--json", action="store_true")

    a = ap.parse_args(argv)
    try:
        cal = load_calibration(a.calibration)
    except NotCalibrated as ex:
        print(f"REFUSING: {ex}", file=sys.stderr)
        return 2

    if a.cmd == "calibrate":
        print(json.dumps({k: cal.get(k) for k in
                          ("tau", "MEASURED_FPR_probe_level", "FPR_probe_level_95pct_upper_bound",
                           "n_probe_comparisons_control", "TPR_int4", "verdict", "honest_limits")},
                         indent=2))
        return 0

    key = os.environ.get(a.api_key_env, "")
    print(f"probe set {probe_sha256()[:12]} · {min(a.n, len(PROBES))} probes · two passes "
          f"(self-consistency at temperature=0)", file=sys.stderr)
    r1, e1 = collect(a.provider, a.model, key, a.n)
    r2, e2 = collect(a.provider, a.model, key, a.n)
    if not r1 or not r2:
        out = {"status": "BLOCKED_INFRA", "errors": {**e1, **e2},
               "note": "provider did not answer; nothing is inferred from a failed probe"}
        print(json.dumps(out, indent=2))
        return 1
    stat = compare(r1, r2)
    v = verdict(stat, cal)
    v["provider_feature_set_allowed"] = stat.get("feature_set")
    v["probe_set_sha256"] = probe_sha256()
    v["n_probes_answered"] = stat.get("n")
    if a.json:
        print(json.dumps({"statistic": stat, "verdict": v}, indent=2))
    else:
        print(f"\n  probes answered .......... {stat['n']}")
        print(f"  feature set allowed ...... {stat['feature_set']}")
        print(f"  self-consistency ......... {stat['top1_agreement_rate']:.3f}  (D={stat['D']})")
        print(f"  tau (from sealed rule) ... {v['tau']}")
        print(f"  measured FPR ............. {v['calibrated_FPR']} "
              f"(95% upper bound ~{v['FPR_95pct_upper_bound']}, n={v['n_control_comparisons']})")
        print(f"\n  {v['statement']}\n")
        for lim in v["interpretation_limits"]:
            print(f"  · {lim}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
