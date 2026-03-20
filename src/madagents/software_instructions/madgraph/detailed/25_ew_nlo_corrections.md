# 25 — Electroweak NLO Corrections

MadGraph5_aMC@NLO supports automated computation of NLO electroweak (EW) corrections in addition to NLO QCD corrections. EW corrections are important at high energies where EW Sudakov logarithms can produce corrections of order 10% or more, comparable to residual QCD scale uncertainties.

## Requirements

NLO EW computations require:

1. A **loop-capable model with EW loops**: `loop_qcd_qed_sm` (not the standard `loop_sm` which only has QCD loops).
2. The appropriate bracket syntax on the `generate` line.
3. LHAPDF with a PDF set that includes a photon PDF (if real photon emission diagrams contribute).

**Important**: The `loop_qcd_qed_sm` model is not shipped with the default MG5 installation. It must be installed separately:

```
install loop_qcd_qed_sm
```

This model includes both QCD and QED loop amplitudes, UV counterterms, and R2 rational terms needed for NLO EW calculations.

Available restriction files for `loop_qcd_qed_sm`:
- `full`: No restrictions
- `no_widths`: Zero widths
- `with_b_mass`: Massive b-quark
- `with_b_mass_no_widths`: Massive b-quark with zero widths

A variant `loop_qcd_qed_sm_Gmu` uses the Gmu input scheme (Fermi constant as input instead of alpha_EW), with restrictions: `ckm`, `full`, `no_widths`.

## NLO EW Syntax

The bracket syntax for NLO corrections specifies which coupling types to include:

```
import model loop_qcd_qed_sm
generate p p > e+ e- [QCD]            # NLO QCD only (same as with loop_sm)
generate p p > e+ e- [QED]            # NLO EW only
generate p p > e+ e- [QCD QED]        # combined NLO QCD + NLO EW
```

The `[QCD QED]` syntax computes the full NLO corrections including both QCD and EW virtual loops, as well as real emission of gluons and photons.

## The `nlo_mixed_expansion` Option

`nlo_mixed_expansion` is an **MG5 interface-level option** (not a run_card parameter). It must be set via the `set` command **before** `generate` and `output`:

```
set nlo_mixed_expansion True      # default in MG5 v3
import model loop_qcd_qed_sm
generate p p > e+ e- [QCD QED]
output my_nlo_ew
```

It appears alongside other interface options such as `complex_mass_scheme` and `loop_optimized_output`. You can check its current value with `display options`.

| Value | Behavior |
|-------|----------|
| `True` (default) | Include contributions from all coupling-order combinations that contribute at the requested perturbative order (mixed QCD-EW terms included). |
| `False` | Include only the "pure" NLO QCD or NLO EW terms; mixed-order interference contributions are dropped. |

**Key points**:
- This is **not** a run_card parameter — do not look for it in `run_card.dat`. It is stored in the process metadata (banner) once the process is output.
- Setting it **after** `output` has no effect on an already-generated process directory.
- It is also relevant for pure QCD NLO computations where the Born process has mixed QCD-EW couplings (e.g., single-top production), as it controls whether pentagon loops with non-QCD particles are included.

See [NLO Computations](06_nlo_computations.md) for additional details on NLO QCD workflows.

## Coupling Order Control

For processes with multiple coupling types, the `QED` and `QCD` coupling order constraints control which Born-level diagrams are included:

```
generate p p > e+ e- QED=2 QCD=0 [QCD]     # Drell-Yan at NLO QCD (Born is pure EW)
generate p p > e+ e- j QED<=3 QCD<=1 [QCD]  # W/Z+jet at NLO QCD
```

The squared coupling order syntax (`QCD^2`, `QED^2`) can also be used to select specific interference patterns. See [Advanced Syntax](17_advanced_syntax.md) for details.

## Physics of EW Corrections

### EW Sudakov Logarithms

At high energies (Q >> M_W), virtual EW corrections produce large negative double logarithms:

```
delta_EW ~ -alpha/(4*pi*sin^2(theta_W)) * log^2(Q^2/M_W^2)
```

These Sudakov logarithms can reach -10% to -30% at TeV-scale energies, significantly suppressing high-pT tails in distributions. This is particularly important for:
- High-mass Drell-Yan production
- Diboson production at high pT
- Any process with large momentum transfer

### Real Photon Emission

NLO EW corrections include real photon emission, which affects:
- Lepton pT distributions (photon radiation softens leptons)
- Missing energy (from neutrinos + undetected photons)
- Invariant mass distributions (radiative return effects)

When photon-initiated processes contribute (e.g., photon-photon -> lepton pairs), a PDF set with a photon PDF component is needed (e.g., NNPDF3.1luxQED).

## Limitations

1. **Model availability**: The `loop_qcd_qed_sm` model must be installed separately.
2. **Computational cost**: NLO EW computations are significantly slower than NLO QCD due to the larger number of diagrams and loop topologies.
3. **Shower matching**: MC@NLO matching for NLO EW corrections with QED showering requires careful treatment. Pythia8 supports QED showering, but the interface may need specific configuration.
4. **Photon PDFs**: For processes with real photon emission from the initial state, a PDF set including the photon PDF is required.

## Cross-References

- **[← Reference: NLO & Matching](nlo_and_matching.md)**
- [NLO Computations](06_nlo_computations.md) — NLO QCD corrections, `nlo_mixed_expansion`
- [Models](03_models.md) — loading loop-capable models
- [Process Syntax](02_process_syntax.md) — bracket syntax, coupling orders
- [Advanced Syntax](17_advanced_syntax.md) — coupling order specifications
- [PDFs and LHAPDF](19_pdfs_and_lhapdf.md) — PDF sets with photon PDFs
- [Parton Shower — Pythia8](09_parton_shower_pythia8.md) — MC@NLO matching
