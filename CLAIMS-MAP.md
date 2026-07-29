# CLAIMS-MAP — kvprobe

**Tag: CLEAN. Licence: Apache-2.0.**

This file exists so the CLEAN tag is *auditable* rather than asserted.

## The line

The nearest filed family covers publishing and honouring a served-model identity. Its
independent claim recites, as its terminal steps:

> *"(a) **publishing a claimed identity** of a model to be served … (d) **refusing to serve
> responses** … withholding responses from an output interface."*

Both are **server-side acts**. `kvprobe` is a **client-side detector**: it sends ordinary
requests to a publicly-offered API and compares the responses. It neither publishes an identity
nor serves — nor withholds — any response.

## A wrong first answer, recorded

An earlier pass through this analysis concluded `kvprobe` had become claims-practicing under
that family, on the reasoning that it "operates on served-model identity." That was wrong, and
it is recorded here rather than quietly dropped, because the same over-broad reasoning would
have mis-tagged four other artifacts in this tree. The operative question is never *what is the
tool about* but *which party performs the recited step*. Here, the recited steps are performed
by the thing being measured, not by the thing measuring.

## Claims approached, and the step not performed

| Filed claim family | What it recites | What kvprobe does instead |
|---|---|---|
| Served-identity conformance | publishing a claimed model identity; comparing served behaviour against it; **refusing to serve, or withholding responses from an output interface** | Sends ordinary requests and compares responses. Serves nothing, withholds nothing, publishes no identity. Output is a descriptive report. |
| Calibrated substitution detection wired to admission | deriving a threshold from a control population, then **admitting or refusing traffic** on the comparison | Derives the threshold from a control population and **reports**. There is no traffic path and no admission point in this package. |

## The accusation rail

There is deliberately **no code path that emits an allegation**. Output is descriptive — *"the
fingerprint shifted by Δ at a measured false-positive rate of f"* — and every verdict ships with
the benign explanations attached (a routine version update, a different serving backend,
load-dependent routing, a provider not honouring `temperature=0`).

This is a design constraint, not a disclaimer. A detector that accuses is a detector whose false
positives are defamatory, and its FPR is therefore not a statistic — it is a liability.

## Non-claims

- A shift is **not** evidence that any provider substituted a model, misrepresented anything, or
  acted in bad faith.
- The calibration is measured on **self-hosted ground truth** and supports no claim about any
  commercial provider.
- `kvprobe` measures publicly-offered APIs with ordinary requests within terms of service. It
  does not probe adversarially, attempt to extract system prompts, or evade rate limits.
