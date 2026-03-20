# 17 — Advanced Syntax

This document covers subtleties in MadGraph5 process syntax that can significantly affect results: diagram filtering operators, automatic coupling-order determination, polarized boson generation, flavor schemes, and gauge invariance considerations.

## Diagram Filtering: `/`, `$`, `$$`

Three operators control which intermediate particles appear in Feynman diagrams:

### `/` — Remove from All Propagators

```
generate p p > e+ e- / h
```

Removes **all** diagrams containing the Higgs as an internal line, in both s-channel and t-channel. This is the most aggressive exclusion.

### `$$` — Remove from S-Channel Only

```
generate p p > e+ e- $$ z
```

Removes **all** diagrams with Z in the **s-channel**, regardless of whether the propagator is on-shell or off-shell. T-channel Z propagators (if any) are kept. Useful for separating production topologies.

### `$` — Forbid On-Shell S-Channel

```
generate p p > e+ e- $ z
```

Keeps all diagrams but **forbids the Z from going on-shell** in the s-channel — i.e., the Z invariant mass must be outside the Breit-Wigner window (M ± bwcutoff × Γ). Off-shell s-channel contributions are retained. Useful for studying off-shell tails.

Note: `$` is less aggressive than `$$`. With `$$`, the diagrams are removed entirely. With `$`, the diagrams remain but only their off-shell contributions survive.

### Summary Table

| Operator | S-channel diagrams | T-channel diagrams | Off-shell s-channel | On-shell s-channel |
|----------|-------------------|-------------------|--------------------|--------------------|
| `/ X` | Removed | Removed | Removed | Removed |
| `$$ X` | Removed | Kept | Removed | Removed |
| `$ X` | Kept | Kept | Kept | Forbidden |

### Example: Z/γ Separation

```
generate p p > e+ e-             # full process (Z + γ + interference)
generate p p > e+ e- $$ a        # Z-only diagrams (no s-channel photon)
generate p p > e+ e- $$ z        # γ-only diagrams (no s-channel Z)
```

**Warning**: The Z-only and γ-only cross-sections do **not** sum to the full cross-section. The missing piece is the Z/γ **interference term**, which is constructive below the Z pole and destructive above it. This separation is not physically meaningful — see Gauge Invariance below.

## Gauge Invariance and Diagram Filtering

When using `/`, `$`, or `$$` to select diagram subsets, two critical dangers arise:

### 1. Breaking Gauge Invariance

Each diagram subset must be independently gauge invariant. If not, the matrix element calculation gives gauge-dependent (unphysical) results. For example, separating Z and γ diagrams individually is gauge invariant (each is a complete gauge-invariant subset). But more complex filterings may break gauge invariance.

**Always verify** with the `check` command:

```
generate p p > e+ e- $$ a
check gauge p p > e+ e- $$ a
```

If the check fails, the diagram subset is not gauge invariant and the results are unreliable.

### 2. Missing Interference

Even when each subset is gauge invariant, splitting a process into subsets loses the interference between subsets. The interference contribution can increase or decrease the cross-section — it is not always positive.

**Bottom line**: Diagram filtering is a useful tool for understanding topologies, but the filtered cross-sections are not directly interpretable as physical contributions. Use the full (unfiltered) process for physics predictions.

### Gauge Invariance of Diagram Filtering: Scalars vs Gauge Bosons

The gauge-invariance risk of diagram filtering depends critically on **what particle is being excluded**:

| Particle type | Example | Gauge invariant to exclude? | Reason |
|---|---|---|---|
| **Gauge bosons** (W, Z, γ, g) | `$$ z`, `/ a` | **Depends on process** | Gauge boson propagators can participate in gauge cancellations between diagrams. Excluding them is safe when the subsets are separately gauge invariant (e.g., Z and γ in Drell-Yan are separate gauge-invariant subsets), but unsafe when diagrams with different gauge bosons cancel against each other (e.g., W/Z in some multi-boson processes). See the existing "Gauge Invariance and Diagram Filtering" section above for specific safe/unsafe cases. |
| **Scalar singlets** (Higgs) | `$$ h`, `/ h` | **Yes** | The Higgs boson is a physical scalar and a gauge singlet. Its propagator is independent of the gauge-fixing parameter (ξ) in R_ξ gauges. Diagrams with and without a Higgs propagator form separately gauge-invariant subsets. |

**Key point:** Using `/ h` or `$$ h` to exclude Higgs-mediated diagrams does **not** break gauge invariance. This is a fundamental difference from excluding gauge bosons whose propagators depend on the gauge parameter.

However, diagram exclusion still has a physical limitation: the **interference term** between Higgs-mediated and non-Higgs diagrams is lost. For processes where signal–background interference is large (e.g., gg → ZZ near and above the Higgs mass), this missing interference can shift the cross section by O(10%) or more in the high-mass tail. The issue is not gauge dependence but an incomplete physics description.

### Signal/Background/Interference Separation via Squared Coupling Orders

For processes like gg → ZZ or gg → WW, the cleanest way to isolate signal, background, and interference is through **squared coupling-order constraints** in a modified model. The official MadGraph wiki provides `loop_sm_modif`, a modified version of `loop_sm` where the Higgs–gauge-boson couplings (HWW, HZZ) are assigned a custom coupling order `NP` instead of the default `QED`.

**What NP tags:** In `loop_sm_modif`, the `NP` coupling order tags the **Higgs–gauge-boson vertices** (HWW and HZZ couplings, i.e., GC_31 and GC_32 in the UFO). Yukawa couplings (yb, yt, etc.) remain tagged with `QED`, unchanged from the standard `loop_sm`. The `NP` order therefore counts the number of HVV vertices in the amplitude.

**Setup:** Download `loop_sm_modif.tar.gz` from the [MadGraph Offshell_interference_effects wiki page](https://cp3.irmp.ucl.ac.be/projects/madgraph/wiki/Offshell_interference_effects) and extract it into your models directory.

#### Commands from the Official Wiki

The MadGraph wiki shows the following syntax for gg → ZZ (4-lepton final state):

```
import model loop_sm_modif

# Signal only (Higgs-mediated squared, triangle²):
generate g g > e+ e- mu+ mu- / e+ e- mu+ mu- [QCD] NP^2==2

# Interference only (triangle × box):
generate g g > e+ e- mu+ mu- / e+ e- mu+ mu- [QCD] NP^2==1

# Background only (box², no Higgs):
generate g g > e+ e- mu+ mu- / e+ e- mu+ mu- [QCD] NP=0

# Total (signal + background + interference):
generate g g > e+ e- mu+ mu- / e+ e- mu+ mu- [QCD] NP=1
```

**Important version caveat:** The `==` squared-order constraint (e.g., `NP^2==2`) may fail in some MadGraph versions with the error *"The squared-order constraints passed are not <=. Other kind of squared-order constraints are not supported at NLO"*. This is because loop-induced processes with `[QCD]` use the NLO framework internally. If `==` fails, use `<=` constraints with subtraction:

```
import model loop_sm_modif

# Background only (no Higgs vertices):
generate g g > e+ e- mu+ mu- / e+ e- mu+ mu- [QCD] NP=0
# → σ_bkg

# Background + interference (up to 1 HVV vertex in |M|²):
generate g g > e+ e- mu+ mu- / e+ e- mu+ mu- [QCD] NP^2<=1
# → σ_bkg + σ_int

# Full (all contributions):
generate g g > e+ e- mu+ mu- / e+ e- mu+ mu- [QCD] NP^2<=2
# → σ_bkg + σ_int + σ_sig
```

Then extract each piece by subtraction: σ_int = σ(NP^2<=1) − σ(NP=0), and σ_sig = σ(NP^2<=2) − σ(NP^2<=1).

**Important:** The standard `loop_sm` model does **not** define the `NP` coupling order — it only has `QCD` and `QED`. You must use `loop_sm_modif` (or create your own modification). Using an undefined coupling order with `loop_sm` will produce an error.

The `/ e+ e- mu+ mu-` in the commands above excludes diagrams with these leptons as internal lines, which is standard for this process to avoid double-counting.

#### Alternative: Diagram Exclusion with `/h`

```
import model loop_sm
# Background only (box diagrams) — gauge invariant:
generate g g > z z / h [noborn=QCD]

# Full process (signal + background + interference):
generate g g > z z [noborn=QCD]
```

The background-only result is gauge invariant (Higgs is a scalar singlet). Interference is obtained by subtraction: σ_int = σ_full − σ_signal − σ_bkg, requiring three separate runs.

#### Summary: Signal/Background Separation Methods

| Method | Gauge invariant? | Captures interference? | Complexity |
|---|---|---|---|
| `/ h` or `$$ h` (exclude Higgs) | Yes (Higgs is scalar singlet) | No — must subtract to get interference | 3 runs needed |
| Squared coupling orders (`NP` in `loop_sm_modif`) | Yes | Yes — each piece isolated | 1 run per piece |
| Full process (no filtering) | Yes | Yes — all included automatically | 1 run, no separation |

## The `bwcutoff` Parameter and On-Shell/Off-Shell Boundaries

The `bwcutoff` parameter in the run_card defines the boundary between "on-shell" and "off-shell" for s-channel resonances. It is central to how decay chains and the `$` operator behave.

### Definition and Default

| Property | Value |
|----------|-------|
| Location | `run_card.dat` |
| Default | `15` |
| Meaning | A resonance is on-shell if its invariant mass satisfies |m − M| < bwcutoff × Γ |

The on-shell window is **M ± bwcutoff × Γ**, where M is the pole mass and Γ is the total width of the particle.

### When `bwcutoff` Affects the Cross Section

`bwcutoff` does **not** affect the cross section of full (non-decay-chain) processes. For full processes like `p p > w+ w- b b~`, MadGraph integrates over all phase space — the `bwcutoff` value only controls which internal propagators are written with status code 2 (intermediate resonance) in the LHE event file.

`bwcutoff` **does** affect the cross section in exactly two cases:

| Syntax | How bwcutoff affects it |
|--------|------------------------|
| Decay chains: `p p > t t~, t > w+ b, t~ > w- b~` | Intermediate particles are **required** to be on-shell (within M ± bwcutoff × Γ). Smaller bwcutoff → narrower integration window → smaller cross section. |
| `$` operator: `p p > w+ w- b b~ $ t t~` | Intermediate particles are **forbidden** from being on-shell (within M ± bwcutoff × Γ). Smaller bwcutoff → narrower exclusion window → larger cross section. |

These two cases are **complementary**: decay chains integrate only inside the on-shell window, while `$` integrates only outside it.

### How `bwcutoff` Interacts with Each Operator

The `$`, `$$`, and `/` operators differ fundamentally in whether they use `bwcutoff` (see the **Summary Table** above for the full operator comparison):

- **`$` (forbid on-shell)**: Uses `bwcutoff`. Keeps all diagrams but applies a phase-space cut — events where the s-channel invariant mass falls inside M ± bwcutoff × Γ are rejected.
- **`$$` (remove s-channel diagrams)**: Does **not** use `bwcutoff`. Removes all diagrams containing the specified s-channel particle entirely.
- **`/` (remove particle everywhere)**: Does **not** use `bwcutoff`. Removes all diagrams containing the specified particle in any role.

### Practical Guidance

- For most analyses, the default `bwcutoff = 15` is appropriate. At 15 widths from the pole, the Breit-Wigner propagator suppression is approximately 1/900 relative to the peak, making the excluded tails negligible.
- Increasing `bwcutoff` in decay chains captures more off-shell tails but moves further from the narrow-width approximation where decay chains are valid.
- The `$` operator with `bwcutoff` provides an approximate separation of resonant vs non-resonant contributions, but this separation is gauge-dependent (see below).

**Details →** [Cards & Parameters](04_cards_and_parameters.md) for other run_card settings.

## Resonant vs Non-Resonant Separation Strategies

A common task is separating resonant contributions (e.g., on-shell top pair production) from non-resonant contributions (e.g., single-top or continuum W⁺W⁻bb̄). MadGraph offers several approaches, each with trade-offs.

### Approach 1: Decay Chain (Narrow-Width Approximation)

```
generate p p > t t~, t > w+ b, t~ > w- b~
```

- Includes **only** doubly-resonant diagrams (both t and t̄ on-shell).
- Valid in the narrow-width limit (Γ_t/m_t ≈ 0.8%). Corrections are O(Γ/M).
- `bwcutoff` controls how far off-shell the intermediate tops can be.
- Spin correlations between production and decay are preserved.
- Computationally efficient.

**Details →** [Decays & Widths](decays_and_widths.md) for full decay chain syntax including nested decays and parenthesized final states.

### Approach 2: Full Matrix Element

```
generate p p > w+ w- b b~
```

- Includes **all** diagrams: doubly-resonant (tt̄), singly-resonant (single-top-like), non-resonant, and all interferences.
- Gauge invariant. This is the most complete LO calculation.
- `bwcutoff` does not affect the cross section (only the LHE event record).
- More expensive computationally.

### Approach 3: `$` Operator (Off-Shell Complement)

```
generate p p > w+ w- b b~ $ t t~
```

- Keeps all diagrams but **forbids** t and t̄ from being on-shell in the s-channel.
- The exclusion window is M ± bwcutoff × Γ — events where an s-channel top would be inside this window are rejected.
- This is the **approximate complement** of the decay chain: decay chain covers the on-shell region, `$` covers the off-shell region.

**Key points:**
- The `$` approach is only approximately gauge invariant. Diagrams with forced s-channel propagators are not gauge invariant far from the Breit-Wigner peak.
- You **cannot** simply add the decay-chain cross section and the `$`-filtered cross section to recover the full result, because interference between resonant and non-resonant diagrams is lost.
- For physics predictions, always use the full matrix element (Approach 2). Use Approaches 1 and 3 only for understanding the anatomy of contributions.

### Approach 4: `$$` Operator (Diagram Removal)

```
generate p p > w+ w- b b~ $$ t t~
```

- **Removes** all diagrams with s-channel t or t̄ entirely. No phase-space cut — the diagrams simply do not exist.
- The remaining diagrams may or may not be gauge invariant. Always verify with `check gauge`.
- Unlike `$`, this does not depend on `bwcutoff`.

### Approach 5: DR/DS Schemes at NLO (MadSTR Plugin)

At NLO, the overlap between processes like tt̄ production and tW single-top production becomes a formal problem: real-emission corrections to tW include doubly-resonant tt̄-like diagrams. Two schemes handle this:

| Scheme | Method | Description |
|--------|--------|-------------|
| **Diagram Removal (DR)** | Remove doubly-resonant diagrams | All real-emission diagrams containing two resonant top propagators are discarded. Simple but introduces a scheme dependence. |
| **Diagram Subtraction (DS)** | Subtract on-shell limit | The on-shell tt̄ contribution is subtracted locally in phase space, keeping all diagrams. More theoretically consistent but computationally involved. |

These schemes are implemented in the **MadSTR plugin** (arXiv:1907.04898). Install from GitHub (`https://github.com/mg5amcnlo/MadSTR`) by copying the inner `MadSTR/` directory into `<MG5_DIR>/PLUGIN/MadSTR`, then launch MadGraph with `--mode=MadSTR`.

> **Version compatibility:** MadSTR requires MG5_aMC@NLO v2.9.0 or later. It has been validated through v3.5.2 and declares support up to v3.6.x (as specified in `__init__.py`: `maximal_mg5amcnlo_version = (3,6,1000)`). For MG5 v3.7.0+, manual editing of the plugin's `__init__.py` (raising `maximal_mg5amcnlo_version`) or `os_wrapper_fks.inc` may be required — check the GitHub repository for updates.

The DR/DS difference provides a systematic uncertainty estimate for the overlap treatment.

### Summary: Choosing the Right Approach

| Goal | Recommended approach |
|------|---------------------|
| Full physics prediction at LO | `p p > w+ w- b b~` (full ME) |
| Efficient on-shell tt̄ generation | Decay chain: `p p > t t~, t > ...` |
| Understanding non-resonant size | Compare full ME to decay chain |
| NLO tt̄ with tW overlap handled | MadSTR plugin (DR/DS) |
| Isolating non-resonant contributions (approximate) | `$ t t~` with appropriate `bwcutoff` |
| Publication result | Full ME or NLO with MadSTR |

## Diagram Filter Plugin (`--diagram_filter`)

The `--diagram_filter` flag activates a user-defined Python function that selectively removes individual Feynman diagrams during process generation. This provides finer-grained control than the built-in `/`, `$`, `$$` operators or coupling-order constraints.

**Warnings:**
- This feature works at **leading order only**. It is not available for NLO processes.
- Removing diagrams can break **gauge invariance**. The MadGraph FAQ states: *"Be carefull about gauge invariance (a non gauge invariant subset will also break lorentz invariance)"* ([FAQ-General-15](https://cp3.irmp.ucl.ac.be/projects/madgraph/wiki/FAQ-General-15)). The lead developer describes this mechanism as *"not a real plugin [but] a (extremelly dangerous) hack"* ([Launchpad Q&A #701855](https://answers.launchpad.net/mg5amcnlo/+question/701855)). Always validate filtered results with `check gauge` and `check lorentz`.
- The filter is applied to **all subprocesses**, including decay chains. See the "Decay Chains" subsection below.

### Setup

1. Create the file `PLUGIN/user_filter.py` in the MadGraph installation directory.
2. Define a function `remove_diag(diag, model)` that returns `True` to **discard** a diagram or `False` to **keep** it.
3. Append `--diagram_filter` to the `generate` or `add process` command.

```
generate p p > w+ w+ j j --diagram_filter
add process p p > w+ w- j j --diagram_filter
```

The `--diagram_filter` flag must appear **at the very end** of the complete process definition (after any decay chains, coupling-order constraints, and `@N` tags). Placing it within the process definition causes a *"No particle --diagram_filter in model"* error ([Launchpad Q&A #696554](https://answers.launchpad.net/mg5amcnlo/+question/696554)).

```
# CORRECT — flag at the very end after decay chains and tags:
generate p p > z w- j j QCD=99, z > l+ l-, w- > j j @0 --diagram_filter

# WRONG — flag placed before the decay chain:
generate p p > z w- j j --diagram_filter, z > l+ l-, w- > j j
```

MadGraph prints a warning showing how many diagrams were removed per subprocess:
```
WARNING: Diagram filter is ON and removed N diagrams for this subprocess.
```

### Decay Chains

When `--diagram_filter` is used with decay chains (comma syntax), the filter function is called for **every subprocess** — both the production process and each decay chain. For example, with `generate p p > z w- j j, z > l+ l-, w- > j j --diagram_filter`, the `remove_diag` function is called separately for the `p p > z w- j j` production, the `z > l+ l-` decay, and the `w- > j j` decay.

To apply different logic to production vs decay diagrams, inspect the diagram structure inside `remove_diag`. For instance, check the number of initial-state legs or use `len(draw.initial_vertex)` in the drawing API to distinguish production diagrams (2 initial-state particles) from decay diagrams (1 initial-state particle).

**Caution:** A filter that is too restrictive can remove ALL diagrams from a decay subprocess, causing a `NoDiagramException: No amplitudes generated` error.

### Diagram Data Structure (Legacy API)

The `diag` argument is a `Diagram` object containing a list of vertices. Each vertex represents a Feynman diagram vertex and has the following structure:

| Attribute | Type | Description |
|-----------|------|-------------|
| `diag['vertices']` | list | All vertices in the diagram |
| `vertex['id']` | int | Vertex interaction ID; **`0` = identity vertex** (always skip vertices with `id` in `[0, -1]`) |
| `vertex['legs']` | list | Particles (legs) attached to this vertex |
| `leg['id']` | int | PDG code of the particle (e.g., 21 = gluon, 24 = W⁺, 6 = top) |
| `leg['number']` | int | Leg number in the DAG |
| `leg['state']` | bool | `True` for s-channel / final-state propagators, **`False` for t-channel propagators** |
| `diag.get('orders')` | dict | Coupling orders for this diagram (e.g., `{'QCD': 2, 'QED': 2}`) |

**T-channel identification:** The authoritative way to identify t-channel propagators is `leg.get('state') == False`. Do **not** rely on `leg['number'] < 3` — while this heuristic appears in some MadGraph examples, it is inaccurate because s-channel propagators formed by combining both initial-state legs also get `number < 3`.

**Propagator convention:** In each vertex, `vertex['legs'][-1]` (the last leg) is the propagator connecting this vertex to the rest of the diagram.

### Diagram Data Structure (Drawing API)

For more complex filtering, convert the DAG to a full graph representation using the drawing module. The following code runs inside `PLUGIN/user_filter.py` within the MadGraph environment (not standalone):

```
# Inside PLUGIN/user_filter.py — requires the MadGraph environment
import madgraph.core.drawing as drawing

def remove_diag(diag, model):
    draw = drawing.FeynmanDiagram(diag, model)
    draw.load_diagram()
    draw.define_level()
    # Now use draw.vertexList, draw.lineList, draw.initial_vertex
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `draw.vertexList` | list | All vertices in the diagram |
| `draw.initial_vertex` | list | External particle vertices |
| `draw.lineList` | list | All particles: initial states, final states, and propagators |
| `vertex.lines` | list | `FeynmanLine` objects connected to this vertex |
| `vertex.level` | int | Hierarchy level (`0` = initial state) |
| `line.id` | int | PDG code |
| `line.begin` | vertex | Starting vertex of the line |
| `line.end` | vertex | Ending vertex of the line |
| `line.number` | int | Original DAG leg number |

### Examples

All examples below are meant to be placed in `PLUGIN/user_filter.py`. They define the `remove_diag` function that MadGraph calls during process generation.

#### Filter by Coupling Orders

```python
def remove_diag(diag, model):
    """Keep only diagrams with exactly QCD=2."""
    if diag.get('orders').get('QCD', 0) != 2:
        return True
    return False
```

#### Remove T-Channel Quarks (Legacy API)

```python
def remove_diag(diag, model=None):
    """Remove all diagrams with a quark in the t-channel."""
    for vertex in diag['vertices']:
        if vertex['id'] in [0, -1]:    # skip identity/sewing vertices
            continue
        propagator = vertex['legs'][-1]
        if not propagator.get('state'):   # t-channel propagator (state == False)
            if abs(propagator['id']) in [1,2,3,4,5]:  # quark PDG codes
                return True
    return False
```

#### Remove 4-Point Contact Interactions (Drawing API)

```
# Inside PLUGIN/user_filter.py — requires the MadGraph environment
import madgraph.core.drawing as drawing

def remove_diag(diag, model):
    """Remove diagrams containing 4-point vertices."""
    draw = drawing.FeynmanDiagram(diag, model)
    draw.load_diagram()
    for v in draw.vertexList:
        if len(v.lines) > 3:
            return True
    return False
```

#### Production-Only Filter (Skip Decay Chain Diagrams)

```
# Inside PLUGIN/user_filter.py — requires the MadGraph environment
import madgraph.core.drawing as drawing

def remove_diag(diag, model):
    """Apply filter only to production diagrams (2 initial-state particles).
    Decay chain diagrams (1 initial-state particle) are kept unconditionally."""
    draw = drawing.FeynmanDiagram(diag, model)
    draw.load_diagram()
    draw.define_level()
    if len(draw.initial_vertex) < 2:
        return False  # this is a decay subprocess — keep it
    # Apply your production filter logic here
    for v in draw.vertexList:
        if len(v.lines) > 3:
            return True
    return False
```

### When to Use the Diagram Filter vs Built-In Operators

| Goal | Best approach |
|------|---------------|
| Remove all diagrams with a specific s-channel particle | `$$` operator |
| Remove all diagrams with a specific particle anywhere | `/` operator |
| Forbid on-shell s-channel resonance only | `$` operator |
| Restrict to pure EW or pure QCD diagrams | Coupling-order constraints (e.g., `QCD=0`) |
| Filter by specific propagator type in specific channel | `--diagram_filter` |
| Remove specific vertex topologies (e.g., 4-point) | `--diagram_filter` |
| Filter based on diagram-level coupling-order combinations | `--diagram_filter` |

### Known Issues (Historical)

The following bugs have been fixed in past MadGraph releases. They are listed here for users on older versions.

- **Crossed diagrams not filtered ([Bug #1820040](https://bugs.launchpad.net/mg5amcnlo/+bug/1820040)):** In MadGraph v2.6.5 and earlier, diagrams reused via crossing symmetry bypassed the filter. Fixed in June 2019.
- **MadSpin crash with `--diagram_filter` ([Bug #1659128](https://bugs.launchpad.net/mg5amcnlo/+bug/1659128)):** MadSpin could crash with *"InvalidCmd: No particle ... in model"* when used on outputs produced with `--diagram_filter`. Fixed in March 2017. Additionally, the lead developer warns that *"a lot of extension (like MadSpin/…) will not work any longer"* when diagram filtering is used ([Q&A #626578](https://answers.launchpad.net/mg5amcnlo/+question/626578)). Test carefully before large production runs.
- **`ValueError: level must be >= 0` ([Q&A #695863](https://answers.launchpad.net/mg5amcnlo/+question/695863)):** Affected v2.8.2 due to a bug in the plugin import mechanism (`misc.py`). Fixed in v2.9.3 (revision 304).

## Process Validation: The `check` Command

The `check` command validates process definitions and model implementations by testing fundamental physics properties (gauge invariance, Lorentz invariance, crossing symmetry). It is essential for validating custom UFO models from FeynRules and for verifying that diagram filtering preserves gauge invariance.

### Syntax

```
check <type> <process_definition> [options]
```

where `<type>` is one of the types listed below, and `<process_definition>` follows standard MG5 syntax (including `/`, `$`, `$$` filtering and coupling-order constraints).

### Check Types

| Type | What It Tests | Tree-level | Loop |
|------|--------------|------------|------|
| `full` | Runs **all four** checks: permutation, gauge, brs, lorentz | Yes | Yes |
| `gauge` | Compares |M|² in **unitary gauge** vs **Feynman gauge** | Yes | Yes (QCD-only NLO) |
| `brs` | Tests **Ward identities** by replacing ε_μ → p_μ for a massless gauge boson | Yes | Yes |
| `lorentz` | Compares |M|² across **four reference frames** (lab + 3 boosts) | Yes | Yes |
| `permutation` | Generates all particle orderings and compares matrix elements | Yes | Yes |
| `cms` | Validates **complex mass scheme** NLO implementation by scaling widths with λ | — | NLO only |
| `timing` | Benchmarks code execution time | — | Loop only |
| `stability` | Returns numerical stability statistics | — | Loop only |
| `profile` | Combined timing + stability (non-interactive) | — | Loop only |

**Important:** The only valid check type keywords are exactly those listed above. In particular, `lorentz_invariance` is **not** a valid alias for `lorentz` — using it causes MG5 to silently misparse the command (treating the unknown word as part of the process definition).

### Basic Examples

```
import model sm
# Run all tree-level checks on a process
check full p p > t t~

# Gauge invariance only
check gauge p p > e+ e-

# Lorentz invariance only
check lorentz p p > w+ w- h

# Ward identity (BRS) check — requires photon or gluon
check brs g g > t t~

# Permutation check
check permutation p p > e+ e- j

# Verify gauge invariance of a filtered process
check gauge p p > e+ e- $$ a
```

### How Each Check Works

#### Gauge Check

Computes |M|² at a random phase-space point in both **unitary gauge** and **Feynman gauge**. All particle widths are **automatically set to zero** during this check (finite widths break gauge invariance unless the complex mass scheme is used).

**Output columns:**

| Column | Meaning |
|--------|---------|
| Process | The process tested |
| Unitary | |M|² computed in unitary gauge |
| Feynman | |M|² computed in Feynman gauge |
| Relative diff | \|ME_F − ME_U\| / max(ME_F, ME_U) |
| Result | Passed / Failed |

Additional **JAMP** rows show individual color-flow amplitude contributions. Each JAMP should independently satisfy gauge invariance.

**Pass threshold:** Relative difference < 10⁻⁸ (same threshold for both tree-level and loop processes).

#### BRS (Ward Identity) Check

For one external massless gauge boson (photon or gluon), replaces the polarization vector ε_μ with the boson's 4-momentum p_μ. By the Ward identity, the resulting amplitude should vanish.

**Output columns:**

| Column | Meaning |
|--------|---------|
| Process | The process tested |
| Matrix | Standard |M|² value |
| BRS | |M|² with ε_μ → p_μ substitution |
| Ratio | BRS / Matrix |
| Result | Passed / Failed |

**Pass thresholds:**

| Process type | Threshold |
|---|---|
| Tree-level | Ratio < 10⁻¹⁰ |
| Loop | Ratio < 10⁻⁵ |

**Note:** If the process has no external massless gauge bosons (no photon or gluon), the BRS check prints `No ward identity` and skips — this is not a failure.

#### Lorentz Invariance Check

Computes |M|² (summed over helicities) in four reference frames: the lab frame and three Lorentz-boosted frames (boost β ≈ 0.5 along x, y, z axes). A Lorentz-invariant matrix element must give identical results in all frames.

**Output columns:**

| Column | Meaning |
|--------|---------|
| Process | The process tested |
| Min element | Smallest |M|² across the 4 frames |
| Max element | Largest |M|² across the 4 frames |
| Relative diff | (max − min) / max |
| Result | Passed / Failed |

**Pass thresholds:**

| Process type | Threshold |
|---|---|
| Tree-level | < 10⁻¹⁰ |
| Loop (rotations) | < 10⁻⁶ |
| Loop (boosts) | < 10⁻³ |

For loop processes, the Lorentz check uses **two separate thresholds**: a tighter threshold (10⁻⁶) for rotations and a more relaxed threshold (10⁻³) for boosts, because numerical loop integration introduces larger errors under Lorentz boosts than under rotations.

#### Permutation Check

Generates the process with all possible orderings of final-state particles (different diagram-building and HELAS call sequences) and compares the resulting matrix elements at the same phase-space point.

**Output columns:**

| Column | Meaning |
|--------|---------|
| Process | The process tested |
| Min element | Smallest |M|² across all orderings |
| Max element | Largest |M|² across all orderings |
| Relative diff | 2 × \|max − min\| / (\|max\| + \|min\|) |
| Result | Passed / Failed |

Note: the permutation check uses the **symmetrized relative difference** formula `2 × |max − min| / (|max| + |min|)`, not the simple `(max − min) / max` used by other checks.

**Pass thresholds:**

| Process type | Threshold |
|---|---|
| Tree-level | < 10⁻⁸ |
| Loop | < 10⁻⁵ |

#### CMS (Complex Mass Scheme) Check

Validates the NLO complex mass scheme implementation. Scales all widths by a parameter λ and checks that the difference between CMS and fixed-width results vanishes as λ → 0 with the expected power-law behavior.

```
check cms u d~ > e+ ve [virt=QCD]
check cms u d~ > e+ ve a [virt=QCD QED] --lambdaCMS=(1.0e-6,5)
```

Key options:

| Option | Default | Description |
|--------|---------|-------------|
| `--lambdaCMS=(min,N)` | `(1.0e-6,5)` | Tuple: minimum λ and points per decade (logarithmic spacing) |
| `--lambdaCMS=[list]` | — | Explicit list of λ values (must include 1.0); spaces must be escaped |
| `--offshellness=X` | `10.0` | Minimum off-shellness: resonance must satisfy p² > (X+1)M²; must be > −1 |
| `--cms=<orders>,<rules>` | auto | Coupling orders and parameter scaling rules (see below) |
| `--name=<name>` | auto | Base name for output/pickle files |
| `--seed=N` | `666` | Seed for kinematic configuration |
| `--tweak=<spec>` | — | Modify computational setup (e.g., `alltweaks` for comprehensive test) |
| `--analyze=f1.pkl,...` | — | Re-analyze previously generated results without recomputation |

The `--cms` option has two comma-separated parts: (1) coupling orders joined by `&` (e.g., `QED&QCD`), and (2) parameter scaling rules (e.g., `aewm1->10.0/lambdaCMS&as->0.1*lambdaCMS`).

The CMS check produces plots showing Δ vs λ (upper panel) and Δ/λ vs λ (lower panel). A successful check shows the Δ/λ curve flattening to a constant at small λ, confirming that the CMS–fixed-width difference vanishes at the expected rate.

### Pass/Fail Threshold Summary

| Check | Formula | Tree threshold | Loop threshold |
|-------|---------|---------------|----------------|
| Gauge | \|ME_F − ME_U\| / max(ME_F, ME_U) | < 10⁻⁸ | < 10⁻⁸ |
| BRS | BRS / Matrix | < 10⁻¹⁰ | < 10⁻⁵ |
| Lorentz | (max − min) / max | < 10⁻¹⁰ | Rotations: < 10⁻⁶, Boosts: < 10⁻³ |
| Permutation | 2\|max − min\| / (\|max\| + \|min\|) | < 10⁻⁸ | < 10⁻⁵ |
| CMS | Visual (Δ/λ → constant) | — | NLO only |

### Common Failure Causes and Remediation

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Gauge check fails | Diagram filtering broke gauge invariance | Remove or adjust `$`/`$$`/`/` filtering |
| Gauge check fails (custom model) | Incorrect UFO model (wrong vertices, missing diagrams) | Re-export from FeynRules; check vertex definitions |
| BRS prints `No ward identity` | No external photon or gluon in process | Not a failure — BRS only applies when massless gauge bosons are external |
| Lorentz check fails | Missing Feynman diagrams or incorrect model implementation | Check diagram filtering; re-validate UFO model |

## Squared Coupling Order Syntax

The `^2` suffix applies coupling constraints at the squared-amplitude level (|M|²) rather than the amplitude level. This enables selection of specific interference patterns:

```
generate p p > j j QED^2==2 QCD^2==2    # QED-QCD interference terms only
```

Supported operators are `==`, `<=`, and `>`:

```
generate p p > e+ e- j j QED^2==4 QCD^2==0    # pure EW squared terms
generate p p > e+ e- j j QED^2==2 QCD^2==2    # QCD-EW interference
generate p p > e+ e- j j QCD^2<=4              # all terms up to QCD^2=4
```

Without `^2`, coupling orders constrain amplitudes: `QCD=2` means amplitudes have at most 2 QCD vertices (2 powers of $g_s$). With `^2`, the constraint applies to the squared matrix element and counts powers of $g_s$ (NOT $\alpha_s$): `QCD^2==4` selects terms with 4 powers of $g_s$ in |M|² (= 2 powers of $\alpha_s$), e.g., from the product of an amplitude with QCD=2 and its conjugate with QCD=2, giving 2+2=4 $g_s$ powers total.

A negative value `COUP^2==-I` refers to the N^(-I+1)LO term in the expansion of that coupling order, which is useful for isolating specific perturbative contributions.

This syntax is essential for VBS (vector boson scattering) studies where QCD-EW interference terms must be isolated or excluded.

## Automatic Coupling Order

When you don't specify coupling orders, MG5 automatically determines them by assigning weights to each coupling type:

- QCD coupling: weight 1
- QED coupling: weight 2

MG5 computes the total weight for each diagram and selects diagrams with the **lowest total weight** that gives a non-zero contribution. This means it minimizes the QED order.

### Example: `p p > w+ b b~ j j`

Without explicit orders, MG5 selects diagrams that minimize QED couplings. This may suppress relevant signal diagrams (e.g., diagrams with intermediate top quarks) in favor of pure QCD diagrams.

**Fix**: Explicitly specify coupling orders:

```
generate p p > w+ b b~ j j QCD=4 QED=1
```

### When Automatic Ordering Fails

The automatic ordering can give unexpected results when:
- Signal and background have different coupling structures
- You want specific topologies (e.g., VBF vs gluon fusion)
- Mixed QCD/EW processes where both contribute at similar orders

**Rule of thumb**: For simple processes (pure QCD or pure EW), automatic ordering works fine. For mixed processes, always specify coupling orders explicitly.

### When Automatic Ordering Drops Diagrams vs. Keeps All

### When does WEIGHTED drop diagrams?

WEIGHTED only drops diagrams when a process has **multiple coupling-order combinations** that produce valid topologies. If all diagrams share the same coupling orders, WEIGHTED keeps everything.

**Key rule**: Count the minimum number of QCD and QED vertices required by the final state. If the final state forces a unique coupling-order split, WEIGHTED is a no-op.

### Worked Example 1: Purely electroweak final state — no diagrams dropped

```
generate p p > mu+ mu- a
```

The final state (two charged leptons + photon) couples only via QED. Every tree-level diagram has exactly **QED=3, QCD=0** (WEIGHTED = 6). There is only one coupling-order combination, so WEIGHTED keeps all 32 diagrams:

```
generate p p > mu+ mu- a              # 32 diagrams, WEIGHTED<=6
generate p p > mu+ mu- a QED<=3       # 32 diagrams (identical)
generate p p > mu+ mu- a QED=99       # 32 diagrams (identical)
```

**How to recognize this case**: If every final-state particle couples only electromagnetically (leptons, photons) and the initial state is `p p`, then all diagrams share the same coupling orders and WEIGHTED changes nothing.

| Process | Coupling orders | Why uniform |
|---------|----------------|-------------|
| `p p > e+ e-` | QED=2, QCD=0 | Drell-Yan, purely EW final state |
| `p p > mu+ mu- a` | QED=3, QCD=0 | Leptons + photon, all EW |
| `e+ e- > mu+ mu-` | QED=2, QCD=0 | Leptonic initial and final state |

### Worked Example 2: Mixed QCD/EW final state — diagrams are dropped

```
generate p p > t t~
```

Top-quark pairs can be produced via **QCD** (g g → t t~ and q q~ → g → t t~, with QCD=2, WEIGHTED=2) and via **EW** (q q~ → Z/γ → t t~, with QED=2, WEIGHTED=4). The default `WEIGHTED<=2` keeps only the QCD diagrams (7 diagrams). With `WEIGHTED<=99`, all 15 diagrams are included. The 8 additional diagrams are the EW topologies.

To include EW contributions:

```
generate p p > t t~ QED=2 QCD=2    # include both QCD and EW diagrams
generate p p > t t~ WEIGHTED<=99    # equivalent: raise the WEIGHTED ceiling
```

| Process | Default WEIGHTED | What is dropped | Fix |
|---------|-----------------|-----------------|-----|
| `p p > t t~` | `<=2` (7 diag.) | EW diagrams q q~ → Z/γ → t t~ (8 diag.) | `WEIGHTED<=99` or `QED=2 QCD=2` |
| `p p > w+ b b~ j j` | Minimal | EW topologies (single-top, ttbar-mediated) | Increase `WEIGHTED` or set explicit orders |
| `p p > e+ e- j j` | Minimal | Subleading EW contributions | Set both `QCD` and `QED` explicitly |

### Diagnostic checklist

1. **Run with default orders** and note the diagram count and `WEIGHTED<=N` value in the output.
2. **Run with `WEIGHTED<=99`** (or `QED=99 QCD=99`) and compare diagram counts.
3. If the counts differ, WEIGHTED dropped diagrams. Decide whether the dropped diagrams matter for your physics.
4. Use `display processes` to inspect which subprocesses and coupling-order combinations are included.

### Common misconceptions

- **"I must always specify coupling orders to be safe."** — No. For processes where only one coupling-order combination exists (purely EW final states), the default is already complete.
- **"Specifying `QED=99` always adds more diagrams."** — No. It only adds diagrams if there are valid higher-QED topologies that WEIGHTED excluded. For `p p > mu+ mu- a`, `QED=99` gives the same 32 diagrams as the default.
- **"WEIGHTED drops diagrams for any process with photons."** — No. A photon in the final state does not automatically mean diagrams are dropped. What matters is whether the process admits multiple coupling-order splits.
- **"Pure QCD processes like `p p > t t~` are unaffected by WEIGHTED."** — No. While `p p > t t~` is predominantly QCD, the EW production diagrams (q q~ → Z/γ → t t~) exist at a higher WEIGHTED value and are dropped by default.

## Polarized Boson Syntax

Since MG5 v2.7.0, you can generate specific polarization states using curly braces:

```
generate e+ e- > w+{0} w-{T}          # longitudinal W+, transverse W-
generate p p > t{L} t~{R}             # left-handed top, right-handed antitop
generate p p > w+{0} w-{T}, w+ > e+ ve   # with decay chain
```

### Polarization Labels

| Label | Meaning | Applies to |
|-------|---------|------------|
| `{0}` | Longitudinal | Massive vector bosons (W, Z) |
| `{T}` | Transverse (sum of +/- helicities) | Massive vector bosons |
| `{L}` | Left-handed helicity | Fermions |
| `{R}` | Right-handed helicity | Fermions |

### Reference Frame

The polarization is defined in a reference frame controlled by the `me_frame` parameter in the run_card. The default is the partonic center-of-mass frame.

### Use Cases

- Studying the Goldstone boson equivalence theorem (longitudinal W/Z scattering)
- Measuring polarization fractions in top quark decays
- Testing anomalous couplings through polarization-dependent observables

### Limitation: External Particles Only

Polarization syntax applies to **external** (initial-state or final-state) particles only. It **cannot** restrict the polarization of intermediate particles in decay chains. The matrix element sums over all polarization states of the intermediate particle, and the physical polarization information is encoded in the angular distributions of the decay products.

```
generate e+ e- > w+{0} w-{T}              # OK: W+, W- are external final-state particles
generate p p > t{L} t~{R}                 # OK: t, t~ are external final-state particles
```

To study the polarization of an unstable particle, generate it as a **polarized final-state particle** and then decay it separately with MadSpin. For example, to study longitudinal W+ bosons from top decay:

```
# Step 1: Generate tops as external particles
generate p p > t t~
# Step 2: Use MadSpin to decay (spin correlations preserved, all W polarizations included)
# Step 3: Analyze angular distributions of W decay products to extract polarization fractions
```

MadSpin preserves the full spin correlation between production and decay, so the physical polarization information is encoded in the angular distributions of decay products — it does not need to be restricted at generation level.

## 4-Flavor vs 5-Flavor Scheme

The flavor scheme determines whether the b-quark is treated as a massive parton or a massless constituent of the proton.

### 5-Flavor Scheme (Default)

```
import model sm-no_b_mass
```

- b-quark is massless
- b appears in the proton PDF and in `p`/`j` multiparticle labels
- Resums large logs of the form ln(Q²/m_b²) via the PDF evolution
- Appropriate for most processes at high Q²

### 4-Flavor Scheme

```
import model sm
define p = g u c d s u~ c~ d~ s~     # explicitly exclude b from proton
```

- b-quark is massive (mb ≈ 4.7 GeV)
- b does NOT appear in the proton PDF or in `p`/`j`
- Appropriate when b-quark mass effects matter

In addition to the model choice, set in the run_card:

```
set run_card maxjetflavor 4    # for 4F scheme
set run_card maxjetflavor 5    # for 5F scheme (default with sm-no_b_mass)
```

And use a consistent PDF set (4F PDF for 4F scheme, 5F PDF for 5F scheme).

### When to Use Each

| 4-Flavor Scheme | 5-Flavor Scheme |
|----------------|-----------------|
| bb̄H associated production | Inclusive Higgs production |
| Single-top tW-channel | Single-top t-channel |
| When m_b effects matter | High-Q² processes |
| Low b-quark pT | b-quarks in initial state |

### Consistency Checklist for 4F

1. `import model sm` (massive b)
2. Redefine `p` and `j` to exclude b: `define p = g u c d s u~ c~ d~ s~`
3. `set run_card maxjetflavor 4`
4. Use a 4-flavor PDF set (e.g., NNPDF31_lo_as_0118_nf4)

## Coupling Order Specifications

Beyond basic `QCD=N` and `QED=N`:

```
generate p p > e+ e- j QED=2 QCD<=1   # exact QED order, max QCD order
generate p p > h j j QCD=0              # pure EW (VBF)
generate p p > h j j QCD=0 QED=4        # explicit both orders
```

For VBF Higgs isolation:

```
# EW only (includes VBF + VH with hadronic V decay)
generate p p > h j j QCD=0

# Pure VBF only (exclude VH)
generate p p > h j j $$ w+ w- z / a QCD=0
```

Note: `heft` model should NOT be used for VBF since it only provides the ggH effective vertex, not the VBF vertex.

## Identical Particles and Symmetry Factors

When identical particles appear in the final state (e.g., `p p > z z`, `p p > j j j`), MadGraph automatically handles the combinatorial symmetry factors. During matrix element generation, MG5 identifies amplitudes that produce the same final-state configuration and combines them into a single matrix element with the appropriate symmetry factor. This avoids double-counting identical permutations.

### How It Works

MG5 uses `IdentifyMETag` to group amplitudes that differ only in the ordering of identical final-state particles. These amplitudes share the same squared matrix element and are combined during `generate_matrix_elements`, with a symmetry factor that accounts for the number of equivalent permutations.

For example, `p p > z z` has a symmetry factor of 1/2! = 1/2 because the two Z bosons are identical. The user does not need to apply any manual correction.

### Decay Chains with Identical Particles

A decay specification applies to **all** instances of the matching particle type in the final state. When the final state contains multiple identical particles and a decay is specified for that particle type, every instance is decayed. There is no mechanism to selectively decay only a subset of identical particles. See [Decays & MadSpin](08_decays_and_madspin.md) for full decay chain documentation.

### Identical Particles in Production and Decay

When using the reweight module (e.g., for parameter scans or PDF variations), identical particles that appear in both the production process and decay products require special treatment. The `identical_particle_in_prod_and_decay` option in the reweight interface controls this:

```
# In the reweight card or interface:
set identical_particle_in_prod_and_decay average   # default: average over assignments
set identical_particle_in_prod_and_decay max       # take the assignment with max weight
set identical_particle_in_prod_and_decay crash      # abort if ambiguity detected
```

This is relevant when, for instance, a process produces a b-quark in production and the decay also produces a b-quark, making it ambiguous which b-quark in the event corresponds to which role. The `average` option (default) averages over all possible assignments; `max` selects the highest-weight assignment.

## Cross-References

- **[← Reference: Process Generation](process_generation.md)**
- [Process Syntax](02_process_syntax.md) — basic `generate` syntax, `@N` tags
- [Cards & Parameters](04_cards_and_parameters.md) — bwcutoff, maxjetflavor
- [Models](03_models.md) — sm vs sm-no_b_mass, restriction files
- [NLO Computations](06_nlo_computations.md) — NLO coupling order considerations
- [Troubleshooting](16_troubleshooting.md) — VBF isolation, 0 diagrams, gauge invariance issues
- [Decays & MadSpin](08_decays_and_madspin.md) — decay chains and polarized boson decays
- [Matching & Merging](07_matching_merging.md) — @N multiplicity tags for matching
- [Systematics & Reweighting](13_systematics_reweighting.md) — reweight module and parameter scans
