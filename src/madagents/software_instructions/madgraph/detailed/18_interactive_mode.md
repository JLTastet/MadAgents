# 18 — Interactive Mode

While script-based execution is recommended for reproducibility and automation (see [Scripted Execution](05_scripted_execution.md)), MG5 also supports an interactive mode useful for exploration, learning, and quick tests.

## Starting an Interactive Session

```bash
<MG5_DIR>/bin/mg5_aMC
```

This opens the interactive prompt:

```
MG5_aMC>
```

## Interactive Workflow

Commands are typed one at a time at the prompt:

```
MG5_aMC> import model sm
MG5_aMC> generate p p > t t~
MG5_aMC> display diagrams
MG5_aMC> output my_ttbar
MG5_aMC> launch my_ttbar
```

## The Launch Dialogue

When you type `launch`, MG5 enters a multi-stage dialogue:

### Stage 1: Switches

```
The following switches determine the programs/options to run:
  1 shower = OFF     (options: HERWIG7|PYTHIA8|OFF)
  2 detector = OFF   (options: DELPHES|OFF)
  3 madspin = OFF    (options: ON|OFF)
  4 analysis = OFF   (options: MadAnalysis5|OFF)
  Type a switch number to toggle, or press Enter/type 'done' to continue.
```

Toggle switches by typing their number (e.g., `1` to toggle shower to PYTHIA8). Type `done` or `0` to proceed.

### Stage 2: Card Editing

```
Do you want to edit any cards?
  1) run_card.dat
  2) param_card.dat
  3) pythia8_card.dat   (if shower enabled)
  0) Done
```

Options:
- Type a number to open a card for editing (in a text editor).
- Use `set` commands for quick changes: `set run_card ebeam1 6500`
- Provide a card file path: `/path/to/my_run_card.dat`
- Type `0` or `done` to start the run.

### Editor Note

In environments without a graphical text editor, MG5 may display:
```
Are you really that fast? .... Please confirm that you have finished to edit the file [y]
```
Type `y` to continue.

## Useful Interactive Commands

For a full list of `display` and `check` commands, see [Process Syntax](02_process_syntax.md). Key interactive-specific commands:

```
MG5_aMC> help                                 # general help
MG5_aMC> help generate                        # help on a specific command
MG5_aMC> history                              # show command history
MG5_aMC> display diagrams                     # view Feynman diagrams (opens viewer)
```

### Computing Widths

```
MG5_aMC> compute_widths t w+ w- z h           # compute and display widths
```

### Installing Tools

```
MG5_aMC> install pythia8
MG5_aMC> install Delphes
MG5_aMC> install MadAnalysis5
MG5_aMC> install lhapdf6
```

## Inspecting Results

After a run completes, MG5 prints the cross-section and output file paths. You can also:

```
MG5_aMC> open index.html                      # open web-based results viewer
```

The `index.html` in the process directory provides a graphical interface to view cross-sections, diagrams, and run history.

## Multiple Runs

You can launch multiple runs for the same process:

```
MG5_aMC> launch my_ttbar                      # creates run_01
# (edit cards, done)
MG5_aMC> launch my_ttbar                      # creates run_02
# (edit cards with different parameters, done)
```

## Converting Interactive Sessions to Scripts

To convert an interactive session to a script:

1. Note all commands you typed at the `MG5_aMC>` prompt.
2. For the `launch` dialogue, include the switch settings and `set` commands.
3. End the launch block with `done`.
4. Save as a `.mg5` text file.

Example conversion:

**Interactive:**
```
MG5_aMC> import model sm
MG5_aMC> generate p p > t t~
MG5_aMC> output my_ttbar
MG5_aMC> launch my_ttbar
> 1                        # toggle shower ON
> done                     # proceed to card editing
> set run_card nevents 10000
> done                     # start run
```

**Script (`my_ttbar.mg5`):**
```
import model sm
generate p p > t t~
output my_ttbar
launch my_ttbar
  shower=PYTHIA8
  set run_card nevents 10000
  done
```

The script form uses keyword assignments (`shower=PYTHIA8`) instead of numeric toggles for portability.

## Exiting

```
MG5_aMC> exit
```

Or `quit`, or Ctrl+D.

## Cross-References

- **[← Reference: Configuration](configuration.md)**
- [Scripted Execution](05_scripted_execution.md) — the recommended non-interactive approach
- [Process Syntax](02_process_syntax.md) — all commands available at the prompt
- [Cards & Parameters](04_cards_and_parameters.md) — card editing details
- [MadWidth](12_madwidth.md) — computing widths interactively
- [Parton Shower — Pythia8](09_parton_shower_pythia8.md) — installing Pythia8
- [Detector Simulation — Delphes](10_detector_simulation_delphes.md) — installing Delphes
- [Analysis — MadAnalysis5](11_analysis_madanalysis5.md) — installing MadAnalysis5
