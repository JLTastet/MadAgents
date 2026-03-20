# 27 — MadDM (Dark Matter)

MadDM is a plugin for MadGraph5_aMC@NLO that computes dark matter observables for any BSM model with a dark matter candidate. It supports:

- **Relic density** (Ωh²) with freeze-out calculation
- **Direct detection** (spin-independent and spin-dependent DM–nucleon cross sections, differential recoil rates)
- **Indirect detection** (velocity-averaged annihilation cross sections, energy spectra of photons, neutrinos, and cosmic rays)
- **Spectral features** (loop-induced line signals: γγ, γZ, γh — added in v3.2)

MadDM uses the MadGraph5 architecture for matrix element generation and phase-space integration.

## Installation

Two installation methods:

**Method 1 — From the MG5 interactive shell:**
```
MG5_aMC> install maddm
```

**Method 2 — Manual installation from GitHub:**
```bash
cd <MG5_DIR>
git clone https://github.com/maddmhep/maddm.git PLUGIN/maddm
cp PLUGIN/maddm/maddm bin/maddm
```

**Requirements:**

| Dependency | Required | Notes |
|------------|----------|-------|
| MadGraph5_aMC@NLO ≥ 2.9.3 | Yes | Enforced by the plugin (`__init__.py` sets `minimal_mg5amcnlo_version = (2,9,3)`). The README may state a lower version but the plugin will refuse to load with MG5 < 2.9.3. |
| Python 2.7 | Yes (master) | See Python version note below |
| gcc | Yes | |
| numpy, scipy | Yes | |
| Pythia8 | Optional | For indirect detection showering/hadronization |
| PyMultiNest | Optional | For parameter scans via nested sampling |
| DRAGON | Optional | For cosmic-ray propagation to Earth |

> **Python version note:** MadDM has **two branches** on GitHub with different Python requirements:
>
> | Branch | Version | Python | MG5 requirement |
> |--------|---------|--------|-----------------|
> | `master` (default) | v3.2.13 (latest stable, July 2023) | **Python 2.7 only** | ≥ 2.9.3 |
> | `dev` | v3.3.0 (in development) | **Python 3.6+** (also Python 2.7 with `six` package) | ≥ 3.6 (per README) |
>
> The `master` branch (installed by default via `git clone` or `install maddm`) does **not** support Python 3. To use MadDM with Python 3, you must explicitly check out the `dev` branch **and** use MG5_aMC@NLO ≥ 3.6:
> ```bash
> cd <MG5_DIR>/PLUGIN/maddm
> git checkout dev
> ```
> The `dev` branch is not an official stable release — expect possible API changes or bugs. For production work, the stable `master` branch with Python 2.7 is recommended.

## Launching MadDM

From the MadGraph installation directory:

```bash
python2.7 bin/maddm          # master branch (v3.2.x)
python bin/maddm             # dev branch (v3.3.x, Python 3)
```

This opens an interactive shell (`MadDM>`) with commands similar to MG5.

To run a script non-interactively:

```bash
python2.7 bin/maddm script.txt
```

Type `tutorial` at the MadDM prompt for a guided walkthrough.

## Core Commands

### Import Model

```
import model DMsimp_s_spin0_MD
```

Loads a UFO model. MadDM can auto-download some models from the MG5 model database — check availability with `display modellist`. Not all `_MD` variants are in the database; some must be downloaded manually from the FeynRules DMsimp wiki and placed in `<MG5_DIR>/models/`.

### Define Dark Matter Candidate

```
define darkmatter ~xd
```

Specifies the DM candidate particle. If omitted, MadDM auto-detects the lightest massive neutral BSM particle with zero width.

> **WARNING — Particle naming differs between DMsimp model variants.** The DM candidate has **different particle names** depending on whether you use a standard DMsimp model or a `_MD` (MadDM-formatted) variant. Using the wrong name silently fails — MadDM will not find the particle and computations will produce errors or nonsensical results.

| Model variant | Example | DM particle name | `define darkmatter` command |
|---------------|---------|-------------------|-----------------------------|
| Standard DMsimp | `DMsimp_s_spin0`, `DMsimp_s_spin1` | `xd` | `define darkmatter xd` |
| `_MD` variant (for MadDM) | `DMsimp_s_spin0_MD`, `DMsimp_s_spin1_MD` | `~xd` | `define darkmatter ~xd` |

**Always run `display particles` after importing a model to verify the exact particle names.** Look for the DM candidate in the output and use that exact name. Do NOT assume the name is `xd` or `~xd` without checking — it depends on the specific model variant.

```
import model DMsimp_s_spin1_MD
display particles              # check the DM candidate name in the output
define darkmatter ~xd          # use the name shown by display particles
```

For standard (non-`_MD`) DMsimp models:

```
import model DMsimp_s_spin0
display particles              # DM candidate is listed as 'xd'
define darkmatter xd           # note: no tilde prefix
```

### Define Coannihilators

```
define coannihilator ~xr
```

Includes coannihilation channels in the relic density computation. Use this when your model has BSM particles close in mass to the DM candidate.

### Generate and Add Observables

```
generate relic_density
add direct_detection
add indirect_detection
add indirect_spectral_features
```

**Key distinction:** `generate` removes all previously generated matrix elements and starts fresh. `add` preserves existing matrix elements and appends new ones. Always use `generate` first, then `add` for additional observables.

You can exclude particles from diagrams using `/` syntax:

```
generate relic_density / z       # exclude Z boson from diagrams
```

For indirect detection, you can specify final states:

```
generate indirect_detection u u~       # specific final state
generate indirect_detection u u~ a     # include internal bremsstrahlung
```

For spectral features (loop-induced, v3.2), specify photon final states:

```
generate indirect_spectral_features a a    # γγ line
add indirect_spectral_features a z         # γZ line
```

MadDM automatically tries loop-induced diagrams (`[noborn=QCD]`) when tree-level diagrams are not found. **Do not** use the `[QCD]` syntax manually — use `indirect_spectral_features` instead.

### Output and Launch

```
output MY_DM_RUN
launch MY_DM_RUN
```

`output` creates the run directory with matrix elements and card templates. `launch` runs the computation and presents an interactive configuration interface.

### Display Commands

```
display modellist          # list downloadable models
display particles          # list particles in the loaded model
display processes relic     # show generated relic density processes
display processes indirect  # show generated indirect detection processes
display diagrams all        # show Feynman diagrams
display options             # show settable run parameters
```

## Complete Workflow Example

### With `_MD` variant (recommended for MadDM)

```
# Launch MadDM
# $ python2.7 bin/maddm

import model DMsimp_s_spin0_MD
define darkmatter ~xd          # ~xd for _MD models
generate relic_density
add direct_detection
add indirect_detection
output my_dm_study
launch my_dm_study
```

### With standard DMsimp model

```
import model DMsimp_s_spin0
define darkmatter xd           # xd for standard models (no tilde)
generate relic_density
add direct_detection
output my_dm_study_std
launch my_dm_study_std
```

The `launch` command presents an interactive menu with numbered options:

| Switch | Options | Description |
|--------|---------|-------------|
| `relic` | `ON` / `OFF` | Compute relic density (Ωh²) |
| `direct` | `direct` / `directional` / `OFF` | Compute DM–nucleon scattering |
| `indirect` | `sigmav` / `flux_source` / `flux_earth` / `OFF` | Compute indirect detection (continuum spectrum) |
| `spectral` | `ON` / `OFF` | Compute loop-induced line spectrum (γγ, γZ, γh) — v3.2 |
| `nestscan` | `ON` / `OFF` | Enable MultiNest parameter scan |

After selecting options, you can edit cards:
- **param_card.dat** — model parameters (masses, couplings)
- **maddm_card.dat** — computation-specific settings
- **multinest_card.dat** — scan configuration (if `nestscan = ON`)

### Setting Parameters at Launch

```
set mxd 500              # set DM mass to 500 GeV
set wy1 AUTO             # auto-compute mediator width
set mxd scan:range(50,700,25)   # scan DM mass from 50 to 700 GeV in 25 GeV steps
```

The `scan:` prefix accepts any Python iterable. Use `scan1:` for parallel (simultaneous) scans of multiple parameters.

## DMsimp Models

The DMsimp (Dark Matter Simplified Models) family provides s-channel mediator models. Variants specifically formatted for MadDM have the `_MD` suffix.

### _MD Variants (for MadDM)

| Model | Mediator | DM Candidate | DM particle name | Notes |
|-------|----------|-------------|------------------|-------|
| `DMsimp_s_spin0_MD` | Y0 (scalar) | Xd (Dirac fermion) | `~xd` | Verify availability with `display modellist`; may need manual download |
| `DMsimp_s_spin1_MD` | Y1 (vector) | Xd (Dirac fermion) | `~xd` | Available on FeynRules wiki; may require manual download |
| `DMsimp_s_spin0_mixed_MD` (zip) | Y0 (scalar, mixed) | Xd (Dirac fermion) | `~xd` | Effective ggY/aaY couplings (LO). **Warning:** MG5 database name may differ from the zip file name |

### Standard DMsimp Models (for collider simulations)

Standard (non-`_MD`) DMsimp models also work with MadDM but are designed for collider simulations:

| Model | Description | DM particle name |
|-------|-------------|------------------|
| `DMsimp_s_spin0` | Scalar mediator (NLO capable) | `xd` |
| `DMsimp_s_spin1` | Vector mediator (NLO capable; v2.0 added leptons, v2.1 added monotop) | `xd` |
| `DMsimp_s_spin2` | Tensor mediator (spin-2) | `xd` |

DMsimp DM candidate types across variants: `Xr` (real scalar), `Xc` (complex scalar), `Xd` (Dirac fermion), `Xv` (vector DM).

### Key param_card Parameters for DMsimp_s_spin1

The DMsimp_s_spin1 model has **generation-specific** couplings. All couplings are in the `DMINPUTS` block:

| Parameter | Description |
|-----------|-------------|
| `gVXd` | DM–mediator vector coupling |
| `gAXd` | DM–mediator axial-vector coupling |
| `gVu11`, `gVu22`, `gVu33` | Vector couplings to up-type quarks (1st, 2nd, 3rd gen) |
| `gVd11`, `gVd22`, `gVd33` | Vector couplings to down-type quarks (1st, 2nd, 3rd gen) |
| `gAu11`, `gAu22`, `gAu33` | Axial-vector couplings to up-type quarks |
| `gAd11`, `gAd22`, `gAd33` | Axial-vector couplings to down-type quarks |
| `gVl11`, `gVl22`, `gVl33` | Vector couplings to charged leptons |
| `gAl11`, `gAl22`, `gAl33` | Axial-vector couplings to charged leptons |
| `gnu11`, `gnu22`, `gnu33` | Couplings to neutrinos |

Mass parameters (in the `MASS` block):

| Parameter | Description |
|-----------|-------------|
| `MXd` | Dark matter mass |
| `MY1` | Vector mediator mass |
| `WY1` | Mediator width (in `DECAY` block; set to `AUTO` for automatic computation) |

> **Note:** The `_MD` variants may have a reduced set of couplings compared to the full collider model. Always check the param_card of the specific model you import.

## maddm_card.dat Parameters

The `maddm_card.dat` controls computation settings. Key parameters:

### Indirect Detection Settings (Continuum)

| Parameter | Options | Default | Description |
|-----------|---------|---------|-------------|
| `sigmav_method` | `reshuffling`, `inclusive`, `madevent` | `reshuffling` | Method for computing ⟨σv⟩ |
| `indirect_flux_source_method` | `pythia8`, `PPPC4DMID_ew`, `PPPC4DMID` | `pythia8` | Source spectrum computation |
| `indirect_flux_earth_method` | `dragon`, `PPPC4DMID_ep` | `dragon` | Cosmic-ray propagation to Earth |
| `vave_indirect_cont` | float | `2e-5` | Mean DM velocity for continuum spectra (dimensionless, c=1; typical for dwarf spheroidals) |

**sigmav_method details:**
- `reshuffling` (default) — Precise mode. Accounts for Maxwell-Boltzmann velocity distribution via reshuffling and reweighting of events.
- `inclusive` — Fast approximate calculation. Used when the `fast` preset is selected.
- `madevent` — Fixed DM velocity; phase-space integration by MadEvent.

**Fast vs. Precise presets:** MadDM offers preset configurations. The `fast` preset switches `sigmav_method` to `inclusive`, `indirect_flux_source_method` to `PPPC4DMID_ew`, and `indirect_flux_earth_method` to `PPPC4DMID_ep`. The `precise` preset uses the defaults shown above.

### Spectral Features Settings (v3.2)

| Parameter | Options | Default | Description |
|-----------|---------|---------|-------------|
| `vave_indirect_line` | float | `7.5e-4` | Mean DM velocity for line searches (dimensionless, c=1; typical for Galactic center) |
| `profile` | `gnfw`, `einasto`, `nfw`, `isothermal`, `burkert` | `einasto` | DM density profile for J-factor computation |
| `r_s` | float (kpc) | `20.0` | Scale radius |
| `alpha` | float | `0.17` | Einasto curvature parameter (only used when `profile = einasto`) |

**Profile details:**
- `einasto` (default) — Einasto profile with curvature parameter α (default 0.17) and scale radius r_s.
- `gnfw` — Generalized Navarro-Frenk-White profile with adjustable inner slope parameter γ (default 1.3). Setting γ=1 recovers the standard NFW profile; γ=1.3 gives a contracted NFW (NFWc).
- `nfw` — Standard Navarro-Frenk-White profile (fixed γ=1).
- `isothermal` — Isothermal sphere profile.
- `burkert` — Burkert (cored) profile.

> **Note:** `vave_indirect_cont` and `vave_indirect_line` are independent parameters. The legacy parameter `vave_indirect` is deprecated; use the specific variants instead.

### Event Generation

The number of events for phase-space integration is set at launch:

```
set nevents 10000
```

A value of 10,000 is commonly recommended for precise determination; 50,000 may be needed for Fermi-LAT constraint comparisons.

### Direct Detection Settings

| Parameter | Description |
|-----------|-------------|
| `vave_direct` | Local DM velocity |
| Detector parameters | Target material, recoil energy thresholds, nuclear form factors, escape velocity, local DM density |

The `directional` mode additionally allows customization of detector smearing and angular distributions.

## Output Structure

After `output` and `launch`, MadDM creates the following directory layout. The `Indirect_*` directories are at the top level of the process directory (not inside `output/`). Combined spectrum `.dat` files are written to the run directory (`output/run_01/`).

```
my_dm_study/
├── Cards/
│   ├── param_card.dat
│   ├── maddm_card.dat
│   ├── multinest_card.dat
│   └── dragon_card.xml
├── Indirect_tree_cont/                       # tree-level continuum processes
│   ├── Cards/
│   │   ├── param_card.dat
│   │   ├── maddm_card.dat
│   │   └── run_card.dat
│   └── Events/run_01/
│       ├── unweighted_events.lhe.gz
│       └── run_shower.sh
├── Indirect_tree_line/                       # tree-level line processes
│   ├── Cards/
│   └── Events/run_01/
├── Indirect_LI_cont/                        # loop-induced continuum processes
│   ├── Cards/
│   └── Events/run_01/
├── Indirect_LI_line/                        # loop-induced line processes (γγ, γZ via loops)
│   ├── Cards/
│   │   └── MadLoopParams.dat                # MadLoop settings
│   └── Events/run_01/
│       ├── unweighted_events.lhe.gz
│       └── run_shower.sh
└── output/
    ├── run_01/
    │   ├── MadDM_results.txt                # summary of all observables
    │   ├── maddm.out                        # computation log
    │   ├── maddm_card.dat                   # copy of settings used
    │   ├── gammas_spectrum_pythia8.dat       # combined spectrum (all Indirect_* summed)
    │   ├── positrons_spectrum_pythia8.dat
    │   ├── antiprotons_spectrum_pythia8.dat
    │   ├── neutrinos_e_spectrum_pythia8.dat
    │   ├── neutrinos_mu_spectrum_pythia8.dat
    │   ├── neutrinos_tau_spectrum_pythia8.dat
    │   ├── Output_Indirect_tree_cont/       # link to Indirect_tree_cont/Events/run_01/
    │   ├── Output_Indirect_tree_line/       # link to Indirect_tree_line/Events/run_01/
    │   ├── Output_Indirect_LI_cont/         # link to Indirect_LI_cont/Events/run_01/
    │   └── Output_Indirect_LI_line/         # link to Indirect_LI_line/Events/run_01/
    └── scan_run_01.txt                      # results for parameter scans
```

**Key points about the output layout:**
- Not all `Indirect_*` directories are always present — only those corresponding to generated observables are created.
- Spectrum `.dat` files in `output/run_01/` are the **combined** spectra from all `Indirect_*` directories.
- `Output_Indirect_*` entries in the run directory are symlinks pointing to the corresponding `Indirect_*/Events/run_01/` subdirectory (the event files), **not** to the `Indirect_*` directory itself. They do not provide access to the `Indirect_*/Cards/` directories.
- Per-process event files (LHE, shower scripts) are in `Indirect_*/Events/run_01/`. Per-process cards are in `Indirect_*/Cards/`.
- The spectrum file names depend on the `indirect_flux_source_method` setting: `*_spectrum_pythia8.dat` when using Pythia8 showering, `*_spectrum_PPPC4DMID_ew.dat` when using PPPC4DMID tables.

### Output Variables in MadDM_results.txt

**Relic density:**

| Variable | Units | Description |
|----------|-------|-------------|
| `OMEGA` | dimensionless | Relic abundance Ωh² |
| `x_f` | dimensionless | Freeze-out parameter mDM/Tf |
| `sigmav(xf)` | cm³/s | Thermally averaged ⟨σv⟩ at freeze-out |
| `xsi` | dimensionless | Thermal abundance fraction ξ |
| Channel contributions | % | Percentage breakdown by annihilation channel |

**Direct detection:**

| Variable | Units | Description |
|----------|-------|-------------|
| `SigmaN_SI_p` | cm² | Spin-independent DM–proton cross section |
| `SigmaN_SI_n` | cm² | Spin-independent DM–neutron cross section |
| `SigmaN_SD_p` | cm² | Spin-dependent DM–proton cross section |
| `SigmaN_SD_n` | cm² | Spin-dependent DM–neutron cross section |
| Constraint flags | — | "ALLOWED" or limit from LUX/Xenon1T/PICO-60 |

**Indirect detection:**

| Variable | Units | Description |
|----------|-------|-------------|
| `<sigma v>` per channel | cm³/s | Velocity-averaged annihilation cross section |
| `Fermi ul` | cm³/s | Fermi-LAT dwarf spheroidal upper limit |
| Integrated fluxes | particles/(cm²·s·sr) | Photon, neutrino, cosmic-ray fluxes |

**Spectral features (v3.2):**

| Variable | Units | Description |
|----------|-------|-------------|
| Line cross sections | cm³/s | ⟨σv⟩ for γγ, γZ, γh channels |
| J-factor | GeV²/cm⁵ | Astrophysical J-factor for the chosen profile and ROI |
| Fermi-LAT / HESS limits | cm³/s | Comparison against experimental line-search limits |

## Parameter Scans

### Sequential Scan

Use the `scan:` prefix with any Python iterable:

```
set mxd scan:range(50, 700, 25)          # scan DM mass
set mxd scan:[100, 200, 500, 1000]       # explicit list
```

Results are written to `output/scan_run_NN.txt`.

### Parallel Scan

To scan two parameters simultaneously (same-length iterables):

```
set mxd scan1:range(50, 700, 25)
set my1 scan1:range(100, 1400, 50)
```

The `scan1:` prefix ensures both parameters advance together (i.e., the i-th value of `mxd` pairs with the i-th value of `my1`).

### MultiNest Scan

For Bayesian parameter inference:

1. Set `nestscan = ON` at the launch menu.
2. Edit `multinest_card.dat` to configure priors, live points, and evidence tolerance.
3. Requires PyMultiNest.

## Coannihilation

If your model has BSM particles nearly degenerate in mass with the DM candidate, coannihilation processes contribute to the relic density:

```
import model MY_BSM_MODEL
define darkmatter ~chi1
define coannihilator ~chi2 ~chi3
generate relic_density
add direct_detection
output coann_study
launch coann_study
```

MadDM automatically includes all 2→2 annihilation and coannihilation channels involving the DM candidate and the defined coannihilators.

## Using Custom UFO Models

MadDM works with **any** UFO model that contains a dark matter candidate (a stable, neutral BSM particle). To use a custom model:

1. Place the UFO directory in `<MG5_DIR>/models/`.
2. Import it in MadDM: `import model MY_MODEL`.
3. Run `display particles` to find the DM candidate particle name.
4. Define the DM candidate: `define darkmatter <particle_name>`.
5. Proceed with `generate`/`add`/`output`/`launch` as usual.

The DMsimp `_MD` variants are convenience models pre-configured for MadDM. Standard UFO models (including MSSM, 2HDM+DM, etc.) also work if they contain a valid DM candidate.

## Loop-Induced Processes / Spectral Features (v3.2)

MadDM v3.2 supports loop-induced processes for indirect detection line signals (e.g., DM DM → γγ via loops):

```
generate indirect_spectral_features a a    # γγ line
add indirect_spectral_features a z         # γZ line
```

This enables computation of monochromatic photon signals from DM annihilation. MadDM automatically handles loop-induced diagram generation internally.

### Combined Workflow (Continuum + Lines)

```
import model topphilic_NLO_EW_CM_UFO
define darkmatter chi
generate relic_density
add indirect_detection
add indirect_detection g g
add indirect_spectral_features
output my_complete_study
launch my_complete_study
```

At launch, set velocity parameters for each observable type:

```
set vave_indirect_cont 2.e-5       # for continuum (dwarf spheroidals)
set vave_indirect_line 7.5e-4      # for lines (Galactic center)
set nevents 10000
set profile einasto
```

## Common Pitfalls

- **Wrong DM particle name**: The most common error. Standard DMsimp models use `xd`; `_MD` variants use `~xd`. Always run `display particles` after `import model` and use the exact name shown. Using the wrong name causes MadDM to fail silently or produce errors.
- **Forgetting `generate` before `add`**: The first observable must use `generate`, not `add`. Using `add` without a prior `generate` produces an error.
- **Python version mismatch**: The stable MadDM release (master branch, v3.2.13) requires Python 2.7. Python 3 is only supported on the `dev` branch (v3.3.0) with MG5 ≥ 3.6.
- **Missing model**: Not all `_MD` variants are in the MG5 model database. If `import model` fails, download the model manually from the FeynRules DMsimp wiki.
- **Width not set to AUTO**: For consistent results, set mediator widths to `AUTO` so MadDM computes them from the model parameters.

## Key Points

- **Particle naming varies by model**: `_MD` models use `~xd`, standard DMsimp uses `xd`. Always verify with `display particles`.
- **Python 2.7 required** for stable release (master, v3.2.13). Python 3.6+ only on `dev` branch (v3.3.0) with MG5 ≥ 3.6.
- MadGraph5_aMC@NLO **≥ 2.9.3** is required for the stable release (the plugin enforces `minimal_mg5amcnlo_version = (2,9,3)` in `__init__.py`; the README may state a lower version).
- `generate` clears previous matrix elements; `add` preserves them.
- Use `_MD` model variants for out-of-the-box compatibility with MadDM. Some `_MD` models may need manual download from the FeynRules wiki.
- DMsimp coupling names are **generation-specific**: `gVu11`/`gVu22`/`gVu33`, not a single `gVu`.
- Set mediator widths to `AUTO` for consistent width computation.
- The `scan:` syntax accepts any Python iterable for parameter scans.
- Output observables are in `output/run_NN/MadDM_results.txt`. Spectrum `.dat` files are also directly in `output/run_NN/`.
- `Indirect_*` directories (at the process dir top level) contain per-process event files and cards. Symlinks `Output_Indirect_*` in `output/run_NN/` point to `Indirect_*/Events/run_NN/` (event files only, not cards).
- Use `indirect_spectral_features` (not `indirect_detection`) for loop-induced γ-ray lines.
- Use `vave_indirect_cont` for continuum and `vave_indirect_line` for line searches — these are independent parameters.
- The `spectral` switch in the launch menu (v3.2) toggles line-spectrum computation independently from continuum.
- DM density profile options: `gnfw`, `einasto` (default), `nfw`, `isothermal`, `burkert`. The `gnfw` profile has an adjustable inner slope γ (default 1.3).
- Type `tutorial` at the MadDM prompt for an interactive guided walkthrough.

## References

- MadDM v1.0: [arXiv:1308.4955](https://arxiv.org/abs/1308.4955)
- MadDM v2.0 (direct detection): [arXiv:1505.04190](https://arxiv.org/abs/1505.04190)
- MadDM v3.0: [arXiv:1804.00044](https://arxiv.org/abs/1804.00044)
- MadDM v3.1 user guide: [arXiv:2012.09016](https://arxiv.org/abs/2012.09016)
- MadDM v3.2 (lines and loops): [arXiv:2107.04598](https://arxiv.org/abs/2107.04598) / [EPJC 83 (2023) 241](https://link.springer.com/article/10.1140/epjc/s10052-023-11377-2)
- DMsimp models: [FeynRules DMsimp page](https://feynrules.irmp.ucl.ac.be/wiki/DMsimp)
- GitHub: [maddmhep/maddm](https://github.com/maddmhep/maddm)

## Cross-References

- [Models](03_models.md) — UFO model loading, restriction files
- [Cards & Parameters](04_cards_and_parameters.md) — param_card editing
- [Scripted Execution](05_scripted_execution.md) — non-interactive script syntax
- [Parton Shower (Pythia8)](09_parton_shower_pythia8.md) — required for indirect detection spectra
- [MadWidth](12_madwidth.md) — computing BSM particle widths