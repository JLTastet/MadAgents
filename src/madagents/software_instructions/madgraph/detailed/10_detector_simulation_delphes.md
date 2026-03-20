# 10 — Detector Simulation — Delphes

Delphes is a fast detector simulation framework that approximates the response of a multipurpose particle detector (like CMS or ATLAS). It takes showered events from Pythia8 and produces reconstructed objects: jets, electrons, muons, photons, and missing transverse energy (MET).

## Role in the Simulation Chain

```
MadGraph5 (LHE) → Pythia8 (HepMC) → Delphes (ROOT) → Analysis
```

Delphes bridges the gap between particle-level predictions and experimental observables by applying:
- Energy smearing (calorimeter resolution)
- Tracking efficiency and resolution
- Jet clustering
- b-tagging with realistic efficiency and mistag rates
- Lepton identification and isolation
- Missing transverse energy reconstruction

## Enabling Delphes in Scripts

```
launch my_process
  shower=PYTHIA8
  detector=Delphes
  set run_card nevents 10000
  done
```

Pythia8 must also be enabled — Delphes reads the showered events. The output is a ROOT file:
`Events/run_01/tag_1_delphes_events.root`

## Installation

If Delphes is not installed:

```
install Delphes
```

This downloads and compiles Delphes within the MG5 installation. See [Installation & Setup](01_installation_setup.md).

## Detector Cards

Delphes uses a card file to define the detector configuration. Pre-built cards for major experiments are provided:

| Card | Description |
|------|-------------|
| `delphes_card_CMS.dat` | CMS detector configuration |
| `delphes_card_ATLAS.dat` | ATLAS detector configuration |
| `delphes_card_FCC.dat` | Future Circular Collider |

The default card is typically the CMS card. You can provide a custom card:

```
launch my_process
  shower=PYTHIA8
  detector=Delphes
  /path/to/my_delphes_card.dat
  done
```

## Detector Card Components

A Delphes card is organized into modules. Key configurable components:

### Jet Clustering

```
module FastJetFinder {
  set JetAlgorithm 6        # anti-kT algorithm
  set ParameterR 0.4        # cone radius
  set JetPTMin 20.0         # minimum jet pT (GeV)
}
```

Algorithm options: 6 = anti-kT (standard at LHC), 5 = Cambridge-Aachen, 4 = kT.

### b-Tagging

```
module BTagging {
  # b-jet efficiency (pT-dependent)
  add EfficiencyFormula {0} {0.001}    # light-jet mistag rate
  add EfficiencyFormula {4} {0.10}     # c-jet mistag rate
  add EfficiencyFormula {5} {0.70}     # b-jet tagging efficiency
}
```

### Other Configurable Modules

Delphes cards also configure: `ElectronEfficiency`, `MuonEfficiency` (pT/eta-dependent ID efficiency), `Isolation` (cone radius `DeltaRMax`, pT ratio `PTRatioMax`), `Calorimeter` (ECAL/HCAL energy resolution and segmentation), `MissingET` (computed from all visible objects), and `TauTagging`.

## Output Format

Delphes produces a ROOT file containing trees with reconstructed objects:

- `Jet`: Reconstructed jets with pT, eta, phi, mass, b-tag flag
- `Electron`: Reconstructed electrons with ID and isolation info
- `Muon`: Reconstructed muons
- `Photon`: Reconstructed photons
- `MissingET`: Missing transverse energy (MET)
- `Track`: Reconstructed tracks
- `Tower`: Calorimeter towers

The ROOT file can be analyzed with ROOT, PyROOT, uproot, or MadAnalysis5.

## Cross-References

- **[← Reference: Shower, Detector & Analysis](shower_detector_analysis.md)**
- [Scripted Execution](05_scripted_execution.md) — enabling Delphes in scripts
- [Parton Shower — Pythia8](09_parton_shower_pythia8.md) — Pythia8 output for Delphes input
- [Analysis — MadAnalysis5](11_analysis_madanalysis5.md) — analyzing Delphes ROOT output
- [Installation & Setup](01_installation_setup.md) — installing Delphes
- [Output Formats & LHE](15_output_formats_lhe.md) — ROOT output format details
- [Troubleshooting](16_troubleshooting.md) — diagnosing detector simulation issues
