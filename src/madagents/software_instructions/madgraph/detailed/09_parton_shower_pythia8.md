# 09 — Parton Shower — Pythia8

Pythia8 is the parton shower and hadronization program integrated with MadGraph5. It takes the parton-level LHE events from MG5 and adds:

- **Parton shower**: QCD and QED radiation from initial- and final-state partons
- **Hadronization**: Conversion of quarks and gluons into hadrons (using the Lund string model)
- **Underlying event**: Multiple parton interactions from the same proton-proton collision
- **Particle decays**: Decays of unstable hadrons and tau leptons

## Enabling Pythia8 in Scripts

```
launch my_process
  shower=PYTHIA8
  set run_card nevents 10000
  done
```

The showered output is written as a HepMC file:
`Events/run_01/tag_1_pythia8_events.hepmc.gz`

## Installation

If Pythia8 is not installed, MG5 reports an error when you try to enable the shower. Install from within MG5:

```
install pythia8
```

This downloads, compiles, and configures Pythia8 automatically. See [Installation & Setup](01_installation_setup.md).

## pythia8_card.dat

The Pythia8 configuration card is located in `<PROC_DIR>/Cards/pythia8_card.dat`. It uses Pythia8's native syntax of `Setting:Parameter = Value`.

### Key Settings

#### Tune

```
Tune:pp = 14              ! Monash 2013 tune (default, recommended)
```

The tune sets a consistent set of shower, hadronization, and underlying event parameters fitted to data.

#### MLM Matching Parameters

When using MLM matching (`ickkw = 1` in the run_card):

```
JetMatching:scheme = 1         ! shower-kt MLM scheme
JetMatching:qCut = 30          ! matching scale in GeV (must be > xqcut)
JetMatching:nJetMax = 2        ! maximum number of matched jets
```

The `qCut` must be larger than `xqcut` in the run_card. See [Matching & Merging](07_matching_merging.md) for proper setup.

#### MC@NLO Parameters

For NLO runs with MC@NLO matching, Pythia8 parameters are typically set automatically by MG5. The key settings control the shower starting scale and the handling of negative-weight events.

#### Hadronization and Decays

Pythia8 handles hadronization by default. You can control which particles Pythia8 decays (vs leaving stable for a downstream tool like Delphes or an analysis framework):

```
! Example: keep tau leptons stable for Delphes to handle
15:mayDecay = off
```

#### HepMC Output

## HepMC Output Control

### HEPMCoutput:file

The `HEPMCoutput:file` parameter in `pythia8_card.dat` controls where and how the showered HepMC events are written. This is important for managing disk usage, especially for large event samples.

| Value | Description | Typical use case |
|-------|-------------|------------------|
| `hepmc.gz` | **(default)** Writes compressed `.hepmc.gz` file to `Events/run_XX/`. | Standard workflow; keep HepMC for later analysis. |
| `auto` | Runtime alias — resolves to `hepmc.gz`. Equivalent behavior. | Commonly seen in example cards; identical to the default. |
| `hepmc` | Writes **uncompressed** `.hepmc` file to `Events/run_XX/`. | When downstream tools cannot read gzipped HepMC. |
| `autoremove` | Writes the HepMC file during showering, then **automatically deletes it** after the downstream tool (e.g. Delphes) finishes reading. | Pythia8 + Delphes chain where only the Delphes ROOT output is needed. **Recommended for production with Delphes.** |
| `hepmcremove` | Same behavior as `autoremove`. | Alternative spelling. |
| `/dev/null` | Suppresses HepMC output entirely — nothing is written to disk. | When you only need Pythia8 to run (e.g. for matching efficiency) but not the output file. |
| `fifo` | Creates a **named pipe** (FIFO) instead of a regular file in `Events/run_XX/`. External tools (Rivet, MadAnalysis5) read from the pipe in real time with zero disk usage. | Streaming events to an analysis framework without intermediate files. |
| `fifo@<path>` | Same as `fifo` but creates the FIFO at a user-specified path. The file extension **must** be `.hepmc.fifo`. | When the default location does not support FIFOs (e.g. certain network filesystems). |
| `hepmc@<dir>` | Intended to redirect HepMC output to an existing directory `<dir>`. **Bug warning:** this feature is broken in MG5 3.7.0 — see note below. | Redirecting output to a different disk or mount point. |

> **Known bug (MG5 3.7.0):** The `hepmc@<dir>` option crashes with `UnboundLocalError: cannot access local variable 'hepmc_fileformat'` in `store_result()` (`madevent_interface.py`). The variable `hepmc_fileformat` is only initialized inside the `compressHEPMC` branch but is used unconditionally when `moveHEPMC` is in `to_store`. The `hepmc@` format does not set `compressHEPMC`, so the variable is uninitialized. The `run_XX/` subdirectory inside `<dir>` is created, but the file move fails. **Do not use `hepmc@<dir>` in current releases.** Use `autoremove` or `/dev/null` for disk management instead.

#### Setting HEPMCoutput:file in a Script

```
launch my_process
  shower=PYTHIA8
  # Only keep Delphes ROOT output — remove intermediate HepMC
  set pythia8_card HEPMCoutput:file autoremove
  done
```

```
launch my_process
  shower=PYTHIA8
  # Suppress HepMC output entirely
  set pythia8_card HEPMCoutput:file /dev/null
  done
```

```
launch my_process
  shower=PYTHIA8
  # Stream events via named pipe for real-time analysis
  set pythia8_card HEPMCoutput:file fifo
  done
```

**Key points:**
- The default is `hepmc.gz` (compressed `.hepmc.gz` output in `Events/run_XX/`). The value `auto` is an accepted alias that resolves to `hepmc.gz`.
- For Pythia8 + Delphes workflows, use `autoremove` (or equivalently `hepmcremove`) to avoid accumulating large HepMC files.
- `/dev/null` is the most aggressive option — use it only when no downstream tool needs the HepMC events.
- `fifo` enables zero-disk-usage analysis but requires the reading tool to be launched before or concurrently with the MadGraph run.
- Do not use `hepmc@<dir>` in MG5 3.7.0 — it is broken due to an uninitialized variable bug.

### HEPMCoutput:scaling

Controls the weight normalization in the HepMC output. The scaling factor converts weights from millibarns (mb, the native HepMC convention) to the desired unit.

```
HEPMCoutput:scaling = 1.0e9   ! default; weights in pb (1 mb = 1e9 pb)
```

| Value | Resulting weight unit |
|-------|----------------------|
| `1.0e9` | **(default)** picobarns (pb) |
| `1.0` | millibarns (mb) — native HepMC convention |
| `1.0e12` | femtobarns (fb) |

This parameter is hidden (not shown in the default card) but can be set explicitly.

`HEPMCoutput:file` and `HEPMCoutput:scaling` are the **only** two `HEPMCoutput` parameters in MadGraph. No other `HEPMCoutput:*` parameters exist.

The showered events are written in HepMC format (`.hepmc.gz`), which can be read by Delphes, MadAnalysis5, and other analysis tools.

## Modifying Pythia8 Settings in Scripts

Use the `set` command during the launch dialogue:

```
launch my_process
  shower=PYTHIA8
  set pythia8_card JetMatching:qCut 30
  set pythia8_card JetMatching:nJetMax 2
  set pythia8_card Tune:pp 14
  done
```

Alternatively, provide a pre-edited pythia8_card:

```
launch my_process
  shower=PYTHIA8
  /path/to/my_pythia8_card.dat
  done
```

## Pythia8 in the Simulation Chain

```
MadGraph5 (LHE) → Pythia8 (HepMC) → Delphes (ROOT) → Analysis
```

Pythia8 reads the LHE events and produces showered/hadronized events. If Delphes is also enabled, MG5 pipes the Pythia8 output directly to Delphes.

## Cross-Section After Showering

For simple (non-matched) processes, the cross-section after Pythia8 should agree with the MG5 cross-section within statistical uncertainties. The shower does not change the total cross-section — it only redistributes events in phase space.

For matched samples (MLM), the post-shower cross-section differs from the pre-shower sum because matching vetoes reject double-counted events. The post-shower value is the physical cross-section. See [Matching & Merging](07_matching_merging.md).

## NLO: The `parton_shower` Run-Card Parameter

For NLO processes, the run_card contains a `parton_shower` parameter that selects which parton shower's MC@NLO subtraction terms are included in the event generation. This parameter **only appears in NLO run_cards** — LO processes do not have it.

### Available Values

| Value | Shower program |
|-------|----------------|
| `HERWIG6` | **Code-level default.** HERWIG 6 (legacy, frozen code) |
| `HERWIGPP` | Herwig++ / Herwig 7 |
| `PYTHIA6Q` | Pythia 6 (Q-ordered shower) |
| `PYTHIA6PT` | Pythia 6 (pT-ordered shower) |
| `PYTHIA8` | Pythia 8 (recommended for most workflows) |

> **Important:** The **code-level default** in `RunCardNLO` is `HERWIG6`, not `PYTHIA8`. This is a historical default. In practice, when you specify `shower=PYTHIA8` in the launch command, MG5 automatically overrides the run_card value to `PYTHIA8`, so you rarely encounter the HERWIG6 default directly.

### How `shower=` and `parton_shower` Interact

The `shower=PYTHIA8` launch option does two things:
1. Sets the actual shower program that will run after event generation.
2. Automatically updates `parton_shower` in the NLO run_card to match.

You should **not** set `parton_shower` manually in the run_card and then use a different `shower=` value — the MC@NLO subtraction terms are shower-dependent, and a mismatch produces incorrect results.

```
# Correct — shower= and parton_shower agree (set automatically):
launch my_nlo_process
  shower=PYTHIA8
  done

# The run_card will contain: PYTHIA8 = parton_shower (set by MG5)
```

```
# Also correct — explicit run_card setting matching the shower:
launch my_nlo_process
  shower=PYTHIA8
  set run_card parton_shower PYTHIA8
  done
```

**Key points:**
- The `parton_shower` NLO run_card parameter selects which shower's MC@NLO counter-terms are computed. It must match the shower program used.
- The code-level default is `HERWIG6` (historical). Specifying `shower=PYTHIA8` at launch time overrides this automatically.
- You cannot shower NLO events with a different program than specified in `parton_shower` — the subtraction terms are shower-specific.
- For LO processes, this parameter does not exist; only the `shower=` launch option matters.

## Cross-References

- **[← Reference: Shower, Detector & Analysis](shower_detector_analysis.md)**
- [Cards & Parameters](04_cards_and_parameters.md) — pythia8_card settings
- [Scripted Execution](05_scripted_execution.md) — enabling Pythia8 in scripts
- [NLO Computations](06_nlo_computations.md) — MC@NLO interface
- [Matching & Merging](07_matching_merging.md) — MLM/FxFx matching with Pythia8
- [Detector Simulation — Delphes](10_detector_simulation_delphes.md) — next step in the chain
- [Installation & Setup](01_installation_setup.md) — installing Pythia8
- [Decays & MadSpin](08_decays_and_madspin.md) — MadSpin decays before showering
- [Output Formats](15_output_formats_lhe.md) — HepMC output from Pythia8
