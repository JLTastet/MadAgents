# 11 — Analysis — MadAnalysis5

MadAnalysis5 (MA5) is a framework for phenomenological analysis of Monte Carlo event files. It can define signal regions, apply kinematic cuts, produce histograms, and perform recasting of LHC analyses.

## Role in the Simulation Chain

```
MadGraph5 → Pythia8 → Delphes → MadAnalysis5
                                   ↑
                        (or directly from LHE/HepMC)
```

MA5 reads event files in multiple formats: LHE, HepMC, ROOT (Delphes), and LHCO.

## Installation

From within MadGraph5:

```
install MadAnalysis5
```

This downloads and configures MA5 within the MG5 installation. See [Installation & Setup](01_installation_setup.md).

## Enabling MA5 in MG5 Scripts

MA5 can be enabled as part of the MG5 launch chain:

```
launch my_process
  shower=PYTHIA8
  detector=Delphes
  analysis=MadAnalysis5
  set run_card nevents 50000
  done
```

When enabled, MA5 runs after Delphes (or after Pythia8 if no Delphes) and produces analysis outputs automatically.

## MA5 Standalone Usage

MA5 can also be run standalone on existing event files. It has two main modes:

### Normal Mode (Interactive/Command-Line)

MA5 provides its own command-line interface with a domain-specific language:

```
# Launch MA5
./bin/ma5

# Inside the MA5 session:
import /path/to/unweighted_events.lhe.gz
define mu = mu+ mu-
plot PT(mu[1]) 40 0 200 [logY]     # pT of leading muon
plot MET 40 0 500 [logY]            # missing ET distribution
select (mu) PT > 25                  # apply cut
plot M(mu[1] mu[2]) 40 0 200 [logY] # dimuon invariant mass
submit                                # generate plots and cutflow
```

### Expert Mode (C++ Analysis)

For complex analyses, MA5 provides a C++ framework (SampleAnalyzer) where users write custom analysis code with object selection, kinematic cuts, and histogram filling.

## Key Capabilities

### Kinematic Cuts and Selections

MA5 provides functions for:
- Object selection with pT, eta, and isolation cuts
- Invariant mass computation
- Angular separations (ΔR, Δη, Δφ)
- Missing transverse energy cuts
- Jet multiplicity and b-tag requirements

### Histograms

Create distributions of kinematic variables:
- Invariant mass distributions (e.g., dilepton mass, dijet mass)
- Transverse momentum spectra
- Angular distributions
- Event-level quantities (HT, MET, jet multiplicity)

### Signal Regions

Define selection criteria for physics analyses, mimicking experimental search strategies.

### Recasting

MA5 includes a recasting module that reimplements published LHC analyses, allowing users to test BSM models against existing experimental constraints. This compares signal predictions to observed limits from ATLAS and CMS searches.

## Example: WW → Dilepton Analysis

```
import model sm
generate p p > w+ w-
output ww_analysis
launch ww_analysis
  shower=PYTHIA8
  detector=Delphes
  analysis=MadAnalysis5
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 50000
  done
```

Expected distributions:
- The dilepton invariant mass should show a broad distribution from ~10 GeV to ~200 GeV, peaking around 40-80 GeV.
- It should **not** show a narrow peak at M_Z (91 GeV), since the leptons come from different W bosons.

## Output

MA5 produces:
- Histograms in various formats (ROOT, matplotlib)
- Cutflow tables showing efficiency of each selection step
- HTML reports with plots and statistics
- Signal region yields for recasting comparisons

## Cross-References

- **[← Reference: Shower, Detector & Analysis](shower_detector_analysis.md)**
- [Scripted Execution](05_scripted_execution.md) — enabling MA5 in MG5 scripts
- [Detector Simulation — Delphes](10_detector_simulation_delphes.md) — Delphes ROOT input for MA5
- [Output Formats & LHE](15_output_formats_lhe.md) — LHE input for MA5
- [Installation & Setup](01_installation_setup.md) — installing MA5
- [Parton Shower — Pythia8](09_parton_shower_pythia8.md) — HepMC input for MA5
