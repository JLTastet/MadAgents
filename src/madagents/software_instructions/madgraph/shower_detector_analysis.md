# Shower, Detector & Analysis

Chain: `MadGraph5 (LHE) -> Pythia8 (HepMC) -> Delphes (ROOT) -> MadAnalysis5`

---

## Pythia8 Parton Shower

Enable with `shower=PYTHIA8`. Output: `Events/run_01/tag_1_pythia8_events.hepmc.gz`.

```
launch my_process
  shower=PYTHIA8
  done
```

**pythia8_card settings** (syntax `Setting:Parameter = Value`):

| Setting | Value | Purpose |
|---------|-------|---------|
| `Tune:pp` | `14` | Monash 2013 tune (default, recommended) |
| `JetMatching:qCut` | `30` | MLM matching scale (GeV); must be > `xqcut` in run_card |
| `JetMatching:nJetMax` | `2` | Max matched extra jets |
| `15:mayDecay` | `off` | Keep taus stable for downstream handling |

Set from script: `set pythia8_card JetMatching:qCut 30`.

**MC@NLO**: For NLO processes, shower parameters are set automatically by MG5 -- no manual edits needed.

**Cross-section after shower**: Unchanged for non-matched processes; for MLM-matched samples the post-shower value is the physical cross-section.

**Details ->** [Parton Shower -- Pythia8](detailed/09_parton_shower_pythia8.md)

---

## Delphes Detector Simulation

Enable with `detector=Delphes` (requires `shower=PYTHIA8`). Output: `Events/run_01/tag_1_delphes_events.root`.

```
launch my_process
  shower=PYTHIA8
  detector=Delphes
  done
```

**Detector cards**: `delphes_card_CMS.dat` (default), `delphes_card_ATLAS.dat`, `delphes_card_FCC.dat`. Supply a custom card by placing its path on its own line in the launch block.

**Jet clustering** (`FastJetFinder` module): algorithm `6` = anti-kT (LHC standard), `5` = C/A, `4` = kT; cone radius `ParameterR` (typically 0.4); min jet pT `JetPTMin` (typically 20 GeV).

**b-tagging** (`BTagging` module): efficiency formulas per true-flavor -- light mistag ~0.1%, c-jet ~10%, b-jet ~70% (configurable, pT-dependent).

**ROOT output trees**: `Jet`, `Electron`, `Muon`, `Photon`, `MissingET`, `Track`, `Tower`.

**Details ->** [Detector Simulation -- Delphes](detailed/10_detector_simulation_delphes.md)

---

## MadAnalysis5

Enable with `analysis=MadAnalysis5`. Reads LHE, HepMC, ROOT (Delphes), LHCO.

```
launch my_process
  shower=PYTHIA8
  detector=Delphes
  analysis=MadAnalysis5
  done
```

**Script-mode usage** (inside `./bin/ma5`):

```
import /path/to/events.lhe.gz
define mu = mu+ mu-
select (mu) PT > 25                  # kinematic cut
plot PT(mu[1]) 40 0 200 [logY]       # leading-muon pT
plot M(mu[1] mu[2]) 40 0 200 [logY]  # dimuon invariant mass
submit                                # produce plots + cutflow
```

Capabilities: kinematic cuts (pT, eta, MET, invariant mass, DeltaR), histograms, signal regions, recasting against published LHC analyses.

Output: ROOT/matplotlib histograms, cutflow tables, HTML reports.

**Details ->** [Analysis -- MadAnalysis5](detailed/11_analysis_madanalysis5.md)

---

## LHE Output Format

Location: `<PROC_DIR>/Events/run_01/unweighted_events.lhe.gz` (gzip-compressed XML).

**XML structure**: `<header>` (run cards), `<init>` (beam info + cross-section), repeated `<event>` blocks.

**`<init>` key fields**: `XSECUP` (cross-section, pb), `XERRUP` (uncertainty, pb), `IDBMUP` (beam PDG IDs), `EBMUP` (beam energies, GeV).

**Particle record columns** (one line per particle in `<event>`):

| Cols | Fields | Description |
|------|--------|-------------|
| 1 | IDUP | PDG ID |
| 2 | ISTUP | `-1` incoming, `+1` final-state, `+2` intermediate |
| 3-4 | MOTHUP | Mother indices (1-indexed) |
| 5-6 | ICOLUP | Color flow tags |
| 7-10 | PUP(1-4) | px, py, pz, E (GeV) |
| 11 | PUP(5) | Generated mass (GeV) |
| 12 | VTIMUP | Proper lifetime (mm/c) |
| 13 | SPINUP | `+1`/`-1` = helicity, `9.0` = not stored (default), `0.0` = averaged |

**SPINUP**: MG5 default is `9.0`. MadSpin assigns +/-1 helicities. Pythia8 (`TauDecays:mode=1`) reads SPINUP for tau polarization; falls back to internal calculation when 9.0.

**Weight normalization** (`event_norm`): `average` (default) -- average of weights = cross-section; `sum` -- sum = cross-section; `unity` -- weights = +/-1.

**Details ->** [Output Formats & LHE](detailed/15_output_formats_lhe.md)

---

## Python LHE Parsing

```python
import gzip
with gzip.open('unweighted_events.lhe.gz', 'rt') as f:
    in_init = False
    for line in f:
        if '<init>' in line:
            in_init = True; next(f); continue
        if '</init>' in line: break
        if in_init:
            parts = line.split()
            xsec, xerr = float(parts[0]), float(parts[1])  # pb
```

For events: inside `<event>`, skip XML tag lines (`<`), first data line is the event header (`NUP ...`), remaining lines are particles. Filter `ISTUP == 1` for final-state; columns 7-10 are `(px, py, pz, E)`.

**Details ->** [Output Formats & LHE](detailed/15_output_formats_lhe.md)

---

## Common Pitfalls

- **Delphes without Pythia8**: Delphes needs showered input; always set `shower=PYTHIA8` alongside `detector=Delphes`.
- **qCut <= xqcut**: MLM matching fails silently; `JetMatching:qCut` must be strictly > `xqcut`.
- **SPINUP = 9.0**: Means "not stored", not a physical helicity; only trust +/-1 from MadSpin or polarized generation.
- **Weight normalization**: Check `event_norm` before summing/averaging; the cross-section is always in `<init>` regardless.
- **Missing intermediates in LHE**: Status-2 particles only appear for on-shell resonances, not interfering diagrams.

---

## Cross-References

- [Configuration](configuration.md)
- [NLO & Matching](nlo_and_matching.md)
- [Decays & Widths](decays_and_widths.md)
- [Production & Troubleshooting](production_and_troubleshooting.md)
