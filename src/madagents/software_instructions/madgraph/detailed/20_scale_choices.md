# 20 — Scale Choices

The renormalization scale (mu_R) and factorization scale (mu_F) are unphysical parameters that appear in perturbative QCD calculations. Their choice affects cross-section predictions, particularly at LO where the dependence is strongest.

## Scale Parameters in the Run Card

```
False  = fixed_ren_scale       ! if True, use fixed renormalization scale
False  = fixed_fac_scale       ! if True, use fixed factorization scale
91.188 = scale                 ! fixed ren scale (GeV), used when fixed_ren_scale = True
91.188 = dsqrt_q2fact1         ! fixed fac scale for beam 1 (GeV)
91.188 = dsqrt_q2fact2         ! fixed fac scale for beam 2 (GeV)
-1     = dynamical_scale_choice ! dynamical scale selection
1.0    = scalefact             ! multiplicative factor applied to the chosen scale
```

## Fixed vs Dynamical Scales

- **Fixed scales** (`fixed_ren_scale = True`): mu_R and mu_F are set to the values of `scale` and `dsqrt_q2fact1`/`dsqrt_q2fact2` respectively, the same for every event.
- **Dynamical scales** (`fixed_ren_scale = False`, default): mu_R and mu_F are computed event-by-event based on the kinematics, using the `dynamical_scale_choice` option. This is the recommended approach for most processes.

When using dynamical scales, the `scale` and `dsqrt_q2fact` values are ignored.

## Dynamical Scale Options

The `dynamical_scale_choice` parameter selects the dynamical scale definition. Allowed values are -1, 0, 1, 2, 3, 4:

| Value | Definition | Formula |
|-------|-----------|---------|
| **-1** | CKKW back-clustering (default) | Clusters final-state particles following the Feynman diagram topology back to a 2->2 system; uses the transverse mass of that system |
| **0** | User-defined | Requires editing `SubProcesses/setscales.f` in the process directory |
| **1** | Total transverse energy | sum of E_T for all final-state particles |
| **2** | HT | sum of transverse mass sqrt(m^2 + pT^2) for all final-state particles |
| **3** | HT/2 | Half the sum of transverse mass |
| **4** | sqrt(s-hat) | Partonic center-of-mass energy |

### When to Use Each

- **-1 (CKKW, default)**: Good general-purpose choice. Follows the structure of the Feynman diagram, giving process-aware scales. Required when using MLM matching (`ickkw = 1`).
- **1 (total E_T)**: Similar to HT but uses transverse energy instead of transverse mass.
- **2 (HT)**: Common choice for multi-jet or heavy-particle production (e.g., tt-bar + jets). Reflects the overall hardness of the event.
- **3 (HT/2)**: Popular choice for top-quark pair production and multi-jet processes. Often gives better perturbative convergence than HT.
- **4 (sqrt(s-hat))**: Fixed for a given collider energy in 2->2 processes. Useful for inclusive cross-sections.
- **0 (user-defined)**: For custom scale definitions. Edit the file `<PROC_DIR>/SubProcesses/setscales.f` — the subroutine `set_ren_scale` receives the four-momenta of all particles and must return the scale value.

## The `scalefact` Multiplier

The `scalefact` parameter multiplies the dynamical scale:

```
mu_R = scalefact * (dynamical scale)
```

Default is 1.0. Common use: set `scalefact = 0.5` to use HT/2 when `dynamical_scale_choice = 2`, which is equivalent to using `dynamical_scale_choice = 3`.

## Separate Factorization Scales per Beam

The factorization scales for the two beams can be set independently via the hidden parameters `fixed_fac_scale1` and `fixed_fac_scale2`:

```
False  = fixed_fac_scale1   ! factorization scale for beam 1
False  = fixed_fac_scale2   ! factorization scale for beam 2
```

This is rarely needed — the main use case is asymmetric colliders where the two beams have very different characteristics.

## The `alpsfact` Parameter

The hidden parameter `alpsfact` (default 1.0) is used in MLM matching to control the alpha_s reweighting at clustering vertices. It multiplies the scale used for alpha_s evaluation at each QCD vertex found by the clustering algorithm. This is only relevant when `ickkw = 1`. See [Matching & Merging](07_matching_merging.md).

## Scale Variations for Uncertainty Estimation

Scale variations are the primary method for estimating perturbative uncertainties. The standard procedure is the 7-point envelope: vary mu_R and mu_F independently by factors of 0.5 and 2 around the central scale, excluding the two extreme anti-correlated combinations (mu_R=0.5, mu_F=2) and (mu_R=2, mu_F=0.5).

This is done automatically via the systematics module:

```
True    = use_syst
systematics = systematics_program
['--mur=0.5,1,2', '--muf=0.5,1,2', '--pdf=errorset'] = systematics_arguments
```

See [Systematics & Reweighting](13_systematics_reweighting.md) for details.

## NLO Scale Choices

At NLO, the run card has additional scale-related parameters:

- `mur_over_ref` and `muf_over_ref`: Ratios of mu_R/mu_ref and mu_F/mu_ref for the central scale.
- `reweight_scale`: Whether to include scale variation weights in the output.
- `rw_rscale` and `rw_fscale`: Lists of scale factors for reweighting (default: `[1.0, 2.0, 0.5]`).

## Cross-References

- **[← Reference: Configuration](configuration.md)**
- [Cards & Parameters](04_cards_and_parameters.md) — all run_card parameters
- [Systematics & Reweighting](13_systematics_reweighting.md) — scale variation uncertainties
- [Matching & Merging](07_matching_merging.md) — scale choices in matched samples, `alpsfact`
- [NLO Computations](06_nlo_computations.md) — NLO-specific scale parameters
- [Troubleshooting](16_troubleshooting.md) — diagnosing scale-related issues
