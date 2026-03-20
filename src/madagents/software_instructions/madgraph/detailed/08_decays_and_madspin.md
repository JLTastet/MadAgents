# 08 — Decays & MadSpin

MadGraph provides two approaches for handling particle decays: inline decay chain syntax in the `generate` command, and the external MadSpin tool. Both preserve spin correlations, but differ in flexibility, performance, and applicability.

## Decay Chain Syntax in `generate`

### On-Shell Decay (Comma Syntax)

```
generate p p > t t~, t > w+ b, t~ > w- b~
```

The **comma** (`,`) forces the intermediate particle to be **on-shell** within a Breit-Wigner window. The comma separates production from decay, and the intermediate particle is required to have an invariant mass within:

```
M - bwcutoff × Γ  <  m_inv  <  M + bwcutoff × Γ
```

where `bwcutoff` (default 15) is set in the run_card.

Key properties:
- The intermediate particle appears in the LHE output.
- Final-state cuts on decay products are **disabled by default** (`cut_decays = F` in the run_card).
- The cross-section equals σ(production) × BR(decay), under the narrow-width approximation (NWA).

### S-Channel Requirement (> Syntax)

```
generate p p > w+ > e+ ve
```

The `>` through an intermediate particle requires it in the **s-channel** but does **not** force it on-shell. Off-shell contributions are included. This gives a different (generally larger) cross-section than the comma syntax.

### Important: These Give Different Results

For the same physics, comma and `>` syntax produce different cross-sections:

```
generate p p > w+, w+ > e+ ve      # on-shell W+, NWA
generate p p > w+ > e+ ve           # s-channel W+ required, off-shell included
generate p p > e+ ve                 # all diagrams, no W+ requirement
```

Each has a different cross-section. The choice depends on the physics question.

### Decay Specifications Apply to All Matching Particles

A decay specification applies to **every** particle of that type in the final state. If the final state contains multiple instances of the same particle, a single decay specification is sufficient to decay all of them. There is no syntax to decay only a subset of identical final-state particles while leaving others stable. This applies equally to both generate-level decay chains and MadSpin `decay` directives.

## Why Production × BR Doesn't Match

A common confusion: generating `p p > t t~` and comparing with `p p > t t~, t > w+ b, t~ > w- b~` expecting σ₁ × BR(t→Wb)² ≈ σ₂. The match is approximate but not exact, due to:

1. **Final-state cuts**: Different final-state particles mean different cuts apply. Disable with `cut_decays = F`.
2. **Width consistency**: The total width in the param_card must match the physical width. MG5 divides the phase-space integral by the total width.
3. **bwcutoff**: Restricts the off-shell range, introducing a small bias.
4. **NWA precision**: The narrow-width approximation has intrinsic precision of order Γ/M.
5. **Scale choices**: Dynamical scale choices can evaluate differently for different final states.
6. **NLO vs LO widths**: If the param_card width is from NLO but the matrix element is LO, there is a mismatch.

## MadSpin

MadSpin is an external tool that decays heavy resonances **after** event generation while preserving spin correlations. It operates between the hard-process generation and the parton shower.

### Advantages of MadSpin

- **Faster**: Decays are applied to already-generated events, avoiding the combinatorial explosion of including all decay products in the matrix element.
- **NLO compatible**: For NLO processes, including decays directly in the `generate` line is often not possible. MadSpin is the recommended approach.
- **Flexible**: Different decay channels can be specified without regenerating the hard process.

### MadSpin in Scripts

The madspin_card uses its own command language — it is **not** a parameter-value card like the run_card or param_card. You cannot use `set madspin_card decay ...` to add decay lines. Instead, use bare `decay` commands directly in the launch block.

> **Common mistake**: Writing `set madspin_card decay t > w+ b, w+ > l+ vl` in a launch block does NOT work. MadGraph will emit a warning (`Command set not allowed for modifying the madspin_card`) and MadSpin will fall back to the default madspin_card, which typically contains all-channel decays. Use bare `decay` commands instead (see below).

**Correct approach — bare `decay` commands in the launch block:**

```
import model sm
generate p p > t t~
output ttbar_madspin
launch ttbar_madspin
  madspin=ON
  shower=PYTHIA8
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  decay t > w+ b, w+ > l+ vl
  decay t~ > w- b~, w- > l- vl~
  done
```

Bare `decay` commands typed during the card-editing phase (between `launch` and `done`) are written directly into the madspin_card.dat. This is the simplest and recommended approach.

**Alternative — provide a custom madspin_card.dat file:**

For complex MadSpin configurations (custom spinmode, BW_cut, multiparticle definitions, etc.), create a `madspin_card.dat` file and provide its path in the launch block:

1. Create a `madspin_card.dat` file:

```
# madspin_card.dat
set spinmode onshell
set BW_cut 15

decay t > w+ b, w+ > l+ vl
decay t~ > w- b~, w- > l- vl~

launch
```

2. Reference it in the launch block:

```
launch ttbar_madspin
  madspin=ON
  shower=PYTHIA8
  /path/to/madspin_card.dat
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  set run_card nevents 10000
  done
```

MadGraph auto-detects the card type from the file content and copies it to the correct location.

### Syntax Comparison: madspin_card vs Other Cards

The `set <card> <param> <value>` syntax in a launch block is supported only for certain cards. The madspin_card is not one of them.

| Card | `set <card>` syntax in launch block | Notes |
|------|-------------------------------------|-------|
| `param_card` | `set param_card mass 6 172.5` | Full parameter-value support |
| `run_card` | `set run_card nevents 10000` | Full parameter-value support |
| `pythia8_card` | `set pythia8_card TimeShower:alphaSvalue 0.118` | Appends Pythia8 directives |
| `delphes_card` | `set delphes_card atlas` | **Presets only**: `default`, `atlas`, or `cms` — not arbitrary parameters |
| `madspin_card` | **Not supported** — use bare `decay` commands or provide file path | `decay t > w+ b, w+ > l+ vl` |

For all cards, you can alternatively provide a file path in the launch block; MadGraph auto-detects the card type.

**Details ->** [Cards and Parameters](detailed/04_cards_and_parameters.md)

### MadSpin Card Configuration

The `madspin_card.dat` contains MadSpin commands executed sequentially. Key directives:

```
# spinmode options:
#   madspin = full spin correlations and off-shell effects (default)
#   full    = alias for madspin (functionally identical)
#   onshell = full spin correlations, particle kept exactly on-shell (requires f2py)
#   none    = no spin correlations, no off-shell effects (supports 3-body decay, loop-induced)
set spinmode madspin
set BW_cut 15              # Breit-Wigner cutoff: on-shell window = mass ± BW_cut*width
                           # Default: -1 (inherit bwcutoff from run_card)

# Multiparticle labels (optional — built-in l+, l-, vl, vl~ are available)
define ell+ = e+ mu+
define ell- = e- mu-

# Decay specifications — bare 'decay' commands, one per line
decay t > w+ b, w+ > l+ vl
decay t~ > w- b~, w- > l- vl~

# 'launch' triggers MadSpin execution
launch
```

**Key points:**
- The `launch` at the end of the madspin_card.dat is required — it triggers the actual decay processing.
- The MadSpin parameter for the BW cutoff is `BW_cut` (not `bwcutoff` — that is the run_card parameter name). When `BW_cut` is set to `-1` (default), MadSpin inherits the value from the run_card's `bwcutoff`.
- The `spinmode` default is `madspin`. Valid values: `madspin`, `full`, `onshell`, `none`. The `full` and `madspin` modes are functionally identical.

**Details ->** [Scripted Execution](detailed/05_scripted_execution.md)

### Cascade Decays with Parentheses

For multi-step cascade decays, parentheses define the nesting hierarchy:

```
decay h2 > z h3 mu+ mu-, (h3 > z h1 j j, h1 > b b~)
```

**Without parentheses**, MadSpin may misinterpret the decay chain, causing orders-of-magnitude errors in the cross-section. Always use parentheses for cascades beyond simple two-body decays.

### Common MadSpin Issues

#### Branching Ratio > 1

```
WARNING: Branching ratio larger than one for particle 25 (Higgs)
```

This means the total width in the param_card is too small. MadSpin computes the partial width for the requested decay and divides by the stated total width. If the partial width exceeds the total width, BR > 1.

**Fix**: Use `compute_widths` to calculate consistent widths, or manually set the correct total width in the param_card. For the Higgs, the SM width is ~6.5×10⁻³ GeV. See [MadWidth](12_madwidth.md).

#### Dependent Parameters Warning

```
WARNING: Failed to update dependent parameter
```

External programs (MadSpin, Pythia8) read the param_card and may get inconsistent values if dependent parameters aren't updated. Respond with `update dependent` when prompted, or ensure manual consistency.

## Multiparticle Labels in Decay Chains

Multiparticle labels in decay specifications are expanded via Cartesian product over all particles in the label. MG5 does **not** validate whether the resulting decay channels are physically allowed.

Example pitfall: Defining `define nu = vl vl~` (mixing neutrinos and antineutrinos) and then writing:

```
decay w+ > l+ nu
```

This expands to both `w+ > l+ vl` (physical: W+ → l+ ν) **and** `w+ > l+ vl~` (unphysical: W+ → l+ ν̄, violates charge conservation). MG5 silently skips unphysical channels that produce no diagrams or have no matching branching ratio, but this can cause confusing behavior: only a subset of the intended channels are generated.

**Best practice**: Use the built-in multiparticle labels (`vl`, `vl~`, `l+`, `l-`) in decay specifications. These are defined with correct particle/antiparticle content:

```
decay w+ > l+ vl       # correct: l+ vl = e+ ve, mu+ vm, ta+ vt
decay w- > l- vl~      # correct: l- vl~ = e- ve~, mu- vm~, ta- vt~
```

Do not define custom multiparticle labels that mix particles and antiparticles for use in decay chains.

## Production vs Decay Radiation

When generating a process with radiation alongside an unstable particle — e.g., `p p > t t~ a` — the matrix element includes photons from **all** sources: initial-state radiation, radiation off the top quarks, and radiation from the decay products (if decays are included). MG5 does not distinguish these contributions; the full matrix element handles them coherently.

However, double counting arises if you **also** decay the tops with MadSpin including photon radiation, or if you combine this sample with events from `p p > t t~` followed by showered decay radiation. To avoid this:

- Generate the full final state in one `generate` command when radiation matters (e.g., `p p > t t~ a, t > w+ b, t~ > w- b~`)
- Or generate `p p > t t~` with MadSpin for decays and rely on the parton shower for soft/collinear radiation — but do NOT add a separate `p p > t t~ a` sample

## Choosing Between Generate-Level Decays and MadSpin

| Criterion | Generate-level decay | MadSpin |
|-----------|---------------------|---------|
| Speed | Slower (full ME) | Faster (post-generation) |
| NLO processes | Often not possible | Recommended approach |
| Spin correlations | Full, exact | Preserved (NWA-level) |
| Off-shell effects | Included (with `>` syntax) | No (on-shell NWA) |
| Flexibility | Fixed at generation | Decay later, reuse events |
| Complex cascades | Limited | Better (with parentheses) |

**When to use which**:

- **LO production**: Prefer generate-level decay chains — they include full off-shell effects and exact spin correlations, and are simpler to set up.
- **NLO production**: Use MadSpin — decay chains are not supported inside `[QCD]` brackets. MadSpin preserves spin correlations at NWA-level accuracy.
- **Scalar particle decays** (e.g., H → WW* → 4f): Spin correlations between production and decay are absent for scalars. MadSpin's NWA limitation is less important here; the main concern is off-shell W* effects, which require generate-level treatment or dedicated tools.
- **Broad resonances** (Γ/M > 5-10%): Do not use decay chain syntax or MadSpin. Generate the full final state as a single process to capture off-shell and interference effects.

## Narrow-Width Approximation

Both comma syntax and MadSpin rely on the NWA, which factorizes production and decay:

```
σ(pp → tt̄ → bW⁺b̄W⁻) ≈ σ(pp → tt̄) × BR(t → Wb)²
```

This is valid when Γ << M (typically Γ/M < 5-10%). For the top quark, Γ/M ≈ 0.8%, so NWA works well. For broad resonances, use the full matrix element (no decay chain syntax).

## The `bwcutoff` Parameter

Controls the Breit-Wigner window for on-shell resonances:

```
15.0    = bwcutoff    ! in the run_card
```

An on-shell particle's invariant mass must satisfy |m - M| < bwcutoff × Γ. The default of 15 widths captures essentially the full resonance. Reduce for narrow cuts; increase for very broad resonances (but consider using the full matrix element instead).

## The `cut_decays` Parameter

Controls whether generation-level cuts apply to decay products:

```
False   = cut_decays    ! in the run_card
```

When `False` (default), cuts like `ptl` and `etal` do not apply to leptons from resonance decays. When `True`, all final-state cuts apply uniformly. This matters for cross-section comparisons between decayed and undecayed processes.

## Cross-References

- **[← Reference: Decays & Widths](decays_and_widths.md)**
- [Process Syntax](02_process_syntax.md) — decay chain syntax basics
- [Cards & Parameters](04_cards_and_parameters.md) — bwcutoff, cut_decays, param_card widths
- [Scripted Execution](05_scripted_execution.md) — MadSpin in scripts
- [NLO Computations](06_nlo_computations.md) — MadSpin with NLO
- [MadWidth](12_madwidth.md) — computing consistent widths
- [Output Formats & LHE](15_output_formats_lhe.md) — intermediate particles in LHE
- [Troubleshooting](16_troubleshooting.md) — BR > 1, width mismatches
- [Width Treatment & Complex Mass Scheme](23_complex_mass_scheme.md) — CMS, NWA, off-shell effects, width consistency
