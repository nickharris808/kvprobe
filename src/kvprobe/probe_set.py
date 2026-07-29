"""probe_set.py — THE SEALED PROBE SET shared by P1 (black-box audit) and P2 (determinism).

Everything downstream depends on this set being FIXED BEFORE ANY DATA IS SEEN. The detector's
false-positive rate is only meaningful if the probes could not have been chosen to produce it, so
the set is generated deterministically here and its sha256 is sealed into
`specs/blackbox_prereg_sealed.json` / `specs/determinism_prereg_sealed.json` and committed BEFORE
the first measured run. Adding or removing a probe after that invalidates the FPR — if the set must
change, re-seal under a new version and say so.

DESIGN. Probes are chosen to spread across the axes a precision change is most likely to perturb,
without being adversarial to any provider (these are ordinary requests; P1 measures publicly-offered
APIs descriptively and within ToS):

  factual      — short, low-entropy continuations; a substituted/quantized model tends to keep the
                 top-1 token but shift the logprob mass
  arithmetic   — multi-step, error-compounding; argmax divergence tends to appear at a specific step
  code         — highly structured, tokenizer-sensitive
  longform     — many decode steps ⇒ the first-divergence index becomes informative
  ambiguous    — deliberately near-tie continuations, where a small numeric perturbation is most
                 likely to flip the argmax (the most sensitive detector feature)

STDLIB ONLY, deterministic, no network. `probe_sha256()` is the identity that gets sealed.
"""
from __future__ import annotations

import hashlib
import json

VERSION = "probe_set_v1"

# --- the frozen probes. DO NOT EDIT after sealing; add a new VERSION instead. ---
PROBES: list[dict] = [
    # factual (10)
    {"id": "fact_01", "cls": "factual", "prompt": "The capital city of Australia is"},
    {"id": "fact_02", "cls": "factual", "prompt": "Water boils at a temperature of"},
    {"id": "fact_03", "cls": "factual", "prompt": "The chemical symbol for iron is"},
    {"id": "fact_04", "cls": "factual", "prompt": "The largest planet in our solar system is"},
    {"id": "fact_05", "cls": "factual", "prompt": "The author of the novel Nineteen Eighty-Four is"},
    {"id": "fact_06", "cls": "factual", "prompt": "The speed of light in a vacuum is approximately"},
    {"id": "fact_07", "cls": "factual", "prompt": "The longest river in South America is"},
    {"id": "fact_08", "cls": "factual", "prompt": "The currency used in Japan is called the"},
    {"id": "fact_09", "cls": "factual", "prompt": "DNA is an abbreviation that stands for"},
    {"id": "fact_10", "cls": "factual", "prompt": "The first element on the periodic table is"},
    # arithmetic (10) — error-compounding, reveals WHERE divergence starts
    {"id": "arith_01", "cls": "arithmetic", "prompt": "Compute step by step: 17 * 23 + 41 ="},
    {"id": "arith_02", "cls": "arithmetic", "prompt": "Compute step by step: 128 / 4 - 7 ="},
    {"id": "arith_03", "cls": "arithmetic", "prompt": "Compute step by step: 3^5 + 2^7 ="},
    {"id": "arith_04", "cls": "arithmetic", "prompt": "Compute step by step: 1234 + 5678 ="},
    {"id": "arith_05", "cls": "arithmetic", "prompt": "Compute step by step: 91 * 11 - 100 ="},
    {"id": "arith_06", "cls": "arithmetic", "prompt": "If a train travels 60 km in 45 minutes, its speed in km/h is"},
    {"id": "arith_07", "cls": "arithmetic", "prompt": "The sum of the first 20 positive integers is"},
    {"id": "arith_08", "cls": "arithmetic", "prompt": "Compute step by step: 45% of 880 ="},
    {"id": "arith_09", "cls": "arithmetic", "prompt": "Compute step by step: (14 + 6) * (9 - 4) ="},
    {"id": "arith_10", "cls": "arithmetic", "prompt": "The greatest common divisor of 84 and 126 is"},
    # code (8) — structured, tokenizer-sensitive
    {"id": "code_01", "cls": "code", "prompt": "def fibonacci(n):\n    \"\"\"Return the nth Fibonacci number.\"\"\"\n"},
    {"id": "code_02", "cls": "code", "prompt": "def is_prime(n):\n    \"\"\"Return True if n is prime.\"\"\"\n"},
    {"id": "code_03", "cls": "code", "prompt": "SELECT name, COUNT(*) FROM orders GROUP BY"},
    {"id": "code_04", "cls": "code", "prompt": "import json\n\ndef load_config(path):\n"},
    {"id": "code_05", "cls": "code", "prompt": "def binary_search(arr, target):\n    lo, hi = 0, len(arr) - 1\n"},
    {"id": "code_06", "cls": "code", "prompt": "class Stack:\n    def __init__(self):\n"},
    {"id": "code_07", "cls": "code", "prompt": "def reverse_words(s: str) -> str:\n"},
    {"id": "code_08", "cls": "code", "prompt": "for i in range(10):\n    if i % 2 == 0:\n"},
    # longform (6) — many decode steps ⇒ first-divergence index is informative
    {"id": "long_01", "cls": "longform", "prompt": "Explain how photosynthesis works, in three sentences."},
    {"id": "long_02", "cls": "longform", "prompt": "Summarize the causes of the First World War."},
    {"id": "long_03", "cls": "longform", "prompt": "Describe how a refrigerator keeps food cold."},
    {"id": "long_04", "cls": "longform", "prompt": "Explain the difference between weather and climate."},
    {"id": "long_05", "cls": "longform", "prompt": "Describe the water cycle in simple terms."},
    {"id": "long_06", "cls": "longform", "prompt": "Explain what a compiler does, step by step."},
    # ambiguous (6) — near-tie continuations: the most numerically sensitive probes
    {"id": "amb_01", "cls": "ambiguous", "prompt": "The best colour is"},
    {"id": "amb_02", "cls": "ambiguous", "prompt": "My favourite season is"},
    {"id": "amb_03", "cls": "ambiguous", "prompt": "A good name for a cat is"},
    {"id": "amb_04", "cls": "ambiguous", "prompt": "The number I am thinking of is"},
    {"id": "amb_05", "cls": "ambiguous", "prompt": "Pick a random fruit:"},
    {"id": "amb_06", "cls": "ambiguous", "prompt": "The next word in this sentence is"},
]

CLASSES = sorted({p["cls"] for p in PROBES})


def probe_sha256() -> str:
    """The sealed identity of the probe set. Any edit changes this and invalidates prior seals."""
    payload = {"version": VERSION,
               "probes": [{"id": p["id"], "cls": p["cls"], "prompt": p["prompt"]} for p in PROBES]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def summary() -> dict:
    counts: dict = {}
    for p in PROBES:
        counts[p["cls"]] = counts.get(p["cls"], 0) + 1
    return {"version": VERSION, "n_probes": len(PROBES), "classes": CLASSES,
            "per_class": counts, "probe_sha256": probe_sha256()}


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
