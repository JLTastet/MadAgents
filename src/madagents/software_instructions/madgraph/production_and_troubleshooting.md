# Production & Troubleshooting

Quick reference for installation, gridpacks, systematics, non-pp colliders, biased generation, and common errors.

---

## Installation

```bash
wget https://launchpad.net/mg5amcnlo/3.0/3.6.x/+download/MG5_aMC_v3.6.7.tar.gz
tar xzf MG5_aMC_v3.6.7.tar.gz
cd MG5_aMC_v3_6_7 && ./bin/mg5_aMC
```

Inside the MG5 prompt, install optional tools:

```
install pythia8          # parton shower & hadronization
install Delphes          # fast detector simulation
install lhapdf6          # PDF library (recommended for production)
install MadAnalysis5     # analysis framework
```

Pre-installed tools can be linked via paths in `input/mg5_configuration.txt`. Without LHAPDF, MG5 falls back to a limited built-in PDF set.

**Details ->** [Installation & Setup](detailed/01_installation_setup.md)

---

## Gridpack Creation

A gridpack is a portable tarball containing pre-compiled code and optimized integration grids for fast event generation on clusters.

**Workflow:** set `gridpack = True` in run_card -> MG5 integrates and produces a tarball -> copy to cluster nodes -> each job runs `./run.sh <nevents> <seed>`.

| Aspect | Notes |
|--------|-------|
| Create | `set run_card gridpack True` during `launch` |
| Run | `tar xzf run_01_gridpack.tar.gz && cd madevent && ./run.sh 10000 42` |
| Seeds | Each job needs a unique seed; use job array index or sequential integers |
| Modify | Generation cuts can be edited in the untarred `Cards/run_card.dat`; physics model changes require a new gridpack |

**Limitations:** Parameters frozen at creation time. Limited NLO support. Parton-level LHE only (shower separately). Size: 100 MB -- several GB.

**Details ->** [Gridpacks](detailed/14_gridpacks.md)

---

## Systematics & Reweighting

Enable on-the-fly scale and PDF reweighting (no regeneration needed):

```
set run_card use_syst True
set run_card sys_scalefact 0.5 1 2        # 7-point scale envelope
set run_card sys_pdf 303400               # LHAPDF ID for PDF error set
```

- **Scale variations:** 7-point envelope -- vary mu_R, mu_F by factors 0.5 and 2, excluding extreme anti-correlated pairs. Typical uncertainty: LO +/-30-50%, NLO +/-10-20%.
- **PDF uncertainties:** Hessian sets (CT10, MMHT) use eigenvector differences; MC replica sets (NNPDF) use the standard deviation across members. Typical: +/-3-15%.
- **Accessing weights:** Stored in LHE `<rwgt>` blocks as `<wgt id='XXXX'>`. The ID-to-variation mapping is in the LHE file header.
- **Matching uncertainty:** Requires separate generations with varied `xqcut` (cannot be reweighted on-the-fly).
- **Interference limitation:** On-the-fly scale reweighting (`use_syst`) is unreliable for cross-sections dominated by interference between different coupling orders (e.g., SM–EFT interference). For such processes, estimate scale uncertainties by running separate generations with different `scalefact` values.

**Details ->** [Systematics & Reweighting](detailed/13_systematics_reweighting.md)

---

## Common Errors and Fixes

| Error / Symptom | Cause | Fix |
|-----------------|-------|-----|
| "0 diagrams" / no amplitudes | Conservation-law violation, wrong model, or coupling orders too restrictive | Check charge/color conservation; use `heft` for gg->h; relax `QCD=`/`QED=` |
| Cross-section too small | Overly tight generation cuts, wrong beam energy or beam type | Relax `ptj`/`ptl`/`mxx_min_pdg`; verify `ebeam` and `lpp` |
| Cross-section too large | Physical (QCD), missing cuts, matching misconfiguration | Add `ptj` cut for jet processes; use post-shower cross-section with matching |
| "Poles do not cancel" (NLO) | VBF/VBS pentagon filtering | Set `IRPoleCheckThreshold = -1.0d0` in `FKS_params.dat` |
| Fortran line-length error | Complex BSM model + helicity recycling | `set run_card hel_recycling False`, or upgrade to MG5 v3.4.2+ |
| Large negative weights (NLO) | MC@NLO method (10-30% is typical) | Increase `folding` values (e.g., `set run_card folding 4 4 1`); increase statistics |
| "No events passed matching" | Missing `@N` tags, single multiplicity with `ickkw=1`, or `qCut` too large | Add `@0`, `@1` tags; set `qCut ~ 1.2-1.5 x xqcut` |
| Too few events generated | `xqcut=0` with matching, or very tight cuts | Set `xqcut` to 15-30 GeV; relax phase-space cuts |
| "fail to reach target" | Low unweighting efficiency: missing/loose cuts, poor phase-space mapping, zero widths | Add generation cuts (`ptj`, `draj`, etc.); try `sde_strategy = 2`; fix particle widths; try different `iseed` |
| SIGFPE (floating-point exception) | Loop-reduction library numerics, strict compiler FPE traps, kinematic edge cases | Remove `-ffpe-trap` from `Source/make_opts`; try `sde_strategy = 1`; recompile dependencies; upgrade MG5 |
| "failed to reduce to color indices" | Bug in leading-color flow assignment; subprocess grouping conflicts | Upgrade MG5 to latest release; try toggling `group_subprocesses` |
| "BR larger than one" (MadSpin) | Total width in param_card too small | Run `compute_widths <particle>` |
| Slow generation (custom model) | Massive light quarks prevent subprocess grouping | Use a restriction file setting u/d/s/c masses to zero |

**Details ->** [Troubleshooting](detailed/16_troubleshooting.md)

---

## Lepton & Photon Colliders

Beam type is set by `lpp1`/`lpp2` in the run_card:

| `lpp` | Beam | Notes |
|-------|------|-------|
| 0 | Fixed-energy lepton | No PDF/ISR. Set `pdlabel none`. |
| +/-1 | Proton / antiproton | Standard hadron collider (default). |
| +/-2 | EPA photon from (anti)proton | Elastic photon-photon or photon-proton processes. |
| +/-3 | Electron / positron with ISR | Includes ISR structure functions. |
| +/-4 | Muon / antimuon with ISR | For muon collider studies. |

- **e+e- (no ISR):** `lpp1=0, lpp2=0, pdlabel none, ebeam1=ebeam2=sqrt(s)/2`.
- **e+e- (with ISR):** `lpp1=-3, lpp2=3` for more realistic beam spectrum.
- **Muon collider:** `lpp1=-4, lpp2=4`.
- **Photon fusion (EPA at LHC):** `lpp1=2, lpp2=2`.
- **Beam polarization:** `polbeam1`, `polbeam2` in range [-100, +100] (only for `lpp=0`). Example: ILC-like with `polbeam1=-80, polbeam2=30`.

**Details ->** [Lepton & Photon Colliders](detailed/22_lepton_photon_colliders.md)

---

## Biased Event Generation

Enhances poorly-populated phase-space regions (e.g., high-pT tails) while preserving correct weighted distributions.

```
set run_card bias_module ptj_bias
set run_card bias_parameters {ptj_bias_target_ptj: 500.0, ptj_bias_enhancement_power: 4.0}
```

- **`ptj_bias`** (built-in): enhances leading-jet high-pT tail. `enhancement_power` controls strength.
- **Custom modules:** Write a Fortran `bias_wgt(p, original_weight, bias_weight)` subroutine; place under `<PROC_DIR>/Source/BIAS/` or specify full path.
- **Cross-section:** With `impact_xsec = .False.` (default), the reported cross-section remains unbiased; only the event distribution changes.
- Histograms **must** use event weights; unweighted histograms show the biased distribution.

**Details ->** [Biased Event Generation](detailed/24_biased_event_generation.md)

---

## Custom Cuts and Subprocess Grouping

MadGraph groups subprocesses with identical spin/color/mass structure (`group_subprocesses = True` by default), dramatically reducing integration time. Custom phase-space cuts can break the symmetries this relies on.

**Two methods for custom cuts:**

- **`custom_fcts`** (recommended): `set run_card custom_fcts ['/path/to/my_cuts.f']` — the file defines a `dummy_cuts(p)` Fortran function.
- **Edit `SubProcesses/dummy_fct.f`** directly in the process directory.

**When to disable grouping:** If your custom cuts distinguish between grouped subprocesses (e.g., flavor-dependent cuts, asymmetric rapidity cuts), the cross section will be **silently wrong**. Set `group_subprocesses False` before `generate`/`output` — it is a generation-time MG5 option, not a run_card parameter:

```
set group_subprocesses False
generate p p > mu+ mu- j
output my_process
```

Standard run_card cuts adjust both the integrand and the phase-space integrator; custom cuts only modify the integrand, so tight custom cuts reduce integration efficiency.

**Details ->** [Cards & Parameters — Custom Cuts](detailed/04_cards_and_parameters.md) | [Troubleshooting](detailed/16_troubleshooting.md)

## Nearly Massless Final-State Particles

BSM models with very light particles (dark photons, ALPs, light scalars) coupling to heavier final-state particles produce **soft and collinear singularities** — the matrix element diverges when the light particle becomes soft or collinear. This is NOT a narrow-resonance or unweighting-efficiency problem; decay-chain syntax does not help.

**Symptoms:** "fail to reach target" with very few events, extremely slow generation, unstable cross-section.

**Fixes:** Apply a pT cut via `pt_min_pdg` (e.g., `{9000005: 5.0}`) to regulate the soft region, and a deltaR separation via custom cuts (`custom_fcts`) to regulate the collinear region. If custom cuts break symmetries, disable `group_subprocesses`. For marginal cases, try `sde_strategy 2` or the `bias_module`.

**Details ->** [Troubleshooting](detailed/16_troubleshooting.md)

## Common Pitfalls

- **Forgetting `lpp=0` for e+e-:** Proton PDFs are applied silently, giving wrong results.
- **NLO requires `loop_sm`:** Using `import model sm` for NLO processes fails; use `import model loop_sm`.
- **Matching without `@N` tags:** MLM matching silently discards all events if multiplicity labels are missing.
- **Gridpack parameter freeze:** Physics parameters cannot be changed after gridpack creation; only generation cuts can be edited.
- **Biased events without weights:** Filling unweighted histograms from biased samples produces unphysical distributions.
- **`xqcut=0` with `ickkw=1`:** Causes divergent soft/collinear integration and extremely inefficient unweighting.

---

## Cross-References

- [Configuration](configuration.md) -- cards, scripted execution, PDFs, scales, parameter scans
- [NLO & Matching](nlo_and_matching.md) -- NLO computations, MLM/FxFx matching setup
- [Shower, Detector & Analysis](shower_detector_analysis.md) -- Pythia8, Delphes, MadAnalysis5
