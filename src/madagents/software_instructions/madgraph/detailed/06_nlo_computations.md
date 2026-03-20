# 06 — NLO Computations

MadGraph5_aMC@NLO computes next-to-leading order (NLO) QCD corrections for arbitrary processes, providing more precise cross-section predictions and reduced scale uncertainties compared to LO.

## Requirements

NLO computations require:
1. A **loop-capable model**: `import model loop_sm` (not `sm`)
2. The **`[QCD]`** syntax on the `generate` line
3. Optional but recommended: Pythia8 for MC@NLO matching to a parton shower

## Basic NLO Syntax

```
import model loop_sm
generate p p > t t~ [QCD]
output ttbar_NLO
launch ttbar_NLO
  shower=PYTHIA8
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  done
```

The `[QCD]` triggers computation of NLO QCD corrections: real emission diagrams, virtual (one-loop) diagrams, and the associated subtraction terms.

## NLO Syntax Variants

```
generate p p > t t~ [QCD]          # full NLO QCD (real + virtual + subtraction)
generate p p > t t~ [virt=QCD]     # virtual corrections only (one-loop amplitudes)
generate g g > z z [noborn=QCD]    # loop-induced process (no Born amplitude exists)
```

### Loop-Induced Processes

Some processes have no tree-level diagrams but proceed through loops at leading order (e.g., gg → ZZ, gg → HH). Use `[noborn=QCD]` to signal that the Born contribution is absent:

```
import model loop_sm
generate g g > z z [noborn=QCD]
```

If you try `generate g g > z z` without `[noborn=QCD]`, MG5 reports 0 diagrams because there is no tree-level amplitude.

**Warning**: MG5 does not validate that the Born amplitude truly vanishes when you use `[noborn=QCD]`. It trusts the user's assertion and skips the Born contribution. If the Born actually exists, the computation silently produces incomplete (wrong) results. Always verify independently that the process is genuinely loop-induced.

Loop-induced LO computations can receive very large higher-order corrections. For example, gg → H has a K-factor of ~2 from NLO QCD, making the LO cross-section a poor normalization. Use loop-induced LO for distribution shapes, but normalize to higher-order predictions (from dedicated codes or literature) when available.

## MC@NLO Matching

MG5_aMC@NLO uses the MC@NLO method to combine NLO calculations with a parton shower:

- Subtracts the shower approximation analytically from the NLO calculation.
- **Produces events with negative weights** — this is inherent to the method, not a bug.
- The negative weight fraction is typically 10-30% depending on the process.
- Requires a parton shower (Pythia8) for physically meaningful predictions.

In the run_card:
```
PYTHIA8   = parton_shower      # shower program for MC@NLO matching
```

Note: POWHEG is a separate framework (POWHEG-BOX), not part of MG5_aMC@NLO.

## Reducing Negative Weights

Large negative weight fractions reduce the effective statistics. For MC@NLO events unweighted to +1/-1, the effective number of events is:

```
N_eff = N × (1 - 2f)²
```

where **f** is the fraction of negative-weight events. The required number of events to achieve a given statistical precision scales as 1/(1 - 2f)² relative to an all-positive sample:

| Negative weight fraction (f) | Events needed (relative) | Effective statistics |
|------------------------------|--------------------------|---------------------|
| 10% | 1.56× | 64% |
| 20% | 2.78× | 36% |
| 25% | 4.00× | 25% |
| 30% | 6.25× | 16% |

### Why MC@NLO Produces Negative Weights

The MC@NLO method decomposes the NLO cross section into **H-events** (hard, (n+1)-body kinematics) and **S-events** (soft/standard, n-body kinematics). H-events carry the weight dσ_real − dσ_MC, where dσ_MC is the parton shower's O(α_s) emission approximation used as a local subtraction term. In soft/collinear regions, the shower approximation can locally exceed the NLO real-emission matrix element, making dσ_real − dσ_MC negative. S-events can also carry negative weights when the virtual corrections are negative for certain Born configurations. This is inherent to the method and not a bug.

See Frederix, Frixione, Prestel, Torrielli, JHEP 07 (2020) 238 ([arXiv:2002.12716](https://arxiv.org/abs/2002.12716)) for a detailed classification of negative weight sources and the MC@NLO-Delta method for reducing them.

Strategies to mitigate:

### Folding Parameters

The `folding` parameters in the run_card increase sampling points in the FKS subtraction, reducing the negative weight fraction at the cost of longer runtime:

```
set run_card folding 4 4 4
```

The three values control folding in different FKS subtraction variables (xi_i, y_ij, phi_i). Default is `1 1 1`. Each value must be 1, 2, 4, or 8. Increasing the values reduces negative weights at the cost of longer runtime (scales approximately linearly).

### More Integration Points

Better grid optimization reduces weight fluctuations:
- Increase the number of iterations/points for grid optimization.
- The first launch is slower (grid buildup), subsequent launches with the same process directory can reuse grids.

## FKS_params.dat — Technical NLO Parameters

Located in `<PROC_DIR>/Cards/FKS_params.dat`:

```
1d-5    = IRPoleCheckThreshold    ! IR pole cancellation threshold
1.0d-3  = PrecisionVirtualAtRunTime
```

### Pole Cancellation Errors

If you see `aMCatNLOError: Poles do not cancel`, the IR (infrared) subtraction terms and virtual corrections don't cancel to the expected precision. Common causes:

1. **VBF/VBS processes**: MG5 filters out certain pentagon diagrams containing non-QCD particles (W, Z, γ, H). These are UV-finite and typically contribute < 1% but cause the pole check to fail.

   **Fix**: Set `IRPoleCheckThreshold = -1.0d0` in FKS_params.dat to disable the check:
   ```
   set FKS_params IRPoleCheckThreshold -1.0d0
   ```

2. **Numerical instabilities**: Rare phase-space points with poor numerical precision. Increasing `PrecisionVirtualAtRunTime` triggers re-evaluation at higher precision for flagged points.

## MadLoop and External One-Loop Providers (BLHA Interface)

### MadLoop — The Built-In One-Loop Provider

MadLoop is the default one-loop provider (OLP) in MG5_aMC@NLO. It computes virtual (one-loop) amplitudes using integrand-reduction and tensor-integral-reduction methods.

**Default reduction tools** (statically linked — no user configuration needed):

| Tool | Method | Notes |
|------|--------|-------|
| **CutTools** | OPP integrand reduction | Required; always present |
| **IREGI** | Tensor integral reduction (TIR) | Required; always present |
| **Ninja** | OPP with Laurent expansion | Recommended; installed by default |

MadLoop implements a multi-tool stability rescue system: each phase-space point is first evaluated with one reduction tool in double precision. If numerical instability is detected, the point is re-evaluated with a different tool and/or in quadruple precision. Return codes indicate which tool and precision were used.

**Optional reduction libraries** (dynamically linked, must be installed separately):

| Library | Install command | Notes |
|---------|----------------|-------|
| COLLIER | `install collier` | Tensor reduction; alternative to IREGI |
| Golem95 | `install Golem95` | Tensor reduction (note: capital G is required) |
| PJFry++ | (manual) | Tensor reduction |
| Samurai | (manual) | OPP reduction |

Paths to optional libraries are set in `input/mg5_configuration.txt`:

```
# ninja = ./HEPTools/lib        # path to Ninja library (default)
# collier = ./HEPTools/lib       # path to COLLIER library
# golem = auto                   # path to Golem95 library (auto = auto-detect)
# samurai = None                 # path to Samurai library (None = disabled)
# pjfry = auto                   # path to PJFry++ library
```

The `output_dependencies` option controls how MadLoop's reduction libraries are bundled:

```
# output_dependencies = external          # links to MG5-wide libraries (default)
# output_dependencies = internal          # copies libraries into the output directory
# output_dependencies = environment_paths # searches PATH for libraries at runtime
```

### The Binoth Les Houches Accord (BLHA)

The BLHA is a standardized interface protocol between Monte Carlo event generators and one-loop providers. It allows MG5_aMC@NLO to delegate virtual amplitude computation to an external code instead of MadLoop.

**References:**
- BLHA1: Binoth et al., Comp. Phys. Comm. 181 (2010) 1612 ([arXiv:1001.1307](https://arxiv.org/abs/1001.1307))
- BLHA2: Alioli et al., Comp. Phys. Comm. 185 (2014) 560 ([arXiv:1308.3462](https://arxiv.org/abs/1308.3462))

The BLHA works in two phases:

1. **Order/Contract phase** (at code-generation time):
   - MG5 writes an **order file** (`OLE_order.lh`) specifying: subprocess list, coupling powers (QCD/QED), renormalization/regularization schemes, and a path to an SLHA parameter file (`ModelFile`) for masses, widths, and couplings.
   - The OLP reads the order file and produces a **contract file** (`OLE_order.olc`) confirming which subprocesses it can provide, assigning each an integer label.

2. **Runtime phase** (during integration/event generation):
   - `OLP_Start(contract_file, ierr)` — initializes the OLP, reads the contract. `ierr=1` on success.
   - `OLP_EvalSubProcess(label, momenta, mu_r, alpha_s, rval)` — evaluates the one-loop amplitude for subprocess `label` at the given phase-space point and renormalization scale `mu_r`, with strong coupling `alpha_s`. Returns a 4-element array: `rval(1)` = coefficient of double IR pole (1/epsilon²), `rval(2)` = coefficient of single IR pole (1/epsilon), `rval(3)` = finite part, `rval(4)` = Born |M|². Momenta are packed as 5-tuples (E, kx, ky, kz, M) per particle.

   This is the BLHA1 subroutine signature. BLHA2 introduces `OLP_EvalSubProcess2` which drops `alpha_s` from the argument list and adds a double-precision accuracy estimate. MG5_aMC@NLO uses the BLHA1 signature when interfacing external OLPs like GoSam.

**Note:** MG5's internal communication between MadFKS (real-emission/subtraction) and MadLoop uses a BLHA-inspired architecture — it shares the order/contract file mechanism and BinothLHA-named source files — but internally calls `sloopmatrix_thres()` rather than the standard BLHA subroutines.

### Supported External OLPs

| OLP | Method | Native MG5 support | Notes |
|-----|--------|-------------------|-------|
| **GoSam** | Algebraic code generation | Yes (`set OLP GoSam`) | Automated one-loop generator; uses reduction tools from GoSamContrib (Golem95, Samurai, and optionally Ninja) |
| **OpenLoops** | On-the-fly numerical recursion | Via `[real=QCD]` + manual interface | Fast for high-multiplicity processes |
| **RECOLA** | Recursive amplitude construction | Via `[real=QCD]` + manual interface | Uses COLLIER for reduction |

### Using GoSam as the OLP

GoSam has a native interface to MG5_aMC@NLO based on the BLHA1 standard. To use it:

**Option 1: Interactive command**
```
MG5_aMC> set OLP GoSam
```

**Option 2: Persistent configuration** in `input/mg5_configuration.txt`:
```
OLP = GoSam
```

With GoSam selected, `generate p p > e+ ve [QCD]` and `launch` will automatically:
1. Generate the BLHA order file (`OLE_order.lh`) with subprocess definitions.
2. Invoke GoSam to produce one-loop amplitudes and write the contract file (`OLE_order.olc`).
3. Use GoSam's loop amplitudes during integration and event generation.

GoSam-specific settings (loop particle content, model, number of active flavors) can be customized via a `gosam.rc` configuration file. Consult the GoSam documentation for details.

**Prerequisites:** GoSam and its dependencies (GoSamContrib, which includes Golem95 and Samurai) must be installed and accessible. GoSam generates Fortran code for the loop amplitudes, so the first run involves a code-generation step.

### Using Other OLPs via `[real=QCD]`

For OpenLoops, RECOLA, or other BLHA-compliant OLPs without a native MG5 interface, use the `[real=QCD]` syntax:

```
import model loop_sm
generate p p > t t~ [real=QCD]
output ttbar_real_only
```

The `[real=QCD]` directive generates the full NLO real-emission infrastructure (MadFKS subtraction, phase-space integration) but does **not** link MadLoop for virtual amplitudes. The user must provide the virtual corrections by interfacing their chosen OLP through the BinothLHA Fortran files in the output directory.

**Key syntax variants for separating NLO components** (see also NLO Syntax Variants above):

| Syntax | What is generated | Use case |
|--------|-------------------|----------|
| `[QCD]` | Full NLO: real + virtual + subtraction (MadLoop) | Standard NLO computation |
| `[real=QCD]` | Real emission + FKS subtraction only (no MadLoop) | Interface your own OLP for virtuals |
| `[virt=QCD]` | Virtual (one-loop) corrections only | Standalone loop amplitude computation |

### When to Use an External OLP vs MadLoop

- **Cross-validation:** Using a different OLP provides an independent numerical check of virtual corrections, valuable for new or complex processes.
- **BSM models:** Some BSM models may be implemented in GoSam or RECOLA but not in MadLoop's UFO-based framework, or vice versa.
- **Performance:** For specific processes, external OLPs may be faster. OpenLoops' numerical recursion can be more efficient for high-multiplicity processes.
- **Default recommendation:** Use MadLoop (the default) unless you have a specific reason to use an external OLP. MadLoop is tightly integrated, requires no external dependencies beyond the statically linked reduction tools, and handles most SM and BSM processes.

## Version Differences: v2 vs v3

MG5 v3 includes pentagon loops with non-colored particles (e.g., W/Z loops connecting quark lines) that were discarded in v2. This affects processes with t-channel vector bosons at LO:

- VBF Higgs production
- VBS (vector boson scattering)
- Single-top production

The `nlo_mixed_expansion` parameter in the run_card controls this:

```
True    = nlo_mixed_expansion    ! include non-colored loops (v3 default)
False   = nlo_mixed_expansion    ! v2 behavior (discard non-colored loops)
```

For most processes the difference is negligible. For VBF/VBS it can be noticeable. The v3 behavior is more theoretically consistent.

## NLO + MadSpin + Shower + Delphes

Complete NLO workflow with all tools:

```
import model loop_sm
generate p p > t t~ [QCD]
output ttbar_NLO_full
launch ttbar_NLO_full
  shower=PYTHIA8
  madspin=ON
  detector=Delphes
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  set madspin_card decay t > w+ b, w+ > l+ vl
  set madspin_card decay t~ > w- b~, w- > l- vl~
  done
```

MadSpin handles decays between the fixed-order computation and the shower, preserving spin correlations. This is the recommended approach for NLO — including decays directly in the NLO `generate` line is often not possible or impractical.

## FxFx Merging at NLO

FxFx is the NLO extension of MLM matching. It merges NLO-accurate samples of different jet multiplicities:

```
import model loop_sm
generate p p > t t~ [QCD] @0
add process p p > t t~ j [QCD] @1
output ttbar_FxFx
launch ttbar_FxFx
  shower=PYTHIA8
  set run_card ickkw 3
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 50000
  done
```

FxFx requires `ickkw = 3` in the run_card. See [Matching & Merging](07_matching_merging.md) for details.

## Process Overlap at NLO

### Internal Overlap (FKS Subtraction)

At NLO, real-emission diagrams can produce topologies that overlap with different Born configurations. For example, in `p p > t t~ j [QCD]`, a real-emission diagram may produce a configuration where the extra jet is soft or collinear, overlapping with the Born process `p p > t t~`. MG5 handles this automatically via the FKS subtraction scheme: the `check_ij_confs()` and `find_reals_to_integrate()` routines identify overlapping configurations and assign each real-emission phase-space point to exactly one FKS partition, preventing double-counting.

**No user action is needed** for this internal overlap — FKS handles it correctly by construction.

### Physics-Level Process Overlap (Wt vs tt̄)

A different kind of overlap arises at the physics level. The classic example is **single-top Wt production** (`p p > t w-`) at NLO: its real-emission diagrams include `g b > t w- b̄`, which is also a leading-order diagram for **tt̄ production** (`p p > t t~, t~ > w- b~`). This is a physics ambiguity, not a technical subtraction issue.

MG5 does **not** provide built-in diagram removal (DR) or diagram subtraction (DS) schemes to handle this overlap. The standard approaches are:

1. **Inclusive approach**: Generate the full process including all diagrams. This is gauge-invariant but conflates Wt and tt̄.
2. **Invariant mass cuts**: Apply a veto on the invariant mass of the (W, b̄) system to exclude configurations near the top mass. This can be done at analysis level.
3. **External tools**: Dedicated Wt-channel generators implement DR/DS schemes. If precise Wt isolation is needed, consult the literature for the appropriate scheme.

For most analyses, the inclusive NLO calculation of `p p > t t~` supplemented by the inclusive single-top calculations is sufficient, provided the analysis selection avoids the overlap region.

## MadSTR Plugin — Diagram Removal and Subtraction for Resonance Overlap

The **MadSTR** (Simplified Treatments of Resonances) plugin implements Diagram Removal (DR) and Diagram Subtraction (DS) schemes within MG5_aMC@NLO to handle the resonance overlap problem described above. It is the standard tool for computing NLO-accurate tW production separated from tt̄.

### The Overlap Problem

When computing `p p > t w-` at NLO QCD, real-emission diagrams produce `g b > t w- b̄` configurations that are kinematically identical to `p p > t t~` followed by `t~ > w- b~`. The standard FKS subtraction handles internal IR divergences correctly but does **not** resolve this physics-level double-counting between tW and tt̄. Without treatment, the NLO tW cross-section is ill-defined because doubly-resonant tt̄ diagrams dominate the real emission.

### DR and DS Schemes

Two families of schemes address the overlap:

| Scheme | Variant | Description | Gauge Invariance |
|--------|---------|-------------|------------------|
| **DR** (Diagram Removal) | DR1 | Removes all doubly-resonant amplitudes before squaring the matrix element. Both the squared resonant contribution and the interference with singly-resonant amplitudes are removed. | **Not gauge-invariant.** Removing diagrams before squaring breaks gauge cancellations. For tW production with small top-quark width, the gauge-dependence effects are numerically negligible. |
| | DR2 | Removes only the squared doubly-resonant contribution; keeps the interference between singly-resonant and doubly-resonant amplitudes. | **Not gauge-invariant.** Same issue as DR1; additionally, the result is not positive-definite due to the surviving interference. |
| **DS** (Diagram Subtraction) | — | Constructs a local subtraction term from the full (gauge-invariant) on-shell tt̄ matrix element weighted by a Breit-Wigner ratio BW(M_bW)/BW(m_t). This cancels the doubly-resonant contribution near the top mass shell while preserving the full amplitude away from it. | **Gauge-invariant by construction.** The subtraction term is built from the complete tt̄ amplitude (which is itself gauge-invariant) times a kinematic BW ratio, so gauge invariance is preserved at every phase-space point. |

**Key points:**
- DR breaks gauge invariance because removing individual diagrams disrupts gauge cancellations. DS was developed specifically to avoid this problem.
- For practical tW calculations, DR gauge-dependence effects are negligible because the top width is small relative to the top mass.
- The difference between DR and DS results provides an estimate of the scheme uncertainty.
- DR1 is the simplest to implement. DS preserves more of the amplitude structure but introduces a dependence on the momentum reshuffling prescription.

### Installation

MadSTR is distributed as a plugin via GitHub. The repository root contains an inner `MadSTR/` package directory. MG5 expects the plugin at `PLUGIN/MadSTR/__init__.py`, so you must copy the **inner** directory:

```bash
# Find the MG5 installation root directory
MG5DIR=$(dirname $(dirname $(readlink -f $(which mg5_aMC))))

git clone https://github.com/mg5amcnlo/MadSTR.git /tmp/MadSTR_repo
cp -r /tmp/MadSTR_repo/MadSTR "$MG5DIR/PLUGIN/MadSTR"
rm -rf /tmp/MadSTR_repo
```

The double `dirname` is necessary because `mg5_aMC` lives at `<MG5_ROOT>/bin/mg5_aMC` — the first `dirname` strips the filename to give `<MG5_ROOT>/bin/`, and the second strips `bin/` to give the MG5 root where `PLUGIN/` resides.

Verify the directory structure is:
```
MG5_aMC/PLUGIN/MadSTR/__init__.py
MG5_aMC/PLUGIN/MadSTR/madstr_interface.py
MG5_aMC/PLUGIN/MadSTR/...
```

A common mistake is placing the git repo directory as `PLUGIN/MadSTR/MadSTR/` — this results in the plugin failing to load because MG5 cannot find the required `new_interface` attribute in the outer package.

**Version constraint:** The plugin's `__init__.py` declares `maximal_mg5amcnlo_version = (3,6,1000)`, meaning it will refuse to load on MG5 v3.7.0 or later. If you are using MG5 ≥ 3.7.0, you must edit `PLUGIN/MadSTR/__init__.py` and raise the `maximal_mg5amcnlo_version` tuple (e.g., to `(3,9,1000)`). This is an untested configuration — verify your results by comparing `istr=0` output against a standard MG5 NLO run.

### Invocation

MadSTR requires launching MG5 in a special mode:

```bash
mg5_aMC --mode=MadSTR
```

Then generate the process normally. **You must use a massless-b-quark model** for tW processes:

```
import model loop_sm-no_b_mass
generate p p > t w- [QCD]
add process p p > t~ w+ [QCD]
output tW_NLO_STR
```

### Event Generation

The `launch` command is **unconditionally blocked** in MadSTR mode. The source code (`madstr_interface.py`) overrides `do_launch()` to always raise `MadSTRInterfaceError` with the message:

> *With MadSTR, the launch command must not be executed from the MG5_aMC shell. Rather, the event generation / cross-section computation should be launched from within the process directory.*

This is a deliberate design choice, not a bug. After `output`, you must run event generation from inside the process directory:

```bash
cd tW_NLO_STR
./bin/generate_events
```

The `generate_events` script launches its own interactive interface that prompts you to edit cards and set parameters (similar to the standard aMC@NLO workflow). You can set MadSTR parameters interactively when prompted, or edit the `Cards/run_card.dat` file directly before running with the `-f` flag:

```bash
# Option 1: Edit run_card.dat directly, then run non-interactively
# (edit Cards/run_card.dat to set istr, beam energies, etc.)
./bin/generate_events -f

# Option 2: Run interactively and set parameters when prompted
./bin/generate_events
```

### The `istr` Parameter

MadSTR adds the `istr` parameter to the run_card, controlling the overlap removal scheme. The complete list of values (from `os_wrapper_fks.inc`):

| `istr` | Scheme | Reshuffling | BW type | Description |
|--------|--------|-------------|---------|-------------|
| 0 | None | — | — | No subtraction — standard MG5 behavior. Gives unphysical results for processes with resonance overlap. Use for validation only. |
| 1 | DR1 | — | — | Diagram Removal without interference. All doubly-resonant amplitudes are set to zero in the matrix element code (`matrix_X.f`). |
| 2 | DR2 | Identity | None (`ibw=0`) | Diagram Removal with interference. Removes only the squared doubly-resonant contribution via on-shell subtraction with identity momentum mapping. |
| 3 | DS | Initial-state | Standard (`ibw=1`) | Diagram Subtraction with initial-state reshuffling and fixed-width Breit-Wigner. |
| 4 | DS | Initial-state | Running (`ibw=2`) | Diagram Subtraction with initial-state reshuffling and running-width Breit-Wigner. |
| 5 | DS | Final-state | Standard (`ibw=1`) | Diagram Subtraction with final-state particle reshuffling and fixed-width BW. |
| 6 | DS | Final-state | Running (`ibw=2`) | Diagram Subtraction with final-state particle reshuffling and running-width BW. |
| 7 | DS | Spectator | Standard (`ibw=1`) | Diagram Subtraction with spectator reshuffling and fixed-width BW. |
| 8 | DS | Spectator | Running (`ibw=2`) | Diagram Subtraction with spectator reshuffling and running-width BW. |

The reshuffling prescription determines how the real-emission momenta are mapped to on-shell tt̄ kinematics for the subtraction term. The BW type controls whether the Breit-Wigner ratio uses a fixed or energy-dependent width.

### Additional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `str_include_pdf` | Boolean | True | Include PDF ratio corrections in the subtraction term. |
| `str_include_flux` | Boolean | True | Include flux factor corrections in the subtraction term. |

### Worked Example: tW Production with DR1

**Step 1: Process generation.** Create a script `tW_generate.mg5`:

```
import model loop_sm-no_b_mass
generate p p > t w- [QCD]
add process p p > t~ w+ [QCD]
output tW_DR1
```

Run with:
```bash
mg5_aMC --mode=MadSTR tW_generate.mg5
```

**Step 2: Configure the run_card.** Edit `tW_DR1/Cards/run_card.dat` to set the MadSTR parameters and beam energies:

```bash
cd tW_DR1
# Set istr to 1 (DR1)
sed -i 's/.*=\s*istr/1 = istr/' Cards/run_card.dat
# Set beam energies to 6500 GeV (13 TeV LHC)
sed -i 's/.*=\s*ebeam1/6500.0 = ebeam1/' Cards/run_card.dat
sed -i 's/.*=\s*ebeam2/6500.0 = ebeam2/' Cards/run_card.dat
# Set number of events
sed -i 's/.*=\s*nevents/50000 = nevents/' Cards/run_card.dat
```

**Step 3: Generate events.** Run from inside the process directory:

```bash
./bin/generate_events -f
```

The `-f` flag skips the interactive card-editing prompts and uses the run_card as-is.

To compare DR2, change `istr` to `2`. For DS with initial-state reshuffling and fixed-width BW, use `istr 3`. The spread across DR and DS results estimates the scheme uncertainty.

### Limitations

- **`launch` is blocked**: The `launch` command cannot be used from the MadSTR MG5 shell. Always use `./bin/generate_events` from inside the process directory.
- **Massless b-quark required**: The model must use `loop_sm-no_b_mass` (or equivalent with `mb=0`). This is a five-flavor scheme (5FS) requirement: the b-quark must be massless in the matrix element for consistency with 5-flavor PDF evolution, which resums collinear logarithms ln(Q²/m_b²) into the b-quark PDF. Additionally, using a 4-flavor scheme (massive b) for tW production would introduce the tW/tt̄ overlap already at leading order (through the `g g > t w- b~` Born process), defeating the purpose of DR/DS at NLO.

### Version Compatibility and Known Issues

| Issue | Versions affected | Status / Fix |
|-------|-------------------|-----|
| **Version constraint** — `__init__.py` declares `minimal_mg5amcnlo_version = (2,9,0)` and `maximal_mg5amcnlo_version = (3,6,1000)`. MG5 ≥ 3.7.0 will refuse to load the plugin. | MG5 ≥ 3.7.0 | Edit `PLUGIN/MadSTR/__init__.py` to raise `maximal_mg5amcnlo_version`. Untested — verify results against standard NLO with `istr=0`. |
| **`istr=1` uninitialized array** — `amp_split_os` array not zeroed in `os_wrapper_fks.inc` for the DR1 code path, causing undefined Fortran behavior. DR2 and DS (`istr ≥ 2`) are unaffected. | Older MadSTR versions (reported with MG5 v3.5.4) | Fixed in current MadSTR GitHub master. If using an old checkout, add `amp_split_os(:) = 0d0` before the `if (istr.le.1)` early return in `os_wrapper_fks.inc`. |
| **Parameter identification bug** ([Launchpad Bug #2062439](https://bugs.launchpad.net/mg5amcnlo/+bug/2062439)) — If MG5_aMC is on `PYTHONPATH`, `generate_events` loads the system-wide `banner.py` instead of MadSTR's modified version, causing `istr`, `str_include_pdf`, and `str_include_flux` to be silently ignored. | MG5 ≤ 3.5.x | MG5 v3.6.0+ introduces a dedicated plugin parameter API. For older versions: remove MG5 from `PYTHONPATH` before running `generate_events`. |
| **Last validated version** — `__init__.py` declares `latest_validated_version = (3,5,2)`. | — | Informational. MadSTR may work with newer MG5 versions but is not officially tested. Check the [MadSTR GitHub repository](https://github.com/mg5amcnlo/MadSTR) for the latest status. |

### References

- DR and DS for tW: Frixione, Laenen, Motylinski, Webber, White, "Single-top hadroproduction in association with a W boson", JHEP 0807 (2008) 029 ([arXiv:0805.3067](https://arxiv.org/abs/0805.3067))
- tW isolation at the LHC: White, Frixione, Laenen, Maltoni, "Isolating Wt production at the LHC", JHEP 0911 (2009) 074 ([arXiv:0908.0631](https://arxiv.org/abs/0908.0631))
- On-shell subtraction generalization (MadSTR framework): Frixione, Fuks, Hirschi, Mawatari, Shao, Sunder, Zaro, "Automated simulations beyond the Standard Model: supersymmetry", JHEP 12 (2019) 008 ([arXiv:1907.04898](https://arxiv.org/abs/1907.04898))
- MadSTR repository: [github.com/mg5amcnlo/MadSTR](https://github.com/mg5amcnlo/MadSTR)

## Loop-Induced Processes with Additional Jets

## Squared Order Constraints in Loop-Induced Processes

Squared order constraints (`^2==`, `^2<=`, `^2>`) **are fully supported** for loop-induced `[noborn=QCD]` processes. They filter contributions at the squared-amplitude level based on coupling-order composition.

### Standard Coupling Orders

You can use squared order constraints on QCD and QED:

```
import model loop_sm
generate g g > z z QED^2==4 [noborn=QCD]
generate g g > z z QCD^2==4 [noborn=QCD]
```

Both commands are syntactically valid and produce diagrams. However, for processes where all diagrams share the same coupling-order composition, these constraints do not separate topologically distinct contributions.

### The Box vs Triangle Problem

In `g g > z z`, both the box diagrams (quark loops with four vertices) and the triangle diagrams (s-channel Higgs with ggH and HZZ vertices) have **identical** QCD and QED coupling orders: `QCD^2==4` and `QED^2==4`. Standard squared order constraints on QCD/QED therefore cannot distinguish them.

The same issue arises in any loop-induced process where different diagram topologies share identical coupling-order powers (e.g., `g g > h h`, `g g > z a`).

### Solution: Custom Coupling Orders in the UFO Model

To separate contributions with identical standard coupling orders, introduce a **custom coupling order** in the UFO model that tags the vertex unique to one topology. For example, to separate box and triangle contributions in `g g > z z`:

**Step 1.** In the UFO model directory (e.g., `models/loop_sm/`), edit `coupling_orders.py` to register a new order:

```python
# Add to coupling_orders.py
HZZ = CouplingOrder(name='HZZ', expansion_order=99, hierarchy=2)
```

**Step 2.** In `couplings.py`, find the coupling used for the Z-Z-H vertex and add the new order. For example, change:

```python
order = {'QED': 1}
```
to:
```python
order = {'QED': 1, 'HZZ': 1}
```

**Step 3.** Delete all `*.pkl` files in the UFO model directory so MG5 reloads from source:

```bash
rm models/loop_sm/*.pkl
```

**Step 4.** Generate with squared order constraints on the custom coupling:

```
import model loop_sm
generate g g > z z [noborn=QCD] HZZ^2==0    # box diagrams only (no HZZ vertex)
generate g g > z z [noborn=QCD] HZZ^2==1    # interference (box × triangle)
generate g g > z z [noborn=QCD] HZZ^2==2    # triangle diagrams only (HZZ vertex squared)
```

The squared order `HZZ^2==N` counts powers of the custom coupling at the squared-amplitude level: `N=0` selects terms with no HZZ vertices (box), `N=2` selects terms with two HZZ vertices (triangle squared), and `N=1` selects the cross-terms (interference).

**Key points:**
- The interference term (`HZZ^2==1`) can be **negative** — this is physical and expected. The interference between box and triangle contributions is destructive in certain kinematic regions.
- Events from the interference sample carry signed weights. Treat them the same way as MC@NLO negative-weight events: fill histograms with the event weight including its sign.
- The sum of the three samples (box + interference + triangle) reproduces the full `g g > z z [noborn=QCD]` result.
- Amplitude-level constraints (e.g., `QCD=2`) take precedence over squared order constraints. If an amplitude-level constraint makes a squared order value unreachable, no diagrams are generated. Do not combine both unless you understand their interaction.
- Squared order constraints are **not supported in decay specifications** — applying them in a decay chain raises a `MadGraph5Error`.

### Alternative: Loop Diagram Filtering

For advanced users, MG5 provides a `user_filter` function in `madgraph/loop/loop_diagram_generation.py` that can filter individual loop diagrams programmatically based on their coupling orders via `diag.get_loop_orders(model)`. This is useful when the process has many diagram topologies and custom coupling orders alone are insufficient.

### Mixing Restriction

MG5 explicitly forbids combining loop-induced processes with non-loop-induced processes in the same generation run. For example:

```
import model loop_sm
generate g g > h [noborn=QCD]      # loop-induced (gg→H)
add process p p > h j [QCD]        # NLO with Born (qq̄→Hg, qg→Hq)
```

This will **fail** because MG5 detects the inconsistency: some subprocesses are loop-induced (`has_born=False`) while others have a tree-level Born contribution (`has_born=True`). The code explicitly checks for this mismatch and raises an error.

**Workaround**: Generate loop-induced and non-loop-induced contributions as separate runs and combine the results at the analysis level (add cross-sections and merge event samples).

### The `[noborn=QCD]` Scope

The `[noborn=QCD]` directive applies **globally** to all subprocesses in the generation. It tells MG5 to skip the Born (tree-level) contribution for every subprocess, not just the ones that are genuinely loop-induced. If some subprocesses have valid tree-level contributions, those contributions are silently discarded, producing incomplete results.

For example, adding jets to a loop-induced process:

```
generate g g > h j [noborn=QCD]
```

This generates `gg → Hg` at one loop (loop-induced) but also includes subprocesses like `q q̄ → H g` where a tree-level Born **does** exist. With `[noborn=QCD]`, the tree-level Born for `q q̄ → H g` is suppressed, giving wrong results for those subprocesses.

**Best practice**: Only use `[noborn=QCD]` when ALL subprocesses in the generation are genuinely loop-induced. When mixing with processes that have tree-level contributions, generate them separately.

## Common Pitfalls

1. **Wrong model**: `import model sm` with `[QCD]` fails — must use `loop_sm`.
2. **Forgetting shower**: NLO events need MC@NLO matching to a shower for physical predictions. Fixed-order NLO events alone are not suitable for direct experimental comparison.
3. **Negative weights in histograms**: Each event must be filled with its weight (which can be negative). Ignoring weights gives wrong distributions.
4. **Pole cancellation with VBF**: Use `IRPoleCheckThreshold = -1.0d0` for VBF/VBS processes.
5. **Comparing v2 and v3**: Check `nlo_mixed_expansion` setting if comparing cross-sections between versions.
6. **Overly tight generation cuts at NLO**: NLO real-emission topologies explore different phase-space regions than Born. Generation-level cuts that work at LO can starve the real-emission integration at NLO, causing zero cross-section or wildly fluctuating results. Use loose generation cuts and apply tight cuts at analysis level (via `FixedOrderAnalysis` or after showering).
7. **Mixing loop-induced with Born processes**: Cannot combine `[noborn=QCD]` and `[QCD]` processes in the same run. Generate separately and combine at analysis level.
8. **`[noborn=QCD]` with non-loop-induced subprocesses**: The directive suppresses Born for ALL subprocesses. Only use when every subprocess is genuinely loop-induced.

## Flavor Scheme Choices at NLO (4FS vs 5FS)

When generating NLO processes involving b-quarks, you must choose a consistent flavor scheme. The two options are the **5-flavor scheme (5FS)** and the **4-flavor scheme (4FS)**. All three ingredients — model (b-quark mass), PDF set (number of active flavors), and multiparticle definitions (proton/jet content) — must be mutually consistent.

### 5-Flavor Scheme (5FS)

In the 5FS the b-quark is treated as massless and appears as a parton inside the proton. Initial-state collinear logarithms ln(Q²/m_b²) are resummed into the b-quark PDF. Use a model with the `-no_b_mass` restriction:

```
import model loop_sm-no_b_mass
# b/b~ are automatically included in the default p and j definitions
# when the b-quark is massless in the model
generate p p > b b~ z [QCD]
output bbZ_5FS_NLO
launch bbZ_5FS_NLO
  shower=PYTHIA8
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  set run_card maxjetflavor 5
  done
```

This is a well-defined NLO calculation. MG5 generates all relevant subprocesses (including `b b~ > b b~ z`, `g g > b b~ z`, `q q~ > b b~ z`, etc.) with full NLO QCD corrections, FKS subtraction, and MC@NLO matching.

**Key points for 5FS:**
- Import `sm-no_b_mass` or `loop_sm-no_b_mass`. MG5 auto-upgrades `sm-no_b_mass` to `loop_sm-no_b_mass` when `[QCD]` is used.
- The proton and jet multiparticle labels automatically include `b b~` when the b-quark is massless in the model.
- Use a 5-flavor PDF set (e.g., `NNPDF31_nlo_as_0118`).
- Set `maxjetflavor = 5` in the run_card.
- The b-quark Yukawa coupling is zero (`ymb = 0`) in this model. Processes that proceed through the b-Yukawa (e.g., `b b~ > h`) have zero cross-section in the 5FS with `sm-no_b_mass`. To keep a nonzero b-Yukawa with a massless b-quark, you must create a custom restriction file: copy `models/loop_sm/restrict_no_b_mass.dat`, edit it to set `MB = 0` but keep `ymb ≠ 0`, and save it as `models/loop_sm/restrict_<your_name>.dat`. Then import with `import model loop_sm-<your_name>`. Note: this is an advanced setup — at NLO, a nonzero Yukawa with massless b requires care at the model-generation level.

### 4-Flavor Scheme (4FS)

In the 4FS the b-quark is massive and does **not** appear as a parton inside the proton. The b-quark is produced only through the hard matrix element. Use the default model (massive b):

```
import model loop_sm
define p = g u c d s u~ c~ d~ s~
define j = g u c d s u~ c~ d~ s~
generate p p > b b~ z [QCD]
output bbZ_4FS_NLO
launch bbZ_4FS_NLO
  shower=PYTHIA8
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  set run_card maxjetflavor 4
  # Use a 4-flavor PDF set:
  set run_card lhaid 320500  # NNPDF31_nlo_as_0118_nf_4
  done
```

**Key points for 4FS:**
- Use the standard `loop_sm` model (massive b-quark, `MB ≈ 4.7 GeV`).
- Redefine `p` and `j` to exclude `b b~`.
- Use a 4-flavor PDF set (`nf = 4`).
- Set `maxjetflavor = 4` in the run_card.
- The b-quark mass provides a physical IR cutoff, so final-state b-quarks are always resolved.

### Comparison

| Setting | 5-Flavor Scheme | 4-Flavor Scheme |
|---------|----------------|----------------|
| Model | `loop_sm-no_b_mass` | `loop_sm` |
| b-quark mass | 0 (massless) | ~4.7 GeV (massive) |
| b in proton/jet | Yes (automatic) | No (redefine `p`, `j` to exclude) |
| PDF | 5-flavor set | 4-flavor set |
| `maxjetflavor` | 5 | 4 |
| Inclusive normalization | Better (resums ln(Q²/m_b²)) | Worse at high Q² |
| b-jet kinematics | Approximate (massless b) | Better (massive b, threshold effects) |

### Common Inconsistency: Massive b + 5-Flavor PDF

Using the default `loop_sm` model (massive b) while keeping b-quarks in the proton definition and a 5-flavor PDF is **inconsistent** and can cause IR pole cancellation failures at NLO. The FKS subtraction terms assume massless initial-state partons, but the matrix elements use a massive b propagator, so the soft/collinear limits do not match. This is the typical cause of `Poles do not cancel` errors in b-quark processes — not a fundamental limitation of the process itself, but a flavor-scheme inconsistency.

**Rule:** If b is in the proton, use a massless-b model. If b is massive, exclude it from the proton.

## Cross-References

- **[← Reference: NLO & Matching](nlo_and_matching.md)**
- [Process Syntax](02_process_syntax.md) — `[QCD]`, `[virt=QCD]`, `[noborn=QCD]` syntax
- [Models](03_models.md) — loop_sm model
- [Cards & Parameters](04_cards_and_parameters.md) — NLO-specific run_card parameters
- [Scripted Execution](05_scripted_execution.md) — NLO script examples
- [Matching & Merging](07_matching_merging.md) — FxFx merging
- [Decays & MadSpin](08_decays_and_madspin.md) — MadSpin with NLO
- [Parton Shower — Pythia8](09_parton_shower_pythia8.md) — MC@NLO interface
- [Systematics & Reweighting](13_systematics_reweighting.md) — scale/PDF variations at NLO
- [Troubleshooting](16_troubleshooting.md) — pole errors, negative weights
- [Detector Simulation — Delphes](10_detector_simulation_delphes.md) — Delphes in the NLO chain
- [Scale Choices](20_scale_choices.md) — renormalization/factorization scale options
- [EW NLO Corrections](25_ew_nlo_corrections.md) — `[QED]` syntax, `nlo_mixed_expansion`, EW Sudakov logarithms
