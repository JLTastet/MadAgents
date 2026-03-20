# 07 — Matching & Merging

Matching and merging combine matrix-element calculations for processes with different numbers of extra jets with the parton shower, avoiding double-counting of jet radiation. This is essential for producing physically meaningful multi-jet predictions.

## Why Matching is Needed

Without matching, two problems arise:
1. **Double-counting**: The parton shower generates additional jets from the hard process. If you also include matrix-element jets (via `add process ... j`), the same jet configuration is counted twice — once from the matrix element and once from the shower.
2. **Inconsistent jet spectra**: Using only the shower gives inaccurate hard-jet predictions; using only matrix elements misses soft/collinear radiation.

Matching resolves this by defining a boundary (the matching scale) between the matrix-element and shower domains.

## MLM Matching (LO)

MLM matching is the standard method for LO multi-jet samples. It works by:
1. Generating matrix-element events for each jet multiplicity separately.
2. Showering all events with Pythia8.
3. Applying a veto: events where the shower generates jets above the matching scale that aren't matched to matrix-element partons are rejected.

### Setup

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

### Key Parameters

| Parameter | Location | Description |
|-----------|----------|-------------|
| `ickkw` | run_card | Matching scheme: 0=none, 1=MLM, 3=FxFx |
| `xqcut` | run_card | Minimum kt measure for matrix-element generation (GeV). **Must be nonzero.** |
| `maxjetflavor` | run_card | Maximum quark flavor counted as a jet (4 or 5) |
| `@N` tags | generate/add process | Jet multiplicity label for each subprocess |
| `JetMatching:qCut` | pythia8_card | Shower-side matching scale (GeV). Must be > xqcut. |
| `JetMatching:nJetMax` | pythia8_card | Maximum number of matched jets (= highest `@N`) |
| `JetMatching:scheme` | pythia8_card | Matching algorithm: 1 = shower-kt MLM |

### Parameter Relationships

- **xqcut**: Generation-level cut on the kt measure between partons. Regulates soft/collinear divergences in the matrix element. Typical values: 10-30 GeV for light processes, 15-25 GeV for Z/W+jets, 20-40 GeV for tt̄+jets.
- **qCut**: Shower-side matching scale. Must satisfy `qCut > xqcut`. Typical rule: `qCut ≈ 1.2-1.5 × xqcut`.
- **`@N` tags**: Must start at `@0` (inclusive process) and increment by 1 for each additional jet.

### The `@N` Tags

Each jet multiplicity must be labeled:

```
generate p p > z @0              # 0 extra jets
add process p p > z j @1         # 1 extra jet
add process p p > z j j @2       # 2 extra jets
```

The `@N` tags tell MG5 which multiplicity each subprocess belongs to. The matching algorithm uses this information to determine the maximum number of jets for each sample.

## Pre-Shower vs Post-Shower Cross-Sections

With matching enabled, two cross-sections are reported:

1. **Pre-shower**: Sum of cross-sections for each multiplicity before Pythia8. This is **not** the physical cross-section — it does not include Sudakov suppression or matching vetoes.
2. **Post-shower**: The cross-section after Pythia8 matching vetoes. **This is the physical cross-section.**

The post-shower cross-section is typically smaller than the pre-shower sum because the matching vetoes reject events where the shower generates hard jets that duplicate matrix-element jets.

## DJR Validation

Differential Jet Rate (DJR) distributions validate that matching is working correctly. The DJR distribution measures the kt scale at which an N-jet event transitions to (N-1)-jet.

### What to Check

- **Smooth transition at qCut**: The DJR distribution (log₁₀(d₀₁), log₁₀(d₁₂), etc.) should be smooth and continuous at the matching scale log₁₀(qCut).
- **No kinks or discontinuities**: A visible step or kink at log₁₀(qCut) indicates a matching problem — typically xqcut/qCut are poorly chosen.

### Producing DJR Plots

Pythia8 can output DJR distributions. Alternatively, analyze the showered events with a jet clustering algorithm and plot the kt clustering scales.

## Common Pitfalls

### 1. xqcut = 0 with ickkw = 1

This is the most common matching bug. Without a nonzero `xqcut`, there is no generation-level cut to regulate QCD divergences in multi-jet samples. Symptoms:
- Very few unweighted events generated despite requesting many.
- Poor integration convergence.
- Enormous pre-shower cross-sections.

**Fix**: Set `xqcut` to an appropriate value (e.g., 15-20 GeV for Z+jets).

### 2. Missing @N Tags

Using `ickkw = 1` without `@N` tags on the `generate`/`add process` lines:

```
# WRONG — no @N tags
generate p p > t t~
add process p p > t t~ j
```

This causes Pythia8 to report "no events passed the matching" because it cannot determine the jet multiplicity of each event.

**Fix**: Always use `@N` tags when `ickkw = 1`:
```
# CORRECT
generate p p > t t~ @0
add process p p > t t~ j @1
```

### 3. ickkw = 1 without Multiple Multiplicities

Setting `ickkw = 1` (MLM matching) but only generating a single multiplicity (no `add process ... j`). The matching veto rejects events whose shower produces jets that should have come from a higher-multiplicity matrix element, but that multiplicity doesn't exist.

**Fix**: Either disable matching (`ickkw = 0`) for single-multiplicity generation, or add the additional multiplicities.

### 4. Conflicting Matching Settings

Do not combine conflicting matching settings. For MLM: set `ickkw = 1` with a nonzero `xqcut` and appropriate Pythia8 `JetMatching` parameters. For FxFx (NLO merging): set `ickkw = 3`. Setting `ickkw = 1` while also using NLO-specific or CKKW-L-style shower settings causes divergent or nonsensical results. Only one matching scheme should be active at a time.

### 5. Non-QCD Processes in Matched Samples

MLM and FxFx matching handle the overlap between matrix-element **QCD radiation** (additional jets) and parton-shower QCD radiation. All subprocesses included in a matched sample must represent different QCD jet multiplicities of the **same underlying physics process**. The `@N` tags label these jet multiplicities for the matching algorithm.

Mixing fundamentally different physics processes — e.g., dark matter production with additional jets (`X + j`, `X + jj`) alongside associated electroweak production (`X + W`, `X + Z`) — in a single matched sample is incorrect. The associated electroweak processes are not "jet multiplicities" that the matching algorithm can handle. They must be generated in separate, unmatched runs and combined with the matched jet sample at the analysis level.

### 6. Divergent Cross-Sections

If the effective luminosity goes to 0 or 10^-100 pb^-1 regardless of xqcut variations:
- Check the UFO model for bugs (model errors — particularly in form factors or custom vertices — can masquerade as matching problems and produce spurious divergences).
- Verify 4-flavor vs 5-flavor scheme consistency.
- Ensure only one matching scheme is active.

### 7. Flavor Scheme Consistency: Explicit Heavy Quarks (e.g., tt̄bb̄)

> **Critical rule**: The flavor scheme must be consistent across **all three** components: (1) the proton/jet definition in the process card, (2) the `maxjetflavor` parameter in the run_card, and (3) the PDF set. Mixing a 5-flavor PDF with `maxjetflavor = 4` (or vice versa) is **inconsistent and produces wrong results**.

Processes with explicit b quarks in the final state — such as `p p > t t~ b b~` — require particular care because the b quark can appear both as a resolved final-state particle and (in the 5-flavor scheme) as an initial-state parton from the proton PDF.

#### The Double-Counting Problem

In the 5-flavor scheme, the b-quark PDF already resums collinear `g → bb̄` splittings via DGLAP evolution. If you then also generate matrix-element diagrams with explicit `g → bb̄` splittings (as part of `p p > t t~ b b~`), **the same physical configuration is counted twice** — once through the b-PDF and once through the explicit ME diagram. This diagram-level double-counting inflates the cross-section independently of any matching issues.

Additionally, when `maxjetflavor = 5`, the matching algorithm treats b quarks as matchable jets. But the b quarks in `t t~ b b~` are meant to be resolved hard final-state particles, not shower-generated jets to be matched. The matching algorithm cannot distinguish between "signal" b quarks and "extra jet" b quarks, breaking the matching procedure.

#### Recommended Approach: 4-Flavor Scheme

For processes with explicit b quarks in the final state (tt̄bb̄, Hbb̄, single-top + b, etc.), use the **4-flavor scheme**. This avoids both double-counting and matching ambiguities by construction:

- b quarks are **massive** (physical mass ~4.7 GeV)
- b quarks are **not** in the proton PDF
- b quarks are **not** part of the jet definition for matching
- There is a clean separation between hard b quarks and matched light jets

```
import model sm
# 4FS: b is NOT in the proton or jet definitions (MG5 default for massive b)
define j = g u c d s u~ c~ d~ s~
define p = j
generate p p > t t~ b b~ @0
add process p p > t t~ b b~ j @1
output pp_ttbb_4FS
launch pp_ttbb_4FS
  shower=PYTHIA8
  set run_card ickkw 1
  set run_card maxjetflavor 4
  set run_card xqcut 20
  set run_card lhaid 320500   # NNPDF31_nlo_as_0118_nf_4 (4-flavor PDF)
  set run_card asrwgtflavor 4
  set pythia8_card JetMatching:qCut 30
  set pythia8_card JetMatching:nJetMax 1
  done
```

**Key points:**
- Use the default `sm` model (b quark is massive).
- Explicitly define `j` and `p` without b quarks, or rely on MG5's default definitions for massive quarks.
- Use a **4-flavor PDF set** (e.g., NNPDF31_nlo_as_0118_nf_4, LHAID 320500). Using a 5-flavor PDF with `maxjetflavor = 4` is inconsistent.
- Set `asrwgtflavor = 4` to match the PDF flavor number (controls the number of active flavors in α_s reweighting for matching).
- The `@N` tags and matching parameters apply only to the light jets (`j`), not to the b quarks.

| Parameter | Description | 4FS value |
|-----------|-------------|-----------|
| `maxjetflavor` | Highest quark flavor treated as a jet for matching | `4` |
| `asrwgtflavor` | Highest quark flavor for α_s reweighting in matching | `4` |
| `lhaid` | LHAPDF ID — must use an nf=4 PDF set | e.g., `320500` |

#### Why NOT to Use 5FS with Explicit b Quarks

Do **not** generate `p p > t t~ b b~` in the 5-flavor scheme (with b in the proton). This creates two independent problems:

| Problem | Mechanism | Consequence |
|---------|-----------|-------------|
| Diagram-level double-counting | b-PDF resums `g → bb̄`; ME also contains explicit `g → bb̄` | Inflated cross-section |
| Matching breakdown | `maxjetflavor = 5` makes b quarks matchable, but they are signal particles | Matching vetoes reject valid events or fail to converge |

The "hybrid" approach — using a 5-flavor PDF with `maxjetflavor = 4` — is also wrong. The MadGraph documentation explicitly warns: *using a 5F PDF with maxjetflavor = 4 is inconsistent*. The PDF contains b-quark contributions that the matching ignores, leading to unphysical results.

#### If You Need the 5-Flavor Scheme

If your analysis specifically requires the 5FS (e.g., for consistency with other samples), do **not** put explicit b quarks in the matrix-element final state. Instead, generate the inclusive process and let b quarks arise from the shower or PDF-initiated subprocesses:

```
import model sm-no_b_mass
define p = g u c d s b u~ c~ d~ s~ b~
define j = p
generate p p > t t~ @0
add process p p > t t~ j @1
add process p p > t t~ j j @2
output pp_tt_5FS
launch pp_tt_5FS
  shower=PYTHIA8
  set run_card ickkw 1
  set run_card maxjetflavor 5
  set run_card xqcut 20
  set run_card asrwgtflavor 5
  set pythia8_card JetMatching:qCut 30
  set pythia8_card JetMatching:nJetMax 2
  done
```

In this case, bb̄ pairs come from gluon splitting in the parton shower or from b-quark-initiated subprocesses included automatically via the `j` definition. The trade-off is that the bb̄ kinematics are less accurately described (shower approximation vs. full matrix element).

#### Summary Table: Flavor Scheme Choice for Processes with b Quarks

| Feature | 4-Flavor Scheme (recommended) | 5-Flavor Scheme |
|---------|-------------------------------|------------------|
| b quark mass | Physical (~4.7 GeV) | Zero |
| b in proton PDF | No | Yes |
| b in jet definition | No | Yes |
| `maxjetflavor` | 4 | 5 |
| PDF set | 4-flavor (nf=4) | 5-flavor (nf=5) |
| Explicit b in ME final state | Yes (e.g., `t t~ b b~`) | **No** — use inclusive jets |
| Double-counting risk | None | High if b in final state |
| bb̄ kinematics | Full ME accuracy | Shower approximation |

## FxFx Merging (NLO)

## CKKW-L Merging (LO, Pythia8-native)

CKKW-L (CKKW with Lonnblad improvements) is an alternative LO merging scheme where the merging logic is handled entirely by Pythia8, not by MadGraph's built-in matching infrastructure. Unlike MLM (which uses `ickkw = 1` and MadGraph's `JetMatching` settings), CKKW-L uses Pythia8's native `Merging:` namespace parameters.

### When to Use CKKW-L vs MLM

| Feature | MLM | CKKW-L |
|---------|-----|--------|
| Accuracy | LO | LO |
| Merging logic | MadGraph + Pythia8 `JetMatching` | Pythia8 `Merging:` namespace |
| `ickkw` setting | 1 | 0 |
| Generation-level cut | `xqcut` (kt measure) | `ktdurham` (kt separation) |
| Pythia8 parameter namespace | `JetMatching:*` | `Merging:*` |
| Shower veto mechanism | Pythia8 rejects events via JetMatching veto | Pythia8 reweights events via Sudakov/αs history |
| Cross-section estimation run | Not required | Not required |

Both are valid LO merging approaches. MLM is more commonly used in MadGraph workflows and is better supported by the MadGraph–Pythia8 interface. CKKW-L may be preferred when the user wants finer control over the merging procedure or when following analysis prescriptions that specifically require CKKW-L.

### MadGraph-Side Setup (run_card)

For CKKW-L, MadGraph generates multi-jet LHE files **without** applying its own matching logic. The critical run_card settings are:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `ickkw` | `0` | Disables MadGraph-side matching (MLM/FxFx) |
| `xqcut` | `0` | No MadGraph-side kt cut (CKKW-L uses `ktdurham` instead) |
| `ktdurham` | e.g. `50` | kt separation cut for CKKW-L merging (GeV). Regulates soft/collinear divergences at generation level. |
| `ptj` | e.g. `20` | Minimum jet pT cut. Should be consistent with or below `ktdurham`. |
| `drjj` | e.g. `0.4` | Minimum ΔR between jets at generation level |
| `maxjetflavor` | e.g. `5` | Number of light quark flavors in jets. MadGraph automatically passes this to Pythia8 as `Merging:nQuarksMerge`. |

The `ktdurham` parameter in the run_card serves the same role for CKKW-L that `xqcut` serves for MLM — it provides the generation-level phase-space cut that regulates QCD divergences. The `@N` tags on `generate`/`add process` lines are still required.

### Pythia8-Side Setup (pythia8_card)

CKKW-L merging is controlled by Pythia8's `Merging:` namespace. The `JetMatching` namespace must be disabled.

**Parameters the user must set:**

| Parameter | Value | Description |
|-----------|-------|-------------|
| `JetMatching:merge` | `off` | **Must disable** MLM matching |
| `Merging:doKTMerging` | `on` | Enables CKKW-L merging with kt-based merging scale |
| `Merging:TMS` | e.g. `50` | Merging scale in GeV. Should match `ktdurham` from run_card. |
| `Merging:nJetMax` | e.g. `2` | Maximum number of additional jets in the matrix element (= highest `@N` minus the base process jets) |
| `Merging:Process` | `guess` | Hard process specification. Use `guess` to let Pythia8 infer the process from the LHE file. See note below. |
| `Merging:Dparameter` | `0.4` (default `1.0`) | D parameter in the longitudinally invariant kt definition. Set to match analysis jet radius. |

**Parameters auto-managed by MadGraph (do NOT set manually):**

When `ktdurham > 0`, MadGraph automatically configures these Pythia8 parameters. Setting them manually in the pythia8_card causes a fatal error ("The parameter is already set").

| Parameter | Auto-set value | Source |
|-----------|---------------|--------|
| `SpaceShower:pTmaxMatch` | `1` | Set by MG5 when `ktdurham > 0` |
| `TimeShower:pTmaxMatch` | `1` | Set by MG5 when `ktdurham > 0` |
| `Merging:nQuarksMerge` | from `maxjetflavor` | Set by MG5 from run_card `maxjetflavor` |

**Note on `Merging:Process`:** Pythia8 supports explicit process strings (e.g., `pp>tt~`), but in practice these can cause parsing crashes in some Pythia8 versions (e.g., 8.316). The `guess` option (available since Pythia8 8.223) reliably infers the hard process from the LHE file headers. Always prefer `Merging:Process = guess`.

### Complete Example: tt̄ + jets with CKKW-L

```
import model sm
generate p p > t t~ @0
add process p p > t t~ j @1
add process p p > t t~ j j @2
output ttbar_ckkwl
launch ttbar_ckkwl
  shower=PYTHIA8
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 50000
  set run_card ickkw 0
  set run_card xqcut 0
  set run_card ktdurham 50
  set run_card ptj 20
  set run_card drjj 0.4
  set run_card maxjetflavor 5
  set pythia8_card JetMatching:merge = off
  set pythia8_card Merging:doKTMerging = on
  set pythia8_card Merging:TMS = 50
  set pythia8_card Merging:nJetMax = 2
  set pythia8_card Merging:Process = guess
  set pythia8_card Merging:Dparameter = 0.4
  done
```

**Key points:**
- Do **not** set `SpaceShower:pTmaxMatch`, `TimeShower:pTmaxMatch`, or `Merging:nQuarksMerge` manually — MadGraph handles these automatically.
- Use `Merging:Process = guess` instead of an explicit process string to avoid Pythia8 parsing issues.
- Set `maxjetflavor` in the run_card to control which quark flavors are treated as mergeable partons.

### Alternative: Automated MadGraph File Handling

Pythia8 provides a convenience mode that reads merging parameters directly from the LHE file headers:

| Parameter | Value | Description |
|-----------|-------|-------------|
| `Merging:doMGMerging` | `on` | Reads `ktdurham` from LHE file, infers hard process from `@1` tag |
| `Merging:nJetMax` | e.g. `2` | Still must be set manually |

When `Merging:doMGMerging = on`, the merging scale is extracted from the `ktdurham` value in the LHE file header, and the hard process is read from the `@1`-tagged subprocess. This avoids manually specifying `Merging:TMS` and `Merging:Process`, but `Merging:nJetMax` must still be set. This mode is less explicit and may fail for complex multi-jet processes — prefer manual specification for reliability.

### CKKW-L Cross-Sections and Event Weights

Unlike MLM matching (which applies accept/reject vetoes), CKKW-L applies event-by-event reweighting via Sudakov form factors and αs ratios reconstructed from the parton shower history. The physical cross-section is obtained from the weighted events. Use `Info::mergingWeight()` in Pythia8 to access the CKKW-L weight for each event (this does not include the phase-space weight from the LHE file).

**Note:** CKKW-L runs with MadGraph may produce non-fatal warnings such as "Failed to produce Pythia8 merging plots" and "Cross-sections could not be read from XML node". These are expected — the automatic merging validation plots that MadGraph produces for MLM matching are not available for CKKW-L. The merging is still applied correctly; validate the merging quality by examining differential jet distributions (e.g., jet pT spectra, jet multiplicity) in the output events.

### Common CKKW-L Pitfalls

1. **Leaving `JetMatching:merge` on**: If MLM matching is not explicitly disabled, it conflicts with the `Merging:` settings. Always set `JetMatching:merge = off` when using CKKW-L.

2. **Mismatched `ktdurham` and `Merging:TMS`**: The Pythia8-side merging scale (`Merging:TMS`) must match the generation-level cut (`ktdurham` in the run_card). A mismatch causes double-counting or gaps in the jet spectrum.

3. **Manually setting auto-managed parameters**: Do not set `SpaceShower:pTmaxMatch`, `TimeShower:pTmaxMatch`, or `Merging:nQuarksMerge` in the pythia8_card. MadGraph sets these automatically when `ktdurham > 0` (from `madevent_interface.py`). Manually setting them causes a fatal error: "The parameter X is already set. You can not change it."

4. **Using explicit `Merging:Process` strings**: While Pythia8 documents explicit process notation (e.g., `pp>tt~`), this can cause `std::out_of_range` crashes in some Pythia8 versions. Use `Merging:Process = guess` instead.

5. **`Merging:applyVeto` behavior**: The Pythia8 native default for `Merging:applyVeto` is `on`. When using the MG5aMC–Pythia8 interface with systematics enabled, MadGraph overrides this to `off` (handling the veto externally). Do not change this parameter unless you understand the veto handling in your specific workflow.

FxFx is the NLO extension of MLM. It merges NLO-accurate samples of different jet multiplicities:

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
  set pythia8_card JetMatching:doFxFx = on
  set pythia8_card JetMatching:qCutME = 10
  set pythia8_card JetMatching:nJetMax = 1
  set pythia8_card TimeShower:pTmaxMatch = 1
  set pythia8_card SpaceShower:pTmaxMatch = 1
  done
```

Key differences from MLM:
- Uses `ickkw = 3` (not 1).
- Pythia8 requires FxFx-specific settings: `JetMatching:doFxFx = on`, `JetMatching:qCutME` (merging scale), and `pTmaxMatch = 1` for both space and time showers.
- Each multiplicity is computed at NLO accuracy.
- More theoretically consistent but computationally expensive.

### FxFx Applicability

FxFx merging is designed for processes where the Born process has a non-QCD hard scale — typically the production of an electroweak or heavy particle (W, Z, H, tt̄) — and additional QCD jets are merged on top. The merging scale separates the matrix-element and parton-shower domains, and this separation relies on a clear distinction between the hard process and QCD radiation.

For **pure QCD multijet production** (inclusive dijets, trijets, etc.), where QCD jets define the Born process itself, this distinction breaks down: there is no non-QCD hard scale to anchor the merging. FxFx at the lowest jet multiplicity is not applicable for such processes. Use LO MLM matching instead, generating multiple jet multiplicities:

```
import model sm
generate p p > j j @0
add process p p > j j j @1
add process p p > j j j j @2
output dijets_matched
launch dijets_matched
  shower=PYTHIA8
  set run_card ickkw 1
  set run_card xqcut 20
  set pythia8_card JetMatching:qCut 30
  set pythia8_card JetMatching:nJetMax 2
```

For these processes, the matching/merging scale should be guided by the hard scale of the process (e.g., the minimum jet pT threshold), not derived from an electroweak scale. Ensure that the generation-level pT cut (`ptj`) is consistent with `xqcut`.

## Matching Uncertainties

To assess matching uncertainties:
- Vary `xqcut` by factors of 0.5 and 2 around the central value.
- Vary `qCut` consistently.
- Compare the resulting post-shower cross-sections and distributions.
- The variation should be small (< 10%) for well-chosen parameters.

Large sensitivity to xqcut/qCut indicates the parameters are too far from optimal or the process has intrinsic sensitivity to the matching scale.

## Cross-References

- **[← Reference: NLO & Matching](nlo_and_matching.md)**
- [Process Syntax](02_process_syntax.md) — `@N` tags, `add process`
- [Cards & Parameters](04_cards_and_parameters.md) — ickkw, xqcut, maxjetflavor
- [Scripted Execution](05_scripted_execution.md) — matched sample scripts
- [NLO Computations](06_nlo_computations.md) — FxFx at NLO
- [Parton Shower — Pythia8](09_parton_shower_pythia8.md) — pythia8_card matching parameters
- [Troubleshooting](16_troubleshooting.md) — matching diagnostics
