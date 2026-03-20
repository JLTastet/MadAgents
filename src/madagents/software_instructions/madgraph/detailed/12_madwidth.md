# 12 — MadWidth

MadWidth computes particle decay widths and branching ratios within MadGraph5. By default, it calculates **tree-level (LO)** partial widths for all kinematically allowed decay channels of specified particles.

**NLO consistency note**: Since `compute_widths` and `DECAY X auto` produce LO widths by default, using them with NLO matrix elements introduces an O(alpha_s) mismatch. The sum of LO partial widths will not exactly match the NLO total width, creating a small systematic bias in the Breit-Wigner normalization and branching ratios. For most processes this is a sub-percent effect, but for precision studies, consider using widths from dedicated higher-order calculations.

## The `compute_widths` Command

```
import model sm
compute_widths t w+ w- z h
```

This computes the decay widths and branching ratios for the top quark, W+, W-, Z, and Higgs boson. The results are printed to the terminal and written to the param_card.

### Script Usage

```
import model sm
compute_widths t w+ w- z h
generate p p > t t~
output my_process
launch my_process
  set run_card nevents 10000
  done
```

Run `compute_widths` **before** `output` to ensure the param_card in the output directory has consistent widths. Note: `compute_widths` does not require a generated process — it operates on the model alone. But `output` requires a prior `generate` command.

### Specifying Options

```
compute_widths t --body_decay=2.0      # include 2-body decays only
compute_widths h --precision=0.01      # set precision threshold
compute_widths all                      # compute widths for all particles
```

## Reading the Output

The `compute_widths` command prints a table for each particle:

```
DECAY   6   1.4915e+00   # t : total width
#   BR          NDA   ID1   ID2
    1.000000    2     24     5     # W+ b
```

This shows:
- Total width of the top quark: ~1.49 GeV
- 100% branching ratio to W+b

## Why Consistent Widths Matter

Incorrect widths in the param_card cause: MadSpin BR > 1 errors (width too small) or underweighted events (width too large), incorrect Breit-Wigner resonance windows, and broken NWA factorization. See [Decays & MadSpin](08_decays_and_madspin.md) for details.

## Fixing BR > 1 Errors

When MadSpin reports `Branching ratio larger than one for particle 25 (Higgs)`:

1. Check the DECAY block in the param_card:
   ```
   DECAY 25 1.0e-5    # Wrong! Too small
   ```

2. Fix by computing the correct width:
   ```
   compute_widths h
   ```

3. Or manually set the correct value:
   ```
   set param_card decay 25 6.478e-3
   ```

## Model-Dependent Limitations: Loop-Induced Channels

`compute_widths` computes partial widths using the **tree-level vertices available in the loaded model**. Decay channels that proceed through loop diagrams — and for which the model contains no tree-level effective vertex — are not included.

The most important SM example is the **Higgs boson** in the `sm` model:
- **Included** (tree-level vertices exist): H→bb̄, H→ττ, H→cc̄ (and other kinematically allowed fermionic channels)
- **Not included** (loop-induced, no tree-level vertex in `sm`): H→gg, H→γγ, H→Zγ

The missing channels mean the computed branching ratios and total width are incomplete. Additionally, the tree-level computation uses the b-quark pole mass for the Yukawa coupling, which significantly differs from the running mass used in state-of-the-art predictions. The net result is that `compute_widths` with the `sm` model gives a Higgs width that differs substantially from the physical SM value (~4.1×10⁻³ GeV from LHCHXSWG).

In the `heft` model, the effective Hgg vertex is present, so `compute_widths` with `heft` **will** include H→gg. However, `heft` does not include H→γγ.

**Practical guidance:**
- For the Higgs boson, set the total width manually from external calculations (e.g., LHCHXSWG predictions) rather than relying on `compute_widths`.
- For internal consistency (e.g., MadSpin using the same tree-level matrix elements), the `compute_widths` value can be used — but be aware it does not match the physical SM width.
- For BSM models, be aware that new particles may have significant loop-induced decay channels that `compute_widths` will miss if the model lacks the corresponding effective vertices.
- Running `compute_widths` remains the correct approach for most particles where tree-level channels dominate (top, W, Z, and most BSM particles).

## BSM Models

For BSM models, particle widths are generally not known a priori. Always run `compute_widths` for BSM particles:

```
import model 2HDM    # requires downloaded 2HDM UFO model
compute_widths h+ h- h2 h3 a0
```

This ensures:
- Consistent param_card values for MadSpin and event generation
- Correct branching ratios for decay chain specifications
- Proper Breit-Wigner resonance shapes

## Auto-Width

Setting `DECAY X auto` in the param_card (or via `set param_card decay X auto`) tells MG5 to compute the width automatically during event generation.

## Cross-References

- **[← Reference: Decays & Widths](decays_and_widths.md)**
- [Cards & Parameters](04_cards_and_parameters.md) — DECAY block in param_card
- [Decays & MadSpin](08_decays_and_madspin.md) — width consistency for MadSpin
- [Models](03_models.md) — BSM model setup with compute_widths
- [Troubleshooting](16_troubleshooting.md) — BR > 1 diagnosis
- [Scripted Execution](05_scripted_execution.md) — script examples with compute_widths
