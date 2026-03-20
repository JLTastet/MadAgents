# Process Generation

Quick reference for defining processes, choosing models, controlling coupling orders, filtering diagrams, and selecting flavor schemes in MadGraph5.

## Models

| Model | Description | When to use |
|-------|-------------|-------------|
| `sm` | Standard Model, massive b (4-flavor) | Default LO computations |
| `sm-no_b_mass` | SM, massless b (5-flavor) | b in initial state / jets |
| `loop_sm` | SM with loop amplitudes | Required for NLO (`[QCD]`) |
| `heft` | SM + effective ggH vertex | Fast gg->H (valid mH << 2mt) |

Load a model (resets session):
```
import model sm
import model sm-no_b_mass          # restriction file sets mb=0
```

Key points:
- `heft` provides only the ggH vertex -- do NOT use for VBF (`p p > h j j`).
- `loop_sm` is mandatory for `[QCD]` bracket syntax; plain `sm` will fail.
- BSM UFO models: place directory in `<MG5_DIR>/models/`, then `import model <name>`.
- Always create a restriction file setting light quark masses to zero for BSM models to enable subprocess grouping.

**Details ->** [Models](detailed/03_models.md)

## Generate / Add Process

```
generate p p > t t~                 # define the hard process
add process p p > t t~ j            # add subprocess (summed incoherently)
output my_process                   # create process directory
launch my_process                   # start event generation
```

- Within one `generate` command, amplitudes interfere coherently.
- Separate `generate` / `add process` lines sum cross-sections incoherently (no interference).
- Antiparticles: `t~`, `b~`. Charges: `e+`, `e-`, `w+`, `w-`.
- `@N` tags label jet multiplicities for MLM matching: `generate p p > t t~ @0`.

**Details ->** [Process Syntax](detailed/02_process_syntax.md)

## Multiparticle Labels

| Label | Default content (SM) | Notes |
|-------|---------------------|-------|
| `p` / `j` | `g u c d s u~ c~ d~ s~` | Excludes b in 4-flavor `sm` |
| `l+` / `l-` | `e+ mu+` / `e- mu-` | Charged leptons |
| `vl` / `vl~` | `ve vm vt` / `ve~ vm~ vt~` | Neutrinos |

Define custom labels:
```
define ll = e+ e- mu+ mu-
generate p p > ll ll
```
With `sm-no_b_mass`, b quarks are automatically added to `p` and `j`.

**Details ->** [Process Syntax](detailed/02_process_syntax.md)

## Coupling Orders

```
generate p p > e+ e- j QED=2 QCD<=1   # constrain both orders
generate p p > h j j QCD=0             # pure EW (VBF isolation)
generate p p > h j j QCD=0 QED=4       # explicit both
generate p p > j j QED^2==2 QCD^2==2   # squared-amplitude level (interference terms)
```

| Syntax | Meaning |
|--------|---------|
| `QCD=N` | Amplitude-level: QCD order <= N |
| `QED==N` | Amplitude-level: QED order exactly N |
| `QCD^2==N` | Squared-amplitude level: total number of $g_s$ powers in \|M\|^2 equals N (note: N powers of $g_s$ = N/2 powers of $\alpha_s$) |

Automatic ordering (no explicit orders) minimizes QED (weight 2) over QCD (weight 1). This works for simple processes but can suppress signal diagrams in mixed QCD/EW processes -- always specify orders explicitly for mixed processes.

**Details ->** [Advanced Syntax](detailed/17_advanced_syntax.md)

**Details ->** [EFT / SMEFTsim](detailed/26_eft_smeftsim.md)

## Diagram Filtering

| Operator | Effect |
|----------|--------|
| `/ X` | Remove X from ALL propagators (s-channel + t-channel) |
| `$$ X` | Remove all diagrams with X in s-channel (on-shell + off-shell) |
| `$ X` | Forbid X on-shell in s-channel only (off-shell kept) |

```
generate p p > e+ e- / h       # no Higgs anywhere
generate p p > e+ e- $$ z      # no s-channel Z (any virtuality)
generate p p > e+ e- $ z       # no on-shell Z; off-shell tail kept
```

VBF isolation example:
```
generate p p > h j j $$ w+ w- z / a QCD=0    # pure VBF (excludes VH)
```

Verify gauge invariance after filtering: `check gauge <process>`.

**Details ->** [Advanced Syntax](detailed/17_advanced_syntax.md)

## Polarized Bosons

```
generate e+ e- > w+{0} w-{T}       # longitudinal W+, transverse W-
generate p p > t{L} t~{R}          # left-handed top, right-handed antitop
```

| Label | Meaning | Applies to |
|-------|---------|------------|
| `{0}` | Longitudinal | W, Z |
| `{T}` | Transverse (sum +/- helicities) | W, Z |
| `{L}` / `{R}` | Left / right-handed | Fermions |

Reference frame controlled by `me_frame` in the run_card (default: partonic CM frame).

**Note:** Polarization syntax applies to **external** (initial-state or final-state) particles only. Intermediate resonances in decay chains (e.g., the W+ in `p p > w+ w-, w+ > l+ vl`) include contributions from all polarization states — the polarization cannot be restricted at the decay-chain level. To study polarization fractions of unstable particles, generate them as polarized final-state particles and analyze angular distributions of their decay products.

**Details ->** [Advanced Syntax](detailed/17_advanced_syntax.md)

## Flavor Schemes

| | 4-Flavor | 5-Flavor |
|-|----------|----------|
| Model | `sm` (massive b) | `sm-no_b_mass` |
| `p` / `j` content | Excludes b | Includes b |
| `maxjetflavor` | 4 | 5 |
| PDF set | 4F (e.g. NNPDF31_lo_as_0118_nf4) | 5F (default) |
| Use when | mb effects matter, bbH, low-pT b | Most high-Q^2 processes |

4-flavor consistency checklist: (1) `import model sm`, (2) `define p = g u c d s u~ c~ d~ s~`, (3) `set run_card maxjetflavor 4`, (4) use a 4F PDF.

**Details ->** [Advanced Syntax](detailed/17_advanced_syntax.md)

## Common Pitfalls

- **Lost interference**: Splitting `p p > e+ e-` into separate Z-only and gamma-only `generate` lines loses the Z/gamma interference term -- always keep interfering topologies in a single `generate`.
- **Unconstrained coupling**: Specifying only `QED=6` leaves QCD unconstrained (defaults to model max); constrain both orders for mixed processes.
- **heft for VBF**: `heft` has no VBF vertex; using it for `p p > h j j` gives wrong results.
- **Gauge violation from filtering**: `$` / `$$` / `/` can produce gauge-dependent results; always run `check gauge` after filtering.
- **Slow BSM models**: FeynRules models with massive light quarks prevent subprocess grouping; create a restriction file setting mu, md, ms, mc to zero.
- **4F/5F mismatch**: Using a 5F PDF with `maxjetflavor 4` (or vice versa) gives inconsistent results.
- **EFT restriction file values**: In EFT models, setting active Wilson coefficients to the same value (e.g., all `1.0`) in the restriction file can cause MG5 to merge couplings and silently produce incorrect results. Set active parameters to random, distinct, non-zero values different from 1.

**Details ->** [Maddm Dark Matter](detailed/27_maddm_dark_matter.md)
## Cross-References

- [Configuration](configuration.md)
- [NLO & Matching](nlo_and_matching.md)
- [Decays & Widths](decays_and_widths.md)

**Details ->** [Standalone Matrix Elements](detailed/28_standalone_matrix_elements.md)
