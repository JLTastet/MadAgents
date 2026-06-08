# MadAgents — Claude Code installer data

The **data** the installer skills operate on (templates, the canonical renderer, examples).
The skills themselves live in the session dir [`../../claude_code/`](../../claude_code/) — run
Claude Code there and use `/install-madagents` or `/update-madagents`.

> Scope: Claude Code, default mode only. The verify / doc-editing / eval machinery
> from the top-level `claude_code/` setup is intentionally left out here.

## Layout

```
install/
  claude_code/                           # session dir — run claude here (.claude/ has the skills)
  data/claude_code/                      # ← this directory: the data the skills use
    scripts/
      render.sh                          # canonical renderer (shared by install, example, update)
    examples/
      build_example.sh                   # runnable end-to-end bare install + verify
      verify_install.sh                  # objective pass/fail checks for any install
    templates/
      .claude/
        CLAUDE.md                       # environment + operational context
        rules/{correctness,mandatory-reviews}.md
        agents/                         # worker + reviewer fleet (madgraph-operator assembled at render)
      prompts/
        system-prompt-append.md         # orchestrator role (passed via --append-system-prompt)
        madgraph-operator.header.md      # header for the assembled operator card
      start_madagents.bare.sh            # the launcher (copied verbatim)
      start_madagents.container.sh       # deferred — see CONTAINER_DEFERRED.md
  data/claude_code/CONTAINER_DEFERRED.md # what's dormant for the future container mode
```

## How the templates adapt to each mode

The agent simply works in the user's repo (its cwd), like a normal Claude Code session —
there is nothing to mount or describe. The templates carry one placeholder, `{{DOCS}}`
(the read-only MadGraph docs location), which the renderer substitutes to
`<repo>/.madagents/madgraph_docs`.

The templates also contain `<!-- container-only -->` blocks (and a `{{REPO}}` placeholder
inside them) for a future **container mode**. The bare renderer **strips those blocks
entirely**, so they never reach a bare install. See `CONTAINER_DEFERRED.md`.

## Assembled at install time (not stored here)

These are produced by the install step, not committed as templates:

1. **`agents/madgraph-operator.md`** — the operator card = `madgraph-operator.header.md`
   concatenated with the MadGraph software instructions
   (`src/madagents/software_instructions/madgraph.md`, heading levels shifted by +1).
   Mirrors `claude_code/scripts/build_madgraph_operator.py`.
2. **The MadGraph docs** — copied from `src/madagents/software_instructions/madgraph/`
   into `<repo>/.madagents/madgraph_docs`. Referenced from source, not duplicated here.
3. **A start script** — `start_madagents.sh` runs `claude --append-system-prompt …` in the
   repo. It **forwards args and env to Claude**: positional args pass through (`--resume`,
   `--continue`, …), and `--env KEY=VALUE` (repeatable) sets env vars.
4. **A manifest** — `<repo>/.madagents/install.json` records the installed version
   (`git describe`), source commit, mode, and paths. No file snapshot.

## Updating

`update-madagents` updates an existing install while preserving the user's edits via a
**3-way merge**. Because nothing pristine is stored locally (a user could edit it), the merge
**base** — the original of the installed version — is *reconstructed* by rendering that
version's templates from git history (`git archive <source_commit>`). Per file:

- `current == base` (untouched) → take the new version
- user-edited only → keep theirs
- both changed → `git merge-file` (clean merge keeps both; overlap → conflict markers + `.orig` backup)

This applies to **everything** installed (agents, rules, the CLAUDE.md block, docs, launcher).
The user's own files and content outside the CLAUDE block are never touched.
`install-madagents` detects an existing install (manifest or markers) and refers the user here.

## Status

Bare install + update are implemented and validated. Container mode is built but deferred
(see `CONTAINER_DEFERRED.md`). A Codex installer is separate, future work.
