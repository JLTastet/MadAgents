# 19 — PDFs and LHAPDF

Parton Distribution Functions (PDFs) describe the momentum distribution of quarks and gluons inside hadrons. Every hadron-collider simulation in MadGraph requires a PDF choice, which also determines the strong coupling constant alpha_s and its running.

## PDF Selection in the Run Card

Two parameters control the PDF:

```
nn23lo1   = pdlabel   ! PDF set
230000    = lhaid      ! if pdlabel=lhapdf, this is the LHAPDF set ID
```

### Built-In PDF Sets (`pdlabel`)

MG5 ships with several built-in PDF sets that require no external installation:

| `pdlabel` value | PDF set | LHAPDF ID | Order | Use case |
|-----------------|---------|-----------|-------|----------|
| `nn23lo1` | NNPDF2.3 LO (set 1) | 247000 | LO | Default for LO computations |
| `nn23lo` | NNPDF2.3 LO | 246800 | LO | Alternative LO set |
| `nn23nlo` | NNPDF2.3 NLO | 244800 | NLO | NLO computations (basic) |
| `cteq6l1` | CTEQ6L1 | — | LO | Legacy LO set |
| `cteq6_l` | CTEQ6L | — | LO | Legacy LO set |
| `cteq6_m` | CTEQ6M | — | NLO | Legacy NLO set |

These sets are compiled into MG5 and work without LHAPDF. However, they are older sets — for publication-quality results, use LHAPDF with a modern PDF set.

### Using LHAPDF (`pdlabel = lhapdf`)

For modern PDF sets (NNPDF3.1, NNPDF4.0, CT18, MSHT20, etc.), set:

```
lhapdf  = pdlabel
303400  = lhaid       ! LHAPDF set ID (e.g. NNPDF3.1 NLO)
```

This requires LHAPDF to be installed and configured. See [Installation & Setup](01_installation_setup.md) for installing LHAPDF via `install lhapdf6`.

The `lhaid` value is the LHAPDF ID number. Each PDF set has a unique ID. To find IDs, consult the [LHAPDF website](https://lhapdf.hepforge.org/pdfsets.html) or run:

```
lhapdf list
```

### Other `pdlabel` Options

| `pdlabel` | Description |
|-----------|-------------|
| `none` | No PDF (equivalent to `lpp = 0`). Used for fixed-energy lepton beams. |
| `iww` | Improved Weizsaecker-Williams approximation for photon emission from leptons. |
| `eva` | Effective Vector boson Approximation (W/Z/photon from fermions). |
| `edff` | Electron fragmentation function. |
| `chff` | Charged hadron fragmentation function. |

For lepton colliders, additional lepton-beam PDF sets may be available depending on the MG5 version — see [Lepton & Photon Colliders](22_lepton_photon_colliders.md).

## LO vs NLO PDF Consistency

A critical requirement: **the PDF order must match the perturbative order of the calculation**.

| Calculation | Required PDF |
|-------------|-------------|
| LO | LO PDF set |
| NLO | NLO PDF set |

Using an NLO PDF for an LO calculation (or vice versa) is inconsistent and gives unreliable results. The reason is that alpha_s is extracted from the PDF fit at the corresponding order — an LO PDF encodes LO alpha_s running, and an NLO PDF encodes NLO alpha_s running.

In practice:
- For LO: use `nn23lo1` (built-in) or an LO LHAPDF set
- For NLO: use `nn23nlo` (built-in) or an NLO LHAPDF set (recommended)

## Per-Beam PDF Configuration

MG5 supports different PDFs for each beam via hidden parameters:

```
lhapdf  = pdlabel1    ! PDF for beam 1
lhapdf  = pdlabel2    ! PDF for beam 2
```

These are hidden by default. When `pdlabel` is set, it applies to both beams. Per-beam PDFs are mainly relevant for asymmetric colliders (e.g., ep collisions where one beam is a proton and the other an electron).

## LHAPDF Configuration

The path to the LHAPDF installation is configured in `mg5_configuration.txt`:

```
lhapdf_py3 = /path/to/lhapdf-config
```

After installation, PDF sets must be downloaded. LHAPDF stores sets in a data directory (typically `share/LHAPDF/`). To install a new PDF set:

```bash
lhapdf install NNPDF31_nlo_as_0118
```

Or download manually from the LHAPDF website and place in the LHAPDF data directory.

## Flavor Number Consistency

The number of active quark flavors in the PDF must be consistent with the physics model:

- **5-flavor scheme** (default): b-quark is massless and appears in the proton PDF. Use `sm-no_b_mass` or set `maxjetflavor = 5`.
- **4-flavor scheme**: b-quark is massive and does NOT appear in the proton PDF. Use `sm` (default) and set `maxjetflavor = 4`. Must use a 4-flavor PDF set.

Inconsistency between the flavor scheme in the model and the PDF can lead to wrong results, particularly for processes with b-quarks in the initial state. See [Advanced Syntax](17_advanced_syntax.md) for details on flavor schemes.

## PDF Uncertainties

PDF uncertainties are evaluated using the `use_syst` mechanism in the run card. When enabled, MG5 stores reweighting information for PDF error sets in the LHE file. See [Systematics & Reweighting](13_systematics_reweighting.md) for details.

## Common Issues

1. **"LHAPDF not found"**: The `lhapdf_py3` path in `mg5_configuration.txt` is not set or points to a missing installation. Install via `install lhapdf6` in the MG5 interactive prompt.

2. **"PDF set not found"**: The requested `lhaid` corresponds to a PDF set that is not installed in the LHAPDF data directory. Download the set with `lhapdf install <setname>`.

3. **Wrong alpha_s**: If your cross-section disagrees with expectations, check that the PDF order matches the calculation order. The PDF choice automatically determines alpha_s.

4. **Manually set alpha_s ignored**: For proton beams (`lpp=1`), the `aS(MZ)` value in param_card Block SMINPUTS is **overridden** by the alpha_s value fitted to the chosen PDF set. This is physically correct — the PDF was extracted with a specific alpha_s. To study alpha_s variations, use the systematics reweighting module (see [Systematics & Reweighting](13_systematics_reweighting.md)), not the param_card.

## Cross-References

- **[← Reference: Configuration](configuration.md)**
- [Installation & Setup](01_installation_setup.md) — installing LHAPDF
- [Cards & Parameters](04_cards_and_parameters.md) — run_card PDF parameters
- [Systematics & Reweighting](13_systematics_reweighting.md) — PDF uncertainty evaluation
- [Advanced Syntax](17_advanced_syntax.md) — 4-flavor vs 5-flavor scheme
- [NLO Computations](06_nlo_computations.md) — NLO PDF requirements
- [Lepton & Photon Colliders](22_lepton_photon_colliders.md) — lepton beam PDFs
- [Troubleshooting](16_troubleshooting.md) — PDF-related errors
