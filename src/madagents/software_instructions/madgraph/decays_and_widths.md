# Decays & Widths

Quick reference for handling particle decays, width computation, and off-shell effects in MadGraph5.

## Decay Chain Syntax

Two distinct syntaxes exist in the `generate` command for requiring intermediate resonances:

| Syntax | Example | Behaviour |
|--------|---------|-----------|
| Comma (`,`) | `p p > t t~, t > w+ b, t~ > w- b~` | On-shell resonance within Breit-Wigner window (NWA). Cross-section = production x BR. |
| S-channel (`>`) | `p p > w+ > e+ ve` | Requires s-channel propagator but includes off-shell contributions. Generally larger cross-section. |
| No resonance | `p p > e+ ve` | All contributing diagrams, no intermediate-particle requirement. |

These three approaches give **different cross-sections** for the same final state. Choose based on the physics question.

**Nested cascades require parentheses.** For multi-level decay chains (where a decay product itself decays), wrap each branch in parentheses:
```
generate p p > t t~, (t > w+ b, w+ > j j), (t~ > w- b~, w- > l- vl~)
```
Without parentheses, MadGraph silently discards the sub-decays (e.g. `w+ > j j`) — producing fewer diagrams and wrong physics. Flat comma syntax only works for single-level decays like `t > w+ b`.

**Details ->** [Decays & MadSpin](detailed/08_decays_and_madspin.md)

## MadSpin

MadSpin decays heavy resonances **after** event generation while preserving spin correlations. It runs between the hard process and the parton shower.

### Setup in a Script

```
launch my_process
  madspin=ON
  shower=PYTHIA8
  set madspin_card decay t > w+ b, w+ > l+ vl
  set madspin_card decay t~ > w- b~, w- > l- vl~
  done
```

For cascade decays use parentheses: `decay h2 > z h3 mu+ mu-, (h3 > z h1 j j, h1 > b b~)`. Omitting parentheses in multi-step cascades can produce orders-of-magnitude errors.

### `spinmode` Options (in madspin_card)

| Mode | Spin correlations | Off-shell effects | Speed | Use when |
|------|-------------------|-------------------|-------|----------|
| `full` (default) | Yes | Yes | Slowest | Default choice; needed for precision |
| `onshell` | Yes | No | Faster | Narrow resonances where off-shell tails are irrelevant |
| `none` | No | No | Fastest | Phase-space decay; testing or when spin is unimportant |

**Details ->** [Decays & MadSpin](detailed/08_decays_and_madspin.md)

## MadWidth (`compute_widths`)

Computes tree-level partial widths and branching ratios, writing results into the param_card.

```
import model sm
compute_widths t w+ w- z h       # run before 'output' for consistent widths
```

For BSM models, always run `compute_widths` on new particles. Auto-width shortcut: `DECAY X auto` in the param_card computes at generation time.

Output format: `DECAY 6 1.4915e+00` (PDG ID, total width in GeV), followed by `BR NDA ID1 ID2 ...` lines per channel.

**Note:** `compute_widths` produces LO (tree-level) widths. This has two implications:
- Using them with NLO matrix elements introduces an O(alpha_s) mismatch — usually sub-percent but relevant for precision studies.
- Decay channels that have no tree-level vertex in the loaded model are missed entirely. The most notable SM example is the Higgs in the `sm` model: the loop-induced channels H→gg and H→γγ have no tree-level vertices and are not included. For the Higgs, the tree-level width also differs from the physical SM value for other reasons (pole mass vs running mass in the Yukawa coupling). Set the Higgs width manually from external calculations.

**Details ->** [MadWidth](detailed/12_madwidth.md)

## Complex Mass Scheme (CMS)

Promotes unstable-particle masses to complex values (`M^2 -> M^2 - i*M*Gamma`) so that all derived couplings remain gauge-invariant order by order. The simpler fixed-width Breit-Wigner (default at LO) can violate gauge invariance at high energies.

**When to enable:** NLO computations with unstable particles near resonance; precision observables sensitive to gauge invariance; high-energy tails. Usually unnecessary for LO inclusive cross-sections.

```
set run_card complex_mass_scheme True    # NLO run card (hidden parameter)
```

**Details ->** [Width Treatment & Complex Mass Scheme](detailed/23_complex_mass_scheme.md)

## Narrow-Width Approximation (NWA) vs Full Off-Shell

| Aspect | NWA (comma syntax / MadSpin) | Full off-shell (`p p > final-state`) |
|--------|------------------------------|--------------------------------------|
| Validity | Gamma/M < ~5% | Always valid |
| Speed | Fast (factorised) | Slow (many diagrams) |
| Spin correlations | Exact (generate-level) or NWA-level (MadSpin) | Exact |
| Non-resonant diagrams | Excluded | Included |
| Off-shell tails | Excluded (or Breit-Wigner window) | Included |

SM NWA quality: top (~0.8% Gamma/M, excellent), W (~2.6%, good for inclusive), Z (~2.7%, good for inclusive), Higgs (~0.003%, excellent). For BSM resonances with Gamma/M > 5-10%, use the full matrix element.

The NWA also breaks down near **kinematic thresholds**: when the sum of daughter masses approaches or exceeds the parent mass, the decay is dominated by off-shell effects that the NWA cannot capture. If the on-shell decay is kinematically forbidden (e.g., m(parent) < m(daughter1) + m(daughter2)), the comma syntax and MadSpin produce zero or negligible cross-sections. In such cases, generate the full final state without requiring specific intermediate resonances.

**Details ->** [Width Treatment & Complex Mass Scheme](detailed/23_complex_mass_scheme.md)

## `bwcutoff` Parameter

Controls the Breit-Wigner invariant-mass window for on-shell resonances: `15.0 = bwcutoff` in the run_card means the resonance mass must satisfy `|m - M| < bwcutoff * Gamma`. Default 15 captures the full resonance for narrow particles. Reducing to ~5 speeds generation but risks missing off-shell tails. For broad resonances, prefer the full off-shell matrix element over increasing `bwcutoff`.

**Details ->** [Decays & MadSpin](detailed/08_decays_and_madspin.md) | [Width Treatment & Complex Mass Scheme](detailed/23_complex_mass_scheme.md)

## Decision Table: Which Decay Method to Use

| Scenario | Recommended method |
|----------|--------------------|
| LO, narrow resonance, simple decay | Generate-level comma syntax |
| LO, need off-shell / interference | Full final-state generation (no decay chain) |
| NLO production | MadSpin (decay chains not supported inside `[QCD]`) |
| Scalar decay (e.g., H -> WW*) | Generate-level for off-shell W*; MadSpin acceptable if off-shell effects are small |
| Broad resonance (Gamma/M > 5-10%) | Full matrix element -- do not use comma syntax or MadSpin |
| Reusing hard-process events with multiple decay channels | MadSpin (apply different decays without regenerating) |

## Common Pitfalls

- **MadSpin BR > 1**: The total width in the param_card is too small. Fix with `compute_widths` or set the correct width manually.
- **Zero width on s-channel resonance**: Causes zero or wildly fluctuating cross-section. Always set a physical width or use `compute_widths`.
- **Width inconsistency after changing masses**: Rerun `compute_widths` whenever you modify particle masses in the param_card.
- **Mixing particles/antiparticles in multiparticle labels for decays**: e.g., `define nu = vl vl~` then `decay w+ > l+ nu` silently drops unphysical channels. Use the built-in labels (`vl`, `vl~`, `l+`, `l-`).
- **Double-counting radiation**: Do not combine `p p > t t~ a` samples with MadSpin photon radiation or separate showered samples that already include the same radiation.
- **LO widths with NLO matrix elements**: `compute_widths` gives LO widths; small O(alpha_s) mismatch with NLO cross-sections.
- **Missing parentheses in MadSpin cascades**: Multi-step decay chains require parentheses to define nesting; omitting them can give wrong cross-sections by orders of magnitude.

## Cross-References

- [Process Generation](process_generation.md)
- [Configuration](configuration.md)
- [Shower, Detector & Analysis](shower_detector_analysis.md)
