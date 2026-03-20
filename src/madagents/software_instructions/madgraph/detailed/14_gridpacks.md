# 14 — Gridpacks

A gridpack is a self-contained tarball that packages the pre-compiled process code and optimized integration grids. It allows fast event generation on batch systems or computing clusters without needing a full MadGraph installation.

## Creating a Gridpack

Set `gridpack = True` in the run_card before launching:

```
import model sm
generate p p > z j
output zj_gridpack
launch zj_gridpack
  set run_card gridpack True
  set run_card ebeam1 6500
  set run_card ebeam2 6500
  done
```

MG5 performs the full integration (optimizing the integration grids) and produces a tarball instead of generating events. The gridpack file is located in:

```
zj_gridpack/run_01_gridpack.tar.gz
```

## Using a Gridpack

The gridpack is portable — copy it to any machine (even without MG5 installed) and generate events:

```bash
tar xzf run_01_gridpack.tar.gz
cd madevent
./run.sh 10000 42        # <nevents> <seed>
```

Arguments:
- First argument: number of events to generate
- Second argument: random seed (use different seeds for independent samples)

The output LHE file appears in `Events/GridRun_XXXX/`.

## Workflow for Large-Scale Production

1. **On a local machine**: Create the gridpack (one-time, may take minutes to hours depending on the process).
2. **Copy to cluster**: Transfer the tarball to your batch system nodes.
3. **Submit jobs**: Each job untars and runs `./run.sh <nevents> <seed>` with a unique seed.
4. **Merge**: Combine the output LHE files from all jobs.

This parallelizes event generation efficiently since the expensive integration step is done once.

## Seed Management

Each cluster job must use a **different random seed** to produce independent event samples. Common approaches:

- Use the job array index as the seed: `./run.sh 10000 $SLURM_ARRAY_TASK_ID`
- Use a hash of the job ID
- Use sequential seeds: 1, 2, 3, ...

Using the same seed produces identical events — which is useful for debugging but not for production.

## Limitations

- **Fixed parameters**: The param_card and run_card are frozen at gridpack creation time. To change physics parameters (masses, couplings, beam energy), you must create a new gridpack.
- **No NLO**: Gridpacks for NLO processes have limited support and may not work for all processes.
- **No shower**: The gridpack produces parton-level LHE events only. Showering and detector simulation must be done separately on the output.
- **Disk space**: Each gridpack can be 100 MB to several GB depending on the process complexity.

## Advanced: Modifying a Gridpack

For minor run_card changes (cuts, number of events), you can modify the cards inside the untarred gridpack before running:

```bash
tar xzf run_01_gridpack.tar.gz
cd madevent
# Edit Cards/run_card.dat
./run.sh 10000 42
```

However, changes to the physics model or process require regenerating the gridpack from scratch.

## Cross-References

- **[← Reference: Production & Troubleshooting](production_and_troubleshooting.md)**
- [Cards & Parameters](04_cards_and_parameters.md) — `gridpack = True` in run_card
- [Scripted Execution](05_scripted_execution.md) — gridpack creation scripts
- [Output Formats & LHE](15_output_formats_lhe.md) — LHE output from gridpacks
- [NLO Computations](06_nlo_computations.md) — NLO gridpack limitations
- [Process Syntax](02_process_syntax.md) — process generation for gridpacks
