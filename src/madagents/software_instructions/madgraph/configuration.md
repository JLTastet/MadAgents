# Configuration

Quick reference for MadGraph cards, scripted execution, PDFs, scales, and parameter scans.

---

## param_card.dat -- Physics Parameters

SLHA-format file in `<PROC_DIR>/Cards/`. Key blocks:

| Block | Key entries (PDG ID) | Example |
|-------|---------------------|---------|
| `MASS` | 6=top, 23=Z, 24=W, 25=Higgs | `set param_card mass 6 172.5` |
| `DECAY` | Width for each particle | `set param_card decay 6 auto` |
| `SMINPUTS` | 1=1/alpha_EW, 2=G_F, 3=alpha_s(MZ) | `set param_card sminputs 3 0.118` |
| `YUKAWA` | 5=ymb, 6=ymt, 15=ymtau | `set param_card yukawa 6 172.5` |

Setting a mass to zero makes that particle massless (changes diagrams and flavor scheme). Use `DECAY X auto` or `compute_widths` to keep widths consistent.

**Pitfall:** Changing input parameters without updating dependent ones causes warnings; use `compute_widths`.

**Details ->** [Cards & Parameters](detailed/04_cards_and_parameters.md)

---

## run_card.dat -- Run Configuration

## Execution Mode (run_mode, nb_core)

These are **MadEvent configuration options** (set in `input/mg5_configuration.txt` or via `set` at the MG5 prompt), not run_card parameters. They control how integration and event generation are parallelized.

| Option | Default | Values | Purpose |
|--------|---------|--------|---------|
| `run_mode` | **2** (multicore) | 0=sequential, 1=cluster, 2=multicore | Parallelization mode for integration/event generation |
| `nb_core` | None (auto-detect) | Integer or None | Number of CPU cores for multicore mode; None = use all available cores |

**Important:** `run_mode` and `nb_core` are MadEvent/configuration options. They must be set **before** any `launch` command — either in `input/mg5_configuration.txt`, or via `set` at the MG5 prompt before `launch`. They **cannot** be set inside a launch block (MG5 will issue `WARNING: invalid set command` if you try).

### Setting Execution Mode

In `input/mg5_configuration.txt` (persistent across sessions):

```
run_mode = 2
nb_core = 4
```

Or at the MG5 prompt or in a script, **before** the `launch` command:

```
set run_mode 2
set nb_core 4
launch my_proc
  set run_card nevents 10000
  done
```

### Cluster Mode (run_mode = 1)

For cluster submission, set `cluster_type` (condor, sge, slurm, lsf, pbs) and optional queue/walltime settings in `mg5_configuration.txt`.

**Key points:**
- `run_mode` and `nb_core` **cannot** be set inside a `launch` block — only before `launch` or in `mg5_configuration.txt`.
- Default is `run_mode = 2` (multicore) with auto-detected core count (`nb_core = None`).

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `ebeam1/2` | 6500 | Beam energies in GeV (half of sqrt(s)) |
| `lpp1/2` | 1 | Beam type: 0=no PDF, 1=proton, -1=antiproton |
| `nevents` | 10000 | Number of unweighted events |
| `iseed` | 0 | Random seed (0=automatic) |
| `pdlabel` / `lhaid` | nn23lo1 / 230000 | PDF label and LHAPDF set ID |
| `dynamical_scale_choice` | -1 | Scale definition (see Scales below) |
| `scalefact` | 1.0 | Multiplier on the chosen scale |
| `ickkw` / `xqcut` | 0 / 0 | Matching scheme and kt cut (GeV) |
| `use_syst` | True | Enable on-the-fly reweighting |

Generation-level cuts: `ptj`, `ptl`, `pta`, `etaj`, `etal`, `drjj`, `drll`. Per-particle cuts via `pt_min_pdg`, `mxx_min_pdg`, `eta_max_pdg` with dict syntax `{PDG: value}`.

**Pitfall:** Overly tight generation cuts can make the cross-section artificially small and break integration.

**Details ->** [Cards & Parameters](detailed/04_cards_and_parameters.md)

---

## Scripted Execution

Run scripts with: `<MG5_DIR>/bin/mg5_aMC my_script.mg5`

### Minimal Template

```
import model sm
generate p p > t t~
output my_ttbar
launch my_ttbar
  shower=PYTHIA8
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  set param_card mass 6 172.5
  done
```

### Launch Dialogue Rules

1. **Switches** come first: `shower=PYTHIA8`, `detector=Delphes`, `madspin=ON`.
2. **`set` commands** modify cards: `set <card> <block_or_param> [index] <value>`.
3. **`done`** ends the launch block. Multiple `launch` blocks create `run_01`, `run_02`, etc.
4. You can also provide a pre-edited card path instead of `set`: `/path/to/my_run_card.dat`.

**Pitfall:** A missing `done` causes the script to hang forever.

**Pitfall:** For e+e- collisions, set `lpp1 = lpp2 = 0`; forgetting this silently applies proton PDFs.

**Details ->** [Scripted Execution](detailed/05_scripted_execution.md) | [Interactive Mode](detailed/18_interactive_mode.md)

---

## PDF Selection

### Built-In vs LHAPDF

| `pdlabel` | Set | LHAPDF ID | Order |
|-----------|-----|-----------|-------|
| `nn23lo1` | NNPDF2.3 LO (default) | 247000 | LO |
| `nn23nlo` | NNPDF2.3 NLO | 244800 | NLO |
| `lhapdf` | External via `lhaid` | user-specified | varies |

Common LHAPDF IDs: `315000` (NNPDF3.1 LO), `303400` (NNPDF3.1 NLO), `11000` (CT10nlo). To use an external set: `set run_card pdlabel lhapdf` and `set run_card lhaid 303400`.

### LO vs NLO Consistency

**The PDF order must match the calculation order.** LO calculations require LO PDFs; NLO (`[QCD]`) requires NLO PDFs. Mismatching gives unreliable results because alpha_s running is extracted from the PDF fit at matching order.

**Pitfall:** For proton beams, `aS(MZ)` in param_card is overridden by the PDF's fitted alpha_s. Use the systematics module for alpha_s variations.

**Pitfall:** The flavor number scheme (4F vs 5F) in the model must match the PDF set.

**Details ->** [PDFs and LHAPDF](detailed/19_pdfs_and_lhapdf.md)

---

## Scale Choices

### Dynamical Scale Options

| `dynamical_scale_choice` | Definition | Typical use |
|--------------------------|-----------|-------------|
| **-1** (default) | CKKW back-clustering | General purpose; required for MLM matching |
| **1** | Sum of transverse energy | Multi-jet production |
| **2** | HT (sum of sqrt(m^2+pT^2)) | Heavy-particle + jets |
| **3** | HT/2 | Top-pair production (good convergence) |
| **4** | sqrt(s-hat) | Inclusive cross-sections |
| **0** | User-defined | Edit `SubProcesses/setscales.f` |

### Fixed Scales

Set `fixed_ren_scale = True` / `fixed_fac_scale = True`, then specify `scale` (ren) and `dsqrt_q2fact1/2` (fac) in GeV.

### `scalefact` Multiplier

Multiplies the dynamical scale: `mu = scalefact * (dynamical scale)`. Example: choice=2 with scalefact=0.5 gives HT/2.

### Scale Uncertainty

Standard 7-point envelope (mu_R, mu_F x 0.5 and x 2, excluding extreme anti-correlated). Enable via `use_syst = True`.

**Details ->** [Scale Choices](detailed/20_scale_choices.md)

---

## Parameter Scans

Replace any card value with `scan:` followed by a Python list expression:

```
set run_card ebeam1 scan:[6500, 7000, 7500]
set param_card mass 6 scan:[170.0, 172.5, 175.0]
```

Any valid Python list expression works: `scan:range(1000,10001,1000)`, `scan:[10**i for i in range(2,5)]`.

Multiple `scan:` entries produce the **Cartesian product**. For **correlated** (lockstep) scanning, use a shared scan ID: `scan1:[6500,7000] = ebeam1` and `scan1:[6500,7000] = ebeam2`. Results appear as `run_01`, `run_01_scan_02`, etc., with a summary cross-section table.

**Pitfall:** Run card scans and param card scans cannot be combined in the same launch.

**Details ->** [Parameter Scans](detailed/21_parameter_scans.md)

---

## Cross-References

- [Process Generation](process_generation.md) -- generate/output commands, process syntax
- [NLO & Matching](nlo_and_matching.md) -- NLO parameters, matching setup, FxFx/MLM
- [Shower, Detector & Analysis](shower_detector_analysis.md) -- Pythia8, Delphes, MadAnalysis5 cards
- [Production & Troubleshooting](production_and_troubleshooting.md) -- gridpacks, systematics, common errors
