# MadGraph5_aMC@NLO — Overview

MadGraph5_aMC@NLO (MG5_aMC) is a framework for automated Monte Carlo simulation of particle physics processes at leading order (LO) and next-to-leading order (NLO) in QCD. It generates matrix elements, performs phase-space integration, and produces parton-level events in Les Houches Event (LHE) format. Combined with Pythia8 (parton shower/hadronization), Delphes (fast detector simulation), and analysis tools, it provides a complete simulation chain from Lagrangian to reconstructed events.

## Simulation Chain

```
Hard process — matrix elements, LHE events (MadGraph5)
  → Parton shower — shower, hadronization, underlying event (Pythia8, Herwig7, ...)
  → Detector simulation — fast/full detector response (Delphes, Geant4, ...)
  → Analysis — cuts, histograms, signal regions (MadAnalysis5, Rivet, ...)
```

Additional tools plug into this chain, e.g.: **MadSpin** (spin-correlated decays, between hard process and parton shower), **MadWidth** (decay width computation).

## Quick Start — Script-Based Execution

Save the following as `ttbar.mg5` and run with `<MG5_DIR>/bin/mg5_aMC ttbar.mg5`:

```
import model sm
generate p p > t t~
output ttbar_LO
launch ttbar_LO
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  done
```

This generates 10,000 LO t-tbar events at 13 TeV. Results appear in `ttbar_LO/Events/run_01/`.

## Reference Documentation

| Reference File | Description |
|----------------|-------------|
| [Process Generation](process_generation.md) | Process syntax, models (sm/heft/loop_sm), coupling orders, multiparticle labels, diagram filtering (`/`, `$`, `$$`), polarized bosons, flavor schemes |
| [Configuration](configuration.md) | param_card/run_card essentials, scripted execution, PDF selection, scale choices, parameter scans |
| [NLO & Matching](nlo_and_matching.md) | NLO syntax (`[QCD]`/`[noborn]`), MC@NLO, MLM/FxFx matching setup, xqcut/qCut guidance, DJR validation, EW corrections |
| [Decays & Widths](decays_and_widths.md) | Decay chain syntax, MadSpin, MadWidth, complex mass scheme, NWA, bwcutoff, choosing a decay method |
| [Shower, Detector & Analysis](shower_detector_analysis.md) | Pythia8 settings, Delphes detector cards, MadAnalysis5, LHE format, Python parsing |
| [Production & Troubleshooting](production_and_troubleshooting.md) | Installation, gridpacks, systematics, common errors & fixes, lepton/photon colliders, biased generation |

Deep-dive documents for edge cases and advanced configurations: `ls /madgraph_docs/detailed/`. Docs for deprecated/superseded tools: `ls /madgraph_docs/deprecated/`.

## Key Conventions

- **Script-first**: All examples are shown as runnable script files (`<MG5_DIR>/bin/mg5_aMC script.mg5`) unless stated otherwise.
- **Placeholders**: `<PROC_DIR>` means a user-chosen process directory name. `<MG5_DIR>` means the MadGraph installation directory.
- **Version**: Documentation targets MG5_aMC v3.x. Version-specific differences are noted where relevant.
