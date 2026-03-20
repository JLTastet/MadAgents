# 05 — Scripted (Non-Interactive) Execution

Script-based execution is the recommended way to run MadGraph5 for reproducibility, automation, and batch processing. A script is a plain text file containing MG5 commands, one per line, executed with:

```
<MG5_DIR>/bin/mg5_aMC my_script.mg5
```

## Script Structure

A typical script follows this pattern:

```
# 1. Load model
import model sm

# 2. Define process
generate p p > t t~

# 3. Create process directory
output my_ttbar

# 4. Launch event generation with settings
launch my_ttbar
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  done
```

Lines starting with `#` are comments and are ignored.

## The Launch Dialogue in Scripts

When `launch` runs, MadGraph enters a dialogue with two stages:

1. **Switches**: Enable/disable parton shower, detector simulation, MadSpin, analysis tools. In scripts, provide switch commands before `done`.
2. **Card editing**: Modify parameters with `set` commands. End with `done`.

In practice, for simple LO runs, a single `done` after `set` commands handles both stages. For runs with optional tools (Pythia8, Delphes, MadSpin), you may need to enable them explicitly.

### Enabling Optional Tools

In scripts, set switches by keyword assignment or numeric selection before the card-editing stage:

```
launch my_process
  shower=PYTHIA8
  detector=Delphes
  madspin=ON
  set run_card nevents 10000
  done
```

Or equivalently by answering the numbered menu:

```
launch my_process
  1           # toggle shower (ON)
  2           # toggle detector (ON)
  3           # toggle MadSpin (ON)
  done        # proceed to card editing
  set run_card nevents 10000
  done        # start the run
```

The exact numbering depends on what tools are installed and the MG5 version. Using keyword assignments (`shower=PYTHIA8`) is more portable.

---

## Complete Script Examples

### Example 1: LO Cross-Section Calculation

Compute the LO cross-section for e+e- → μ+μ- at √s = 91.2 GeV:

```
import model sm
generate e+ e- > mu+ mu-
output ee_mumu
launch ee_mumu
  set run_card ebeam1 45.6
  set run_card ebeam2 45.6
  set run_card lpp1 0
  set run_card lpp2 0
  set run_card nevents 10000
  done
```

Note: For e+e- collisions, set `lpp1 = lpp2 = 0` (no PDFs) and each beam energy is half the center-of-mass energy.

### Example 2: LO Event Generation with Pythia8

Generate pp → tt̄ events at 13 TeV with parton shower:

```
import model sm
generate p p > t t~
output ttbar_shower
launch ttbar_shower
  shower=PYTHIA8
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  done
```

### Example 3: Full Chain — Pythia8 + Delphes

Generate pp → tt̄ with shower and detector simulation:

```
import model sm
generate p p > t t~
output ttbar_full
launch ttbar_full
  shower=PYTHIA8
  detector=Delphes
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  done
```

The Delphes output (ROOT file) appears in `ttbar_full/Events/run_01/tag_1_delphes_events.root`.

### Example 4: With MadSpin Decays

Generate pp → tt̄ with spin-correlated top decays:

```
import model sm
generate p p > t t~
output ttbar_madspin
launch ttbar_madspin
  shower=PYTHIA8
  madspin=ON
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  set madspin_card decay t > w+ b, w+ > l+ vl
  set madspin_card decay t~ > w- b~, w- > l- vl~
  done
```

See [Decays & MadSpin](08_decays_and_madspin.md) for MadSpin configuration details.

### Example 5: NLO QCD Computation

Compute the NLO QCD cross-section for pp → tt̄:

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

Note: NLO requires `import model loop_sm` instead of `sm`. See [NLO Computations](06_nlo_computations.md).

### Example 6: MLM Matched Samples

Generate matched tt̄ + 0,1,2 jets:

```
import model sm
generate p p > t t~ @0
add process p p > t t~ j @1
add process p p > t t~ j j @2
output ttbar_matched
launch ttbar_matched
  shower=PYTHIA8
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 50000
  set run_card ickkw 1
  set run_card xqcut 20
  set run_card maxjetflavor 4
  set pythia8_card JetMatching:qCut 30
  set pythia8_card JetMatching:nJetMax 2
  done
```

See [Matching & Merging](07_matching_merging.md) for parameter tuning and validation.

### Example 7: Parameter Scan (Multiple Launches)

Run the same process with different parameter values:

```
import model sm
generate p p > t t~
output ttbar_scan

launch ttbar_scan
  set param_card mass 6 172.5
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  done

launch ttbar_scan
  set param_card mass 6 180.0
  set run_card nevents 10000
  done

launch ttbar_scan
  set param_card mass 6 165.0
  set run_card nevents 10000
  done
```

Each `launch` creates a new run directory (`run_01`, `run_02`, `run_03`).

### Example 8: Higgs via Gluon Fusion (heft Model)

```
import model heft
generate g g > h
output ggH_heft
launch ggH_heft
  shower=PYTHIA8
  madspin=ON
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  set madspin_card decay h > b b~
  done
```

### Example 9: BSM Workflow — 2HDM Charged Higgs

Requires the 2HDM UFO model (download from FeynRules and place in `<MG5_DIR>/models/`).

```
import model 2HDM
display particles
generate p p > h+ h-
output charged_higgs
launch charged_higgs
  set param_card mass 37 300.0
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  done
```

### Example 10: Using compute_widths

```
import model sm
compute_widths t w+ w- z h
```

This prints widths and branching ratios to screen and can be used to update the param_card consistently. See [MadWidth](12_madwidth.md).

### Example 11: Providing Pre-Edited Card Files

Instead of using `set` commands, provide paths to pre-edited card files:

```
import model sm
generate p p > t t~
output ttbar_custom
launch ttbar_custom
  /path/to/my_run_card.dat
  /path/to/my_param_card.dat
  done
```

MadGraph auto-detects the card type from the file content and copies it to the correct location.

---

## Output Directory Structure

After a successful run, the output directory looks like:

```
my_process/
├── Cards/              # Configuration cards (param_card.dat, run_card.dat, ...)
├── Events/
│   ├── run_01/         # First run
│   │   ├── unweighted_events.lhe.gz          # Parton-level events
│   │   ├── tag_1_pythia8_events.hepmc.gz     # After Pythia8 (if enabled)
│   │   ├── tag_1_delphes_events.root         # After Delphes (if enabled)
│   │   ├── run_01_tag_1_banner.txt           # Run banner with all settings
│   │   └── ...
│   └── run_02/         # Second run (from subsequent launch)
│       └── ...
├── SubProcesses/       # Generated Fortran code
├── Source/              # Common source code
├── lib/                # Libraries
├── bin/                # Executables
└── HTML/               # Web-based results viewer
```

### Locating Key Output Files

| File | Location | When |
|------|----------|------|
| LHE events | `Events/run_XX/unweighted_events.lhe.gz` | Always (LO) or after event generation (NLO) |
| Pythia8 output | `Events/run_XX/tag_1_pythia8_events.hepmc.gz` | When shower is enabled |
| Delphes output | `Events/run_XX/tag_1_delphes_events.root` | When Delphes is enabled |
| Run banner | `Events/run_XX/run_XX_tag_1_banner.txt` | Always |
| Cross-section | Printed to stdout; also in `Events/run_XX/run_XX_tag_1_banner.txt` | Always |

The exact paths are printed at the end of each `launch` in the terminal output.

---

## Tips for Robust Scripts

1. **Always specify beam energies explicitly** — don't rely on defaults, which may change between versions.
2. **Use `done` to advance through dialogue stages** — even if keeping all defaults.
3. **Use `set` for parameter changes** — this is more portable than editing card files.
4. **Comment your scripts** — lines starting with `#` are ignored.
5. **Set the random seed** for reproducible results: `set run_card iseed 42`.
6. **For e+e- collisions**, remember to set `lpp1 = lpp2 = 0`.
7. **Multiple launches reuse the output directory** — each creates a new `run_XX` subdirectory.

## Common Pitfalls

- **Missing `done`**: The script hangs waiting for input. Always end the launch block with `done`.
- **Wrong beam type**: Forgetting `lpp1 = lpp2 = 0` for e+e- collisions uses proton PDFs and gives wrong results.
- **NLO with wrong model**: Using `import model sm` instead of `loop_sm` for `[QCD]` processes fails.
- **Matching without `@N` tags**: Using `ickkw=1` without proper `@N` multiplicity tags gives wrong results.

## Cross-References

- **[← Reference: Configuration](configuration.md)**
- [Process Syntax](02_process_syntax.md) — `generate`, `output`, `launch` commands
- [Cards & Parameters](04_cards_and_parameters.md) — all card parameters
- [NLO Computations](06_nlo_computations.md) — NLO-specific scripting
- [Matching & Merging](07_matching_merging.md) — matched sample scripts
- [Decays & MadSpin](08_decays_and_madspin.md) — MadSpin in scripts
- [Interactive Mode](18_interactive_mode.md) — converting interactive sessions to scripts
- [Parton Shower — Pythia8](09_parton_shower_pythia8.md) — enabling Pythia8 in scripts
- [Detector Simulation — Delphes](10_detector_simulation_delphes.md) — enabling Delphes in scripts
- [Systematics & Reweighting](13_systematics_reweighting.md) — systematic variations in scripts
- [Gridpacks](14_gridpacks.md) — gridpack production scripts
- [Output Formats](15_output_formats_lhe.md) — LHE, HepMC, ROOT output files
- [Troubleshooting](16_troubleshooting.md) — common script errors and fixes
- [Parameter Scans](21_parameter_scans.md) — `scan:` syntax in scripts
- [Lepton & Photon Colliders](22_lepton_photon_colliders.md) — `lpp` beam configuration in scripts
- [Biased Event Generation](24_biased_event_generation.md) — `bias_module` in scripts
