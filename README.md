# kvprobe

**Is your LLM provider serving the model you're paying for?**

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](pyproject.toml)

A model-substitution detector whose **false-positive rate was measured**, not assumed.

## Install

**Not yet on PyPI.** The command below is the one that works today. It installs from this repository, pinned to a tag.

```bash
pip install "git+https://github.com/nickharris808/kvprobe@v0.2.0"
```

`pip install kvprobe` is the intended command once the name is published. **It 404s today**, which is why it is not the first step above. The tag is pinned rather than `@main` so a reader installs the exact code this README documents.

## 30-second quickstart

```bash
kvprobe calibrate            # print the shipped calibration, limits and all
export KVPROBE_API_KEY=...
kvprobe run --provider https://api.example.com/v1/chat/completions --model some-model
```

```
  probes answered .......... 40
  feature set allowed ...... logprobs+text
  self-consistency ......... 1.000  (D=0.0)
  tau (from sealed rule) ... 0.025
  measured FPR ............. 0.01  (400 control comparisons, 10 pairs)

  no fingerprint shift detected (D=0.0 <= tau=0.025) at FPR 0.01
```

## Why this exists

Threads claiming *"my provider quietly swapped in a quantized model"* appear constantly, and almost
none carry evidence that would survive scrutiny. The hard part isn't noticing that two responses
differ — it's knowing **how often your method cries wolf when nothing changed**. That number is only
obtainable on ground truth you control.

So `kvprobe` ships its calibration and **refuses to emit a verdict without one**.

## The calibration (run it yourself: `kvprobe calibrate`)

Measured on self-hosted ground truth — same model, same GPU, only precision varied:

| arm pair | statistic `D` | probes differing |
|---|---|---|
| **control** fp16-vs-fp16 (**10 pairs** from 5 arms, differing seed *and* batch composition) | **0.0 – 0.025** | 0–1 / 40 |
| **positive** fp16-vs-**fp8 KV cache** | **1.0** | **40 / 40** |
| **positive** fp16-vs-int4-AWQ | **0.825** | **33 / 40** |

**τ = 0.025** (derived from a threshold *rule* sealed before any data — not chosen after seeing
results) · **measured probe-level FPR = 0.01** over 400 control comparisons · **TPR = 1.0** on both
positive arms.

**This is the second version of this calibration. The first had four defects that we found and
fixed** — worth reading, because they are the failure modes any detector calibration can have:

1. **Our own seal was violated and we shipped anyway.** The pre-registration required a minimum of
   **10** control pairs; the first run had 4 arms → C(4,2) = **6**, and was declared usable. Fixed
   by adding a 5th fp16 arm: C(5,2) = 10 satisfies the seal *as written*.
2. **The "held-out" FPR was arithmetically forced.** With all six control `D` values tied at 0.0,
   leave-one-pair-out evaluates `0 > 0` six times — it would report 0.0 for *any* tied set. With
   five arms the control values are no longer tied, so the test is a real comparison.
3. **τ = 0 had zero margin** — one differing probe out of 40 triggered a detection. τ is now 0.025,
   from the same sealed rule applied to genuine control spread.
4. **"Zero false positives" overstated precision.** The FPR is now a real non-zero measured rate
   (**0.01**), not a zero needing a rule-of-three bound to interpret.

Full history: `oss/AUDIT.md` §F4.

**TPR now covers a KV-precision change, not just a weight swap.** The fp8-KV arm previously failed
to boot, which is the only reason we used to say *"int4 weight quantization only — do not
generalize."* It now boots and is detected at **D = 1.0, 40/40 probes**. That was the *subtler*
substitution and the one that actually mattered.

**One thing the 5th arm revealed that we did not go looking for:** `fp16_r4` (batch_pad = 16) differs
from every other fp16 arm on **1 of 40 probes** — a genuine top-1 flip caused by **co-batch
composition at temperature 0**. Those arms vary seed *and* batch_pad together and seed should not
matter at greedy decoding, so this is one observation, not a controlled attribution. We report it
because it cuts *against* a convenient claim of ours elsewhere in this repo.

## What this tool will not do

**It does not accuse anyone**, and that isn't just a README promise — there is no code path that emits
an allegation. Output is descriptive: *"fingerprint shifted by Δ at FPR f."* Every verdict carries:

- A shift has **many benign explanations**: a routine version update, a different serving backend,
  load-dependent routing, or the provider simply not honouring `temperature=0`.
- TPR is established for **int4 weight quantization and fp8 KV-cache precision** — one arm-pair each,
  not a distribution. A change subtler than either may still go undetected.
- The control arms are **near-identical** (9 of 10 pairs at D = 0.0), so this says little about how
  the detector behaves against a genuinely **noisy** backend — the realistic adversary.
- One model family, one GPU class, one engine build. Generalization is untested.
- Greedy decoding only. Says nothing about sampled decoding.

It measures **publicly-offered APIs with ordinary requests, within terms of service**. It does not
probe adversarially, attempt to extract system prompts, or evade rate limits.

## How it works

40 frozen probes across 5 classes — factual, arithmetic, code, longform, and deliberately near-tie
*ambiguous* prompts (the most numerically sensitive). The probe set is content-addressed
(`probe_sha256`); editing it invalidates the calibration, by design.

Each provider is probed **twice** at `temperature=0`, so the primary readout is **self-consistency**.
That is interesting on its own: a provider that isn't self-consistent at temperature 0 cannot be
audited by output comparison at all — and knowing which providers are in that class is a finding.

Where a provider exposes no logprobs, the detector **degrades to text-only features** and records that
it did — the feature set each provider allowed is part of the output, never silently assumed.

## Provenance

Every number above resolves to a certificate: `results/data/blackbox/detector_calibration.json`,
hashed into a signed Merkle root. `kvprobe calibrate` prints the certificate, including its honest
limits, so you can check the claim rather than trust it.

## The commercial edition

`kvprobe` **measures and reports**. It is a client-side detector: it neither publishes a model
identity nor serves or withholds any response, which is why it is CLEAN — see
[`CLAIMS-MAP.md`](CLAIMS-MAP.md).

The server-side conformance apparatus — publishing a claimed identity and honouring it at the
serving path — is the licensed offering. **Reading is free. Enforcing is licensed.**

## License

Apache-2.0. Stdlib-only by design — an audit tool should be readable end to end.

<!-- HONEST-SCOPE -->
## Honest scope — what a passing run proves, and what it does not

The two halves are inseparable. A tool that states only the first half is marketing.

**It proves:**

- whether two responses from a provider differ on a sealed 40-probe set, at a threshold derived from a rule fixed before any data
- the measured false-positive rate of that decision on self-hosted ground truth

**It does NOT prove:**

- that a provider swapped your model. A shift has many benign explanations: a version update, a different backend, load-dependent routing, or a provider not honouring temperature=0
- that an undetected change did not happen. TPR is established for int4 weights and fp8 KV — one arm-pair each, not a distribution
- anything about sampled decoding, or about model families other than the one calibrated

Full CLI reference, generated from `--help`: [`docs/CLI.md`](docs/CLI.md)
<!-- /HONEST-SCOPE -->

## Worked example — the calibration, and why it is the whole product

`kvprobe calibrate` prints the sealed operating point and, more importantly, everything that
operating point does **not** cover. Run it before you run anything else:

```console
$ kvprobe calibrate
{
  "tau": 0.025,
  "MEASURED_FPR_probe_level": 0.01,
  "FPR_probe_level_95pct_upper_bound": 0.0075,
  "n_probe_comparisons_control": 400,
  "TPR_int4": 1.0,
  "verdict": "USABLE — separates precision on ground truth at the sealed operating point",
  "honest_limits": [
    "only 10 control pairs — the pairwise FPR is coarse; the probe-level rate (n=400) is the
     statistically meaningful one",
    "ground truth is ONE model family on ONE GPU class; generalization across families/hardware
     is untested",
    "the fp8-KV arm FAILED to boot, so TPR is established for int4 weight-quantization ONLY.
     A detector that catches a 4-bit weight swap need not catch a subtler KV-precision change —
     do NOT generalize the TPR.",
    "the control arms being EXACTLY identical also means this ground truth cannot tell us how the
     detector behaves against a provider whose backend is merely NOISY rather than substituted"
  ]
}
```

**Those five limits are the reason to trust the number.** A detector shipped without a measured
false-positive rate is a detector whose "accuracy" is unfalsifiable — and one shipped without its
limits invites you to generalize a result it never established.

The ground truth behind it is published as
[`llm-precision-fingerprints`](https://huggingface.co/datasets/nickh007/llm-precision-fingerprints)
— 280 rows including **five same-precision control arms**, so you can recompute the FPR yourself
rather than taking ours.

## Contributing

Bug reports and pull requests welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

**A false accusation is a defect of equal severity to a missed detection.** If this tool flags something correct, open an issue with the input and the verdict you expected: over-refusal trains people to bypass refusals, which destroys the tool.

Citation metadata is in [CITATION.cff](CITATION.cff).

<!-- PORTFOLIO -->
---

## The rest of the portfolio

25 artifacts, one idea: **a measurement you cannot check is a press release.** Every tool
here reports; none of them gates.

**Tools**

| | |
|---|---|
| [`abstain-bench`](https://github.com/nickharris808/abstain-bench) | how often does a verifier pass input it could not check? |
| [`evidence`](https://github.com/nickharris808/evidence) | run the whole portfolio over your repo — the weakest leg, never the mean |
| [`floorgen`](https://github.com/nickharris808/floorgen) | what must your system remember? an exact lower bound |
| [`formal-proof-mcp`](https://github.com/nickharris808/formal-proof-mcp) | a proof kernel for your coding agent |
| [`gatecount`](https://github.com/nickharris808/gatecount) | exactly how many states does removing this check admit? |
| [`gridlock`](https://github.com/nickharris808/gridlock) | certify a wait-for relation cannot wedge |
| [`honestbench`](https://github.com/nickharris808/honestbench) | measure your CI's escape rate |
| [`kvleak`](https://github.com/nickharris808/kvleak) | cross-tenant leak scanner |
| [`kvprobe`](https://github.com/nickharris808/kvprobe) | model-substitution detector with a measured FPR ← you are here |
| [`preregister`](https://github.com/nickharris808/preregister) | refuses to seal a plan whose conclusion is already fixed |
| [`proof-carrying-ci`](https://github.com/nickharris808/proof-carrying-ci) | the whole portfolio as one CI check, with SARIF |
| [`proof-to-code-drift`](https://github.com/nickharris808/proof-to-code-drift) | fail the build when the proof stops matching |
| [`sf-verify`](https://github.com/nickharris808/sf-verify) | re-derive admission decisions offline |
| [`signoff-cert`](https://github.com/nickharris808/signoff-cert) | certificates that carry their own false-pass bound |
| [`tokencount`](https://github.com/nickharris808/tokencount) | a token count both parties can recompute |

**Benchmarks** — each recomputes one of our own published numbers from its certificate

| | |
|---|---|
| [`illusion-bench`](https://github.com/nickharris808/illusion-bench) | how many broken kernels does your oracle admit? |
| [`kv-reuse-econ-bench`](https://github.com/nickharris808/kv-reuse-econ-bench) | recompute our economics headline |
| [`llm-tenant-isolation-bench`](https://github.com/nickharris808/llm-tenant-isolation-bench) | recompute our isolation figures |

**Datasets**

| | |
|---|---|
| [`abstain-corpus`](https://huggingface.co/datasets/nickh007/abstain-corpus) | 32 inputs a verifier must NOT pass |
| [`kv-reuse-econ-traces`](https://huggingface.co/datasets/nickh007/kv-reuse-econ-traces) | per-workload reuse accounting + the closed form |
| [`kv-tenant-isolation-bench`](https://huggingface.co/datasets/nickh007/kv-tenant-isolation-bench) | isolation observations, uninterpretable rows included |
| [`llm-precision-fingerprints`](https://huggingface.co/datasets/nickh007/llm-precision-fingerprints) | precision-labelled logprobs with a negative control |

**Try it in a browser** — no install, no GPU

| | |
|---|---|
| [`negative-results-atlas`](https://huggingface.co/spaces/nickh007/negative-results-atlas) | ten claims we took back |
| [`tenant-leak-demo`](https://huggingface.co/spaces/nickh007/tenant-leak-demo) | the residency calculator |
| [`wait-for-visualiser`](https://huggingface.co/spaces/nickh007/wait-for-visualiser) | paste a wait-for graph, see the cycle |

### Documentation

Everything above, explained in one place: **<https://nickharris808.github.io/evidence-docs/>** —
the [tutorial](https://nickharris808.github.io/evidence-docs/start/tutorial/),
[what this proves and what it does not](https://nickharris808.github.io/evidence-docs/concepts/what-this-proves/),
and a [CLI reference](https://nickharris808.github.io/evidence-docs/reference/cli/) generated by
running `--help` on every published command.

### The commercial edition

Everything above is **measure-only** and Apache-2.0: it tells you what is true and never acts on
it. The **enforcement** side — binding a partition key at the admission decision, the compiled gate
corpus, and the certificate-*issuing* faucet — is covered by filed patents and licensed separately.

**Reading is free. Enforcing is licensed.**
<!-- /PORTFOLIO -->
