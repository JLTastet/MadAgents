# NLO & Matching

Quick reference for NLO computations, jet matching/merging, and EW corrections in MadGraph5_aMC@NLO.

---

## NLO QCD Syntax

Requires a loop-capable model: `import model loop_sm` (not `sm`).

```
generate p p > t t~ [QCD]          # full NLO QCD (real + virtual + subtraction)
generate p p > t t~ [virt=QCD]     # virtual corrections only
generate g g > z z [noborn=QCD]    # loop-induced process (no tree-level Born)
```

- `[QCD]` triggers real-emission, one-loop virtual, and FKS subtraction terms.
- `[noborn=QCD]` is for genuinely loop-induced processes (e.g., gg -> ZZ, gg -> HH). MG5 trusts the user -- if a Born actually exists, results are silently wrong.
- `[noborn=QCD]` applies globally to ALL subprocesses. Do not mix loop-induced and Born-containing subprocesses in one run.

**Details ->** [NLO Computations](detailed/06_nlo_computations.md)

---

## MC@NLO: NLO + Parton Shower

MC@NLO subtracts the shower approximation from the NLO calculation, then hands events to Pythia8.

```
import model loop_sm
generate p p > t t~ [QCD]
output ttbar_NLO
launch ttbar_NLO
  shower=PYTHIA8
  set run_card nevents 10000
```

- **Negative weights** are inherent (typically 10-30% of events). Not a bug. Every event must be filled into histograms with its signed weight.
- **Reducing negative weights** — two complementary techniques:
  - `set run_card mcatnlo_delta True` — MC@NLO-Δ method, negligible CPU cost, requires Pythia8 ≥ 8.309.
  - `set run_card folding 4 4 1` — more sampling in FKS subtraction variables (values: 1, 2, 4, or 8 per variable; runtime scales linearly).
- NLO events without a shower are not suitable for experimental comparison.

**Details ->** [NLO Computations](detailed/06_nlo_computations.md)

---

## MLM Matching (LO Multi-Jet Merging)

Merges LO matrix-element samples of different jet multiplicities with the parton shower, avoiding double-counting.

```
import model sm
generate p p > z @0
add process p p > z j @1
add process p p > z j j @2
output z_matched
launch z_matched
  shower=PYTHIA8
  set run_card ickkw 1
  set run_card xqcut 20
  set run_card maxjetflavor 4
  set pythia8_card JetMatching:qCut 30
  set pythia8_card JetMatching:nJetMax 2
```

| Parameter | Where | Guidance |
|-----------|-------|---------|
| `ickkw` | run_card | `1` for MLM |
| `xqcut` | run_card | ME-level kt cut (GeV). Typical: 10-30 (light), 15-25 (W/Z+jets), 20-40 (tt+jets). **Must be nonzero.** |
| `qCut` | pythia8_card | Shower-side matching scale. Rule: `qCut ~ 1.2-1.5 x xqcut`. Must be > xqcut. |
| `nJetMax` | pythia8_card | Highest `@N` tag used |
| `@N` tags | generate line | Start at `@0`, increment by 1 per extra jet. **Required with ickkw=1.** |

The **post-shower** cross-section (after matching vetoes) is the physical one; the pre-shower sum is not.

**Details ->** [Matching & Merging](detailed/07_matching_merging.md)

---

## FxFx Merging (NLO Multi-Jet Merging)

NLO extension of MLM. Each multiplicity is computed at NLO accuracy.

```
import model loop_sm
generate p p > t t~ [QCD] @0
add process p p > t t~ j [QCD] @1
output ttbar_FxFx
launch ttbar_FxFx
  shower=PYTHIA8
  set run_card ickkw 3
  set run_card nevents 50000
  set pythia8_card JetMatching:doFxFx = on
  set pythia8_card JetMatching:qCutME = 10
  set pythia8_card JetMatching:nJetMax = 1
  set pythia8_card TimeShower:pTmaxMatch = 1
  set pythia8_card SpaceShower:pTmaxMatch = 1
```

- `ickkw = 3` (not 1). Pythia8 needs `doFxFx = on`, `qCutME`, and `pTmaxMatch = 1` for both showers.
- More theoretically consistent than MLM but significantly more expensive.
- **Applicability:** FxFx is designed for processes with a non-QCD hard scale (W/Z/H/tt̄ + jets). For pure QCD multijet production (e.g., inclusive dijets), where jets define the Born process itself, FxFx at the lowest multiplicity is not applicable — use MLM matching with multiple jet multiplicities instead.

**Details ->** [Matching & Merging](detailed/07_matching_merging.md) | [NLO Computations](detailed/06_nlo_computations.md)

---

## DJR Validation

Differential Jet Rate (DJR) plots confirm that matching/merging is working. The DJR measures the kt scale at which an N-jet event transitions to (N-1)-jet.

- Plot log10(d01), log10(d12), etc. across the matching-scale boundary.
- **Good:** Smooth, continuous distributions with no visible feature at log10(qCut).
- **Bad:** A kink, step, or discontinuity at log10(qCut) signals poorly chosen xqcut/qCut values.
- **Uncertainty check:** Vary xqcut by factors of 0.5 and 2 (qCut consistently). Post-shower results should change by < 10%.

**Details ->** [Matching & Merging](detailed/07_matching_merging.md)

---

## Electroweak NLO Corrections

Requires `loop_qcd_qed_sm` model (not shipped by default -- install via `install loop_qcd_qed_sm`).

```
import model loop_qcd_qed_sm
generate p p > e+ e- [QED]            # NLO EW only
generate p p > e+ e- [QCD QED]        # combined NLO QCD + NLO EW
```

- EW Sudakov logarithms produce -10% to -30% corrections at TeV scales, suppressing high-pT tails.
- Real photon emission included; may need a photon-PDF set (e.g., NNPDF3.1luxQED).
- `nlo_mixed_expansion = True` (v3 default) includes mixed QCD-EW contributions. Set `False` for pure terms only.
- NLO EW is significantly slower than NLO QCD due to more diagrams and loop topologies.

**Details ->** [EW NLO Corrections](detailed/25_ew_nlo_corrections.md)

---

## Common Pitfalls

- **Wrong model for NLO QCD:** Using `sm` instead of `loop_sm` with `[QCD]` fails. For EW, need `loop_qcd_qed_sm`.
- **xqcut = 0 with ickkw = 1:** No generation-level cut leads to divergent ME samples and huge pre-shower cross-sections.
- **Missing @N tags with MLM:** Pythia8 reports "no events passed the matching" -- cannot determine jet multiplicities.
- **Single multiplicity with ickkw = 1:** Matching vetoes reject events for missing higher-multiplicity samples. Use `ickkw = 0`.
- **Pole cancellation errors (VBF/VBS):** Set `IRPoleCheckThreshold = -1.0d0` in FKS_params.dat.
- **Mixing loop-induced and Born processes:** Cannot combine `[noborn=QCD]` and `[QCD]` in one run. Generate separately.
- **Tight generation cuts at NLO:** Real-emission phase space differs from Born. Apply tight cuts at analysis level instead.
- **Conflicting matching schemes:** Only one scheme (MLM or FxFx) at a time. Do not mix ickkw values.
- **Non-QCD processes in matched samples:** Matching handles QCD jet multiplicities of a single underlying process. Do not include non-QCD associated production (e.g., X + W/Z/γ) alongside jet multiplicities (X + jets) in the same matched sample — these are different physics processes, not additional jet multiplicities. Generate them separately and combine at analysis level.
- **FxFx for pure QCD jets:** FxFx merging requires a non-QCD hard scale to define the Born process. For inclusive multijet production (dijets, trijets), where QCD jets define the Born itself, FxFx at the lowest multiplicity is not applicable. Use LO MLM matching with multiple jet multiplicities instead.

---

## Cross-References

- [Process Generation](process_generation.md)
- [Configuration](configuration.md)
- [Shower, Detector & Analysis](shower_detector_analysis.md)
